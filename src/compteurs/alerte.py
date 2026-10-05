"""Alerte sur chute des ventes (F2.7).

La décision tient en trois règles, et chacune existe pour une raison :

- **on compare au même jour de la semaine**, parce qu'un dimanche ne se compare
  pas à un mardi ;
- **on n'alerte pas avant midi**, parce que l'activité d'une matinée est
  toujours inférieure à celle d'une journée entière ;
- **on n'alerte pas sans historique**, parce qu'il n'y a rien à comparer.

Une alerte qui se déclenche sans raison cesse d'être lue au bout d'une semaine :
c'est le réglage qui fait l'outil, pas le calcul.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import psycopg2

from common.config import load_settings

SEUIL_POURCENT = 60.0
HEURE_MINIMALE = 12
JOURS_MINIMUM = 2

REQUETE = """
    SELECT jour, jour_semaine, achats, achats_habituels, jours_compares
    FROM staging.v_alerte_ventes
    ORDER BY jour DESC
    LIMIT %(limite)s
"""


@dataclass(frozen=True)
class Verdict:
    jour: date
    achats: int
    habituels: float | None
    jours_compares: int
    heure: int
    seuil: float = SEUIL_POURCENT

    @property
    def niveau_pourcent(self) -> float | None:
        """Part de l'activité habituelle, en pourcentage."""
        if not self.habituels:
            return None
        return round(100.0 * self.achats / float(self.habituels), 1)

    @property
    def comparable(self) -> bool:
        return self.jours_compares >= JOURS_MINIMUM and bool(self.habituels)

    @property
    def alerte(self) -> bool:
        if not self.comparable or self.heure < HEURE_MINIMALE:
            return False
        return self.niveau_pourcent < self.seuil

    def message(self) -> str:
        if not self.comparable:
            return (
                f"{self.jour} : pas assez d'historique pour comparer "
                f"({self.jours_compares} jour(s) de référence, {JOURS_MINIMUM} requis)"
            )
        if self.heure < HEURE_MINIMALE:
            return (
                f"{self.jour} : trop tôt pour juger ({self.heure} h) — "
                f"l'activité d'une matinée est toujours incomplète"
            )
        if self.alerte:
            return (
                f"{self.jour} : {self.achats} achat(s) contre {self.habituels} "
                f"habituellement, soit {self.niveau_pourcent} % — en dessous du "
                f"seuil de {self.seuil:.0f} %"
            )
        return (
            f"{self.jour} : {self.achats} achat(s) contre {self.habituels} "
            f"habituellement, soit {self.niveau_pourcent} % — rien à signaler"
        )


def evaluer(ligne: dict, heure: int) -> Verdict:
    return Verdict(
        jour=ligne["jour"],
        achats=ligne["achats"],
        habituels=float(ligne["achats_habituels"]) if ligne["achats_habituels"] else None,
        jours_compares=ligne["jours_compares"],
        heure=heure,
    )


def collecter(limite: int = 10, heure: int | None = None) -> list[Verdict]:
    """Les derniers jours, chacun avec son verdict."""
    heure = datetime.now().hour if heure is None else heure
    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        curseur.execute(REQUETE, {"limite": limite})
        colonnes = [colonne.name for colonne in curseur.description]
        lignes = [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]
    # Seul le jour le plus récent est jugé à l'heure courante : les jours
    # passés sont complets, on les évalue comme s'il était midi passé.
    return [evaluer(ligne, heure if i == 0 else 23) for i, ligne in enumerate(lignes)]
