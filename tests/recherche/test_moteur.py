"""Tests du moteur de recherche (F4.2, F4.3).

Aucun test n'a besoin d'Elasticsearch : la requête se construit sans service,
et le client est remplacé par un faux qui enregistre ce qu'on lui envoie. Ce
qui se vérifie ici, c'est la FORME de la requête et la lecture de la réponse ;
la pertinence réelle (« chaise de bureu », le piège « lampe ») se vérifie dans
test_recherche_integration.py.
"""

import json

import pytest

from recherche.moteur import (
    CHAMPS_RECHERCHE,
    TAILLE_MAX,
    ErreurRecherche,
    construire_requete,
    rechercher,
    rechercher_plusieurs,
)
from recherche.schema import INDEX


def brut(total=1, hits=None, took=7):
    """Une réponse Elasticsearch minimale."""
    if hits is None:
        hits = [
            {
                "_score": 9.5,
                "_source": {
                    "product_id": "123",
                    "designation": "Chaise de bureau",
                    "categorie_code": "1560",
                },
            }
        ][:total]
    return {"took": took, "hits": {"total": {"value": total}, "hits": hits}}


class FauxClient:
    def __init__(self, reponse=None, reponses=None):
        self.reponse = reponse if reponse is not None else brut()
        self.reponses = reponses
        self.appels_search = []
        self.appels_msearch = []

    def search(self, **parametres):
        self.appels_search.append(parametres)
        return self.reponse

    def msearch(self, searches):
        self.appels_msearch.append(searches)
        nombre = len(searches) // 2
        return {"responses": self.reponses or [self.reponse] * nombre}


# ------------------------------------------------------------ la requête


@pytest.mark.parametrize("texte", ["", "   ", None])
def test_une_requete_vide_est_refusee(texte):
    with pytest.raises(ValueError, match="requête vide"):
        construire_requete(texte)


def test_la_designation_pese_plus_que_la_description():
    assert CHAMPS_RECHERCHE[0].startswith("designation^")
    assert "description" in CHAMPS_RECHERCHE


def test_la_recherche_porte_sur_la_designation_et_la_description():
    corps = construire_requete("chaise de bureu")
    multi = corps["query"]["bool"]["must"][0]["multi_match"]
    assert multi["query"] == "chaise de bureu"
    assert multi["fields"] == list(CHAMPS_RECHERCHE)


def test_la_tolerance_aux_fautes_est_dans_la_requete_pas_dans_l_index():
    multi = construire_requete("bureu")["query"]["bool"]["must"][0]["multi_match"]
    assert multi["fuzziness"] == "AUTO"
    # La première lettre doit être exacte : c'est ce qui sépare « lampe » de « rampe ».
    assert multi["prefix_length"] >= 1


def test_la_tolerance_peut_etre_desactivee_pour_comparer_les_reglages():
    multi = construire_requete("bureu", tolerance=None)["query"]["bool"]["must"][0]["multi_match"]
    assert "fuzziness" not in multi
    assert "prefix_length" not in multi


def test_les_correspondances_exactes_passent_devant():
    corps = construire_requete("lampe")["query"]["bool"]
    exacte = corps["should"][0]["multi_match"]
    assert exacte["boost"] > 1
    assert "fuzziness" not in exacte


def test_sans_filtre_la_liste_des_filtres_est_vide():
    assert construire_requete("lampe")["query"]["bool"]["filter"] == []


def test_filtre_par_categorie_et_par_langue():
    filtres = construire_requete("lampe", categorie="2060", langue="fr")["query"]["bool"]["filter"]
    assert {"term": {"categorie_code": "2060"}} in filtres
    assert {"term": {"langue": "fr"}} in filtres


def test_la_categorie_numerique_est_envoyee_comme_texte():
    # `categorie_code` est un keyword : un entier ne le trouverait pas.
    filtres = construire_requete("lampe", categorie=2060)["query"]["bool"]["filter"]
    assert filtres == [{"term": {"categorie_code": "2060"}}]


def test_aucune_clause_de_prix():
    """Décision F4.3 : le catalogue n'a aucun prix, on ne filtre donc pas dessus."""
    corps = json.dumps(construire_requete("lampe", categorie="2060", langue="fr"))
    for mot in ("prix", "price", "range"):
        assert mot not in corps


@pytest.mark.parametrize("taille", [-1, TAILLE_MAX + 1])
def test_une_taille_hors_limites_est_refusee(taille):
    with pytest.raises(ValueError, match="taille"):
        construire_requete("lampe", taille=taille)


def test_le_nombre_total_de_fiches_est_exact():
    # Sans cela, Elasticsearch plafonne le compte à 10 000 : « sans résultat »
    # n'est pas concerné, mais le total affiché le serait.
    assert construire_requete("lampe")["track_total_hits"] is True


# ----------------------------------------------------------- les réponses


def test_rechercher_interroge_l_index_catalogue_et_lit_les_resultats():
    client = FauxClient()
    reponse = rechercher(client, "chaise de bureu", categorie="1560")

    appel = client.appels_search[0]
    assert appel["index"] == INDEX
    assert appel["size"] == 10
    assert reponse.aboutit
    assert reponse.total == 1
    assert reponse.temps_serveur_ms == 7
    assert reponse.temps_total_ms >= 0
    premier = reponse.resultats[0]
    assert (premier.product_id, premier.categorie_code, premier.score) == ("123", "1560", 9.5)


def test_chaque_resultat_porte_les_champs_promis_par_le_contrat():
    """Contrat d'index §5 : product_id, designation, categorie_code, score."""
    resultat = rechercher(FauxClient(), "chaise").resultats[0]
    assert resultat.product_id and resultat.designation
    assert resultat.categorie_code
    assert isinstance(resultat.score, float)


def test_une_recherche_sans_fiche_n_aboutit_pas():
    reponse = rechercher(FauxClient(brut(total=0, hits=[])), "bcdfghjk")
    assert reponse.total == 0
    assert reponse.resultats == []
    assert not reponse.aboutit


def test_rechercher_plusieurs_garde_l_ordre_et_envoie_un_seul_lot():
    client = FauxClient(reponses=[brut(total=2), brut(total=0, hits=[])])
    reponses = rechercher_plusieurs(client, ["lampe", "bcdfghjk"], taille=0)

    assert len(client.appels_msearch) == 1
    envoi = client.appels_msearch[0]
    assert envoi[0] == {"index": INDEX}  # en-tête, puis corps, en alternance
    assert envoi[1]["size"] == 0
    assert [r.texte for r in reponses] == ["lampe", "bcdfghjk"]
    assert [r.aboutit for r in reponses] == [True, False]


def test_rechercher_plusieurs_sans_requete_n_appelle_pas_elasticsearch():
    client = FauxClient()
    assert rechercher_plusieurs(client, []) == []
    assert client.appels_msearch == []


def test_une_erreur_d_une_recherche_du_lot_est_signalee_pas_comptee_comme_zero():
    """Une requête en erreur n'est pas une requête « sans résultat »."""
    client = FauxClient(reponses=[brut(), {"error": {"type": "search_phase_execution_exception"}}])
    with pytest.raises(ErreurRecherche):
        rechercher_plusieurs(client, ["lampe", "chaise"])


def test_un_lot_dont_la_taille_ne_correspond_pas_est_refuse():
    client = FauxClient(reponses=[brut()])
    with pytest.raises(ErreurRecherche):
        rechercher_plusieurs(client, ["lampe", "chaise"])
