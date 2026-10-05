"""Test de bout en bout RAW → QUALITY → PostgreSQL (staging, quarantaine, journal).

Nécessite PostgreSQL démarré, avec les migrations appliquées :
    PYTHONPATH=src python scripts/appliquer_sql.py
    pytest -m integration tests/quality/test_integration_qualite.py

La quarantaine est append-only et ne doit jamais recevoir de données de test :
chaque test travaille dans une transaction annulée à la fin (charger(...,
valider=False)), et lit ses propres écritures dans cette même transaction.

Le dernier test rejoue une vraie ingestion Olist si la variable
INGESTION_OLIST_REELLE désigne une ingestion complète de data/raw (9 fichiers).
"""

import json
import os
import uuid

import psycopg2
import pytest

from common.config import load_settings
from quality import rapport
from quality.chargement import charger
from quality.controle import controler

from .conftest import (
    NB_ARTICLES_SANS_COMMANDE_RETENUE,
    NB_CLIENTS_SANS_IDENTIFIANT,
    NB_LIVREES_SANS_DATE,
    construire_ingestion_olist,
    construire_ingestion_rakuten,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def transaction():
    connexion = psycopg2.connect(load_settings().postgres_dsn)
    try:
        yield connexion
    finally:
        connexion.rollback()
        connexion.close()


@pytest.fixture
def ingestion():
    # Un identifiant propre au test : aucune collision avec de vraies ingestions.
    return f"test{uuid.uuid4().hex[:12]}"


def _un(connexion, requete, *parametres):
    with connexion.cursor() as curseur:
        curseur.execute(requete, parametres)
        return curseur.fetchone()[0]


def _rejets_par_regle(connexion, ingestion):
    with connexion.cursor() as curseur:
        curseur.execute(
            """
            SELECT regle_violee, COUNT(*) FROM quarantaine.rejets
            WHERE ingestion = %s GROUP BY regle_violee
            """,
            (ingestion,),
        )
        return dict(curseur.fetchall())


def test_raw_quality_staging_quarantaine_journal_puis_rapport(tmp_path, transaction, ingestion):
    racine = tmp_path / "raw"
    construire_ingestion_olist(racine, ingestion)
    resultat = controler("olist", ingestion, racine)

    bilan = charger(resultat, connexion=transaction, valider=False)

    # STAGING : les commandes valides seulement
    assert _un(transaction, "SELECT COUNT(*) FROM staging.olist_orders") == 12
    assert (
        _un(
            transaction,
            "SELECT COUNT(*) FROM staging.olist_orders WHERE order_id = ANY(%s)",
            [f"o{i:02d}" for i in range(1, NB_LIVREES_SANS_DATE + 1)],
        )
        == 0
    )
    assert _un(transaction, "SELECT COUNT(*) FROM staging.olist_order_reviews") == 4
    assert _un(transaction, "SELECT COUNT(*) FROM staging.olist_geolocation") == 2
    # le zéro initial du code postal est conservé jusqu'en base
    assert (
        _un(transaction, "SELECT customer_zip_code_prefix FROM staging.olist_customers LIMIT 1")
        == "01037"
    )
    assert (
        _un(
            transaction,
            "SELECT product_category_name FROM staging.olist_products WHERE product_id = 'p2'",
        )
        == "inconnu"
    )

    # QUARANTAINE : les 8 commandes livrées sans date y sont réellement
    rejets = _rejets_par_regle(transaction, ingestion)
    assert rejets == {
        "OLIST_COMMANDES_02": NB_LIVREES_SANS_DATE,
        # Les lignes d'article des commandes rejetées partent avec elles.
        "OLIST_ARTICLES_02": NB_ARTICLES_SANS_COMMANDE_RETENUE,
        "OLIST_AVIS_01": 1,
        "OLIST_AVIS_02": 1,
        "OLIST_CLIENTS_01": NB_CLIENTS_SANS_IDENTIFIANT,
    }
    with transaction.cursor() as curseur:
        curseur.execute(
            """
            SELECT enregistrement->>'order_id', fichier, gravite, ligne_origine
            FROM quarantaine.rejets
            WHERE ingestion = %s AND regle_violee = 'OLIST_COMMANDES_02'
            ORDER BY ligne_origine
            """,
            (ingestion,),
        )
        lignes = curseur.fetchall()
    assert [ligne[0] for ligne in lignes] == [f"o{i:02d}" for i in range(1, 9)]
    assert {(ligne[1], ligne[2]) for ligne in lignes} == {("orders.csv", "bloquante")}
    assert [ligne[3] for ligne in lignes] == list(range(1, 9))

    # EXECUTION_LOG : une ligne « qualite » qui dit la même chose que la quarantaine
    with transaction.cursor() as curseur:
        curseur.execute(
            """
            SELECT pipeline, etape, source, lignes_lues, lignes_ecrites,
                   lignes_rejetees, statut, message
            FROM staging.execution_log WHERE id = %s
            """,
            (bilan.execution_id,),
        )
        pipeline, etape, source, lues, ecrites, rejetees, statut, message = curseur.fetchone()
    assert (pipeline, etape, source, statut) == ("qualite", "controle", "olist", "succes")
    assert rejetees == sum(rejets.values()) == 11 + NB_ARTICLES_SANS_COMMANDE_RETENUE
    assert lues == ecrites + rejetees + 1  # + 1 doublon strict de géolocalisation
    detail = {c["regle"]: c for c in json.loads(message)["controles"]}
    assert detail["OLIST_COMMANDES_02"]["lignes_quarantaine"] == NB_LIVREES_SANS_DATE

    # RAPPORT : les vues retrouvent l'exécution et ses rejets
    with transaction.cursor() as curseur:
        par_execution = rapport._lire(
            curseur,
            "SELECT * FROM quarantaine.v_taux_rejet_par_execution WHERE execution_id = %(id)s",
            id=bilan.execution_id,
        )
        par_source = rapport._lire(curseur, rapport._PAR_SOURCE, source="olist")
        par_regle = rapport._lire(curseur, rapport._PAR_REGLE, source="olist", limite=100)
    (execution,) = par_execution
    assert execution["lignes_rejetees"] == 11 + NB_ARTICLES_SANS_COMMANDE_RETENUE
    assert float(execution["taux_rejet_pourcent"]) == rapport.taux_pourcent(lues, rejetees)
    # la dernière exécution d'olist, celle que le rapport affiche, est la nôtre
    assert (par_source[0]["lignes_lues"], par_source[0]["lignes_rejetees"]) == (lues, rejetees)
    regles = {ligne["regle"] for ligne in par_regle}
    assert "OLIST_COMMANDES_02" in regles


def test_relancer_la_meme_ingestion_ne_duplique_rien(tmp_path, transaction, ingestion):
    racine = tmp_path / "raw"
    construire_ingestion_olist(racine, ingestion)

    premier = charger(controler("olist", ingestion, racine), connexion=transaction, valider=False)
    staging_1 = _un(transaction, "SELECT COUNT(*) FROM staging.olist_orders")
    second = charger(controler("olist", ingestion, racine), connexion=transaction, valider=False)

    # staging est écrasée, pas complétée
    assert _un(transaction, "SELECT COUNT(*) FROM staging.olist_orders") == staging_1
    # la quarantaine ne reçoit pas deux fois les mêmes rejets
    attendus = 11 + NB_ARTICLES_SANS_COMMANDE_RETENUE
    assert sum(_rejets_par_regle(transaction, ingestion).values()) == attendus
    assert premier.rejets_inseres == attendus
    assert second.rejets_inseres == 0
    assert second.rejets_deja_presents == attendus
    # le journal garde une ligne par exécution, chacune avec les rejets qu'elle a détectés
    assert second.execution_id != premier.execution_id
    assert (
        _un(
            transaction,
            "SELECT COUNT(*) FROM staging.execution_log "
            "WHERE id IN (%s, %s) AND lignes_rejetees = %s",
            premier.execution_id,
            second.execution_id,
            attendus,
        )
        == 2
    )


def test_rakuten_charge_le_catalogue_et_journalise_sans_rejet(tmp_path, transaction, ingestion):
    racine = tmp_path / "raw"
    construire_ingestion_rakuten(racine, ingestion)

    bilan = charger(controler("rakuten", ingestion, racine), connexion=transaction, valider=False)

    assert _un(transaction, "SELECT COUNT(*) FROM staging.rakuten_produits") == 6
    assert _un(transaction, "SELECT COUNT(DISTINCT jeu) FROM staging.rakuten_produits") == 1
    assert _rejets_par_regle(transaction, ingestion) == {}
    assert (
        _un(
            transaction,
            "SELECT lignes_rejetees FROM staging.execution_log WHERE id = %s",
            bilan.execution_id,
        )
        == 0
    )


def test_un_echec_de_chargement_ne_laisse_aucune_trace(tmp_path, ingestion):
    racine = tmp_path / "raw"
    construire_ingestion_olist(racine, ingestion)
    resultat = controler("olist", ingestion, racine)
    # Une date illisible : PostgreSQL refuse la copie de staging.olist_orders.
    resultat.valides["olist_orders"].loc[
        resultat.valides["olist_orders"].index[0], "order_purchase_timestamp"
    ] = "pas une date"

    with psycopg2.connect(load_settings().postgres_dsn) as connexion:
        journal_avant = _un(connexion, "SELECT COUNT(*) FROM staging.execution_log")
        commandes_avant = _un(connexion, "SELECT COUNT(*) FROM staging.olist_orders")
    connexion.close()

    with pytest.raises(psycopg2.Error):
        charger(resultat)  # sa propre connexion, validée… si tout réussit

    with psycopg2.connect(load_settings().postgres_dsn) as connexion:
        assert _un(connexion, "SELECT COUNT(*) FROM staging.execution_log") == journal_avant
        assert _un(connexion, "SELECT COUNT(*) FROM staging.olist_orders") == commandes_avant
        assert _rejets_par_regle(connexion, ingestion) == {}
    connexion.close()


@pytest.mark.skipif(
    not os.getenv("INGESTION_OLIST_REELLE"),
    reason="définir INGESTION_OLIST_REELLE=<AAAAMMJJTHHMMSS> pour rejouer une vraie ingestion",
)
def test_vraie_ingestion_olist(transaction):
    ingestion = os.environ["INGESTION_OLIST_REELLE"]
    resultat = controler("olist", ingestion)

    bilan = charger(resultat, connexion=transaction, valider=False)

    with transaction.cursor() as curseur:
        curseur.execute(
            """
            SELECT regle_violee, COUNT(*) FROM quarantaine.rejets
            WHERE source = 'olist' AND ingestion = %s GROUP BY regle_violee
            """,
            (ingestion,),
        )
        rejets = dict(curseur.fetchall())
    assert rejets["OLIST_COMMANDES_02"] == 8
    assert rejets["OLIST_AVIS_01"] == 814
    assert rejets["OLIST_AVIS_02"] == 243
    assert _un(transaction, "SELECT COUNT(*) FROM staging.olist_order_reviews") == 98167
    assert _un(transaction, "SELECT COUNT(*) FROM staging.olist_orders") == 99441 - 8
    assert bilan.lignes_rejetees == 8 + 814 + 243
