"""F1.10 — Chargement de l'entrepôt en étoile (schéma `dwh`).

Lit la zone intermédiaire (`staging`) et la table de correspondance des produits
(F1.9) — jamais la zone brute — puis charge les dimensions, puis les faits, dans
une seule transaction : le chargement réussit en entier ou ne change rien.

Le contrat (tables, grains, clés, règles) est docs/contrats/entrepot.md.

Étape 1 du contrat (§10) : chargement simple. Les dimensions sont rechargées
sans historisation — toute ligne est une version courante — et les faits sont
vidés puis rechargés. Le résultat est identique à chaque lancement : le
chargement est idempotent.

Usage :
    docker compose exec app python -m integration.chargement

Code de sortie : 0 si le chargement a abouti, 1 sinon (rien n'a alors changé).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import psycopg2

from common.config import load_settings

# Verrou de transaction : deux chargements simultanés (une reprise Airflow qui
# chevauche un lancement manuel, par exemple) s'attendent au lieu de se mélanger.
VERROU = "dwh_chargement"

# Ce que le chargement lit : si l'une de ces tables manque, une étape précédente
# de la chaîne n'a pas tourné.
TABLES_SOURCES = (
    "staging.olist_orders",
    "staging.olist_order_items",
    "staging.olist_order_payments",
    "staging.olist_customers",
    "staging.olist_products",
    "staging.olist_sellers",
    "staging.rakuten_produits",
    "staging.correspondance_produits",
)

TABLES_ENTREPOT = (
    "dwh.dim_date",
    "dwh.dim_client",
    "dwh.dim_produit",
    "dwh.dim_vendeur",
    "dwh.fait_commande",
    "dwh.fait_ligne_commande",
)

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


class ChargementError(Exception):
    """Erreur fonctionnelle du chargement F1.10 : rien n'a été modifié."""


@dataclass(frozen=True)
class Dimension:
    """Une dimension historisable : où la lire, comment l'identifier, quoi suivre."""

    nom: str  # nom de la table, dans le schéma dwh
    cle: str  # clé de substitution
    metier: str  # identifiant métier, conservé en texte
    suivis: tuple[str, ...]  # attributs dont un changement ouvrira une version
    entrants: str  # requête SQL : ce que la zone intermédiaire dit aujourd'hui


# La ville et l'état d'une personne sont ceux de son customer_id le plus petit :
# un choix arbitraire mais déterministe, comme l'écrit le contrat (§3).
_ENTRANTS_CLIENT = """
    SELECT DISTINCT ON (customer_unique_id)
        customer_unique_id,
        customer_city            AS ville,
        customer_state           AS etat,
        customer_zip_code_prefix AS code_postal_prefixe
    FROM staging.olist_customers
    ORDER BY customer_unique_id, customer_id
"""

# La langue est celle de la fiche rattachée. Une fiche peut figurer dans les
# jeux train et test : on retient la ligne du train, la seule qui soit
# affectée par la correspondance (prdtypecode renseigné).
_ENTRANTS_PRODUIT = """
    SELECT
        p.product_id                AS id_produit_olist,
        p.product_category_name_norm AS categorie,
        c.categorie_catalogue,
        c.id_fiche                  AS id_fiche_rakuten,
        c.rattache,
        r.langue
    FROM staging.olist_products AS p
    JOIN staging.correspondance_produits AS c ON c.id_produit = p.product_id
    LEFT JOIN (
        SELECT DISTINCT ON (productid) productid, langue
        FROM staging.rakuten_produits
        WHERE prdtypecode IS NOT NULL
        ORDER BY productid, jeu, index_ligne
    ) AS r ON r.productid = c.id_fiche
"""

_ENTRANTS_VENDEUR = """
    SELECT
        seller_id               AS id_vendeur_olist,
        seller_city             AS ville,
        seller_state            AS etat,
        seller_zip_code_prefix  AS code_postal_prefixe
    FROM staging.olist_sellers
"""

DIMENSIONS = (
    Dimension(
        nom="dim_client",
        cle="client_id",
        metier="customer_unique_id",
        suivis=("ville", "etat", "code_postal_prefixe"),
        entrants=_ENTRANTS_CLIENT,
    ),
    Dimension(
        nom="dim_produit",
        cle="produit_id",
        metier="id_produit_olist",
        suivis=("categorie", "categorie_catalogue", "id_fiche_rakuten", "rattache", "langue"),
        entrants=_ENTRANTS_PRODUIT,
    ),
    Dimension(
        nom="dim_vendeur",
        cle="vendeur_id",
        metier="id_vendeur_olist",
        suivis=("ville", "etat", "code_postal_prefixe"),
        entrants=_ENTRANTS_VENDEUR,
    ),
)

