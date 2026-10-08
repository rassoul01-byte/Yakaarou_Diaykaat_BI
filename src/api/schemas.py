"""Schémas Pydantic pour l'API de démonstration.

Ces schémas sont le miroir exact des types TypeScript côté frontend
(frontend/src/types/api.ts). Toute modification doit être répercutée
des deux côtés dans la même PR.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# --------------------------------------------------------------- assistant


class AssistantIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    k: int = Field(default=3, ge=1, le=10)


class PassageOut(BaseModel):
    id: str
    theme: str
    question: str
    source: str
    score: float


class AssistantOut(BaseModel):
    reponse: str
    refus: bool
    motif: str | None
    passages: list[PassageOut]
    suggestions: list[PassageOut]
    duree_ms: int


# --------------------------------------------------------------- recherche


class RechercheIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)
    k: int = Field(default=5, ge=1, le=20)
