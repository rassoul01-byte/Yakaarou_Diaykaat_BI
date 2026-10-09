"""Statistiques inférentielles pour l'évaluation du modèle de ré-achat.

Intervalle de Wilson sur une proportion : adapté aux proportions faibles
(quelques succès sur des milliers), là où l'approximation normale donne
des bornes négatives et inutilisables.
"""

from __future__ import annotations

from math import sqrt


def wilson(succes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance à 95 % sur une proportion, méthode de Wilson.

    Retourne (borne_basse, borne_haute) sur la proportion, dans [0, 1].

    Exemple : wilson(8, 100) → (0.0412, 0.1503)

    Référence : Wilson, E. B. (1927). Probable inference, the law of
    succession, and statistical inference. JASA, 22(158), 209-212.
    """
    if n <= 0:
        return (0.0, 0.0)
    if succes < 0 or succes > n:
        raise ValueError(f"succes={succes} hors de [0, {n}]")

    p = succes / n
    denominateur = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominateur
    demi = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominateur
    return (max(0.0, centre - demi), centre + demi)


def gain_avec_intervalle(
    succes: int, n_cibles: int, base: float, z: float = 1.96
) -> tuple[float, float, float]:
    """Gain (précision / base) et son intervalle de confiance.

    Paramètres
    ----------
    succes : int
        Nombre de positifs trouvés dans le top.
    n_cibles : int
        Nombre de clients ciblés (taille du top).
    base : float
        Prévalence dans la population (positifs / population).
    z : float
        Quantile normal pour le niveau de confiance (1.96 pour 95 %).

    Retourne
    --------
    (gain_central, gain_bas, gain_haut)
    """
    if base <= 0:
        raise ValueError("base doit être strictement positive")
    if n_cibles <= 0:
        return (0.0, 0.0, 0.0)

    bas, haut = wilson(succes, n_cibles, z)
    central = succes / n_cibles / base
    return (central, bas / base, haut / base)


def pooler(fenetres: list[dict]) -> dict:
    """Agrège plusieurs fenêtres par sommes, pas par moyenne de gains.

    Chaque fenêtre est un dict avec au moins `trouves` et `cibles`.
    On somme les trouvés sur les cibles, puis on applique Wilson une fois
    sur le total. C'est ce qui resserre l'intervalle — moyenner des gains
    ne le fait pas.

    Retourne un dict avec `trouves`, `cibles`, `precision`, `wilson`.
    """
    total_trouves = sum(f["trouves"] for f in fenetres)
    total_cibles = sum(f["cibles"] for f in fenetres)
    if total_cibles == 0:
        return {
            "trouves": 0,
            "cibles": 0,
            "precision": 0.0,
            "wilson": (0.0, 0.0),
        }
    return {
        "trouves": total_trouves,
        "cibles": total_cibles,
        "precision": total_trouves / total_cibles,
        "wilson": wilson(total_trouves, total_cibles),
    }
