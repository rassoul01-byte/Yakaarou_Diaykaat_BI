"""Tests de l'indexation du catalogue.

Aucun test n'a besoin d'Elasticsearch : le client est remplacé par un faux qui
enregistre ce qu'on lui envoie. Ce qui est vérifié ici, c'est la forme des
documents et la mécanique d'envoi — le reste relève du test d'intégration.
"""

import pytest

from recherche.indexation import creer_index, indexer
from recherche.schema import CHAMPS, INDEX, PARAMETRES, construire_document, identifiant


class FauxIndices:
    def __init__(self, existe=False):
        self._existe = existe
        self.cree = None
        self.supprime = False
        self.rafraichi = False

    def exists(self, index):
        return self._existe

    def create(self, index, settings, mappings):
        self.cree = {"index": index, "settings": settings, "mappings": mappings}
        self._existe = True

    def delete(self, index):
        self.supprime = True
        self._existe = False

    def refresh(self, index):
        self.rafraichi = True


class FauxClient:
    """Enregistre les lots reçus, et peut simuler une erreur d'indexation."""

    def __init__(self, existe=False, erreurs=0):
        self.indices = FauxIndices(existe)
        self.lots = []
        self._erreurs = erreurs

    def bulk(self, operations, refresh=False):
        self.lots.append(operations)
        if not self._erreurs:
            return {"errors": False, "items": []}
        items = [{"index": {"error": {"reason": "champ invalide"}}} for _ in range(self._erreurs)]
        return {"errors": True, "items": items}


def fiche(index_ligne=1, jeu="train", description="Une description", code=1560, langue="fr"):
    return {
        "jeu": jeu,
        "index_ligne": index_ligne,
        "productid": f"p{index_ligne}",
        "designation": "Lampe de bureau articulée",
        "description": description,
        "prdtypecode": code,
        "langue": langue,
    }


# --- La forme du document ---------------------------------------------------


def test_le_document_reprend_les_champs_du_contrat():
    document = construire_document(fiche())

    assert set(document) == {
        "product_id",
        "index_ligne",
        "jeu",
        "designation",
        "description",
        "categorie_code",
        "langue",
        "a_description",
    }


def test_une_fiche_sans_description_est_signalee():
    # 35 % du catalogue : un moteur de recherche doit pouvoir le savoir.
    document = construire_document(fiche(description=""))

    assert document["a_description"] is False
    assert document["description"] is None


def test_une_description_faite_d_espaces_compte_comme_absente():
    assert construire_document(fiche(description="   "))["a_description"] is False


def test_une_fiche_avec_description_est_signalee():
    assert construire_document(fiche())["a_description"] is True


def test_le_code_categorie_est_du_texte_pour_servir_de_filtre():
    # keyword côté Elasticsearch : on filtre dessus, on ne calcule pas avec.
    assert construire_document(fiche(code=1560))["categorie_code"] == "1560"


def test_une_fiche_sans_categorie_n_invente_pas_de_code():
    assert construire_document(fiche(code=None))["categorie_code"] is None


# --- L'identifiant, et donc l'idempotence -----------------------------------


def test_l_identifiant_vient_de_la_cle_primaire_de_la_table():
    # Et non de product_id, dont rien ne garantit l'unicité.
    assert identifiant("train", 42) == "train:42"


def test_deux_jeux_ne_se_recouvrent_pas():
    assert identifiant("train", 1) != identifiant("test", 1)


# --- La structure de l'index ------------------------------------------------


def test_l_analyseur_retire_les_accents():
    # C'est ce qui fait qu'« eclairage » trouve « éclairage ».
    filtres = PARAMETRES["analysis"]["analyzer"]["francais"]["filter"]

    assert "asciifolding" in filtres
    assert "lowercase" in filtres


def test_les_champs_de_recherche_sont_analyses_et_les_filtres_ne_le_sont_pas():
    proprietes = CHAMPS["properties"]

    assert proprietes["designation"]["type"] == "text"
    assert proprietes["categorie_code"]["type"] == "keyword"
    assert proprietes["product_id"]["type"] == "keyword"


# --- La création de l'index -------------------------------------------------


def test_l_index_est_cree_s_il_n_existe_pas():
    client = FauxClient(existe=False)

    assert creer_index(client) is True
    assert client.indices.cree["index"] == INDEX


def test_un_index_existant_n_est_pas_recree_sans_demande():
    client = FauxClient(existe=True)

    assert creer_index(client) is False
    assert client.indices.supprime is False


def test_recreer_supprime_l_index_existant():
    client = FauxClient(existe=True)

    assert creer_index(client, recreer=True) is True
    assert client.indices.supprime is True


# --- L'envoi par lots -------------------------------------------------------


def test_chaque_fiche_donne_une_instruction_et_un_document():
    client = FauxClient(existe=True)

    envoyes, erreurs = indexer(client, [fiche(1), fiche(2)], taille_lot=10)

    assert (envoyes, erreurs) == (2, 0)
    assert len(client.lots[0]) == 4  # deux paires instruction + document


def test_les_fiches_sont_decoupees_en_lots():
    client = FauxClient(existe=True)

    envoyes, _ = indexer(client, [fiche(i) for i in range(5)], taille_lot=2)

    assert envoyes == 5
    assert len(client.lots) == 3  # 2 + 2 + 1


def test_les_erreurs_d_indexation_sont_comptees_et_non_ignorees():
    client = FauxClient(existe=True, erreurs=2)

    _, erreurs = indexer(client, [fiche(1), fiche(2)], taille_lot=10)

    assert erreurs == 2


def test_l_index_est_rafraichi_pour_que_les_documents_soient_cherchables():
    client = FauxClient(existe=True)

    indexer(client, [fiche(1)], taille_lot=10)

    assert client.indices.rafraichi is True


def test_un_catalogue_vide_n_envoie_rien():
    client = FauxClient(existe=True)

    envoyes, erreurs = indexer(client, [], taille_lot=10)

    assert (envoyes, erreurs) == (0, 0)
    assert client.lots == []


# --- Le bilan ---------------------------------------------------------------


def test_un_index_conforme_quand_tout_est_indexe():
    from recherche.indexation import Resultat

    assert Resultat(fiches_en_base=10, documents_indexes=10, erreurs=0).conforme is True


@pytest.mark.parametrize(
    "indexes, erreurs", [(9, 0), (10, 1)], ids=["document manquant", "erreur d'indexation"]
)
def test_un_index_non_conforme_est_detecte(indexes, erreurs):
    from recherche.indexation import Resultat

    assert Resultat(fiches_en_base=10, documents_indexes=indexes, erreurs=erreurs).conforme is False
