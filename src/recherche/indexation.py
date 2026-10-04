"""Lecture du catalogue et alimentation de l'index.

Le module ne lit que `staging.rakuten_produits`, c'est-à-dire le catalogue
après contrôle et transformation : balisage décodé, langue détectée.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg2
import psycopg2.extras

from common.config import load_settings

from .schema import CHAMPS, INDEX, PARAMETRES, construire_document, identifiant

TAILLE_LOT = 1000

REQUETE_CATALOGUE = """
    SELECT jeu, index_ligne, productid, designation, description, prdtypecode, langue
    FROM staging.rakuten_produits
    ORDER BY jeu, index_ligne
"""


@dataclass(frozen=True)
class Resultat:
    fiches_en_base: int
    documents_indexes: int
    erreurs: int

    @property
    def conforme(self) -> bool:
        """L'index contient exactement ce que la zone intermédiaire contient."""
        return self.erreurs == 0 and self.documents_indexes == self.fiches_en_base


def lire_catalogue(dsn: str | None = None):
    """Rend les fiches du catalogue nettoyé, une par une."""
    connexion = psycopg2.connect(dsn or load_settings().postgres_dsn)
    try:
        with connexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as curseur:
            curseur.execute(REQUETE_CATALOGUE)
            yield from (dict(ligne) for ligne in curseur)
    finally:
        connexion.close()


def creer_index(client, recreer: bool = False) -> bool:
    """Crée l'index s'il n'existe pas. Renvoie True s'il a été créé.

    `recreer` supprime l'index existant : c'est la seule façon de changer le
    type d'un champ, Elasticsearch ne sachant pas le modifier en place.
    """
    if recreer and client.indices.exists(index=INDEX):
        client.indices.delete(index=INDEX)
    if client.indices.exists(index=INDEX):
        return False
    client.indices.create(index=INDEX, settings=PARAMETRES, mappings=CHAMPS)
    return True


def _envoyer(client, operations: list) -> int:
    """Envoie un lot et renvoie le nombre d'erreurs."""
    if not operations:
        return 0
    reponse = client.bulk(operations=operations, refresh=False)
    if not reponse.get("errors"):
        return 0
    return sum(1 for item in reponse.get("items", []) if item.get("index", {}).get("error"))


def indexer(client, fiches, taille_lot: int = TAILLE_LOT) -> tuple[int, int]:
    """Indexe les fiches par lots. Renvoie (documents envoyés, erreurs)."""
    operations: list = []
    envoyes = erreurs = 0

    for ligne in fiches:
        document = construire_document(ligne)
        operations.append(
            {"index": {"_index": INDEX, "_id": identifiant(ligne["jeu"], ligne["index_ligne"])}}
        )
        operations.append(document)
        envoyes += 1
        if len(operations) >= taille_lot * 2:
            erreurs += _envoyer(client, operations)
            operations = []

    erreurs += _envoyer(client, operations)
    client.indices.refresh(index=INDEX)
    return envoyes, erreurs


def compter_en_base(dsn: str | None = None) -> int:
    connexion = psycopg2.connect(dsn or load_settings().postgres_dsn)
    try:
        with connexion.cursor() as curseur:
            curseur.execute("SELECT count(*) FROM staging.rakuten_produits")
            return curseur.fetchone()[0]
    finally:
        connexion.close()


def compter_indexes(client) -> int:
    if not client.indices.exists(index=INDEX):
        return 0
    return client.count(index=INDEX)["count"]
