"""Tests du rapport de taux de rejet.

Le calcul du taux et la décision de seuil sont des fonctions pures : elles se
testent sans base de données. Les tests marqués « integration » vérifient que
les vues existent et renvoient ce qu'on attend.
"""

import json
from datetime import datetime

import pytest

from quality.rapport import (
    SEUIL_PAR_DEFAUT,
    afficher_complements,
    depassements,
    evolution,
    extraire_mesures,
    main,
    sources_sans_mesure,
    taux_pourcent,
)

# --- Le calcul du taux -------------------------------------------------------


def test_le_taux_est_la_part_des_lignes_rejetees():
    assert taux_pourcent(1000, 50) == 5.0


def test_le_taux_est_arrondi_comme_la_vue():
    """Trois décimales, celles de `quarantaine.v_taux_rejet_par_source`.

    Le dictionnaire des indicateurs désigne la vue comme le calcul du taux :
    la fonction Python ne peut pas arrondir autrement, sinon le même
    indicateur vaut deux choses selon qu'on le lit en base ou dans le rapport.
    """
    assert taux_pourcent(99441, 775) == 0.779
    # Le cas qui faisait échouer le test d'intégration : 20,21 contre 20,213.
    assert taux_pourcent(94, 19) == 20.213


def test_sans_ligne_lue_le_taux_n_existe_pas():
    # Afficher 0 % laisserait croire que tout va bien alors que rien n'a été lu.
    assert taux_pourcent(0, 0) is None
    assert taux_pourcent(None, None) is None


def test_aucun_rejet_donne_un_taux_nul():
    assert taux_pourcent(500, 0) == 0.0


def test_un_rejet_de_chaque_ligne_donne_cent_pour_cent():
    assert taux_pourcent(42, 42) == 100.0


# --- La décision de seuil ----------------------------------------------------


def test_le_seuil_du_projet_vaut_cinq_pour_cent():
    assert SEUIL_PAR_DEFAUT == 5.0


def test_une_source_au_dessus_du_seuil_est_signalee():
    lignes = [{"source": "olist", "taux_rejet_pourcent": 7.5}]

    (depassement,) = depassements(lignes, seuil=5.0)

    assert depassement.source == "olist"
    assert depassement.taux == 7.5


def test_une_source_juste_sous_le_seuil_passe():
    lignes = [{"source": "olist", "taux_rejet_pourcent": 4.99}]

    assert depassements(lignes, seuil=5.0) == []


def test_une_source_exactement_au_seuil_passe():
    # Le dossier dit « au-delà de 5 % » : 5 % n'est pas un dépassement.
    lignes = [{"source": "olist", "taux_rejet_pourcent": 5.0}]

    assert depassements(lignes, seuil=5.0) == []


def test_une_source_sans_mesure_n_est_pas_un_depassement():
    lignes = [{"source": "rakuten", "taux_rejet_pourcent": None}]

    assert depassements(lignes, seuil=5.0) == []
    assert sources_sans_mesure(lignes) == ["rakuten"]


def test_plusieurs_sources_au_dessus_sont_toutes_signalees():
    lignes = [
        {"source": "olist", "taux_rejet_pourcent": 9.1},
        {"source": "rakuten", "taux_rejet_pourcent": 6.0},
        {"source": "evenements", "taux_rejet_pourcent": 1.2},
    ]

    assert [d.source for d in depassements(lignes, seuil=5.0)] == ["olist", "rakuten"]


def test_un_seuil_severe_attrape_ce_qu_un_seuil_large_laisse_passer():
    lignes = [{"source": "olist", "taux_rejet_pourcent": 0.78}]

    assert depassements(lignes, seuil=5.0) == []
    assert len(depassements(lignes, seuil=0.1)) == 1


# --- Les lignes marquées et supprimées ---------------------------------------


def _message(*controles):
    return json.dumps({"ingestion": "I1", "controles": list(controles)})


