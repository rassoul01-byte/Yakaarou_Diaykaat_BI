"""
Moteur de contrôle qualité des données DataFlow360.

F1.5 - Contrôler la conformité des données avant intégration.

Ce module :
- lit les données depuis la zone RAW ;
- applique les contrôles qualité ;
- respecte les gravités définies dans rules.py ;
- prépare les résultats pour les futures zones staging/quarantine.
"""

import argparse
import html
from pathlib import Path

import pandas as pd

from src.quality.rules import get_rules
from src.quality.schemas import schema_avis
from src.quality.sorties import ecrire_staging, ecrire_quarantaine, ecrire_execution_log


# ---------------------------------------------------------------------------
# Chemins des données RAW / zone brute
# ---------------------------------------------------------------------------

RAW_DIR = Path("data/raw")

# Le catalogue F1.5 utilise "olist" comme source métier.
# L'acquisition SQL du Sprint 1 dépose physiquement les fichiers
# dans data/raw/lots/boutique/ingestion=<horodatage>/.
INGESTION_DIR = None


def chemin_olist(nom_fichier):
    """Retourne le chemin d'un fichier Olist dans l'ingestion sélectionnée."""
    if INGESTION_DIR is None:
        raise RuntimeError(
            "Aucune ingestion Olist sélectionnée. "
            "Utilisez --ingestion AAAAMMJJTHHMMSS."
        )

    chemin = INGESTION_DIR / nom_fichier

    if not chemin.exists():
        raise FileNotFoundError(
            f"Fichier absent de l'ingestion : {chemin}"
        )

    return chemin


def resoudre_ingestion(source, ingestion):
    """Résout explicitement le dossier d'une ingestion.

    Pour Olist, les données proviennent de la source SQL 'boutique'.
    Le paramètre --ingestion évite de sélectionner implicitement
    la dernière ingestion.
    """
    if not ingestion:
        raise ValueError(
            "--ingestion est obligatoire pour contrôler une source par lot."
        )

    if source == "olist":
        source_physique = "boutique"
    else:
        source_physique = source

    dossier = RAW_DIR / "lots" / source_physique / f"ingestion={ingestion}"

    if not dossier.is_dir():
        raise FileNotFoundError(
            f"Ingestion introuvable : {dossier}"
        )

    manifeste = dossier / "manifeste.json"

    if not manifeste.is_file():
        raise FileNotFoundError(
            f"Manifeste absent : {manifeste}"
        )

    return dossier


def valider_avec_pandera(df, schema, nom_schema):
    """
    Valide un DataFrame avec Pandera.

    lazy=True permet de récupérer toutes les erreurs
    de validation en une seule exécution.
    """
    try:
        df_valide = schema.validate(df, lazy=True)

        print(f"\nValidation Pandera : {nom_schema}")
        print("Statut : OK")
        print("Lignes validées :", len(df_valide))

        return df_valide

    except Exception as erreur:
        print(f"\nValidation Pandera : {nom_schema}")
        print("Statut : ERREUR")
        print(erreur)

        return None



# ---------------------------------------------------------------------------
# Lecture des données
# ---------------------------------------------------------------------------

def lire_csv(chemin):
    """Charge un fichier CSV et retourne un DataFrame."""
    print(f"\nLecture : {chemin}")

    df = pd.read_csv(chemin)

    print(f"Lignes chargées : {len(df)}")
    print(f"Colonnes : {len(df.columns)}")

    return df


# ---------------------------------------------------------------------------
# Contrôle des doublons stricts
# ---------------------------------------------------------------------------

def controler_doublons_stricts(df, rule):
    """
    Contrôle les doublons stricts d'un DataFrame.

    Gravité :
        silencieuse

    Comportement :
        - les doublons stricts sont retirés ;
        - les lignes supprimées sont comptées ;
        - aucune ligne n'est envoyée en quarantaine.
    """

    avant = len(df)

    df_sans_doublons = df.drop_duplicates().copy()

    supprimes = avant - len(df_sans_doublons)

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Lignes avant :", avant)
    print("Doublons stricts supprimés :", supprimes)
    print("Lignes après :", len(df_sans_doublons))

    return df_sans_doublons, supprimes



