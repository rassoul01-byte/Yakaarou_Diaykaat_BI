"""Déduplication avec comptage : rien n'est supprimé sans être compté.

Une suppression silencieuse non comptée est une donnée perdue sans trace : la
fonction renvoie toujours, avec le résultat, le nombre de lignes retirées, qui est
ensuite écrit dans le journal des exécutions.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def dedupliquer(
    lignes: pd.DataFrame, cles: Sequence[str] | None = None
) -> tuple[pd.DataFrame, int]:
    """Supprime les doublons et renvoie `(lignes_conservees, nombre_supprime)`.

    - `cles=None` : doublon strict, toutes les colonnes identiques (cas de la
      géolocalisation : 261 831 lignes sur 1 000 163) ;
    - `cles=[...]` : doublon sur clé métier explicite.

    La première occurrence est conservée, dans l'ordre d'origine : deux exécutions
    sur les mêmes données donnent exactement le même résultat.
    """
    conservees = lignes.drop_duplicates(subset=list(cles) if cles else None, keep="first")
    return conservees, len(lignes) - len(conservees)
