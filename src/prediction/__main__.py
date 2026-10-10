"""Entraîne le modèle de ré-achat et publie son évaluation.

Usage :
    docker compose exec app python -m prediction
    docker compose exec app python -m prediction --fabrique   # jeu de 200 lignes

Protocole : docs/contrats/modele.md

Code de sortie : 0 si le modèle est évalué, 1 si les données sont inutilisables.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2

from .classement import lignes_rapport
from .donnees import DATE_ENTRAINEMENT, DATE_EVALUATION, lire, separer, verifier_absence_de_fuite
from .modele import entrainer, evaluer, influences


def afficher(evaluation, variables_influentes) -> None:
    print("\nÉvaluation du modèle de ré-achat\n")
    print(f"  Entraîné sur la période précédant le {DATE_ENTRAINEMENT}")
    print(f"  Évalué sur la période précédant le {DATE_EVALUATION}")
    print("  Découpage temporel — jamais aléatoire\n")

    print(f"  Clients évalués        : {evaluation.total}")
    print(f"  Dont revenus           : {evaluation.positifs_reels} ({evaluation.part_positifs} %)")
    print(f"\n  Rappel                 : {evaluation.rappel}")
    print(f"  Précision              : {evaluation.precision}")
    print(f"  F1                     : {evaluation.f1}")

    print("\n  Matrice de confusion\n")
    print(f"    {'':<22}{'prédit : revient':>20}{'prédit : ne revient pas':>26}")
    print(f"    {'revenu':<22}{evaluation.vrais_positifs:>20}{evaluation.faux_negatifs:>26}")
    print(f"    {'non revenu':<22}{evaluation.faux_positifs:>20}{evaluation.vrais_negatifs:>26}")

    print("\n  Comparaison aux règles en une ligne\n")
    for nom, mesures in evaluation.naives.items():
        print(
            f"    {nom:<26}rappel {mesures['rappel']:<8}"
            f"précision {mesures['precision']:<8}F1 {mesures['f1']}"
        )
    print(
        f"    {'le modèle':<26}rappel {evaluation.rappel:<8}"
        f"précision {evaluation.precision:<8}F1 {evaluation.f1}"
    )

    verdict = (
        "Le modèle fait mieux que les règles naïves."
        if evaluation.mieux_que_naif
        else "Le modèle ne fait PAS mieux qu'une règle en une ligne (F1) — c'est un "
        "résultat, et il se publie tel quel."
    )
    print(f"\n  {verdict}")

    if evaluation.classement:
        print()
        for ligne in lignes_rapport(evaluation.classement):
            print(ligne)

    print("\n  Variables les plus influentes\n")
    for nom, coefficient in variables_influentes:
        sens = "augmente" if coefficient > 0 else "diminue"
        print(f"    {nom:<26}{coefficient:>8}   {sens} la chance de retour")
    print(
        "\n  Les variables sont liées entre elles (le montant total est le montant"
        "\n  moyen multiplié par le nombre de commandes) : les coefficients ne se"
        "\n  lisent pas un à un."
    )

    print(
        "\n  L'exactitude n'est pas calculée : un modèle qui répondrait « ne revient"
        "\n  pas » à tout le monde en afficherait plus de 95 % et serait inutile.\n"
    )


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python -m prediction", description=__doc__.split("\n")[0]
    )
    analyseur.add_argument(
        "--fabrique", action="store_true", help="jeu fabriqué, résultats sans valeur"
    )
    arguments = analyseur.parse_args(argv)

    try:
        donnees = lire(arguments.fabrique)
        verifier_absence_de_fuite(donnees)
        x_entrainement, y_entrainement, x_evaluation, y_evaluation = separer(donnees)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire l'historique client ({premiere})", file=sys.stderr)
        print("Vérifier que la vue dwh.v_historique_client existe.", file=sys.stderr)
        return 1
    except ValueError as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    modele = entrainer(x_entrainement, y_entrainement)
    if arguments.fabrique:
        print("\n  JEU FABRIQUÉ — ces résultats ne veulent rien dire.")
    afficher(evaluer(modele, x_evaluation, y_evaluation), influences(modele, x_evaluation))
    return 0


if __name__ == "__main__":
    sys.exit(main())
