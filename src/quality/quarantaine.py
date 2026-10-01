"""Enregistrement et consultation des rejets de qualité."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import psycopg2
from psycopg2.extras import Json, execute_values

from common.config import load_settings

GRAVITES_AUTORISEES = {"bloquante", "non bloquante"}


def _ouvrir_connexion():
    """Ouvre une connexion PostgreSQL avec la configuration du projet."""
    return psycopg2.connect(load_settings().postgres_dsn)


def _normaliser_rejet(rejet: Mapping[str, Any]) -> tuple:
    """Transforme un rejet du contrat en ligne prête pour PostgreSQL."""
    champs_obligatoires = (
        "source",
        "ingestion",
        "regle",
        "gravite",
        "donnees_brutes",
    )

    for champ in champs_obligatoires:
        if champ not in rejet:
            raise ValueError(f"Champ obligatoire manquant : {champ}")

    gravite = str(rejet["gravite"])
    if gravite not in GRAVITES_AUTORISEES:
        raise ValueError(
            f"Gravité invalide : {gravite!r}. Valeurs autorisées : {sorted(GRAVITES_AUTORISEES)}"
        )

    return (
        str(rejet["source"]),
        str(rejet["ingestion"]),
        rejet.get("fichier"),
        rejet.get("ligne_origine"),
        str(rejet["regle"]),
        gravite,
        Json(rejet["donnees_brutes"]),
    )


def enregistrer_rejets(
    rejets: Iterable[Mapping[str, Any]],
    connexion=None,
    valider: bool = True,
) -> int:
    """Enregistre plusieurs rejets en une seule opération par lots.

    `valider=False` laisse la transaction ouverte : c'est l'appelant qui
    valide ou annule, pour charger staging, quarantaine et journal d'un seul
    tenant (voir quality.chargement).

    Retourne le nombre de rejets enregistrés.
    """
    lignes = [_normaliser_rejet(rejet) for rejet in rejets]

    if not lignes:
        return 0

    connexion_locale = connexion is None
    connexion = connexion or _ouvrir_connexion()

    try:
        with connexion.cursor() as curseur:
            execute_values(
                curseur,
                """
                INSERT INTO quarantaine.rejets (
                    source,
                    ingestion,
                    fichier,
                    ligne_origine,
                    regle_violee,
                    gravite,
                    enregistrement
                )
                VALUES %s
                """,
                lignes,
                page_size=500,
            )

        if valider:
            connexion.commit()
        return len(lignes)

    except Exception:
        if valider:
            connexion.rollback()
        raise

    finally:
        if connexion_locale:
            connexion.close()


def lister_rejets(
    source: str | None = None,
    regle: str | None = None,
    limite: int = 20,
    connexion=None,
) -> list[dict[str, Any]]:
    """Retourne les rejets les plus récents correspondant aux filtres."""
    if limite <= 0:
        raise ValueError("La limite doit être supérieure à zéro.")

    conditions = []
    parametres: list[Any] = []

    if source:
        conditions.append("source = %s")
        parametres.append(source)

    if regle:
        conditions.append("regle_violee = %s")
        parametres.append(regle)

    clause_where = ""
    if conditions:
        clause_where = "WHERE " + " AND ".join(conditions)

    requete = f"""
        SELECT
            id,
            source,
            ingestion,
            fichier,
            ligne_origine,
            regle_violee,
            gravite,
            enregistrement,
            horodatage
        FROM quarantaine.rejets
        {clause_where}
        ORDER BY horodatage DESC, id DESC
        LIMIT %s
    """

    parametres.append(limite)

    connexion_locale = connexion is None
    connexion = connexion or _ouvrir_connexion()

    try:
        with connexion.cursor() as curseur:
            curseur.execute(requete, parametres)
            lignes = curseur.fetchall()
            colonnes = [colonne.name for colonne in curseur.description]

        return [dict(zip(colonnes, ligne, strict=True)) for ligne in lignes]

    finally:
        if connexion_locale:
            connexion.close()


def afficher_rejets(
    source: str | None = None,
    regle: str | None = None,
    limite: int = 20,
) -> int:
    """Affiche les rejets et retourne le nombre affiché."""
    rejets = lister_rejets(
        source=source,
        regle=regle,
        limite=limite,
    )

    if not rejets:
        print("Aucun rejet trouvé.")
        return 0

    print(f"{len(rejets)} rejet(s) trouvé(s).")

    for rejet in rejets:
        print("-" * 70)
        print(f"ID          : {rejet['id']}")
        print(f"Source      : {rejet['source']}")
        print(f"Ingestion   : {rejet['ingestion']}")
        print(f"Fichier     : {rejet['fichier']}")
        print(f"Ligne       : {rejet['ligne_origine']}")
        print(f"Règle       : {rejet['regle_violee']}")
        print(f"Gravité     : {rejet['gravite']}")
        print(f"Horodatage  : {rejet['horodatage']}")
        print(f"Donnée      : {rejet['enregistrement']}")

    return len(rejets)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Consulter les rejets de qualité.")
    parser.add_argument(
        "--source",
        help="Filtrer par source, par exemple olist ou rakuten.",
    )
    parser.add_argument(
        "--regle",
        help="Filtrer par identifiant de règle.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=20,
        help="Nombre maximal de rejets à afficher.",
    )

    args = parser.parse_args()

    try:
        afficher_rejets(
            source=args.source,
            regle=args.regle,
            limite=args.limite,
        )
    except psycopg2.Error:
        print(
            "ERREUR : impossible de contacter la base PostgreSQL.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
