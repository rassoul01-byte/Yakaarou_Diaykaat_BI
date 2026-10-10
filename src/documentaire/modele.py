"""Le modèle de vecteurs (fastembed).

Importé à la demande : les tests unitaires n'ont pas besoin de la bibliothèque
ni du téléchargement du modèle (environ 200 Mo, une seule fois).
"""

from __future__ import annotations

from functools import lru_cache

from .schema import MODELE


@lru_cache(maxsize=1)
def _modele():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=MODELE)


def vectoriser(textes: list[str]) -> list[list[float]]:
    """Un vecteur par texte, dans le même ordre."""
    return [[float(x) for x in vecteur] for vecteur in _modele().embed(textes)]
