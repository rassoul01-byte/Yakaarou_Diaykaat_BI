"""
Moteur de contrôle qualité des données DataFlow360.

F1.5 - Contrôler la conformité des données avant intégration.

Ce module :
- lit une ingestion explicite de la zone brute (data/raw/lots/...) ;
- applique les règles du catalogue (rules.py) en respectant leur gravité ;
- sépare les lignes valides des lignes rejetées ;
- confie le résultat à quality.chargement, qui écrit en une transaction
  staging.<tables>, quarantaine.rejets et staging.execution_log.

Usage :
    python -m quality.controle --source olist --ingestion 20260930T120000
    python -m quality.controle --source rakuten --ingestion 20260930T120500
    python -m quality.controle --source olist --catalogue

Seules les règles « bloquante » envoient des lignes en quarantaine. Les
règles « non bloquante » et « silencieuse » conservent les lignes et
comptent les anomalies dans le journal.
"""

from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from common.config import load_settings
from quality.rules import get_rule, get_rules
from quality.schemas import schema_avis

# ---------------------------------------------------------------------------
# Emplacement des ingestions dans la zone brute
# ---------------------------------------------------------------------------

# Le catalogue F1.5 utilise « olist » comme source métier. L'acquisition SQL
# du Sprint 1 dépose physiquement ses fichiers sous le nom de la base source.
SOURCE_PHYSIQUE = {"olist": "boutique", "rakuten": "rakuten"}

FICHIER_RAKUTEN = "rakuten_catalogue_produits.csv"


def resoudre_ingestion(source, ingestion, racine_brute=None):
    """Résout explicitement le dossier d'une ingestion.

    Pour Olist, les données proviennent de la source SQL « boutique ».
    Le paramètre --ingestion évite de sélectionner implicitement
    la dernière ingestion.
    """
    if not ingestion:
        raise ValueError("--ingestion est obligatoire pour contrôler une source par lot.")

    racine_brute = Path(racine_brute) if racine_brute else load_settings().raw_dir
    source_physique = SOURCE_PHYSIQUE.get(source, source)
    dossier = racine_brute / "lots" / source_physique / f"ingestion={ingestion}"

    if not dossier.is_dir():
        raise FileNotFoundError(f"Ingestion introuvable : {dossier}")

    manifeste = dossier / "manifeste.json"

    if not manifeste.is_file():
        raise FileNotFoundError(f"Manifeste absent : {manifeste}")

    return dossier


# ---------------------------------------------------------------------------
# Résultat d'un contrôle
# ---------------------------------------------------------------------------


@dataclass
class LotRejete:
    """Lignes d'un fichier rejetées par une règle bloquante."""

    table: str
    fichier: str
    regle: dict
    lignes: pd.DataFrame


@dataclass
class ResultatControle:
    """Tout ce que le contrôle d'une ingestion a produit.

    - valides : lignes conservées, par table de staging (sans le préfixe
      de schéma), prêtes à être chargées ;
    - rejets : lots de lignes rejetées, destinés à quarantaine.rejets ;
    - controles : une entrée par règle, pour staging.execution_log.
    """

    source: str
    ingestion: str
    demarre_a: datetime
    lignes_lues: int = 0
    valides: dict[str, pd.DataFrame] = field(default_factory=dict)
    rejets: list[LotRejete] = field(default_factory=list)
    controles: list[dict] = field(default_factory=list)

    @property
    def lignes_ecrites(self) -> int:
        return sum(len(df) for df in self.valides.values())

    @property
    def lignes_rejetees(self) -> int:
        return sum(len(lot.lignes) for lot in self.rejets)

    @property
    def lignes_supprimees(self) -> int:
        return sum(c["lignes_supprimees"] for c in self.controles)

    def journaliser(self, rule, table, initiales, valides, supprimees=0, rejetees=0, **extra):
        """Ajoute l'entrée d'une règle au journal du contrôle."""
        self.controles.append(
            {
                "regle": rule["identifiant"],
                "gravite": rule["gravite"],
                "table": table,
                "lignes_initiales": int(initiales),
                "lignes_valides": int(valides),
                "lignes_supprimees": int(supprimees),
                "lignes_quarantaine": int(rejetees),
                **{cle: int(valeur) for cle, valeur in extra.items()},
            }
        )

    def rejeter(self, rule, table, fichier, lignes):
        """Retient les lignes rejetées par une règle bloquante."""
        if not lignes.empty:
            self.rejets.append(LotRejete(table, fichier, rule, lignes))


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
    """Charge un fichier CSV et retourne un DataFrame.

    Toutes les colonnes sont lues en texte : un code postal comme « 01037 »
    garde son zéro initial (contrat de la zone intermédiaire), et seule une
    cellule vide devient une valeur manquante — « NA » ou « null » dans une
    désignation restent du texte. L'index conserve la position de chaque
    enregistrement dans le fichier : il sert de ligne d'origine en quarantaine.
    """
    print(f"\nLecture : {chemin}")

    df = pd.read_csv(chemin, dtype=str, keep_default_na=False, na_values=[""])

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
# Règles Olist et Rakuten
# ---------------------------------------------------------------------------


