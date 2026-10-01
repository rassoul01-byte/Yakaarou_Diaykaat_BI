import pandas as pd

from transformation.deduplication import dedupliquer


def test_deux_lignes_strictement_identiques_n_en_laissent_qu_une():
    lignes = pd.DataFrame({"zip": ["01001", "01001", "01002"], "ville": ["a", "a", "b"]})

    conservees, supprimees = dedupliquer(lignes)

    assert len(conservees) == 2
    assert supprimees == 1


def test_sans_doublon_rien_n_est_supprime():
    lignes = pd.DataFrame({"zip": ["01001", "01002"], "ville": ["a", "b"]})

    conservees, supprimees = dedupliquer(lignes)

    assert len(conservees) == 2
    assert supprimees == 0


def test_une_ligne_qui_ne_differe_que_d_une_colonne_est_conservee():
    lignes = pd.DataFrame({"zip": ["01001", "01001"], "ville": ["a", "b"]})

    _, supprimees = dedupliquer(lignes)

    assert supprimees == 0


def test_deduplication_sur_cle_metier():
    lignes = pd.DataFrame({"id": [1, 1, 2], "note": [5, 3, 4]})

    conservees, supprimees = dedupliquer(lignes, cles=["id"])

    assert supprimees == 1
    assert conservees["note"].tolist() == [5, 4]  # la première occurrence est gardée


def test_relancer_la_deduplication_donne_le_meme_resultat_et_un_compteur_a_zero():
    lignes = pd.DataFrame({"zip": ["01001", "01001", "01002"], "ville": ["a", "a", "b"]})
    premiere, _ = dedupliquer(lignes)

    seconde, supprimees = dedupliquer(premiere)

    assert seconde.equals(premiere)
    assert supprimees == 0
