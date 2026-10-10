"""Tests de l'intervalle de Wilson et de l'agrégation par sommes."""

from __future__ import annotations

import pytest

from prediction.statistiques import gain_avec_intervalle, pooler, wilson


def test_wilson_exemple_ndege_penda():
    """L'exemple de référence : 8 succès sur 100, base = 413 / 26190."""
    bas, haut = wilson(8, 100)
    base = 413 / 26190

    assert bas == pytest.approx(0.0411, abs=1e-3)
    assert haut == pytest.approx(0.1500, abs=1e-3)

    gain_bas = bas / base
    gain_haut = haut / base
    assert gain_bas == pytest.approx(2.61, abs=0.05)
    assert gain_haut == pytest.approx(9.51, abs=0.05)


def test_wilson_cas_limites():
    assert wilson(0, 100) == pytest.approx((0.0, 0.0370), abs=1e-3)
    assert wilson(100, 100) == pytest.approx((0.9630, 1.0), abs=1e-3)


def test_wilson_entrees_invalides():
    with pytest.raises(ValueError):
        wilson(5, 3)
    with pytest.raises(ValueError):
        wilson(-1, 10)
    assert wilson(0, 0) == (0.0, 0.0)


def test_gain_avec_intervalle():
    base = 413 / 26190
    central, bas, haut = gain_avec_intervalle(8, 100, base)
    assert central == pytest.approx(8 / 100 / base, abs=0.01)
    assert bas < central < haut


def test_pooler_somme_les_fenetres():
    fenetres = [
        {"trouves": 8, "cibles": 100},
        {"trouves": 13, "cibles": 250},
        {"trouves": 17, "cibles": 500},
    ]
    resultat = pooler(fenetres)
    assert resultat["trouves"] == 38
    assert resultat["cibles"] == 850
    assert resultat["precision"] == pytest.approx(38 / 850, abs=1e-6)


def test_pooler_intervalle_plus_serre_que_fenetre_unique():
    """L'intervalle poolé doit être plus étroit qu'une fenêtre seule."""
    fenetres = [
        {"trouves": 8, "cibles": 100},
        {"trouves": 8, "cibles": 100},
        {"trouves": 8, "cibles": 100},
    ]
    resultat = pooler(fenetres)
    bas_pool, haut_pool = resultat["wilson"]
    bas_seul, haut_seul = wilson(8, 100)

    largeur_pool = haut_pool - bas_pool
    largeur_seul = haut_seul - bas_seul
    assert largeur_pool < largeur_seul
