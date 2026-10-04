"""Acquisition des sources vers la zone brute.

Usage :
    docker compose exec app python -m acquisition
    docker compose exec app python -m acquisition --depuis 2017-01-01
    docker compose exec app python -m acquisition --racine data
    docker compose exec app python -m acquisition --source rakuten

La source « boutique » (défaut) est une base SQL. Toute autre source est une
source fichier : ses CSV livrés dans data/sources/<source>/ sont copiés à
l'identique dans la zone brute.

Code de sortie : 0 si l'acquisition s'est bien passée, 1 sinon.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

from .ingestion import acquerir, acquerir_catalogue, acquerir_fichiers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dépose une source dans la zone brute.")
    parser.add_argument(
        "--source",
        default="boutique",
        help="boutique (base SQL, défaut) ou une source fichier, par exemple rakuten",
    )
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
        if args.source == "catalogue":
            resultat = acquerir_catalogue(racine_donnees=args.racine)
        elif args.source == "boutique":
            resultat = acquerir(depuis=args.depuis, racine_donnees=args.racine)
        else:
            resultat = acquerir_fichiers(args.source, racine_donnees=args.racine)
    except FileNotFoundError as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
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
