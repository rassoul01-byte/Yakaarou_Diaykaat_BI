"""Chargement du résultat du contrôle qualité dans PostgreSQL.

C'est le pont entre quality.controle, qui sépare lignes valides et rejets,
et les traitements qui lisent la base : la transformation lit staging.*,
le rapport de taux de rejet lit staging.execution_log et quarantaine.rejets.

Une exécution, une transaction :

    BEGIN
      TRUNCATE des tables staging de la source   (zone écrasée à chaque passage)
      COPY des lignes valides                    (staging.<table>)
      INSERT des rejets                          (quarantaine.rejets, via quality.quarantaine)
      INSERT d'une ligne de journal              (staging.execution_log, pipeline « qualite »)
    COMMIT — ou ROLLBACK au moindre échec : jamais d'état à moitié chargé.

Relancer le contrôle d'une même ingestion :
- staging est vidée puis rechargée : aucun doublon ;
- la quarantaine est append-only (docs/contrats/zones_stockage.md) : les
  rejets d'une règle déjà enregistrés pour cette source et cette ingestion
  ne sont pas réinsérés, et rien n'est supprimé ;
- le journal reçoit une ligne par exécution, comme pour l'acquisition et la
  transformation : c'est un historique des passages, pas un état.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import psycopg2

from common.config import load_settings
from quality.quarantaine import enregistrer_rejets

# Colonnes écrites par le contrôle, dans l'ordre des migrations 002 et 003.
# Les colonnes ajoutées par la transformation (006 : product_category_name_norm,
# langue) n'y figurent pas : le rechargement les remet à NULL, la
# transformation les recalcule.
COLONNES_STAGING = {
    "olist_orders": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "olist_order_items": [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ],
    "olist_products": [
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
    "olist_customers": [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ],
    "olist_geolocation": [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ],
    "olist_order_payments": [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ],
    "olist_order_reviews": [
        "review_id",
        "order_id",
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
    ],
    "olist_sellers": [
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ],
    "product_category_translation": [
        "product_category_name",
        "product_category_name_english",
    ],
    "rakuten_produits": [
        "index_ligne",
        "jeu",
        "designation",
        "description",
        "productid",
        "imageid",
        "prdtypecode",
    ],
}

# Tables de staging alimentées par le contrôle de chaque source.
TABLES_PAR_SOURCE = {
    "olist": [
        "olist_customers",
        "olist_orders",
        "olist_order_items",
        "olist_order_payments",
        "olist_products",
        "olist_sellers",
        "olist_geolocation",
        "product_category_translation",
        "olist_order_reviews",
    ],
    "rakuten": ["rakuten_produits"],
}


@dataclass(frozen=True)
class BilanChargement:
    source: str
    ingestion: str
    lignes_lues: int
    lignes_staging: int
    lignes_rejetees: int
    rejets_inseres: int
    rejets_deja_presents: int
    execution_id: int

    def __str__(self) -> str:
        return (
            f"Chargement {self.source} (ingestion {self.ingestion}) validé : "
            f"{self.lignes_staging} ligne(s) en staging, "
            f"{self.lignes_rejetees} rejet(s) détecté(s) dont {self.rejets_inseres} "
            f"inséré(s) en quarantaine et {self.rejets_deja_presents} déjà présent(s), "
            f"journal n° {self.execution_id}."
        )


# --------------------------------------------------------------------------- #
# Préparation — sans base de données
# --------------------------------------------------------------------------- #


def _sans_manquants(df: pd.DataFrame) -> pd.DataFrame:
    """Remplace NaN par None : JSON et psycopg2 attendent un vrai NULL."""
    return df.astype(object).where(df.notna(), None)


def preparer_rejets(resultat) -> list[dict]:
    """Traduit les lots rejetés au format du contrat de quarantaine.

    `ligne_origine` est la position de l'enregistrement dans son fichier de
    la zone brute, à partir de 1, en-tête exclu : c'est l'index que
    quality.controle.lire_csv conserve à travers les filtres.
    """
    rejets = []
    for lot in resultat.rejets:
        lignes = _sans_manquants(lot.lignes)
        for position, enregistrement in zip(lignes.index, lignes.to_dict("records"), strict=True):
            rejets.append(
                {
                    "source": resultat.source,
                    "ingestion": resultat.ingestion,
                    "fichier": lot.fichier,
                    "ligne_origine": int(position) + 1,
                    "regle": lot.regle["identifiant"],
                    "gravite": lot.regle["gravite"],
                    "donnees_brutes": enregistrement,
                }
            )
    return rejets


def message_journal(resultat, rejets_inseres: int, rejets_deja_presents: int) -> str:
    """Détail d'une exécution pour la colonne message du journal (JSON).

    Les colonnes du journal portent les totaux ; le détail par règle — dont
    les lignes supprimées silencieusement, absentes de la quarantaine — est
    ici, conformément au dictionnaire des indicateurs.
    """
    return json.dumps(
        {
            "ingestion": resultat.ingestion,
            "lignes_supprimees": resultat.lignes_supprimees,
            "rejets_inseres": rejets_inseres,
            "rejets_deja_presents": rejets_deja_presents,
            "controles": resultat.controles,
        },
        ensure_ascii=False,
    )


def verifier_tables(resultat) -> None:
    """Refuse un résultat qui ne couvre pas exactement les tables de sa source."""
    attendues = set(TABLES_PAR_SOURCE[resultat.source])
    recues = set(resultat.valides)
    if attendues != recues:
        raise ValueError(
            f"tables de staging inattendues pour {resultat.source} : "
            f"manquantes {sorted(attendues - recues)}, en trop {sorted(recues - attendues)}"
        )
    for table, df in resultat.valides.items():
        absentes = [c for c in COLONNES_STAGING[table] if c not in df.columns]
        if absentes:
            raise ValueError(f"staging.{table} : colonnes absentes {absentes}")


# --------------------------------------------------------------------------- #
# Écriture
# --------------------------------------------------------------------------- #


def _copier(curseur, table: str, df: pd.DataFrame) -> None:
    """Charge un DataFrame dans staging.<table> par COPY.

    Une cellule vide devient NULL ; le typage (TIMESTAMP, NUMERIC, INTEGER)
    est fait par PostgreSQL selon la migration, qui refuse toute valeur
    non conforme — et fait échouer, donc annuler, tout le chargement.
    """
    colonnes = COLONNES_STAGING[table]
    tampon = io.StringIO()
    df[colonnes].to_csv(tampon, index=False, header=False)
    tampon.seek(0)
    curseur.copy_expert(
        f"COPY staging.{table} ({', '.join(colonnes)}) FROM STDIN WITH (FORMAT csv)",
        tampon,
    )


def _regles_deja_en_quarantaine(curseur, source: str, ingestion: str) -> set[str]:
    curseur.execute(
        """
        SELECT DISTINCT regle_violee
        FROM quarantaine.rejets
        WHERE source = %s AND ingestion = %s
        """,
        (source, ingestion),
    )
    return {regle for (regle,) in curseur.fetchall()}


def _journaliser(curseur, resultat, demarre_a: datetime, message: str) -> int:
    curseur.execute(
        """
        INSERT INTO staging.execution_log
            (pipeline, etape, source, demarre_a, termine_a,
             lignes_lues, lignes_ecrites, lignes_rejetees, statut, message)
        VALUES ('qualite', 'controle', %s, %s, now(), %s, %s, %s, 'succes', %s)
        RETURNING id
        """,
        (
            resultat.source,
            demarre_a,
            resultat.lignes_lues,
            resultat.lignes_ecrites,
            resultat.lignes_rejetees,
            message,
        ),
    )
    return curseur.fetchone()[0]


def charger(resultat, connexion=None, valider: bool = True) -> BilanChargement:
    """Charge un ResultatControle : staging, quarantaine et journal, d'un seul tenant.

    Avec `valider=False`, la transaction reste ouverte et c'est l'appelant
    qui valide ou annule (tests d'intégration).
    """
    verifier_tables(resultat)
    rejets = preparer_rejets(resultat)

    connexion_locale = connexion is None
    connexion = connexion or psycopg2.connect(load_settings().postgres_dsn)

    try:
        with connexion.cursor() as curseur:
            tables = ", ".join(f"staging.{t}" for t in TABLES_PAR_SOURCE[resultat.source])
            curseur.execute(f"TRUNCATE {tables}")
            for table in TABLES_PAR_SOURCE[resultat.source]:
                _copier(curseur, table, resultat.valides[table])

            deja = _regles_deja_en_quarantaine(curseur, resultat.source, resultat.ingestion)

        nouveaux = [r for r in rejets if r["regle"] not in deja]
        inseres = enregistrer_rejets(nouveaux, connexion=connexion, valider=False)
        deja_presents = len(rejets) - len(nouveaux)

        with connexion.cursor() as curseur:
            execution_id = _journaliser(
                curseur,
                resultat,
                resultat.demarre_a,
                message_journal(resultat, inseres, deja_presents),
            )

        if valider:
            connexion.commit()

    except Exception:
        if valider:
            connexion.rollback()
        raise

    finally:
        if connexion_locale:
            connexion.close()

    return BilanChargement(
        source=resultat.source,
        ingestion=resultat.ingestion,
        lignes_lues=resultat.lignes_lues,
        lignes_staging=resultat.lignes_ecrites,
        lignes_rejetees=resultat.lignes_rejetees,
        rejets_inseres=inseres,
        rejets_deja_presents=deja_presents,
        execution_id=execution_id,
    )
