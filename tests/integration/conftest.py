"""Une base d'essai pour les tests de l'entrepôt (F1.10).

Les schémas `staging` et `dwh` sont recréés dans une **base séparée**
(`dataflow360_test`), jamais dans celle du projet : un test ne doit jamais
pouvoir détruire l'entrepôt de quelqu'un. Les tables sont créées par les vraies
migrations, pas par une copie : si une migration change, les tests le voient.

Le jeu d'essai est petit, et ses valeurs sont calculées à la main :

  commande  client   statut     achat       livrée      lignes (produit, prix, port)   paiements
  ------------------------------------------------------------------------------------------------
  o1        cust-a1  delivered  2017-03-15  2017-03-25  (p1, 100, 10) (p2, 50, 5)      80 + 70
  o2        cust-b1  delivered  2017-04-10  2017-04-20  (p3, 200, 20)                  220
  o3        cust-a2  canceled   2017-05-01  —           (p1, 999, 99)                  1098
  o4        cust-b1  delivered  2017-06-30  2017-07-05  aucune                         30

  Personnes : u-A (cust-a1 + cust-a2), u-B (cust-b1), u-C (aucune commande) → 3
  Prix : 1349   Frais de port : 134   Montants payés : 150 + 220 + 1098 + 30 = 1498
  Délai de livraison : o1 = 10 jours, o2 = 10, o3 = NULL, o4 = 5
"""

from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest

from common.config import load_settings
from tests.integration.aides import RACINE

MIGRATIONS = ("002_intermediaire.sql", "003_intermediaire_rakuten.sql", "006_transformation.sql")
MIGRATION_ENTREPOT = "007_entrepot.sql"
BASE_D_ESSAI = "dataflow360_test"

_JOURNAL_ET_CORRESPONDANCE = """
CREATE TABLE staging.execution_log (
    id BIGSERIAL PRIMARY KEY, pipeline TEXT NOT NULL, etape TEXT NOT NULL, source TEXT,
    demarre_a TIMESTAMPTZ NOT NULL DEFAULT now(), termine_a TIMESTAMPTZ,
    lignes_lues BIGINT, lignes_ecrites BIGINT, lignes_rejetees BIGINT,
    statut TEXT NOT NULL DEFAULT 'en_cours', message TEXT);

-- Même structure que integration.correspondance.creer_table
CREATE TABLE staging.correspondance_produits (
    id_produit TEXT PRIMARY KEY, id_fiche TEXT, categorie_boutique TEXT NOT NULL,
    categorie_catalogue TEXT NOT NULL, rattache BOOLEAN NOT NULL);
"""

JEU_D_ESSAI = """
INSERT INTO staging.olist_customers VALUES
    ('cust-a1', 'u-A', '01000', 'Rio', 'RJ'),
    ('cust-a2', 'u-A', '02000', 'Niteroi', 'RJ'),
    ('cust-b1', 'u-B', '03000', 'Sao Paulo', 'SP'),
    ('cust-c1', 'u-C', '04000', 'Recife', 'PE');

INSERT INTO staging.olist_sellers VALUES
    ('s1', '10000', 'Curitiba', 'PR'),
    ('s2', '20000', 'Salvador', 'BA');

INSERT INTO staging.olist_products (product_id, product_category_name_norm) VALUES
    ('p1', 'meubles'), ('p2', 'luminaires'), ('p3', NULL);

INSERT INTO staging.rakuten_produits
    (index_ligne, jeu, designation, productid, imageid, prdtypecode, langue) VALUES
    (1, 'train', 'Chaise', 'f1', 'i1', 1560, 'fr'),
    (2, 'train', 'Lamp',   'f2', 'i2', 2060, 'en'),
    (3, 'test',  'Chaise', 'f1', 'i1', NULL, 'de');

INSERT INTO staging.correspondance_produits VALUES
    ('p1', 'f1', 'meubles',    '1560',    TRUE),
    ('p2', 'f2', 'luminaires', '2060',    TRUE),
    ('p3', NULL, 'inconnu',    'inconnu', FALSE);

INSERT INTO staging.olist_orders VALUES
    ('o1', 'cust-a1', 'delivered', '2017-03-15 10:00', '2017-03-15 11:00',
     '2017-03-17 09:00', '2017-03-25 14:00', '2017-04-01 00:00'),
    ('o2', 'cust-b1', 'delivered', '2017-04-10 08:00', '2017-04-10 09:00',
     '2017-04-12 09:00', '2017-04-20 16:00', '2017-04-25 00:00'),
    ('o3', 'cust-a2', 'canceled',  '2017-05-01 12:00', NULL, NULL, NULL, '2017-05-20 00:00'),
    ('o4', 'cust-b1', 'delivered', '2017-06-30 18:00', '2017-06-30 19:00',
     '2017-07-01 09:00', '2017-07-05 10:00', '2017-07-20 00:00');

INSERT INTO staging.olist_order_items VALUES
    ('o1', 1, 'p1', 's1', '2017-03-20 00:00', 100.00, 10.00),
    ('o1', 2, 'p2', 's1', '2017-03-20 00:00',  50.00,  5.00),
    ('o2', 1, 'p3', 's2', '2017-04-15 00:00', 200.00, 20.00),
    ('o3', 1, 'p1', 's1', '2017-05-05 00:00', 999.00, 99.00);

INSERT INTO staging.olist_order_payments VALUES
    ('o1', 1, 'credit_card', 1, 80.00),
    ('o1', 2, 'voucher',     1, 70.00),
    ('o2', 1, 'credit_card', 1, 220.00),
    ('o3', 1, 'credit_card', 1, 1098.00),
    ('o4', 1, 'boleto',      1, 30.00);
"""


def _executer_fichier(curseur, nom: str) -> None:
    curseur.execute((RACINE / "sql" / nom).read_text(encoding="utf-8"))


@pytest.fixture
def cnx():
    """Une connexion sur un entrepôt d'essai vide : migrations appliquées, jeu d'essai chargé."""
    dsn_projet = load_settings().postgres_dsn

    admin = psycopg2.connect(dsn_projet)
    try:
        admin.autocommit = True  # CREATE DATABASE refuse les transactions
        with admin.cursor() as curseur:
            curseur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (BASE_D_ESSAI,))
            if not curseur.fetchone():
                curseur.execute(f'CREATE DATABASE "{BASE_D_ESSAI}"')
    finally:
        admin.close()

    morceaux = urlsplit(dsn_projet)
    dsn = urlunsplit(morceaux._replace(path=f"/{BASE_D_ESSAI}"))

    connexion = psycopg2.connect(dsn)
    with connexion, connexion.cursor() as curseur:
        curseur.execute("DROP SCHEMA IF EXISTS dwh CASCADE; DROP SCHEMA IF EXISTS staging CASCADE;")
        curseur.execute("CREATE SCHEMA staging; CREATE SCHEMA dwh;")
        for migration in MIGRATIONS:
            _executer_fichier(curseur, migration)
        curseur.execute(_JOURNAL_ET_CORRESPONDANCE)
        _executer_fichier(curseur, MIGRATION_ENTREPOT)
        curseur.execute(JEU_D_ESSAI)

    yield connexion
    connexion.close()
