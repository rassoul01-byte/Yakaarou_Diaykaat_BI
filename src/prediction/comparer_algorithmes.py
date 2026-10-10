"""Comparaison d'algorithmes de classification pour le modèle de ré-achat.

On reste sur scikit-learn (pas de nouvelle dépendance avant la soutenance).
Les algorithmes sont testés sur les mêmes features, mêmes dates, même
protocole que la phase 0.

Le gain au top N est calculé par fenêtre puis poolé (somme des trouvés sur
somme des ciblés, un seul Wilson sur le total). Les IC permettent de dire
si un algorithme est significativement meilleur qu'un autre.

Références documentées (docs/contrats/modele.md, dictionnaire) :
- Modèle, top 250 : 14/250, 3,55x [2,13x ; 5,82x]
- Modèle, 711 clients : 18/711, 1,61x [1,02x ; 2,52x]
- Règle 2+, 711 clients : 32/711, 2,85x [2,03x ; 3,99x]
- Modèle, top 10 % : 56/413, 1,36x [1,05x ; 1,75x]

Cible : battre 2,85x à 711 clients et 3,55x au top 250.

Usage :
    docker compose exec app python -m prediction.comparer_algorithmes
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import date

import numpy as np
import pandas as pd
import psycopg2
from sklearn.ensemble import (
    AdaBoostClassifier,
    BaggingClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .classement import retours_captes
from .donnees import (
    DATE_ENTRAINEMENT,
    DATE_EVALUATION,
    VARIABLES,
    lire,
    verifier_absence_de_fuite,
)
from .statistiques import pooler, wilson

GRAINE = 42

# Paliers en fraction pour l'agrégation poolée.
# 0.10 correspond au top 10 % documenté dans le dictionnaire des indicateurs.
PALIERS_FRACTION = (0.005, 0.01, 0.02, 0.05, 0.10)

# Paliers en nombre fixe pour le tableau B.
# 711 est le volume de la règle « 2+ commandes » au 2017-09-30, chiffre
# de référence dans docs/contrats/modele.md ligne 113.
# 250 est la référence documentée (3,55x avec IC [2,13x ; 5,82x]).
PALIERS_FIXES = (100, 250, 500, 711, 1000)


def _pipeline(clf) -> Pipeline:
    """Pipeline commun : imputation médiane + standardisation + classifieur.

    Le StandardScaler n'a pas d'effet sur les arbres, mais il est
    inoffensif et garde le code uniforme.
    """
    return Pipeline(
        [
            ("imputation", SimpleImputer(strategy="median")),
            ("echelle", StandardScaler()),
            ("clf", clf),
        ]
    )


def algorithmes() -> dict[str, Pipeline]:
    """Les algorithmes à comparer, tous natifs sklearn."""
    return {
        "LogReg baseline": _pipeline(
            LogisticRegression(class_weight="balanced", max_iter=1000, random_state=GRAINE)
        ),
        "LogReg C=0.01": _pipeline(
            LogisticRegression(C=0.01, class_weight="balanced", max_iter=1000, random_state=GRAINE)
        ),
        "LogReg C=0.1": _pipeline(
            LogisticRegression(C=0.1, class_weight="balanced", max_iter=1000, random_state=GRAINE)
        ),
        "LogReg C=10": _pipeline(
            LogisticRegression(C=10, class_weight="balanced", max_iter=1000, random_state=GRAINE)
        ),
        "Ridge": _pipeline(RidgeClassifier(class_weight="balanced", random_state=GRAINE)),
        "RandomForest": _pipeline(
            RandomForestClassifier(
                n_estimators=200,
                class_weight="balanced",
                random_state=GRAINE,
                n_jobs=-1,
            )
        ),
        "ExtraTrees": _pipeline(
            ExtraTreesClassifier(
                n_estimators=200,
                class_weight="balanced",
                random_state=GRAINE,
                n_jobs=-1,
            )
        ),
        "GradientBoosting": _pipeline(
            GradientBoostingClassifier(n_estimators=100, random_state=GRAINE)
        ),
        "HistGradientBoosting": _pipeline(
            HistGradientBoostingClassifier(
                max_iter=200, class_weight="balanced", random_state=GRAINE
            )
        ),
        "AdaBoost": _pipeline(AdaBoostClassifier(n_estimators=100, random_state=GRAINE)),
        "Bagging": _pipeline(BaggingClassifier(n_estimators=100, random_state=GRAINE, n_jobs=-1)),
        "DecisionTree": _pipeline(
            DecisionTreeClassifier(class_weight="balanced", random_state=GRAINE, max_depth=8)
        ),
    }


def _score_par_ordre(clf: Pipeline, X: np.ndarray) -> np.ndarray:
    """Un score continu par client, plus haut = plus probable de revenir.

    On utilise predict_proba si disponible, sinon decision_function.
    Ridge et certains classifieurs n'ont pas de predict_proba.
    """
    if hasattr(clf, "predict_proba"):
        return clf.predict_proba(X)[:, 1]
    return clf.decision_function(X)


def _evaluer_sur_fenetre(
    modele: Pipeline,
    X_eval: np.ndarray,
    cible: np.ndarray,
    part: float,
) -> dict:
    """Pour une fenêtre et un palier, retourne {trouves, cibles}."""
    scores = _score_par_ordre(modele, X_eval)
    n = len(cible)
    k = max(1, math.ceil(part * n))
    trouves = retours_captes(cible, scores, k)
    return {"trouves": trouves, "cibles": k}


def _evaluer_sur_nombre_fixe(
    modele: Pipeline, X_eval: np.ndarray, cible: np.ndarray, k: int
) -> dict:
    """Pour une fenêtre et un top N fixe."""
    scores = _score_par_ordre(modele, X_eval)
    k_eff = min(k, len(cible))
    return {"trouves": retours_captes(cible, scores, k_eff), "cibles": k_eff}


def _liste_dates(dsn: str | None = None) -> list[date]:
    from common.config import load_settings

    with (
        psycopg2.connect(dsn or load_settings().postgres_dsn) as connexion,
        connexion.cursor() as curseur,
    ):
        curseur.execute("SELECT date_reference FROM dwh.v_dates_reference ORDER BY 1")
        return [ligne[0] for ligne in curseur.fetchall()]


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python -m prediction.comparer_algorithmes",
        description=__doc__.split("\n")[0],
    )
    analyseur.add_argument(
        "--min-positifs",
        type=int,
        default=50,
        help="écarte les fenêtres trop maigres",
    )
    arguments = analyseur.parse_args(argv)

    try:
        donnees = lire()
        verifier_absence_de_fuite(donnees)
        dates = _liste_dates()
    except (psycopg2.Error, ValueError) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    # Prépare les fenêtres d'évaluation
    reference = pd.to_datetime(donnees["date_reference"]).dt.date
    entrainement = donnees[reference == DATE_ENTRAINEMENT]
    if entrainement.empty:
        print(f"ERREUR : pas de données à {DATE_ENTRAINEMENT}", file=sys.stderr)
        return 1

    fenetres = []
    for d in dates:
        if d == DATE_ENTRAINEMENT:
            continue
        bloc = donnees[reference == d]
        if bloc.empty:
            continue
        positifs = int(bloc["a_rachete"].sum())
        if positifs < arguments.min_positifs:
            print(
                f"  Fenêtre {d} écartée : {positifs} positifs < {arguments.min_positifs}",
                file=sys.stderr,
            )
            continue
        fenetres.append((d, bloc))
        print(
            f"  Fenêtre {d} : {len(bloc)} clients, {positifs} positifs",
            file=sys.stderr,
        )

    if not fenetres:
        print("ERREUR : aucune fenêtre exploitable", file=sys.stderr)
        return 1

    # Base poolée pour les gains
    total_clients = sum(len(f[1]) for f in fenetres)
    total_positifs = sum(int(f[1]["a_rachete"].sum()) for f in fenetres)
    base_pool = total_positifs / total_clients

    # Fenêtre de référence pour le tableau B
    fenetre_B = next((f for f in fenetres if f[0] == DATE_EVALUATION), None)
    if fenetre_B is None:
        print(
            f"ATTENTION : fenêtre {DATE_EVALUATION} absente, tableau B désactivé",
            file=sys.stderr,
        )

    X_train = entrainement[list(VARIABLES)].to_numpy()
    y_train = entrainement["a_rachete"].astype(int).to_numpy()

    resultats = []
    for nom, modele in algorithmes().items():
        t0 = time.time()
        try:
            modele.fit(X_train, y_train)
        except Exception as e:  # noqa: BLE001
            print(f"  {nom} : échec entraînement ({e})", file=sys.stderr)
            continue

        # Tableau A — fractions
        gains_A = {}
        for part in PALIERS_FRACTION:
            par_fenetre = []
            for _d, bloc in fenetres:
                X_eval = bloc[list(VARIABLES)].to_numpy()
                y_eval = bloc["a_rachete"].astype(int).to_numpy()
                par_fenetre.append(_evaluer_sur_fenetre(modele, X_eval, y_eval, part))
            pooled = pooler(par_fenetre)
            gain = pooled["precision"] / base_pool
            gains_A[part] = {
                "trouves": pooled["trouves"],
                "cibles": pooled["cibles"],
                "precision": pooled["precision"],
                "gain": gain,
                "wilson": pooled["wilson"],
            }

        # Tableau B — top N fixes, sur 2017-09-30
        gains_B = {}
        if fenetre_B:
            _d_B, bloc_B = fenetre_B
            base_B = int(bloc_B["a_rachete"].sum()) / len(bloc_B)
            for k in PALIERS_FIXES:
                res = _evaluer_sur_nombre_fixe(
                    modele,
                    bloc_B[list(VARIABLES)].to_numpy(),
                    bloc_B["a_rachete"].astype(int).to_numpy(),
                    k,
                )
                gains_B[k] = {
                    "trouves": res["trouves"],
                    "cibles": res["cibles"],
                    "gain": ((res["trouves"] / res["cibles"]) / base_B if res["cibles"] else 0),
                    "wilson": wilson(res["trouves"], res["cibles"]),
                }

        duree = time.time() - t0
        resultats.append(
            {
                "nom": nom,
                "duree_s": duree,
                "gains_A": gains_A,
                "gains_B": gains_B,
            }
        )
        print(f"  {nom} entraîné en {duree:.1f}s", file=sys.stderr)

    # --- Affichage Tableau A ---
    print(f"\n\nBase poolée : {total_positifs} / {total_clients} = {100 * base_pool:.3f} %\n")
    print("Tableau A — Gain au top N poolé, avec intervalle de confiance\n")
    for r in sorted(resultats, key=lambda x: -x["gains_A"][PALIERS_FRACTION[0]]["gain"]):
        print(f"  {r['nom']}")
        for part in PALIERS_FRACTION:
            g = r["gains_A"][part]
            bas_w, haut_w = g["wilson"]
            gain_bas = bas_w / base_pool
            gain_haut = haut_w / base_pool
            print(
                f"    top {part * 100:g}% : {g['gain']:.2f}x "
                f"[{gain_bas:.2f}x ; {gain_haut:.2f}x] "
                f"({g['trouves']}/{g['cibles']})"
            )
        print()

    # --- Affichage Tableau B ---
    if fenetre_B:
        d_B, bloc_B = fenetre_B
        base_B = int(bloc_B["a_rachete"].sum()) / len(bloc_B)
        print(f"\nTableau B — Gain au top N fixe ({d_B}, base {100 * base_B:.3f} %)\n")
        entete = f"  {'Algorithme':<24}"
        for k in PALIERS_FIXES:
            entete += f" {'top ' + str(k):>16}"
        print(entete)
        print("  " + "-" * (24 + 17 * len(PALIERS_FIXES)))

        # Tri par gain au top 250 (référence documentée à 3,55x)
        for r in sorted(
            resultats,
            key=lambda x: -x["gains_B"].get(250, {}).get("gain", 0) if x["gains_B"] else 0,
        ):
            ligne = f"  {r['nom']:<24}"
            for k in PALIERS_FIXES:
                g = r["gains_B"].get(k)
                if g:
                    ligne += f" {g['gain']:>14.2f}x"
            print(ligne)

        # Règle 2+ : uniquement au volume 711 (son volume naturel au
        # 2017-09-30). Aux autres paliers, la règle n'est pas définie
        # comme un top N — elle sélectionne tous les clients à 2+ commandes.
        cible_B = bloc_B["a_rachete"].astype(int).to_numpy()
        masque_regle = (bloc_B["commandes"] >= 2).to_numpy()
        trouves_711 = int(cible_B[masque_regle].sum())
        cibles_711 = int(masque_regle.sum())
        gain_711 = (trouves_711 / cibles_711) / base_B if cibles_711 else 0
        print(
            f"\n  Règle 2+ commandes : {trouves_711} / {cibles_711} "
            f"= gain {gain_711:.2f}x (volume naturel {cibles_711})"
        )

    # --- Référence règle 2+ poolée ---
    print("\nRappel — règle 2+ commandes (poolée) :")
    par_fenetre_regle = []
    for _d, bloc in fenetres:
        masque = (bloc["commandes"] >= 2).to_numpy()
        par_fenetre_regle.append(
            {
                "trouves": int(bloc["a_rachete"].astype(int).to_numpy()[masque].sum()),
                "cibles": int(masque.sum()),
            }
        )
    pooled_regle = pooler(par_fenetre_regle)
    print(
        f"  {pooled_regle['trouves']} / {pooled_regle['cibles']} "
        f"= {100 * pooled_regle['precision']:.2f} %, "
        f"gain {pooled_regle['precision'] / base_pool:.2f}x "
        f"[{pooled_regle['wilson'][0] / base_pool:.2f}x ; "
        f"{pooled_regle['wilson'][1] / base_pool:.2f}x]"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