def test_les_lignes_marquees_et_supprimees_sont_lues_dans_le_journal():
    message = _message(
        {
            "regle": "OLIST_GEOLOCALISATION_01",
            "gravite": "silencieuse",
            "lignes_supprimees": 261831,
        },
        {
            "regle": "OLIST_AVIS_03",
            "gravite": "non bloquante",
            "anomalies": 57612,
            "lignes_supprimees": 0,
        },
    )

    mesures = extraire_mesures("olist", message)

    assert {m["regle"]: (m["lignes_marquees"], m["lignes_supprimees"]) for m in mesures} == {
        "OLIST_GEOLOCALISATION_01": (0, 261831),
        "OLIST_AVIS_03": (57612, 0),
    }


def test_une_regle_qui_n_a_rien_signale_n_est_pas_listee():
    message = _message(
        {"regle": "OLIST_AVIS_01", "gravite": "bloquante", "lignes_quarantaine": 814}
    )
    assert extraire_mesures("olist", message) == []


def test_les_mesures_les_plus_grosses_viennent_en_premier():
    message = _message(
        {"regle": "PETITE", "gravite": "non bloquante", "anomalies": 3},
        {"regle": "GROSSE", "gravite": "non bloquante", "anomalies": 3000},
    )
    assert [m["regle"] for m in extraire_mesures("olist", message)] == ["GROSSE", "PETITE"]


@pytest.mark.parametrize("message", [None, "", "pas du json", "[]", '{"controles": null}'])
def test_un_message_absent_ou_illisible_ne_fait_pas_echouer_le_rapport(message):
    assert extraire_mesures("olist", message) == []


def test_l_affichage_distingue_les_lignes_marquees_des_lignes_supprimees(capsys):
    mesures = [
        {
            "source": "olist",
            "regle": "OLIST_GEOLOCALISATION_01",
            "gravite": "silencieuse",
            "lignes_marquees": 0,
            "lignes_supprimees": 261831,
        }
    ]

    afficher_complements(mesures, [])

    sortie = capsys.readouterr().out
    assert "Marquées" in sortie and "Supprimées" in sortie
    assert "OLIST_GEOLOCALISATION_01" in sortie and "261831" in sortie
    assert "Évolution" not in sortie


# --- L'évolution du taux d'une exécution à l'autre ---------------------------


def _execution(source, numero, taux, lues=1000):
    return {
        "execution_id": numero,
        "source": source,
        "demarre_a": datetime(2026, 10, 1, 8, numero),
        "lignes_lues": lues,
        "lignes_rejetees": 0 if taux is None else int(lues * taux / 100),
        "taux_rejet_pourcent": taux,
    }


def test_la_variation_est_l_ecart_avec_l_execution_precedente():
    suivies = evolution(
        [_execution("olist", 1, 0.5), _execution("olist", 2, 2.0), _execution("olist", 3, 1.5)]
    )

    assert [e["variation"] for e in suivies] == [None, 1.5, -0.5]
    assert [e["numero"] for e in suivies] == [1, 2, 3]


def test_chaque_source_a_sa_propre_evolution():
    suivies = evolution(
        [_execution("olist", 1, 1.0), _execution("rakuten", 2, 0.0), _execution("rakuten", 3, 0.0)]
    )

    olist = [e for e in suivies if e["source"] == "olist"]
    rakuten = [e for e in suivies if e["source"] == "rakuten"]
    assert olist[0]["variation"] is None
    assert [e["variation"] for e in rakuten] == [None, 0.0]


def test_la_fenetre_garde_les_dernieres_executions_mais_la_variation_regarde_avant():
    executions = [_execution("olist", n, float(n)) for n in range(1, 8)]

    suivies = evolution(executions, limite=3)

    assert [e["numero"] for e in suivies] == [5, 6, 7]
    assert suivies[0]["variation"] == 1.0  # calculée par rapport à l'exécution 4, hors fenêtre


