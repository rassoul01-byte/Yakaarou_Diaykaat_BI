"""Les garde-fous : chaque catégorie de refus, et la frontière avec les questions générales.

Le plus important n'est pas ce qui est refusé, mais ce qui NE l'est PAS : un refus à tort
fait perdre un client, comme une invention le trompe.
"""

import pytest

from assistant import garde_fous as g
from assistant.passages import Passage


@pytest.mark.parametrize(
    ("question", "motif"),
    [
        ("Quel est le prix de la chaise de bureau ?", g.PRIX),
        ("Combien coûte un canapé ?", g.PRIX),
        ("Quel est le tarif de cet article ?", g.PRIX),
        ("Où est ma commande numéro 8f3a2c ?", g.COMMANDE_PRECISE),
        ("Mon colis 4521 n'est toujours pas arrivé", g.COMMANDE_PRECISE),
        ("Pouvez-vous vérifier le statut de la commande 123456 ?", g.COMMANDE_PRECISE),
        ("Je veux être remboursé de 50 euros pour ma commande", g.REMBOURSEMENT_PERSONNALISE),
        ("Rembourse-moi s'il te plaît", g.REMBOURSEMENT_PERSONNALISE),
        ("Je veux que vous me remboursiez 30 € aujourd'hui", g.REMBOURSEMENT_PERSONNALISE),
        ("", g.QUESTION_INVALIDE),
        ("   ", g.QUESTION_INVALIDE),
        ("?", g.QUESTION_INVALIDE),
        ("a" * 501, g.QUESTION_INVALIDE),
    ],
)
def test_ce_que_la_base_ne_contiendra_jamais_est_refuse_avant_la_recherche(question, motif):
    assert g.filtre_avant(question) == motif


@pytest.mark.parametrize(
    "question",
    [
        "Quel est le délai de remboursement ?",
        "Sous combien de temps suis-je remboursé après un retour ?",
        "Combien coûte un retour ?",
        "Le prix de la livraison, c'est combien ?",
        "La livraison est-elle payante ?",
        "Comment suivre ma commande ?",
        "Où retrouver le numéro de ma commande ?",
        "Mon colis arrive endommagé, que faire ?",
        "Puis-je payer en 3 fois ?",
        "Le retour est possible pendant 14 jours ?",
        "Quels moyens de paiement acceptez-vous ?",
        "Depuis 2017 je n'ai plus reçu de mail de confirmation",
    ],
)
def test_une_question_generale_n_est_jamais_refusee_par_les_regles(question):
    """La frontière « général / personnel » : dans le doute, on laisse passer à la recherche."""
    assert g.filtre_avant(question) is None


def test_une_question_generale_avec_un_identifiant_devient_personnelle():
    assert (
        g.filtre_avant("Quel est le délai de remboursement pour ma commande 55555 ?")
        == g.COMMANDE_PRECISE
    )


# ------------------------------------------------------------- la décision B


def passage(id_: str, score: float) -> Passage:
    return Passage(
        id_, "retours", f"Question {id_} ?", f"Réponse {id_}.", "politique:retours", score
    )


SEUILS = g.Seuils(reponse=0.5, suggestion=0.3, marge=0.1)


def test_aucun_passage_est_un_refus_sans_suggestion():
    decision = g.decider([], SEUILS)
    assert (
        decision.retenu is None and decision.motif == g.AUCUN_PASSAGE and not decision.suggestions
    )


def test_un_passage_net_est_retenu():
    decision = g.decider([passage("a", 0.8), passage("b", 0.3)], SEUILS)
    assert decision.retenu.id == "a" and decision.motif is None


def test_un_seul_passage_assez_proche_est_retenu():
    assert g.decider([passage("a", 0.6)], SEUILS).retenu.id == "a"


def test_deux_passages_proches_l_un_de_l_autre_font_hesiter_au_lieu_de_deviner():
    decision = g.decider([passage("a", 0.62), passage("b", 0.58)], SEUILS)
    assert decision.retenu is None and decision.motif == g.INCERTAIN
    assert [p.id for p in decision.suggestions] == ["a", "b"]


def test_un_score_moyen_propose_sans_affirmer():
    decision = g.decider([passage("a", 0.4), passage("b", 0.35), passage("c", 0.1)], SEUILS)
    assert decision.motif == g.INCERTAIN
    assert [p.id for p in decision.suggestions] == ["a", "b"]  # c est sous le seuil de suggestion


def test_les_suggestions_sont_limitees_a_trois():
    passages = [passage(c, 0.45 - i * 0.01) for i, c in enumerate("abcde")]
    assert len(g.decider(passages, SEUILS).suggestions) == 3


def test_un_score_trop_bas_est_hors_base():
    decision = g.decider([passage("a", 0.1)], SEUILS)
    assert decision.motif == g.HORS_BASE and not decision.suggestions


def test_la_limite_du_seuil_est_incluse():
    assert g.decider([passage("a", 0.5)], SEUILS).retenu is not None
    assert g.decider([passage("a", 0.3)], SEUILS).motif == g.INCERTAIN


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(reponse=0.2, suggestion=0.3, marge=0.1),
        dict(reponse=1.2, suggestion=0.3, marge=0.1),
        dict(reponse=0.5, suggestion=0.3, marge=-1),
    ],
)
def test_des_seuils_incoherents_sont_refuses(kwargs):
    with pytest.raises(ValueError):
        g.Seuils(**kwargs)
