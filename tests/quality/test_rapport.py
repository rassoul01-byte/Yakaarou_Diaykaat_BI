"""Tests du rapport de taux de rejet.

Le calcul du taux et la décision de seuil sont des fonctions pures : elles se
testent sans base de données. Les tests marqués « integration » vérifient que
les vues existent et renvoient ce qu'on attend.
"""

import pytest

from quality.rapport import (
    SEUIL_PAR_DEFAUT,
    depassements,
    main,
    sources_sans_mesure,
    taux_pourcent,
)

# --- Le calcul du taux -------------------------------------------------------


def test_le_taux_est_la_part_des_lignes_rejetees():
    assert taux_pourcent(1000, 50) == 5.0


def test_le_taux_est_arrondi_au_centieme():
    assert taux_pourcent(99441, 775) == 0.78


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
def test_le_rapport_s_execute_sans_seuil(capsys):
    assert main([]) == 0
    assert "Taux de rejet par source" in capsys.readouterr().out


@pytest.mark.integration
def test_un_seuil_impossible_fait_echouer_le_rapport_s_il_y_a_des_rejets(capsys):
    from quality.rapport import collecter

    par_source, _, _ = collecter()
    mesures = [ligne for ligne in par_source if ligne["taux_rejet_pourcent"] is not None]
    if not mesures or max(float(m["taux_rejet_pourcent"]) for m in mesures) == 0:
        pytest.skip("aucun rejet enregistré : rien à faire dépasser")

    assert main(["--seuil", "0.0001"]) == 1
    assert "SEUIL DÉPASSÉ" in capsys.readouterr().out
