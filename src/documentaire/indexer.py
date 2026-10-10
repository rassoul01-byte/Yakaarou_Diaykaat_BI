"""Indexe la foire aux questions dans Elasticsearch, un passage par ligne.

Contrat : docs/contrats/passages.md
Usage :
    docker compose exec app python -m documentaire.verifier
    docker compose exec app python -m documentaire.indexer
    docker compose exec app python -m documentaire.indexer --recreer

Idempotent : l'identifiant du document est l'`id` du passage, donc réindexer
écrase au lieu de dupliquer, et les passages retirés du fichier sont supprimés
de l'index.

Code de sortie : 0 si l'index contient exactement les passages du fichier,
1 sinon.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from elasticsearch.exceptions import ApiError, TransportError

from recherche.client import adresse, connexion

from .modele import vectoriser as vectoriser_par_defaut
from .schema import CHAMPS as MAPPING
from .schema import INDEX, PARAMETRES, construire_document, texte_a_vectoriser
from .verifier import CHAMPS as CHAMPS_FAQ
from .verifier import FICHIER_PAR_DEFAUT, charger


class FichierInvalide(Exception):
    """La foire aux questions ne peut pas être indexée telle quelle."""

    def __init__(self, problemes: list[str]):
        super().__init__("; ".join(problemes))
        self.problemes = problemes


@dataclass(frozen=True)
class Resultat:
    passages_en_fichier: int
    envoyes: int
    erreurs: int
    supprimes: int
    dans_index: int

    @property
    def conforme(self) -> bool:
        """L'index contient exactement ce que le fichier contient."""
        return self.erreurs == 0 and self.dans_index == self.passages_en_fichier


def lire_passages(chemin: Path) -> list[dict]:
    """Lit le fichier et refuse tout ce qui empêcherait une indexation sûre.

    Le contrôle complet reste celui de `documentaire.verifier` ; ici on ne
    vérifie que le strict nécessaire : lecture, champs présents, identifiants
    uniques.
    """
    lignes, problemes = charger(chemin)
    passages: list[dict] = []
    vus: set[str] = set()

    for numero, entree in lignes:
        if not isinstance(entree, dict):
            problemes.append(f"ligne {numero} : l'entrée n'est pas un objet JSON")
            continue
        manquants = [
            champ
            for champ in CHAMPS_FAQ
            if not isinstance(entree.get(champ), str) or not entree[champ].strip()
        ]
        if manquants:
            problemes.append(f"ligne {numero} : champ(s) absent(s) ou vide(s) : {manquants}")
            continue
        if entree["id"] in vus:
            problemes.append(f"ligne {numero} : identifiant « {entree['id']} » en double")
            continue
        vus.add(entree["id"])
        passages.append(entree)

    if problemes:
        raise FichierInvalide(problemes)
    if not passages:
        raise FichierInvalide(["le fichier ne contient aucun passage"])
    return passages


def creer_index(client, recreer: bool = False) -> bool:
    """Crée l'index s'il n'existe pas. Renvoie True s'il a été créé."""
    if recreer and client.indices.exists(index=INDEX):
        client.indices.delete(index=INDEX)
    if client.indices.exists(index=INDEX):
        return False
    client.indices.create(index=INDEX, settings=PARAMETRES, mappings=MAPPING)
    return True


def _compter_erreurs(reponse: dict) -> int:
    if not reponse.get("errors"):
        return 0
    return sum(1 for item in reponse.get("items", []) if item.get("index", {}).get("error"))


def indexer(
    client,
    passages: list[dict],
    vectoriser: Callable[[list[str]], list[list[float]]] = vectoriser_par_defaut,
) -> Resultat:
    """Indexe les passages, puis retire de l'index ceux qui ne sont plus dans le fichier."""
    vecteurs = vectoriser([texte_a_vectoriser(entree) for entree in passages])

    operations: list[dict] = []
    for entree, vecteur in zip(passages, vecteurs, strict=True):
        operations.append({"index": {"_index": INDEX, "_id": entree["id"]}})
        operations.append(construire_document(entree, vecteur))
    reponse = client.bulk(operations=operations, refresh=True)
    erreurs = _compter_erreurs(reponse)

    identifiants = [entree["id"] for entree in passages]
    supprimes = client.delete_by_query(
        index=INDEX,
        query={"bool": {"must_not": [{"ids": {"values": identifiants}}]}},
        refresh=True,
    ).get("deleted", 0)

    return Resultat(
        passages_en_fichier=len(passages),
        envoyes=len(passages),
        erreurs=erreurs,
        supprimes=supprimes,
        dans_index=client.count(index=INDEX)["count"],
    )


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Indexation de la foire aux questions.")
    analyseur.add_argument("--fichier", type=Path, default=FICHIER_PAR_DEFAUT)
    analyseur.add_argument(
        "--recreer",
        action="store_true",
        help="supprimer l'index avant de le reconstruire (obligatoire si la structure change)",
    )
    arguments = analyseur.parse_args(argv)

    try:
        passages = lire_passages(arguments.fichier)
    except FileNotFoundError:
        print(f"ERREUR : fichier introuvable : {arguments.fichier}", file=sys.stderr)
        return 1
    except FichierInvalide as erreur:
        print("ERREUR : la foire aux questions n'est pas indexable :", file=sys.stderr)
        for probleme in erreur.problemes:
            print(f"  - {probleme}", file=sys.stderr)
        print("Lancer : python -m documentaire.verifier", file=sys.stderr)
        return 1

    try:
        client = connexion()
        cree = creer_index(client, recreer=arguments.recreer)
        print(f"Index {INDEX} : {'créé' if cree else 'déjà présent'} sur {adresse()}")
        resultat = indexer(client, passages)
    except (ApiError, TransportError) as erreur:
        print(
            f"ERREUR : Elasticsearch n'a pas répondu ({erreur.__class__.__name__})",
            file=sys.stderr,
        )
        print(f"Vérifier que le service tourne : {adresse()}", file=sys.stderr)
        return 1

    print(f"  passages dans le fichier : {resultat.passages_en_fichier}")
    print(f"  passages envoyés         : {resultat.envoyes}")
    print(f"  passages supprimés       : {resultat.supprimes}")
    print(f"  erreurs                  : {resultat.erreurs}")
    print(f"  passages dans l'index    : {resultat.dans_index}")

    if not resultat.conforme:
        print("\nL'index ne reflète pas le fichier.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
