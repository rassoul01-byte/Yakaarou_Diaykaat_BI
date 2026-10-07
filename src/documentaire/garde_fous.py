"""Garde-fous appliqués avant la recherche : questions hors périmètre de la FAQ."""

import re

# Numéro de 3 chiffres ou plus : « commande 4521 », « CMD-4521 », « colis #98765 ».
# « 3 fois » ou « 30 jours » ne sont pas concernés.
NUMERO = re.compile(r"(?<!\d)\d{3,}(?!\d)")

# Montant avec devise : « 50 euros », « 10 000 FCFA », « € 20 », « R$ 15 ».
MONTANT = re.compile(
    r"(?:\d[\d\s.,]*\s*(?:€|\$|r\$|(?:euros?|eur|f\s?cfa|fcfa|xof|cfa|usd|reais|brl)(?!\w))"
    r"|(?:€|\$|r\$)\s*\d)",
    re.IGNORECASE,
)


def motif_de_refus(question: str) -> str | None:
    """Renvoie « commande_precise » ou « montant » si la question doit être refusée, sinon None."""
    if MONTANT.search(question):
        return "montant"
    if NUMERO.search(question):
        return "commande_precise"
    return None
