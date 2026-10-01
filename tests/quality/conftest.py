"""Ingestions synthétiques de la zone brute pour tester le contrôle qualité.

Chaque défaut y est placé en nombre connu, pour que les tests puissent
vérifier des comptes exacts plutôt que « quelque chose a été rejeté ».
Les fichiers ont le format produit par l'acquisition : CSV avec en-tête,
cellule vide pour NULL, manifeste à côté.
"""

import csv

import pytest

from zone_brute.manifeste import construire_manifeste, ecrire_manifeste

INGESTION_OLIST = "20260930T120000"
INGESTION_RAKUTEN = "20260930T120500"

# Défauts placés dans l'ingestion Olist synthétique
NB_COMMANDES = 20
NB_LIVREES_SANS_DATE = 8  # OLIST_COMMANDES_02 — bloquante
NB_COMMANDES_SANS_ARTICLE = 1  # OLIST_COMMANDES_01 — non bloquante
NB_REVIEW_ID_DUPLIQUES = 1  # OLIST_AVIS_01 — bloquante
NB_AVIS_EN_TROP_PAR_COMMANDE = 1  # OLIST_AVIS_02 — bloquante
NB_AVIS_SANS_COMMENTAIRE = 2  # OLIST_AVIS_03 — non bloquante
NB_COMMANDES_PAIEMENT_MULTIPLE = 1  # OLIST_PAIEMENTS_01 — non bloquante
NB_PRODUITS_SANS_CATEGORIE = 1  # OLIST_ARTICLES_01 — non bloquante
NB_CLIENTS_SANS_IDENTIFIANT = 1  # OLIST_CLIENTS_01 — bloquante
NB_GEO_DOUBLONS_STRICTS = 1  # OLIST_GEOLOCALISATION_01 — silencieuse


def _ecrire(chemin, entetes, lignes):
    with open(chemin, "w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(entetes)
        ecrivain.writerows(lignes)


def _finaliser(dossier, source, ingestion):
    fichiers = sorted(dossier.glob("*.csv"))
    ecrire_manifeste(construire_manifeste(source, ingestion, fichiers), dossier / "manifeste.json")


def construire_ingestion_olist(racine_brute, ingestion=INGESTION_OLIST):
    dossier = racine_brute / "lots" / "boutique" / f"ingestion={ingestion}"
    dossier.mkdir(parents=True)

    commandes = [f"o{i:02d}" for i in range(1, NB_COMMANDES + 1)]

    # orders : o01..o08 livrées sans date ; o09 expédiée sans date (légitime) ;
    # o20 n'a aucun article.
    orders = []
    for i, order_id in enumerate(commandes, start=1):
        if i <= NB_LIVREES_SANS_DATE:
            statut, livree = "delivered", ""
        elif i == 9:
            statut, livree = "shipped", ""
        else:
            statut, livree = "delivered", "2018-01-10 10:00:00"
        orders.append(
            [
                order_id,
                f"c{i:02d}",
                statut,
                "2018-01-01 09:00:00",
                "2018-01-01 09:30:00",
                "2018-01-03 12:00:00",
                livree,
                "2018-01-15 00:00:00",
            ]
        )
    _ecrire(
        dossier / "orders.csv",
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        orders,
    )

    _ecrire(
        dossier / "order_items.csv",
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ],
        [
            [order_id, 1, "p1" if i % 2 else "p2", "s1", "2018-01-02 00:00:00", "29.90", "8.72"]
            for i, order_id in enumerate(commandes[:-NB_COMMANDES_SANS_ARTICLE], start=1)
        ],
    )

    paiements = [[order_id, 1, "credit_card", 1, "38.62"] for order_id in commandes]
    paiements.append(["o10", 2, "voucher", 1, "10.00"])  # o10 : deux paiements
    _ecrire(
        dossier / "order_payments.csv",
        [
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ],
        paiements,
    )

    _ecrire(
        dossier / "order_reviews.csv",
        [
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ],
        [
            [
                "r01",
                "o10",
                5,
                "",
                "très bien\nlivré vite",
                "2018-01-11 00:00:00",
                "2018-01-12 10:00:00",
            ],
            ["r01", "o11", 4, "", "même review_id", "2018-01-11 00:00:00", "2018-01-12 10:00:00"],
            ["r02", "o12", 3, "", "premier avis", "2018-01-11 00:00:00", "2018-01-12 10:00:00"],
            ["r03", "o12", 1, "", "second avis", "2018-01-11 00:00:00", "2018-01-12 10:00:00"],
            ["r04", "o13", 5, "", "", "2018-01-11 00:00:00", "2018-01-12 10:00:00"],
            ["r05", "o14", 2, "titre", "", "2018-01-11 00:00:00", "2018-01-12 10:00:00"],
        ],
    )

    _ecrire(
        dossier / "products.csv",
        [
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ],
        [
            ["p1", "perfumaria", 40, 287, 1, 225, 16, 10, 14],
            ["p2", "", "", "", "", 1000, 30, 18, 20],
        ],
    )

    clients = [
        [f"c{i:02d}", f"u{i:02d}", "01037", "sao paulo", "SP"] for i in range(1, NB_COMMANDES + 1)
    ]
    clients[-1][1] = ""  # c20 : customer_unique_id absent
    _ecrire(
        dossier / "customers.csv",
        [
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
        clients,
    )

    _ecrire(
        dossier / "sellers.csv",
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        [["s1", "09350", "maua", "SP"]],
    )

    _ecrire(
        dossier / "geolocation.csv",
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ],
        [
            ["01037", "-23.54562128115268", "-46.63929204800168", "sao paulo", "SP"],
            ["01037", "-23.54562128115268", "-46.63929204800168", "sao paulo", "SP"],
            ["09350", "-23.6", "-46.4", "maua", "SP"],
        ],
    )

    _ecrire(
        dossier / "category_translation.csv",
        ["product_category_name", "product_category_name_english"],
        [["perfumaria", "perfumery"], ["artes", "art"]],
    )

    _finaliser(dossier, "boutique", ingestion)
    return dossier


def construire_ingestion_rakuten(racine_brute, ingestion=INGESTION_RAKUTEN):
    dossier = racine_brute / "lots" / "rakuten" / f"ingestion={ingestion}"
    dossier.mkdir(parents=True)
    _ecrire(
        dossier / "rakuten_catalogue_produits.csv",
        ["source_index", "productid", "imageid", "prdtypecode", "designation", "description"],
        [
            [0, "3804725264", "1263597046", 10, "Carnet", ""],
            [1, "436067568", "1008141237", 2280, "Journal des arts", "Id&eacute;es cadeaux"],
            [2, "201115110", "938777978", 50, "Stylet", "L&#39;ergonomie<br>parfaite"],
            [3, "50418756", "457047496", 1280, "Carnet", "<p>Petit carnet</p>"],
            [4, "278535884", "1077757786", 2705, "Livre de cuisine", ""],
            [5, "5862738", "393356830", 2280, "NA", "Le texte « NA » reste du texte"],
        ],
    )
    _finaliser(dossier, "rakuten", ingestion)
    return dossier


@pytest.fixture
def racine_brute(tmp_path):
    return tmp_path / "raw"


@pytest.fixture
def ingestion_olist(racine_brute):
    return construire_ingestion_olist(racine_brute)


@pytest.fixture
def ingestion_rakuten(racine_brute):
    return construire_ingestion_rakuten(racine_brute)
