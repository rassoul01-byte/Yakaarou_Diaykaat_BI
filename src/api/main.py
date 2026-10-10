"""API HTTP pour l'app React de démonstration.

Quatre endpoints (périmètre rouvert avec Ndeye Penda le 2026-10-08, pour que
la vue générale affiche des chiffres plutôt que des captures d'écran) :
- GET  /api/health
- GET  /api/indicateurs        (routers/indicateurs.py)  — lecture seule
- POST /api/assistant/ask      (routers/assistant.py)
- POST /api/recherche          (routers/recherche.py)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import assistant, indicateurs, recherche

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


# --------------------------------------------------------------- modules

app.include_router(assistant.router, prefix="/api/assistant", tags=["assistant"])
app.include_router(recherche.router, prefix="/api/recherche", tags=["recherche"])
app.include_router(indicateurs.router, prefix="/api/indicateurs", tags=["indicateurs"])
