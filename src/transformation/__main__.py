"""Transformation des données validées — F1.7, F1.8 (Sprint 2).

Usage :
    docker compose exec app python -m transformation --source olist
    docker compose exec app python -m transformation --source rakuten

Olist : déduplication de la géolocalisation, normalisation du libellé de
catégorie (clé de rapprochement du Sprint 3).
Rakuten : décodage du balisage, détection de langue.

Code de sortie : 0 si la transformation s'est bien passée, 1 sinon.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2

from .pipeline import (
    connexion,
    journaliser,
    transformer_categories,
    transformer_geolocation,
    transformer_rakuten,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Applique les transformations à la zone intermédiaire."
    )
    parser.add_argument("--source", choices=["olist", "rakuten"], required=True)
    args = parser.parse_args(argv)

    try:
        cnx = connexion()
    except psycopg2.Error as erreur:
        print(f"ERREUR : base injoignable ou a refusé la requête ({erreur})", file=sys.stderr)
        return 1

    try:
        if args.source == "olist":
            resultats = [transformer_geolocation(cnx), transformer_categories(cnx)]
        else:
            resultats = [transformer_rakuten(cnx)]
    except psycopg2.Error as erreur:
        cnx.rollback()
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    finally:
        cnx.close()

    for resultat in resultats:
        print(
            f"{resultat.etape:<20} lues={resultat.lignes_lues:<8} "
            f"écrites={resultat.lignes_ecrites:<8} supprimées={resultat.lignes_supprimees:<8}"
        )
        print(f"  {resultat.message}")
        journaliser(resultat, args.source)

    return 0


if __name__ == "__main__":
    sys.exit(main())
