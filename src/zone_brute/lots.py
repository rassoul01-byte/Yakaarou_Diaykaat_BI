"""Listage et vérification des ingestions par lots de la zone brute.

Ce module ne crée pas d'ingestions — c'est le rôle du Livrable 1
(src/acquisition/lots.py, Mouhameth). Il liste ce qui existe déjà sous
data/raw/lots/ et vérifie que rien n'a été altéré depuis, en
recalculant les empreintes enregistrées dans chaque manifeste.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .manifeste import lire_manifeste, sha256_fichier

RACINE_LOTS_DEFAUT = Path("data/raw/lots")


@dataclass
class Ingestion:
    source: str
    horodatage: str
    dossier: Path
    manifeste: dict


def lister_ingestions(racine: Path = RACINE_LOTS_DEFAUT) -> List[Ingestion]:
    """Retourne toutes les ingestions trouvées sous
    data/raw/lots/<source>/ingestion=<horodatage>/."""
    ingestions: List[Ingestion] = []
    if not racine.exists():
        return ingestions
    for dossier_source in sorted(racine.iterdir()):
        if not dossier_source.is_dir():
            continue
        for dossier_ingestion in sorted(dossier_source.glob("ingestion=*")):
            chemin_manifeste = dossier_ingestion / "manifeste.json"
            if not chemin_manifeste.exists():
                continue
            manifeste = lire_manifeste(chemin_manifeste)
            horodatage = dossier_ingestion.name.split("=", 1)[1]
            ingestions.append(
                Ingestion(
                    source=dossier_source.name,
                    horodatage=horodatage,
                    dossier=dossier_ingestion,
                    manifeste=manifeste,
                )
            )
    return ingestions


@dataclass
class Anomalie:
    ingestion: Ingestion
    fichier: str
    attendu: str
    trouve: Optional[str]


def verifier_ingestions(racine: Path = RACINE_LOTS_DEFAUT) -> List[Anomalie]:
    """Recalcule l'empreinte de chaque fichier listé dans chaque
    manifeste et la compare au SHA-256 enregistré. Toute différence, ou
    tout fichier manquant, est remontée comme anomalie."""
    anomalies: List[Anomalie] = []
    for ingestion in lister_ingestions(racine):
        for entree in ingestion.manifeste.get("fichiers", []):
            chemin_fichier = ingestion.dossier / entree["nom"]
            if not chemin_fichier.exists():
                anomalies.append(Anomalie(ingestion, entree["nom"], entree["sha256"], None))
                continue
            empreinte = sha256_fichier(chemin_fichier)
            if empreinte != entree["sha256"]:
                anomalies.append(Anomalie(ingestion, entree["nom"], entree["sha256"], empreinte))
    return anomalies
