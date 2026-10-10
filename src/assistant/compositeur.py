"""Le compositeur : la réponse est le texte du passage, pas une rédaction.

Rien n'est généré. La réponse d'une question couverte est la réponse écrite dans la
foire aux questions, suivie de sa citation. C'est ce qui rend « aucune information absente
des passages cités » vrai par construction, et non par vérification.

Les textes de refus sont fixes et écrits ici. Aucun ne contient d'adresse, de numéro de
téléphone ni de lien : le corpus n'en contient aucun, et on n'en invente pas.
"""

from __future__ import annotations

from . import garde_fous as g
from .passages import Passage

_SERVICE_CLIENT = "contacter le service client"

REFUS: dict[str, str] = {
    g.PRIX: (
        "Je n'ai pas d'information sur les prix. Pour connaître le prix d'un article, "
        f"veuillez consulter sa fiche ou {_SERVICE_CLIENT}."
    ),
    g.COMMANDE_PRECISE: (
        "Je ne peux pas consulter une commande en particulier. Pour une question sur votre commande, "
        f"veuillez {_SERVICE_CLIENT}, en vous munissant de son numéro."
    ),
    g.REMBOURSEMENT_PERSONNALISE: (
        "Je ne peux pas traiter un remboursement personnalisé. Pour une demande liée à votre situation, "
        f"veuillez {_SERVICE_CLIENT}."
    ),
    g.QUESTION_INVALIDE: (
        "Je n'ai pas compris votre question. Pouvez-vous la reformuler en une phrase courte ?"
    ),
    g.AUCUN_PASSAGE: (
        "Je n'ai trouvé aucune information correspondant à votre question. "
        f"Pour une réponse adaptée, veuillez {_SERVICE_CLIENT}."
    ),
    g.HORS_BASE: (
        "Je ne peux pas répondre à cette question avec les informations dont je dispose. "
        f"Pour une réponse adaptée, veuillez {_SERVICE_CLIENT}."
    ),
    g.INCERTAIN: (
        "Je ne suis pas certain d'avoir compris votre question. "
        "Voulez-vous dire l'une de celles-ci ? Sinon, "
        f"veuillez {_SERVICE_CLIENT}."
    ),
}


def citation(passage: Passage) -> str:
    return f"[{passage.id}]"


def composer(passage: Passage) -> str:
    """La réponse : le texte du passage, suivi de sa citation."""
    return f"{passage.reponse} {citation(passage)}"


def refuser(motif: str) -> str:
    return REFUS[motif]
