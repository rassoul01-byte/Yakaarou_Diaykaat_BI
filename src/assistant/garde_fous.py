"""Les garde-fous : quand l'assistant refuse, et pourquoi.

Deux étapes, dans cet ordre :

  A. AVANT la recherche, des règles de refus pour ce que la base ne contiendra jamais
     (un prix, une commande précise, un remboursement chiffré). Déterministes, testables.
  B. APRÈS la recherche, une décision sur les scores : répondre, hésiter, ou refuser.

Un refus est une réponse correcte, pas un échec. Aucune de ces règles ne génère de texte.

Frontière « général » ou « personnel » : « Quel est le délai de remboursement ? » est
général, la base y répond. « Rembourse-moi 50 euros pour la commande 8f3a2c » est personnel,
la base ne peut rien en dire. La règle A ne refuse que sur un signe explicite de
personnalisation (identifiant, montant, impératif) : dans le doute, elle laisse passer et
c'est le seuil de la recherche qui tranche.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .passages import Passage
from .texte import normaliser

# Motifs de refus : valeurs stables, écrites dans le journal et le contrat.
PRIX = "prix"
COMMANDE_PRECISE = "commande_precise"
REMBOURSEMENT_PERSONNALISE = "remboursement_personnalise"
QUESTION_INVALIDE = "question_invalide"
AUCUN_PASSAGE = "aucun_passage"
HORS_BASE = "hors_base"
INCERTAIN = "incertain"

LONGUEUR_MAX = 500


@dataclass(frozen=True)
class Seuils:
    """Propres à chaque recherche : un score n'a pas la même échelle d'une recherche à l'autre."""

    reponse: float  # en dessous, on ne répond jamais
    suggestion: float  # entre les deux seuils, on propose sans affirmer
    marge: float  # écart minimal entre le premier et le deuxième passage pour répondre

    def __post_init__(self) -> None:
        if not 0 <= self.suggestion <= self.reponse <= 1 or self.marge < 0:
            raise ValueError(f"seuils incohérents : {self}")


@dataclass(frozen=True)
class Decision:
    retenu: Passage | None = None  # le passage qui répond, ou None
    motif: str | None = None  # le motif du refus, ou None si l'on répond
    suggestions: list[Passage] = field(default_factory=list)


# ------------------------------------------------------------------ A. avant

# Les prix : le catalogue n'en contient aucun (décision F4.3).
_PRIX = re.compile(
    r"\b(combien (ca |cela |il )?(coute|coutent|vaut|valent)|"
    r"quel(s)? (est|sont) (le |les |son |leur )?(prix|tarif|tarifs)|"
    r"(le )?(prix|tarif|tarifs) (de|du|des|d)|a quel prix)\b"
)
# « Combien coûte un retour ? » ou « le prix de la livraison ? » : la base y répond.
_FRAIS = re.compile(r"\b(retour|retourner|livraison|port|envoi|expedition|frais|abonnement)\b")

_CONTEXTE_COMMANDE = re.compile(
    r"\b(commande|colis|order|numero|num|n|no|ref|reference|suivi|tracking|paiement|facture)\b"
)
_MONTANT = re.compile(
    r"(\d[\d\s.,]*\s?(€|euros?|eur\b|reais?|r\$|\$|usd|fcfa|cfa))|([€$]\s?\d)", re.IGNORECASE
)
_IMPERATIF_REMBOURSEMENT = re.compile(
    r"\b(rembourse|remboursez)\s+(moi|nous)\b|\bje (veux|voudrais|souhaite|exige) (etre )?rembourse\b"
)


def _identifiant_present(normalisee: str) -> bool:
    """Un numéro de commande, de colis ou de paiement : un mot de 3 chiffres ou plus, qui n'est pas une année."""
    for mot in normalisee.split():
        chiffres = sum(c.isdigit() for c in mot)
        if chiffres >= 3 and not re.fullmatch(r"(19|20)\d{2}", mot):
            return True
    return False


def filtre_avant(question: str) -> str | None:
    """Le motif de refus si la question est hors périmètre avant toute recherche, sinon None."""
    texte = (question or "").strip()
    if not texte or len(texte) > LONGUEUR_MAX:
        return QUESTION_INVALIDE
    normalisee = normaliser(texte)
    if not normalisee:
        return QUESTION_INVALIDE

    if _identifiant_present(normalisee) and _CONTEXTE_COMMANDE.search(normalisee):
        return COMMANDE_PRECISE
    if "rembours" in normalisee and (
        _MONTANT.search(texte.lower()) or _IMPERATIF_REMBOURSEMENT.search(normalisee)
    ):
        return REMBOURSEMENT_PERSONNALISE
    if _PRIX.search(normalisee) and not _FRAIS.search(normalisee):
        return PRIX
    return None


# ------------------------------------------------------------------ B. après


def decider(passages: list[Passage], seuils: Seuils) -> Decision:
    """Répondre, hésiter ou refuser, d'après les scores des passages (triés du meilleur au pire)."""
    if not passages:
        return Decision(motif=AUCUN_PASSAGE)

    meilleur = passages[0]
    suivant = passages[1].score if len(passages) > 1 else 0.0

    if meilleur.score >= seuils.reponse and meilleur.score - suivant >= seuils.marge:
        return Decision(retenu=meilleur)
    if meilleur.score >= seuils.suggestion:
        proches = [p for p in passages if p.score >= seuils.suggestion][:3]
        return Decision(motif=INCERTAIN, suggestions=proches)
    return Decision(motif=HORS_BASE)
