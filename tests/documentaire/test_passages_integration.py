"""Indexation et recherche réelles : Elasticsearch démarré et modèle de vecteurs.

Lancement : docker compose exec app python -m pytest tests/documentaire -m integration

Le premier lancement télécharge le modèle (réseau nécessaire).
"""

from __future__ import annotations

import pytest
from elasticsearch.exceptions import ApiError, TransportError

from documentaire.indexer import creer_index, indexer, lire_passages
from documentaire.rechercher import rechercher
from documentaire.verifier import FICHIER_PAR_DEFAUT
from recherche.client import connexion

pytestmark = pytest.mark.integration

# Questions posées autrement que dans la foire aux questions -> passage attendu.
# À compléter avec des reformulations réelles, une par thème au minimum.
REFORMULATIONS = {
    "Quand vais-je recevoir mon colis ?": "liv-01",
}


@pytest.fixture(scope="module")
def client():
    client = connexion()
    try:
        client.info()
    except (ApiError, TransportError):
        pytest.skip("Elasticsearch ne répond pas")
    creer_index(client)
    indexer(client, lire_passages(FICHIER_PAR_DEFAUT))
    return client


def test_la_reindexation_reelle_est_idempotente(client):
    passages = lire_passages(FICHIER_PAR_DEFAUT)

    bilan = indexer(client, passages)

    assert bilan.conforme
    assert bilan.dans_index == len(passages)


# Cas connus où le modèle ne place pas le passage en premier : identifiant -> rang toléré.
# pai-08 (« Quand suis-je débité ? ») est très courte, le modèle la rapproche de liv-02.
CAS_CONNUS = {"pai-08": 5}


def test_chaque_question_de_la_faq_retrouve_son_propre_passage(client):
    for passage in lire_passages(FICHIER_PAR_DEFAUT):
        rang_tolere = CAS_CONNUS.get(passage["id"], 1)
        sortie = rechercher(client, passage["question"], k=rang_tolere)

        identifiants = [resultat["id"] for resultat in sortie["resultats"]]
        assert passage["id"] in identifiants, passage["id"]


@pytest.mark.parametrize(("question", "attendu"), REFORMULATIONS.items())
def test_une_question_reformulee_retrouve_le_bon_passage(client, question, attendu):
    sortie = rechercher(client, question, k=3)

    assert attendu in [resultat["id"] for resultat in sortie["resultats"]]


def test_chaque_passage_remonte_avec_sa_source(client):
    sortie = rechercher(client, "Comment retourner un produit ?", k=3)

    assert sortie["resultats"]
    assert all(resultat["source"] for resultat in sortie["resultats"])
