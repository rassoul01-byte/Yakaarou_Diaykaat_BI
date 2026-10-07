"""La recherche de passages : le même contrat pour toute réalisation (passages.md, §7)."""

import pytest

from assistant.garde_fous import Seuils
from assistant.passages import Passage, charger
from assistant.retrouveur import (
    ReponseContratInvalide,
    RetrouveurDepannage,
    RetrouveurExterne,
    depuis_contrat,
)

EXEMPLE_DU_CONTRAT = {
    "question_posee": "Quand vais-je recevoir mon colis ?",
    "resultats": [
        {
            "id": "liv-01",
            "theme": "livraison",
            "question": "Combien de temps faut-il pour recevoir ma commande ?",
            "reponse": "Le délai dépend de la région.",
            "source": "donnee:fait_commande.delai_livraison_jours",
            "score": 0.82,
        }
    ],
}


@pytest.fixture(scope="module")
def depannage():
    return RetrouveurDepannage.depuis_faq()


# ------------------------- les propriétés que TOUTE recherche doit tenir


def test_les_passages_sont_tries_du_plus_au_moins_proche(depannage):
    scores = [p.score for p in depannage.retrouver("Comment suivre ma commande ?", k=5)]
    assert scores == sorted(scores, reverse=True)


def test_au_plus_k_passages_sont_rendus(depannage):
    assert len(depannage.retrouver("Comment suivre ma commande ?", k=2)) == 2
    assert len(depannage.retrouver("Comment suivre ma commande ?", k=1)) == 1


def test_les_scores_sont_entre_zero_et_un(depannage):
    for question in ("paiement", "retour d'un produit", "bonjour"):
        assert all(0 <= p.score <= 1 for p in depannage.retrouver(question, k=5))


def test_chaque_passage_rendu_est_un_vrai_passage_avec_sa_source(depannage):
    ids = {p.id for p in charger()}
    for p in depannage.retrouver("Comment demander un retour ?", k=5):
        assert p.id in ids and p.source


def test_une_question_vide_ne_ramene_rien(depannage):
    assert depannage.retrouver("", k=3) == []
    assert depannage.retrouver("???", k=3) == []


def test_la_recherche_ne_rend_jamais_un_texte_qui_n_est_pas_celui_du_passage(depannage):
    originaux = {p.id: p for p in charger()}
    for p in depannage.retrouver("Mon colis est arrivé cassé", k=5):
        assert (p.question, p.reponse) == (originaux[p.id].question, originaux[p.id].reponse)


# ------------------------- ce que la recherche de dépannage sait faire


@pytest.mark.parametrize(
    ("question", "attendu"),
    [
        ("Comment suivre ma commande ?", "liv-03"),
        ("Comment demander un retour ?", "ret-03"),
        ("Qu'est-ce qu'un boleto ?", "pai-02"),
        ("Comment supprimer mon compte ?", "cpt-06"),
    ],
)
def test_une_question_proche_de_la_foire_aux_questions_retrouve_son_passage(
    depannage, question, attendu
):
    assert depannage.retrouver(question, k=1)[0].id == attendu


def test_une_faute_de_frappe_est_rattrapee_par_les_lettres(depannage):
    assert "cpt-06" in [p.id for p in depannage.retrouver("Comment suprimer mon compte ?", k=3)]


def test_le_lexique_comble_un_ecart_de_vocabulaire(depannage):
    """« colis » n'est pas dans la question de liv-03 ; le lexique le relie à « commande »."""
    assert "liv-03" in [
        p.id for p in depannage.retrouver("Comment connaître l'avancement de mon colis ?", k=3)
    ]


# ------------------------- le contrat de Seydina (passages.md, §7)


def test_le_json_du_contrat_se_convertit_en_passages():
    passages = depuis_contrat(EXEMPLE_DU_CONTRAT)
    assert passages == [
        Passage(
            "liv-01",
            "livraison",
            "Combien de temps faut-il pour recevoir ma commande ?",
            "Le délai dépend de la région.",
            "donnee:fait_commande.delai_livraison_jours",
            0.82,
        )
    ]


def test_une_liste_vide_est_un_resultat_valide():
    assert depuis_contrat({"question_posee": "x", "resultats": []}) == []


@pytest.mark.parametrize(
    "reponse",
    [
        {},
        {"resultats": [{"id": "a"}]},  # champs manquants
        {"resultats": [{**EXEMPLE_DU_CONTRAT["resultats"][0], "score": 1.5}]},  # hors [0, 1]
        {"resultats": [{**EXEMPLE_DU_CONTRAT["resultats"][0], "score": "x"}]},
        {  # mal triés
            "resultats": [
                {**EXEMPLE_DU_CONTRAT["resultats"][0], "score": 0.2},
                {**EXEMPLE_DU_CONTRAT["resultats"][0], "id": "liv-02", "score": 0.9},
            ]
        },
    ],
)
def test_une_reponse_hors_contrat_est_refusee_plutot_que_devinee(reponse):
    with pytest.raises(ReponseContratInvalide):
        depuis_contrat(reponse)


def test_l_adaptateur_appelle_la_recherche_de_seydina_et_respecte_k():
    appels = []

    def recherche(question, k):
        appels.append((question, k))
        return EXEMPLE_DU_CONTRAT

    retrouveur = RetrouveurExterne(recherche, Seuils(0.9, 0.7, 0.05))
    assert [p.id for p in retrouveur.retrouver("Quand vais-je recevoir mon colis ?", k=3)] == [
        "liv-01"
    ]
    assert appels == [("Quand vais-je recevoir mon colis ?", 3)]
    assert retrouveur.nom == "documentaire"


def test_l_adaptateur_exige_des_seuils():
    """Contrat §8 : le seuil se mesure sur le jeu fixé, il n'a pas de valeur par défaut."""
    with pytest.raises(TypeError):
        RetrouveurExterne(lambda q, k: EXEMPLE_DU_CONTRAT)
