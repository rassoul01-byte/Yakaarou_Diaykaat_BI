"""Le lexique métier : il ajoute des mots, il n'en retire jamais."""

import pytest

from assistant.lexique import LEXIQUE, etendre
from assistant.passages import charger
from assistant.retrouveur import RetrouveurDepannage
from assistant.texte import normaliser


def test_un_mot_du_client_attire_le_mot_de_la_foire_aux_questions():
    assert "commande" in etendre("Où est mon colis ?").split()
    assert "remboursement" in etendre("Je veux mon argent").split()


def test_la_question_d_origine_est_conservee():
    assert etendre("Mon colis est cassé").startswith("mon colis est casse")


def test_une_question_sans_entree_du_lexique_n_est_pas_modifiee():
    assert etendre("Bonjour tout le monde") == "bonjour tout le monde"


def test_les_mots_ne_sont_pas_ajoutes_en_double():
    ajouts = etendre("colis colis envoi").split()[3:]  # après les trois mots d'origine
    assert ajouts and len(ajouts) == len(set(ajouts))


def test_cles_et_valeurs_sont_normalisees():
    for cle, valeurs in LEXIQUE.items():
        assert cle == normaliser(cle), cle
        assert all(v == normaliser(v) for v in valeurs), cle


def test_chaque_entree_n_ajoute_que_des_mots_presents_dans_la_foire_aux_questions():
    """Règle du module : on ne fabrique pas de vocabulaire que les passages n'ont pas."""
    vocabulaire = {m for p in charger() for m in normaliser(f"{p.question} {p.reponse}").split()}
    absents = {
        (cle, v) for cle, valeurs in LEXIQUE.items() for v in valeurs if v not in vocabulaire
    }
    assert not absents, absents


# ----------------------------------------- les confusions que le lexique dénoue
#
# Ces quatre questions désignaient le passage VOISIN : le mot le plus fort de la
# question appartenait à un autre passage que celui qui y répond. Chacune est ici
# pour qu'un futur ajout au lexique ne les renvoie pas dans le mur.


@pytest.mark.parametrize(
    ("question", "attendu", "voisin_trompeur"),
    [
        ("Combien coûte un retour ?", "ret-04", "ret-01"),
        ("Qui supporte le coût de renvoi du colis ?", "ret-04", "ret-01"),
        ("Quand l'argent sort-il de mon compte ?", "pai-08", "ret-05"),
        ("Comment obtenir un nouveau mot de passe ?", "cpt-02", "cpt-01"),
    ],
)
def test_le_bon_passage_passe_devant_son_voisin(question, attendu, voisin_trompeur):
    trouves = RetrouveurDepannage.depuis_faq().retrouver(question, k=3)
    assert trouves, question
    assert trouves[0].id == attendu, (
        f"« {question} » devrait désigner {attendu}, pas {trouves[0].id} "
        f"(voisin trompeur connu : {voisin_trompeur})"
    )
