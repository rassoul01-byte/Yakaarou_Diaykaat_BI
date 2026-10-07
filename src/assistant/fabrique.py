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

# Seuils de la recherche vectorielle, mesurés sur le jeu gelé (62 questions)
# le 2026-10-07 (SHA256 786dada1d1874e139d0376b7ff148c957762ffa16a77d1524f99c3700f4e0dbd).
# Contraintes respectées : mauvais_passage=0, réponse_à_tort=0.
# Résultats : 6 bonnes réponses, 23 suggestions, 2 faux refus (q05, s07 :
# leur passage n'est pas dans le top 5 — limite du retrouveur).
# Marge à 0 : les scores du retrouveur sont très serrés entre les top passages.
SEUILS_EXTERNE = Seuils(reponse=0.84, suggestion=0.20, marge=0.00)


def _recherche_documentaire(question: str, k: int) -> dict:
    """Adapte documentaire.rechercher au contrat passages.md §7.

    Import et création du client tardifs : le mode depannage reste hors ligne.
    Les erreurs réseau d'Elasticsearch (TransportError et ses sous-classes :
    ConnectionError, ConnectionTimeout) sont converties en ConnectionError
    native pour que __main__ les présente proprement.
    """
    from elastic_transport import TransportError

    from documentaire.rechercher import rechercher
    from recherche.client import connexion

    try:
        return rechercher(connexion(), question, k)
    except TransportError as erreur:
        raise ConnectionError(str(erreur)) from erreur


def creer_retrouveur() -> Retrouveur:
    """Rend le retrouveur à utiliser, selon `ASSISTANT_RETROUVEUR` (défaut : externe)."""
    choix = os.getenv("ASSISTANT_RETROUVEUR", "externe").strip().lower()
    if choix == "externe":
        return RetrouveurExterne(_recherche_documentaire, SEUILS_EXTERNE)
    if choix == "depannage":
        return RetrouveurDepannage.depuis_faq()
    raise ValueError(f"ASSISTANT_RETROUVEUR={choix!r} inconnu (attendu : 'externe' ou 'depannage')")
