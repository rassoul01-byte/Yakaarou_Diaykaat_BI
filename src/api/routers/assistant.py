"""Router de l'assistant FAQ.

Expose `POST /api/assistant/ask` : une question, le contrat complet en retour
(réponse, refus, motif, passages, suggestions, durée).

Chaque échange est écrit dans le journal (`assistant/journal.py`), qui alimente le
taux de réponses ancrées et la relecture des reformulations. **Le journal ne doit
jamais faire échouer une réponse** : un disque plein est un problème de mesure, pas
un problème de service.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from assistant.assistant import repondre
from assistant.fabrique import creer_retrouveur
from assistant.journal import JournalFichier
from assistant.passages import ErreurCorpus
from assistant.retrouveur import ReponseContratInvalide

from ..schemas import AssistantIn, AssistantOut

router = APIRouter()
logger = logging.getLogger(__name__)


class _JournalTolerant:
    """Le journal, enveloppé : une écriture qui échoue est signalée, jamais propagée.

    Le chemin est relu à chaque échange plutôt que gardé : `ASSISTANT_JOURNAL` peut
    changer entre deux appels (tests, démonstration) et un journal mal placé ne doit
    pas survivre au redémarrage d'un paramètre.
    """

    def enregistrer(self, reponse, retrouveur: str, **provenance) -> None:
        try:
            JournalFichier().enregistrer(reponse, retrouveur, **provenance)
        except OSError:
            logger.warning("journal de l'assistant non écrit", exc_info=True)


@router.post("/ask", response_model=AssistantOut)
def assistant_ask(payload: AssistantIn) -> AssistantOut:
    """Pose une question à l'assistant et renvoie le contrat complet."""
    try:
        retrouveur = creer_retrouveur()
        rep = repondre(
            payload.question,
            retrouveur,
            k=payload.k,
            journal=_JournalTolerant(),
            origine=payload.origine,
            reformulation=payload.reformulation,
        )
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