# Ce qui rendrait le chargement faux sans le faire échouer : on le refuse avant
# de toucher à quoi que ce soit.
_CONTROLES_PREALABLES = (
    (
        "commande(s) dont le client est absent de staging.olist_customers",
        """
        SELECT count(*)
        FROM staging.olist_orders AS o
        LEFT JOIN staging.olist_customers AS c ON c.customer_id = o.customer_id
        WHERE c.customer_id IS NULL
        """,
    ),
    (
        "ligne(s) d'article dont la commande est absente de staging.olist_orders",
        """
        SELECT count(*)
        FROM staging.olist_order_items AS i
        LEFT JOIN staging.olist_orders AS o ON o.order_id = i.order_id
        WHERE o.order_id IS NULL
        """,
    ),
    (
        "produit(s) vendu(s) absent(s) de la table de correspondance "
        "(relancer : python -m integration.correspondance)",
        """
        SELECT count(*)
        FROM staging.olist_products AS p
        LEFT JOIN staging.correspondance_produits AS c ON c.id_produit = p.product_id
        WHERE c.id_produit IS NULL
        """,
    ),
)


@dataclass(frozen=True)
class ResultatChargement:
    """Ce qu'un chargement a produit, pour l'affichage et le journal."""

    lignes_lues: int
    lignes_ecrites: int
    comptages: dict[str, int] = field(default_factory=dict)
    message: str = ""


def connexion() -> psycopg2.extensions.connection:
    """Ouvre la connexion PostgreSQL avec la configuration du projet."""
    return psycopg2.connect(load_settings().postgres_dsn)


def _scalaire(curseur, sql: str, parametres=None):
    curseur.execute(sql, parametres)
    return curseur.fetchone()[0]


def verifier_prerequis(curseur) -> None:
    """Refuse de charger si une étape précédente manque ou si les sources se contredisent."""
    manquantes = [
        table
        for table in (*TABLES_SOURCES, *TABLES_ENTREPOT)
        if _scalaire(curseur, "SELECT to_regclass(%s) IS NULL", (table,))
    ]
    if manquantes:
        raise ChargementError(
            "tables absentes : "
            + ", ".join(manquantes)
            + " — appliquer les migrations (scripts/appliquer_sql.py) et "
            "lancer la transformation puis la correspondance."
        )

    if _scalaire(curseur, "SELECT count(*) FROM staging.olist_orders") == 0:
        raise ChargementError("staging.olist_orders est vide : rien à charger.")

    for libelle, requete in _CONTROLES_PREALABLES:
        nombre = _scalaire(curseur, requete)
        if nombre:
            raise ChargementError(f"{nombre} {libelle}.")


def charger_dim_date(curseur) -> int:
    """Complète dim_date : de la première à la dernière date manipulée, plus un mois de marge.

    Toutes les dates de l'entrepôt doivent exister — achat, approbation, remise
    au transporteur, livraison et livraison estimée — sinon une jointure sur
    une date de livraison postérieure à la dernière commande ne trouverait rien.
    """
    curseur.execute(
        """
        SELECT
            (date_trunc('month', MIN(LEAST(
                order_purchase_timestamp, order_approved_at, order_delivered_carrier_date,
                order_delivered_customer_date, order_estimated_delivery_date
            ))) - interval '1 month')::date,
            (date_trunc('month', MAX(GREATEST(
                order_purchase_timestamp, order_approved_at, order_delivered_carrier_date,
                order_delivered_customer_date, order_estimated_delivery_date
            ))) + interval '2 months' - interval '1 day')::date
        FROM staging.olist_orders
        """
    )
    debut, fin = curseur.fetchone()

    curseur.execute(
        """
        INSERT INTO dwh.dim_date
            (date_id, date, annee, trimestre, mois, semaine_iso, jour, nom_jour, nom_mois)
        SELECT
            to_char(d, 'YYYYMMDD')::integer,
            d::date,
            EXTRACT(YEAR    FROM d)::integer,
            EXTRACT(QUARTER FROM d)::integer,
            EXTRACT(MONTH   FROM d)::integer,
            EXTRACT(WEEK    FROM d)::integer,
            EXTRACT(DAY     FROM d)::integer,
            (%(jours)s::text[])[EXTRACT(ISODOW FROM d)::integer],
            (%(mois)s::text[])[EXTRACT(MONTH FROM d)::integer]
        FROM generate_series(%(debut)s::date, %(fin)s::date, interval '1 day') AS d
        ON CONFLICT (date_id) DO NOTHING
        """,
        {"jours": list(JOURS), "mois": list(MOIS), "debut": debut, "fin": fin},
    )
    return curseur.rowcount


