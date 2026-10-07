"""Indexation et recherche des passages — sans Elasticsearch ni modèle réel.

Contrat : docs/contrats/passages.md
"""

from __future__ import annotations

import copy
import json

import pytest

from documentaire.indexer import FichierInvalide, indexer, lire_passages
from documentaire.rechercher import construire_requete, rechercher
from documentaire.schema import DIMENSION, INDEX, construire_document, texte_a_vectoriser

PASSAGES = [
    {
        "id": "liv-01",
        "theme": "livraison",
        "question": "Combien de temps faut-il pour recevoir ma commande ?",
        "reponse": "Le délai dépend de la région.",
        "source": "donnee:fait_commande.delai_livraison_jours",
        "maj": "2026-10-05",
    },
    {
        "id": "ret-01",
        "theme": "retours",
        "question": "Quel est le délai pour retourner un produit ?",
        "reponse": "Le délai de retour est de 14 jours à compter de la réception.",
        "source": "politique:retours",
        "maj": "2026-10-05",
    },
    {
        "id": "cpt-01",
        "theme": "compte",
        "question": "Comment réinitialiser mon mot de passe ?",
        "reponse": "Un lien valable 1 heure est envoyé par e-mail.",
        "source": "politique:compte",
        "maj": "2026-10-05",
    },
]


def faux_vectoriser(textes):
    """Vecteurs fictifs, déterministes : la longueur du texte et une constante."""
    return [[float(len(texte)), 1.0] for texte in textes]


class FausseGestionIndex:
    def __init__(self):
        self.existe = False

    def exists(self, index):
        return self.existe

    def create(self, index, settings=None, mappings=None):
        self.existe = True

    def delete(self, index):
        self.existe = False


class FauxClient:
    """Garde les documents par identifiant, comme Elasticsearch le fait."""

    def __init__(self):
        self.documents: dict[str, dict] = {}
        self.indices = FausseGestionIndex()
        self.recherches: list[dict] = []
        self.hits: list[dict] = []

    def bulk(self, operations, refresh=False):
        for action, document in zip(operations[::2], operations[1::2], strict=True):
            assert action["index"]["_index"] == INDEX
            self.documents[action["index"]["_id"]] = copy.deepcopy(document)
        return {"errors": False, "items": []}

    def delete_by_query(self, index, query, refresh=False):
        gardes = set(query["bool"]["must_not"][0]["ids"]["values"])
        retires = [identifiant for identifiant in self.documents if identifiant not in gardes]
        for identifiant in retires:
            del self.documents[identifiant]
        return {"deleted": len(retires)}

    def count(self, index):
        return {"count": len(self.documents)}

    def search(self, index, **corps):
        self.recherches.append({"index": index, **corps})
        return {"hits": {"hits": self.hits}}


def ecrire_faq(chemin, passages):
    chemin.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in passages) + "\n", encoding="utf-8"
    )
    return chemin


# --- le passage ------------------------------------------------------------


def test_le_texte_vectorise_contient_la_question_et_la_reponse():
    texte = texte_a_vectoriser(PASSAGES[0])

    assert PASSAGES[0]["question"] in texte
    assert PASSAGES[0]["reponse"] in texte


def test_un_document_garde_sa_source_et_son_vecteur():
    document = construire_document(PASSAGES[1], [0.5, 0.25])

    assert document["id"] == "ret-01"
    assert document["source"] == "politique:retours"
    assert document["vecteur"] == [0.5, 0.25]


def test_le_vecteur_a_la_dimension_du_modele_choisi():
    assert DIMENSION == 384


# --- l'indexation ----------------------------------------------------------


def test_l_identifiant_du_document_est_l_id_du_passage():
    client = FauxClient()

    indexer(client, PASSAGES, faux_vectoriser)

    assert set(client.documents) == {"liv-01", "ret-01", "cpt-01"}


def test_la_reindexation_est_idempotente():
    client = FauxClient()

    premier = indexer(client, PASSAGES, faux_vectoriser)
    etat_apres_premier = copy.deepcopy(client.documents)
    second = indexer(client, PASSAGES, faux_vectoriser)

    assert client.documents == etat_apres_premier
    assert premier.dans_index == second.dans_index == len(PASSAGES)
    assert second.supprimes == 0
    assert second.conforme is True


