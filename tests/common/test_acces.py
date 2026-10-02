"""Tests du compte de lecture seule.

Le test qui compte est le dernier : il crée vraiment le compte, s'y connecte,
et vérifie qu'il ne peut rien écrire. Vouloir un compte en lecture ne suffit
pas — il faut le prouver.
"""

import psycopg2
import pytest

from common.acces import (
    SCHEMAS_LISIBLES,
    creer_compte_lecture,
    dsn_du_compte,
    identifiants,
    nom_de_base,
    valider_nom,
    verifier_lecture_seule,
)

COMPTE_D_ESSAI = "essai_lecture_seule"
MOTDEPASSE_D_ESSAI = "mot-de-passe-d-essai"


# --- Validation, sans base de données ---------------------------------------


@pytest.mark.parametrize("nom", ["powerbi_lecture", "lecture", "bi_2026"])
def test_les_noms_simples_sont_acceptes(nom):
    valider_nom(nom)


@pytest.mark.parametrize(
    "nom", ['bob"; DROP DATABASE dataflow360; --', "Majuscule", "ab", "nom avec espace", ""]
)
def test_un_nom_douteux_est_refuse(nom):
    # Un nom de rôle ne peut pas être passé en paramètre : il est validé ici.
    with pytest.raises(ValueError, match="nom de compte invalide"):
        valider_nom(nom)


def test_le_mot_de_passe_est_obligatoire(monkeypatch):
    monkeypatch.delenv("POWERBI_MOTDEPASSE", raising=False)

    with pytest.raises(ValueError, match="POWERBI_MOTDEPASSE"):
        identifiants()


def test_le_compte_et_le_mot_de_passe_viennent_de_l_environnement(monkeypatch):
    monkeypatch.setenv("POWERBI_UTILISATEUR", "lecture_bi")
    monkeypatch.setenv("POWERBI_MOTDEPASSE", "secret")

    assert identifiants() == ("lecture_bi", "secret")


def test_les_trois_schemas_du_projet_sont_couverts():
    assert SCHEMAS_LISIBLES == ("dwh", "quarantaine", "staging")


def test_le_nom_de_la_base_est_extrait_de_la_connexion():
    assert nom_de_base("postgresql://u:p@postgres:5432/dataflow360") == "dataflow360"


def test_la_connexion_du_compte_garde_l_hote_et_la_base():
    dsn = dsn_du_compte("lecture", "x", "postgresql://dataflow:mdp@postgres:5432/dataflow360")

    assert dsn.startswith("postgresql://lecture:x@postgres:5432/")
    assert dsn.endswith("/dataflow360")


# --- Avec une vraie base ----------------------------------------------------


@pytest.mark.integration
def test_le_compte_est_cree_puis_mis_a_jour_sans_erreur():
    premier = creer_compte_lecture(COMPTE_D_ESSAI, MOTDEPASSE_D_ESSAI)
    second = creer_compte_lecture(COMPTE_D_ESSAI, MOTDEPASSE_D_ESSAI)

    assert premier.utilisateur == COMPTE_D_ESSAI
    assert second.cree is False, "un second passage ne doit pas recréer le compte"


@pytest.mark.integration
def test_un_schema_absent_est_signale_mais_n_arrete_rien():
    resultat = creer_compte_lecture(
        COMPTE_D_ESSAI, MOTDEPASSE_D_ESSAI, schemas=("staging", "schema_qui_n_existe_pas")
    )

    assert "staging" in resultat.schemas_accordes
    assert "schema_qui_n_existe_pas" in resultat.schemas_absents


@pytest.mark.integration
def test_le_compte_lit_mais_ne_peut_rien_ecrire():
    creer_compte_lecture(COMPTE_D_ESSAI, MOTDEPASSE_D_ESSAI)

    assert verifier_lecture_seule(COMPTE_D_ESSAI, MOTDEPASSE_D_ESSAI) == []


@pytest.mark.integration
def test_le_compte_voit_bien_les_donnees_du_projet():
    creer_compte_lecture(COMPTE_D_ESSAI, MOTDEPASSE_D_ESSAI)

    with psycopg2.connect(dsn_du_compte(COMPTE_D_ESSAI, MOTDEPASSE_D_ESSAI)) as connexion:
        with connexion.cursor() as curseur:
            curseur.execute("SELECT count(*) FROM staging.execution_log")
            assert curseur.fetchone()[0] >= 0
