"""Interroger le service référentiel depuis un autre module.

C'est par ici qu'Aissata récupère les jours fériés pour la dimension temps, et
que les indicateurs convertissent un montant. Personne n'appelle de service
extérieur directement.
"""

from __future__ import annotations

import os
from datetime import date

import httpx

ADRESSE_PAR_DEFAUT = "http://referentiel:8000"
DELAI = 10.0


def adresse() -> str:
    return os.getenv("REFERENTIEL_URL", ADRESSE_PAR_DEFAUT)


def jours_feries(annee: int, client: httpx.Client | None = None) -> list[date]:
    """Dates des jours fériés d'une année, prêtes pour la dimension temps."""
    appelant = client or httpx.Client(timeout=DELAI)
    reponse = appelant.get(f"{adresse()}/feries/{annee}")
    reponse.raise_for_status()
    return [date.fromisoformat(f["date"]) for f in reponse.json()["feries"]]


def taux_du_jour(jour: date, devise: str = "EUR", client: httpx.Client | None = None) -> float:
    """Taux du réal vers la devise, à cette date ou au dernier jour ouvré avant."""
    appelant = client or httpx.Client(timeout=DELAI)
    reponse = appelant.get(f"{adresse()}/taux", params={"date": jour.isoformat(), "devise": devise})
    reponse.raise_for_status()
    return float(reponse.json()["taux"])
