"""CLI F1.9 — table de correspondance des produits."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

from .correspondance import (
    MAPPING_PATH,
    CorrespondanceError,
    executer,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Construit la table de correspondance Olist / Rakuten."
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=MAPPING_PATH,
        help="Fichier CSV du mapping des catégories.",
    )

    args = parser.parse_args(argv)

    try:
        executer(args.mapping)
    except CorrespondanceError as erreur:
        print(f"ERREUR F1.9 : {erreur}", file=sys.stderr)
        return 1
    except psycopg2.Error as erreur:
        print(
            f"ERREUR F1.9 : problème PostgreSQL ({erreur})",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
