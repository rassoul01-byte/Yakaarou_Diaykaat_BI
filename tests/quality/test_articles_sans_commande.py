"""Tests de la règle OLIST_ARTICLES_02 — cascade du rejet d'une commande.

Rejeter une commande sans rejeter ses lignes d'article laisse des montants
rattachés à rien. Le chargement de l'entrepôt les refuse — c'est ce qui a
révélé le manque — mais la cause doit être tracée en quarantaine, pas
découverte trois étapes plus loin.
"""

import pandas as pd
import pytest

from quality.controle import controler_articles_sans_commande
from quality.rules import get_rule


@pytest.fixture
def regle():
    return get_rule("OLIST_ARTICLES_02")


COLONNES = ["order_id", "order_item_id", "price"]


def articles(*couples) -> pd.DataFrame:
    lignes = [{"order_id": o, "order_item_id": n, "price": 10.0} for o, n in couples]
    return pd.DataFrame(lignes, columns=COLONNES)


def commandes(*identifiants) -> pd.DataFrame:
    return pd.DataFrame({"order_id": list(identifiants)}, columns=["order_id"])


def test_la_regle_est_bloquante(regle):
    assert regle["gravite"] == "bloquante"
    assert regle["source"] == "olist"


def test_une_ligne_dont_la_commande_est_retenue_passe(regle):
    valides, rejetees = controler_articles_sans_commande(
        articles(("o1", 1)), commandes("o1"), regle
    )

    assert len(valides) == 1
    assert rejetees.empty


def test_une_ligne_dont_la_commande_a_ete_rejetee_part_en_quarantaine(regle):
    valides, rejetees = controler_articles_sans_commande(
        articles(("o1", 1), ("o2", 1)), commandes("o1"), regle
    )

    assert list(valides["order_id"]) == ["o1"]
    assert list(rejetees["order_id"]) == ["o2"]


def test_toutes_les_lignes_d_une_commande_rejetee_partent_ensemble(regle):
    # Une commande à trois articles : les trois suivent le sort de la commande.
    valides, rejetees = controler_articles_sans_commande(
        articles(("o1", 1), ("o1", 2), ("o1", 3), ("o2", 1)), commandes("o2"), regle
    )

    assert len(rejetees) == 3
    assert rejetees["order_id"].nunique() == 1
    assert len(valides) == 1


def test_aucune_ligne_n_est_perdue(regle):
    lignes = articles(("o1", 1), ("o2", 1), ("o3", 1))

    valides, rejetees = controler_articles_sans_commande(lignes, commandes("o1"), regle)

    assert len(valides) + len(rejetees) == len(lignes)


def test_sans_aucune_commande_retenue_tout_part_en_quarantaine(regle):
    valides, rejetees = controler_articles_sans_commande(
        articles(("o1", 1), ("o2", 1)), commandes(), regle
    )

    assert valides.empty
    assert len(rejetees) == 2


def test_une_ligne_sans_commande_renseignee_est_rejetee(regle):
    # Un order_id vide ne se rattache à rien : il ne doit pas se faufiler.
    valides, rejetees = controler_articles_sans_commande(
        articles((None, 1), ("o1", 2)), commandes("o1"), regle
    )

    assert list(valides["order_id"]) == ["o1"]
    assert len(rejetees) == 1


def test_sans_aucune_ligne_le_controle_ne_rejette_rien(regle):
    valides, rejetees = controler_articles_sans_commande(articles(), commandes("o1"), regle)

    assert valides.empty and rejetees.empty
