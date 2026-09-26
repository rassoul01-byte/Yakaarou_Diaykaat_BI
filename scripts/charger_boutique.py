"""Remplit la base « boutique » à partir des fichiers de data/sources/olist/.

Ce script ne fait PAS partie du pipeline : il simule l'existence du système de
gestion de l'e-commerçant. Il se lance une fois, à l'installation. Ensuite, la
plateforme ne connaît plus les fichiers : elle ne connaît que la base.

Usage :
    docker compose exec app python scripts/charger_boutique.py
    docker compose exec app python scripts/charger_boutique.py --recharger

Code de sortie : 0 si la base est remplie et conforme, 1 sinon.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import psycopg2  # noqa: E402

from acquisition.boutique import BASE_PAR_DEFAUT, dsn_boutique, dsn_maintenance  # noqa: E402

RACINE_PROJET = Path(__file__).resolve().parent.parent
SCHEMA = RACINE_PROJET / "sql" / "boutique" / "schema.sql"

# À chaque table de la boutique, le fichier livré qui la remplit.
FICHIERS = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def creer_base_si_absente(base: str = BASE_PAR_DEFAUT) -> bool:
    """Crée la base source si elle n'existe pas. Renvoie True si elle a été créée."""
    # Pas de « with » sur la connexion ici : il ouvre une transaction, et
    # CREATE DATABASE refuse de s'exécuter à l'intérieur d'une transaction.
    cnx = psycopg2.connect(dsn_maintenance())
    try:
        cnx.autocommit = True
        with cnx.cursor() as curseur:
            curseur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (base,))
            if curseur.fetchone():
                return False
            curseur.execute(f'CREATE DATABASE "{base}"')
            return True
    finally:
        cnx.close()


def appliquer_schema(curseur) -> None:
    curseur.execute(SCHEMA.read_text(encoding="utf-8"))


def charger(curseur, table: str, chemin: Path) -> int:
    """Charge un fichier CSV dans une table, et renvoie le nombre de lignes."""
    with open(chemin, encoding="utf-8") as fichier:
        curseur.copy_expert(
            f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')", fichier
        )
    curseur.execute(f"SELECT count(*) FROM {table}")
    return curseur.fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remplit la base source boutique.")
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("data/sources/olist"),
        help="dossier des fichiers livrés (défaut : data/sources/olist)",
    )
    parser.add_argument(
        "--recharger", action="store_true", help="vider les tables et tout recharger"
    )
    args = parser.parse_args(argv)

    manquants = [f for f in FICHIERS.values() if not (args.sources / f).exists()]
    if manquants:
        print(
            f"ERREUR : fichier(s) introuvable(s) dans {args.sources} : {', '.join(manquants)}",
            file=sys.stderr,
        )
        print("Lancer d'abord : python scripts/download_data.py", file=sys.stderr)
        return 1

    try:
        if creer_base_si_absente():
            print(f"Base {BASE_PAR_DEFAUT} créée.")
        with psycopg2.connect(dsn_boutique()) as cnx, cnx.cursor() as curseur:
            appliquer_schema(curseur)
            for table, nom in FICHIERS.items():
                curseur.execute(f"SELECT count(*) FROM {table}")
                deja = curseur.fetchone()[0]
                if deja and not args.recharger:
                    print(f"  {table:<22} {deja:>9} lignes — déjà chargée")
                    continue
                if deja:
                    curseur.execute(f"TRUNCATE {table}")
                total = charger(curseur, table, args.sources / nom)
                print(f"  {table:<22} {total:>9} lignes")
    except psycopg2.Error as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    print("\nLa base source est prête. Acquisition : python -m acquisition")
    return 0


if __name__ == "__main__":
    sys.exit(main())
