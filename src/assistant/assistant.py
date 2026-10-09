"""L'assistant : une question entre, une réponse citée ou un refus sort.

    repondre(question, retrouveur)  ->  Reponse

Invariant, vérifié à la construction d'une Reponse : une réponse qui n'est pas un refus
est exactement le texte de ses passages, avec leur citation ; un refus ne cite rien.
Il est donc impossible de produire une affirmation sans source.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import compositeur, garde_fous
from . import journal as journal_module
from .passages import Passage
from .retrouveur import Retrouveur


@dataclass(frozen=True)
class Reponse:
    question: str
    refus: bool
    motif: str | None
    reponse: str
    passages: list[Passage] = field(default_factory=list)  # ceux qui fondent la réponse
    suggestions: list[Passage] = field(default_factory=list)  # proposés quand l'assistant hésite
    duree_ms: int = 0

    def __post_init__(self) -> None:
        if self.refus:
            if self.passages or self.motif is None:
                raise ValueError("un refus porte un motif et ne cite aucun passage")
        else:
            if not self.passages or self.motif is not None or self.suggestions:
                raise ValueError("une réponse cite au moins un passage et n'a pas de motif")
            if self.reponse != " ".join(compositeur.composer(p) for p in self.passages):
                raise ValueError("une réponse est le texte de ses passages, rien d'autre")

    def en_dict(self) -> dict:
        """Le format publié dans docs/contrats/assistant.md, §3."""
        return {
            "question": self.question,
            "refus": self.refus,
            "motif": self.motif,
            "reponse": self.reponse,
            "passages": [
                {
                    "id": p.id,
                    "theme": p.theme,
                    "question": p.question,
                    "source": p.source,
                    "score": p.score,
                }
                for p in self.passages
            ],
            "suggestions": [{"id": p.id, "question": p.question} for p in self.suggestions],
            "duree_ms": self.duree_ms,
        }


def _refus(
    question: str, motif: str, debut: float, suggestions: list[Passage] | None = None
) -> Reponse:
    return Reponse(
        question=question,
        refus=True,
        motif=motif,
        reponse=compositeur.refuser(motif),
        suggestions=suggestions or [],
        duree_ms=round((time.perf_counter() - debut) * 1000),
    )


def repondre(
    question: str,
    retrouveur: Retrouveur,
    *,
    k: int = 3,
    journal=None,
    seuils: garde_fous.Seuils | None = None,
    origine: str = journal_module.ORIGINE_PAR_DEFAUT,
    reformulation: str | None = None,
) -> Reponse:
    """Répond à une question, ou refuse. Un refus est une réponse, pas une exception.

    Les pannes techniques (la recherche qui ne répond pas) remontent en exceptions : une
    panne n'est pas un refus et ne doit pas être comptée comme telle.

    `origine` et `reformulation` ne changent RIEN à la réponse : ils ne servent qu'au
    journal, pour savoir d'où venait la question (voir `journal.py`).
    """
    debut = time.perf_counter()
    texte = (question or "").strip()

    motif = garde_fous.filtre_avant(texte)
    if motif:
        reponse = _refus(texte, motif, debut)
    else:
        decision = garde_fous.decider(retrouveur.retrouver(texte, k), seuils or retrouveur.seuils)
        if decision.retenu:
            reponse = Reponse(
                question=texte,
                refus=False,
                motif=None,
                reponse=compositeur.composer(decision.retenu),
                passages=[decision.retenu],
                duree_ms=round((time.perf_counter() - debut) * 1000),
            )
        else:
            reponse = _refus(texte, decision.motif, debut, decision.suggestions)

    if journal is not None:
        journal.enregistrer(
            reponse,
            retrouveur=retrouveur.nom,
            origine=origine,
            reformulation=reformulation,
        )
    return reponse
