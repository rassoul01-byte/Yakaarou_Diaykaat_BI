"""Tests du modèle de ré-achat.

Ce qui est vérifié ici, ce ne sont pas les performances du modèle — elles
dépendent des données — mais les **règles du protocole** : découpage temporel,
pondération des classes, absence de fuite, et refus de l'exactitude comme
mesure.
"""

from datetime import date

import pytest

from prediction.donnees import (
    CIBLE,
    DATE_ENTRAINEMENT,
    VARIABLES,
    separer,
    verifier_absence_de_fuite,
)
from prediction.fabrique import deux_periodes, jeu_fabrique
from prediction.modele import PONDERATION, entrainer, evaluer, influences, regles_naives


def jeu(lignes=200, date_reference=DATE_ENTRAINEMENT, part_positifs=0.1, graine=0):
    return jeu_fabrique(lignes, date_reference, part_positifs, graine)


# --- Le découpage est temporel ----------------------------------------------


def test_le_decoupage_separe_par_date_de_reference():
    x_ent, y_ent, x_eval, y_eval = separer(deux_periodes())

    assert len(x_ent) == 200
    assert len(x_eval) == 200


def test_les_deux_jeux_ne_partagent_aucune_ligne():
    # C'est toute la raison du découpage temporel : l'entraînement ne doit
    # jamais voir la période d'évaluation.
    donnees = deux_periodes()
    x_ent, _, x_eval, _ = separer(donnees)

    assert x_ent.index.intersection(x_eval.index).empty


def test_le_decoupage_ne_garde_que_les_variables_du_protocole():
    x_ent, _, _, _ = separer(deux_periodes())

    assert list(x_ent.columns) == list(VARIABLES)


def test_une_date_de_reference_absente_est_signalee():
    # Mieux vaut une erreur claire qu'un jeu vide qui entraîne un modèle creux.
    with pytest.raises(ValueError, match="dates de référence"):
        separer(jeu(date_reference=date(2020, 1, 1)))


# --- La fuite d'information -------------------------------------------------


def test_un_jeu_sain_passe_la_verification():
    verifier_absence_de_fuite(jeu())


def test_une_recence_negative_est_refusee():
    # Dernier achat postérieur à la date de référence : la réponse est dans
    # les variables, le modèle serait excellent et faux.
    donnees = jeu()
    donnees.loc[0, "recence_jours"] = -5

    with pytest.raises(ValueError, match="récence négative"):
        verifier_absence_de_fuite(donnees)


def test_une_anciennete_negative_est_refusee():
    donnees = jeu()
    donnees.loc[0, "anciennete_jours"] = -1

    with pytest.raises(ValueError, match="ancienneté négative"):
        verifier_absence_de_fuite(donnees)


# --- Le déséquilibre --------------------------------------------------------


def test_les_classes_sont_ponderees():
    # Sans pondération, le modèle apprendrait à répondre « non » à tout le monde.
    assert PONDERATION == "balanced"
    modele = entrainer(*_xy(jeu()))

    assert modele.named_steps["regression"].class_weight == "balanced"


def test_le_modele_ne_repond_pas_non_a_tout_le_monde():
    modele = entrainer(*_xy(jeu(graine=1)))
    prediction = modele.predict(jeu(graine=2)[list(VARIABLES)])

    assert prediction.sum() > 0, "un modèle qui ne prédit jamais le retour est inutile"


# --- Les mesures ------------------------------------------------------------


def test_l_evaluation_ne_calcule_pas_l_exactitude():
    # Elle vaudrait plus de 95 % pour un modèle inutile : elle n'existe pas ici.
    evaluation = evaluer(entrainer(*_xy(jeu(graine=1))), *_xy(jeu(graine=2)))

    assert not hasattr(evaluation, "exactitude")


def test_l_evaluation_donne_les_quatre_nombres_de_la_matrice():
    evaluation = evaluer(entrainer(*_xy(jeu(graine=1))), *_xy(jeu(graine=2)))
    somme = (
        evaluation.vrais_positifs
        + evaluation.faux_positifs
        + evaluation.vrais_negatifs
        + evaluation.faux_negatifs
    )

    assert somme == evaluation.total


def test_les_regles_naives_servent_de_juge():
    variables, cible = _xy(jeu())

    naives = regles_naives(variables, cible)

    assert set(naives) == {"tous negatifs", "deux commandes ou plus"}
    assert naives["tous negatifs"]["rappel"] == 0.0


def test_la_comparaison_porte_sur_le_f1_et_non_sur_le_seul_rappel():
    # « Tout le monde revient » a un rappel parfait et une précision dérisoire :
    # comparer le seul rappel déclarerait cette règle gagnante.
    variables, cible = _xy(jeu())
    naives = regles_naives(variables, cible)

    assert all("f1" in regle for regle in naives.values())


def test_un_rappel_parfait_mais_imprecis_ne_bat_pas_le_modele():
    evaluation = evaluer(entrainer(*_xy(jeu(1500, graine=1))), *_xy(jeu(1500, graine=2)))
    naif = evaluation.naives["deux commandes ou plus"]

    assert naif["rappel"] >= evaluation.rappel  # la règle rattrape tout
    assert naif["f1"] < evaluation.f1  # mais au prix d'une précision dérisoire
    assert evaluation.mieux_que_naif is True


def test_un_modele_qui_ne_bat_pas_les_regles_naives_est_signale():
    evaluation = evaluer(entrainer(*_xy(jeu(graine=1))), *_xy(jeu(graine=2)))

    # Le verdict existe et tranche, dans un sens ou dans l'autre.
    assert evaluation.mieux_que_naif in (True, False)


def test_la_part_de_positifs_est_connue():
    evaluation = evaluer(entrainer(*_xy(jeu(graine=1))), *_xy(jeu(graine=2)))

    assert 5.0 < evaluation.part_positifs < 15.0


# --- Reproductibilité et explicabilité --------------------------------------


def test_deux_entrainements_donnent_le_meme_modele():
    donnees = jeu()
    premier = evaluer(entrainer(*_xy(donnees)), *_xy(donnees))
    second = evaluer(entrainer(*_xy(donnees)), *_xy(donnees))

    assert (premier.rappel, premier.precision) == (second.rappel, second.precision)


def test_les_variables_influentes_sont_lisibles():
    donnees = jeu()
    modele = entrainer(*_xy(donnees))

    influentes = influences(modele, donnees[list(VARIABLES)])

    assert len(influentes) == 10
    assert all(nom in VARIABLES for nom, _ in influentes)
    # Du coefficient le plus fort au plus faible, en valeur absolue.
    valeurs = [abs(coefficient) for _, coefficient in influentes]
    assert valeurs == sorted(valeurs, reverse=True)


def _xy(donnees):
    return donnees[list(VARIABLES)], donnees[CIBLE]
