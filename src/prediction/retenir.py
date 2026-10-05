"""Segment à retenir : quel seuil, pour quel coût.

Usage :
    docker compose exec app python -m prediction.retenir
    docker compose exec app python -m prediction.retenir --taille 500
    docker compose exec app python -m prediction.retenir --taille 500 --export segment.csv

Code de sortie : 0 si le segment est produit, 1 si les données manquent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

from .donnees import CLE, VARIABLES, charger, separer, verifier_absence_de_fuite
from .modele import entrainer
from .segment import paliers, segment


def afficher_paliers(liste) -> None:
    if not liste:
        print("\nPas assez de clients pour proposer un segment.\n")
        return

    base = liste[0].base_pourcent
    print("\nCe que contient chaque taille de segment\n")
    print(
        f"  {'Clients retenus':>16}{'Reviendront':>13}{'Part':>9}"
        f"{'Gain':>8}{'À contacter pour rien':>24}"
    )
    for palier in liste:
        print(
            f"  {palier.taille:>16}{palier.positifs:>13}{palier.part_pourcent:>8} %"
            f"{palier.gain:>7}×{palier.faux_positifs:>24}"
        )

    print(f"\n  Au hasard, on trouverait {base} % de clients qui reviennent.")
    print("  Le gain dit combien de fois le modèle fait mieux que ce hasard.")


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Segment à retenir.")
    analyseur.add_argument("--taille", type=int, help="produire la liste de cette taille")
    analyseur.add_argument("--export", type=Path, help="écrire la liste dans un fichier CSV")
    arguments = analyseur.parse_args(argv)

    try:
        donnees = charger()
        verifier_absence_de_fuite(donnees)
        x_entrainement, y_entrainement, x_evaluation, y_evaluation = separer(donnees)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire l'historique client ({premiere})", file=sys.stderr)
        return 1
    except ValueError as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    modele = entrainer(x_entrainement, y_entrainement)
    # La probabilité d'appartenir à la classe « revient », et non la décision
    # binaire : c'est elle qui permet de classer et donc de choisir un seuil.
    scores = modele.predict_proba(x_evaluation)[:, 1]

    afficher_paliers(paliers(scores, y_evaluation.to_numpy()))

    if arguments.taille:
        evaluation = donnees[donnees.index.isin(x_evaluation.index)][[CLE, *VARIABLES]].assign(
            a_rachete=y_evaluation
        )
        liste = segment(evaluation, scores, arguments.taille)
        retrouves = int(liste["a_rachete"].sum())

        print(f"\nSegment de {arguments.taille} clients\n")
        print(f"  Reviendront réellement : {retrouves}")
        print(f"  Contactés pour rien    : {arguments.taille - retrouves}")
        print(f"  Score le plus bas retenu : {liste['score'].min():.4f}")

        if arguments.export:
            liste.to_csv(arguments.export, index=False)
            print(f"\n  Liste écrite dans {arguments.export}")

    print(
        "\n  Ce segment n'est PAS une liste de clients perdus : c'est une liste de"
        "\n  clients à qui il vaudrait peut-être la peine de s'adresser.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
