"""Dépôt d'une extraction dans la zone brute.

Ce fichier ne sait pas d'où viennent les données : il reçoit des fichiers, les
range dans une ingestion datée, écrit le manifeste et journalise l'exécution.

Le manifeste est construit par le module de la zone brute — celui d'Aissata —
plutôt que recalculé ici : la compatibilité avec sa vérification est ainsi
garantie par construction.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg2

from common.config import load_settings
from zone_brute.manifeste import construire_manifeste, ecrire_manifeste, lire_manifeste

from .boutique import TABLES, connexion, extraire_table

NOM_MANIFESTE = "manifeste.json"


@dataclass(frozen=True)
class Resultat:
    source: str
    ingestion: str | None  # None si rien n'a changé depuis la dernière fois
    lignes: int
    fichiers: int
    message: str

    @property
    def succes(self) -> bool:
        return True


def horodatage_ingestion(moment: datetime | None = None) -> str:
    """Identifiant d'une ingestion, au format du contrat de la zone brute."""
    return (moment or datetime.now(UTC)).strftime("%Y%m%dT%H%M%S")


def identifiant_libre(destination: Path, identifiant: str) -> str:
    """Décale l'horodatage d'une seconde tant que le dossier existe déjà.

    Deux acquisitions lancées dans la même seconde produiraient sinon le même
    nom d'ingestion. Le format du contrat de la zone brute — à la seconde près —
    est ainsi respecté sans jamais écraser une ingestion existante.
    """
    moment = datetime.strptime(identifiant, "%Y%m%dT%H%M%S")
    while (destination / f"ingestion={identifiant}").exists():
        moment += timedelta(seconds=1)
        identifiant = moment.strftime("%Y%m%dT%H%M%S")
    return identifiant


def racine_lots(racine_donnees: Path, source: str) -> Path:
    return racine_donnees / "raw" / "lots" / source


def derniere_ingestion(racine: Path) -> Path | None:
    """Dossier de l'ingestion la plus récente, ou None s'il n'y en a aucune."""
    if not racine.exists():
        return None
    ingestions = sorted(d for d in racine.glob("ingestion=*") if (d / NOM_MANIFESTE).exists())
    return ingestions[-1] if ingestions else None


def empreintes(manifeste: dict) -> dict:
    """Réduit un manifeste à ce qui permet de comparer deux extractions."""
    return {f["nom"]: f["sha256"] for f in manifeste.get("fichiers", [])}


def lignes_totales(manifeste: dict) -> int:
    """Nombre de lignes de données, en-têtes CSV déduits."""
    return sum(max(f.get("lignes", 0) - 1, 0) for f in manifeste.get("fichiers", []))


def acquerir(
    depuis: str | None = None,
    racine_donnees: Path = Path("data"),
    source: str = "boutique",
    tables: tuple = TABLES,
) -> Resultat:
    """Extrait la source et dépose le résultat dans la zone brute.

    Rien n'est écrit dans la zone brute si l'extraction est identique à la
    précédente : l'ingestion est préparée à l'écart, comparée, puis déplacée
    seulement si elle apporte quelque chose de nouveau.
    """
    debut = datetime.now(UTC)
    destination = racine_lots(racine_donnees, source)
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=destination) as brouillon:
        brouillon = Path(brouillon)
        with connexion() as cnx, cnx.cursor() as curseur:
            for table in tables:
                extraire_table(curseur, table, brouillon / f"{table}.csv", depuis)

        fichiers = sorted(brouillon.glob("*.csv"))
        identifiant = horodatage_ingestion(debut)
        manifeste = construire_manifeste(source, identifiant, fichiers)
        lignes = lignes_totales(manifeste)

        precedente = derniere_ingestion(destination)
        if precedente and empreintes(lire_manifeste(precedente / NOM_MANIFESTE)) == empreintes(
            manifeste
        ):
            _journaliser(source, debut, lignes, 0, "inchange", f"identique a {precedente.name}")
            return Resultat(
                source, None, lignes, len(fichiers), "aucun changement depuis la dernière ingestion"
            )

        identifiant = identifiant_libre(destination, identifiant)
        manifeste["ingestion"] = identifiant
        dossier = destination / f"ingestion={identifiant}"
        dossier.mkdir()
        for fichier in fichiers:
            shutil.move(str(fichier), dossier / fichier.name)
        ecrire_manifeste(manifeste, dossier / NOM_MANIFESTE)

    _journaliser(source, debut, lignes, lignes, "succes", f"ingestion {identifiant}")
    return Resultat(source, identifiant, lignes, len(fichiers), f"ingestion {identifiant} créée")


def _journaliser(
    source: str, debut: datetime, lues: int, ecrites: int, statut: str, message: str
) -> None:
    """Enregistre l'exécution dans staging.execution_log.

    Une panne de journalisation n'interrompt pas l'acquisition : les données
    sont déjà dans la zone brute, et les perdre pour une ligne de journal
    manquante serait absurde. L'incident est signalé, pas fatal.
    """
    try:
        with psycopg2.connect(load_settings().postgres_dsn) as cnx, cnx.cursor() as curseur:
            curseur.execute(
                """
                INSERT INTO staging.execution_log
                    (pipeline, etape, source, demarre_a, termine_a,
                     lignes_lues, lignes_ecrites, lignes_rejetees, statut, message)
                VALUES ('acquisition', 'extraction', %s, %s, now(), %s, %s, 0, %s, %s)
                """,
                (source, debut, lues, ecrites, statut, message),
            )
    except psycopg2.Error as erreur:
        print(f"AVERTISSEMENT : exécution non journalisée ({erreur.__class__.__name__})")