# ---------------------------------------------------------------------------
# Contrôle Olist géolocalisation
# ---------------------------------------------------------------------------


def controler_review_id(df, rule):
    """
    Contrôle OLIST_AVIS_01.

    Gravité : bloquante
    - première occurrence conservée ;
    - doublons rejetés ;
    - validation finale avec Pandera ;
    - les rejets sont envoyés en quarantaine.
    """
    doublons = df["review_id"].duplicated(keep="first")

    df_quarantaine = df.loc[doublons].copy()
    df_valides = df.loc[~doublons].copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Lignes analysées :", len(df))
    print("Lignes conservées :", len(df_valides))
    print("Lignes rejetées :", len(df_quarantaine))

    df_valides_pandera = valider_avec_pandera(
        df_valides,
        schema_avis,
        rule["identifiant"],
    )

    if df_valides_pandera is None:
        print("ERREUR : les lignes conservées ne passent pas Pandera.")
        return pd.DataFrame(), df_quarantaine

    if not df_quarantaine.empty:
        ecrire_quarantaine(
            df_quarantaine,
            "olist",
            "order_reviews",
            rule["identifiant"],
        )

    return df_valides_pandera, df_quarantaine

def controler_avis_par_commande(df, rule):
    """
    Contrôle OLIST_AVIS_02.

    Une commande ne doit conserver qu'un seul avis.

    Gravité : bloquante
    - premier avis conservé ;
    - avis supplémentaires rejetés ;
    - rejets envoyés en quarantaine.
    """
    doublons = df["order_id"].duplicated(keep="first")

    df_valide = df.loc[~doublons].copy()
    df_quarantaine = df.loc[doublons].copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Lignes analysées :", len(df))
    print("Lignes conservées :", len(df_valide))
    print("Lignes rejetées :", len(df_quarantaine))

    return df_valide, df_quarantaine

def controler_commandes_sans_articles(df_orders, df_items, rule):
    """
    Contrôle que chaque commande possède au moins une ligne d'article.

    Gravité :
        non bloquante

    Comportement :
        - les commandes sans article sont détectées ;
        - elles restent conservées ;
        - elles sont comptées comme anomalies ;
        - aucune ligne n'est envoyée en quarantaine.
    """

    commandes_avec_articles = set(df_items["order_id"].dropna())

    masque_sans_articles = ~df_orders["order_id"].isin(
        commandes_avec_articles
    )

    df_sans_articles = df_orders.loc[masque_sans_articles].copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Commandes analysées :", len(df_orders))
    print("Commandes sans ligne d'article :", len(df_sans_articles))
    print("Lignes conservées :", len(df_orders))
    print("Lignes quarantaine :", 0)

    return df_orders.copy(), df_sans_articles

def controler_paiements_multiples(df_payments, rule):
    """
    Contrôle les commandes possédant plusieurs paiements.

    Gravité :
        non bloquante

    Comportement :
        - les paiements sont regroupés par order_id ;
        - le nombre de paiements par commande est calculé ;
        - les commandes avec plusieurs paiements sont détectées ;
        - les montants peuvent ensuite être agrégés avant les jointures.
    """

    paiements_par_commande = (
        df_payments
        .groupby("order_id")
        .size()
        .rename("nombre_paiements")
        .reset_index()
    )

    commandes_multiples = paiements_par_commande[
        paiements_par_commande["nombre_paiements"] > 1
    ].copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Paiements analysés :", len(df_payments))
    print(
        "Commandes avec plusieurs paiements :",
        len(commandes_multiples),
    )

    return paiements_par_commande, commandes_multiples

