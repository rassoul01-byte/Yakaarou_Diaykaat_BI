"""Router de la recherche produits (catalogue Rakuten).

Expose `POST /api/recherche` : une requête, les fiches du catalogue classées
par pertinence. Aucun filtre de prix : le catalogue n'en contient pas
(docs/contrats/recherche.md).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from elasticsearch.exceptions import ApiError, TransportError
from fastapi import APIRouter, HTTPException

from recherche.client import connexion
from recherche.moteur import ErreurRecherche, rechercher

from ..schemas import ProduitOut, RechercheIn, RechercheOut

router = APIRouter()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def client_es():
    """Un seul client Elasticsearch pour toute la durée du service.

    Il était auparavant instancié dans le handler : chaque recherche créait un
    transport et un pool de connexions, jamais fermés. Le coût se voyait dans
    le `temps_serveur_ms` que la page affiche.
    """
    return connexion()


@router.post("", response_model=RechercheOut)
def recherche_produits(payload: RechercheIn) -> RechercheOut:
    """Cherche dans le catalogue produits (index ES `catalogue`).

    Champs du contrat recherche.md §1 : product_id, designation,
    categorie_code, score.
    """
    try:
        reponse = rechercher(
            client_es(),
            payload.q,
            taille=payload.k,
            categorie=payload.categorie,
            langue=payload.langue,
        )
    except ValueError as erreur:
        # `min_length=1` compte les espaces : «     » passe la validation
        # Pydantic, puis le moteur refuse une requête vide. C'est une entrée
        # invalide, pas une panne du service — 422, jamais 500.
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except (ConnectionError, TransportError, ApiError) as erreur:
        logger.exception("Elasticsearch indisponible")
        raise HTTPException(
            status_code=503, detail=f"Elasticsearch indisponible : {erreur}"
        ) from erreur
    except ErreurRecherche as erreur:
        logger.exception("Recherche hors contrat")
        raise HTTPException(status_code=502, detail=str(erreur)) from erreur

    return RechercheOut(
        question_posee=payload.q,
        produits=[
            ProduitOut(
                product_id=r.product_id,
                designation=r.designation,
                categorie_code=r.categorie_code,
                score=r.score,
            )
            for r in reponse.resultats
        ],
        total=reponse.total,
        temps_serveur_ms=reponse.temps_serveur_ms,
    )
