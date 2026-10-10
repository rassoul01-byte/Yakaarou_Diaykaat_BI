"""Les passages : la foire aux questions sous la forme que l'assistant manipule.

Un passage est une ligne de `docs/documentaire/faq.jsonl` (contrat F5.2, §2).
Le chargement refuse un corpus que `documentaire.verifier` rejette : l'assistant
ne cite jamais une source qui n'a pas passé le contrôle.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path

from documentaire.verifier import charger as lire_lignes
from documentaire.verifier import verifier as controler

FAQ = Path(__file__).resolve().parents[2] / "docs" / "documentaire" / "faq.jsonl"


class ErreurCorpus(RuntimeError):
    """La foire aux questions n'est pas exploitable."""


@dataclass(frozen=True)
class Passage:
    id: str
    theme: str
    question: str
    reponse: str
    source: str
    score: float = 0.0  # proximité avec la question posée, entre 0 et 1

    def avec_score(self, score: float) -> Passage:
        return replace(self, score=float(score))

    def en_dict(self) -> dict:
        return asdict(self)


def charger(chemin: Path = FAQ) -> list[Passage]:
    """Les passages du fichier, après contrôle. Lève ErreurCorpus si le fichier est invalide."""
    try:
        lignes, erreurs = lire_lignes(chemin)
    except OSError as erreur:
        raise ErreurCorpus(f"{chemin.name} illisible ({erreur.strerror or erreur})") from erreur
    erreurs = [*erreurs, *controler(lignes)]
    if erreurs:
        raise ErreurCorpus(f"{chemin.name} : {erreurs[0]} ({len(erreurs)} erreur(s))")
    return [
        Passage(
            id=e["id"],
            theme=e["theme"],
            question=e["question"],
            reponse=e["reponse"],
            source=e["source"],
        )
        for _, e in lignes
    ]
