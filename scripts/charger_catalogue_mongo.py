"""Remplit la base documentaire `catalogue` depuis le fichier source.

À lancer une fois, comme charger_boutique.py pour la base de la boutique. La
collection est vidée puis remplie : relancer donne exactement la même chose.

Usage :
    docker compose exec app python scripts/charger_catalogue_mongo.py
    docker compose exec app python scripts/charger_catalogue_mongo.py --fichier <chemin>

Code de sortie : 0 si la collection est remplie, 1 sinon.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymongo.errors import PyMongoError  # noqa: E402

from acquisition.catalogue import COLLECTION, charger, connexion, nom_base  # noqa: E402
from common.config import load_settings  # noqa: E402

FICHIER_PAR_DEFAUT = "data/sources/rakuten/rakuten_catalogue_produits.csv"


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Charge le catalogue dans MongoDB.")
    analyseur.add_argument(
        "--fichier",
        type=Path,
        default=Path(os.getenv("CATALOGUE_RAKUTEN", FICHIER_PAR_DEFAUT)),
        help="fichier source du catalogue",
    )
    arguments = analyseur.parse_args(argv)

    if not arguments.fichier.exists():
        print(f"ERREUR : fichier introuvable : {arguments.fichier}", file=sys.stderr)
        print("Lancer d'abord : python scripts/download_data.py", file=sys.stderr)
        return 1

    try:
        client = connexion()
        base = client[nom_base(load_settings().mongo_uri)]
        inseres = charger(arguments.fichier, base)
        sans_description = base[COLLECTION].count_documents({"description": {"$exists": False}})
    except PyMongoError as erreur:
        print(f"ERREUR : MongoDB n'a pas répondu ({erreur.__class__.__name__})", file=sys.stderr)
        return 1
    finally:
        try:
            client.close()
        except NameError:
            pass

    part = 100 * sans_description / inseres if inseres else 0
    print(f"Collection {COLLECTION} remplie depuis {arguments.fichier}")
    print(f"  fiches insérées          : {inseres}")
    print(f"  sans champ description   : {sans_description} ({part:.1f} %)")
    print("\nLe champ est absent, pas vide : c'est ce que le contrôle de qualité lira.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
