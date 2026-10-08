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


_QUALITE = """
    SELECT sources, lignes_lues, lignes_rejetees, taux_rejet_pourcent
    FROM quarantaine.v_taux_rejet_global
"""

# La vue est par source : on agrège pour obtenir le motif, toutes sources confondues.
_MOTIFS = """
    SELECT regle, gravite, SUM(rejets)::int AS rejets
    FROM quarantaine.v_taux_rejet_par_regle
    GROUP BY regle, gravite
    ORDER BY rejets DESC
    LIMIT %(limite)s
"""

_JOUR = """
    SELECT a.jour::text          AS jour,
           a.sessions,
           a.pages_vues,
           a.recherches,
           a.ajouts_panier,
           a.achats,
           c.sessions_avec_achat,
           c.taux_conversion_pourcent
    FROM staging.v_activite_par_jour AS a
    LEFT JOIN staging.v_taux_conversion AS c ON c.jour = a.jour
    ORDER BY a.jour DESC
    LIMIT 1
"""

# Les 24 heures sont toujours renvoyées, y compris celles à zéro : un graphique
# dont l'axe saute de 3 h à 7 h ment sur la forme de la journée.
# L'heure est lue en UTC, comme le `jour` qu'écrit l'ingestion.
_ACHATS_PAR_HEURE = """
    WITH dernier AS (
        SELECT MAX(jour) AS jour FROM staging.evenements_du_jour
    ),
    par_heure AS (
        SELECT EXTRACT(HOUR FROM e.horodatage AT TIME ZONE 'UTC')::int AS heure,
               COUNT(*) AS achats
        FROM staging.evenements_du_jour AS e, dernier AS d
        WHERE e.type = 'achat' AND e.jour = d.jour
        GROUP BY 1
    )
    SELECT h.heure, COALESCE(p.achats, 0)::int AS achats
    FROM generate_series(0, 23) AS h(heure)
    LEFT JOIN par_heure AS p ON p.heure = h.heure
    ORDER BY h.heure
"""

_SEGMENT = """
    SELECT COUNT(*)::int            AS clients,
           MAX(date_reference)::text AS date_reference
    FROM dwh.v_segment_a_retenir
"""

# Aucun nom de pipeline en dur : on renvoie la dernière exécution de chaque
# étape, le pipeline avec, et l'appelant regroupe comme il veut.
_CHAINE = """
    SELECT pipeline,
           etape,
           source,
           duree_secondes,
           lignes_lues,
           lignes_rejetees,
           statut,
           demarre_a::text AS demarre_a
    FROM staging.v_derniere_execution
    ORDER BY demarre_a
"""


def _lire(curseur, requete: str, **parametres) -> list[dict]:
    curseur.execute(requete, parametres)
    colonnes = [colonne.name for colonne in curseur.description]
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]


def _premier(lignes: list[dict]) -> dict | None:
    """La première ligne, ou None si la vue est vide — base jamais chargée."""
    return lignes[0] if lignes else None


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


def collecter_pour_la_page(top: int = 8, motifs: int = 6) -> dict:
    """Tout ce qu'affiche la vue générale du frontend, en une connexion.

    Chaque bloc peut être `None` ou vide sans que l'appel échoue : une base
    fraîchement montée n'a ni ventes, ni événements, ni exécutions, et la page
    doit savoir le dire plutôt que renvoyer une erreur 500.

    L'alerte n'est pas calculée ici : elle appartient à `compteurs.alerte`,
    qui porte le seuil, la règle de midi et celle de l'historique minimum.
    """
    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        return {
            "ventes": _premier(_lire(curseur, _TOTAUX)),
            "categories": _lire(curseur, _CATEGORIES, limite=top),
            "qualite": _premier(_lire(curseur, _QUALITE)),
            "motifs_de_rejet": _lire(curseur, _MOTIFS, limite=motifs),
            "jour": _premier(_lire(curseur, _JOUR)),
            "achats_par_heure": _lire(curseur, _ACHATS_PAR_HEURE),
            "segment": _premier(_lire(curseur, _SEGMENT)),
            "chaine": _lire(curseur, _CHAINE),
        }
