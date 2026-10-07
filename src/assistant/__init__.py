"""Assistant client local (F5.3 à F5.6) : il sélectionne et cite, il ne rédige pas.

Une question entre ; l'assistant retrouve des passages de la foire aux questions,
et soit répond avec le texte du passage retenu et sa citation, soit refuse. Aucun
texte n'est généré : une réponse est exacte par construction.

    from assistant import repondre
    from assistant.retrouveur import RetrouveurDepannage
    reponse = repondre("Comment suivre ma commande ?", RetrouveurDepannage.depuis_faq())

Contrat : docs/contrats/assistant.md.
"""

from .assistant import Reponse, repondre

__all__ = ["Reponse", "repondre"]
