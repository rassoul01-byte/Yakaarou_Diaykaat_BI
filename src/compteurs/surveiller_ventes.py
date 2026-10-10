"""Alerte sur chute des ventes.

Usage :
    docker compose exec app python -m compteurs.surveiller_ventes
    docker compose exec app python -m compteurs.surveiller_ventes --heure 14
    docker compose exec app python -m compteurs.surveiller_ventes --jours 14

⚠️ Trafic simulé : cette alerte ne détecte rien de réel. Ce qu'elle démontre,
c'est le dispositif — une anomalie fabriquée la déclenche, une journée normale
ne la déclenche pas.

Code de sortie : 0 si rien à signaler, 1 si une chute est détectée **ou si le
flux s'est interrompu** — une absence de données n'est pas une absence de chute.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

import psycopg2

from .alerte import (
    HEURE_MINIMALE,
    SEUIL_POURCENT,
    collecter,
    dernier_jour_connu,
    flux_interrompu,
)


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Alerte sur chute des ventes.")
    analyseur.add_argument("--jours", type=int, default=10, help="jours affichés")
    analyseur.add_argument(
        "--heure", type=int, help="heure à considérer, pour rejouer une situation"
    )
    arguments = analyseur.parse_args(argv)

    try:
        verdicts = collecter(arguments.jours, arguments.heure)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire les compteurs ({premiere})", file=sys.stderr)
        return 1

    if not verdicts:
        print("\nAucun achat enregistré.")
        print("Lancer le générateur, puis : python -m compteurs\n")
        return 0

    print("\nAchats comparés au même jour de la semaine\n")
    print(f"  {'Jour':<13}{'Achats':>8}{'Habituel':>11}{'Niveau':>10}{'Comparé à':>12}")
    for verdict in verdicts:
        # `is not None`, et non la valeur elle-même : un niveau de 0,0 % est
        # faux en Python. Le tiret s'affichait donc exactement dans le cas le
        # plus grave — zéro achat, alerte déclenchée.
        niveau = f"{verdict.niveau_pourcent} %" if verdict.niveau_pourcent is not None else "—"
        habituel = "—" if verdict.habituels is None else str(verdict.habituels)
        marque = "!" if verdict.alerte else " "
        print(
            f" {marque}{str(verdict.jour):<13}{verdict.achats:>8}"
            f"{habituel:>11}{niveau:>10}"
            f"{verdict.jours_compares:>9} jour(s)"
        )

    # Un flux arrêté ne produit aucune ligne, donc aucune chute : sans ce
    # contrôle, l'alerte se tait précisément quand la chaîne est tombée.
    retard = flux_interrompu(dernier_jour_connu(verdicts), datetime.now(UTC).date())
    if retard is not None:
        print(
            f"\n  ! AUCUN FLUX DEPUIS {retard} JOUR(S) — dernier jour connu "
            f"{dernier_jour_connu(verdicts)}. Les verdicts ci-dessus portent sur "
            f"des données périmées. Vérifier le consommateur d'événements "
            f"(python -m compteurs) et le retard du flux.\n"
        )
        return 1

    # Toute journée sous le seuil est signalée, pas seulement la plus récente :
    # une chute passée inaperçue reste une chute, et le jour le plus récent est
    # souvent celui qui a le moins d'historique.
    signalees = [verdict for verdict in verdicts if verdict.alerte]
    courant = verdicts[0]

    print("\nCe qui mérite d'être regardé\n")
    for verdict in signalees:
        print(f"  ! {verdict.message()}")
    if not signalees:
        print(f"  {courant.message()}")
        if courant.comparable:
            print(
                f"\n  Le seuil est à {SEUIL_POURCENT:.0f} % de l'activité habituelle, "
                f"et l'alerte ne se prononce pas avant {HEURE_MINIMALE} h."
            )
    elif not courant.alerte:
        print(f"\n  Jour le plus récent — {courant.message()}")
    print("\n  Trafic simulé — l'alerte démontre le dispositif, elle ne détecte rien de réel.\n")

    return 1 if signalees else 0


if __name__ == "__main__":
    sys.exit(main())
