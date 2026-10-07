"""Pose une question à l'assistant.

    docker compose exec app python -m assistant "Comment suivre ma commande ?"
    docker compose exec app python -m assistant "Combien coûte un canapé ?" --json

Code de sortie : 0 si l'assistant répond OU refuse (un refus est une réponse correcte),
1 si une panne technique l'empêche de répondre (foire aux questions illisible, recherche
qui ne répond pas). Le journal est écrit par défaut ; --sans-journal l'évite.
"""

from __future__ import annotations

import argparse
import json
import sys

from .assistant import repondre
from .journal import JournalFichier
from .passages import ErreurCorpus
from .fabrique import creer_retrouveur
from .retrouveur import ReponseContratInvalide


def afficher(reponse) -> None:
    print(f"\n{reponse.reponse}\n")
    if reponse.passages:
        print("Sources :")
        for p in reponse.passages:
            print(f"  [{p.id}] {p.theme} — {p.question}  ({p.source})")
    if reponse.suggestions:
        print("Vouliez-vous dire :")
        for p in reponse.suggestions:
            print(f"  - {p.question}")
    print()


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Assistant client local.")
    analyseur.add_argument("question", nargs="+", help="la question du client")
    analyseur.add_argument("--json", action="store_true", help="sortie au format du contrat")
    analyseur.add_argument("-k", type=int, default=3, help="passages examinés")
    analyseur.add_argument("--sans-journal", action="store_true")
    arguments = analyseur.parse_args(argv)

    try:
        retrouveur = creer_retrouveur()
        journal = None if arguments.sans_journal else JournalFichier()
        reponse = repondre(" ".join(arguments.question), retrouveur, k=arguments.k, journal=journal)
    except (ConnectionError, OSError) as erreur:
        print(f"ERREUR : Elasticsearch ne répond pas ({erreur})", file=sys.stderr)
        return 1
    except ReponseContratInvalide as erreur:
        print(f"ERREUR : la recherche a répondu hors contrat ({erreur})", file=sys.stderr)
        return 1

    if arguments.json:
        print(json.dumps(reponse.en_dict(), ensure_ascii=False, indent=2))
    else:
        afficher(reponse)
    return 0


if __name__ == "__main__":
    sys.exit(main())
