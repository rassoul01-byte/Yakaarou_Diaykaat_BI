"""Expose les scores de ré-achat, client par client.

Usage :
    docker compose exec app python -m prediction.scorer
    docker compose exec app python -m prediction.scorer --top 50
    docker compose exec app python -m prediction.scorer --csv scores.csv
    docker compose exec app python -m prediction.scorer --fabrique   # jeu de 200 lignes

Le modèle est entraîné sur la période d'entraînement, puis appliqué aux clients
tels qu'ils sont décrits à la date de référence demandée. Les clients sont
classés du plus au moins à risque de ne plus revenir.

Code de sortie : 0 si les scores sont produits, 1 si les données sont inutilisables.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd
import psycopg2

from .donnees import (
    CLE,
    DATE_ENTRAINEMENT,
    DATE_EVALUATION,
    VARIABLES,
    clients_a_scorer,
    lire,
    separer,
    verifier_absence_de_fuite,
)
from .modele import entrainer, probabilites_de_retour


def tableau_des_scores(
    donnees: pd.DataFrame,
    date_reference: date = DATE_EVALUATION,
    date_entrainement: date = DATE_ENTRAINEMENT,
) -> pd.DataFrame:
    """Un score par client, du plus au moins à risque.

    Le modèle n'apprend que sur la période d'entraînement : la réponse observée
    de la période scorée n'est jamais utilisée. Les ex æquo sont départagés par
    l'identifiant, pour que deux exécutions donnent le même tableau.
    """
    x_entrainement, y_entrainement, _, _ = separer(donnees, date_entrainement, date_reference)
    modele = entrainer(x_entrainement, y_entrainement)

    clients = clients_a_scorer(donnees, date_reference)
    proba = probabilites_de_retour(modele, clients[list(VARIABLES)])

    tableau = pd.DataFrame(
        {
            CLE: clients[CLE].to_numpy(),
            "proba_retour": proba.round(4),
            "risque_depart": (1 - proba).round(4),
        }
    )
    return tableau.sort_values(
        ["risque_depart", CLE], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)


def _date(texte: str) -> date:
    try:
        return date.fromisoformat(texte)
    except ValueError as erreur:
        raise argparse.ArgumentTypeError(
            f"date attendue au format AAAA-MM-JJ : {texte!r}"
        ) from erreur


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python -m prediction.scorer", description=__doc__.split("\n")[0]
    )
    analyseur.add_argument(
        "--date", type=_date, default=DATE_EVALUATION, help="date de référence à scorer"
    )
    analyseur.add_argument(
        "--top", type=int, default=20, help="nombre de clients affichés (défaut 20)"
    )
    analyseur.add_argument("--csv", help="écrit TOUS les scores dans ce fichier")
    analyseur.add_argument(
        "--fabrique", action="store_true", help="jeu fabriqué, résultats sans valeur"
    )
    arguments = analyseur.parse_args(argv)

    try:
        donnees = lire(arguments.fabrique)
        verifier_absence_de_fuite(donnees)
        tableau = tableau_des_scores(donnees, arguments.date)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire l'historique client ({premiere})", file=sys.stderr)
        print("Vérifier que la vue dwh.v_historique_client existe.", file=sys.stderr)
        return 1
    except ValueError as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    if arguments.fabrique:
        print("\n  JEU FABRIQUÉ — ces scores ne veulent rien dire.")
    print(f"\nScores de ré-achat au {arguments.date} — {len(tableau)} clients\n")
    print(tableau.head(arguments.top).to_string(index=False))

    if arguments.csv:
        tableau.to_csv(arguments.csv, index=False)
        print(f"\n  {len(tableau)} scores écrits dans {arguments.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
