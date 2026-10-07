"""Mesures de classement du modèle de ré-achat, indépendantes du seuil.

Le F1 est calculé à un seuil unique (0,5), choisi sans justification forte.
Ces mesures jugent l'ordre des clients : le modèle met-il en haut de la liste
ceux qui reviennent vraiment ? Elles se comparent au taux de base et à la règle
« deux commandes ou plus », au même nombre de clients signalés.
"""

from __future__ import annotations

import math

import numpy as np
from sklearn.metrics import average_precision_score


def _verifier(y_vrai, scores):
    y = np.asarray(y_vrai).astype(int)
    s = np.asarray(scores, dtype=float)
    if y.ndim != 1 or s.ndim != 1 or len(y) != len(s):
        raise ValueError("y_vrai et scores doivent être deux vecteurs de même longueur")
    if len(y) == 0:
        raise ValueError("aucun client à évaluer")
    if y.sum() == 0:
        raise ValueError("aucun client revenu : les mesures de classement n'ont pas de sens")
    return y, s


def _ordre(scores):
    """Du plus au moins probable ; à score égal, l'ordre d'origine (déterministe)."""
    return np.argsort(-scores, kind="stable")


def retours_captes(y_vrai, scores, volume):
    """Nombre de clients revenus parmi les `volume` clients les mieux classés."""
    y, s = _verifier(y_vrai, scores)
    volume = int(min(max(volume, 0), len(y)))
    return int(y[_ordre(s)[:volume]].sum())


def mesures_classement(y_vrai, scores, regle=None, part=0.10):
    """Mesures de classement ; `regle` est un vecteur 0/1 (ex. deux commandes ou plus)."""
    if not 0 < part <= 1:
        raise ValueError("part doit être comprise entre 0 (exclu) et 1")
    y, s = _verifier(y_vrai, scores)
    n, revenus = len(y), int(y.sum())
    base = revenus / n
    ap = float(average_precision_score(y, s))

    k_part = max(1, math.ceil(part * n))
    captes_part = retours_captes(y, s, k_part)

    m = {
        "clients": n,
        "revenus": revenus,
        "taux_base": base,
        "precision_moyenne": ap,
        "gain_precision_moyenne": ap / base,
        "part": part,
        "volume_part": k_part,
        "captes_part": captes_part,
        "capture_part": captes_part / revenus,
        "capture_hasard": part,
    }

    if regle is not None:
        r = np.asarray(regle).astype(int)
        if len(r) != n:
            raise ValueError("regle doit avoir la même longueur que y_vrai")
        volume = int(r.sum())
        captes_regle = int(y[r == 1].sum())
        captes_modele = retours_captes(y, s, volume) if volume else 0
        m.update(
            {
                "volume_regle": volume,
                "captes_regle": captes_regle,
                "rappel_regle": captes_regle / revenus,
                "captes_modele_meme_volume": captes_modele,
                "rappel_modele_meme_volume": captes_modele / revenus,
            }
        )
    return m


def _pct(x):
    return f"{100 * x:.1f} %".replace(".", ",")


def lignes_rapport(m):
    """Texte français prêt à afficher, avec la lecture honnête des chiffres."""
    lignes = [
        "  Qualité du classement (indépendante du seuil)",
        "",
        f"    Taux de base (revenus / clients)     : {_pct(m['taux_base'])}",
        (
            f"    Précision moyenne du modèle          : {m['precision_moyenne']:.3f}"
            f"   (x{m['gain_precision_moyenne']:.1f} le taux de base ; 1,0 = hasard)"
        ),
        (
            f"    Parmi les {_pct(m['part'])} de clients les mieux classés "
            f"({m['volume_part']}) : {m['captes_part']} revenus sur {m['revenus']}"
            f" = {_pct(m['capture_part'])} des retours (hasard : {_pct(m['capture_hasard'])})"
        ),
    ]
    if "volume_regle" in m:
        lignes += [
            "",
            f"    À volume égal ({m['volume_regle']} clients signalés) :",
            (
                f"      règle « deux commandes ou plus » : {m['captes_regle']} revenus"
                f" (rappel {_pct(m['rappel_regle'])})"
            ),
            (
                f"      modèle, mêmes {m['volume_regle']} mieux classés : "
                f"{m['captes_modele_meme_volume']} revenus"
                f" (rappel {_pct(m['rappel_modele_meme_volume'])})"
            ),
        ]
    return lignes