def test_sans_taux_pas_de_variation():
    suivies = evolution([_execution("olist", 1, None), _execution("olist", 2, 1.0)])
    assert [e["variation"] for e in suivies] == [None, None]


def test_l_affichage_de_l_evolution_montre_la_variation(capsys):
    afficher_complements([], evolution([_execution("olist", 1, 0.5), _execution("olist", 2, 2.0)]))

    sortie = capsys.readouterr().out
    assert "Évolution du taux de rejet" in sortie
    assert "+1.50 pt" in sortie


def test_sans_complement_rien_n_est_affiche(capsys):
    afficher_complements([], [])
    assert capsys.readouterr().out == ""


# --- Le comportement en cas de base injoignable ------------------------------


def test_une_base_injoignable_donne_un_message_lisible_et_le_code_1(monkeypatch, capsys):
    import psycopg2

    def refuser(*_args, **_kwargs):
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(psycopg2, "connect", refuser)

    code = main([])

    assert code == 1
    erreurs = capsys.readouterr().err
    assert "ERREUR" in erreurs
    assert "Traceback" not in erreurs


# --- Avec une vraie base -----------------------------------------------------


@pytest.mark.integration
def test_les_vues_existent_et_repondent():
    from quality.rapport import collecter

    par_source, par_regle, par_gravite = collecter()

    assert isinstance(par_source, list)
    assert isinstance(par_regle, list)
    assert isinstance(par_gravite, list)


@pytest.mark.integration
def test_les_complements_se_lisent_en_base():
    from quality.rapport import collecter_complements

    mesures, historique = collecter_complements()

    assert isinstance(mesures, list)
    assert isinstance(historique, list)


@pytest.mark.integration
def test_le_rapport_s_execute_sans_seuil(capsys):
    assert main([]) == 0
    assert "Taux de rejet par source" in capsys.readouterr().out


def test_un_rapport_sans_aucune_mesure_echoue_au_lieu_de_passer_au_vert(monkeypatch, capsys):
    """Une absence de mesure n'est pas une absence de rejet.

    `v_taux_rejet_par_source` est vide dès que `staging.execution_log` l'est —
    et cette table n'est créée par aucune migration, seulement par le script
    d'initialisation du premier démarrage. Le garde-fou du DAG sortait alors 0
    et la chaîne chargeait l'entrepôt sans qu'aucun taux ait été évalué.
    """
    from quality import rapport

    monkeypatch.setattr(rapport, "collecter", lambda *a, **k: ([], [], []))
    monkeypatch.setattr(rapport, "collecter_complements", lambda *a, **k: ([], []))

    assert main(["--seuil", "5"]) == 1
    assert "AUCUNE MESURE DE QUALITÉ" in capsys.readouterr().err


def test_un_rapport_sans_mesure_et_sans_seuil_ne_fait_pas_echouer(monkeypatch):
    """Sans seuil, la commande ne garde rien : elle affiche, c'est tout."""
    from quality import rapport

    monkeypatch.setattr(rapport, "collecter", lambda *a, **k: ([], [], []))
    monkeypatch.setattr(rapport, "collecter_complements", lambda *a, **k: ([], []))

    assert main([]) == 0


@pytest.mark.integration
def test_un_seuil_impossible_fait_echouer_le_rapport_s_il_y_a_des_rejets(capsys):
    from quality.rapport import collecter

    par_source, _, _ = collecter()
    mesures = [ligne for ligne in par_source if ligne["taux_rejet_pourcent"] is not None]
    if not mesures or max(float(m["taux_rejet_pourcent"]) for m in mesures) == 0:
        pytest.skip("aucun rejet enregistré : rien à faire dépasser")

    assert main(["--seuil", "0.0001"]) == 1
    assert "SEUIL DÉPASSÉ" in capsys.readouterr().out
