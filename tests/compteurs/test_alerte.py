"""Tests de l'alerte sur chute des ventes.

Tout le livrable est dans le réglage. Une alerte qui se déclenche sans raison
cesse d'être lue au bout d'une semaine : ces tests décrivent exactement quand
elle parle, et surtout quand elle se tait.
"""

from datetime import date
from pathlib import Path

import pytest

from compteurs.alerte import (
    HEURE_MINIMALE,
    JOURS_MINIMUM,
    JOURS_SANS_FLUX_TOLERES,
    SEUIL_POURCENT,
    Verdict,
    dernier_jour_connu,
    evaluer,
    flux_interrompu,
)


def verdict(achats=10, habituels=20.0, jours=4, heure=14):
    return Verdict(
        jour=date(2026, 9, 7),
        achats=achats,
        habituels=habituels,
        jours_compares=jours,
        heure=heure,
    )


# --- Quand l'alerte se déclenche --------------------------------------------


def test_une_chute_sous_le_seuil_declenche_l_alerte():
    # 10 achats contre 20 habituels : 50 %, sous le seuil de 60 %.
    assert verdict(achats=10, habituels=20.0).alerte is True


def test_une_journee_normale_ne_declenche_rien():
    assert verdict(achats=19, habituels=20.0).alerte is False


def test_une_journee_meilleure_que_d_habitude_ne_declenche_rien():
    assert verdict(achats=40, habituels=20.0).alerte is False


def test_exactement_au_seuil_ne_declenche_pas():
    # 12 sur 20 fait 60 % : le seuil est « en dessous de », pas « au plus ».
    assert verdict(achats=12, habituels=20.0).alerte is False


def test_aucun_achat_du_tout_declenche_l_alerte():
    # Le cas d'une chaîne arrêtée : les compteurs tombent à zéro.
    assert verdict(achats=0, habituels=20.0).alerte is True


# --- Quand elle se tait, et pourquoi ----------------------------------------


@pytest.mark.parametrize("heure", [0, 8, 11])
def test_avant_midi_l_alerte_ne_se_prononce_pas(heure):
    # L'activité d'une matinée est toujours incomplète.
    assert verdict(achats=0, heure=heure).alerte is False


def test_a_midi_l_alerte_se_prononce():
    assert verdict(achats=0, heure=HEURE_MINIMALE).alerte is True


@pytest.mark.parametrize("jours", [0, 1])
def test_sans_historique_suffisant_l_alerte_se_tait(jours):
    assert verdict(achats=0, jours=jours).alerte is False


def test_sans_moyenne_connue_il_n_y_a_rien_a_comparer():
    assert verdict(habituels=None, jours=3).alerte is False
    assert verdict(habituels=None, jours=3).niveau_pourcent is None


# --- Le calcul du niveau ----------------------------------------------------


def test_le_niveau_est_la_part_de_l_activite_habituelle():
    assert verdict(achats=15, habituels=20.0).niveau_pourcent == 75.0


def test_le_niveau_depasse_cent_quand_la_journee_est_meilleure():
    assert verdict(achats=30, habituels=20.0).niveau_pourcent == 150.0


# --- Les messages -----------------------------------------------------------


def test_le_message_d_alerte_donne_les_deux_chiffres_et_le_seuil():
    message = verdict(achats=5, habituels=20.0).message()

    assert "5 achat(s)" in message
    assert "20.0" in message
    assert "60 %" in message


def test_le_message_explique_le_manque_d_historique():
    assert "pas assez d'historique" in verdict(jours=1).message()


def test_le_message_explique_qu_il_est_trop_tot():
    assert "trop tôt" in verdict(achats=0, heure=9).message()


def test_une_journee_normale_le_dit_sans_ambiguite():
    assert "rien à signaler" in verdict(achats=19, habituels=20.0).message()


# --- Les réglages sont explicites -------------------------------------------


def test_les_seuils_sont_ceux_du_dictionnaire():
    assert SEUIL_POURCENT == 60.0
    assert HEURE_MINIMALE == 12
    assert JOURS_MINIMUM == 2
    assert JOURS_SANS_FLUX_TOLERES == 1


# --- L'arrondi ne décide pas ------------------------------------------------


def test_un_niveau_sous_le_seuil_declenche_meme_si_l_arrondi_le_remonte():
    """240 / 400,25 = 59,96 %, qui s'arrondit à 60,0 %.

    En comparant la valeur arrondie, `60,0 < 60,0` est faux et l'alerte était
    perdue. C'est le seuil qui décide, pas l'affichage.
    """
    v = verdict(achats=240, habituels=400.25)

    assert v.niveau_pourcent == 60.0, "l'affichage reste arrondi"
    assert v.niveau_exact < SEUIL_POURCENT
    assert v.alerte is True


def test_un_niveau_exactement_au_seuil_ne_declenche_pas():
    """La frontière reste stricte : 60 % pile n'est pas une chute."""
    assert verdict(achats=120, habituels=200.0).alerte is False


# --- L'absence de flux n'est pas une absence de chute -----------------------


def test_un_flux_a_jour_ne_signale_rien():
    assert flux_interrompu(date(2026, 9, 7), date(2026, 9, 7)) is None
    assert flux_interrompu(date(2026, 9, 6), date(2026, 9, 7)) is None


def test_un_flux_interrompu_est_signale_avec_son_retard():
    assert flux_interrompu(date(2026, 9, 4), date(2026, 9, 7)) == 3


def test_une_vue_vide_ne_signale_pas_un_flux_interrompu():
    """Sans aucune ligne, on ne sait pas depuis quand : c'est un autre message."""
    assert flux_interrompu(None, date(2026, 9, 7)) is None
    assert dernier_jour_connu([]) is None


def test_le_dernier_jour_connu_est_le_plus_recent():
    recent, ancien = verdict(), Verdict(date(2026, 9, 1), 5, 20.0, 4, 14)

    assert dernier_jour_connu([recent, ancien]) == date(2026, 9, 7)


# --- Une seule définition du seuil ------------------------------------------


def test_le_seuil_sql_et_le_seuil_python_sont_le_meme():
    """Deux définitions d'un même indicateur finissent toujours par diverger.

    Le seuil vit dans `sql/026_verdict_de_l_alerte.sql`, pour que la vue puisse
    publier le verdict et que Power BI n'ait pas à le réécrire. La constante
    Python porte la même valeur, et ce test interdit qu'elles se séparent.
    """
    migration = (
        Path(__file__).resolve().parents[2] / "sql" / "026_verdict_de_l_alerte.sql"
    ).read_text(encoding="utf-8")

    assert f"< {SEUIL_POURCENT}" in migration, (
        f"le seuil de la vue ne vaut plus {SEUIL_POURCENT} ; "
        "aligner sql/026 et compteurs.alerte.SEUIL_POURCENT"
    )
    assert f">= {JOURS_MINIMUM}" in migration


# --- La lecture d'une ligne de la vue ---------------------------------------


def test_une_ligne_de_la_vue_devient_un_verdict():
    ligne = {
        "jour": date(2026, 9, 7),
        "jour_semaine": 1,
        "achats": 8,
        "achats_habituels": 20.0,
        "jours_compares": 4,
    }

    resultat = evaluer(ligne, heure=15)

    assert resultat.achats == 8
    assert resultat.alerte is True
