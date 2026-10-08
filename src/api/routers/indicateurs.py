"""Router des indicateurs de la vue générale.

Expose `GET /api/indicateurs` : tout ce qu'affiche la page d'accueil du
frontend, en une seule réponse et une seule connexion PostgreSQL.

**Lecture seule.** Le router ne calcule rien : il lit des vues et il appelle
`compteurs.alerte`, qui porte déjà le seuil de chute des ventes, la règle de
midi et celle de l'historique minimum. Dupliquer ce calcul ici, c'est accepter
qu'un jour les deux ne disent plus la même chose.

Les montants viennent de l'entrepôt ; les compteurs du jour viennent du
générateur d'événements, donc d'un **trafic simulé** — le drapeau
`trafic_simule` est dans la réponse pour que la page l'affiche sans avoir à le
savoir d'elle-même.
"""

from __future__ import annotations

import logging

import psycopg2
from fastapi import APIRouter, HTTPException, Query

from compteurs.alerte import collecter as collecter_alertes
from indicateurs.lecture import collecter_pour_la_page

from ..schemas import AlerteOut, IndicateursOut

router = APIRouter()
logger = logging.getLogger(__name__)


def _alerte_la_plus_recente(heure: int | None = None) -> AlerteOut | None:
    """La journée signalée la plus récente, ou None si rien n'est à signaler.

    On parcourt les dix derniers jours plutôt que le seul jour courant : une
    chute passée inaperçue reste une chute, et le jour le plus récent est
    souvent celui qui a le moins d'historique derrière lui.
    """
    verdicts = collecter_alertes(limite=10, heure=heure)
    signalees = [verdict for verdict in verdicts if verdict.alerte]
    if not signalees:
        return None

    verdict = signalees[0]
    return AlerteOut(
        jour=str(verdict.jour),
        achats=verdict.achats,
        achats_habituels=verdict.habituels,
        jours_compares=verdict.jours_compares,
        niveau_pourcent=verdict.niveau_pourcent,
        seuil_pourcent=verdict.seuil,
        declenchee=True,
        message=verdict.message(),
    )


@router.get("", response_model=IndicateursOut)
def indicateurs(
    top: int = Query(default=8, ge=1, le=30, description="catégories renvoyées"),
    motifs: int = Query(default=6, ge=1, le=20, description="motifs de rejet renvoyés"),
    heure: int | None = Query(
        default=None,
        ge=0,
        le=23,
        description="heure à considérer pour l'alerte, pour rejouer une situation",
    ),
) -> IndicateursOut:
    """Lit les vues et renvoie la page entière.

    Un bloc vide n'est pas une erreur : sur une base fraîchement montée, les
    ventes, les événements et les exécutions sont absents, et la page doit
    pouvoir l'afficher.
    """
    try:
        donnees = collecter_pour_la_page(top=top, motifs=motifs)
        alerte = _alerte_la_plus_recente(heure)
    except psycopg2.OperationalError as erreur:
        logger.exception("PostgreSQL injoignable")
        raise HTTPException(
            status_code=503, detail=f"PostgreSQL injoignable : {erreur}"
        ) from erreur
    except psycopg2.Error as erreur:
        # Vue absente, migration non appliquée, droits manquants : la base
        # répond, mais pas ce qu'on lui demande. Ce n'est pas une panne réseau.
        logger.exception("Lecture des indicateurs impossible")
        raise HTTPException(
            status_code=502, detail=f"Lecture des indicateurs impossible : {erreur}"
        ) from erreur

    return IndicateursOut(
        ventes=donnees["ventes"],
        categories=donnees["categories"],
        qualite=donnees["qualite"],
        motifs_de_rejet=donnees["motifs_de_rejet"],
        jour=donnees["jour"],
        achats_par_heure=donnees["achats_par_heure"],
        alerte=alerte,
        segment=donnees["segment"],
        chaine=donnees["chaine"],
    )
