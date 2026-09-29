"""Acquisition de la source SQL vers la zone brute.

Usage :
    docker compose exec app python -m acquisition
    docker compose exec app python -m acquisition --depuis 2017-01-01
    docker compose exec app python -m acquisition --racine data

Code de sortie : 0 si l'acquisition s'est bien passée, 1 sinon.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

from .ingestion import acquerir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extrait la base boutique vers la zone brute.")
    parser.add_argument("--source", default="boutique", help="nom de la source (défaut : boutique)")
    parser.add_argument(
        "--depuis",
        metavar="AAAA-MM-JJ",
        help="n'extraire que les commandes passées à partir de cette date",
    )
    parser.add_argument(
        "--racine", default="data", type=Path, help="racine des données (défaut : data)"
    )
    args = parser.parse_args(argv)

    try:
        resultat = acquerir(depuis=args.depuis, racine_donnees=args.racine, source=args.source)
    except psycopg2.Error as erreur:
        print(
            f"ERREUR : la base source est injoignable ou a refusé la requête ({erreur})",
            file=sys.stderr,
        )
        return 1

    print(f"Source       : {resultat.source}")
    print(f"Fichiers     : {resultat.fichiers}")
    print(f"Lignes lues  : {resultat.lignes}")
    print(f"Résultat     : {resultat.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
