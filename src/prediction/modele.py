"""Entraînement et évaluation du modèle de ré-achat."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

GRAINE = 42

# Pondération des classes : la classe rare pèse davantage à l'entraînement.
# On ne duplique aucun exemple et on n'en supprime aucun — la pondération ne
# fabrique pas de données, elle change seulement ce que le modèle a à perdre
# en se trompant sur un client qui revient.
PONDERATION = "balanced"


@dataclass
class Evaluation:
    rappel: float
    precision: float
    f1: float
    vrais_positifs: int
    faux_positifs: int
    vrais_negatifs: int
    faux_negatifs: int
    positifs_reels: int
    total: int
    naives: dict = field(default_factory=dict)

    @property
    def part_positifs(self) -> float:
        return round(100.0 * self.positifs_reels / self.total, 2) if self.total else 0.0

    @property
    def mieux_que_naif(self) -> bool:
        """Le modèle bat-il la meilleure règle en une ligne ?

        La comparaison porte sur le **F1**, qui combine rappel et précision.
        Comparer le seul rappel déclarerait gagnante une règle qui répond
        « revient » à tout le monde : rappel parfait, précision dérisoire, et
        aucune utilité. Comparer la seule précision aurait le défaut inverse.

        Si la réponse est non, c'est un résultat qu'on publie tel quel : un
        modèle qui ne fait pas mieux qu'une règle triviale ne sert à rien, et
        le dire vaut mieux que l'habiller.
        """
        if not self.naives:
            return False
        meilleur = max(regle["f1"] for regle in self.naives.values())
        return self.f1 > meilleur


def construire() -> Pipeline:
    """Le modèle : imputation, mise à l'échelle, régression logistique.

    L'imputation remplace les valeurs manquantes par la médiane — un client
    qui n'a donné aucun avis n'a pas de note moyenne, et c'est fréquent.
    """
    return Pipeline(
        [
            ("imputation", SimpleImputer(strategy="median")),
            ("echelle", StandardScaler()),
            (
                "regression",
                LogisticRegression(
                    class_weight=PONDERATION,
                    max_iter=1000,
                    random_state=GRAINE,
                ),
            ),
        ]
    )


def entrainer(variables: pd.DataFrame, cible: pd.Series) -> Pipeline:
    modele = construire()
    modele.fit(variables, cible)
    return modele


def probabilites_de_retour(modele: Pipeline, variables: pd.DataFrame):
    """Probabilité, pour chaque client, de repasser commande (classe 1)."""
    return modele.predict_proba(variables)[:, 1]


def regles_naives(variables: pd.DataFrame, cible: pd.Series) -> dict:
    """Deux règles en une ligne, qui servent de juge au modèle."""
    import numpy as np

    regles = {
        "tous negatifs": np.zeros(len(cible), dtype=int),
        "deux commandes ou plus": (variables["commandes"] >= 2).astype(int).to_numpy(),
    }
    return {
        nom: {
            "rappel": round(recall_score(cible, prediction, zero_division=0), 3),
            "precision": round(precision_score(cible, prediction, zero_division=0), 3),
            "f1": round(f1_score(cible, prediction, zero_division=0), 3),
        }
        for nom, prediction in regles.items()
    }


def evaluer(modele: Pipeline, variables: pd.DataFrame, cible: pd.Series) -> Evaluation:
    """Mesure le modèle. L'exactitude n'est volontairement pas calculée.

    Un modèle qui répondrait « il ne reviendra pas » à tout le monde afficherait
    plus de 95 % d'exactitude et serait inutile. Ce chiffre n'apparaît nulle
    part, pour qu'il ne soit jamais cité.
    """
    prediction = modele.predict(variables)
    vn, fp, fn, vp = confusion_matrix(cible, prediction, labels=[0, 1]).ravel()

    return Evaluation(
        rappel=round(recall_score(cible, prediction, zero_division=0), 3),
        precision=round(precision_score(cible, prediction, zero_division=0), 3),
        f1=round(f1_score(cible, prediction, zero_division=0), 3),
        vrais_positifs=int(vp),
        faux_positifs=int(fp),
        vrais_negatifs=int(vn),
        faux_negatifs=int(fn),
        positifs_reels=int(cible.sum()),
        total=len(cible),
        naives=regles_naives(variables, cible),
    )


def influences(modele: Pipeline, variables: pd.DataFrame, limite: int = 10) -> list:
    """Les variables qui pèsent le plus, du coefficient le plus fort au plus faible.

    Les coefficients sont lisibles parce que les variables sont mises à la même
    échelle : sans cela, un montant en milliers d'euros écraserait un nombre de
    commandes qui vaut 1 ou 2.
    """
    coefficients = modele.named_steps["regression"].coef_[0]
    paires = sorted(
        zip(variables.columns, coefficients, strict=True),
        key=lambda paire: abs(paire[1]),
        reverse=True,
    )
    return [(nom, round(float(valeur), 3)) for nom, valeur in paires[:limite]]
