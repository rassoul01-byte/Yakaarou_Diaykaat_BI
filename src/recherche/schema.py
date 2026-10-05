"""Structure de l'index : analyseur, champs, et forme d'un document.

Tout est ici, et rien n'est calculé ailleurs : Elasticsearch ne sait pas
changer le type d'un champ existant, donc une erreur de structure se paie par
une réindexation complète. Autant la relire une fois de plus.
"""

from __future__ import annotations

INDEX = "catalogue"

# L'analyseur « francais » : minuscules, accents retirés, mots vides, et
# racinisation légère. C'est lui qui fait qu'« eclairage » trouve « éclairage »
# — le cas le plus fréquent d'une recherche tapée vite.
PARAMETRES = {
    "analysis": {
        "filter": {
            "mots_vides_fr": {"type": "stop", "stopwords": "_french_"},
            "racines_fr": {"type": "stemmer", "language": "light_french"},
            "elisions_fr": {
                "type": "elision",
                "articles_case": True,
                "articles": ["l", "m", "t", "qu", "n", "s", "j", "d", "c"],
            },
        },
        "analyzer": {
            "francais": {
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    "elisions_fr",
                    "asciifolding",
                    "mots_vides_fr",
                    "racines_fr",
                ],
            }
        },
    }
}

CHAMPS = {
    "properties": {
        "product_id": {"type": "keyword"},
        "index_ligne": {"type": "integer"},
        "jeu": {"type": "keyword"},
        "designation": {"type": "text", "analyzer": "francais"},
        "description": {"type": "text", "analyzer": "francais"},
        "categorie_code": {"type": "keyword"},
        "langue": {"type": "keyword"},
        "a_description": {"type": "boolean"},
    }
}


def identifiant(jeu: str, index_ligne: int) -> str:
    """Identifiant du document dans l'index.

    C'est la clé primaire de la table d'origine, et non `product_id` : rien ne
    garantit que celui-ci soit unique dans le catalogue. Réindexer écrase donc
    la fiche au lieu d'en créer une seconde — c'est tout le mécanisme
    d'idempotence de ce module.
    """
    return f"{jeu}:{index_ligne}"


def construire_document(ligne: dict) -> dict:
    """Transforme une ligne de la zone intermédiaire en document indexable."""
    description = (ligne.get("description") or "").strip()
    return {
        "product_id": ligne["productid"],
        "index_ligne": ligne["index_ligne"],
        "jeu": ligne["jeu"],
        "designation": ligne["designation"],
        "description": description or None,
        "categorie_code": str(ligne["prdtypecode"]) if ligne.get("prdtypecode") else None,
        "langue": ligne.get("langue"),
        # 35 % des fiches n'ont pas de description : l'indiquer évite de lire un
        # silence comme une absence de résultat.
        "a_description": bool(description),
    }
