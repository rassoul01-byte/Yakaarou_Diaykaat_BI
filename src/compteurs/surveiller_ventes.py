"""Alerte sur chute des ventes.

Usage :
    docker compose exec app python -m compteurs.surveiller_ventes
    docker compose exec app python -m compteurs.surveiller_ventes --heure 14
    docker compose exec app python -m compteurs.surveiller_ventes --jours 14

⚠️ Trafic simulé : cette alerte ne détecte rien de réel. Ce qu'elle démontre,
c'est le dispositif — une anomalie fabriquée la déclenche, une journée normale
ne la déclenche pas.

Code de sortie : 0 si rien à signaler, 1 si une chute est détectée.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2

from .alerte import HEURE_MINIMALE, SEUIL_POURCENT, collecter


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
        niveau = f"{verdict.niveau_pourcent} %" if verdict.niveau_pourcent else "—"
        marque = "!" if verdict.alerte else " "
        print(
            f" {marque}{str(verdict.jour):<13}{verdict.achats:>8}"
            f"{str(verdict.habituels or '—'):>11}{niveau:>10}"
            f"{verdict.jours_compares:>9} jour(s)"
        )

    courant = verdicts[0]
    print("\nCe qui mérite d'être regardé\n")
    print(f"  {'! ' if courant.alerte else ''}{courant.message()}")
    if not courant.alerte and courant.comparable:
        print(
            f"\n  Le seuil est à {SEUIL_POURCENT:.0f} % de l'activité habituelle, "
            f"et l'alerte ne se prononce pas avant {HEURE_MINIMALE} h."
        )
    print("\n  Trafic simulé — l'alerte démontre le dispositif, elle ne détecte rien de réel.\n")

    return 1 if courant.alerte else 0


if __name__ == "__main__":
    sys.exit(main())
