"""Recherche de passages dans la foire aux questions.

Contrat : docs/contrats/passages.md
Usage :
    docker compose exec app python -m documentaire.rechercher "ma question"
    docker compose exec app python -m documentaire.rechercher "ma question" -k 5

Affiche le JSON du contrat (§7). La recherche ne rédige jamais de réponse : elle
renvoie des passages triés, et c'est à l'assistant de décider s'ils suffisent.

Le `score` est celui d'Elasticsearch pour la similarité cosinus, soit
(1 + cosinus) / 2 : entre 0 et 1, plus il est haut plus le passage est proche.

Code de sortie : 0 si la recherche a eu lieu (même sans résultat), 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

from elasticsearch.exceptions import ApiError, TransportError

from recherche.client import adresse, connexion

from .modele import vectoriser as vectoriser_par_defaut
from .schema import INDEX

K_PAR_DEFAUT = 3
CANDIDATS_MIN = 50  # la foire aux questions tient en quelques dizaines de passages


def construire_requete(vecteur: list[float], k: int) -> dict:
    """Corps de la recherche. Ne contacte pas Elasticsearch."""
    return {
        "knn": {
            "field": "vecteur",
            "query_vector": vecteur,
            "k": k,
            "num_candidates": max(CANDIDATS_MIN, k),
        },
        "size": k,
        "source_excludes": ["vecteur", "texte"],
    }


def rechercher(
    client,
    question: str,
    k: int = K_PAR_DEFAUT,
    vectoriser: Callable[[list[str]], list[list[float]]] = vectoriser_par_defaut,
) -> dict:
    """Renvoie les k passages les plus proches de la question, avec leur source."""
    if not question.strip():
        raise ValueError("la question est vide")
    if k < 1:
        raise ValueError("k doit valoir au moins 1")

    vecteur = vectoriser([question])[0]
    reponse = client.search(index=INDEX, **construire_requete(vecteur, k))

    resultats = [
        {
            "id": hit["_source"]["id"],
            "theme": hit["_source"]["theme"],
            "question": hit["_source"]["question"],
            "reponse": hit["_source"]["reponse"],
            "source": hit["_source"]["source"],
            "score": round(float(hit["_score"]), 4),
        }
        for hit in reponse["hits"]["hits"]
    ]
    return {"question_posee": question, "resultats": resultats}


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Recherche de passages.")
    analyseur.add_argument("question", help="la question, en texte libre")
    analyseur.add_argument("-k", type=int, default=K_PAR_DEFAUT, help="nombre de passages")
    arguments = analyseur.parse_args(argv)

    try:
        resultat = rechercher(connexion(), arguments.question, arguments.k)
    except ValueError as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    except (ApiError, TransportError) as erreur:
        print(
            f"ERREUR : Elasticsearch n'a pas répondu ({erreur.__class__.__name__})",
            file=sys.stderr,
        )
        print(f"Vérifier que le service tourne : {adresse()}", file=sys.stderr)
        return 1

    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
