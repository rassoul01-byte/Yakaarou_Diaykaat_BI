"""Tests du moteur de contrôle qualité (F1.5), sans base de données.

Chaque règle est testée seule sur un petit DataFrame, puis le contrôle
complet d'une ingestion synthétique (tests/quality/conftest.py) vérifie que
ce qui est annoncé dans le journal est bien ce qui part en quarantaine.
"""

import pandas as pd
import pytest

from quality import controle
from quality.controle import (
    controler,
    controler_avis_par_commande,
    controler_commandes_sans_articles,
    controler_date_livraison,
    controler_designations_dupliquees,
    controler_doublons_stricts,
    controler_html_rakuten,
    controler_identifiant_client,
    controler_langue_rakuten,
    controler_olist,
    controler_paiements_multiples,
    controler_produits_sans_categorie,
    controler_review_id,
    lire_csv,
    resoudre_ingestion,
)
from quality.rules import get_rule

from .conftest import (
    INGESTION_OLIST,
    INGESTION_RAKUTEN,
    NB_AVIS_EN_TROP_PAR_COMMANDE,
    NB_AVIS_SANS_COMMENTAIRE,
    NB_CLIENTS_SANS_IDENTIFIANT,
    NB_COMMANDES,
    NB_COMMANDES_PAIEMENT_MULTIPLE,
    NB_COMMANDES_SANS_ARTICLE,
    NB_GEO_DOUBLONS_STRICTS,
    NB_LIVREES_SANS_DATE,
    NB_PRODUITS_SANS_CATEGORIE,
    NB_REVIEW_ID_DUPLIQUES,
)


def _journal(resultat):
    return {c["regle"]: c for c in resultat.controles}


def _rejets(resultat, regle):
    return [lot for lot in resultat.rejets if lot.regle["identifiant"] == regle]


# --- Règles Olist, une à une -------------------------------------------------


def test_identifiant_client_absent_est_rejete():
    clients = pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3"],
            "customer_unique_id": ["u1", None, "  "],
        }
    )

    valides, rejetes = controler_identifiant_client(clients, get_rule("OLIST_CLIENTS_01"))

    assert list(valides["customer_id"]) == ["c1"]
    assert list(rejetes["customer_id"]) == ["c2", "c3"]


def test_commande_sans_article_est_conservee_et_comptee():
    commandes = pd.DataFrame({"order_id": ["o1", "o2"]})
    articles = pd.DataFrame({"order_id": ["o1"]})

    valides, sans_article = controler_commandes_sans_articles(
        commandes, articles, get_rule("OLIST_COMMANDES_01")
    )

    assert len(valides) == 2  # non bloquante : rien n'est retiré
    assert list(sans_article["order_id"]) == ["o2"]


def test_commande_livree_sans_date_est_rejetee_et_les_autres_statuts_non():
    commandes = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3"],
            "order_status": ["delivered", "delivered", "shipped"],
            "order_delivered_customer_date": [None, "2018-01-10 10:00:00", None],
        }
    )

    valides, rejetees = controler_date_livraison(commandes, get_rule("OLIST_COMMANDES_02"))

    assert list(rejetees["order_id"]) == ["o1"]
    assert list(valides["order_id"]) == ["o2", "o3"]


def test_produit_sans_categorie_est_rattache_a_inconnu():
    produits = pd.DataFrame(
        {"product_id": ["p1", "p2", "p3"], "product_category_name": ["a", None, ""]}
    )

    valides, sans_categorie = controler_produits_sans_categorie(
        produits, get_rule("OLIST_ARTICLES_01")
    )

    assert list(valides["product_category_name"]) == ["a", "inconnu", "inconnu"]
    assert len(sans_categorie) == 2


def test_review_id_duplique_garde_la_premiere_occurrence():
    avis = pd.DataFrame({"review_id": ["r1", "r1", "r2"], "order_id": ["o1", "o2", "o3"]})

    valides, rejetes = controler_review_id(avis, get_rule("OLIST_AVIS_01"))

    assert list(valides["order_id"]) == ["o1", "o3"]
    assert list(rejetes["order_id"]) == ["o2"]


def test_review_id_absent_arrete_le_controle_au_lieu_de_vider_les_avis():
    avis = pd.DataFrame({"review_id": ["r1", None], "order_id": ["o1", "o2"]})

    with pytest.raises(ValueError, match="OLIST_AVIS_01"):
        controler_review_id(avis, get_rule("OLIST_AVIS_01"))


def test_plusieurs_avis_pour_une_commande_seul_le_premier_reste():
    avis = pd.DataFrame({"review_id": ["r1", "r2", "r3"], "order_id": ["o1", "o1", "o2"]})

    valides, rejetes = controler_avis_par_commande(avis, get_rule("OLIST_AVIS_02"))

    assert list(valides["review_id"]) == ["r1", "r3"]
    assert list(rejetes["review_id"]) == ["r2"]


