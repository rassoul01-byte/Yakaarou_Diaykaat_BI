"""Récupération des données sources de DataFlow360.

Télécharge depuis le Drive de l'équipe le jeu de commandes Olist (archive zip)
et le catalogue produits Rakuten, les range dans la zone brute, puis vérifie
chaque fichier contre les volumes de référence.

Usage, depuis la racine du dépôt :
    python scripts/download_data.py              récupère ce qui manque, puis vérifie
    python scripts/download_data.py --verifier   vérifie seulement, sans rien télécharger
    python scripts/download_data.py --forcer     retélécharge tout, même si c'est conforme

Dans le conteneur :
    docker compose exec app python scripts/download_data.py

Code de sortie : 0 si les dix fichiers sont conformes, 1 sinon.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pandas as pd

RACINE_DEPOT = Path(__file__).resolve().parent.parent

# Identifiants des deux fichiers sur le Drive de l'équipe.
# Lus dans l'environnement s'ils y sont définis ; sinon ces valeurs sont utilisées,
# afin que le script fonctionne sur un poste vierge, sans aucune configuration.
DRIVE_IDS_PAR_DEFAUT = {
    "olist": "10FeZJEhyK6YHiChmKDFBTBIIVdKhi8YU",
    "rakuten": "1YI0L8CIkjOSAFpIfTecH5kG3Vmp6TW-k",
}


@dataclass(frozen=True)
class FichierAttendu:
    source: str  # sous-dossier de la zone brute : « olist » ou « rakuten »
    nom: str
    lignes: int
    colonnes: int


# Volumes de référence, mesurés sur les fichiers d'origine.
# Tout écart signale un téléchargement incomplet ou un fichier modifié.
REFERENCE = [
    FichierAttendu("rakuten", "rakuten_catalogue_produits.csv", 84_916, 6),
    FichierAttendu("olist", "olist_customers_dataset.csv", 99_441, 5),
    FichierAttendu("olist", "olist_geolocation_dataset.csv", 1_000_163, 5),
    FichierAttendu("olist", "olist_order_items_dataset.csv", 112_650, 7),
    FichierAttendu("olist", "olist_order_payments_dataset.csv", 103_886, 5),
    FichierAttendu("olist", "olist_order_reviews_dataset.csv", 99_224, 7),
    FichierAttendu("olist", "olist_orders_dataset.csv", 99_441, 8),
    FichierAttendu("olist", "olist_products_dataset.csv", 32_951, 9),
    FichierAttendu("olist", "olist_sellers_dataset.csv", 3_095, 4),
    FichierAttendu("olist", "product_category_name_translation.csv", 71, 2),
]


@dataclass(frozen=True)
class Resultat:
    attendu: FichierAttendu
    conforme: bool
    detail: str


# --------------------------------------------------------------------------- #
# Emplacements
# --------------------------------------------------------------------------- #


def dossier_donnees() -> Path:
    """Racine des données : DATA_DIR si défini, sinon « data/ » à la racine du dépôt.

    Le chemin est calculé à partir de l'emplacement du script et non du dossier
    courant : le script donne le même résultat où qu'on le lance.
    """
    valeur = os.getenv("DATA_DIR")
    if not valeur:
        return RACINE_DEPOT / "data"
    chemin = Path(valeur)
    return chemin if chemin.is_absolute() else RACINE_DEPOT / chemin


def chemin_de(data_dir: Path, attendu: FichierAttendu) -> Path:
    return data_dir / "raw" / attendu.source / attendu.nom


def preparer_dossiers(data_dir: Path) -> None:
    """Crée l'arborescence de la zone de données, absente après un clonage."""
    for sous_dossier in ("raw/olist", "raw/rakuten", "quarantine", "models"):
        (data_dir / sous_dossier).mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Vérification
# --------------------------------------------------------------------------- #


def verifier(data_dir: Path, reference: list[FichierAttendu]) -> list[Resultat]:
    """Contrôle chaque fichier attendu : présence, lisibilité, nombre de lignes et de colonnes.

    Le comptage passe par pandas et non par un simple comptage de lignes du fichier :
    les avis clients contiennent des commentaires sur plusieurs lignes, qu'un comptage
    naïf compterait plusieurs fois.
    """
    resultats = []
    for attendu in reference:
        chemin = chemin_de(data_dir, attendu)
        if not chemin.exists():
            resultats.append(Resultat(attendu, False, "absent"))
            continue
        try:
            lignes, colonnes = pd.read_csv(chemin, low_memory=False).shape
        except Exception as erreur:  # fichier tronqué, encodage inattendu…
            resultats.append(Resultat(attendu, False, f"illisible ({erreur.__class__.__name__})"))
            continue
        if (lignes, colonnes) == (attendu.lignes, attendu.colonnes):
            resultats.append(Resultat(attendu, True, f"{lignes} x {colonnes}"))
        else:
            detail = f"attendu {attendu.lignes} x {attendu.colonnes}, obtenu {lignes} x {colonnes}"
            resultats.append(Resultat(attendu, False, detail))
    return resultats