def controler_produits_sans_categorie(df_products, rule):
    """
    Contrôle les produits dont la catégorie est absente.

    Gravité :
        non bloquante

    Comportement :
        - les produits sans catégorie sont détectés ;
        - ils restent conservés ;
        - leur catégorie est représentée par « inconnu » ;
        - aucune ligne n'est envoyée en quarantaine.
    """

    masque_sans_categorie = (
        df_products["product_category_name"].isna()
        | (
            df_products["product_category_name"]
            .astype(str)
            .str.strip()
            .eq("")
        )
    )

    df_sans_categorie = df_products.loc[
        masque_sans_categorie
    ].copy()

    df_produits_valides = df_products.copy()

    df_produits_valides.loc[
        masque_sans_categorie,
        "product_category_name"
    ] = "inconnu"

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Produits analysés :", len(df_products))
    print(
        "Produits sans catégorie :",
        len(df_sans_categorie),
    )
    print("Produits conservés :", len(df_produits_valides))
    print("Lignes quarantaine :", 0)

    return df_produits_valides, df_sans_categorie

def controler_date_livraison(df_orders, rule):
    """
    Contrôle la présence de la date de livraison pour les commandes livrées.

    Gravité :
        bloquante

    Comportement :
        - une commande livrée doit avoir une date de livraison ;
        - les commandes livrées sans date sont rejetées ;
        - les autres commandes restent valides.
    """

    masque_livree_sans_date = (
        df_orders["order_status"].eq("delivered")
        & df_orders["order_delivered_customer_date"].isna()
    )

    df_quarantaine = df_orders.loc[
        masque_livree_sans_date
    ].copy()

    df_valides = df_orders.loc[
        ~masque_livree_sans_date
    ].copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Commandes analysées :", len(df_orders))
    print(
        "Commandes livrées sans date de livraison :",
        len(df_quarantaine),
    )
    print("Commandes conservées :", len(df_valides))
    print("Lignes quarantaine :", len(df_quarantaine))

    return df_valides, df_quarantaine

def controler_commentaires_absents(df_reviews, rule):
    """
    Contrôle les avis sans commentaire textuel.

    Gravité :
        non bloquante

    Comportement :
        - les avis sans commentaire sont détectés ;
        - ils restent conservés ;
        - aucune ligne n'est envoyée en quarantaine.
    """

    masque_sans_commentaire = (
        df_reviews["review_comment_message"].isna()
        | (
            df_reviews["review_comment_message"]
            .astype(str)
            .str.strip()
            .eq("")
        )
    )

    df_sans_commentaire = df_reviews.loc[
        masque_sans_commentaire
    ].copy()

    df_valides = df_reviews.copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Avis analysés :", len(df_reviews))
    print(
        "Avis sans commentaire textuel :",
        len(df_sans_commentaire),
    )
    print("Avis conservés :", len(df_valides))
    print("Lignes quarantaine :", 0)

    return df_valides, df_sans_commentaire

def controler_identifiant_client(df_customers, rule):
    """
    Contrôle la présence et l'utilisation de customer_unique_id.

    Gravité :
        bloquante

    Comportement :
        - customer_unique_id doit être présent ;
        - il sert d'identifiant de personne pour les agrégations ;
        - customer_id reste l'identifiant du contexte de commande.
    """

    masque_identifiant_absent = (
        df_customers["customer_unique_id"].isna()
        | (
            df_customers["customer_unique_id"]
            .astype(str)
            .str.strip()
            .eq("")
        )
    )

    df_quarantaine = df_customers.loc[
        masque_identifiant_absent
    ].copy()

    df_valides = df_customers.loc[
        ~masque_identifiant_absent
    ].copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Clients analysés :", len(df_customers))
    print(
        "customer_unique_id uniques :",
        df_customers["customer_unique_id"].nunique(),
    )
    print(
        "customer_id uniques :",
        df_customers["customer_id"].nunique(),
    )
    print("Clients conservés :", len(df_valides))
    print("Lignes quarantaine :", len(df_quarantaine))

    return df_valides, df_quarantaine

