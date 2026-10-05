"""Tests de la surveillance du retard du flux.

Le réglage est tout le sujet : un retard de mille messages peut être sain, un
retard de dix peut être inquiétant. Ce qui se surveille, c'est la **tendance**,
et ces tests décrivent exactement quand elle déclenche un signalement.
"""

import pytest

from supervision.flux import RELEVES_POUR_UNE_TENDANCE, Lecteur, anomalies


def lecteur(releves, groupe="compteurs-du-jour", sujet="navigation.evenements"):
    """Relevés du plus récent au plus ancien, comme les renvoie la vue."""
    return Lecteur(groupe=groupe, sujet=sujet, retard=releves[0], releves=tuple(releves))


# --- Quand un lecteur décroche ----------------------------------------------


def test_un_retard_qui_grandit_a_chaque_releve_signale_un_decrochage():
    assert lecteur([300, 200, 100]).decroche is True


def test_un_retard_stable_ne_signale_rien():
    # Un flux chargé mais suivi : le lecteur tient le rythme.
    assert lecteur([1000, 1000, 1000]).decroche is False


def test_un_retard_qui_se_resorbe_ne_signale_rien():
    assert lecteur([100, 200, 300]).decroche is False


def test_un_retard_eleve_mais_qui_baisse_ne_signale_rien():
    # Mille messages de retard, mais le lecteur rattrape : rien à faire.
    assert lecteur([1000, 2000, 3000]).decroche is False


def test_une_hausse_puis_une_baisse_ne_fait_pas_une_tendance():
    # Un à-coup de trafic n'est pas un décrochage.
    assert lecteur([250, 300, 100]).decroche is False


# --- Pas assez d'historique -------------------------------------------------


@pytest.mark.parametrize("releves", [[100], [200, 100]], ids=["un relevé", "deux relevés"])
def test_sans_trois_releves_aucune_tendance_n_est_jugee(releves):
    assert lecteur(releves).decroche is False


def test_le_seuil_de_tendance_est_de_trois_releves():
    # Deux suffiraient à alerter au moindre pic de trafic.
    assert RELEVES_POUR_UNE_TENDANCE == 3


# --- Les signalements -------------------------------------------------------


def test_le_signalement_nomme_le_groupe_le_sujet_et_la_suite():
    signalements = anomalies([lecteur([300, 200, 100])])

    assert len(signalements) == 1
    assert "compteurs-du-jour" in signalements[0]
    assert "navigation.evenements" in signalements[0]
    assert "100 → 200 → 300" in signalements[0]


def test_un_bus_sain_ne_signale_rien():
    assert anomalies([lecteur([100, 100, 100]), lecteur([50, 60, 70])]) == []


def test_seuls_les_lecteurs_qui_decrochent_sont_signales():
    signalements = anomalies(
        [
            lecteur([100, 100, 100], groupe="sain"),
            lecteur([300, 200, 100], groupe="en-retard"),
        ]
    )

    assert len(signalements) == 1
    assert "en-retard" in signalements[0]


def test_sans_aucun_lecteur_il_n_y_a_rien_a_signaler():
    assert anomalies([]) == []
