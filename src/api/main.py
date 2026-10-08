"""API HTTP pour l'app React de démonstration.

Trois endpoints (périmètre figé avec Ndeye Penda) :
- GET  /api/health
- POST /api/assistant/ask      (routers/assistant.py)
- POST /api/recherche          (routers/recherche.py)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import assistant, recherche

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
