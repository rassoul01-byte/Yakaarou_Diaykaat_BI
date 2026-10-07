import pytest

from documentaire.garde_fous import motif_de_refus


@pytest.mark.parametrize(
    ("question", "motif"),
    [
        ("Où en est ma commande numéro 4521 ?", "commande_precise"),
        ("Mon colis CMD-98765 n'est pas arrivé", "commande_precise"),
        ("Je veux un remboursement personnalisé de 50 euros", "montant"),
        ("Remboursez-moi 10 000 FCFA", "montant"),
        ("Je veux récupérer € 20", "montant"),
    ],
)
def test_refuse_commande_precise_et_montant(question, motif):
    assert motif_de_refus(question) == motif


@pytest.mark.parametrize(
    "question",
    [
        "Paiement en 3 fois possible ?",
        "Combien de jours j'ai pour renvoyer un article ?",
        "Où trouver mon numéro de commande ?",
        "Quand vais-je recevoir mon colis ?",
        "Livraison en 48 heures possible ?",
        "Bonjour",
    ],
)
def test_laisse_passer_les_questions_de_la_faq(question):
    assert motif_de_refus(question) is None
