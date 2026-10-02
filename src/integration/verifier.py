"""F1.10 — Vérifications de niveau 3 après le chargement de l'entrepôt.

Compare l'entrepôt à la zone intermédiaire dont il vient : mêmes comptages,
mêmes totaux, aucun fait orphelin. Ce module ne corrige rien, il constate.

Usage :
    docker compose exec app python -m integration.verifier

Code de sortie : 0 si tous les contrôles passent, 1 si l'un d'eux échoue ou si
l'entrepôt est illisible. C'est ce code qu'Airflow lit pour marquer la tâche
de vérification en échec.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg2

from common.config import load_settings


@dataclass(frozen=True)
class Controle:
    """Un contrôle : ce qu'on attendait, ce qu'on a constaté."""

    nom: str
    attendu: object
    constate: object

    @property
    def ok(self) -> bool:
        return self.attendu == self.constate


# (table de faits, colonne, dimension ou fait référencé, colonne référencée)
CLES_ETRANGERES = (
    ("fait_commande", "client_id", "dim_client", "client_id"),
    ("fait_commande", "date_id", "dim_date", "date_id"),
    ("fait_ligne_commande", "order_id", "fait_commande", "order_id"),
    ("fait_ligne_commande", "produit_id", "dim_produit", "produit_id"),
    ("fait_ligne_commande", "vendeur_id", "dim_vendeur", "vendeur_id"),
    ("fait_ligne_commande", "date_id", "dim_date", "date_id"),
)

# (dimension historisée, clé de substitution, identifiant métier, table staging)
DIMENSIONS_HISTORISEES = (
    (
        "dim_client",
        "client_id",
        "customer_unique_id",
        "staging.olist_customers",
        "customer_unique_id",
    ),
    ("dim_produit", "produit_id", "id_produit_olist", "staging.olist_products", "product_id"),
    ("dim_vendeur", "vendeur_id", "id_vendeur_olist", "staging.olist_sellers", "seller_id"),
)


def connexion() -> psycopg2.extensions.connection:
    """Ouvre la connexion PostgreSQL avec la configuration du projet."""
    return psycopg2.connect(load_settings().postgres_dsn)


def _scalaire(curseur, sql: str):
    curseur.execute(sql)
    return curseur.fetchone()[0]


def construire_controles(curseur) -> list[Controle]:
    """Exécute tous les contrôles du contrat (§7), plus quelques recoupements."""
    controles: list[Controle] = []

    def ajouter(nom: str, attendu_sql: str | None, constate_sql: str, attendu=None) -> None:
        valeur_attendue = _scalaire(curseur, attendu_sql) if attendu_sql else attendu
        controles.append(Controle(nom, valeur_attendue, _scalaire(curseur, constate_sql)))

    # --- Comptages comparés à la zone intermédiaire ---------------------------
    ajouter(
        "comptage fait_ligne_commande = staging.olist_order_items",
        "SELECT count(*) FROM staging.olist_order_items",
        "SELECT count(*) FROM dwh.fait_ligne_commande",
    )
    ajouter(
        "comptage fait_commande = staging.olist_orders",
        "SELECT count(*) FROM staging.olist_orders",
        "SELECT count(*) FROM dwh.fait_commande",
    )

    # --- Aucun fait orphelin, ligne « inconnu » (0) comprise comme cible valide
    for table, colonne, cible, cle_cible in CLES_ETRANGERES:
        ajouter(
            f"aucun orphelin : {table}.{colonne} → {cible}",
            None,
            f"""
            SELECT count(*)
            FROM dwh.{table} AS f
            LEFT JOIN dwh.{cible} AS c ON c.{cle_cible} = f.{colonne}
            WHERE c.{cle_cible} IS NULL
            """,
            attendu=0,
        )
    ajouter(
        "date d'une ligne = date d'achat de sa commande",
        None,
        """
        SELECT count(*)
        FROM dwh.fait_ligne_commande AS l
        JOIN dwh.fait_commande AS c USING (order_id)
        WHERE l.date_id <> c.date_id
        """,
        attendu=0,
    )

    # --- Totaux ----------------------------------------------------------------
    ajouter(
        "somme des prix = staging.olist_order_items",
        "SELECT COALESCE(SUM(price), 0) FROM staging.olist_order_items",
        "SELECT COALESCE(SUM(prix), 0) FROM dwh.fait_ligne_commande",
    )
    ajouter(
        "somme des frais de port = staging.olist_order_items",
        "SELECT COALESCE(SUM(freight_value), 0) FROM staging.olist_order_items",
        "SELECT COALESCE(SUM(frais_port), 0) FROM dwh.fait_ligne_commande",
    )
    # Un montant réglé en plusieurs fois ne doit être compté qu'une fois.
    ajouter(
        "somme des montants payés = paiements staging (sans doublon)",
        """
        SELECT COALESCE(SUM(p.payment_value), 0)
        FROM staging.olist_order_payments AS p
        JOIN staging.olist_orders AS o USING (order_id)
        """,
        "SELECT COALESCE(SUM(montant_paye), 0) FROM dwh.fait_commande",
    )

    # --- Commandes sans ligne d'article : présentes, mais elles pèsent zéro -----
    ajouter(
        "commandes sans article = marquées a_une_ligne_article = faux",
        """
        SELECT count(*)
        FROM staging.olist_orders AS o
        WHERE NOT EXISTS (SELECT 1 FROM staging.olist_order_items AS i WHERE i.order_id = o.order_id)
        """,
        "SELECT count(*) FROM dwh.fait_commande WHERE NOT a_une_ligne_article",
    )
    ajouter(
        "a_une_ligne_article cohérent avec fait_ligne_commande",
        None,
        """
        SELECT count(*)
        FROM dwh.fait_commande AS c
        WHERE c.a_une_ligne_article
              IS DISTINCT FROM EXISTS (
                  SELECT 1 FROM dwh.fait_ligne_commande AS l WHERE l.order_id = c.order_id
              )
        """,
        attendu=0,
    )

    # --- Dimensions ---------------------------------------------------------------
    for nom, cle, metier, source, cle_source in DIMENSIONS_HISTORISEES:
        # dim_client : 96 096 personnes sur le jeu complet, plus la ligne 0.
        ajouter(
            f"{nom} : lignes courantes = identifiants de {source} + ligne 0",
            f"SELECT count(DISTINCT {cle_source}) + 1 FROM {source}",
            f"SELECT count(*) FROM dwh.{nom} WHERE est_courante",
        )
        ajouter(
            f"{nom} : au plus une version courante par identifiant",
            None,
            f"""
            SELECT count(*) FROM (
                SELECT {metier} FROM dwh.{nom}
                WHERE est_courante
                GROUP BY {metier} HAVING count(*) > 1
            ) AS doublons
            """,
            attendu=0,
        )
        ajouter(
            f"{nom} : la ligne « inconnu » (0) est présente et courante",
            None,
            f"SELECT count(*) FROM dwh.{nom} WHERE {cle} = 0 AND est_courante",
            attendu=1,
        )

    return controles


def verifier(cnx) -> list[Controle]:
    """Lit l'entrepôt et retourne les contrôles, réussis ou non."""
    with cnx.cursor() as curseur:
        return construire_controles(curseur)


