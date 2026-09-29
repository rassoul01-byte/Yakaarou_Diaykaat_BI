"""Rapport du taux de rejet.

Répond à trois questions, dans cet ordre : est-ce que la qualité se dégrade,
sur quelle source, et à cause de quelle règle.

Les définitions sont dans docs/dictionnaire_indicateurs.md, le calcul dans
sql/005_vues_taux_de_rejet.sql. Ce module ne calcule rien lui-même : il lit les
vues et met en forme. Le seuil, lui, est une décision — elle est ici.

Usage :
    docker compose exec app python -m quality.rapport
    docker compose exec app python -m quality.rapport --seuil 5
    docker compose exec app python -m quality.rapport --source olist

Code de sortie : 0 si tout est sous le seuil, 1 si une source le dépasse ou si
la base est injoignable. C'est ce code qu'Airflow lira au Sprint 3 pour
interrompre la chaîne quotidienne.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import psycopg2

from common.config import load_settings

# Seuil par défaut, fixé par le dossier de conception : au-delà, le chargement
# du jour est interrompu et examiné.
SEUIL_PAR_DEFAUT = 5.0

_PAR_SOURCE = """
    SELECT source, lignes_lues, lignes_rejetees, taux_rejet_pourcent,
           executions, taux_rejet_cumule_pourcent, derniere_le
    FROM quarantaine.v_taux_rejet_par_source
    WHERE (%(source)s IS NULL OR source = %(source)s)
    ORDER BY taux_rejet_pourcent DESC NULLS LAST, source
"""

_PAR_REGLE = """
    SELECT source, regle, gravite, rejets, part_des_rejets_pourcent
    FROM quarantaine.v_taux_rejet_par_regle
    WHERE (%(source)s IS NULL OR source = %(source)s)
    ORDER BY rejets DESC
    LIMIT %(limite)s
"""

_PAR_GRAVITE = """
    SELECT source, gravite, rejets, regles_concernees
    FROM quarantaine.v_rejets_par_gravite
    WHERE (%(source)s IS NULL OR source = %(source)s)
    ORDER BY source, rejets DESC
"""


@dataclass(frozen=True)
class Depassement:
    source: str
    taux: float


# --------------------------------------------------------------------------- #
# Calcul et décision — testables sans base de données
# --------------------------------------------------------------------------- #


def taux_pourcent(lignes_lues: int | None, lignes_rejetees: int | None) -> float | None:
    """Part des lignes rejetées, en pourcentage.

    Renvoie None quand aucune ligne n'a été lue : un taux n'a alors pas de sens,
    et afficher 0 % laisserait croire que tout va bien alors que rien n'a été
    contrôlé.
    """
    lues = lignes_lues or 0
    if lues <= 0:
        return None
    return round(100.0 * (lignes_rejetees or 0) / lues, 2)


def depassements(lignes: list[dict], seuil: float) -> list[Depassement]:
    """Sources dont le taux de rejet dépasse le seuil.

    Une source sans taux — rien n'a été lu — n'est pas un dépassement : c'est
    une absence de mesure, signalée séparément.
    """
    au_dessus = []
    for ligne in lignes:
        taux = ligne.get("taux_rejet_pourcent")
        if taux is not None and float(taux) > seuil:
            au_dessus.append(Depassement(ligne["source"], float(taux)))
    return au_dessus


def sources_sans_mesure(lignes: list[dict]) -> list[str]:
    return [ligne["source"] for ligne in lignes if ligne.get("taux_rejet_pourcent") is None]


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #


def _lire(curseur, requete: str, **parametres) -> list[dict]:
    curseur.execute(requete, parametres)
    colonnes = [colonne.name for colonne in curseur.description]
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]


def collecter(source: str | None = None, limite: int = 10) -> tuple[list, list, list]:
    """Lit les trois vues : par source, par règle, par gravité."""
    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        par_source = _lire(curseur, _PAR_SOURCE, source=source)
        par_regle = _lire(curseur, _PAR_REGLE, source=source, limite=limite)
        par_gravite = _lire(curseur, _PAR_GRAVITE, source=source)
    return par_source, par_regle, par_gravite


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #


def _pourcent(valeur) -> str:
    return "     —" if valeur is None else f"{float(valeur):>5.2f} %"


def afficher(par_source: list[dict], par_regle: list[dict], par_gravite: list[dict]) -> None:
    print("\nTaux de rejet par source — dernière exécution\n")
    if not par_source:
        print("  Aucun contrôle de qualité n'a encore été exécuté.")
        print("  Lancer d'abord : python -m quality.controle --source olist\n")
        return

    print(f"  {'Source':<16}{'Lues':>12}{'Rejetées':>12}{'Taux':>10}{'Cumulé':>10}  Exéc.")
    for ligne in par_source:
        print(
            f"  {ligne['source']:<16}{ligne['lignes_lues']:>12}{ligne['lignes_rejetees']:>12}"
            f"{_pourcent(ligne['taux_rejet_pourcent']):>10}"
            f"{_pourcent(ligne['taux_rejet_cumule_pourcent']):>10}"
            f"  {ligne['executions']}"
        )

    if par_regle:
        print("\nRègles qui rejettent le plus\n")
        print(f"  {'Source':<12}{'Règle':<28}{'Gravité':<16}{'Rejets':>9}{'Part':>9}")
        for ligne in par_regle:
            print(
                f"  {ligne['source']:<12}{ligne['regle']:<28}{ligne['gravite']:<16}"
                f"{ligne['rejets']:>9}{_pourcent(ligne['part_des_rejets_pourcent']):>9}"
            )

    if par_gravite:
        print("\nRépartition par gravité\n")
        for ligne in par_gravite:
            print(
                f"  {ligne['source']:<12}{ligne['gravite']:<16}"
                f"{ligne['rejets']:>9} rejet(s) sur {ligne['regles_concernees']} règle(s)"
            )
    print()


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Taux de rejet du contrôle de qualité.")
    analyseur.add_argument("--source", help="n'examiner qu'une source, par exemple olist")
    analyseur.add_argument(
        "--seuil",
        type=float,
        metavar="POURCENT",
        help=f"échouer si une source dépasse ce taux (défaut du projet : {SEUIL_PAR_DEFAUT} %%)",
    )
    analyseur.add_argument(
        "--limite", type=int, default=10, help="nombre de règles affichées (défaut : 10)"
    )
    arguments = analyseur.parse_args(argv)

    try:
        par_source, par_regle, par_gravite = collecter(arguments.source, arguments.limite)
    except psycopg2.Error as erreur:
        premiere_ligne = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire les indicateurs ({premiere_ligne})", file=sys.stderr)
        print(
            "Vérifier que les services tournent et que les migrations sont appliquées.",
            file=sys.stderr,
        )
        return 1

    afficher(par_source, par_regle, par_gravite)

    for source in sources_sans_mesure(par_source):
        print(f"  ATTENTION : aucune ligne lue pour {source}, le taux n'a pas de sens.")

    if arguments.seuil is None:
        return 0

    au_dessus = depassements(par_source, arguments.seuil)
    if not au_dessus:
        print(f"  Toutes les sources sont sous le seuil de {arguments.seuil} %.\n")
        return 0

    print(f"\n  SEUIL DÉPASSÉ ({arguments.seuil} %) :")
    for depassement in au_dessus:
        print(f"    {depassement.source} — {depassement.taux} %")
    print("  Le chargement doit être interrompu et examiné.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
