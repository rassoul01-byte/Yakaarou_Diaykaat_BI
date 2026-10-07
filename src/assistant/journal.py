"""Le journal : une ligne par échange, pour mesurer le taux de réponses ancrées (F5.7).

Un client peut taper son numéro de commande, son e-mail ou son téléphone dans la question :
tout est **masqué avant d'être écrit**. Le journal ne contient jamais de donnée personnelle.

Format d'une ligne (JSON) — docs/contrats/assistant.md, §5 :
    horodatage, question (masquée), refus, motif, passages_cites, score_meilleur,
    suggestions, duree_ms, retrouveur
Un refus poli est une réponse ancrée (dictionnaire) : `refus` et `motif` permettent de le
compter sans le confondre avec une affirmation.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from .assistant import Reponse

JOURNAL_DEFAUT = Path("data/assistant/journal.jsonl")

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


def entree(reponse: Reponse, retrouveur: str, maintenant: datetime | None = None) -> dict:
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
    }


class JournalFichier:
    """Ajoute une ligne JSON par échange. Le chemin vient de ASSISTANT_JOURNAL, sinon du défaut."""

    def __init__(self, chemin: Path | str | None = None) -> None:
        self.chemin = Path(chemin or os.environ.get("ASSISTANT_JOURNAL") or JOURNAL_DEFAUT)

    def enregistrer(self, reponse: Reponse, retrouveur: str) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with self.chemin.open("a", encoding="utf-8") as fichier:
            fichier.write(json.dumps(entree(reponse, retrouveur), ensure_ascii=False) + "\n")


class JournalMemoire:
    """Pour les tests : garde les entrées en mémoire."""

    def __init__(self) -> None:
        self.entrees: list[dict] = []

    def enregistrer(self, reponse: Reponse, retrouveur: str) -> None:
        self.entrees.append(entree(reponse, retrouveur))
