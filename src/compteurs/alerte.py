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
from datetime import UTC, date, datetime

import psycopg2

from common.config import load_settings

SEUIL_POURCENT = 60.0
HEURE_MINIMALE = 12
JOURS_MINIMUM = 2

# Au-delà de ce nombre de jours sans aucun événement, le silence n'est plus une
# absence de chute : c'est une panne de la chaîne. Voir `flux_interrompu`.
JOURS_SANS_FLUX_TOLERES = 1

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
        """Part de l'activité habituelle, en pourcentage, arrondie pour l'affichage.

        **Ne pas comparer au seuil avec cette valeur** : l'arrondi peut faire
        remonter un niveau sous le seuil jusqu'au seuil exact. Avec 240 achats
        contre 400,25 habituels, le niveau réel est 59,96 % et l'arrondi donne
        60,0 % — l'alerte serait perdue. `alerte` compare la valeur exacte.
        """
        exact = self.niveau_exact
        return None if exact is None else round(exact, 1)

    @property
    def niveau_exact(self) -> float | None:
        """Le même niveau, sans arrondi : c'est lui qui décide."""
        if not self.habituels:
            return None
        return 100.0 * self.achats / float(self.habituels)

    @property
    def comparable(self) -> bool:
        return self.jours_compares >= JOURS_MINIMUM and bool(self.habituels)

    @property
    def alerte(self) -> bool:
        if not self.comparable or self.heure < HEURE_MINIMALE:
            return False
        return self.niveau_exact < self.seuil

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


def flux_interrompu(dernier_jour: date | None, aujourd_hui: date) -> int | None:
    """Nombre de jours sans aucun événement, ou None si le flux est à jour.

    Pourquoi cette fonction existe. `v_achats_par_jour` agrège par jour : un
    jour **sans aucun événement** ne produit pas de ligne. L'alerte lisait donc
    le jour le plus récent *présent dans la vue*, jamais la date du jour. Si le
    consommateur du bus s'arrête, elle se taisait — et jugeait « rien à
    signaler » une journée vieille de trois jours.

    C'est le cas que le dictionnaire prétendait couvrir : « l'alerte détecte
    aussi bien une panne de la chaîne qu'une baisse réelle ». Zéro achat
    déclenchait bien ; zéro **événement** ne déclenchait rien. La panne la plus
    franche était la seule invisible.
    """
    if dernier_jour is None:
        return None
    retard = (aujourd_hui - dernier_jour).days
    return retard if retard > JOURS_SANS_FLUX_TOLERES else None


def collecter(
    limite: int = 10, heure: int | None = None, aujourd_hui: date | None = None
) -> list[Verdict]:
    """Les derniers jours, chacun avec son verdict.

    L'heure et le jour sont lus en UTC, comme le `jour` qu'écrit l'ingestion
    (`compteurs/consommateur.py`). `datetime.now()` sans fuseau donnait l'heure
    locale du conteneur : cela coïncidait tant que le conteneur tournait en UTC,
    mais rien ne le garantissait.
    """
    maintenant = datetime.now(UTC)
    heure = maintenant.hour if heure is None else heure
    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        curseur.execute(REQUETE, {"limite": limite})
        colonnes = [colonne.name for colonne in curseur.description]
        lignes = [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]
    # Seul le jour le plus récent est jugé à l'heure courante : les jours
    # passés sont complets, on les évalue comme s'il était midi passé.
    return [evaluer(ligne, heure if i == 0 else 23) for i, ligne in enumerate(lignes)]


def dernier_jour_connu(verdicts: list[Verdict]) -> date | None:
    """Le jour le plus récent présent dans la vue, ou None si elle est vide."""
    return verdicts[0].jour if verdicts else None
