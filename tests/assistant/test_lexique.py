"""Le lexique métier : il ajoute des mots, il n'en retire jamais."""

from assistant.lexique import LEXIQUE, etendre
from assistant.passages import charger
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