def controler_html_rakuten(df_products, rule):
    """
    Contrôle la présence de HTML dans les textes Rakuten.

    Gravité :
        non bloquante

    Comportement :
        - détecte les entités HTML ;
        - détecte les balises HTML ;
        - prépare une version nettoyée du texte ;
        - aucune ligne n'est envoyée en quarantaine.
    """

    designation = df_products["designation"].fillna("").astype(str)
    description = df_products["description"].fillna("").astype(str)

    masque_entites = (
        designation.str.contains(r"&(?:[a-zA-Z]+|#\\d+);", regex=True)
        | description.str.contains(r"&(?:[a-zA-Z]+|#\\d+);", regex=True)
    )

    masque_balises = (
        designation.str.contains(r"<[^>]+>", regex=True)
        | description.str.contains(r"<[^>]+>", regex=True)
    )

    masque_html = masque_entites | masque_balises

    df_nettoye = df_products.copy()

    df_nettoye["designation"] = (
        df_nettoye["designation"]
        .fillna("")
        .astype(str)
        .map(html.unescape)
        .str.replace(r"<[^>]+>", "", regex=True)
        .str.strip()
    )

    df_nettoye["description"] = (
        df_nettoye["description"]
        .fillna("")
        .astype(str)
        .map(html.unescape)
        .str.replace(r"<[^>]+>", "", regex=True)
        .str.strip()
    )

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Produits analysés :", len(df_products))
    print("Produits contenant des entités HTML :", int(masque_entites.sum()))
    print("Produits contenant des balises HTML :", int(masque_balises.sum()))
    print("Produits contenant du HTML :", int(masque_html.sum()))
    print("Produits conservés :", len(df_nettoye))
    print("Lignes quarantaine :", 0)

    return df_nettoye, df_products.loc[masque_html].copy()

def controler_descriptions_absentes(df_products, rule):
    """
    Contrôle les produits sans description.

    Gravité :
        non bloquante

    Comportement :
        - les descriptions absentes sont détectées ;
        - les produits restent conservés ;
        - aucune ligne n'est envoyée en quarantaine.
    """

    masque_sans_description = (
        df_products["description"].isna()
        | (
            df_products["description"]
            .astype(str)
            .str.strip()
            .eq("")
        )
    )

    df_sans_description = df_products.loc[
        masque_sans_description
    ].copy()

    df_valides = df_products.copy()

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Produits analysés :", len(df_products))
    print(
        "Produits sans description :",
        len(df_sans_description),
    )
    print("Produits conservés :", len(df_valides))
    print("Lignes quarantaine :", 0)

    return df_valides, df_sans_description

