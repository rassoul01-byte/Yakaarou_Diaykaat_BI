"""Tests des indicateurs de ventes.

Le cœur du test est un petit entrepôt construit à la main, dont le chiffre
d'affaires et le panier moyen sont calculés sur le papier — c'est le seul
moyen de vérifier une formule : la comparer à ce qu'on attendait, pas à ce
que la base renvoie.

L'entrepôt d'essai :

  commande  statut     lignes               prix       frais  dans le CA ?
  ---------------------------------------------------------------------
  o1        delivered  2 lignes             100 + 50   10+5   oui → 150
  o2        delivered  1 ligne              200        20     oui → 200
  o3        canceled   1 ligne              999        99     NON (annulée)
  o4        delivered  aucune ligne         —          —      NON (pèse zéro)

  Chiffre d'affaires attendu : 350,00   Commandes : 2   Panier moyen : 175,00
"""

from pathlib import Path

import psycopg2
import pytest

from indicateurs.lecture import collecter

RACINE = Path(__file__).resolve().parents[2]
VUES = RACINE / "sql" / "010_vues_indicateurs.sql"
VUES_ISO = RACINE / "sql" / "025_annee_iso.sql"

# Les deux fichiers sont appliqués dans l'ordre des migrations. `dim_date` est
# créée SANS `annee_iso` ci-dessous : c'est sql/025 qui ajoute la colonne et la
# remplit depuis `date`, exactement comme sur la base réelle. Le test couvre
# donc aussi la reprise des lignes déjà chargées.
MIGRATIONS = (VUES, VUES_ISO)

ENTREPOT_D_ESSAI = """
DROP SCHEMA IF EXISTS dwh CASCADE;
CREATE SCHEMA dwh;

CREATE TABLE dwh.dim_date (
    date_id integer PRIMARY KEY, date date, annee integer, mois integer,
    semaine_iso integer, jour integer);
CREATE TABLE dwh.dim_produit (
    produit_id integer PRIMARY KEY, id_produit_olist text, categorie text,
    categorie_catalogue text, id_fiche_rakuten text, rattache boolean, langue text);
CREATE TABLE dwh.dim_vendeur (vendeur_id integer PRIMARY KEY, id_vendeur_olist text);
CREATE TABLE dwh.dim_client (client_id integer PRIMARY KEY, customer_unique_id text);
CREATE TABLE dwh.fait_commande (
    order_id text PRIMARY KEY, client_id integer, date_id integer, statut text,
    montant_paye numeric(12,2), nombre_paiements integer, a_une_ligne_article boolean);
CREATE TABLE dwh.fait_ligne_commande (
    order_id text, order_item_id integer, produit_id integer, vendeur_id integer,
    date_id integer, prix numeric(10,2), frais_port numeric(10,2), quantite integer DEFAULT 1,
    PRIMARY KEY (order_id, order_item_id));

INSERT INTO dwh.dim_date VALUES
    (0, '1900-01-01', 0, 0, 0, 0),
    (20170315, '2017-03-15', 2017, 3, 11, 15),
    (20170410, '2017-04-10', 2017, 4, 15, 10);
INSERT INTO dwh.dim_produit VALUES
    (0, 'inconnu', 'inconnu', 'inconnu', NULL, false, NULL),
    (1, 'p-chaise', 'meubles', 'mobilier', 'f-1', true, 'fr'),
    (2, 'p-lampe', 'luminaires', 'maison', 'f-2', true, 'fr');
INSERT INTO dwh.dim_vendeur VALUES (0, 'inconnu'), (1, 'v-1');
INSERT INTO dwh.dim_client VALUES (0, 'inconnu'), (1, 'c-1');

INSERT INTO dwh.fait_commande VALUES
    ('o1', 1, 20170315, 'delivered', 165.00, 1, true),
    ('o2', 1, 20170410, 'delivered', 220.00, 2, true),
    ('o3', 1, 20170410, 'canceled',  999.00, 1, true),
    ('o4', 1, 20170410, 'delivered',   0.00, 1, false);
INSERT INTO dwh.fait_ligne_commande VALUES
    ('o1', 1, 1, 1, 20170315, 100.00, 10.00, 1),
    ('o1', 2, 2, 1, 20170315,  50.00,  5.00, 1),
    ('o2', 1, 1, 1, 20170410, 200.00, 20.00, 1),
    ('o3', 1, 2, 1, 20170410, 999.00, 99.00, 1);
"""


