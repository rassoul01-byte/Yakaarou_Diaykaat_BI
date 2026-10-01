"""Affiche l'état du bus d'événements : les sujets, leur volume, et le retard des lecteurs.

Le retard d'un groupe est le nombre de messages publiés qu'il n'a pas encore lus.
Un retard qui grandit sans cesse signale un lecteur arrêté ou trop lent : c'est
la première brique de la surveillance du flux (F6.3).

Usage :
    docker compose exec app python scripts/etat_bus.py
    docker compose exec app python scripts/etat_bus.py --surveiller 5     # toutes les 5 secondes

Code de sortie : 0 si le bus répond, 1 sinon.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from confluent_kafka import KafkaException  # noqa: E402

from common.bus import etat_du_bus  # noqa: E402


def afficher(sujets: list, retards: list) -> None:
    print(f"\nÉtat du bus — {datetime.now():%H:%M:%S}\n")
    print(f"  {'Sujet':<26}{'Partitions':>11}{'Messages':>12}")
    for s in sujets:
        print(f"  {s.nom:<26}{s.partitions:>11}{s.messages:>12}")
    if not sujets:
        print("  (aucun sujet — lancer scripts/creer_sujets.py)")

    print(f"\n  {'Groupe de lecture':<30}{'Sujet':<26}{'Retard':>8}")
    for r in retards:
        print(f"  {r.groupe:<30}{r.sujet:<26}{r.retard:>8}")
    if not retards:
        print("  (aucun groupe de lecture pour l'instant)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="État du bus d'événements.")
    parser.add_argument(
        "--surveiller",
        type=float,
        metavar="SECONDES",
        help="rafraîchir l'affichage à intervalle régulier, jusqu'à Ctrl+C",
    )
    args = parser.parse_args(argv)

    try:
        while True:
            afficher(*etat_du_bus())
            if not args.surveiller:
                return 0
            time.sleep(args.surveiller)
    except KafkaException as erreur:
        print(f"ERREUR : le bus ne répond pas ({erreur})", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
