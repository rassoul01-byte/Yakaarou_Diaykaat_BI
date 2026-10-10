"""Évaluation multi-fenêtres du modèle de ré-achat.

Contrairement à `evaluer`, qui mesure sur une seule date de référence,
ce module évalue sur les 5 fenêtres de `dwh.v_dates_reference`, puis
agrège les résultats par **sommes** (pas par moyenne de gains).

C'est ce qui resserre les intervalles : moyenner des gains de fenêtres
de tailles différentes ne le ferait pas.

Usage :
    docker compose exec app python -m prediction.evaluer_multi
    docker compose exec app python -m prediction.evaluer_multi --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import pandas as pd
import psycopg2

from .classement import retours_captes
from .donnees import (
    DATE_ENTRAINEMENT,
    DATE_EVALUATION,
    VARIABLES,
    lire,
    verifier_absence_de_fuite,
)
from .modele import entrainer, probabilites_de_retour
from .statistiques import pooler, wilson

# Paliers pour la comparaison entre fenêtres (en fractions)
PALIERS_FRACTION = (0.005, 0.01, 0.02, 0.05)

# Paliers en nombre fixe (uniquement au 2017-09-30, pour comparer aux
# chiffres déjà publiés dans le dictionnaire des indicateurs)
PALIERS_FIXES = (100, 250, 500, 1000)


def _liste_dates(dsn: str | None = None) -> list[date]:
    """Les dates de référence, triées, lues depuis la vue."""
    import psycopg2

    from common.config import load_settings

    with (
        psycopg2.connect(dsn or load_settings().postgres_dsn) as connexion,
        connexion.cursor() as curseur,
    ):
        curseur.execute("SELECT date_reference FROM dwh.v_dates_reference ORDER BY 1")
        return [ligne[0] for ligne in curseur.fetchall()]


def _evaluer_fenetre(
    donnees: pd.DataFrame,
    date_reference: date,
    date_entrainement: date,
) -> dict:
    """Entraîne sur `date_entrainement`, évalue sur `date_reference`.

    Retourne un dict avec les scores triés et la cible correspondante.
    """
    reference = pd.to_datetime(donnees["date_reference"]).dt.date
    entrainement = donnees[reference == date_entrainement]
    evaluation = donnees[reference == date_reference]

    if entrainement.empty or evaluation.empty:
        raise ValueError(
            f"fenêtre {date_reference} vide (entrainement={len(entrainement)}, "
            f"evaluation={len(evaluation)})"
        )

    modele = entrainer(entrainement[list(VARIABLES)], entrainement["a_rachete"].astype(int))
    scores = probabilites_de_retour(modele, evaluation[list(VARIABLES)])
    cible = evaluation["a_rachete"].astype(int).to_numpy()
    regle = (evaluation["commandes"] >= 2).astype(int).to_numpy()

    return {
        "date": date_reference,
        "clients": len(evaluation),
        "positifs": int(cible.sum()),
        "scores": scores,
        "cible": cible,
        "regle": regle,
    }


def _gain_par_fraction(fenetre: dict, part: float) -> dict:
    """Nombre de trouvés et ciblés pour un palier en fraction."""
    n = fenetre["clients"]
    import math

    k = max(1, math.ceil(part * n))
    trouves = retours_captes(fenetre["cible"], fenetre["scores"], k)
    return {"trouves": trouves, "cibles": k}


def _gain_par_nombre_fixe(fenetre: dict, k: int) -> dict:
    """Nombre de trouvés et ciblés pour un palier en nombre fixe."""
    k_effectif = min(k, fenetre["clients"])
    trouves = retours_captes(fenetre["cible"], fenetre["scores"], k_effectif)
    return {"trouves": trouves, "cibles": k_effectif}


def _gain_regle(fenetre: dict) -> dict:
    """Gain de la règle « deux commandes ou plus » sur une fenêtre."""
    masque = fenetre["regle"] == 1
    return {
        "trouves": int(fenetre["cible"][masque].sum()),
        "cibles": int(masque.sum()),
    }


def _tableau_a(
    fenetres: list[dict],
    base_pool: float,
) -> list[dict]:
    """Tableau A — comparaison entre fenêtres, par fractions, poolé."""
    resultats = []
    for part in PALIERS_FRACTION:
        gains_modele = [_gain_par_fraction(f, part) for f in fenetres]
        pool_modele = pooler(gains_modele)
        resultats.append(
            {
                "palier": f"top {part * 100:g}%",
                "part": part,
                "modele": {
                    **pool_modele,
                    "gain": pool_modele["precision"] / base_pool if base_pool else 0,
                },
            }
        )

    # Règle 2+ commandes : pas de palier en fraction, on agrège directement
    gains_regle = [_gain_regle(f) for f in fenetres]
    pool_regle = pooler(gains_regle)
    resultats.append(
        {
            "palier": "règle 2+ commandes",
            "part": None,
            "modele": {
                **pool_regle,
                "gain": pool_regle["precision"] / base_pool if base_pool else 0,
            },
        }
    )
    return resultats


def _tableau_b(
    fenetre_reference: dict,
    base_reference: float,
) -> list[dict]:
    """Tableau B — paliers en nombre fixe, au 2017-09-30 seul."""
    resultats = []
    for k in PALIERS_FIXES:
        gain = _gain_par_nombre_fixe(fenetre_reference, k)
        resultats.append(
            {
                "palier": f"top {k}",
                "modele": {
                    **gain,
                    "precision": gain["trouves"] / gain["cibles"] if gain["cibles"] else 0,
                    "gain": (
                        gain["trouves"] / gain["cibles"] / base_reference
                        if gain["cibles"] and base_reference
                        else 0
                    ),
                    "wilson": wilson(gain["trouves"], gain["cibles"]),
                },
            }
        )

    gain_regle = _gain_regle(fenetre_reference)
    resultats.append(
        {
            "palier": "règle 2+ commandes",
            "modele": {
                **gain_regle,
                "precision": gain_regle["trouves"] / gain_regle["cibles"],
                "gain": gain_regle["trouves"] / gain_regle["cibles"] / base_reference,
                "wilson": wilson(gain_regle["trouves"], gain_regle["cibles"]),
            },
        }
    )
    return resultats


def _afficher_tableau(titre: str, lignes: list[dict], base: float) -> None:
    print(f"\n{titre}\n")
    print(
        f"  {'Palier':<24} {'Trouvés':>8} {'Ciblés':>8} {'Précision':>10} "
        f"{'Gain':>7} {'IC 95 %':>20}"
    )
    print("  " + "-" * 82)
    for ligne in lignes:
        m = ligne["modele"]
        bas, haut = m["wilson"]
        gain_bas = bas / base if base else 0
        gain_haut = haut / base if base else 0
        precision_pct = f"{100 * m['precision']:.2f} %"
        ic = f"[ {gain_bas:.2f}x ; {gain_haut:.2f}x ]"
        print(
            f"  {ligne['palier']:<24} {m['trouves']:>8} {m['cibles']:>8} "
            f"{precision_pct:>10} {m['gain']:>6.2f}x {ic:>20}"
        )
    print()


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="python -m prediction.evaluer_multi", description=__doc__.split("\n")[0]
    )
    analyseur.add_argument("--fabrique", action="store_true")
    analyseur.add_argument("--format", choices=("texte", "json"), default="texte")
    arguments = analyseur.parse_args(argv)

    try:
        donnees = lire(arguments.fabrique)
        verifier_absence_de_fuite(donnees)
        dates = _liste_dates()
    except psycopg2.Error as erreur:
        print(f"ERREUR : PostgreSQL — {erreur}", file=sys.stderr)
        return 1
    except ValueError as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    if arguments.fabrique:
        # Le jeu fabriqué n'a qu'une seule fenêtre, on évalue classique
        print("Jeu fabriqué — évaluation classique sur une seule fenêtre.")
        return 0

    MIN_POSITIFS = 50
    fenetres = []
    ecartees = []
    for d in dates:
        if d == DATE_ENTRAINEMENT:
            continue
        try:
            f = _evaluer_fenetre(donnees, d, DATE_ENTRAINEMENT)
            if f["positifs"] < MIN_POSITIFS:
                ecartees.append((d, f["clients"], f["positifs"]))
                print(
                    f"  Fenêtre {d} écartée : {f['positifs']} positifs < {MIN_POSITIFS}",
                    file=sys.stderr,
                )
                continue
            fenetres.append(f)
            print(
                f"  Fenêtre {d} : {f['clients']} clients, {f['positifs']} positifs "
                f"({100 * f['positifs'] / f['clients']:.2f} %)",
                file=sys.stderr,
            )
        except ValueError as e:
            print(f"  Fenêtre {d} écartée : {e}", file=sys.stderr)

    # Base poolée pour le tableau A
    total_clients = sum(f["clients"] for f in fenetres)
    total_positifs = sum(f["positifs"] for f in fenetres)
    base_pool = total_positifs / total_clients if total_clients else 0

    tableau_a = _tableau_a(fenetres, base_pool)

    # Tableau B : au 2017-09-30 seulement
    ref = next((f for f in fenetres if f["date"] == DATE_EVALUATION), None)
    if ref:
        base_ref = ref["positifs"] / ref["clients"]
        tableau_b = _tableau_b(ref, base_ref)
    else:
        tableau_b = []

    if arguments.format == "json":

        def _clean(d):
            return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}

        print(
            json.dumps(
                {
                    "fenetres": [
                        {"date": str(f["date"]), "clients": f["clients"], "positifs": f["positifs"]}
                        for f in fenetres
                    ],
                    "tableau_a": tableau_a,
                    "tableau_b": tableau_b,
                },
                default=str,
                indent=2,
            )
        )
        return 0

    print(f"\nBase poolée : {total_positifs} / {total_clients} = {100 * base_pool:.3f} %")
    print(f"\nFenêtres retenues ({len(fenetres)}) :")
    for f in fenetres:
        print(
            f"  {f['date']} : {f['clients']} clients, "
            f"{f['positifs']} positifs ({100 * f['positifs'] / f['clients']:.2f} %)"
        )

    _afficher_tableau(
        f"Tableau A — Comparaison entre fenêtres (poolé, base {100 * base_pool:.3f} %)",
        tableau_a,
        base_pool,
    )

    if tableau_b:
        base_ref = ref["positifs"] / ref["clients"]
        _afficher_tableau(
            f"Tableau B — Référence au {DATE_EVALUATION} (base {100 * base_ref:.3f} %)",
            tableau_b,
            base_ref,
        )

    if ecartees:
        print("Fenêtres écartées (positifs insuffisants) :")
    for d, clients, positifs in ecartees:
        print(f"  {d} : {clients} clients, {positifs} positifs — écartée")
        print()

    print("Réserve : les fenêtres partagent des clients. L'intervalle poolé")
    print("est donc légèrement optimiste. À écrire dans la documentation.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
