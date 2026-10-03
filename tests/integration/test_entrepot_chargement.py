"""Tests du chargement de l'entrepôt (F1.10).

Le jeu d'essai et ses valeurs attendues sont décrits dans conftest.py : tout est
calculé à la main, on compare à ce qu'on attendait, pas à ce que la base renvoie.
"""

from datetime import date
from decimal import Decimal

import pytest

from integration import chargement
from integration.chargement import ChargementError, charger
from tests.integration.aides import RACINE, lire

pytestmark = pytest.mark.integration

JOUR_1 = date(2026, 10, 1)


def test_comptages_des_faits_et_des_dimensions(cnx):
    resultat = charger(cnx, JOUR_1)

    assert resultat.comptages["fait_commande"] == 4
    assert resultat.comptages["fait_ligne_commande"] == 4
    assert resultat.comptages["dim_client"] == 3  # personnes, pas customer_id
    assert resultat.comptages["dim_produit"] == 3
    assert resultat.comptages["dim_vendeur"] == 2
    assert resultat.lignes_lues == 8  # 4 commandes + 4 lignes


def test_chaque_dimension_garde_sa_ligne_inconnu(cnx):
    charger(cnx, JOUR_1)

    for table, cle in (
        ("dim_client", "client_id"),
        ("dim_produit", "produit_id"),
        ("dim_vendeur", "vendeur_id"),
        ("dim_date", "date_id"),
    ):
        assert lire(cnx, f"SELECT count(*) FROM dwh.{table} WHERE {cle} = 0") == [(1,)]
    assert lire(cnx, "SELECT valide_du, est_courante FROM dwh.dim_client WHERE client_id = 0") == [
        (date(1900, 1, 1), True)
    ]


def test_dim_client_est_batie_sur_la_personne(cnx):
    charger(cnx, JOUR_1)

    # u-A a deux customer_id : une seule ligne, localisée par le plus petit (cust-a1).
    assert lire(cnx, "SELECT ville, etat FROM dwh.dim_client WHERE customer_unique_id = 'u-A'") == [
        ("Rio", "RJ")
    ]
    assert lire(cnx, "SELECT count(*) FROM dwh.dim_client WHERE customer_unique_id = 'u-A'") == [
        (1,)
    ]
    # Les deux commandes de u-A (cust-a1 et cust-a2) pointent vers la même ligne.
    assert lire(
        cnx,
        """
        SELECT count(DISTINCT f.client_id)
        FROM dwh.fait_commande AS f JOIN dwh.dim_client AS c USING (client_id)
        WHERE c.customer_unique_id = 'u-A'
        """,
    ) == [(1,)]


def test_dim_produit_porte_la_correspondance_et_la_langue(cnx):
    charger(cnx, JOUR_1)

    lignes = lire(
        cnx,
        """
        SELECT id_produit_olist, categorie, categorie_catalogue, id_fiche_rakuten, rattache, langue
        FROM dwh.dim_produit WHERE produit_id <> 0 ORDER BY id_produit_olist
        """,
    )
    assert lignes == [
        ("p1", "meubles", "1560", "f1", True, "fr"),  # la langue vient du train, pas du test
        ("p2", "luminaires", "2060", "f2", True, "en"),
        ("p3", None, "inconnu", None, False, None),  # produit sans catégorie : conservé
    ]


def test_paiements_multiples_ne_sont_pas_dupliques(cnx):
    charger(cnx, JOUR_1)

    # o1 a deux paiements (80 + 70) ET deux lignes d'article : sans agrégation
    # préalable, le montant serait compté quatre fois.
    assert lire(
        cnx, "SELECT montant_paye, nombre_paiements FROM dwh.fait_commande WHERE order_id = 'o1'"
    ) == [(Decimal("150.00"), 2)]
    assert lire(cnx, "SELECT SUM(montant_paye) FROM dwh.fait_commande") == [(Decimal("1498.00"),)]


def test_commande_sans_article_existe_et_pese_zero(cnx):
    charger(cnx, JOUR_1)

    assert lire(
        cnx, "SELECT statut, a_une_ligne_article FROM dwh.fait_commande WHERE order_id = 'o4'"
    ) == [("delivered", False)]
    assert lire(cnx, "SELECT count(*) FROM dwh.fait_ligne_commande WHERE order_id = 'o4'") == [(0,)]


def test_totaux_des_lignes(cnx):
    charger(cnx, JOUR_1)

    assert lire(cnx, "SELECT SUM(prix), SUM(frais_port) FROM dwh.fait_ligne_commande") == [
        (Decimal("1349.00"), Decimal("134.00"))
    ]


def test_delai_de_livraison_en_jours(cnx):
    charger(cnx, JOUR_1)

    delais = dict(lire(cnx, "SELECT order_id, delai_livraison_jours FROM dwh.fait_commande"))
    assert delais == {"o1": 10, "o2": 10, "o3": None, "o4": 5}


def test_les_lignes_portent_la_date_d_achat_de_leur_commande(cnx):
    charger(cnx, JOUR_1)

    assert lire(
        cnx, "SELECT DISTINCT date_id FROM dwh.fait_ligne_commande WHERE order_id = 'o1'"
    ) == [(20170315,)]


