"""Lecture de la source SQL : la base « boutique ».

C'est le seul fichier du paquet qui sait que les données viennent d'une base de
données. Il expose deux choses : comment s'y connecter, et comment en extraire
une table vers un fichier CSV.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2

from common.config import load_settings

BASE_PAR_DEFAUT = "boutique"

# Les tables de la source, dans l'ordre d'extraction.
TABLES = (
    "customers",
    "orders",
    "order_items",
    "order_payments",
    "products",
    "sellers",
    "geolocation",
    "category_translation",
)

# Colonne de date utilisée par l'extraction incrémentale. Les tables absentes
# de ce dictionnaire sont toujours extraites en entier : ce sont des
# référentiels, qui n'ont pas de date de création.
COLONNE_INCREMENTALE = {"orders": "order_purchase_timestamp"}


def dsn_boutique(base: str = BASE_PAR_DEFAUT) -> str:
    """Chaîne de connexion à la base source.

    Par défaut, c'est le même serveur PostgreSQL que le reste de la plateforme,
    avec une autre base : la source et les zones de stockage sont ainsi
    distinctes sans conteneur supplémentaire. La variable BOUTIQUE_DSN permet
    de pointer vers un autre serveur, si la source déménage un jour.
    """
    impose = os.getenv("BOUTIQUE_DSN")
    if impose:
        return impose
    morceaux = urlsplit(load_settings().postgres_dsn)
    return urlunsplit(morceaux._replace(path=f"/{base}"))


def dsn_maintenance() -> str:
    """Connexion à la base d'administration, pour créer la base source."""
    return dsn_boutique(base="postgres")


def connexion(dsn: str | None = None):
    return psycopg2.connect(dsn or dsn_boutique())


def requete_extraction(table: str, depuis: str | None = None) -> str:
    """Construit la requête d'extraction d'une table.

    Lève ValueError pour une table inconnue : les noms de tables ne peuvent pas
    être passés comme paramètres à PostgreSQL, ils sont donc validés ici plutôt
    que concaténés à l'aveugle.
    """
    if table not in TABLES:
        raise ValueError(f"table inconnue : {table!r}")
    colonne = COLONNE_INCREMENTALE.get(table)
    if depuis and colonne:
        return f"SELECT * FROM {table} WHERE {colonne} >= %(depuis)s ORDER BY {colonne}"
    return f"SELECT * FROM {table}"


def extraire_table(curseur, table: str, destination: Path, depuis: str | None = None) -> None:
    """Écrit le contenu d'une table dans un fichier CSV, en-tête compris.

    L'extraction passe par COPY : PostgreSQL écrit directement le flux CSV,
    sans que les lignes transitent une par une par Python.
    """
    requete = curseur.mogrify(requete_extraction(table, depuis), {"depuis": depuis}).decode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8", newline="") as fichier:
        curseur.copy_expert(f"COPY ({requete}) TO STDOUT WITH (FORMAT csv, HEADER true)", fichier)