@pytest.fixture
def entrepot(dsn_test):
    """Un entrepôt d'essai, avec les vues réelles appliquées dessus.

    Tout se passe dans la base d'essai (voir conftest.py) : la base du projet
    n'est jamais touchée.
    """
    with psycopg2.connect(dsn_test) as cnx:
        cnx.autocommit = True
        with cnx.cursor() as curseur:
            curseur.execute(ENTREPOT_D_ESSAI)
            for migration in MIGRATIONS:
                curseur.execute(migration.read_text(encoding="utf-8"))
    return dsn_test


# --- Les formules -----------------------------------------------------------


@pytest.mark.integration
def test_le_chiffre_d_affaires_est_celui_calcule_a_la_main(entrepot):
    totaux = collecter()["totaux"]

    assert float(totaux["chiffre_affaires"]) == 350.00


@pytest.mark.integration
def test_les_frais_de_port_ne_sont_pas_dans_le_chiffre_d_affaires(entrepot):
    # 350 avec les frais de port ferait 385 : la décision se voit dans le chiffre.
    assert float(collecter()["totaux"]["chiffre_affaires"]) != 385.00


@pytest.mark.integration
def test_une_commande_annulee_ne_compte_pas(entrepot):
    totaux = collecter()["totaux"]

    assert float(totaux["chiffre_affaires"]) == 350.00  # et non 1349
    assert totaux["commandes"] == 2


@pytest.mark.integration
def test_une_commande_sans_article_pese_zero_et_n_entre_pas_au_denominateur(entrepot):
    totaux = collecter()["totaux"]

    assert totaux["commandes"] == 2
    assert float(totaux["panier_moyen"]) == 175.00  # 350 / 2, et non 350 / 3


@pytest.mark.integration
def test_le_panier_moyen_est_le_chiffre_d_affaires_sur_les_commandes(entrepot):
    totaux = collecter()["totaux"]
    attendu = round(float(totaux["chiffre_affaires"]) / totaux["commandes"], 2)

    assert float(totaux["panier_moyen"]) == attendu


# --- Les périodes se recoupent ----------------------------------------------


@pytest.mark.integration
def test_la_somme_des_mois_egale_le_total(entrepot):
    donnees = collecter(periode="mois")
    somme = sum(float(ligne["chiffre_affaires"]) for ligne in donnees["series"])

    assert somme == float(donnees["totaux"]["chiffre_affaires"])


@pytest.mark.integration
def test_la_somme_des_jours_egale_le_total(entrepot):
    donnees = collecter(periode="jour")
    somme = sum(float(ligne["chiffre_affaires"]) for ligne in donnees["series"])

    assert somme == float(donnees["totaux"]["chiffre_affaires"])


@pytest.mark.integration
def test_chaque_periode_a_sa_vue(entrepot):
    for periode in ("jour", "semaine", "mois"):
        assert collecter(periode=periode)["series"], f"aucune ligne pour {periode}"


# --- La frontière d'année ---------------------------------------------------
#
# Il manquait le symétrique des deux tests ci-dessus pour la semaine, et le jeu
# d'essai principal évite les frontières d'année (mars et avril). Les deux
# ensemble laissaient passer le défaut : `semaine_iso` était appariée à l'année
# CIVILE, donc le 2017-01-01 — semaine 52 de l'année ISO 2016 — se rangeait dans
# « 2017-S52 », avec la semaine de Noël 2017. Voir sql/025.

