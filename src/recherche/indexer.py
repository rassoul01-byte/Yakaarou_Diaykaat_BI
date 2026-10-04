"""Indexe le catalogue produits dans Elasticsearch.

Usage :
    docker compose exec app python -m recherche.indexer
    docker compose exec app python -m recherche.indexer --recreer

Code de sortie : 0 si l'index contient exactement les fiches de la zone
intermédiaire, 1 sinon. C'est ce code que la tâche Airflow lit.
"""

from __future__ import annotations

import argparse
import sys

from elasticsearch import ElasticsearchWarning  # noqa: F401  (import vérifié au démarrage)
from elasticsearch.exceptions import ApiError, TransportError

from .client import adresse, connexion
from .indexation import compter_en_base, creer_index, indexer, lire_catalogue
from .schema import INDEX


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Indexation du catalogue produits.")
    analyseur.add_argument(
        "--recreer",
        action="store_true",
        help="supprimer l'index avant de le reconstruire (obligatoire si la structure change)",
    )
    analyseur.add_argument("--taille-lot", type=int, default=1000)
    arguments = analyseur.parse_args(argv)

    try:
        client = connexion()
        cree = creer_index(client, recreer=arguments.recreer)
        print(f"Index {INDEX} : {'créé' if cree else 'déjà présent'} sur {adresse()}")

        fiches_en_base = compter_en_base()
        if fiches_en_base == 0:
            print("\nAucune fiche dans staging.rakuten_produits.", file=sys.stderr)
            print("Lancer d'abord : python -m transformation --source rakuten", file=sys.stderr)
            return 1

        envoyes, erreurs = indexer(client, lire_catalogue(), arguments.taille_lot)

    except (ApiError, TransportError) as erreur:
        print(
            f"ERREUR : Elasticsearch n'a pas répondu ({erreur.__class__.__name__})", file=sys.stderr
        )
        print(f"Vérifier que le service tourne : {adresse()}", file=sys.stderr)
        return 1

    print(f"  fiches en zone intermédiaire : {fiches_en_base}")
    print(f"  documents envoyés            : {envoyes}")
    print(f"  erreurs                      : {erreurs}")

    if erreurs or envoyes != fiches_en_base:
        print("\nL'index ne reflète pas la zone intermédiaire.", file=sys.stderr)
        return 1

    print("\nIndex conforme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
