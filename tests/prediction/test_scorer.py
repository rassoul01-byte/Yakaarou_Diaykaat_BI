"""Tests des scores et des commandes en ligne.

Les règles du protocole vérifiées ici : les scores ne dépendent pas de la réponse
observée de la période scorée, deux exécutions donnent le même tableau, et
aucune fonction de découpage aléatoire n'existe dans le paquet.
"""

from pathlib import Path

import pandas as pd
import pytest

import prediction
from prediction import __main__ as entrainement
from prediction import scorer
from prediction.donnees import CIBLE, CLE, DATE_EVALUATION, DATE_REFERENCE, clients_a_scorer
from prediction.fabrique import deux_periodes


def test_un_score_par_client_a_la_date_demandee():
    tableau = scorer.tableau_des_scores(deux_periodes())

    assert len(tableau) == 200
    assert list(tableau.columns) == [CLE, "proba_retour", "risque_depart"]
    assert tableau[CLE].is_unique


def test_les_probabilites_sont_des_probabilites():
    tableau = scorer.tableau_des_scores(deux_periodes())

    assert tableau["proba_retour"].between(0, 1).all()
    assert ((tableau["proba_retour"] + tableau["risque_depart"]) - 1).abs().max() < 1e-3


def test_les_clients_sont_classes_du_plus_au_moins_a_risque():
    tableau = scorer.tableau_des_scores(deux_periodes())

    assert tableau["risque_depart"].is_monotonic_decreasing


def test_deux_executions_donnent_exactement_le_meme_tableau():
    donnees = deux_periodes()

    pd.testing.assert_frame_equal(
        scorer.tableau_des_scores(donnees), scorer.tableau_des_scores(donnees)
    )


def test_les_scores_ne_dependent_pas_de_la_reponse_de_la_periode_scoree():
    # Si le score changeait quand on falsifie la réponse observée de la période
    # scorée, le modèle aurait vu l'avenir.
    donnees = deux_periodes()
    falsifie = donnees.copy()
    en_evaluation = pd.to_datetime(falsifie[DATE_REFERENCE]).dt.date == DATE_EVALUATION
    falsifie.loc[en_evaluation, CIBLE] = 1 - falsifie.loc[en_evaluation, CIBLE]

    pd.testing.assert_frame_equal(
        scorer.tableau_des_scores(donnees), scorer.tableau_des_scores(falsifie)
    )


def test_une_date_sans_client_est_signalee():
    with pytest.raises(ValueError, match="dates"):
        clients_a_scorer(deux_periodes(), pd.Timestamp("2020-01-01").date())


def test_aucune_fonction_de_decoupage_aleatoire():
    # Un découpage aléatoire sur des données temporelles ferait voir l'avenir
    # au modèle : ses résultats seraient flatteurs et faux.
    interdits = ("train_test_split", "ShuffleSplit", "KFold", "shuffle=True")
    dossier = Path(prediction.__file__).parent

    for fichier in dossier.glob("*.py"):
        code = fichier.read_text(encoding="utf-8")
        for nom in interdits:
            assert nom not in code, f"{nom} trouvé dans {fichier.name}"


def test_la_commande_d_entrainement_tourne_sur_le_jeu_fabrique(capsys):
    code = entrainement.main(["--fabrique"])
    sortie = capsys.readouterr().out

    assert code == 0
    assert "JEU FABRIQUÉ" in sortie
    assert "Matrice de confusion" in sortie
    assert (
        "exactitude" in sortie.lower()
    )  # elle n'est citée que pour dire qu'elle n'est pas calculée


def test_la_commande_de_scores_affiche_et_ecrit_le_csv(tmp_path, capsys):
    fichier = tmp_path / "scores.csv"

    code = scorer.main(["--fabrique", "--top", "5", "--csv", str(fichier)])
    sortie = capsys.readouterr().out

    assert code == 0
    assert "JEU FABRIQUÉ" in sortie
    assert len(pd.read_csv(fichier)) == 200


def test_une_date_mal_formee_est_refusee():
    with pytest.raises(SystemExit):
        scorer.main(["--fabrique", "--date", "demain"])
