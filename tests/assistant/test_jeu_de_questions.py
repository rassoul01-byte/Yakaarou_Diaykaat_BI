"""Le jeu de questions : bien formé, et l'assistant ne commet pas les deux fautes graves dessus.

Le jeu est gelé (voir jeu_de_questions.gel.json) : 52 questions provisoires écrites par
l'auteur de l'assistant, plus 10 questions pièges écrites par Seydina (origine « seydina »).
Toute modification du jeu invalide l'empreinte SHA256 et doit être suivie d'un nouveau gel.
"""
from collections import Counter

from assistant.evaluer import evaluer, lire_jeu, synthese
from assistant.passages import charger
from assistant.retrouveur import RetrouveurDepannage

CATEGORIES = {
    "couverte", "prix", "commande_precise", "remboursement_personnalise", "hors_sujet", "proche", "piege",
}  # fmt: skip


def test_le_jeu_est_bien_forme():
    jeu = lire_jeu()
    ids_passages = {p.id for p in charger()}
    assert len({q["id"] for q in jeu}) == len(jeu)
    for q in jeu:
        assert q["categorie"] in CATEGORIES and q["attendu"] in ("reponse", "refus")
        assert q["origine"]
        if q["attendu"] == "reponse":
            # Un piège peut recevoir une réponse (le bon passage existe),
            # la distinction réponse/refus est portée par `attendu`.
            assert q["categorie"] in ("couverte", "piege") and q["passage"] in ids_passages
        else:
            assert q["passage"] is None and q["categorie"] != "couverte"


def test_chaque_categorie_de_refus_est_representee():
    compte = Counter(q["categorie"] for q in lire_jeu())
    assert compte["couverte"] >= 20
    for categorie in CATEGORIES - {"couverte"}:
        assert compte[categorie] >= 3, categorie


def test_le_jeu_contient_des_questions_generales_voisines_des_regles_de_refus():
    """Ce qui NE doit PAS être refusé à tort : « Combien coûte un retour ? », « délai de remboursement »."""
    questions = {q["question"] for q in lire_jeu() if q["attendu"] == "reponse"}
    assert {"Combien coûte un retour ?", "Quel est le délai de remboursement ?"} <= questions


def test_aucune_reponse_a_tort_et_aucun_mauvais_passage_sur_le_jeu_provisoire():
    s = synthese(evaluer(RetrouveurDepannage.depuis_faq(), lire_jeu()))
    assert s["réponse à tort"] == 0
    assert s["mauvais passage"] == 0


def test_toutes_les_reponses_du_jeu_sont_ancrees():
    s = synthese(evaluer(RetrouveurDepannage.depuis_faq(), lire_jeu()))
    assert s["ancrées"] == s["questions"]
