"""Appels aux deux services publics, et rien d'autre.

C'est le seul fichier qui connaît des adresses extérieures. Le reste du
service travaille sur ce qu'il a déjà conservé : un service public injoignable
n'empêche donc jamais la plateforme de fonctionner.

Les deux services sont gratuits et ne demandent aucune clé :
  - BrasilAPI    — jours fériés brésiliens, une année à la fois ;
  - Frankfurter  — taux de change quotidiens de la Banque centrale européenne.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

import httpx

URL_FERIES = "https://brasilapi.com.br/api/feriados/v1/{annee}"
URL_TAUX = "https://api.frankfurter.dev/v1/{debut}..{fin}"

DELAI = 20.0


class Transport(Protocol):
    """Ce qui va chercher une adresse. Remplacé par un faux dans les tests."""

    def __call__(self, url: str, parametres: dict | None = None) -> object: ...


def transport_http(url: str, parametres: dict | None = None) -> object:
    reponse = httpx.get(url, params=parametres, timeout=DELAI)
    reponse.raise_for_status()
    return reponse.json()


def recuperer_feries(annee: int, transport: Transport = transport_http) -> list[dict]:
    """Jours fériés nationaux d'une année, tels que le service les renvoie."""
    feries = transport(URL_FERIES.format(annee=annee))
    if not isinstance(feries, list):
        raise ValueError(f"réponse inattendue pour les jours fériés {annee}")
    return feries


def recuperer_taux(
    debut: date, fin: date, devise: str = "EUR", transport: Transport = transport_http
) -> dict:
    """Taux quotidiens du réal vers une devise, sur une période.

    Le service ne renvoie que les jours ouvrés : les week-ends et jours fériés
    bancaires sont absents, et c'est au lecteur de retomber sur le jour
    précédent. C'est le comportement attendu, pas un trou dans les données.
    """
    reponse = transport(
        URL_TAUX.format(debut=debut.isoformat(), fin=fin.isoformat()),
        {"base": "BRL", "symbols": devise},
    )
    if not isinstance(reponse, dict) or "rates" not in reponse:
        raise ValueError("réponse inattendue pour les taux de change")
    return reponse