ENTREPOT_FRONTIERE = """
DROP SCHEMA IF EXISTS dwh CASCADE;
CREATE SCHEMA dwh;

CREATE TABLE dwh.dim_date (
    date_id integer PRIMARY KEY, date date, annee integer, mois integer,
    semaine_iso integer, jour integer);
CREATE TABLE dwh.dim_produit (
    produit_id integer PRIMARY KEY, id_produit_olist text, categorie text,
    categorie_catalogue text, id_fiche_rakuten text, rattache boolean, langue text);
CREATE TABLE dwh.dim_vendeur (vendeur_id integer PRIMARY KEY, id_vendeur_olist text);
CREATE TABLE dwh.dim_client (client_id integer PRIMARY KEY, customer_unique_id text);
CREATE TABLE dwh.fait_commande (
    order_id text PRIMARY KEY, client_id integer, date_id integer, statut text,
    montant_paye numeric(12,2), nombre_paiements integer, a_une_ligne_article boolean);
CREATE TABLE dwh.fait_ligne_commande (
    order_id text, order_item_id integer, produit_id integer, vendeur_id integer,
    date_id integer, prix numeric(10,2), frais_port numeric(10,2), quantite integer DEFAULT 1,
    PRIMARY KEY (order_id, order_item_id));

-- Les deux dates portent la MÊME semaine ISO 52 et la même année civile 2017.
-- Seule l'année ISO les sépare : 2016 pour le 1er janvier, 2017 pour le 26 décembre.
INSERT INTO dwh.dim_date VALUES
    (20170101, '2017-01-01', 2017,  1, 52,  1),
    (20171226, '2017-12-26', 2017, 12, 52, 26);
INSERT INTO dwh.dim_produit VALUES (1, 'p-chaise', 'meubles', 'mobilier', 'f-1', true, 'fr');
INSERT INTO dwh.dim_vendeur VALUES (1, 'v-1');
INSERT INTO dwh.dim_client  VALUES (1, 'c-1');

INSERT INTO dwh.fait_commande VALUES
    ('a1', 1, 20170101, 'delivered',  40.00, 1, true),
    ('a2', 1, 20171226, 'delivered',  60.00, 1, true);
INSERT INTO dwh.fait_ligne_commande VALUES
    ('a1', 1, 1, 1, 20170101, 40.00, 4.00, 1),
    ('a2', 1, 1, 1, 20171226, 60.00, 6.00, 1);
"""


@pytest.fixture
def entrepot_frontiere(dsn_test):
    with psycopg2.connect(dsn_test) as cnx:
        cnx.autocommit = True
        with cnx.cursor() as curseur:
            curseur.execute(ENTREPOT_FRONTIERE)
            for migration in MIGRATIONS:
                curseur.execute(migration.read_text(encoding="utf-8"))
    return dsn_test


@pytest.mark.integration
def test_la_somme_des_semaines_egale_le_total(entrepot_frontiere):
    donnees = collecter(periode="semaine")
    somme = sum(float(ligne["chiffre_affaires"]) for ligne in donnees["series"])

    assert somme == float(donnees["totaux"]["chiffre_affaires"]) == 100.00


@pytest.mark.integration
def test_le_premier_janvier_n_est_pas_dans_la_semaine_de_noel(entrepot_frontiere):
    """Deux semaines distinctes, pas une seule ligne à 100 €."""
    series = collecter(periode="semaine")["series"]
    par_periode = {ligne["periode"]: float(ligne["chiffre_affaires"]) for ligne in series}

    assert par_periode == {"2016-S52": 40.00, "2017-S52": 60.00}


# --- Classements ------------------------------------------------------------


@pytest.mark.integration
def test_le_produit_le_plus_vendu_est_celui_qui_rapporte_le_plus(entrepot):
    produits = collecter()["produits"]

    assert produits[0]["id_produit_olist"] == "p-chaise"  # 100 + 200 = 300
    assert float(produits[0]["chiffre_affaires"]) == 300.00


@pytest.mark.integration
def test_les_categories_sont_classees_par_chiffre_d_affaires(entrepot):
    categories = collecter()["categories"]

    assert [c["categorie"] for c in categories][:2] == ["meubles", "luminaires"]


@pytest.mark.integration
def test_les_lignes_annulees_sont_absentes_des_classements(entrepot):
    # p-lampe n'a que 50 retenus : les 999 de la commande annulée sont exclus.
    lampe = next(p for p in collecter()["produits"] if p["id_produit_olist"] == "p-lampe")

    assert float(lampe["chiffre_affaires"]) == 50.00


# --- Le reste, sans base de données ----------------------------------------


def test_une_periode_inconnue_est_refusee():
    with pytest.raises(ValueError, match="période inconnue"):
        collecter(periode="trimestre")


def test_un_entrepot_vide_ne_fait_pas_echouer_le_rapport(capsys):
    from indicateurs.__main__ import afficher

    afficher({"periode": "mois", "totaux": {}, "series": [], "categories": [], "produits": []})

    assert "Aucune vente dans l'entrepôt" in capsys.readouterr().out


def test_une_base_injoignable_donne_un_message_lisible_et_le_code_1(monkeypatch, capsys):
    from indicateurs.__main__ import main

    def refuser(*_a, **_k):
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(psycopg2, "connect", refuser)

    assert main([]) == 1
    erreurs = capsys.readouterr().err
    assert "ERREUR" in erreurs and "Traceback" not in erreurs
