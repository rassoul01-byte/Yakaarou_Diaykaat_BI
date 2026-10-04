"""Surveillance du retard des lecteurs du bus (F6.3).

Le retard d'un groupe est le nombre de messages publiés qu'il n'a pas encore
lus. Ce chiffre seul ne dit rien : mille messages de retard sur un flux
chargé est normal, cent sur un flux calme ne l'est pas. **Ce qui se surveille,
c'est la tendance** — un retard qui grandit relevé après relevé signale un
lecteur arrêté ou trop lent.

D'où un relevé historisé plutôt qu'une photographie.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg2
import psycopg2.extras

from common.bus import etat_du_bus
from common.config import load_settings

# Trois relevés à la hausse : c'est le minimum pour parler d'une tendance et
# non d'un à-coup. Deux suffiraient à alerter sur le moindre pic de trafic.
RELEVES_POUR_UNE_TENDANCE = 3


@dataclass(frozen=True)
class Lecteur:
    groupe: str
    sujet: str
    retard: int
    releves: tuple  # du plus récent au plus ancien

    @property
    def decroche(self) -> bool:
        """Le retard grandit-il à chaque relevé ?"""
        if len(self.releves) < RELEVES_POUR_UNE_TENDANCE:
            return False
        return all(
            recent > ancien for recent, ancien in zip(self.releves, self.releves[1:], strict=False)
        )


def relever(bootstrap: str | None = None, dsn: str | None = None) -> int:
    """Photographie le bus et enregistre le retard de chaque lecteur.

    Renvoie le nombre de lecteurs relevés. Un bus sans aucun groupe de lecture
    n'est pas une erreur : c'est l'état normal avant le premier consommateur.
    """
    _, retards = etat_du_bus(bootstrap)
    if not retards:
        return 0

    lignes = [(r.groupe, r.sujet, r.retard) for r in retards]
    with psycopg2.connect(dsn or load_settings().postgres_dsn) as connexion:
        with connexion.cursor() as curseur:
            psycopg2.extras.execute_values(
                curseur,
                "INSERT INTO staging.retard_flux (groupe, sujet, retard) VALUES %s",
                lignes,
            )
    return len(lignes)


def lire_tendances(dsn: str | None = None) -> list[Lecteur]:
    """Les lecteurs du bus, avec leurs trois derniers relevés."""
    requete = """
        SELECT groupe, sujet,
               array_agg(retard ORDER BY releve_a DESC) AS releves
        FROM staging.v_retard_tendance
        GROUP BY groupe, sujet
        ORDER BY groupe, sujet
    """
    with psycopg2.connect(dsn or load_settings().postgres_dsn) as connexion:
        with connexion.cursor() as curseur:
            curseur.execute(requete)
            return [
                Lecteur(groupe=g, sujet=s, retard=releves[0], releves=tuple(releves))
                for g, s, releves in curseur.fetchall()
            ]


def anomalies(lecteurs: list[Lecteur]) -> list[str]:
    """Ce qui mérite d'être regardé dans le flux, une phrase par lecteur."""
    signalements = []
    for lecteur in lecteurs:
        if lecteur.decroche:
            suite = " → ".join(str(r) for r in reversed(lecteur.releves))
            signalements.append(
                f"{lecteur.groupe} décroche sur {lecteur.sujet} : "
                f"son retard grandit à chaque relevé ({suite})"
            )
    return signalements
