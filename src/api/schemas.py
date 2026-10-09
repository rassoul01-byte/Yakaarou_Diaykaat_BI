"""Schémas Pydantic pour l'API de démonstration.

Ces schémas sont le miroir exact des types TypeScript côté frontend
(frontend/src/types/api.ts). Toute modification doit être répercutée
des deux côtés dans la même PR.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------- assistant


class AssistantIn(BaseModel):
    """`origine` et `reformulation` ne changent pas la réponse : ils vont au journal.

    Quand l'utilisateur clique une suggestion, la page renvoie la question du passage
    en `question`, et SA formulation d'origine en `reformulation`. Le journal garde
    ainsi le couple (ce qu'il a écrit, le passage qui lui a convenu) — voir
    `assistant/journal.py`.
    """

    question: str = Field(min_length=1, max_length=500)
    k: int = Field(default=3, ge=1, le=10)
    origine: Literal["saisie", "exemple", "suggestion"] = "saisie"
    reformulation: str | None = Field(default=None, max_length=500)


class PassageOut(BaseModel):
    id: str
    theme: str
    question: str
    source: str
    score: float


class SuggestionOut(BaseModel):
    """Ce que l'assistant propose quand il hésite : le contrat (assistant.md §3)
    ne publie que l'identifiant et la question, pas le texte ni le score."""

    id: str
    question: str


class AssistantOut(BaseModel):
    reponse: str
    refus: bool
    motif: str | None
    passages: list[PassageOut]
    suggestions: list[SuggestionOut]
    duree_ms: int


# --------------------------------------------------------------- recherche produits


class RechercheIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)
    k: int = Field(default=10, ge=1, le=50)
    categorie: str | None = None
    langue: str | None = None


class ProduitOut(BaseModel):
    product_id: str
    designation: str
    categorie_code: str | None
    score: float


class RechercheOut(BaseModel):
    question_posee: str
    produits: list[ProduitOut]
    total: int
    temps_serveur_ms: int


# --------------------------------------------------------------- indicateurs
#
# Chaque bloc est optionnel ou vide par construction : une base fraîchement
# montée n'a ni ventes, ni événements, ni exécutions. La page doit afficher
# « pas encore de données » au lieu de recevoir une erreur.


class VentesOut(BaseModel):
    chiffre_affaires: float
    commandes: int
    articles: int
    panier_moyen: float
    premier_jour: str | None = None
    dernier_jour: str | None = None


class CategorieOut(BaseModel):
    categorie: str | None
    chiffre_affaires: float | None
    articles: int | None
    commandes: int | None


class QualiteOut(BaseModel):
    sources: int
    lignes_lues: int | None
    lignes_rejetees: int | None
    taux_rejet_pourcent: float | None


class MotifRejetOut(BaseModel):
    regle: str
    gravite: str | None
    rejets: int


class JourOut(BaseModel):
    """Compteurs du dernier jour connu. Aucun montant : les événements
    simulés n'en portent pas (docs/contrats/evenements.md)."""

    jour: str
    sessions: int
    pages_vues: int
    recherches: int
    ajouts_panier: int
    achats: int
    sessions_avec_achat: int | None = None
    taux_conversion_pourcent: float | None = None


class HeureOut(BaseModel):
    heure: int
    achats: int


class AlerteOut(BaseModel):
    """Verdict de `compteurs.alerte`, qui porte le seuil et ses garde-fous."""

    jour: str
    achats: int
    achats_habituels: float | None
    jours_compares: int
    niveau_pourcent: float | None
    seuil_pourcent: float
    declenchee: bool
    message: str


class SegmentOut(BaseModel):
    clients: int
    date_reference: str | None


class EtapeOut(BaseModel):
    pipeline: str
    etape: str
    source: str | None
    duree_secondes: float | None
    lignes_lues: int | None
    lignes_rejetees: int | None
    statut: str
    demarre_a: str | None


class IndicateursOut(BaseModel):
    ventes: VentesOut | None
    categories: list[CategorieOut]
    qualite: QualiteOut | None
    motifs_de_rejet: list[MotifRejetOut]
    jour: JourOut | None
    achats_par_heure: list[HeureOut]
    alerte: AlerteOut | None
    segment: SegmentOut | None
    chaine: list[EtapeOut]
    trafic_simule: bool = True
