"""Tests du journal des exécutions.

Ce qui est vérifié ici, c'est la détection d'anomalies : les vues SQL font le
calcul, le module dit ce qui mérite d'être regardé. Une supervision qui
signale tout ne signale rien — c'est le réglage qui compte, pas l'affichage.
"""

import pytest

from supervision.journal import anomalies


def execution(pipeline="qualite", etape="controle", source="olist", duree=10.0, statut="succes"):
    return {
        "pipeline": pipeline,
        "etape": etape,
        "source": source,
        "demarre_a": None,
        "duree_secondes": duree,
        "lignes_lues": 1000,
        "lignes_ecrites": 1000,
        "lignes_rejetees": 0,
        "statut": statut,
    }


def profil(pipeline="qualite", etape="controle", source="olist", moyenne=10.0, executions=10):
    return {
        "pipeline": pipeline,
        "etape": etape,
        "source": source,
        "executions": executions,
        "echecs": 0,
        "duree_moyenne_secondes": moyenne,
        "duree_maximale_secondes": moyenne * 2,
        "lignes_lues_moyenne": 1000,
    }


def donnees(dernieres=None, profils=None, en_cours=None):
    return {
        "dernieres": dernieres if dernieres is not None else [],
        "profil": profils if profils is not None else [],
        "echecs": [],
        "volume": [],
        "en_cours": en_cours if en_cours is not None else [],
    }


# --- Les échecs -------------------------------------------------------------


def test_une_etape_en_echec_est_signalee():
    signalements = anomalies(donnees([execution(statut="echec")], [profil()]))

    assert len(signalements) == 1
    assert "a échoué" in signalements[0]


def test_une_journee_normale_ne_signale_rien():
    assert anomalies(donnees([execution()], [profil()])) == []


def test_le_signalement_nomme_l_etape_et_la_source():
    signalements = anomalies(donnees([execution(statut="erreur")], [profil()]))

    assert "qualite/controle" in signalements[0]
    assert "olist" in signalements[0]


# --- Les durées anormales ---------------------------------------------------


def test_une_etape_trois_fois_plus_longue_que_d_habitude_est_signalee():
    signalements = anomalies(donnees([execution(duree=30.0)], [profil(moyenne=10.0)]))

    assert len(signalements) == 1
    assert "plus longtemps que d'habitude" in signalements[0]


def test_une_etape_deux_fois_plus_longue_ne_l_est_pas():
    # Le seuil est à trois : un facteur deux arrive trop souvent pour alerter.
    assert anomalies(donnees([execution(duree=20.0)], [profil(moyenne=10.0)])) == []


def test_sans_historique_suffisant_aucune_duree_n_est_jugee():
    # Deux exécutions ne font pas une habitude.
    donnees_courtes = donnees([execution(duree=100.0)], [profil(moyenne=10.0, executions=2)])

    assert anomalies(donnees_courtes) == []


def test_une_etape_sans_profil_connu_ne_declenche_rien():
    assert anomalies(donnees([execution(duree=999.0)], [])) == []


def test_une_execution_en_cours_n_a_pas_de_duree_a_comparer():
    assert anomalies(donnees([execution(duree=None)], [profil()])) == []


# --- Les exécutions qui ne finissent pas ------------------------------------


def test_une_execution_en_cours_depuis_trop_longtemps_est_signalee():
    en_cours = [{"pipeline": "qualite", "etape": "controle", "depuis_secondes": 2400}]

    signalements = anomalies(donnees(en_cours=en_cours))

    assert "interrompue" in signalements[0]
    assert "40 minutes" in signalements[0]


def test_une_execution_qui_vient_de_demarrer_n_est_pas_signalee():
    en_cours = [{"pipeline": "qualite", "etape": "controle", "depuis_secondes": 120}]

    assert anomalies(donnees(en_cours=en_cours)) == []


# --- Plusieurs anomalies ----------------------------------------------------


def test_les_anomalies_s_additionnent():
    signalements = anomalies(
        donnees(
            [execution(statut="echec"), execution(etape="chargement", duree=60.0)],
            [profil(), profil(etape="chargement", moyenne=10.0)],
        )
    )

    assert len(signalements) == 2


def test_une_execution_en_cours_n_est_pas_un_echec():
    # Elle n'a pas fini, ce n'est pas la même chose qu'avoir échoué. Si elle
    # traîne, c'est le contrôle des exécutions interrompues qui la signalera.
    assert anomalies(donnees([execution(statut="en_cours", duree=None)], [profil()])) == []


@pytest.mark.parametrize("statut", ["echec", "erreur", "interrompu"])
def test_tout_statut_autre_que_succes_est_une_anomalie(statut):
    assert anomalies(donnees([execution(statut=statut)], [profil()])) != []