def controler_review_id(df, rule):
    """
    Contrôle OLIST_AVIS_01.

    Gravité : bloquante
    - première occurrence conservée ;
    - doublons rejetés ;
    - validation finale avec Pandera ;
    - les rejets sont renvoyés à l'appelant, qui les met en quarantaine.
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

    # Renvoyer un DataFrame vide ferait disparaître tous les avis de staging
    # sans le dire : on arrête le contrôle, rien n'est chargé.
    if df_valides_pandera is None:
        raise ValueError(
            f"{rule['identifiant']} : les avis conservés ne passent pas la validation Pandera."
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

    masque_sans_articles = ~df_orders["order_id"].isin(commandes_avec_articles)

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
        - le montant total par commande est calculé (somme de payment_value).

    Les lignes de paiement ne sont pas modifiées : staging.olist_order_payments
    garde le grain d'un paiement (clé order_id + payment_sequential). L'agrégat
    renvoyé est celui qu'il faudra joindre aux commandes, jamais le détail.
    """

    paiements_par_commande = (
        df_payments.assign(
            payment_value=pd.to_numeric(df_payments["payment_value"], errors="coerce")
        )
        .groupby("order_id")
        .agg(
            nombre_paiements=("payment_value", "size"),
            montant_total=("payment_value", "sum"),
        )
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

    masque_sans_categorie = df_products["product_category_name"].isna() | (
        df_products["product_category_name"].astype(str).str.strip().eq("")
    )

    df_sans_categorie = df_products.loc[masque_sans_categorie].copy()

    df_produits_valides = df_products.copy()

    df_produits_valides.loc[masque_sans_categorie, "product_category_name"] = "inconnu"

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

    df_quarantaine = df_orders.loc[masque_livree_sans_date].copy()

    df_valides = df_orders.loc[~masque_livree_sans_date].copy()

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

    masque_sans_commentaire = df_reviews["review_comment_message"].isna() | (
        df_reviews["review_comment_message"].astype(str).str.strip().eq("")
    )

    df_sans_commentaire = df_reviews.loc[masque_sans_commentaire].copy()

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

    masque_identifiant_absent = df_customers["customer_unique_id"].isna() | (
        df_customers["customer_unique_id"].astype(str).str.strip().eq("")
    )

    df_quarantaine = df_customers.loc[masque_identifiant_absent].copy()

    df_valides = df_customers.loc[~masque_identifiant_absent].copy()

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

    # Entité nommée (&eacute;) ou numérique (&#39;). Dans une chaîne brute,
    # « \\d » chercherait une barre oblique littérale et manquerait toutes
    # les entités numériques, les plus fréquentes du catalogue.
    motif_entite = r"&(?:[a-zA-Z]+|#\d+);"
    masque_entites = designation.str.contains(motif_entite, regex=True) | description.str.contains(
        motif_entite, regex=True
    )

    masque_balises = designation.str.contains(r"<[^>]+>", regex=True) | description.str.contains(
        r"<[^>]+>", regex=True
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

    masque_sans_description = df_products["description"].isna() | (
        df_products["description"].astype(str).str.strip().eq("")
    )

    df_sans_description = df_products.loc[masque_sans_description].copy()

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

    designation = df_products["designation"].fillna("").astype(str).str.strip()

    masque_doublon = designation.duplicated(keep=False) & designation.ne("")

    df_designations_dupliquees = df_products.loc[masque_doublon].copy()

    df_valides = df_products.copy()

    nombre_designations_dupliquees = designation[masque_doublon].nunique()

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
    print(
        "Doublons de désignation :",
        int(df_products["designation"].duplicated().sum()),
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

    La détection effective est faite par la transformation
    (transformation.langue, langdetect), qui écrit la colonne
    staging.rakuten_produits.langue : elle travaille sur le texte décodé.
    """

    df_valides = df_products.copy()

    textes_non_vides = df_valides["designation"].fillna("").astype(str).str.strip().ne("")

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
        "Détection de langue : python -m transformation --source rakuten "
        "(colonne staging.rakuten_produits.langue)"
    )

    return df_valides, df_products.loc[~textes_non_vides].copy()


def controler_olist(dossier, ingestion=None):
    """Applique les règles Olist à une ingestion de la zone brute.

    Rien n'est écrit ici : le résultat est chargé par quality.chargement.
    """
    dossier = Path(dossier)
    resultat = ResultatControle(
        source="olist",
        ingestion=ingestion or dossier.name.split("=", 1)[-1],
        demarre_a=datetime.now(UTC),
    )

    def lire(table):
        chemin = dossier / f"{table}.csv"
        if not chemin.exists():
            raise FileNotFoundError(f"Fichier absent de l'ingestion : {chemin}")
        df = lire_csv(chemin)
        resultat.lignes_lues += len(df)
        return df

    # OLIST_GEOLOCALISATION_01 — doublons stricts retirés silencieusement
    rule = get_rule("OLIST_GEOLOCALISATION_01")
    df_geo = lire("geolocation")
    df_geo_valide, nb_geo_supprimes = controler_doublons_stricts(df_geo, rule)
    resultat.journaliser(
        rule, "geolocation", len(df_geo), len(df_geo_valide), supprimees=nb_geo_supprimes
    )

    # OLIST_AVIS_01 puis OLIST_AVIS_02 — chaque règle garde ses propres rejets
    df_reviews = lire("order_reviews")

    rule_review_id = get_rule("OLIST_AVIS_01")
    df_reviews_id_valides, df_reviews_id_quarantaine = controler_review_id(
        df_reviews, rule_review_id
    )
    resultat.journaliser(
        rule_review_id,
        "order_reviews",
        len(df_reviews),
        len(df_reviews_id_valides),
        rejetees=len(df_reviews_id_quarantaine),
    )
    resultat.rejeter(
        rule_review_id, "order_reviews", "order_reviews.csv", df_reviews_id_quarantaine
    )

    rule_avis_commande = get_rule("OLIST_AVIS_02")
    df_reviews_final, df_reviews_commande_quarantaine = controler_avis_par_commande(
        df_reviews_id_valides, rule_avis_commande
    )
    resultat.journaliser(
        rule_avis_commande,
        "order_reviews",
        len(df_reviews_id_valides),
        len(df_reviews_final),
        rejetees=len(df_reviews_commande_quarantaine),
    )
    resultat.rejeter(
        rule_avis_commande, "order_reviews", "order_reviews.csv", df_reviews_commande_quarantaine
    )

    # OLIST_AVIS_03 — avis sans commentaire : conservés, comptés
    rule = get_rule("OLIST_AVIS_03")
    df_reviews_final, df_reviews_sans_commentaire = controler_commentaires_absents(
        df_reviews_final, rule
    )
    resultat.journaliser(
        rule,
        "order_reviews",
        len(df_reviews_final),
        len(df_reviews_final),
        anomalies=len(df_reviews_sans_commentaire),
    )

    # OLIST_COMMANDES_01 — commandes sans article : conservées, comptées
    df_orders = lire("orders")
    df_items = lire("order_items")
    rule = get_rule("OLIST_COMMANDES_01")
    df_orders_valides, df_commandes_sans_articles = controler_commandes_sans_articles(
        df_orders, df_items, rule
    )
    resultat.journaliser(
        rule,
        "orders",
        len(df_orders),
        len(df_orders_valides),
        anomalies=len(df_commandes_sans_articles),
    )

    # OLIST_COMMANDES_02 — commande livrée sans date de livraison : rejetée
    rule = get_rule("OLIST_COMMANDES_02")
    df_orders_valides_livraison, df_orders_livraison_quarantaine = controler_date_livraison(
        df_orders_valides, rule
    )
    resultat.journaliser(
        rule,
        "orders",
        len(df_orders_valides),
        len(df_orders_valides_livraison),
        rejetees=len(df_orders_livraison_quarantaine),
    )
    resultat.rejeter(rule, "orders", "orders.csv", df_orders_livraison_quarantaine)

    # OLIST_PAIEMENTS_01 — paiements multiples : détail conservé, agrégat calculé
    df_payments = lire("order_payments")
    rule = get_rule("OLIST_PAIEMENTS_01")
    _, df_commandes_paiements_multiples = controler_paiements_multiples(df_payments, rule)
    resultat.journaliser(
        rule,
        "order_payments",
        len(df_payments),
        len(df_payments),
        anomalies=len(df_commandes_paiements_multiples),
    )

    # OLIST_ARTICLES_01 — produit sans catégorie : rattaché à « inconnu »
    df_products = lire("products")
    rule = get_rule("OLIST_ARTICLES_01")
    df_products_valides, df_products_sans_categorie = controler_produits_sans_categorie(
        df_products, rule
    )
    resultat.journaliser(
        rule,
        "products",
        len(df_products),
        len(df_products_valides),
        anomalies=len(df_products_sans_categorie),
    )

    # OLIST_CLIENTS_01 — customer_unique_id absent : rejeté
    df_customers = lire("customers")
    rule = get_rule("OLIST_CLIENTS_01")
    df_customers_valides, df_customers_quarantaine = controler_identifiant_client(
        df_customers, rule
    )
    resultat.journaliser(
        rule,
        "customers",
        len(df_customers),
        len(df_customers_valides),
        rejetees=len(df_customers_quarantaine),
    )
    resultat.rejeter(rule, "customers", "customers.csv", df_customers_quarantaine)

    # Tables sans règle au catalogue : chargées telles quelles
    df_sellers = lire("sellers")
    df_categories = lire("category_translation")

    resultat.valides = {
        "olist_customers": df_customers_valides,
        "olist_orders": df_orders_valides_livraison,
        "olist_order_items": df_items,
        "olist_order_payments": df_payments,
        "olist_products": df_products_valides,
        "olist_sellers": df_sellers,
        "olist_geolocation": df_geo_valide,
        "product_category_translation": df_categories,
        "olist_order_reviews": df_reviews_final,
    }
    return resultat


def controler_rakuten(dossier, ingestion=None):
    """Applique les règles Rakuten à une ingestion de la zone brute.

    Les quatre règles Rakuten sont non bloquantes ou silencieuses : aucune
    fiche n'est rejetée, les anomalies sont comptées. Le texte chargé en
    staging est celui de la zone brute : le décodage du HTML et la détection
    de langue appartiennent à la transformation (F1.7), qui les applique en
    place dans staging.rakuten_produits.
    """
    dossier = Path(dossier)
    resultat = ResultatControle(
        source="rakuten",
        ingestion=ingestion or dossier.name.split("=", 1)[-1],
        demarre_a=datetime.now(UTC),
    )

    chemin = dossier / FICHIER_RAKUTEN
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier absent de l'ingestion : {chemin}")
    df_rakuten = lire_csv(chemin)
    resultat.lignes_lues = len(df_rakuten)

    # RAKUTEN_PRODUITS_01 — HTML détecté ; le texte nettoyé sert aux règles suivantes
    rule = get_rule("RAKUTEN_PRODUITS_01")
    df_rakuten_nettoye, df_rakuten_html = controler_html_rakuten(df_rakuten, rule)
    resultat.journaliser(
        rule,
        "rakuten_produits",
        len(df_rakuten),
        len(df_rakuten_nettoye),
        anomalies=len(df_rakuten_html),
    )

    # RAKUTEN_PRODUITS_02 — description absente (y compris après nettoyage)
    rule = get_rule("RAKUTEN_PRODUITS_02")
    df_rakuten_valides, df_rakuten_sans_description = controler_descriptions_absentes(
        df_rakuten_nettoye, rule
    )
    resultat.journaliser(
        rule,
        "rakuten_produits",
        len(df_rakuten_nettoye),
        len(df_rakuten_valides),
        anomalies=len(df_rakuten_sans_description),
    )

    # RAKUTEN_PRODUITS_03 — désignations répétées : signalées, jamais dédupliquées
    rule = get_rule("RAKUTEN_PRODUITS_03")
    _, df_rakuten_designations_dupliquees = controler_designations_dupliquees(df_rakuten, rule)
    resultat.journaliser(
        rule,
        "rakuten_produits",
        len(df_rakuten),
        len(df_rakuten),
        anomalies=len(df_rakuten_designations_dupliquees),
    )

    # RAKUTEN_PRODUITS_04 — texte analysable pour la détection de langue
    rule = get_rule("RAKUTEN_PRODUITS_04")
    _, df_rakuten_textes_vides = controler_langue_rakuten(df_rakuten_nettoye, rule)
    resultat.journaliser(
        rule,
        "rakuten_produits",
        len(df_rakuten_nettoye),
        len(df_rakuten_nettoye),
        anomalies=len(df_rakuten_textes_vides),
    )

    resultat.valides = {"rakuten_produits": preparer_rakuten_staging(df_rakuten)}
    return resultat


def preparer_rakuten_staging(df_rakuten):
    """Met le catalogue au format de staging.rakuten_produits (migration 003).

    Le fichier livré réunit fiches et catégories (README, « Sources des
    données ») : une fiche avec prdtypecode appartient au jeu d'entraînement,
    une fiche sans prdtypecode au jeu de test.
    """
    df = df_rakuten.rename(columns={"source_index": "index_ligne"}).copy()
    df["jeu"] = df["prdtypecode"].notna().map({True: "train", False: "test"})
    return df


CONTROLEURS = {"olist": controler_olist, "rakuten": controler_rakuten}


def controler(source, ingestion, racine_brute=None):
    """Contrôle une ingestion explicite d'une source, sans rien écrire."""
    dossier = resoudre_ingestion(source, ingestion, racine_brute)
    print(f"\nIngestion sélectionnée : {dossier}")
    return CONTROLEURS[source](dossier, ingestion)


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
        print(f"{rule['identifiant']} | {rule['gravite']} | {rule['colonne']}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def afficher_resultat(resultat):
    """Affiche le bilan par règle d'un contrôle."""
    print("\n" + "=" * 70)
    print(f"RÉSULTAT DU CONTRÔLE — {resultat.source} — ingestion {resultat.ingestion}")
    print("=" * 70)
    for c in resultat.controles:
        print(
            f"{c['regle']:<26} initiales={c['lignes_initiales']:<9} "
            f"valides={c['lignes_valides']:<9} quarantaine={c['lignes_quarantaine']:<6} "
            f"supprimées={c['lignes_supprimees']:<7} anomalies={c.get('anomalies', 0)}"
        )
    print(
        f"\nLignes lues : {resultat.lignes_lues} · valides : {resultat.lignes_ecrites} · "
        f"rejetées : {resultat.lignes_rejetees} · supprimées : {resultat.lignes_supprimees}"
    )


def main(argv=None):
    """Point d'entrée du moteur de contrôle. Renvoie le code de sortie."""

    parser = argparse.ArgumentParser(description="Moteur de contrôle qualité DataFlow360")

    parser.add_argument(
        "--source",
        required=True,
        choices=sorted(CONTROLEURS),
        help="Source des données à contrôler",
    )

    parser.add_argument(
        "--catalogue",
        action="store_true",
        help="Afficher uniquement le catalogue des règles",
    )

    parser.add_argument(
        "--ingestion",
        help="Identifiant explicite de l'ingestion à contrôler (format AAAAMMJJTHHMMSS)",
    )

    parser.add_argument(
        "--sans-chargement",
        action="store_true",
        help="Contrôler sans rien écrire dans PostgreSQL (essai à blanc)",
    )

    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Exporter aussi une copie d'audit en CSV (data/audit_qualite/)",
    )

    args = parser.parse_args(argv)

    if args.catalogue:
        afficher_regles(args.source)
        return 0

    try:
        resultat = controler(args.source, args.ingestion)
    except (ValueError, FileNotFoundError) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    afficher_resultat(resultat)

    if args.export_csv:
        from quality.sorties import exporter_audit

        exporter_audit(resultat)

    if args.sans_chargement:
        print("\nEssai à blanc : rien n'a été écrit dans PostgreSQL.")
        return 0

    import psycopg2

    from quality.chargement import charger

    try:
        bilan = charger(resultat)
    except psycopg2.Error as erreur:
        premiere_ligne = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : chargement annulé, rien n'a été écrit ({premiere_ligne})", file=sys.stderr)
        return 1

    print(f"\n{bilan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
