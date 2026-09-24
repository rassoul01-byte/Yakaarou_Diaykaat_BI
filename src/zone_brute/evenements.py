"""Archivage horaire et rejeu des événements de navigation (flux F-10).

Ce module ne parle pas à Kafka directement : les fonctions ci-dessous
reçoivent des événements déjà consommés (`archiver_evenements`) ou une
fonction de publication déjà connectée (`rejouer_tranche`). C'est le
CLI (voir __main__.py) qui fait le lien avec common.bus (Livrable 3,
Ndeye Penda). Cette séparation permet de tester l'archivage et le
rejeu sans avoir besoin de Kafka.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

from .manifeste import compter_lignes, ecrire_manifeste, sha256_fichier

RACINE_EVENEMENTS_DEFAUT = Path("data/raw/evenements/navigation.evenements")
SUJET_SOURCE = "navigation.evenements"
SUJET_REJEU = "navigation.rejeu"


def _chemin_tranche(dossier_jour: Path, heure: str) -> Path:
    return dossier_jour / f"heure={heure}.jsonl"


def _chemin_manifeste(dossier_jour: Path, heure: str) -> Path:
    return dossier_jour / f"heure={heure}.manifeste.json"


def _decouper_horodatage(horodatage_iso: str) -> Tuple[str, str]:
    """Retourne (date, heure) au format AAAA-MM-JJ et HH à partir d'un
    horodatage ISO 8601 d'événement, en UTC."""
    dt = datetime.fromisoformat(horodatage_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H")


def archiver_evenements(
    evenements: Iterable[dict],
    racine: Path = RACINE_EVENEMENTS_DEFAUT,
) -> List[Path]:
    """Ajoute chaque événement à la tranche horaire correspondant à son
    horodatage (data/raw/evenements/.../date=.../heure=HH.jsonl), puis
    réécrit le manifeste de chaque tranche touchée.

    Le regroupement se fait sur l'horodatage de l'ÉVÉNEMENT, pas sur
    l'heure d'archivage. Un fichier existant est complété par ajout,
    jamais réécrit (règle d'or de la zone brute).

    Retourne la liste des manifestes écrits ou mis à jour.
    """
    tranches_touchees: Dict[Tuple[str, str], Path] = {}
    for evenement in evenements:
        date, heure = _decouper_horodatage(evenement["horodatage"])
        dossier_jour = racine / f"date={date}"
        dossier_jour.mkdir(parents=True, exist_ok=True)
        chemin = _chemin_tranche(dossier_jour, heure)
        with open(chemin, "a", encoding="utf-8") as f:
            f.write(json.dumps(evenement, ensure_ascii=False) + "\n")
        tranches_touchees[(date, heure)] = chemin

    chemins_manifestes = []
    for (date, heure), chemin in tranches_touchees.items():
        manifeste = {
            "source": SUJET_SOURCE,
            "ingestion": f"{date}T{heure}",
            "fichiers": [
                {
                    "nom": chemin.name,
                    "lignes": compter_lignes(chemin),
                    "octets": chemin.stat().st_size,
                    "sha256": sha256_fichier(chemin),
                }
            ],
        }
        chemin_manifeste = _chemin_manifeste(chemin.parent, heure)
        ecrire_manifeste(manifeste, chemin_manifeste)
        chemins_manifestes.append(chemin_manifeste)
    return chemins_manifestes


def rejouer_tranche(
    date: str,
    heure: str,
    publieur: Callable[[str, str, dict], None],
    racine: Path = RACINE_EVENEMENTS_DEFAUT,
) -> int:
    """Relit la tranche archivée date=<date>/heure=<heure> et republie
    chaque événement sur navigation.rejeu via `publieur(sujet, cle,
    message)`. Un sujet à part évite que les événements rejoués soient
    comptés deux fois par les consommateurs du flux normal.

    Retourne le nombre d'événements republiés. Lève FileNotFoundError
    si la tranche n'existe pas.
    """
    chemin = _chemin_tranche(racine / f"date={date}", heure)
    if not chemin.exists():
        raise FileNotFoundError(
            f"Aucune tranche archivée pour date={date} heure={heure} : {chemin}"
        )
    compte = 0
    with open(chemin, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            evenement = json.loads(ligne)
            cle = evenement.get("id_session") or evenement.get("id_evenement")
            publieur(SUJET_REJEU, cle, evenement)
            compte += 1
    return compte
