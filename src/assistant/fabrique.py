"""Choix du retrouveur de passages.

Par défaut, l'assistant utilise la recherche de Seydina (`RetrouveurExterne`,
contrat passages.md §7), adossée à l'index Elasticsearch alimenté par
`documentaire.indexer`. Le retrouveur de dépannage (TF-IDF en mémoire) reste
accessible pour les tests hors ligne et les diagnostics, via la variable
d'environnement `ASSISTANT_RETROUVEUR=depannage`.
"""

from __future__ import annotations

import os

from .garde_fous import Seuils
from .retrouveur import Retrouveur, RetrouveurDepannage, RetrouveurExterne

# Seuils de la recherche vectorielle. PROVISOIRES : repris du dépannage en
# attendant la remesure sur le jeu gelé (passages.md §8). Échelle cosinus,
# plus haut = plus proche.
# TODO(F5): remplacer par les seuils mesurés sur le jeu gelé.
SEUILS_EXTERNE = Seuils(reponse=0.35, suggestion=0.18, marge=0.12)


def _recherche_documentaire(question: str, k: int) -> dict:
    """Adapte `documentaire.rechercher` au contrat passages.md §7.

    Import et création du client tardifs : utiliser le retrouveur de dépannage
    ne doit pas exiger qu'Elasticsearch soit joignable.
    """
    from documentaire.rechercher import rechercher
    from recherche.client import connexion

    return rechercher(connexion(), question, k)


def creer_retrouveur() -> Retrouveur:
    """Rend le retrouveur à utiliser, selon `ASSISTANT_RETROUVEUR` (défaut : externe)."""
    choix = os.getenv("ASSISTANT_RETROUVEUR", "externe").strip().lower()
    if choix == "externe":
        return RetrouveurExterne(_recherche_documentaire, SEUILS_EXTERNE)
    if choix == "depannage":
        return RetrouveurDepannage.depuis_faq()
    raise ValueError(f"ASSISTANT_RETROUVEUR={choix!r} inconnu (attendu : 'externe' ou 'depannage')")
