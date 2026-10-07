"""Segment à retenir — choisir un seuil, et savoir ce qu'il coûte (F3.7).

Le modèle produit un score par client. En faire une liste exploitable suppose
un seuil, et **il n'existe pas de bon seuil dans l'absolu** : viser large
retient plus de clients qui reviendront mais en sollicite beaucoup qui ne
reviendront pas ; viser étroit sollicite moins de monde pour rien mais laisse de
côté des clients qui reviendront.

Ce module ne choisit pas à la place du Product Owner. Il montre ce que chaque
taille de segment rapporte et ce qu'elle coûte, pour que le choix soit fait
sur des chiffres.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Les tailles de segment proposées : de 100 clients à 5 000. Un responsable
# marketing raisonne en nombre de personnes à contacter, pas en probabilité.
TAILLES = (100, 250, 500, 1000, 2500, 5000)


@dataclass(frozen=True)
class Palier:
    taille: int
    positifs: int
    part_pourcent: float
    base_pourcent: float
    score_minimum: float

    @property
    def gain(self) -> float:
        """Combien de fois mieux que de prendre des clients au hasard."""
        if not self.base_pourcent:
            return 0.0
        return round(self.part_pourcent / self.base_pourcent, 2)

    @property
    def faux_positifs(self) -> int:
        return self.taille - self.positifs


def paliers(scores: np.ndarray, verite: np.ndarray, tailles=TAILLES) -> list[Palier]:
    """Pour chaque taille de segment, ce qu'on y trouve.

    Les clients sont classés par score **décroissant** : le segment des 100
    premiers est celui des cent clients que le modèle juge les plus enclins à
    revenir. On compte ensuite combien sont effectivement revenus.
    """
    ordre = np.argsort(-np.asarray(scores, dtype=float))
    verite = np.asarray(verite, dtype=int)[ordre]
    classes = np.asarray(scores, dtype=float)[ordre]
    total = len(verite)
    base = 100.0 * verite.sum() / total if total else 0.0

    resultat = []
    for taille in tailles:
        if taille > total:
            continue
        retenus = verite[:taille]
        positifs = int(retenus.sum())
        resultat.append(
            Palier(
                taille=taille,
                positifs=positifs,
                part_pourcent=round(100.0 * positifs / taille, 2),
                base_pourcent=round(base, 2),
                score_minimum=round(float(classes[taille - 1]), 4),
            )
        )
    return resultat


def segment(donnees: pd.DataFrame, scores: np.ndarray, taille: int) -> pd.DataFrame:
    """La liste des clients à retenir, du score le plus élevé au plus faible."""
    resultat = donnees.assign(score=np.asarray(scores, dtype=float))
    return resultat.nlargest(taille, "score")