def vider_faits(curseur) -> None:
    """Vide les faits : un fait n'a qu'une version, il est rechargé entièrement."""
    curseur.execute("TRUNCATE dwh.fait_ligne_commande, dwh.fait_commande")


def recharger_dimension(curseur, dimension: Dimension, aujourdhui: date) -> int:
    """Étape 1 : repart d'une dimension vide (hors ligne « inconnu »), tout est courant.

    La clé de substitution repart de 1 et l'ordre est celui de l'identifiant
    métier : deux lancements donnent exactement les mêmes clés.
    """
    curseur.execute(f"DELETE FROM dwh.{dimension.nom} WHERE {dimension.cle} <> 0")
    curseur.execute(
        "SELECT setval(pg_get_serial_sequence(%s, %s), 1, false)",
        (f"dwh.{dimension.nom}", dimension.cle),
    )

    colonnes = ", ".join((dimension.metier, *dimension.suivis))
    curseur.execute(
        f"""
        INSERT INTO dwh.{dimension.nom}
            ({colonnes}, valide_du, valide_au, est_courante)
        SELECT {colonnes}, %(aujourdhui)s, NULL, TRUE
        FROM ({dimension.entrants}) AS entrants
        ORDER BY {dimension.metier}
        """,
        {"aujourdhui": aujourdhui},
    )
    return curseur.rowcount


def charger_fait_commande(curseur) -> int:
    """Une ligne par commande, y compris celles sans ligne d'article.

    Les paiements sont agrégés par commande AVANT la jointure : joindre les
    paiements ligne à ligne dupliquerait le montant des commandes réglées en
    plusieurs fois.
    """
    curseur.execute(
        """
        INSERT INTO dwh.fait_commande
            (order_id, client_id, date_id, statut,
             date_achat, date_approbation, date_livraison_transporteur,
             date_livraison_client, date_livraison_estimee,
             delai_livraison_jours, montant_paye, nombre_paiements, a_une_ligne_article)
        SELECT
            o.order_id,
            dc.client_id,
            to_char(o.order_purchase_timestamp, 'YYYYMMDD')::integer,
            o.order_status,
            o.order_purchase_timestamp,
            o.order_approved_at,
            o.order_delivered_carrier_date,
            o.order_delivered_customer_date,
            o.order_estimated_delivery_date,
            (o.order_delivered_customer_date::date - o.order_purchase_timestamp::date),
            COALESCE(p.montant, 0),
            COALESCE(p.nombre, 0),
            EXISTS (SELECT 1 FROM staging.olist_order_items AS i WHERE i.order_id = o.order_id)
        FROM staging.olist_orders AS o
        JOIN staging.olist_customers AS c ON c.customer_id = o.customer_id
        JOIN dwh.dim_client AS dc
            ON dc.customer_unique_id = c.customer_unique_id AND dc.est_courante
        LEFT JOIN (
            SELECT order_id, SUM(payment_value) AS montant, COUNT(*) AS nombre
            FROM staging.olist_order_payments
            GROUP BY order_id
        ) AS p ON p.order_id = o.order_id
        ORDER BY o.order_id
        """
    )
    return curseur.rowcount


def charger_fait_ligne_commande(curseur) -> int:
    """Une ligne par article. Un produit ou un vendeur sans fiche pointe vers la ligne 0."""
    curseur.execute(
        """
        INSERT INTO dwh.fait_ligne_commande
            (order_id, order_item_id, produit_id, vendeur_id, date_id,
             prix, frais_port, quantite)
        SELECT
            i.order_id,
            i.order_item_id,
            COALESCE(dp.produit_id, 0),
            COALESCE(dv.vendeur_id, 0),
            c.date_id,
            i.price,
            i.freight_value,
            1
        FROM staging.olist_order_items AS i
        JOIN dwh.fait_commande AS c ON c.order_id = i.order_id
        LEFT JOIN dwh.dim_produit AS dp
            ON dp.id_produit_olist = i.product_id AND dp.est_courante
        LEFT JOIN dwh.dim_vendeur AS dv
            ON dv.id_vendeur_olist = i.seller_id AND dv.est_courante
        ORDER BY i.order_id, i.order_item_id
        """
    )
    return curseur.rowcount


