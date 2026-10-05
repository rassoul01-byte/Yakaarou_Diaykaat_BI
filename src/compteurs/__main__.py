"""Compteurs du jour : consommer le bus, puis afficher l'activité.

Usage :
    docker compose exec app python -m compteurs                 # lire puis afficher
    docker compose exec app python -m compteurs --sans-lire     # afficher seulement
    docker compose exec app python -m compteurs --duree 60      # attendre 60 s sans message

⚠️ Trafic simulé : ces chiffres décrivent le générateur, pas des visiteurs
réels. Et ils ne contiennent aucun montant — un événement d'achat n'en porte
pas.

Code de sortie : 0 si les compteurs sont lisibles, 1 sinon.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2
from confluent_kafka import KafkaException

from .consommateur import alimenter, consommer_le_bus
from .lecture import collecter

MENTION = "Trafic simulé — ces chiffres décrivent le générateur, pas des visiteurs réels."


def afficher(donnees: dict) -> None:
    activite = donnees["activite"]
    print("\nActivité par jour\n")
    if not activite:
        print("  Aucun événement enregistré.")
        print("  Lancer le générateur, puis : python -m compteurs\n")
        return

    print(
        f"  {'Jour':<13}{'Sessions':>10}{'Pages':>9}{'Recherches':>12}"
        f"{'Paniers':>9}{'Achats':>8}{'Clients':>9}"
    )
    for ligne in activite:
        print(
            f"  {ligne['jour']:<13}{ligne['sessions']:>10}{ligne['pages_vues']:>9}"
            f"{ligne['recherches']:>12}{ligne['ajouts_panier']:>9}"
            f"{ligne['achats']:>8}{ligne['clients_identifies']:>9}"
        )

    print("\nTaux de conversion\n")
    print(f"  {'Jour':<13}{'Sessions':>10}{'Avec achat':>12}{'Taux':>9}")
    for ligne in donnees["conversion"]:
        taux = ligne["taux_conversion_pourcent"]
        print(
            f"  {ligne['jour']:<13}{ligne['sessions']:>10}"
            f"{ligne['sessions_avec_achat']:>12}{float(taux):>8.2f} %"
        )

    if donnees["requetes"]:
        print("\nCe que les visiteurs cherchent\n")
        print(f"  {'Requête':<40}{'Occurrences':>12}{'Sessions':>10}")
        for ligne in donnees["requetes"]:
            print(f"  {ligne['requete'][:39]:<40}{ligne['occurrences']:>12}{ligne['sessions']:>10}")

    print(f"\n  {MENTION}\n")


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Compteurs du jour.")
    analyseur.add_argument("--sans-lire", action="store_true", help="ne pas consommer le bus")
    analyseur.add_argument("--duree", type=float, default=15.0, help="attente sans message")
    analyseur.add_argument("--jours", type=int, default=7)
    analyseur.add_argument("--top", type=int, default=15, help="requêtes affichées")
    arguments = analyseur.parse_args(argv)

    try:
        if not arguments.sans_lire:
            bilan = alimenter(consommer_le_bus(arguments.duree))
            print(
                f"\nBus lu : {bilan.lus} message(s), {bilan.retenus} retenu(s), "
                f"{bilan.ignores} illisible(s), "
                f"{bilan.lus - bilan.ignores - bilan.retenus} déjà connu(s)."
            )
        donnees = collecter(arguments.jours, arguments.top)
    except KafkaException as erreur:
        print(f"ERREUR : le bus n'a pas répondu ({erreur})", file=sys.stderr)
        return 1
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire les compteurs ({premiere})", file=sys.stderr)
        return 1

    afficher(donnees)
    return 0


if __name__ == "__main__":
    sys.exit(main())
