"""Lecture de l'historique client et découpage temporel.

La table attendue porte une ligne **par client et par date de référence**,
avec la réponse observée : `a_rachete`. Deux dates de référence suffisent —
une pour entraîner, une pour évaluer.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import psycopg2

from common.config import load_settings

TABLE = "dwh.v_historique_client"

CIBLE = "a_rachete"
CLE = "customer_unique_id"
DATE_REFERENCE = "date_reference"

# Les variables du protocole. L'ordre n'a pas d'importance pour le modèle, il
# en a pour la lecture des coefficients : on le fixe donc une fois.
VARIABLES = (
    "commandes",
    "montant_total",
    "montant_moyen",
    "recence_jours",
    "anciennete_jours",
    "note_moyenne",
    "avis_donnes",
    "delai_livraison_moyen",
    "livraisons_en_retard",
    "categories_distinctes",
)

# Les deux dates du protocole. L'entraînement ne voit jamais la période
# d'évaluation : c'est toute la raison d'être de ce découpage.
DATE_ENTRAINEMENT = date(2017, 3, 31)
DATE_EVALUATION = date(2017, 9, 30)


def charger(dsn: str | None = None) -> pd.DataFrame:
    """Lit l'historique client, toutes dates de référence confondues."""
    colonnes = ", ".join((CLE, DATE_REFERENCE, *VARIABLES, CIBLE))
    with (
        psycopg2.connect(dsn or load_settings().postgres_dsn) as connexion,
        connexion.cursor() as curseur,
    ):
        # `ORDER BY` explicite : sans lui, PostgreSQL ne garantit aucun ordre.
        # Or le départage des ex æquo au classement est « l'ordre d'origine »
        # (classement._ordre, tri stable). Pour un modèle à scores discrets —
        # un arbre de profondeur 8 produit au plus 256 valeurs distinctes pour
        # 26 000 clients — le top 250 tombe à l'intérieur d'un paquet d'ex
        # æquo, et son contenu dépendait de l'ordre de lecture en base.
        # La promesse « deux entraînements donnent les mêmes chiffres »
        # (contrats/modele.md) n'était donc pas tenue.
        curseur.execute(f"SELECT {colonnes} FROM {TABLE} ORDER BY {DATE_REFERENCE}, {CLE}")
        noms = [colonne.name for colonne in curseur.description]
        return pd.DataFrame(curseur.fetchall(), columns=noms)


def lire(fabrique: bool = False) -> pd.DataFrame:
    """Source des données : l'entrepôt, ou le jeu fabriqué de 200 lignes.

    Le jeu fabriqué a les mêmes colonnes que la vue réelle. Le jour où les
    variables de Bachir sont livrées, on n'appelle plus `lire(fabrique=True)`
    et rien d'autre ne change.
    """
    if fabrique:
        from .fabrique import deux_periodes

        return deux_periodes()
    return charger()


def clients_a_scorer(donnees: pd.DataFrame, date_reference: date = DATE_EVALUATION) -> pd.DataFrame:
    """Les clients tels qu'ils sont décrits à une date de référence donnée."""
    reference = pd.to_datetime(donnees[DATE_REFERENCE]).dt.date
    lignes = donnees[reference == date_reference]
    if lignes.empty:
        disponibles = sorted({str(d) for d in reference})
        raise ValueError(
            f"aucun client à la date de référence {date_reference} — dates "
            f"présentes : {', '.join(disponibles) or 'aucune'}"
        )
    return lignes


def verifier_absence_de_fuite(donnees: pd.DataFrame) -> None:
    """Refuse un jeu dont une variable connaît l'avenir.

    C'est la seule erreur qui invalide le modèle sans que rien ne le signale :
    une récence négative signifie que le dernier achat est postérieur à la date
    de référence, donc que la réponse est déjà dans les variables.
    """
    if (donnees["recence_jours"] < 0).any():
        nombre = int((donnees["recence_jours"] < 0).sum())
        raise ValueError(
            f"{nombre} ligne(s) ont une récence négative : une variable contient "
            "une information postérieure à la date de référence. Le jeu est inutilisable."
        )
    if (donnees["anciennete_jours"] < 0).any():
        raise ValueError(
            "des clients ont une ancienneté négative : leur premier achat est "
            "postérieur à la date de référence, ils ne devraient pas être dans le jeu."
        )


def separer(
    donnees: pd.DataFrame,
    date_entrainement: date = DATE_ENTRAINEMENT,
    date_evaluation: date = DATE_EVALUATION,
) -> tuple:
    """Découpe le jeu **par la date**, jamais au hasard.

    Un découpage aléatoire mélangerait des clients observés à des périodes
    différentes : le modèle apprendrait sur ce qu'il doit prédire, et ses
    résultats seraient excellents et faux.
    """
    reference = pd.to_datetime(donnees[DATE_REFERENCE]).dt.date

    entrainement = donnees[reference == date_entrainement]
    evaluation = donnees[reference == date_evaluation]

    if entrainement.empty or evaluation.empty:
        disponibles = sorted({str(d) for d in reference})
        raise ValueError(
            "jeu d'entraînement ou d'évaluation vide — dates de référence "
            f"présentes : {', '.join(disponibles) or 'aucune'}"
        )

    return (
        entrainement[list(VARIABLES)],
        entrainement[CIBLE].astype(int),
        evaluation[list(VARIABLES)],
        evaluation[CIBLE].astype(int),
    )
