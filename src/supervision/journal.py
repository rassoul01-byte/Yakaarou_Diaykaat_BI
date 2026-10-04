"""Lecture du journal des exécutions.

Rien n'est calculé ici : les vues de la migration 013 font le travail, ce
module les lit et les met en forme.
"""

from __future__ import annotations

import psycopg2
import psycopg2.extras

from common.config import load_settings

DERNIERES = """
    SELECT pipeline, etape, source, demarre_a, duree_secondes,
           lignes_lues, lignes_ecrites, lignes_rejetees, statut
    FROM staging.v_derniere_execution
    ORDER BY pipeline, etape, source NULLS FIRST
"""

PROFIL = """
    SELECT pipeline, etape, source, executions, echecs,
           duree_moyenne_secondes, duree_maximale_secondes, lignes_lues_moyenne
    FROM staging.v_profil_etapes
    ORDER BY duree_moyenne_secondes DESC NULLS LAST
    LIMIT %(limite)s
"""

ECHECS = """
    SELECT pipeline, etape, source, demarre_a, statut, message
    FROM staging.v_echecs
    LIMIT %(limite)s
"""

VOLUME = """
    SELECT jour::text, pipeline, executions, lignes_lues, lignes_rejetees,
           duree_totale_secondes
    FROM staging.v_volume_par_jour
    ORDER BY jour DESC, pipeline
    LIMIT %(limite)s
"""

EN_COURS = """
    SELECT pipeline, etape, source, demarre_a,
           ROUND(EXTRACT(EPOCH FROM (now() - demarre_a))::numeric, 0) AS depuis_secondes
    FROM staging.execution_log
    WHERE termine_a IS NULL
    ORDER BY demarre_a
"""


def _lire(curseur, requete: str, **parametres) -> list[dict]:
    curseur.execute(requete, parametres)
    colonnes = [colonne.name for colonne in curseur.description]
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]


def collecter(limite: int = 20, jours: int = 7) -> dict:
    """Lit les vues de supervision et renvoie de quoi afficher le journal."""
    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        return {
            "dernieres": _lire(curseur, DERNIERES),
            "profil": _lire(curseur, PROFIL, limite=limite),
            "echecs": _lire(curseur, ECHECS, limite=limite),
            "volume": _lire(curseur, VOLUME, limite=jours * 4),
            "en_cours": _lire(curseur, EN_COURS),
        }


def anomalies(donnees: dict, duree_anormale: float = 3.0) -> list[str]:
    """Ce qui mérite d'être regardé, dit en une phrase chacun.

    Trois signaux : une étape en échec, une étape qui dure beaucoup plus que
    d'habitude, et une exécution qui n'est jamais arrivée à son terme. Les
    trois se lisent dans le journal ; aucun ne demande un outil de plus.
    """
    signalements = []

    for ligne in donnees["dernieres"]:
        # Une exécution encore en cours n'a pas échoué : elle est traitée plus
        # bas, et seulement si elle traîne depuis trop longtemps.
        if ligne["statut"] not in ("succes", "en_cours"):
            signalements.append(
                f"{ligne['pipeline']}/{ligne['etape']}"
                f"{' · ' + ligne['source'] if ligne['source'] else ''} "
                f"a échoué à sa dernière exécution ({ligne['statut']})"
            )

    profils = {(p["pipeline"], p["etape"], p["source"]): p for p in donnees["profil"]}
    for ligne in donnees["dernieres"]:
        profil = profils.get((ligne["pipeline"], ligne["etape"], ligne["source"]))
        if not profil or not profil["duree_moyenne_secondes"] or not ligne["duree_secondes"]:
            continue
        if profil["executions"] < 3:
            continue  # pas assez d'historique pour parler d'habitude
        rapport = float(ligne["duree_secondes"]) / float(profil["duree_moyenne_secondes"])
        if rapport >= duree_anormale:
            signalements.append(
                f"{ligne['pipeline']}/{ligne['etape']} a duré {rapport:.1f} fois "
                f"plus longtemps que d'habitude ({ligne['duree_secondes']} s "
                f"contre {profil['duree_moyenne_secondes']} s en moyenne)"
            )

    for ligne in donnees["en_cours"]:
        minutes = int(ligne["depuis_secondes"]) // 60
        if minutes >= 30:
            signalements.append(
                f"{ligne['pipeline']}/{ligne['etape']} est marquée en cours "
                f"depuis {minutes} minutes : exécution interrompue ?"
            )

    return signalements
