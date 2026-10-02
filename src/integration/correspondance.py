"""F1.9 — Table de correspondance des produits Olist / Rakuten.

La correspondance repose uniquement sur le mapping de catégories versionné
dans docs/mappings/olist_rakuten_categories.csv.

Aucune similarité textuelle n'est utilisée.
L'affectation d'une fiche est déterministe grâce à une graine fixe.
"""

from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from common.config import load_settings

MAPPING_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "mappings" / "olist_rakuten_categories.csv"
)

TABLE = "staging.correspondance_produits"
SEED = 36019
TAILLE_PAGE = 500


class CorrespondanceError(Exception):
    """Erreur fonctionnelle du traitement F1.9."""


@dataclass(frozen=True)
class ResultatCorrespondance:
    """Résumé de l'exécution F1.9."""

    lignes_lues: int
    lignes_ecrites: int
    lignes_inconnues: int
    taux_global: float
    message: str


def connexion() -> psycopg2.extensions.connection:
    """Ouvre la connexion PostgreSQL avec la configuration du projet."""
    return psycopg2.connect(load_settings().postgres_dsn)


def charger_mapping(path: Path = MAPPING_PATH) -> dict[str, str]:
    """Charge le mapping Olist -> Rakuten depuis le CSV versionné."""
    if not path.exists():
        raise CorrespondanceError(f"Fichier de mapping introuvable : {path}")

    with path.open("r", encoding="utf-8", newline="") as fichier:
        lecteur = csv.DictReader(fichier)

        colonnes_attendues = {
            "categorie_olist",
            "categorie_rakuten",
            "justification",
        }

        if not lecteur.fieldnames:
            raise CorrespondanceError("Le fichier de mapping ne contient pas d'en-tête.")

        colonnes = set(lecteur.fieldnames)
        manquantes = colonnes_attendues - colonnes

        if manquantes:
            raise CorrespondanceError(f"Colonnes manquantes dans le mapping : {sorted(manquantes)}")

        mapping: dict[str, str] = {}

        for numero, ligne in enumerate(lecteur, start=2):
            categorie_olist = (ligne["categorie_olist"] or "").strip()
            categorie_rakuten = (ligne["categorie_rakuten"] or "").strip()

            if not categorie_olist:
                raise CorrespondanceError(f"Catégorie Olist vide à la ligne {numero}.")

            if not categorie_rakuten:
                raise CorrespondanceError(f"Catégorie Rakuten vide à la ligne {numero}.")

            if categorie_olist in mapping:
                raise CorrespondanceError(
                    f"Catégorie Olist dupliquée dans le mapping : {categorie_olist}"
                )

            mapping[categorie_olist] = categorie_rakuten

    return mapping


def charger_produits(cnx) -> list[tuple[str, str]]:
    """Charge les produits Olist transformés."""
    with cnx.cursor() as curseur:
        curseur.execute(
            """
            SELECT product_id, product_category_name_norm
            FROM staging.olist_products
            ORDER BY product_id
            """
        )

        return [
            (
                product_id,
                categorie if categorie else "inconnu",
            )
            for product_id, categorie in curseur.fetchall()
        ]


def charger_fiches(cnx) -> dict[str, list[str]]:
    """Regroupe les fiches Rakuten par code de catégorie."""
    with cnx.cursor() as curseur:
        curseur.execute(
            """
            SELECT productid, prdtypecode
            FROM staging.rakuten_produits
            WHERE productid IS NOT NULL
              AND prdtypecode IS NOT NULL
            ORDER BY prdtypecode, productid, index_ligne
            """
        )

        fiches: dict[str, list[str]] = defaultdict(list)

        for productid, prdtypecode in curseur.fetchall():
            fiches[str(prdtypecode)].append(str(productid))

    return dict(fiches)


def verifier_mapping(
    produits: list[tuple[str, str]],
    mapping: dict[str, str],
    fiches: dict[str, list[str]],
) -> None:
    """Vérifie les préconditions fonctionnelles du rapprochement."""

    categories_produits = {categorie for _, categorie in produits}

    categories_absentes = sorted(categories_produits - mapping.keys())

    if categories_absentes:
        raise CorrespondanceError(
            "Catégorie(s) Olist absente(s) du mapping : " + ", ".join(categories_absentes)
        )

    codes_attendus = {code for code in mapping.values() if code != "inconnu"}

    codes_absents_catalogue = sorted(codes_attendus - fiches.keys())

    if codes_absents_catalogue:
        raise CorrespondanceError(
            "Catégorie(s) Rakuten utilisée(s) par le mapping "
            "mais absente(s) du catalogue : " + ", ".join(codes_absents_catalogue)
        )


def construire_correspondance(
    produits: list[tuple[str, str]],
    mapping: dict[str, str],
    fiches: dict[str, list[str]],
    seed: int = SEED,
) -> list[tuple[str, str | None, str, str, bool]]:
    """Construit la table de correspondance de façon déterministe."""

    rng = random.Random(seed)

    pools: dict[str, list[str]] = {}
    positions: dict[str, int] = {}

    for code in sorted(fiches):
        pool = list(fiches[code])
        rng.shuffle(pool)
        pools[code] = pool
        positions[code] = 0

    resultat: list[tuple[str, str | None, str, str, bool]] = []

    for product_id, categorie in sorted(
        produits,
        key=lambda ligne: ligne[0],
    ):
        code = mapping[categorie]

        if code == "inconnu":
            resultat.append(
                (
                    product_id,
                    None,
                    categorie,
                    "inconnu",
                    False,
                )
            )
            continue

        pool = pools.get(code, [])

        if not pool:
            raise CorrespondanceError(f"Aucune fiche disponible pour la catégorie Rakuten {code}.")

        position = positions[code]
        id_fiche = pool[position % len(pool)]
        positions[code] = position + 1

        resultat.append(
            (
                product_id,
                id_fiche,
                categorie,
                code,
                True,
            )
        )

    return resultat