def test_un_passage_retire_du_fichier_disparait_de_l_index():
    client = FauxClient()
    indexer(client, PASSAGES, faux_vectoriser)

    bilan = indexer(client, PASSAGES[:2], faux_vectoriser)

    assert set(client.documents) == {"liv-01", "ret-01"}
    assert bilan.supprimes == 1
    assert bilan.conforme is True


def test_un_passage_modifie_remplace_l_ancien():
    client = FauxClient()
    indexer(client, PASSAGES, faux_vectoriser)
    modifie = [dict(PASSAGES[0], reponse="Nouvelle réponse.")] + PASSAGES[1:]

    indexer(client, modifie, faux_vectoriser)

    assert client.documents["liv-01"]["reponse"] == "Nouvelle réponse."
    assert len(client.documents) == len(PASSAGES)


# --- la lecture du fichier -------------------------------------------------


def test_un_fichier_conforme_est_lu_en_entier(tmp_path):
    chemin = ecrire_faq(tmp_path / "faq.jsonl", PASSAGES)

    assert [p["id"] for p in lire_passages(chemin)] == ["liv-01", "ret-01", "cpt-01"]


def test_un_identifiant_en_double_est_refuse(tmp_path):
    chemin = ecrire_faq(tmp_path / "faq.jsonl", PASSAGES + [PASSAGES[0]])

    with pytest.raises(FichierInvalide) as erreur:
        lire_passages(chemin)

    assert "en double" in str(erreur.value)


def test_un_champ_vide_est_refuse(tmp_path):
    chemin = ecrire_faq(tmp_path / "faq.jsonl", [dict(PASSAGES[0], source="")])

    with pytest.raises(FichierInvalide):
        lire_passages(chemin)


def test_une_ligne_qui_n_est_pas_du_json_est_refusee(tmp_path):
    chemin = tmp_path / "faq.jsonl"
    chemin.write_text("pas du json\n", encoding="utf-8")

    with pytest.raises(FichierInvalide):
        lire_passages(chemin)


def test_un_fichier_vide_est_refuse(tmp_path):
    chemin = tmp_path / "faq.jsonl"
    chemin.write_text("", encoding="utf-8")

    with pytest.raises(FichierInvalide):
        lire_passages(chemin)


# --- la recherche ----------------------------------------------------------


def un_hit(passage, score):
    return {"_score": score, "_source": {**passage, "maj": passage["maj"]}}


def test_la_recherche_interroge_les_vecteurs_sans_les_renvoyer():
    corps = construire_requete([0.1, 0.2], k=3)

    assert corps["knn"]["field"] == "vecteur"
    assert corps["knn"]["k"] == 3
    assert corps["knn"]["num_candidates"] >= 3
    assert corps["size"] == 3
    assert "vecteur" in corps["source_excludes"]


def test_chaque_resultat_remonte_avec_sa_source_et_son_score():
    client = FauxClient()
    client.hits = [un_hit(PASSAGES[0], 0.8213456), un_hit(PASSAGES[1], 0.61)]

    sortie = rechercher(client, "Quand vais-je recevoir mon colis ?", 2, faux_vectoriser)

    assert sortie["question_posee"] == "Quand vais-je recevoir mon colis ?"
    premier = sortie["resultats"][0]
    assert premier["id"] == "liv-01"
    assert premier["source"] == "donnee:fait_commande.delai_livraison_jours"
    assert premier["score"] == 0.8213
    assert "vecteur" not in premier


def test_une_liste_vide_est_un_resultat_valide():
    client = FauxClient()

    sortie = rechercher(client, "Quel est le prix de ce téléviseur ?", 3, faux_vectoriser)

    assert sortie["resultats"] == []


def test_la_recherche_vectorise_la_question_posee():
    client = FauxClient()

    rechercher(client, "abc", 3, faux_vectoriser)

    assert client.recherches[0]["knn"]["query_vector"] == [3.0, 1.0]
    assert client.recherches[0]["index"] == INDEX


def test_une_question_vide_est_refusee():
    with pytest.raises(ValueError):
        rechercher(FauxClient(), "   ", 3, faux_vectoriser)