def test_paiements_multiples_sont_agreges_avec_leur_montant():
    paiements = pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2"],
            "payment_sequential": ["1", "2", "1"],
            "payment_value": ["30.00", "12.50", "10.00"],
        }
    )

    agregat, multiples = controler_paiements_multiples(paiements, get_rule("OLIST_PAIEMENTS_01"))

    par_commande = agregat.set_index("order_id")
    assert par_commande.loc["o1", "nombre_paiements"] == 2
    assert par_commande.loc["o1", "montant_total"] == pytest.approx(42.50)
    assert par_commande.loc["o2", "montant_total"] == pytest.approx(10.00)
    assert list(multiples["order_id"]) == ["o1"]
    assert len(paiements) == 3  # le détail n'est pas modifié


def test_geolocalisation_doublons_stricts_retires_sans_quarantaine():
    geo = pd.DataFrame({"zip": ["01037", "01037", "01037"], "lat": ["-23.5", "-23.5", "-23.6"]})

    valides, supprimes = controler_doublons_stricts(geo, get_rule("OLIST_GEOLOCALISATION_01"))

    assert supprimes == 1
    assert len(valides) == 2


# --- Règles Rakuten, une à une -----------------------------------------------


def test_html_detecte_les_entites_numeriques_seules():
    # Régression : « #\\d+ » dans une chaîne brute cherchait une barre oblique
    # littérale et manquait toutes les entités numériques comme &#39;.
    produits = pd.DataFrame(
        {
            "designation": ["Stylet", "Carnet", "Livre"],
            "description": ["L&#39;ergonomie", "Id&eacute;es", "texte simple"],
        }
    )

    nettoye, avec_html = controler_html_rakuten(produits, get_rule("RAKUTEN_PRODUITS_01"))

    assert list(avec_html["designation"]) == ["Stylet", "Carnet"]
    assert list(nettoye["description"]) == ["L'ergonomie", "Idées", "texte simple"]


def test_html_detecte_les_balises_et_les_retire_du_texte_nettoye():
    produits = pd.DataFrame({"designation": ["A"], "description": ["<p>Petit<br>carnet</p>"]})

    nettoye, avec_html = controler_html_rakuten(produits, get_rule("RAKUTEN_PRODUITS_01"))

    assert len(avec_html) == 1
    assert nettoye.loc[0, "description"] == "Petitcarnet"


def test_description_absente_ne_rejette_pas_la_fiche():
    produits = pd.DataFrame({"designation": ["A", "B", "C"], "description": ["x", None, " "]})

    valides, sans_description = controle.controler_descriptions_absentes(
        produits, get_rule("RAKUTEN_PRODUITS_02")
    )

    assert len(valides) == 3
    assert len(sans_description) == 2


def test_designations_identiques_signalees_jamais_dedupliquees():
    produits = pd.DataFrame({"designation": ["Carnet", "Carnet", "Stylo", ""]})

    valides, repetees = controler_designations_dupliquees(produits, get_rule("RAKUTEN_PRODUITS_03"))

    assert len(valides) == 4
    assert len(repetees) == 2
    # Le chiffre de référence du catalogue (2 651) est duplicated().sum() :
    # une occurrence en trop par désignation répétée.
    assert int(produits["designation"].duplicated().sum()) == 1


def test_langue_compte_les_textes_non_analysables_sans_filtrer():
    produits = pd.DataFrame({"designation": ["Carnet", "", None]})

    valides, vides = controler_langue_rakuten(produits, get_rule("RAKUTEN_PRODUITS_04"))

    assert len(valides) == 3
    assert len(vides) == 2


# --- Lecture de la zone brute --------------------------------------------------


def test_lecture_en_texte_garde_les_zeros_initiaux_et_le_texte_na(tmp_path):
    chemin = tmp_path / "customers.csv"
    chemin.write_text("zip,ville\n01037,NA\n09790,\n", encoding="utf-8")

    df = lire_csv(chemin)

    assert list(df["zip"]) == ["01037", "09790"]
    assert df.loc[0, "ville"] == "NA"
    assert pd.isna(df.loc[1, "ville"])


def test_une_ingestion_est_obligatoire():
    with pytest.raises(ValueError, match="--ingestion"):
        resoudre_ingestion("olist", None)


def test_olist_se_lit_dans_les_lots_de_la_boutique(ingestion_olist, racine_brute):
    assert resoudre_ingestion("olist", INGESTION_OLIST, racine_brute) == ingestion_olist


def test_une_ingestion_sans_manifeste_est_refusee(racine_brute):
    dossier = racine_brute / "lots" / "boutique" / "ingestion=20260101T000000"
    dossier.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Manifeste"):
        resoudre_ingestion("olist", "20260101T000000", racine_brute)


