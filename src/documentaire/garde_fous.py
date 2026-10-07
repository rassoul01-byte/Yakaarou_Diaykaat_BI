"""Garde-fous appliqués avant la recherche : questions hors périmètre de la FAQ."""

import re

# Numéro de 3 chiffres ou plus : « commande 4521 », « CMD-4521 », « colis #98765 ».
# « 3 fois » ou « 30 jours » ne sont pas concernés.
NUMERO = re.compile(r"(?<!\d)\d{3,}(?!\d)")

# Référence avec lettres : « commande numéro 8f3a2c ». Le mot qui suit « commande »,
# « colis » ou « numéro » doit contenir un chiffre (« numéro de commande » passe).
REFERENCE = re.compile(
    r"\b(?:commande|colis|cmd|n°|num[ée]ro|#)\s*(?:de\s+)?(?:n°|num[ée]ro|#)?\s*:?\s*"
    r"(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{4,}",
    re.IGNORECASE,
)

# Montant avec devise : « 50 euros », « 10 000 FCFA », « € 20 », « R$ 15 ».
MONTANT = re.compile(
    r"(?:\d[\d\s.,]*\s*(?:€|\$|r\$|(?:euros?|eur|f\s?cfa|fcfa|xof|cfa|usd|reais|brl)(?!\w))"
    r"|(?:€|\$|r\$)\s*\d)",
    re.IGNORECASE,
)

# Demande de remboursement à l'impératif : « rembourse-moi », « remboursez-nous ».
REMBOURSE_MOI = re.compile(r"\brembours\w*[- ](?:moi|nous)\b", re.IGNORECASE)

# Tentative de faire ignorer ou révéler les consignes de l'assistant.
INJECTION = re.compile(
    r"\bignor\w*\s+(?:tes|vos|les|ces|toutes?\s+(?:tes|vos|les))\s+(?:instructions|consignes|r[èe]gles)\b"
    r"|\b(?:ta|votre)\s+consigne\b|\bsystem prompt\b|\bprompt syst[èe]me\b",
    re.IGNORECASE,
)


def motif_de_refus(question: str) -> str | None:
    """Motif du refus (« montant », « commande_precise », « remboursement_personnalise »,
    « injection »), ou None si la question peut aller à la recherche."""
    if MONTANT.search(question):
        return "montant"
    if NUMERO.search(question) or REFERENCE.search(question):
        return "commande_precise"
    if REMBOURSE_MOI.search(question):
        return "remboursement_personnalise"
    if INJECTION.search(question):
        return "injection"
    return None
