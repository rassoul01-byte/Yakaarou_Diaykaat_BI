"""Une base d'essai pour les tests d'intégration des indicateurs.

Les vues sont écrites sur le schéma `dwh` : les tester suppose donc un schéma
`dwh`. Il est créé dans une **base séparée**, jamais dans celle du projet —
un test ne doit jamais pouvoir détruire l'entrepôt de quelqu'un.
"""

from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest

from common.config import load_settings

BASE_D_ESSAI = "dataflow360_test"


@pytest.fixture
def dsn_test(monkeypatch) -> str:
    """Crée la base d'essai au besoin, et y dirige les lectures d'indicateurs."""
    dsn_projet = load_settings().postgres_dsn

    connexion = psycopg2.connect(dsn_projet)
    try:
        connexion.autocommit = True  # CREATE DATABASE refuse les transactions
        with connexion.cursor() as curseur:
            curseur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (BASE_D_ESSAI,))
            if not curseur.fetchone():
                curseur.execute(f'CREATE DATABASE "{BASE_D_ESSAI}"')
    finally:
        connexion.close()

    morceaux = urlsplit(dsn_projet)
    dsn = urlunsplit(morceaux._replace(path=f"/{BASE_D_ESSAI}"))
    monkeypatch.setattr(
        "indicateurs.lecture.load_settings", lambda: SimpleNamespace(postgres_dsn=dsn)
    )
    return dsn
