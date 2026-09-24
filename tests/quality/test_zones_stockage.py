"""Tests d'intégration des zones de stockage (F1.6).

Vérifient que les trois zones existent avec la structure attendue.
Nécessitent une base PostgreSQL démarrée : marqués `integration`.
"""

import pytest
import psycopg2

from common.config import load_settings


@pytest.fixture(scope="module")
def connexion():
    settings = load_settings()
    conn = psycopg2.connect(settings.postgres_dsn)
    yield conn
    conn.close()


def _colonnes(curseur, schema: str, table: str) -> dict[str, str]:
    """Retourne {nom_colonne: type_donnee} pour une table donnée."""
    curseur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return dict(curseur.fetchall())


@pytest.mark.integration
def test_schema_quarantaine_existe(connexion):
    with connexion.cursor() as cur:
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'quarantaine'"
        )
        assert cur.fetchone() is not None


@pytest.mark.integration
def test_schema_raw_quarantine_n_existe_plus(connexion):
    """Vérifie que le renommage a bien eu lieu (pas de doublon de schéma)."""
    with connexion.cursor() as cur:
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'raw_quarantine'"
        )
        assert cur.fetchone() is None


@pytest.mark.integration
def test_table_quarantaine_rejets_colonnes(connexion):
    with connexion.cursor() as cur:
        colonnes = _colonnes(cur, "quarantaine", "rejets")

    assert colonnes["source"] == "text"
    assert colonnes["regle_violee"] == "text"
    assert colonnes["gravite"] == "text"
    assert colonnes["enregistrement"] == "jsonb"
    assert colonnes["horodatage"] == "timestamp with time zone"


@pytest.mark.integration
@pytest.mark.parametrize(
    "table",
    [
        "olist_orders",
        "olist_order_items",
        "olist_products",
        "olist_customers",
        "olist_geolocation",
        "olist_order_payments",
        "olist_order_reviews",
        "olist_sellers",
        "rakuten_produits",
        "product_category_translation",
    ],
)
def test_tables_intermediaires_existent(connexion, table):
    with connexion.cursor() as cur:
        colonnes = _colonnes(cur, "staging", table)
    assert colonnes, f"la table staging.{table} n'existe pas ou n'a aucune colonne"


@pytest.mark.integration
def test_identifiants_en_texte_pas_en_nombre(connexion):
    """Vérifie la règle : un identifiant ou un code postal ne perd jamais un zéro initial."""
    with connexion.cursor() as cur:
        colonnes_clients = _colonnes(cur, "staging", "olist_customers")
        colonnes_vendeurs = _colonnes(cur, "staging", "olist_sellers")

    assert colonnes_clients["customer_zip_code_prefix"] == "text"
    assert colonnes_vendeurs["seller_zip_code_prefix"] == "text"


@pytest.mark.integration
def test_montants_en_numeric_pas_en_flottant(connexion):
    """Vérifie la règle : un montant est en NUMERIC, jamais en FLOAT."""
    with connexion.cursor() as cur:
        colonnes = _colonnes(cur, "staging", "olist_order_items")

    assert colonnes["price"] == "numeric"
    assert colonnes["freight_value"] == "numeric"
