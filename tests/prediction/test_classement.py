import numpy as np
import pytest

from prediction.classement import lignes_rapport, mesures_classement, retours_captes


def _jeu(n=1000, revenus=20):
    y = np.zeros(n, dtype=int)
    y[:revenus] = 1
    return y


def test_classement_parfait():
    y = _jeu()
    m = mesures_classement(y, y.astype(float))
    assert m["precision_moyenne"] == pytest.approx(1.0)
    assert m["capture_part"] == pytest.approx(1.0)
    assert m["taux_base"] == pytest.approx(0.02)


def test_classement_inverse_est_pire_que_le_hasard():
    y = _jeu()
    m = mesures_classement(y, 1 - y.astype(float))
    assert m["precision_moyenne"] < m["taux_base"] * 1.1
    assert m["captes_part"] == 0


def test_scores_sans_information_restent_pres_du_taux_de_base():
    rng = np.random.default_rng(0)
    y = _jeu(n=20000, revenus=400)
    m = mesures_classement(y, rng.random(len(y)))
    assert m["gain_precision_moyenne"] < 1.5
    assert abs(m["capture_part"] - m["capture_hasard"]) < 0.05


def test_volume_egal_avec_la_regle():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 1])
    scores = np.array([0.9, 0.1, 0.8, 0.7, 0.2, 0.2, 0.2, 0.2, 0.2, 0.6])
    regle = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    m = mesures_classement(y, scores, regle=regle)
    assert m["volume_regle"] == 1
    assert m["captes_regle"] == 1
    assert m["captes_modele_meme_volume"] == 1  # le client au score 0,9
    assert m["rappel_regle"] == pytest.approx(1 / 3)


def test_regle_vide_ne_plante_pas():
    y = _jeu(100, 5)
    m = mesures_classement(y, y.astype(float), regle=np.zeros(100))
    assert m["volume_regle"] == 0
    assert m["rappel_modele_meme_volume"] == 0


def test_egalites_sont_deterministes():
    y = _jeu(100, 5)
    scores = np.full(100, 0.3)
    assert retours_captes(y, scores, 10) == retours_captes(y, scores, 10)
    assert mesures_classement(y, scores) == mesures_classement(y, scores)


def test_ne_depend_pas_de_l_ordre_des_clients_a_scores_distincts():
    y = _jeu(200, 10)
    scores = np.linspace(1, 0, 200)
    p = np.arange(200)[::-1]
    a = mesures_classement(y, scores)
    b = mesures_classement(y[p], scores[p])
    assert a["precision_moyenne"] == pytest.approx(b["precision_moyenne"])
    assert a["captes_part"] == b["captes_part"]


@pytest.mark.parametrize(
    "y,s",
    [
        (np.zeros(10), np.arange(10)),  # aucun revenu
        (np.array([1, 0]), np.array([0.1])),  # longueurs différentes
        (np.array([]), np.array([])),  # vide
    ],
)
def test_entrees_invalides(y, s):
    with pytest.raises(ValueError):
        mesures_classement(y, s)


def test_part_invalide():
    with pytest.raises(ValueError):
        mesures_classement(_jeu(), np.arange(1000), part=0)


def test_rapport_contient_le_hasard_et_le_volume_egal():
    y = _jeu()
    texte = "\n".join(lignes_rapport(mesures_classement(y, y.astype(float), regle=y)))
    assert "hasard" in texte
    assert "À volume égal" in texte
