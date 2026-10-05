"""Source NoSQL — le catalogue produits servi depuis MongoDB.

Pourquoi une base documentaire et pas une table : 35 % des fiches du catalogue
n'ont pas de description, et dans MongoDB ces fiches **n'ont pas le champ du
tout** plutôt qu'un champ vide. C'est la forme réelle d'un catalogue
fournisseur, où chaque fiche porte ce que son vendeur a bien voulu remplir — et
c'est ce qu'un schéma relationnel ne sait pas représenter sans mentir.

Le contrôle de qualité lit donc une structure irrégulière, et sa règle
RAKUTEN_PRODUITS_02 vérifie une **absence de champ**, pas une chaîne vide.
"""

from __future__ import annotations

import csv
from pathlib import Path

from pymongo import MongoClient

from common.config import load_settings

COLLECTION = "produits"

# Les champs tels qu'ils apparaissent dans le fichier plat produit pour la zone
# brute. Une fiche sans description laisse la colonne vide : le fichier reste
# lisible par le contrôle, et l'absence est portée par le champ `a_description`.
COLONNES = (
    "index_ligne",
    "jeu",
    "productid",
    "imageid",
    "designation",
    "description",
    "prdtypecode",
    "a_description",
)


def connexion() -> MongoClient:
    return MongoClient(load_settings().mongo_uri, serverSelectionTimeoutMS=10_000)


def nom_base(uri: str) -> str:
    """Nom de la base, extrait de l'adresse de connexion."""
    from urllib.parse import urlsplit

    chemin = urlsplit(uri).path.lstrip("/")
    return chemin.split("?")[0] or "catalogue"


def _index(ligne: dict) -> int:
    """Index d'origine de la fiche, quel que soit le nom de la colonne.

    Le fichier livré nomme cette colonne « source_index » ; la zone
    intermédiaire la nomme « index_ligne ». Les deux sont acceptés, pour que le
    chargement ne dépende pas de la provenance du fichier.
    """
    for nom in ("index_ligne", "source_index"):
        if ligne.get(nom):
            return int(ligne[nom])
    raise KeyError(
        "aucune colonne d'index dans le fichier source (attendu « index_ligne » "
        f"ou « source_index », trouvé : {', '.join(ligne)})"
    )


def document(ligne: dict) -> dict:
    """Transforme une ligne du fichier source en document MongoDB.

    Les champs vides sont **absents** du document, ils ne sont pas stockés
    vides : c'est tout l'intérêt d'une base documentaire, et c'est ce que le
    contrôle de qualité devra savoir gérer.
    """
    code = (ligne.get("prdtypecode") or "").strip()
    doc: dict = {
        "index_ligne": _index(ligne),
        # Le fichier livré réunit deux jeux : une fiche avec code de catégorie
        # appartient à l'entraînement, une fiche sans code au jeu de test.
        # C'est la règle qu'applique déjà le contrôle de qualité.
        "jeu": ligne.get("jeu") or ("train" if code else "test"),
        "productid": ligne["productid"],
        "imageid": ligne.get("imageid", ""),
        "designation": ligne["designation"],
    }
    description = (ligne.get("description") or "").strip()
    if description:
        doc["description"] = description
    if code:
        doc["prdtypecode"] = int(code)
    return doc


def charger(fichier: Path, base, par_lot: int = 2000) -> int:
    """Remplit la collection depuis le fichier source. Relançable.

    La collection est vidée puis remplie : c'est un chargement initial, pas une
    synchronisation. Deux exécutions donnent exactement la même collection.
    """
    collection = base[COLLECTION]
    collection.delete_many({})

    inseres = 0
    lot: list = []
    with fichier.open(encoding="utf-8", newline="") as flux:
        for ligne in csv.DictReader(flux):
            lot.append(document(ligne))
            if len(lot) >= par_lot:
                collection.insert_many(lot)
                inseres += len(lot)
                lot = []
    if lot:
        collection.insert_many(lot)
        inseres += len(lot)

    collection.create_index("productid")
    collection.create_index("prdtypecode")
    return inseres


def ligne_plate(doc: dict) -> dict:
    """Remet un document irrégulier à plat, pour la zone brute.

    L'absence d'un champ devient une colonne vide, et le fait qu'il manquait
    est conservé dans `a_description` : la zone brute garde des fichiers
    lisibles, sans perdre l'information que la base documentaire portait.
    """
    description = doc.get("description", "")
    return {
        "index_ligne": doc["index_ligne"],
        "jeu": doc.get("jeu", "train"),
        "productid": doc["productid"],
        "imageid": doc.get("imageid", ""),
        "designation": doc.get("designation", ""),
        "description": description,
        "prdtypecode": doc.get("prdtypecode", ""),
        "a_description": "oui" if description else "non",
    }


def extraire(base, destination: Path) -> int:
    """Écrit la collection dans un fichier CSV de la zone brute."""
    collection = base[COLLECTION]
    lignes = 0
    with destination.open("w", encoding="utf-8", newline="") as flux:
        redacteur = csv.DictWriter(flux, fieldnames=COLONNES)
        redacteur.writeheader()
        for doc in collection.find({}, {"_id": 0}).sort([("jeu", 1), ("index_ligne", 1)]):
            redacteur.writerow(ligne_plate(doc))
            lignes += 1
    return lignes
