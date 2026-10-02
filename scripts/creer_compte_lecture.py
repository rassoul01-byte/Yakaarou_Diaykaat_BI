"""Crée le compte de lecture seule utilisé par Power BI.

Le mot de passe est lu dans l'environnement — POWERBI_MOTDEPASSE — et n'est
jamais écrit dans le dépôt. Le script est relançable : un compte existant voit
son mot de passe mis à jour et ses droits réaffirmés.

Usage :
    docker compose exec app python scripts/creer_compte_lecture.py
    docker compose exec app python scripts/creer_compte_lecture.py --verifier

Code de sortie : 0 si le compte est en place et ne peut rien écrire, 1 sinon.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import psycopg2  # noqa: E402

from common.acces import (  # noqa: E402
    creer_compte_lecture,
    identifiants,
    verifier_lecture_seule,
)


def main(argv: list[str] | None = None) -> int:
    import argparse

    analyseur = argparse.ArgumentParser(description="Compte de lecture pour Power BI.")
    analyseur.add_argument(
        "--verifier", action="store_true", help="vérifier sans créer ni modifier"
    )
    arguments = analyseur.parse_args(argv)

    try:
        utilisateur, motdepasse = identifiants()
    except ValueError as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    try:
        if not arguments.verifier:
            resultat = creer_compte_lecture(utilisateur, motdepasse)
            print(f"Compte {resultat.utilisateur} : {'créé' if resultat.cree else 'mis à jour'}")
            print(f"  lecture accordée sur : {', '.join(resultat.schemas_accordes) or 'aucun'}")
            if resultat.schemas_absents:
                print(f"  schémas pas encore créés : {', '.join(resultat.schemas_absents)}")
                print("  relancer ce script après la migration qui les crée.")

        anomalies = verifier_lecture_seule(utilisateur, motdepasse)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : {premiere}", file=sys.stderr)
        return 1

    if anomalies:
        print("\nLe compte n'est PAS en lecture seule :", file=sys.stderr)
        for anomalie in anomalies:
            print(f"  - {anomalie}", file=sys.stderr)
        return 1

    print("\nVérifié : le compte lit et ne peut rien écrire.")
    print("Connexion Power BI : hôte localhost, port de votre .env, base dataflow360.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
