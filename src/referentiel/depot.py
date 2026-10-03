"""Lecture et écriture des données de référence dans la zone brute.

Les réponses des services publics sont conservées telles qu'elles ont été
reçues, comme n'importe quelle autre source : la chaîne reste rejouable même si
un service disparaît.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

RACINE_PAR_DEFAUT = Path("data/raw/referentiel")

NOM_MANIFESTE = "manifeste.json"


def racine(base: Path | None = None) -> Path:
    return base or RACINE_PAR_DEFAUT


def chemin_feries(annee: int, base: Path | None = None) -> Path:
    return racine(base) / "feries" / f"annee={annee}.json"


def chemin_taux(debut: date, fin: date, devise: str, base: Path | None = None) -> Path:
    return racine(base) / "taux" / f"BRL-{devise}_{debut.isoformat()}_{fin.isoformat()}.json"


def ecrire(chemin: Path, contenu: object) -> None:
    """Écrit une réponse brute, telle que reçue."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")


def lire(chemin: Path) -> object:
    return json.loads(chemin.read_text(encoding="utf-8"))


def charger_feries(base: Path | None = None) -> dict[int, list[dict]]:
    """Tous les jours fériés conservés, année par année."""
    dossier = racine(base) / "feries"
    if not dossier.exists():
        return {}
    feries = {}
    for fichier in sorted(dossier.glob("annee=*.json")):
        annee = int(fichier.stem.split("=")[1])
        feries[annee] = lire(fichier)
    return feries


def charger_taux(base: Path | None = None) -> dict[str, dict[str, float]]:
    """Tous les taux conservés : devise, puis date, puis valeur."""
    dossier = racine(base) / "taux"
    if not dossier.exists():
        return {}
    taux: dict[str, dict[str, float]] = {}
    for fichier in sorted(dossier.glob("*.json")):
        reponse = lire(fichier)
        for jour, valeurs in reponse.get("rates", {}).items():
            for devise, valeur in valeurs.items():
                taux.setdefault(devise, {})[jour] = float(valeur)
    return taux
