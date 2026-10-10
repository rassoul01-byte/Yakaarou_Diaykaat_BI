"""Tests de la vérification de l'entrepôt (F1.10).

Chaque anomalie est fabriquée à la main : on vérifie que la vérification la
voit, et qu'elle se termine alors avec le code 1 — celui qu'Airflow lit.
"""

from datetime import date

import pytest

from integration.chargement import charger
from integration.verifier import Controle, code_sortie, verifier
from tests.integration.aides import lire

# Ces tests chargent réellement l'entrepôt : ils exigent PostgreSQL. Le
# marqueur était jusqu'ici implicite — le nom du dossier suffisait à les
# écarter — ce qui écartait aussi les tests qui n'ont besoin d'aucun service.
pytestmark = pytest.mark.integration

JOUR_1 = date(2026, 10, 1)


# --- Sans base : la décision du code de sortie ------------------------------------


def test_un_controle_est_reussi_quand_constate_egale_attendu():
    assert Controle("c", 3, 3).ok
    assert not Controle("c", 3, 4).ok


def test_code_sortie_zero_si_tout_passe():
    assert code_sortie([Controle("a", 1, 1), Controle("b", 0, 0)]) == 0


def test_code_sortie_un_si_un_controle_echoue():
    assert code_sortie([Controle("a", 1, 1), Controle("b", 0, 2)]) == 1


def test_aucun_controle_ne_prouve_rien():
    assert code_sortie([]) == 1


# --- Sur un entrepôt d'essai -------------------------------------------------------

integration = pytest.mark.integration


def _echecs(cnx) -> list[str]:
    return [c.nom for c in verifier(cnx) if not c.ok]


@integration
def test_un_entrepot_charge_passe_tous_les_controles(cnx):
    charger(cnx, JOUR_1)

    controles = verifier(cnx)

    assert code_sortie(controles) == 0
    assert _echecs(cnx) == []


@integration
def test_un_fait_orphelin_fait_echouer_la_verification(cnx):
    charger(cnx, JOUR_1)
    # La base refuserait un orphelin : on retire la contrainte pour en fabriquer un.
    with cnx.cursor() as curseur:
        curseur.execute("ALTER TABLE dwh.fait_ligne_commande DROP CONSTRAINT fk_ligne_produit")
        curseur.execute(
            "UPDATE dwh.fait_ligne_commande SET produit_id = 999 WHERE order_item_id = 2"
        )
    cnx.commit()

    controles = verifier(cnx)

    assert code_sortie(controles) == 1
    assert _echecs(cnx) == ["aucun orphelin : fait_ligne_commande.produit_id → dim_produit"]


@integration
def test_une_ligne_perdue_fait_echouer_les_comptages_et_les_totaux(cnx):
    charger(cnx, JOUR_1)
    with cnx.cursor() as curseur:
        curseur.execute("DELETE FROM dwh.fait_ligne_commande WHERE order_id = 'o2'")
    cnx.commit()

    assert code_sortie(verifier(cnx)) == 1
    echecs = _echecs(cnx)
    assert "comptage fait_ligne_commande = staging.olist_order_items" in echecs
    assert "somme des prix = staging.olist_order_items" in echecs
    assert "a_une_ligne_article cohérent avec fait_ligne_commande" in echecs


@integration
def test_un_paiement_duplique_fait_echouer_la_somme_des_montants(cnx):
    charger(cnx, JOUR_1)
    with cnx.cursor() as curseur:
        curseur.execute(
            "UPDATE dwh.fait_commande SET montant_paye = montant_paye * 2 WHERE order_id = 'o1'"
        )
    cnx.commit()

    assert _echecs(cnx) == ["somme des montants payés = paiements staging (sans doublon)"]


@integration
def test_une_personne_en_double_est_vue_meme_sans_l_index_unique(cnx):
    charger(cnx, JOUR_1)
    with cnx.cursor() as curseur:
        curseur.execute("DROP INDEX dwh.ux_dim_client_courante")
        curseur.execute(
            "INSERT INTO dwh.dim_client (customer_unique_id, valide_du, est_courante)"
            " VALUES ('u-A', '2026-10-01', TRUE)"
        )
    cnx.commit()

    echecs = _echecs(cnx)
    assert "dim_client : au plus une version courante par identifiant" in echecs
    assert (
        "dim_client : lignes courantes = identifiants de staging.olist_customers + ligne 0"
        in echecs
    )


@integration
def test_la_commande_sans_article_n_est_pas_une_anomalie(cnx):
    charger(cnx, JOUR_1)

    assert lire(cnx, "SELECT count(*) FROM dwh.fait_commande WHERE NOT a_une_ligne_article") == [
        (1,)
    ]
    assert _echecs(cnx) == []