def test_dim_date_couvre_toutes_les_dates_avec_un_mois_de_marge(cnx):
    charger(cnx, JOUR_1)

    # Première date : achat de o1 (15 mars 2017) → marge au 1er février.
    # Dernière date : livraison estimée de o4 (20 juillet) → marge au 31 août.
    assert lire(cnx, "SELECT MIN(date), MAX(date) FROM dwh.dim_date WHERE date_id <> 0") == [
        (date(2017, 2, 1), date(2017, 8, 31))
    ]
    # La livraison de o4 est postérieure à la dernière date d'achat (30 juin).
    assert lire(cnx, "SELECT nom_jour, nom_mois FROM dwh.dim_date WHERE date_id = 20170705") == [
        ("mercredi", "juillet")
    ]
    # Aucun trou : un jour de plus que la différence de dates.
    assert lire(cnx, "SELECT count(*) FROM dwh.dim_date WHERE date_id <> 0") == [(212,)]


def test_relancer_le_chargement_ne_change_rien(cnx):
    premier = charger(cnx, JOUR_1)
    cles = lire(cnx, "SELECT client_id, customer_unique_id FROM dwh.dim_client ORDER BY 1")
    empreinte = lire(
        cnx, "SELECT SUM(prix), SUM(montant_paye) FROM dwh.fait_ligne_commande, dwh.fait_commande"
    )

    second = charger(cnx, JOUR_1)

    assert second.comptages == premier.comptages
    assert lire(cnx, "SELECT client_id, customer_unique_id FROM dwh.dim_client ORDER BY 1") == cles
    assert (
        lire(
            cnx,
            "SELECT SUM(prix), SUM(montant_paye) FROM dwh.fait_ligne_commande, dwh.fait_commande",
        )
        == empreinte
    )


def test_le_chargement_est_tout_ou_rien(cnx, monkeypatch):
    charger(cnx, JOUR_1)
    avant = lire(cnx, "SELECT client_id, ville FROM dwh.dim_client ORDER BY 1")

    # Une source change, puis le chargement échoue au dernier moment.
    with cnx.cursor() as curseur:
        curseur.execute(
            "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'"
        )
    cnx.commit()

    def panne(curseur):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(chargement, "charger_fait_ligne_commande", panne)
    with pytest.raises(RuntimeError, match="panne simulée"):
        charger(cnx, JOUR_1)

    # Rien n'a bougé : ni les dimensions, ni les faits.
    assert lire(cnx, "SELECT client_id, ville FROM dwh.dim_client ORDER BY 1") == avant
    assert lire(cnx, "SELECT count(*) FROM dwh.fait_ligne_commande") == [(4,)]


def test_refuse_de_charger_si_la_correspondance_est_incomplete(cnx):
    with cnx.cursor() as curseur:
        curseur.execute("DELETE FROM staging.correspondance_produits WHERE id_produit = 'p3'")
    cnx.commit()

    with pytest.raises(ChargementError, match="correspondance"):
        charger(cnx, JOUR_1)

    assert lire(cnx, "SELECT count(*) FROM dwh.fait_commande") == [(0,)]


def test_refuse_de_charger_une_commande_sans_client(cnx):
    with cnx.cursor() as curseur:
        curseur.execute("DELETE FROM staging.olist_customers WHERE customer_id = 'cust-c1'")
        curseur.execute("DELETE FROM staging.olist_customers WHERE customer_id = 'cust-b1'")
    cnx.commit()

    with pytest.raises(ChargementError, match="client"):
        charger(cnx, JOUR_1)


def test_refuse_de_charger_une_zone_intermediaire_vide(cnx):
    with cnx.cursor() as curseur:
        curseur.execute("TRUNCATE staging.olist_order_items, staging.olist_orders")
    cnx.commit()

    with pytest.raises(ChargementError, match="vide"):
        charger(cnx, JOUR_1)


def test_un_produit_inconnu_de_staging_pointe_vers_la_ligne_zero(cnx):
    # Une ligne d'article dont le produit n'est pas dans olist_products :
    # elle est conservée, rattachée à la ligne « inconnu ».
    with cnx.cursor() as curseur:
        curseur.execute(
            "INSERT INTO staging.olist_order_items VALUES"
            " ('o2', 2, 'p-fantome', 's2', '2017-04-15 00:00', 10.00, 1.00)"
        )
    cnx.commit()

    resultat = charger(cnx, JOUR_1)

    assert resultat.comptages["fait_ligne_commande"] == 5
    assert lire(
        cnx,
        "SELECT produit_id FROM dwh.fait_ligne_commande WHERE order_id = 'o2' AND order_item_id = 2",
    ) == [(0,)]


def test_les_vues_d_indicateurs_lisent_l_entrepot_charge(cnx):
    """Les vues de Bachir (migration 010) doivent s'appliquer au vrai schéma."""
    charger(cnx, JOUR_1)
    with cnx.cursor() as curseur:
        curseur.execute((RACINE / "sql" / "010_vues_indicateurs.sql").read_text(encoding="utf-8"))
    cnx.commit()

    # o1 (150) + o2 (200) ; o3 annulée exclue ; o4 sans article ne compte pas.
    assert lire(
        cnx, "SELECT chiffre_affaires, commandes, panier_moyen FROM dwh.v_ventes_totales"
    ) == [(Decimal("350.00"), 2, Decimal("175.00"))]
