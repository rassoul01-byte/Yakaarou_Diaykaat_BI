"""Router de l'assistant FAQ.

Expose `POST /api/assistant/ask` : une question, le contrat complet en retour
(réponse, refus, motif, passages, suggestions, durée).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from assistant.assistant import repondre
from assistant.fabrique import creer_retrouveur
from assistant.passages import ErreurCorpus
from assistant.retrouveur import ReponseContratInvalide

from ..schemas import AssistantIn, AssistantOut

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=AssistantOut)
def assistant_ask(payload: AssistantIn) -> AssistantOut:
    """Pose une question à l'assistant et renvoie le contrat complet."""
    try:
        retrouveur = creer_retrouveur()
        rep = repondre(payload.question, retrouveur, k=payload.k)
    except ErreurCorpus as erreur:
        logger.exception("FAQ illisible")
        raise HTTPException(status_code=500, detail=f"FAQ illisible : {erreur}") from erreur
    except ConnectionError as erreur:
        logger.exception("Recherche documentaire injoignable")
        raise HTTPException(
            status_code=503, detail=f"Recherche indisponible : {erreur}"
        ) from erreur
    except ReponseContratInvalide as erreur:
        logger.exception("Recherche hors contrat")
        raise HTTPException(status_code=502, detail=f"Réponse hors contrat : {erreur}") from erreur

    return AssistantOut(**rep.en_dict())