def controler_designations_dupliquees(df_products, rule):
    """
    Contrôle les désignations identiques entre plusieurs produits.

    Gravité :
        silencieuse

    Comportement :
        - les désignations répétées sont détectées ;
        - aucun produit n'est supprimé ;
        - aucune ligne n'est envoyée en quarantaine.
    """

    designation = (
        df_products["designation"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    masque_doublon = designation.duplicated(
        keep=False
    ) & designation.ne("")

    df_designations_dupliquees = df_products.loc[
        masque_doublon
    ].copy()

    df_valides = df_products.copy()

    nombre_designations_dupliquees = (
        designation[masque_doublon].nunique()
    )

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Produits analysés :", len(df_products))
    print(
        "Produits avec désignation répétée :",
        len(df_designations_dupliquees),
    )
    print(
        "Désignations distinctes répétées :",
        nombre_designations_dupliquees,
    )
    print("Produits conservés :", len(df_valides))
    print("Lignes quarantaine :", 0)

    return df_valides, df_designations_dupliquees

def controler_langue_rakuten(df_products, rule):
    """
    Contrôle de la langue du catalogue Rakuten.

    Gravité :
        non bloquante

    Comportement :
        - vérifie que les textes peuvent être analysés pour une
          future détection de langue ;
        - aucune fiche produit n'est supprimée ;
        - aucune ligne n'est envoyée en quarantaine.

    La détection effective de langue sera réalisée avec la
    dépendance prévue par le périmètre AD.
    """

    df_valides = df_products.copy()

    textes_non_vides = (
        df_valides["designation"]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    )

    nombre_textes_analysables = int(textes_non_vides.sum())

    print("\nContrôle :", rule["identifiant"])
    print("Gravité :", rule["gravite"])
    print("Condition :", rule["condition"])
    print("Produits analysés :", len(df_products))
    print(
        "Produits avec texte analysable :",
        nombre_textes_analysables,
    )
    print("Produits conservés :", len(df_valides))
    print("Lignes quarantaine :", 0)
    print(
        "Détection de langue : en attente de la dépendance AD"
    )

    return df_valides, df_products.loc[~textes_non_vides].copy()

def controler_olist_geolocation():
    """Applique les contrôles qualité Olist."""

    # ---------------------------------------------------------------
    # Contrôle 1 : doublons stricts de géolocalisation
    # ---------------------------------------------------------------

    chemin_geo = chemin_olist("geolocation.csv")

    df_geo = lire_csv(chemin_geo)

    rule_geo = get_rules("olist")[0]

    df_geo_valide, nb_geo_supprimes = controler_doublons_stricts(
        df_geo,
        rule_geo,
    )

    # ---------------------------------------------------------------
    # Contrôle 2 : review_id dupliqués
    # ---------------------------------------------------------------

    chemin_reviews = chemin_olist("order_reviews.csv")

    df_reviews = lire_csv(chemin_reviews)

    rule_review = get_rules("olist")[1]

    df_reviews_valide, df_reviews_quarantaine = controler_review_id(
        df_reviews,
        rule_review,
    )

    # ---------------------------------------------------------------
    # Contrôle 3 : un seul avis par commande
    # ---------------------------------------------------------------

    rule_order_review = get_rules("olist")[2]

    df_reviews_final, df_reviews_quarantaine = controler_avis_par_commande(
        df_reviews_valide,
        rule_order_review,
    )

    # STAGING FINAL OLIST_AVIS_02
    # Après les deux contrôles bloquants sur les avis,
    # seules les 98167 lignes conformes doivent rester en staging.
    ecrire_staging(
        df_reviews_final,
        "olist",
        "order_reviews",
    )
    print("STAGING FINAL OLIST_AVIS_02 :",
          len(df_reviews_final), "lignes")

    # Écriture des rejets OLIST_AVIS_02
    if not df_reviews_quarantaine.empty:
        ecrire_quarantaine(
            df_reviews_quarantaine,
            "olist",
            "order_reviews",
            rule_order_review["identifiant"],
        )

    # ---------------------------------------------------------------
    # Contrôle 4 : commandes sans ligne d'article
    # ---------------------------------------------------------------

    chemin_orders = chemin_olist("orders.csv")
    chemin_items = chemin_olist("order_items.csv")

    df_orders = lire_csv(chemin_orders)
    df_items = lire_csv(chemin_items)

    rule_commandes_articles = get_rules("olist")[3]

    df_orders_valides, df_commandes_sans_articles = (
        controler_commandes_sans_articles(
            df_orders,
            df_items,
            rule_commandes_articles,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 5 : commandes avec plusieurs paiements
    # ---------------------------------------------------------------

    chemin_payments = (
        chemin_olist("order_payments.csv")
    )

    df_payments = lire_csv(chemin_payments)

    rule_paiements = get_rules("olist")[4]

    df_paiements_agreges, df_commandes_paiements_multiples = (
        controler_paiements_multiples(
            df_payments,
            rule_paiements,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 6 : produits sans catégorie
    # ---------------------------------------------------------------

    chemin_products = (
        chemin_olist("products.csv")
    )

    df_products = lire_csv(chemin_products)

    rule_produits_categorie = get_rules("olist")[5]

    df_products_valides, df_products_sans_categorie = (
        controler_produits_sans_categorie(
            df_products,
            rule_produits_categorie,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 7 : date de livraison des commandes livrées
    # ---------------------------------------------------------------

    rule_date_livraison = get_rules("olist")[6]

    df_orders_valides_livraison, df_orders_livraison_quarantaine = (
        controler_date_livraison(
            df_orders_valides,
            rule_date_livraison,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 8 : avis sans commentaire textuel
    # ---------------------------------------------------------------

    rule_commentaires = get_rules("olist")[7]

    df_reviews_valides_commentaires, df_reviews_sans_commentaire = (
        controler_commentaires_absents(
            df_reviews_final,
            rule_commentaires,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 9 : identifiant client
    # ---------------------------------------------------------------

    chemin_customers = (
        chemin_olist("customers.csv")
    )

    df_customers = lire_csv(chemin_customers)

    rule_client = get_rules("olist")[8]

    df_customers_valides, df_customers_quarantaine = (
        controler_identifiant_client(
            df_customers,
            rule_client,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 10 : HTML dans le catalogue Rakuten
    # ---------------------------------------------------------------

    chemin_rakuten = (
        RAW_DIR / "rakuten" / "rakuten_catalogue_produits.csv"
    )

    df_rakuten = lire_csv(chemin_rakuten)

    rule_html = get_rules("rakuten")[0]

    df_rakuten_nettoye, df_rakuten_html = controler_html_rakuten(
        df_rakuten,
        rule_html,
    )

    # ---------------------------------------------------------------
    # Contrôle 11 : descriptions absentes dans le catalogue Rakuten
    # ---------------------------------------------------------------

    rule_description = get_rules("rakuten")[1]

    df_rakuten_valides, df_rakuten_sans_description = (
        controler_descriptions_absentes(
            df_rakuten_nettoye,
            rule_description,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 12 : désignations identiques entre produits Rakuten
    # ---------------------------------------------------------------

    rule_designation = get_rules("rakuten")[2]

    df_rakuten_final, df_rakuten_designations_dupliquees = (
        controler_designations_dupliquees(
            df_rakuten_valides,
            rule_designation,
        )
    )

    # ---------------------------------------------------------------
    # Contrôle 13 : détection de langue du catalogue Rakuten
    # ---------------------------------------------------------------

    rule_langue = get_rules("rakuten")[3]

    df_rakuten_complet, df_rakuten_textes_vides = (
        controler_langue_rakuten(
            df_rakuten_final,
            rule_langue,
        )
    )

    # ---------------------------------------------------------------
    # Résultats
    # ---------------------------------------------------------------

    # QUARANTAINE OLIST_COMMANDES_02
    if "df_orders_quarantaine" in locals() and not df_orders_quarantaine.empty:
        ecrire_quarantaine(
            df_orders_quarantaine,
            "olist",
            "orders",
            "OLIST_COMMANDES_02",
        )
        print(
            "QUARANTAINE OLIST_COMMANDES_02 :",
            len(df_orders_quarantaine),
            "lignes"
        )

    resultats = {
        "source": "olist",
        "controles": [
            {
                "regle": rule_geo["identifiant"],
                "lignes_initiales": len(df_geo),
                "lignes_valides": len(df_geo_valide),
                "lignes_supprimees": nb_geo_supprimes,
                "lignes_quarantaine": 0,
            },
            {
                "regle": rule_review["identifiant"],
                "lignes_initiales": len(df_reviews),
                "lignes_valides": len(df_reviews_valide),
                "lignes_supprimees": 0,
                "lignes_quarantaine": len(df_reviews_quarantaine),
            },
            {
                "regle": rule_order_review["identifiant"],
                "lignes_initiales": len(df_reviews_valide),
                "lignes_valides": len(df_reviews_final),
                "lignes_supprimees": 0,
                "lignes_quarantaine": len(df_reviews_quarantaine),
            },
            {
                "regle": rule_commandes_articles["identifiant"],
                "lignes_initiales": len(df_orders),
                "lignes_valides": len(df_orders_valides),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_commandes_sans_articles),
            },
            {
                "regle": rule_paiements["identifiant"],
                "lignes_initiales": len(df_payments),
                "lignes_valides": len(df_paiements_agreges),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_commandes_paiements_multiples),
            },
            {
                "regle": rule_produits_categorie["identifiant"],
                "lignes_initiales": len(df_products),
                "lignes_valides": len(df_products_valides),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_products_sans_categorie),
            },
            {
                "regle": rule_date_livraison["identifiant"],
                "lignes_initiales": len(df_orders_valides),
                "lignes_valides": len(df_orders_valides_livraison),
                "lignes_supprimees": 0,
                "lignes_quarantaine": len(df_orders_livraison_quarantaine),
            },
            {
                "regle": rule_commentaires["identifiant"],
                "lignes_initiales": len(df_reviews_final),
                "lignes_valides": len(df_reviews_valides_commentaires),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_reviews_sans_commentaire),
            },
            {
                "regle": rule_client["identifiant"],
                "lignes_initiales": len(df_customers),
                "lignes_valides": len(df_customers_valides),
                "lignes_supprimees": 0,
                "lignes_quarantaine": len(df_customers_quarantaine),
            },
            {
                "regle": rule_html["identifiant"],
                "lignes_initiales": len(df_rakuten),
                "lignes_valides": len(df_rakuten_nettoye),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_rakuten_html),
            },
            {
                "regle": rule_description["identifiant"],
                "lignes_initiales": len(df_rakuten_nettoye),
                "lignes_valides": len(df_rakuten_valides),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_rakuten_sans_description),
            },
            {
                "regle": rule_designation["identifiant"],
                "lignes_initiales": len(df_rakuten_valides),
                "lignes_valides": len(df_rakuten_final),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_rakuten_designations_dupliquees),
            },
            {
                "regle": rule_langue["identifiant"],
                "lignes_initiales": len(df_rakuten_final),
                "lignes_valides": len(df_rakuten_complet),
                "lignes_supprimees": 0,
                "lignes_quarantaine": 0,
                "anomalies": len(df_rakuten_textes_vides),
            },
        ],
    }

    ecrire_execution_log(resultats["controles"], "olist")

    return resultats


# ---------------------------------------------------------------------------
# Affichage du catalogue
# ---------------------------------------------------------------------------

def afficher_regles(source):
    """Affiche les règles disponibles pour une source."""

    rules = get_rules(source)

    print(f"\nSource : {source}")
    print(f"Nombre de règles : {len(rules)}")
    print("-" * 70)

    for rule in rules:
        print(
            f"{rule['identifiant']} | "
            f"{rule['gravite']} | "
            f"{rule['colonne']}"
        )


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    """Point d'entrée du moteur de contrôle."""

    parser = argparse.ArgumentParser(
        description="Moteur de contrôle qualité DataFlow360"
    )

    parser.add_argument(
        "--source",
        required=True,
        choices=["olist", "rakuten"],
        help="Source des données à contrôler",
    )

    parser.add_argument(
        "--catalogue",
        action="store_true",
        help="Afficher uniquement le catalogue des règles",
    )

    parser.add_argument(
        "--ingestion",
        help=(
            "Identifiant explicite de l'ingestion à contrôler "
            "(format AAAAMMJJTHHMMSS)"
        ),
    )

    args = parser.parse_args()

    if args.catalogue:
        afficher_regles(args.source)
        return

    if args.source == "olist":
        global INGESTION_DIR

        INGESTION_DIR = resoudre_ingestion(
            args.source,
            args.ingestion,
        )

        print(
            f"\nIngestion sélectionnée : {INGESTION_DIR}"
        )

        resultat = controler_olist_geolocation()

        print("\n" + "=" * 70)
        print("RÉSULTAT DU CONTRÔLE")
        print("=" * 70)
        print(resultat)

    elif args.source == "rakuten":
        print("\nContrôle Rakuten disponible via le moteur de règles.")
        print("Les règles Rakuten sont intégrées au catalogue central.")


if __name__ == "__main__":
    main()
