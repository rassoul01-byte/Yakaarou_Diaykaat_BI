"""Lecture des compteurs. Les vues calculent, ce module met en forme."""

from __future__ import annotations

import psycopg2

from common.config import load_settings

ACTIVITE = """
    SELECT jour::text, evenements, sessions, pages_vues, recherches,
           ajouts_panier, achats, clients_identifies
    FROM staging.v_activite_par_jour
    ORDER BY jour DESC
    LIMIT %(limite)s
"""

CONVERSION = """
    SELECT jour::text, sessions, sessions_avec_achat, taux_conversion_pourcent
    FROM staging.v_taux_conversion
    ORDER BY jour DESC
    LIMIT %(limite)s
"""

REQUETES = """
    SELECT requete, occurrences, sessions
    FROM staging.v_journal_requetes
    ORDER BY occurrences DESC, requete
    LIMIT %(limite)s
"""


def _lire(curseur, requete: str, **parametres) -> list[dict]:
    curseur.execute(requete, parametres)
    colonnes = [colonne.name for colonne in curseur.description]
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]


def collecter(jours: int = 7, top: int = 15) -> dict:
    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        return {
            "activite": _lire(curseur, ACTIVITE, limite=jours),
            "conversion": _lire(curseur, CONVERSION, limite=jours),
            "requetes": _lire(curseur, REQUETES, limite=top),
        }