def compter(curseur) -> dict[str, int]:
    """Comptages de l'entrepôt : lignes courantes des dimensions, hors ligne « inconnu »."""
    comptages: dict[str, int] = {}

    curseur.execute("SELECT count(*) FROM dwh.dim_date WHERE date_id <> 0")
    comptages["dim_date"] = curseur.fetchone()[0]

    for dimension in DIMENSIONS:
        curseur.execute(
            f"SELECT count(*) FROM dwh.{dimension.nom} WHERE est_courante AND {dimension.cle} <> 0"
        )
        comptages[dimension.nom] = curseur.fetchone()[0]

    for fait in ("fait_commande", "fait_ligne_commande"):
        curseur.execute(f"SELECT count(*) FROM dwh.{fait}")
        comptages[fait] = curseur.fetchone()[0]

    return comptages


def charger(cnx, aujourdhui: date | None = None) -> ResultatChargement:
    """Charge l'entrepôt dans une transaction : tout, ou rien.

    `aujourdhui` est la date de chargement inscrite dans `valide_du` ; elle est
    paramétrable pour que les tests puissent simuler des chargements successifs.
    """
    aujourdhui = aujourdhui or date.today()

    try:
        with cnx.cursor() as curseur:
            curseur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (VERROU,))

            verifier_prerequis(curseur)

            lignes_lues = _scalaire(
                curseur,
                "SELECT (SELECT count(*) FROM staging.olist_orders)"
                " + (SELECT count(*) FROM staging.olist_order_items)",
            )

            charger_dim_date(curseur)

            # Les faits d'abord : ils référencent les dimensions, qu'on va recharger.
            vider_faits(curseur)
            for dimension in DIMENSIONS:
                recharger_dimension(curseur, dimension, aujourdhui)

            charger_fait_commande(curseur)
            charger_fait_ligne_commande(curseur)

            comptages = compter(curseur)

        cnx.commit()
    except Exception:
        cnx.rollback()
        raise

    lignes_ecrites = comptages["fait_commande"] + comptages["fait_ligne_commande"]
    message = " ; ".join(f"{nom}={valeur}" for nom, valeur in comptages.items())

    return ResultatChargement(
        lignes_lues=lignes_lues,
        lignes_ecrites=lignes_ecrites,
        comptages=comptages,
        message=message,
    )


def journaliser(
    debut: datetime, resultat: ResultatChargement | None, erreur: str | None = None
) -> None:
    """Journalise l'exécution sans jamais rendre la journalisation fatale."""
    try:
        with connexion() as cnx, cnx.cursor() as curseur:
            curseur.execute(
                """
                INSERT INTO staging.execution_log
                    (pipeline, etape, source, demarre_a, termine_a,
                     lignes_lues, lignes_ecrites, lignes_rejetees, statut, message)
                VALUES
                    ('integration', 'chargement', 'olist+rakuten', %s, now(),
                     %s, %s, 0, %s, %s)
                """,
                (
                    debut,
                    resultat.lignes_lues if resultat else None,
                    resultat.lignes_ecrites if resultat else None,
                    "succes" if resultat else "echec",
                    resultat.message if resultat else erreur,
                ),
            )
    except psycopg2.Error as exception:
        print(f"AVERTISSEMENT : exécution non journalisée ({exception.__class__.__name__})")


def afficher(resultat: ResultatChargement) -> None:
    """Affiche les comptages : c'est ce que la démonstration montre."""
    print("=== F1.10 — Chargement de l'entrepôt ===")
    for nom, valeur in resultat.comptages.items():
        print(f"  {nom:<22} {valeur:>10}")


def executer() -> ResultatChargement:
    """Exécute le chargement avec la configuration du projet."""
    debut = datetime.now(UTC)
    cnx = connexion()
    try:
        resultat = charger(cnx)
    except Exception as erreur:
        cnx.close()
        journaliser(debut, None, str(erreur))
        raise
    cnx.close()

    afficher(resultat)
    journaliser(debut, resultat)
    return resultat


def main() -> int:
    """Point d'entrée CLI de F1.10."""
    try:
        executer()
    except ChargementError as erreur:
        print(f"ERREUR F1.10 : {erreur}", file=sys.stderr)
        return 1
    except psycopg2.Error as erreur:
        print(f"ERREUR F1.10 : problème PostgreSQL ({erreur})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
