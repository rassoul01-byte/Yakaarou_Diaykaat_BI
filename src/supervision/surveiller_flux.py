"""Relève et surveille le retard des lecteurs du bus.

Usage :
    docker compose exec app python -m supervision.surveiller_flux
    docker compose exec app python -m supervision.surveiller_flux --sans-relever

Code de sortie : 0 si aucun lecteur ne décroche, 1 sinon. C'est ce code que la
tâche de surveillance d'Airflow lit.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2
from confluent_kafka import KafkaException

from .flux import RELEVES_POUR_UNE_TENDANCE, anomalies, lire_tendances, relever


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Retard des lecteurs du bus.")
    analyseur.add_argument(
        "--sans-relever",
        action="store_true",
        help="lire l'historique sans prendre un nouveau relevé",
    )
    arguments = analyseur.parse_args(argv)

    try:
        if not arguments.sans_relever:
            releves = relever()
            print(f"\n{releves} lecteur(s) relevé(s).")
        lecteurs = lire_tendances()
    except KafkaException as erreur:
        print(f"ERREUR : le bus n'a pas répondu ({erreur})", file=sys.stderr)
        return 1
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire les relevés ({premiere})", file=sys.stderr)
        return 1

    if not lecteurs:
        print("\nAucun groupe de lecture sur le bus.")
        print("C'est l'état normal tant qu'aucun consommateur n'a démarré.\n")
        return 0

    print("\nRetard des lecteurs du bus\n")
    print(f"  {'Groupe':<30}{'Sujet':<26}{'Retard':>9}  Trois derniers relevés")
    for lecteur in lecteurs:
        suite = " → ".join(str(r) for r in reversed(lecteur.releves))
        marque = "!" if lecteur.decroche else " "
        print(
            f" {marque}{lecteur.groupe[:29]:<30}{lecteur.sujet[:25]:<26}{lecteur.retard:>9}  {suite}"
        )

    signalements = anomalies(lecteurs)
    print("\nCe qui mérite d'être regardé\n")
    if not signalements:
        print("  Aucun lecteur ne décroche.")
        print(
            f"  Un retard n'est signalé qu'après {RELEVES_POUR_UNE_TENDANCE} "
            "relevés consécutifs à la hausse."
        )
    for signalement in signalements:
        print(f"  ! {signalement}")
    print()

    return 1 if signalements else 0


if __name__ == "__main__":
    sys.exit(main())
