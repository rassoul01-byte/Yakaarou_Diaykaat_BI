"""Tests du segment à retenir.

Ce qui est vérifié : le classement par score, le calcul du gain par rapport au
hasard, et le fait qu'un segment plus large retient plus de monde mais se
trompe davantage. C'est ce compromis que le Product Owner doit arbitrer.
"""

import numpy as np
import pandas as pd
import pytest

from prediction.segment import TAILLES, paliers, segment


def jeu(total=1000, positifs=100, parfait=True):
    """Un jeu où les positifs ont les meilleurs scores, ou des scores au hasard."""
    verite = np.array([1] * positifs + [0] * (total - positifs))
    if parfait:
        scores = np.linspace(1.0, 0.0, total)
    else:
        scores = np.random.default_rng(0).uniform(size=total)
    return scores, verite


# --- Le classement ----------------------------------------------------------


def test_un_modele_parfait_trouve_tous_les_positifs_dans_le_premier_segment():
    scores, verite = jeu(total=1000, positifs=100)

    resultat = paliers(scores, verite, tailles=(100,))[0]

    assert resultat.positifs == 100
    assert resultat.part_pourcent == 100.0


def test_un_segment_plus_large_retient_plus_de_positifs():
    scores, verite = jeu()

    petits, grands = paliers(scores, verite, tailles=(100, 500))

    assert grands.positifs >= petits.positifs


def test_un_segment_plus_large_se_trompe_davantage():
    # C'est tout le compromis : viser large rate moins de monde, mais
    # sollicite plus de gens pour rien.
    scores, verite = jeu()

    petits, grands = paliers(scores, verite, tailles=(100, 500))

    assert grands.faux_positifs > petits.faux_positifs


# --- Le gain par rapport au hasard ------------------------------------------


def test_le_gain_compare_au_taux_de_base():
    # 10 % de positifs dans le jeu, 100 % dans le segment : dix fois mieux.
    scores, verite = jeu(total=1000, positifs=100)

    resultat = paliers(scores, verite, tailles=(100,))[0]

    assert resultat.base_pourcent == 10.0
    assert resultat.gain == 10.0


def test_un_modele_qui_classe_au_hasard_ne_gagne_rien():
    scores, verite = jeu(total=2000, positifs=200, parfait=False)

    resultat = paliers(scores, verite, tailles=(500,))[0]

    # Autour de 1 : le modèle ne fait ni mieux ni pire que le hasard.
    assert 0.5 < resultat.gain < 1.8


def test_le_gain_vaut_zero_sans_aucun_positif():
    resultat = paliers(np.linspace(1, 0, 100), np.zeros(100), tailles=(10,))[0]

    assert resultat.gain == 0.0


# --- Les bornes -------------------------------------------------------------


def test_une_taille_plus_grande_que_le_jeu_est_ignoree():
    scores, verite = jeu(total=300, positifs=30)

    resultat = paliers(scores, verite, tailles=(100, 1000))

    assert [palier.taille for palier in resultat] == [100]


def test_les_tailles_proposees_vont_de_cent_a_cinq_mille():
    # Un responsable raisonne en nombre de personnes à contacter.
    assert TAILLES[0] == 100
    assert TAILLES[-1] == 5000


def test_le_score_minimum_du_segment_est_rapporte():
    scores, verite = jeu(total=1000, positifs=100)

    resultat = paliers(scores, verite, tailles=(100,))[0]

    assert 0.89 < resultat.score_minimum < 0.91


# --- La liste produite ------------------------------------------------------


def test_la_liste_contient_les_meilleurs_scores():
    donnees = pd.DataFrame({"customer_unique_id": [f"c{i}" for i in range(10)]})
    scores = np.array([0.1, 0.9, 0.5, 0.95, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8])

    liste = segment(donnees, scores, taille=3)

    assert list(liste["customer_unique_id"]) == ["c3", "c1", "c9"]


def test_la_liste_est_classee_du_plus_au_moins_probable():
    donnees = pd.DataFrame({"customer_unique_id": [f"c{i}" for i in range(10)]})
    scores = np.linspace(0, 1, 10)

    liste = segment(donnees, scores, taille=5)

    assert list(liste["score"]) == sorted(liste["score"], reverse=True)


@pytest.mark.parametrize("taille", [1, 5, 10])
def test_la_liste_a_la_taille_demandee(taille):
    donnees = pd.DataFrame({"customer_unique_id": [f"c{i}" for i in range(10)]})

    assert len(segment(donnees, np.linspace(0, 1, 10), taille)) == taille
