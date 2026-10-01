"""Utilitaires de manifeste pour la zone brute (Livrable 4, Sprint 1).

Un manifeste décrit, pour un ensemble de fichiers immuables de la zone
brute, leur nom, leur nombre de lignes, leur taille en octets et leur
empreinte SHA-256. Il sert à vérifier plus tard qu'aucun fichier n'a
été altéré. Voir docs/contrats/zone_brute.md.

Le champ `lignes` compte des lignes de données, pas des lignes physiques :
l'en-tête d'un CSV n'est pas compté, et un enregistrement dont un champ
contient un saut de ligne (commentaires d'avis) compte pour un.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


def sha256_fichier(chemin: Path, taille_bloc: int = 1024 * 1024) -> str:
    """Empreinte SHA-256 d'un fichier, lu par blocs pour ne pas charger
    de gros fichiers entièrement en mémoire."""
    empreinte = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(taille_bloc), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def compter_lignes(chemin: Path) -> int:
    """Compte les lignes physiques d'un fichier texte (CSV ou JSONL)."""
    with open(chemin, "rb") as f:
        return sum(1 for _ in f)


def compter_enregistrements(chemin: Path) -> int:
    """Compte les lignes de données d'un fichier, valeur du champ `lignes`.

    CSV : enregistrements hors en-tête, lus par le module csv pour qu'un
    champ entre guillemets sur plusieurs lignes ne soit compté qu'une fois.
    Autres formats (JSONL) : un enregistrement par ligne physique.
    """
    if chemin.suffix.lower() != ".csv":
        return compter_lignes(chemin)
    with open(chemin, encoding="utf-8", newline="") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


@dataclass
class EntreeFichier:
    nom: str
    lignes: int
    octets: int
    sha256: str

    @classmethod
    def depuis_fichier(cls, chemin: Path) -> EntreeFichier:
        return cls(
            nom=chemin.name,
            lignes=compter_enregistrements(chemin),
            octets=chemin.stat().st_size,
            sha256=sha256_fichier(chemin),
        )


def construire_manifeste(source: str, identifiant: str, fichiers: Iterable[Path]) -> dict:
    """Construit un manifeste au format du contrat de zone brute.

    `identifiant` est l'horodatage d'ingestion pour un lot, ou
    `<date>T<heure>` pour une tranche d'événements.
    """
    return {
        "source": source,
        "ingestion": identifiant,
        "fichiers": [asdict(EntreeFichier.depuis_fichier(p)) for p in fichiers],
    }


def ecrire_manifeste(manifeste: dict, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(manifeste, f, ensure_ascii=False, indent=2)


def lire_manifeste(chemin: Path) -> dict:
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)
