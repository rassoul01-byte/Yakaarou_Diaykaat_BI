"""Jeu fabriqué, aux mêmes colonnes que la vue `dwh.v_historique_client`.

Il sert à écrire et tester l'entraînement, l'évaluation et les scores sans
attendre les vraies variables. Ses résultats ne veulent RIEN dire : ils ne
doivent jamais figurer dans un dossier ni dans une démonstration.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .donnees import CIBLE, CLE, DATE_ENTRAINEMENT, DATE_EVALUATION, DATE_REFERENCE


def jeu_fabrique(
    lignes: int = 200,
    date_reference=DATE_ENTRAINEMENT,
    part_positifs: float = 0.1,
    graine: int = 0,
) -> pd.DataFrame:
    """Un jeu déséquilibré comme le vrai : peu de clients reviennent."""
    hasard = np.random.default_rng(graine)
    positifs = int(lignes * part_positifs)
    # Les clients qui reviennent ont commandé plus souvent et plus récemment.
    commandes = np.concatenate(
        [hasard.integers(2, 8, positifs), hasard.integers(1, 3, lignes - positifs)]
    )
    recence = np.concatenate(
        [hasard.integers(5, 90, positifs), hasard.integers(90, 600, lignes - positifs)]
    )
    return pd.DataFrame(
        {
            CLE: [f"c{i:05d}" for i in range(lignes)],
            DATE_REFERENCE: [date_reference] * lignes,
            "commandes": commandes,
            "montant_total": commandes * hasard.uniform(40, 200, lignes),
            "montant_moyen": hasard.uniform(40, 200, lignes),
            "recence_jours": recence,
            "anciennete_jours": recence + hasard.integers(10, 300, lignes),
            "note_moyenne": hasard.uniform(1, 5, lignes),
            "avis_donnes": hasard.integers(0, 3, lignes),
            "delai_livraison_moyen": hasard.uniform(5, 30, lignes),
            "livraisons_en_retard": hasard.integers(0, 2, lignes),
            "categories_distinctes": hasard.integers(1, 5, lignes),
            CIBLE: [1] * positifs + [0] * (lignes - positifs),
        }
    )


def deux_periodes(lignes: int = 200) -> pd.DataFrame:
    """Une période d'entraînement et une période d'évaluation, distinctes."""
    return pd.concat(
        [
            jeu_fabrique(lignes, DATE_ENTRAINEMENT, graine=1),
            jeu_fabrique(lignes, DATE_EVALUATION, graine=2),
        ],
        ignore_index=True,
    )
