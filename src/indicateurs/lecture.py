"""Lecture des vues d'indicateurs, et rien d'autre."""

from __future__ import annotations

import psycopg2

from common.config import load_settings

PERIODES = ("jour", "semaine", "mois")

_REQUETES = {
    "jour": """
        SELECT jour::text AS periode, chiffre_affaires, commandes, panier_moyen
        FROM dwh.v_ventes_par_jour
        ORDER BY jour DESC
        LIMIT %(limite)s
    """,
    "semaine": """
        SELECT annee || '-S' || lpad(semaine_iso::text, 2, '0') AS periode,
               chiffre_affaires, commandes, panier_moyen
        FROM dwh.v_ventes_par_semaine
        ORDER BY annee DESC, semaine_iso DESC
        LIMIT %(limite)s
    """,
    "mois": """
        SELECT annee || '-' || lpad(mois::text, 2, '0') AS periode,
               chiffre_affaires, commandes, panier_moyen
        FROM dwh.v_ventes_par_mois
        ORDER BY annee DESC, mois DESC
        LIMIT %(limite)s
    """,
}

_TOTAUX = """
    SELECT chiffre_affaires, commandes, articles, panier_moyen,
           premier_jour::text, dernier_jour::text
    FROM dwh.v_ventes_totales
"""

_CATEGORIES = """
    SELECT categorie, chiffre_affaires, articles, commandes
    FROM dwh.v_categories_les_plus_vendues
    ORDER BY chiffre_affaires DESC NULLS LAST
    LIMIT %(limite)s
"""

_PRODUITS = """
    SELECT id_produit_olist, categorie, rattache, chiffre_affaires, articles
    FROM dwh.v_produits_les_plus_vendus
    ORDER BY chiffre_affaires DESC NULLS LAST
    LIMIT %(limite)s
"""


def _lire(curseur, requete: str, **parametres) -> list[dict]:
    curseur.execute(requete, parametres)
    colonnes = [colonne.name for colonne in curseur.description]
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]


def collecter(periode: str = "mois", limite: int = 12, top: int = 10) -> dict:
    """Lit les vues et renvoie de quoi afficher le rapport."""
    if periode not in PERIODES:
        raise ValueError(f"période inconnue : {periode!r} (attendu : {', '.join(PERIODES)})")

    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        totaux = _lire(curseur, _TOTAUX)
        return {
            "periode": periode,
            "totaux": totaux[0] if totaux else {},
            "series": _lire(curseur, _REQUETES[periode], limite=limite),
            "categories": _lire(curseur, _CATEGORIES, limite=top),
            "produits": _lire(curseur, _PRODUITS, limite=top),
        }
