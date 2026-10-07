"""Lexique métier : combler l'écart entre les mots du client et ceux de la foire aux questions.

Un client écrit « colis », la foire aux questions dit « commande » ; il écrit « argent »,
elle dit « remboursement ». Une recherche par mots ne le sait pas. Ce lexique, écrit à la
main à partir du vocabulaire réel du corpus, ajoute à la question les mots que la foire aux
questions emploie. Il se lit, se corrige, et s'explique.

Il ne sert qu'à la recherche de dépannage : une recherche sémantique n'en a pas besoin.
Règle : une entrée n'ajoute que des mots présents dans les passages visés.
Clés et valeurs sont normalisées (sans accent, en minuscules).
"""

from __future__ import annotations

from .texte import normaliser

LEXIQUE: dict[str, tuple[str, ...]] = {
    # livraison
    "colis": ("commande", "livraison"),
    "envoi": ("livraison", "frais", "port"),
    "expedition": ("livraison", "expediee"),
    "gratuit": ("payante", "frais", "port"),
    "gratuite": ("payante", "frais", "port"),
    "suivi": ("suivre", "statut"),
    "avancement": ("suivre", "statut"),
    "casse": ("endommage",),
    "abime": ("endommage",),
    "cassee": ("endommage",),
    "abimee": ("endommage",),
    "arrive": ("livraison", "retard"),
    # retours et remboursement
    "renvoyer": ("retourner", "retour"),
    "renvoi": ("retour",),
    "rendre": ("retourner", "retour"),
    "argent": ("remboursement", "rembourse"),
    "rembourser": ("remboursement", "rembourse"),
    "marchandises": ("produits",),
    "marchandise": ("produit",),
    "article": ("produit",),
    "articles": ("produits",),
    "mauvais": ("different", "produit"),
    "erreur": ("different", "produit"),
    "autre": ("echanger",),
    "modele": ("echanger", "produit"),
    # paiement
    "payer": ("paiement", "paiements"),
    "regler": ("paiement", "paiements"),
    "reduction": ("bon", "achat"),
    "coupon": ("bon", "achat"),
    "promo": ("bon", "achat"),
    "fois": ("plusieurs", "echeances", "paiement"),
    "mensualites": ("plusieurs", "echeances", "paiement"),
    "preleve": ("debite", "paiement"),
    "prelevement": ("debite", "paiement"),
    "debit": ("debite", "paiement"),
    # commande
    "annule": ("annulee", "annuler"),
    "annulation": ("annulee", "annuler"),
    "indisponible": ("stock", "statut"),
    # compte et données
    "inscrire": ("creer", "compte"),
    "inscription": ("creer", "compte"),
    "effacer": ("supprimer", "compte"),
    "informations": ("donnees", "personnelles"),
    "infos": ("donnees", "personnelles"),
    "vendez": ("donnees", "personnelles", "protegees"),
    "revendez": ("donnees", "personnelles", "protegees"),
    "mdp": ("mot", "passe", "oublie"),
}


def etendre(question: str) -> str:
    """La question normalisée, suivie des mots de la foire aux questions qui lui correspondent."""
    normalisee = normaliser(question)
    ajouts: list[str] = []
    for mot in normalisee.split():
        for synonyme in LEXIQUE.get(mot, ()):
            if synonyme not in normalisee.split() and synonyme not in ajouts:
                ajouts.append(synonyme)
    return " ".join([normalisee, *ajouts]).strip()