def code_sortie(controles: list[Controle]) -> int:
    """0 si tout passe, 1 sinon. Une liste vide ne prouve rien : c'est un échec."""
    return 0 if controles and all(c.ok for c in controles) else 1


def afficher(controles: list[Controle]) -> None:
    """Un contrôle par ligne ; l'attendu et le constaté ne sont montrés qu'en cas d'écart."""
    print("=== F1.10 — Vérification de l'entrepôt ===")
    for controle in controles:
        if controle.ok:
            print(f"  [OK]    {controle.nom}")
        else:
            print(
                f"  [ECHEC] {controle.nom} — attendu {controle.attendu}, constaté {controle.constate}"
            )
    echecs = sum(1 for c in controles if not c.ok)
    print(f"\n{len(controles) - echecs}/{len(controles)} contrôles réussis.")


def journaliser(debut: datetime, controles: list[Controle]) -> None:
    """Journalise la vérification sans jamais rendre la journalisation fatale."""
    echecs = [c.nom for c in controles if not c.ok]
    try:
        with connexion() as cnx, cnx.cursor() as curseur:
            curseur.execute(
                """
                INSERT INTO staging.execution_log
                    (pipeline, etape, source, demarre_a, termine_a,
                     lignes_lues, lignes_ecrites, lignes_rejetees, statut, message)
                VALUES
                    ('integration', 'verification', 'dwh', %s, now(), %s, 0, %s, %s, %s)
                """,
                (
                    debut,
                    len(controles),
                    len(echecs),
                    "succes" if not echecs else "echec",
                    "; ".join(echecs) or "tous les contrôles réussis",
                ),
            )
    except psycopg2.Error as exception:
        print(f"AVERTISSEMENT : exécution non journalisée ({exception.__class__.__name__})")


def main() -> int:
    """Point d'entrée CLI : 0 si l'entrepôt est conforme, 1 sinon."""
    debut = datetime.now(UTC)
    try:
        cnx = connexion()
        try:
            controles = verifier(cnx)
        finally:
            cnx.close()
    except psycopg2.Error as erreur:
        print(f"ERREUR F1.10 : entrepôt illisible ({erreur})", file=sys.stderr)
        return 1

    afficher(controles)
    journaliser(debut, controles)
    return code_sortie(controles)


if __name__ == "__main__":
    sys.exit(main())