def test_un_fichier_manquant_dans_l_ingestion_arrete_le_controle(ingestion_olist):
    (ingestion_olist / "order_reviews.csv").unlink()

    with pytest.raises(FileNotFoundError, match="order_reviews.csv"):
        controler_olist(ingestion_olist)


# --- Contrôle complet d'une ingestion Olist ------------------------------------


@pytest.fixture
def resultat_olist(ingestion_olist, racine_brute):
    return controler("olist", INGESTION_OLIST, racine_brute)


def test_les_huit_commandes_livrees_sans_date_partent_reellement_en_quarantaine(
    resultat_olist,
):
    (lot,) = _rejets(resultat_olist, "OLIST_COMMANDES_02")

    assert len(lot.lignes) == NB_LIVREES_SANS_DATE
    assert lot.table == "orders"
    assert lot.fichier == "orders.csv"
    assert set(lot.lignes["order_status"]) == {"delivered"}
    assert lot.lignes["order_delivered_customer_date"].isna().all()
    # … et ne sont pas chargées en staging
    commandes_valides = set(resultat_olist.valides["olist_orders"]["order_id"])
    assert commandes_valides.isdisjoint(lot.lignes["order_id"])
    assert len(commandes_valides) == NB_COMMANDES - NB_LIVREES_SANS_DATE


def test_le_journal_annonce_ce_qui_est_reellement_en_quarantaine(resultat_olist):
    journal = _journal(resultat_olist)

    for regle, entree in journal.items():
        reellement = sum(len(lot.lignes) for lot in _rejets(resultat_olist, regle))
        assert entree["lignes_quarantaine"] == reellement, regle


def test_chaque_regle_d_avis_a_son_propre_compte_de_rejets(resultat_olist):
    journal = _journal(resultat_olist)

    assert journal["OLIST_AVIS_01"]["lignes_quarantaine"] == NB_REVIEW_ID_DUPLIQUES
    assert journal["OLIST_AVIS_02"]["lignes_quarantaine"] == NB_AVIS_EN_TROP_PAR_COMMANDE
    (lot_01,) = _rejets(resultat_olist, "OLIST_AVIS_01")
    (lot_02,) = _rejets(resultat_olist, "OLIST_AVIS_02")
    assert list(lot_01.lignes["order_id"]) == ["o11"]
    assert list(lot_02.lignes["review_id"]) == ["r03"]


def test_comptes_des_regles_olist(resultat_olist):
    journal = _journal(resultat_olist)

    assert journal["OLIST_COMMANDES_02"]["lignes_quarantaine"] == NB_LIVREES_SANS_DATE
    assert journal["OLIST_CLIENTS_01"]["lignes_quarantaine"] == NB_CLIENTS_SANS_IDENTIFIANT
    assert journal["OLIST_GEOLOCALISATION_01"]["lignes_supprimees"] == NB_GEO_DOUBLONS_STRICTS
    assert journal["OLIST_COMMANDES_01"]["anomalies"] == NB_COMMANDES_SANS_ARTICLE
    assert journal["OLIST_PAIEMENTS_01"]["anomalies"] == NB_COMMANDES_PAIEMENT_MULTIPLE
    assert journal["OLIST_ARTICLES_01"]["anomalies"] == NB_PRODUITS_SANS_CATEGORIE
    assert journal["OLIST_AVIS_03"]["anomalies"] == NB_AVIS_SANS_COMMENTAIRE


def test_toutes_les_regles_olist_du_catalogue_sont_executees(resultat_olist):
    from quality.rules import get_rules

    executees = {c["regle"] for c in resultat_olist.controles}

    assert executees == {r["identifiant"] for r in get_rules("olist")}


def test_conservation_des_lignes_pour_chaque_regle(resultat_olist):
    # Aucune règle ne perd ni n'invente de ligne : ce qui entre ressort
    # valide, rejeté ou supprimé silencieusement.
    for c in resultat_olist.controles:
        assert c["lignes_initiales"] == (
            c["lignes_valides"] + c["lignes_quarantaine"] + c["lignes_supprimees"]
        ), c["regle"]


def test_seules_les_regles_bloquantes_mettent_en_quarantaine(resultat_olist):
    for lot in resultat_olist.rejets:
        assert lot.regle["gravite"] == "bloquante"
    for c in resultat_olist.controles:
        if c["gravite"] != "bloquante":
            assert c["lignes_quarantaine"] == 0, c["regle"]


