"""API HTTP pour l'app React de démonstration.

Trois endpoints (périmètre figé avec Ndeye Penda) :
- GET  /api/health
- POST /api/assistant/ask
- POST /api/recherche
"""

from __future__ import annotations

import logging

from elasticsearch.exceptions import ApiError, TransportError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from assistant.assistant import repondre
from assistant.fabrique import creer_retrouveur
from assistant.passages import ErreurCorpus
from assistant.retrouveur import ReponseContratInvalide
from documentaire.rechercher import rechercher
from recherche.client import connexion

from .schemas import AssistantIn, AssistantOut, RechercheIn

logger = logging.getLogger(__name__)

app = FastAPI(title="DataFlow360 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------- santé


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------- assistant


@app.post("/api/assistant/ask", response_model=AssistantOut)
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


# --------------------------------------------------------------- recherche


@app.post("/api/recherche")
def recherche(payload: RechercheIn) -> dict:
    """Cherche des passages dans l'index documentaire (contrat passages.md §7)."""
    try:
        client = connexion()
        resultat = rechercher(client, payload.q, payload.k)
    except (ConnectionError, TransportError, ApiError) as erreur:
        # Les erreurs d'Elasticsearch (ConnectionError, ConnectionTimeout, index absent...)
        # n'héritent pas du ConnectionError natif : sans ce `except`, elles donnent un 500.
        logger.exception("Elasticsearch indisponible")
        raise HTTPException(
            status_code=503, detail=f"Elasticsearch indisponible : {erreur}"
        ) from erreur

    return resultat
