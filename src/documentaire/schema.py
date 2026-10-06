"""Structure de l'index des passages : champs, vecteur, et forme d'un document.

Contrat : docs/contrats/passages.md

Comme pour le catalogue, tout est ici : Elasticsearch ne sait pas changer le
type d'un champ existant, donc une erreur de structure se paie par une
réindexation complète (`--recreer`).
"""

from __future__ import annotations

from recherche.schema import PARAMETRES as PARAMETRES

INDEX = "faq_passages"

# Le même modèle doit servir à l'indexation et à la recherche.
MODELE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSION = 384

CHAMPS = {
    "properties": {
        "id": {"type": "keyword"},
        "theme": {"type": "keyword"},
        "question": {"type": "text", "analyzer": "francais"},
        "reponse": {"type": "text", "analyzer": "francais"},
        "source": {"type": "keyword"},
        "maj": {"type": "date", "format": "yyyy-MM-dd"},
        # Le texte réellement vectorisé : gardé pour pouvoir le relire.
        "texte": {"type": "text", "index": False},
        "vecteur": {
            "type": "dense_vector",
            "dims": DIMENSION,
            "index": True,
            "similarity": "cosine",
        },
    }
}


def texte_a_vectoriser(entree: dict) -> str:
    """Question et réponse ensemble : une question reformulée ressemble aux deux."""
    return f"{entree['question'].strip()}\n{entree['reponse'].strip()}"


def construire_document(entree: dict, vecteur) -> dict:
    """Transforme une ligne de la foire aux questions en document indexable."""
    return {
        "id": entree["id"],
        "theme": entree["theme"],
        "question": entree["question"],
        "reponse": entree["reponse"],
        "source": entree["source"],
        "maj": entree["maj"],
        "texte": texte_a_vectoriser(entree),
        "vecteur": [float(x) for x in vecteur],
    }
