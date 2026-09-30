"""Application des transformations à la zone intermédiaire (staging).

Ce module ne calcule rien lui-même que balisage.py, normalisation.py, langue.py
et deduplication.py ne fournissent déjà : il lit les tables de `staging`
(écrites par le contrôle qualité, F1.5), applique ces fonctions pures, et
réécrit le résultat en place, toujours dans `staging`.

Deux principes du Livrable 4 : la transformation lit ce que le contrôle a
laissé passer — jamais la zone brute directement — et toute suppression est
comptée, le compte rejoint staging.execution_log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from common.config import load_settings

from .balisage import decoder_balisage
from .langue import detecter_langue
from .normalisation import normaliser_libelle


@dataclass(frozen=True)
class ResultatTransformation:
    etape: str
    lignes_lues: int
    lignes_ecrites: int
    lignes_supprimees: int
    message: str


def connexion() -> psycopg2.extensions.connection:
    return psycopg2.connect(load_settings().postgres_dsn)


# --------------------------------------------------------------------------- #
# Olist : déduplication de la géolocalisation
# --------------------------------------------------------------------------- #


def transformer_geolocation(cnx) -> ResultatTransformation:
    """Supprime les lignes strictement dupliquées de staging.olist_geolocation.

    Défaut mesuré : 261 831 lignes sur 1 000 163 (26,2 %). La suppression se
    fait en SQL, sur `ctid`, plutôt qu'en chargeant le million de lignes en
    mémoire : la table n'a pas de clé primaire, un doublon strict y est une
    ligne entière répétée.

    Relancer deux fois de suite ne supprime rien la seconde fois : c'est ce
    qui rend la transformation reproductible (critère de réussite F1.7/F1.8).
    """
    with cnx.cursor() as curseur:
        curseur.execute("SELECT COUNT(*) FROM staging.olist_geolocation")
        (lues,) = curseur.fetchone()
        curseur.execute(
            """
            DELETE FROM staging.olist_geolocation
            WHERE ctid NOT IN (
                SELECT MIN(ctid)
                FROM staging.olist_geolocation
                GROUP BY geolocation_zip_code_prefix, geolocation_lat,
                         geolocation_lng, geolocation_city, geolocation_state
            )
            """
        )
        supprimees = curseur.rowcount
    cnx.commit()
    return ResultatTransformation(
        etape="olist_geolocation",
        lignes_lues=lues,
        lignes_ecrites=lues - supprimees,
        lignes_supprimees=supprimees,
        message=f"{supprimees} doublon(s) strict(s) supprimé(s)",
    )


# --------------------------------------------------------------------------- #
# Olist : normalisation du libellé de catégorie, clé de rapprochement Sprint 3
# --------------------------------------------------------------------------- #


def transformer_categories(cnx) -> ResultatTransformation:
    """Écrit product_category_name_norm : le libellé de catégorie normalisé.

    La colonne d'origine, product_category_name, n'est jamais modifiée — elle
    peut encore servir d'affichage. La colonne normalisée est celle que le
    Sprint 3 utilisera pour rapprocher le catalogue Rakuten.
    """
    lignes = pd.read_sql(
        "SELECT product_id, product_category_name FROM staging.olist_products", cnx
    )
    normalisees = lignes["product_category_name"].map(
        lambda v: normaliser_libelle(None if pd.isna(v) else v)
    )
    # pandas convertit un None de sortie de .map() en NaN : sans cette étape,
    # psycopg2 enverrait NaN (un flottant) vers une colonne TEXT, ce qui échoue.
    # astype(object) est nécessaire avec pandas 3 : sans lui, la colonne garde
    # son dtype « str » spécialisé, qui refuse d'accueillir un vrai None.
    normalisees = normalisees.astype(object).where(pd.notna(normalisees), None)
    a_ecrire = list(zip(lignes["product_id"], normalisees, strict=True))

    with cnx.cursor() as curseur:
        execute_values(
            curseur,
            """
            UPDATE staging.olist_products AS p
            SET product_category_name_norm = c.norm
            FROM (VALUES %s) AS c(product_id, norm)
            WHERE p.product_id = c.product_id
            """,
            a_ecrire,
        )
        ecrites = curseur.rowcount
    cnx.commit()
    return ResultatTransformation(
        etape="olist_categories",
        lignes_lues=len(lignes),
        lignes_ecrites=ecrites,
        lignes_supprimees=0,
        message=f"{ecrites} catégorie(s) normalisée(s)",
    )


# --------------------------------------------------------------------------- #
# Rakuten : décodage du balisage et détection de langue
# --------------------------------------------------------------------------- #


def transformer_rakuten(cnx) -> ResultatTransformation:
    """Décode le balisage de designation/description et écrit la langue détectée.

    Défauts mesurés : 63,6 % des descriptions contiennent des entités HTML,
    28,4 % des balises ; le catalogue n'est francophone qu'à 62 %.

    Les 2 651 désignations strictement identiques sur des produits différents
    (défaut mesuré, section 3.3 du dossier de conception) ne sont PAS
    supprimées — les identifiants produits sont uniques, seul le libellé se
    répète — elles sont seulement comptées et rapportées, comme le prévoit la
    stratégie de qualité.
    """
    lignes = pd.read_sql(
        "SELECT jeu, index_ligne, designation, description FROM staging.rakuten_produits", cnx
    )
    designations = lignes["designation"].map(lambda v: decoder_balisage(None if pd.isna(v) else v))
    descriptions = lignes["description"].map(lambda v: decoder_balisage(None if pd.isna(v) else v))
    # Même correction que pour les catégories (voir transformer_categories) :
    # restaurer de vrais None avant psycopg2, via astype(object) requis par pandas 3.
    designations = designations.astype(object).where(pd.notna(designations), None)
    descriptions = descriptions.astype(object).where(pd.notna(descriptions), None)
    langues = [
        detecter_langue(d if d and d.strip() else desc)
        for d, desc in zip(designations, descriptions, strict=True)
    ]
    doublons_designation = int(designations.duplicated(keep=False).sum())

    a_ecrire = list(
        zip(lignes["jeu"], lignes["index_ligne"], designations, descriptions, langues, strict=True)
    )
    with cnx.cursor() as curseur:
        execute_values(
            curseur,
            """
            UPDATE staging.rakuten_produits AS r
            SET designation = c.designation,
                description = c.description,
                langue = c.langue
            FROM (VALUES %s) AS c(jeu, index_ligne, designation, description, langue)
            WHERE r.jeu = c.jeu AND r.index_ligne = c.index_ligne::integer
            """,
            a_ecrire,
        )
        ecrites = curseur.rowcount
    cnx.commit()
    return ResultatTransformation(
        etape="rakuten_catalogue",
        lignes_lues=len(lignes),
        lignes_ecrites=ecrites,
        lignes_supprimees=0,
        message=f"langue détectée pour {ecrites} fiche(s) ; "
        f"{doublons_designation} désignation(s) dupliquée(s), signalées, non supprimées",
    )


# --------------------------------------------------------------------------- #
# Journalisation
# --------------------------------------------------------------------------- #


def journaliser(resultat: ResultatTransformation, source: str) -> None:
    """Enregistre l'exécution dans staging.execution_log.

    Une panne de journalisation n'interrompt pas la transformation, déjà
    écrite en base : la perdre pour une ligne de journal manquante serait
    absurde. L'incident est signalé, pas fatal — même choix que
    src/acquisition/ingestion.py.
    """
    debut = datetime.now(UTC)
    try:
        with connexion() as cnx, cnx.cursor() as curseur:
            curseur.execute(
                """
                INSERT INTO staging.execution_log
                    (pipeline, etape, source, demarre_a, termine_a,
                     lignes_lues, lignes_ecrites, lignes_rejetees, statut, message)
                VALUES ('transformation', %s, %s, %s, now(), %s, %s, %s, 'succes', %s)
                """,
                (
                    resultat.etape,
                    source,
                    debut,
                    resultat.lignes_lues,
                    resultat.lignes_ecrites,
                    resultat.lignes_supprimees,
                    resultat.message,
                ),
            )
    except psycopg2.Error as erreur:
        print(f"AVERTISSEMENT : exécution non journalisée ({erreur.__class__.__name__})")
