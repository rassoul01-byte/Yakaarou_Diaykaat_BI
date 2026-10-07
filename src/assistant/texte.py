"""Normalisation du texte, partagée par la recherche et les garde-fous."""

from __future__ import annotations

import re
import unicodedata


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation remplacée par des espaces."""
    decompose = unicodedata.normalize("NFD", (texte or "").lower())
    sans_accent = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sans_accent)).strip()