def creer_table(cnx) -> None:
    """Crée la table cible si elle n'existe pas encore."""
    with cnx.cursor() as curseur:
        curseur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id_produit TEXT PRIMARY KEY,
                id_fiche TEXT,
                categorie_boutique TEXT NOT NULL,
                categorie_catalogue TEXT NOT NULL,
                rattache BOOLEAN NOT NULL
            )
            """
        )

    cnx.commit()


def enregistrer_correspondance(
    cnx,
    lignes: list[tuple[str, str | None, str, str, bool]],
) -> None:
    """Remplace le contenu de la table par le résultat courant."""
    with cnx.cursor() as curseur:
        curseur.execute(f"TRUNCATE TABLE {TABLE}")

        requete = f"""
            INSERT INTO {TABLE}
                (
                    id_produit,
                    id_fiche,
                    categorie_boutique,
                    categorie_catalogue,
                    rattache
                )
            VALUES %s
        """

        for debut in range(0, len(lignes), TAILLE_PAGE):
            page = lignes[debut : debut + TAILLE_PAGE]

            execute_values(
                curseur,
                requete,
                page,
            )

    cnx.commit()


def calculer_stats(
    lignes: list[tuple[str, str | None, str, str, bool]],
) -> tuple[int, dict[str, tuple[int, int]]]:
    """Calcule le nombre d'inconnus et les taux par catégorie."""

    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    inconnus = 0

    for _, _, categorie, _, rattache in lignes:
        stats[categorie][0] += 1

        if rattache:
            stats[categorie][1] += 1
        else:
            inconnus += 1

    stats_finales = {
        categorie: (total, rattaches) for categorie, (total, rattaches) in stats.items()
    }

    return inconnus, stats_finales


def journaliser(
    resultat: ResultatCorrespondance,
) -> None:
    """Journalise l'exécution sans rendre la journalisation fatale."""

    debut = datetime.now(UTC)

    try:
        with connexion() as cnx, cnx.cursor() as curseur:
            curseur.execute(
                """
                INSERT INTO staging.execution_log
                    (
                        pipeline,
                        etape,
                        source,
                        demarre_a,
                        termine_a,
                        lignes_lues,
                        lignes_ecrites,
                        lignes_rejetees,
                        statut,
                        message
                    )
                VALUES
                    (
                        'integration',
                        'correspondance',
                        'olist+rakuten',
                        %s,
                        now(),
                        %s,
                        %s,
                        0,
                        'succes',
                        %s
                    )
                """,
                (
                    debut,
                    resultat.lignes_lues,
                    resultat.lignes_ecrites,
                    resultat.message,
                ),
            )

    except psycopg2.Error as erreur:
        print(f"AVERTISSEMENT : exécution non journalisée ({erreur.__class__.__name__})")


def executer(
    mapping_path: Path = MAPPING_PATH,
) -> ResultatCorrespondance:
    """Exécute intégralement F1.9."""

    mapping = charger_mapping(mapping_path)

    cnx = connexion()

    try:
        produits = charger_produits(cnx)
        fiches = charger_fiches(cnx)

        verifier_mapping(
            produits,
            mapping,
            fiches,
        )

        lignes = construire_correspondance(
            produits,
            mapping,
            fiches,
        )

        creer_table(cnx)

        enregistrer_correspondance(
            cnx,
            lignes,
        )

        inconnus, stats = calculer_stats(lignes)

        taux_global = ((len(lignes) - inconnus) / len(lignes) * 100) if lignes else 0.0

        message = (
            f"{len(lignes)} produits conservés ; "
            f"{len(lignes) - inconnus} rattachés ; "
            f"{inconnus} inconnu(s) ; "
            f"taux global={taux_global:.2f} %"
        )

        resultat = ResultatCorrespondance(
            lignes_lues=len(produits),
            lignes_ecrites=len(lignes),
            lignes_inconnues=inconnus,
            taux_global=taux_global,
            message=message,
        )

        print("=== F1.9 — Correspondance produits ===")
        print(message)
        print()
        print("Taux de rattachement par catégorie :")

        for categorie in sorted(stats):
            total, rattaches = stats[categorie]

            taux = rattaches / total * 100 if total else 0.0

            print(f"  {categorie:<45} {rattaches:>6}/{total:<6} {taux:>6.2f} %")

        journaliser(resultat)

        return resultat

    except Exception:
        cnx.rollback()
        raise

    finally:
        cnx.close()


def main() -> int:
    """Point d'entrée CLI de F1.9."""

    try:
        executer()

    except CorrespondanceError as erreur:
        print(
            f"ERREUR F1.9 : {erreur}",
            file=sys.stderr,
        )
        return 1

    except psycopg2.Error as erreur:
        print(
            f"ERREUR F1.9 : problème PostgreSQL ({erreur})",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