def test_bilan_global_olist(resultat_olist):
    rejetees = (
        NB_LIVREES_SANS_DATE
        + NB_REVIEW_ID_DUPLIQUES
        + NB_AVIS_EN_TROP_PAR_COMMANDE
        + NB_CLIENTS_SANS_IDENTIFIANT
    )

    assert resultat_olist.lignes_rejetees == rejetees
    assert resultat_olist.lignes_supprimees == NB_GEO_DOUBLONS_STRICTS
    assert resultat_olist.lignes_lues == (
        resultat_olist.lignes_ecrites + rejetees + NB_GEO_DOUBLONS_STRICTS
    )


def test_les_neuf_tables_de_staging_olist_sont_alimentees(resultat_olist):
    from quality.chargement import TABLES_PAR_SOURCE

    assert set(resultat_olist.valides) == set(TABLES_PAR_SOURCE["olist"])
    assert len(resultat_olist.valides["olist_order_reviews"]) == 4
    assert len(resultat_olist.valides["olist_order_payments"]) == NB_COMMANDES + 1


def test_la_categorie_inconnue_est_chargee_en_staging(resultat_olist):
    produits = resultat_olist.valides["olist_products"].set_index("product_id")

    assert produits.loc["p2", "product_category_name"] == "inconnu"


# --- Contrôle complet d'une ingestion Rakuten ----------------------------------


@pytest.fixture
def resultat_rakuten(ingestion_rakuten, racine_brute):
    return controler("rakuten", INGESTION_RAKUTEN, racine_brute)


def test_rakuten_execute_les_quatre_regles_du_catalogue(resultat_rakuten):
    journal = _journal(resultat_rakuten)

    assert set(journal) == {
        "RAKUTEN_PRODUITS_01",
        "RAKUTEN_PRODUITS_02",
        "RAKUTEN_PRODUITS_03",
        "RAKUTEN_PRODUITS_04",
    }
    assert journal["RAKUTEN_PRODUITS_01"]["anomalies"] == 3
    assert journal["RAKUTEN_PRODUITS_02"]["anomalies"] == 2
    assert journal["RAKUTEN_PRODUITS_03"]["anomalies"] == 2
    assert journal["RAKUTEN_PRODUITS_04"]["anomalies"] == 0


def test_rakuten_ne_rejette_aucune_fiche(resultat_rakuten):
    assert resultat_rakuten.rejets == []
    assert resultat_rakuten.lignes_rejetees == 0
    assert resultat_rakuten.lignes_lues == 6
    assert resultat_rakuten.lignes_ecrites == 6


def test_rakuten_prepare_le_format_de_staging(resultat_rakuten):
    staging = resultat_rakuten.valides["rakuten_produits"]

    assert list(staging["index_ligne"]) == ["0", "1", "2", "3", "4", "5"]
    assert set(staging["jeu"]) == {"train"}
    # Le texte chargé est celui de la zone brute : le décodage est fait par la
    # transformation (F1.7), pas deux fois.
    assert staging.loc[2, "description"] == "L&#39;ergonomie<br>parfaite"
    assert staging.loc[5, "designation"] == "NA"


def test_rakuten_une_fiche_sans_categorie_appartient_au_jeu_de_test():
    df = pd.DataFrame({"source_index": ["0", "1"], "prdtypecode": ["10", None]})

    assert list(controle.preparer_rakuten_staging(df)["jeu"]) == ["train", "test"]


# --- Ligne de commande ----------------------------------------------------------


def test_la_ligne_de_commande_rakuten_controle_reellement(
    ingestion_rakuten, racine_brute, monkeypatch, capsys
):
    monkeypatch.setenv("DATA_DIR", str(racine_brute.parent))

    code = controle.main(
        ["--source", "rakuten", "--ingestion", INGESTION_RAKUTEN, "--sans-chargement"]
    )

    sortie = capsys.readouterr().out
    assert code == 0
    for regle in ("RAKUTEN_PRODUITS_01", "RAKUTEN_PRODUITS_04"):
        assert regle in sortie
    assert "Essai à blanc" in sortie


def test_la_ligne_de_commande_sans_ingestion_echoue_proprement(capsys):
    assert controle.main(["--source", "olist"]) == 1
    assert "--ingestion" in capsys.readouterr().err


def test_l_export_csv_d_audit_est_range_par_ingestion(ingestion_olist, racine_brute, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(racine_brute.parent))

    code = controle.main(
        ["--source", "olist", "--ingestion", INGESTION_OLIST, "--sans-chargement", "--export-csv"]
    )

    dossier = racine_brute.parent / "audit_qualite" / "olist" / f"ingestion={INGESTION_OLIST}"
    assert code == 0
    assert (dossier / "valides" / "olist_orders.csv").exists()
    assert (dossier / "rejets" / "orders_OLIST_COMMANDES_02.csv").exists()
    journal = pd.read_csv(dossier / "execution_log.csv")
    assert len(journal) == 9
