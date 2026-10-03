"""Le service référentiel : deux routes, lues par le reste de la plateforme.

    GET /sante                    ce que le service a en mémoire
    GET /feries/{annee}           les jours fériés brésiliens de l'année
    GET /taux?date=AAAA-MM-JJ     le taux du réal vers une devise à cette date

Le service ne sort jamais sur Internet : il sert ce que
scripts/alimenter_referentiel.py a conservé dans la zone brute. Une panne des
services publics n'a donc aucun effet sur la plateforme ni sur une démonstration.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from .depot import charger_feries, charger_taux

_feries: dict[int, list[dict]] = {}
_taux: dict[str, dict[str, float]] = {}


def base_donnees() -> Path | None:
    chemin = os.getenv("REFERENTIEL_RACINE")
    return Path(chemin) if chemin else None


def recharger(base: Path | None = None) -> None:
    """Relit la zone brute. Appelée au démarrage, et par les tests."""
    global _feries, _taux
    _feries = charger_feries(base or base_donnees())
    _taux = charger_taux(base or base_donnees())


@asynccontextmanager
async def _cycle_de_vie(_: FastAPI):
    """Charge la zone brute au démarrage du service."""
    recharger()
    yield


app = FastAPI(
    title="DataFlow360 — service référentiel",
    description="Jours fériés brésiliens et taux de change historiques.",
    version="1.0.0",
    lifespan=_cycle_de_vie,
)


@app.get("/sante")
def sante() -> dict:
    devises = {d: len(v) for d, v in _taux.items()}
    return {
        "etat": "ok" if _feries or _taux else "vide",
        "annees_feries": sorted(_feries),
        "taux_par_devise": devises,
    }


@app.get("/feries/{annee}")
def feries(annee: int) -> dict:
    if annee not in _feries:
        raise HTTPException(
            status_code=404,
            detail=(
                f"aucun jour férié conservé pour {annee} — lancer scripts/alimenter_referentiel.py"
            ),
        )
    return {"annee": annee, "nombre": len(_feries[annee]), "feries": _feries[annee]}


@app.get("/taux")
def taux(
    jour: Annotated[date, Query(alias="date", description="date de la commande")],
    devise: Annotated[str, Query(description="devise d'arrivée")] = "EUR",
) -> dict:
    """Taux du réal vers la devise demandée, à cette date.

    Les services de change ne publient rien les jours non ouvrés. Le taux
    renvoyé est alors celui du dernier jour ouvré précédent, et la date
    réellement utilisée est indiquée : un chiffre converti doit toujours
    pouvoir être expliqué.
    """
    serie = _taux.get(devise.upper())
    if not serie:
        raise HTTPException(status_code=404, detail=f"aucun taux conservé pour {devise.upper()}")

    demande = jour.isoformat()
    disponibles = [d for d in serie if d <= demande]
    if not disponibles:
        raise HTTPException(
            status_code=404, detail=f"aucun taux conservé à cette date ou avant : {demande}"
        )

    effective = max(disponibles)
    return {
        "date_demandee": demande,
        "date_effective": effective,
        "base": "BRL",
        "devise": devise.upper(),
        "taux": serie[effective],
    }
