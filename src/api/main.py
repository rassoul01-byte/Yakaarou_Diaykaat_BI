"""API HTTP pour l'app React de démonstration.

Trois endpoints seulement (périmètre figé avec Ndeye Penda) :
- GET  /api/health
- POST /api/assistant/ask
- POST /api/recherche
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
