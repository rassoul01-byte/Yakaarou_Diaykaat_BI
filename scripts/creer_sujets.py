"""Crée les sujets Kafka du contrat d'événement.

Sans effet sur les sujets qui existent déjà : le script peut être relancé autant
de fois que voulu.

Usage :
    docker compose exec app python scripts/creer_sujets.py

Code de sortie : 0 si tous les sujets existent à la fin, 1 sinon.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from confluent_kafka import KafkaException  # noqa: E402

from common.bus import PARTITIONS, SUJETS, creer_sujets  # noqa: E402


def main() -> int:
    try:
        resultats = creer_sujets()
    except KafkaException as erreur:
        print(f"ERREUR : le bus est injoignable ou a refusé la demande ({erreur})", file=sys.stderr)
        return 1

    print(f"Sujets du contrat ({PARTITIONS} partitions chacun) :")
    for nom in SUJETS:
        print(f"  {nom:<24} {resultats.get(nom, '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