def afficher_bilan(resultats: list[Resultat]) -> None:
    largeur = max(len(r.attendu.nom) for r in resultats)
    print()
    for r in resultats:
        statut = "OK   " if r.conforme else "ECHEC"
        print(f"  [{statut}]  {r.attendu.source:<8} {r.attendu.nom:<{largeur}}  {r.detail}")
    conformes = sum(r.conforme for r in resultats)
    print(f"\n  {conformes} fichier(s) sur {len(resultats)} conforme(s).\n")


# --------------------------------------------------------------------------- #
# Récupération
# --------------------------------------------------------------------------- #


def telecharger(identifiant: str, destination: Path) -> None:
    """Télécharge un fichier du Drive à partir de son identifiant.

    La bibliothèque gdown gère la page d'avertissement que Drive affiche pour les
    fichiers volumineux, ce qu'un simple téléchargement HTTP ne sait pas faire.
    Elle est importée ici, et non en tête de fichier, pour que l'option --verifier
    fonctionne même là où elle n'est pas installée.
    """
    import gdown

    obtenu = gdown.download(id=identifiant, output=str(destination), quiet=False)
    if obtenu is None or not destination.exists():
        raise RuntimeError(
            f"Échec du téléchargement du fichier Drive {identifiant}. Vérifier que le "
            "fichier est partagé en « Tous les utilisateurs disposant du lien » et que "
            "la connexion Internet fonctionne."
        )


def extraire_csv(archive: Path, destination: Path) -> list[str]:
    """Extrait tous les CSV d'une archive dans un dossier, à plat.

    L'archive peut contenir un sous-dossier : seuls les noms de fichiers sont
    conservés, quel que soit leur emplacement dans l'archive. Les fichiers parasites
    ajoutés par macOS sont ignorés.
    """
    extraits = []
    with zipfile.ZipFile(archive) as zf:
        for membre in zf.infolist():
            if membre.is_dir() or membre.filename.startswith("__MACOSX"):
                continue
            nom = PurePosixPath(membre.filename).name
            if nom.startswith("._") or not nom.lower().endswith(".csv"):
                continue
            with zf.open(membre) as source, open(destination / nom, "wb") as cible:
                shutil.copyfileobj(source, cible)
            extraits.append(nom)
    return extraits


def recuperer(data_dir: Path, sources: set[str], identifiants: dict[str, str]) -> None:
    """Télécharge les sources demandées et les range dans la zone brute.

    Les téléchargements passent par un dossier temporaire : un fichier interrompu en
    cours de route n'arrive jamais dans la zone brute sous une forme incomplète.
    """
    with tempfile.TemporaryDirectory(dir=data_dir) as temporaire:
        temporaire = Path(temporaire)

        if "olist" in sources:
            print("Téléchargement du jeu de commandes Olist…")
            archive = temporaire / "Dataset-Olist.zip"
            telecharger(identifiants["olist"], archive)
            extraits = extraire_csv(archive, data_dir / "raw" / "olist")
            print(f"  {len(extraits)} fichier(s) CSV extrait(s) dans raw/olist/")

        if "rakuten" in sources:
            print("Téléchargement du catalogue Rakuten…")
            fichier = temporaire / "rakuten_catalogue_produits.csv"
            telecharger(identifiants["rakuten"], fichier)
            shutil.move(str(fichier), data_dir / "raw" / "rakuten" / fichier.name)
            print("  catalogue placé dans raw/rakuten/")


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Récupère et vérifie les données sources.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verifier", action="store_true", help="vérifier sans télécharger")
    mode.add_argument("--forcer", action="store_true", help="tout retélécharger")
    args = parser.parse_args(argv)

    data_dir = dossier_donnees()
    preparer_dossiers(data_dir)
    print(f"Zone de données : {data_dir}")

    resultats = verifier(data_dir, REFERENCE)

    if args.verifier:
        afficher_bilan(resultats)
        return 0 if all(r.conforme for r in resultats) else 1

    if args.forcer:
        a_recuperer = {f.source for f in REFERENCE}
    else:
        a_recuperer = {r.attendu.source for r in resultats if not r.conforme}

    if not a_recuperer:
        print("Les fichiers sont déjà présents et conformes : rien à télécharger.")
        afficher_bilan(resultats)
        return 0

    identifiants = {
        source: os.getenv(f"DRIVE_{source.upper()}_ID") or defaut
        for source, defaut in DRIVE_IDS_PAR_DEFAUT.items()
    }
    try:
        recuperer(data_dir, a_recuperer, identifiants)
    except (RuntimeError, zipfile.BadZipFile) as erreur:
        print(f"\nERREUR : {erreur}", file=sys.stderr)
        return 1

    resultats = verifier(data_dir, REFERENCE)
    afficher_bilan(resultats)
    return 0 if all(r.conforme for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
