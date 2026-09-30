"""Détection de la langue des fiches produits.

Défaut mesuré : le catalogue n'est pas intégralement francophone (62 % de français,
22 % d'anglais, 6,5 % d'allemand sur un échantillon de 3 000 désignations). Il est
conservé en entier : la langue devient un attribut du produit, elle ne filtre rien.
"""

from __future__ import annotations

from langdetect import DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Valeur écrite quand aucune langue ne peut être déterminée (texte vide, chiffres seuls).
# Elle garantit que la langue est renseignée pour TOUTES les fiches.
LANGUE_INCONNUE = "inconnue"

# langdetect tire au hasard : sans graine fixe, deux exécutions peuvent donner deux
# résultats sur un texte court. Graine fixée, résultat reproductible — c'est ce qui
# rend la transformation rejouable à l'identique.
DetectorFactory.seed = 0


def detecter_langue(texte: str | None) -> str:
    """Renvoie le code de langue ISO 639-1 (`fr`, `en`, `de`…), ou `inconnue`."""
    if texte is None or not texte.strip():
        return LANGUE_INCONNUE
    try:
        from langdetect import detect

        return detect(texte)
    except LangDetectException:
        return LANGUE_INCONNUE
