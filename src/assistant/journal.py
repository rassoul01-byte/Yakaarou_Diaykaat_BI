"""Le journal : une ligne par échange, pour mesurer le taux de réponses ancrées (F5.7).

Un client peut taper son numéro de commande, son e-mail ou son téléphone dans la question :
tout est **masqué avant d'être écrit**. Le journal ne contient jamais de donnée personnelle.

Format d'une ligne (JSON) — docs/contrats/assistant.md, §5 :
    horodatage, question (masquée), refus, motif, passages_cites, score_meilleur,
    suggestions, duree_ms, retrouveur, origine, reformulation (masquée)
Un refus poli est une réponse ancrée (dictionnaire) : `refus` et `motif` permettent de le
compter sans le confondre avec une affirmation.

`origine` et `reformulation` disent D'OÙ vient la question :

    saisie      l'utilisateur l'a tapée lui-même ; `reformulation` est nulle.
    exemple     il a cliqué une question d'exemple de la page ; `reformulation` est nulle.
    suggestion  il a tapé autre chose, l'assistant a hésité, il a cliqué une suggestion.
                `reformulation` porte alors SA formulation, celle que la base n'a pas su
                traiter directement.

Une ligne `suggestion` est donc une étiquette posée par un humain : « cette formulation
voulait dire ce passage ». C'est la matière première pour enrichir la base documentaire
(voir `documentaire.mots_cles`) sans jamais générer de texte.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # `assistant` importe ce module : la dépendance n'existe qu'au typage.
    from .assistant import Reponse

JOURNAL_DEFAUT = Path("data/assistant/journal.jsonl")
JOURNAL_EVALUATION = Path("data/assistant/journal_evaluation.jsonl")

# Valeurs stables : écrites dans le journal, contrôlées par le chargeur et par la base.
ORIGINES = ("saisie", "exemple", "suggestion")
ORIGINE_PAR_DEFAUT = "saisie"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_TELEPHONE = re.compile(r"\+?\d[\d .\-]{7,}\d")
_IDENTIFIANT = re.compile(r"\b(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{5,}\b")
_NOMBRE = re.compile(r"\b\d{4,}\b")


def masquer(texte: str) -> str:
    """Remplace e-mails, téléphones, identifiants et longs nombres par une étiquette."""
    texte = _EMAIL.sub("[email]", texte)
    texte = _TELEPHONE.sub("[telephone]", texte)
    texte = _NOMBRE.sub("[nombre]", texte)  # avant les identifiants : « 123456 » est un nombre
    return _IDENTIFIANT.sub("[identifiant]", texte)


def entree(
    reponse: Reponse,
    retrouveur: str,
    maintenant: datetime | None = None,
    *,
    origine: str = ORIGINE_PAR_DEFAUT,
    reformulation: str | None = None,
) -> dict:
    """Une ligne du journal. `origine` inconnue lève plutôt que d'écrire n'importe quoi."""
    if origine not in ORIGINES:
        raise ValueError(f"origine inconnue : {origine!r} (attendu : {', '.join(ORIGINES)})")
    return {
        "horodatage": (maintenant or datetime.now(UTC)).isoformat(timespec="seconds"),
        "question": masquer(reponse.question),
        "refus": reponse.refus,
        "motif": reponse.motif,
        "passages_cites": [p.id for p in reponse.passages],
        "score_meilleur": reponse.passages[0].score if reponse.passages else None,
        "suggestions": [p.id for p in reponse.suggestions],
        "duree_ms": reponse.duree_ms,
        "retrouveur": retrouveur,
        "origine": origine,
        # Masquée comme la question : c'est aussi du texte tapé par un client.
        "reformulation": masquer(reformulation) if reformulation else None,
    }


class JournalFichier:
    """Ajoute une ligne JSON par échange. Le chemin vient de ASSISTANT_JOURNAL, sinon du défaut."""

    def __init__(self, chemin: Path | str | None = None) -> None:
        self.chemin = Path(chemin or os.environ.get("ASSISTANT_JOURNAL") or JOURNAL_DEFAUT)

    def enregistrer(
        self,
        reponse: Reponse,
        retrouveur: str,
        *,
        origine: str = ORIGINE_PAR_DEFAUT,
        reformulation: str | None = None,
    ) -> None:
        ligne = entree(reponse, retrouveur, origine=origine, reformulation=reformulation)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with self.chemin.open("a", encoding="utf-8") as fichier:
            fichier.write(json.dumps(ligne, ensure_ascii=False) + "\n")


class JournalMemoire:
    """Pour les tests : garde les entrées en mémoire."""

    def __init__(self) -> None:
        self.entrees: list[dict] = []

    def enregistrer(
        self,
        reponse: Reponse,
        retrouveur: str,
        *,
        origine: str = ORIGINE_PAR_DEFAUT,
        reformulation: str | None = None,
    ) -> None:
        self.entrees.append(
            entree(reponse, retrouveur, origine=origine, reformulation=reformulation)
        )
