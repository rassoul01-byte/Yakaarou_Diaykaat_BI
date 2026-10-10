"""Rapport du taux de rejet.

Répond à trois questions, dans cet ordre : est-ce que la qualité se dégrade,
sur quelle source, et à cause de quelle règle.

Les définitions sont dans docs/dictionnaire_indicateurs.md, le calcul dans
sql/005_vues_taux_de_rejet.sql. Ce module ne calcule rien lui-même : il lit les
vues et met en forme. Le seuil, lui, est une décision — elle est ici.

Il complète le taux de rejet par trois mesures : les lignes marquées par les règles
non bloquantes, les lignes supprimées en silence, et l'évolution du taux d'une
exécution à l'autre. Ces lignes ne comptent pas dans le taux de rejet : elles ne
sont pas en quarantaine.

Usage :
    docker compose exec app python -m quality.rapport
    docker compose exec app python -m quality.rapport --seuil 5
    docker compose exec app python -m quality.rapport --source olist
    docker compose exec app python -m quality.rapport --historique 10

Code de sortie : 0 si tout est sous le seuil, 1 si une source le dépasse ou si
la base est injoignable. C'est ce code qu'Airflow lira au Sprint 3 pour
interrompre la chaîne quotidienne.
"""

from __future__ import annotations

import argparse
import json
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

# Le journal de qualité garde, dans sa colonne message, le détail règle par règle de la
# dernière exécution de chaque source : c'est là que sont comptées les lignes marquées
# et supprimées, qui n'ont pas d'entrée en quarantaine.
_DERNIER_JOURNAL = """
    SELECT DISTINCT ON (source) source, message
    FROM staging.execution_log
    WHERE pipeline = 'qualite'
      AND (%(source)s IS NULL OR source = %(source)s)
    ORDER BY source, demarre_a DESC, id DESC
"""

_HISTORIQUE = """
    SELECT execution_id, source, demarre_a, lignes_lues, lignes_rejetees, taux_rejet_pourcent
    FROM quarantaine.v_taux_rejet_par_execution
    WHERE (%(source)s IS NULL OR source = %(source)s)
    ORDER BY source, demarre_a, execution_id
"""

# Nombre d'exécutions affichées par source dans l'évolution du taux.
HISTORIQUE_PAR_DEFAUT = 5


@dataclass(frozen=True)
class Depassement:
    source: str
    taux: float


# --------------------------------------------------------------------------- #
# Calcul et décision — testables sans base de données
# --------------------------------------------------------------------------- #


# Le dictionnaire des indicateurs désigne `quarantaine.v_taux_rejet_par_source`
# comme le **calcul** du taux de rejet. Cette fonction est l'écriture Python de
# la même formule : elle doit arrondir comme la vue, sinon le même indicateur
# vaut deux choses selon qui le lit. La vue arrondit à trois décimales
# (sql/005, sql/011) ; ce nombre est ici pour qu'on ne le change que d'un côté.
DECIMALES_DU_TAUX = 3


def taux_pourcent(lignes_lues: int | None, lignes_rejetees: int | None) -> float | None:
    """Part des lignes rejetées, en pourcentage.

    Renvoie None quand aucune ligne n'a été lue : un taux n'a alors pas de sens,
    et afficher 0 % laisserait croire que tout va bien alors que rien n'a été
    contrôlé.

    L'arrondi est celui de la vue, à trois décimales. Avec deux, 19 lignes
    rejetées sur 94 donnaient 20,21 ici et 20,213 en base : deux valeurs pour
    un seul indicateur, et une comparaison au seuil qui pouvait basculer d'un
    côté à l'autre selon l'endroit où le taux avait été calculé.
    """
    lues = lignes_lues or 0
    if lues <= 0:
        return None
    return round(100.0 * (lignes_rejetees or 0) / lues, DECIMALES_DU_TAUX)


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


def extraire_mesures(source: str, message: str | None) -> list[dict]:
    """Lignes marquées et lignes supprimées, règle par règle, d'après le journal.

    - marquées : conservées mais signalées par la règle (clé « anomalies ») ;
    - supprimées : retirées du flux sans rejet (doublons stricts).

    Les règles qui n'ont rien signalé ni supprimé ne sont pas listées. Un message
    absent ou illisible donne une liste vide : le rapport n'échoue pas pour ça.
    """
    try:
        detail = json.loads(message) if message else {}
    except (TypeError, ValueError):
        return []
    if not isinstance(detail, dict):
        return []

    mesures = []
    for controle in detail.get("controles") or []:
        marquees = int(controle.get("anomalies") or 0)
        supprimees = int(controle.get("lignes_supprimees") or 0)
        if marquees or supprimees:
            mesures.append(
                {
                    "source": source,
                    "regle": controle.get("regle", "?"),
                    "gravite": controle.get("gravite", ""),
                    "lignes_marquees": marquees,
                    "lignes_supprimees": supprimees,
                }
            )
    return sorted(
        mesures, key=lambda m: (m["source"], -(m["lignes_marquees"] + m["lignes_supprimees"]))
    )


def evolution(executions: list[dict], limite: int = HISTORIQUE_PAR_DEFAUT) -> list[dict]:
    """Les dernières exécutions de chaque source, avec la variation du taux de l'une à l'autre.

    `executions` est trié par source puis par date. La variation d'une exécution se
    calcule par rapport à la précédente, même si celle-ci sort de la fenêtre affichée.
    Elle est absente (None) pour la première exécution d'une source ou quand l'une
    des deux n'a pas de taux.
    """
    par_source: dict[str, list[dict]] = {}
    for ligne in executions:
        par_source.setdefault(ligne["source"], []).append(ligne)

    resultat = []
    for source, lignes in par_source.items():
        suivies = []
        precedent = None
        for numero, ligne in enumerate(lignes, start=1):
            taux = ligne.get("taux_rejet_pourcent")
            variation = None
            if taux is not None and precedent is not None:
                variation = round(float(taux) - float(precedent), 2)
            suivies.append({**ligne, "source": source, "numero": numero, "variation": variation})
            precedent = taux
        resultat.extend(suivies[-limite:] if limite > 0 else [])
    return resultat


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


def collecter_complements(
    source: str | None = None, historique: int = HISTORIQUE_PAR_DEFAUT
) -> tuple[list[dict], list[dict]]:
    """Lit les lignes marquées/supprimées de la dernière exécution et l'évolution du taux."""
    with psycopg2.connect(load_settings().postgres_dsn) as connexion, connexion.cursor() as curseur:
        journaux = _lire(curseur, _DERNIER_JOURNAL, source=source)
        executions = _lire(curseur, _HISTORIQUE, source=source)
    mesures = []
    for journal in journaux:
        mesures.extend(extraire_mesures(journal["source"], journal["message"]))
    return mesures, evolution(executions, historique)


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #


def _pourcent(valeur) -> str:
    return "     —" if valeur is None else f"{float(valeur):>5.2f} %"


def afficher(par_source: list[dict], par_regle: list[dict], par_gravite: list[dict]) -> None:
    print("\nTaux de rejet par source — dernière exécution\n")
    if not par_source:
        print("  Aucun contrôle de qualité n'a encore été exécuté.")
        print(
            "  Lancer d'abord : python -m quality.controle --source olist "
            "--ingestion AAAAMMJJTHHMMSS\n"
        )
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


def _variation(valeur) -> str:
    return "         —" if valeur is None else f"{float(valeur):>+7.2f} pt"


def afficher_complements(mesures: list[dict], historique: list[dict]) -> None:
    if mesures:
        print("Lignes marquées ou supprimées — dernière exécution de chaque source\n")
        print(f"  {'Source':<12}{'Règle':<28}{'Gravité':<16}{'Marquées':>10}{'Supprimées':>12}")
        for ligne in mesures:
            print(
                f"  {ligne['source']:<12}{ligne['regle']:<28}{ligne['gravite']:<16}"
                f"{ligne['lignes_marquees']:>10}{ligne['lignes_supprimees']:>12}"
            )
        print(
            "\n  Marquées : conservées, mais signalées par la règle."
            "\n  Supprimées : retirées du flux sans rejet. Aucune des deux n'est dans le taux de rejet.\n"
        )

    if historique:
        print("Évolution du taux de rejet — dernières exécutions\n")
        print(
            f"  {'Source':<12}{'N°':>4}  {'Date':<17}{'Lues':>11}{'Rejetées':>10}{'Taux':>10}{'Variation':>12}"
        )
        for ligne in historique:
            date = ligne["demarre_a"].strftime("%Y-%m-%d %H:%M") if ligne.get("demarre_a") else "—"
            print(
                f"  {ligne['source']:<12}{ligne['numero']:>4}  {date:<17}"
                f"{ligne['lignes_lues']:>11}{ligne['lignes_rejetees']:>10}"
                f"{_pourcent(ligne['taux_rejet_pourcent']):>10}{_variation(ligne['variation']):>12}"
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
    analyseur.add_argument(
        "--historique",
        type=int,
        default=HISTORIQUE_PAR_DEFAUT,
        help=f"exécutions affichées par source (défaut : {HISTORIQUE_PAR_DEFAUT})",
    )
    arguments = analyseur.parse_args(argv)

    try:
        par_source, par_regle, par_gravite = collecter(arguments.source, arguments.limite)
        mesures, historique = collecter_complements(arguments.source, arguments.historique)
    except psycopg2.Error as erreur:
        premiere_ligne = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire les indicateurs ({premiere_ligne})", file=sys.stderr)
        print(
            "Vérifier que les services tournent et que les migrations sont appliquées.",
            file=sys.stderr,
        )
        return 1

    afficher(par_source, par_regle, par_gravite)
    if par_source:
        afficher_complements(mesures, historique)

    for source in sources_sans_mesure(par_source):
        print(f"  ATTENTION : aucune ligne lue pour {source}, le taux n'a pas de sens.")

    if arguments.seuil is None:
        return 0

    # Une absence de mesure n'est pas un succès. Sans ce contrôle, un garde-fou
    # qui n'a RIEN mesuré sortait 0 et laissait la chaîne charger l'entrepôt :
    # `v_taux_rejet_par_source` est vide dès que `staging.execution_log` l'est,
    # et cette table n'est créée par aucune migration — seulement par le script
    # d'initialisation du premier démarrage. Sur une base reconstruite par
    # `scripts/appliquer_sql.py`, le rapport passait donc au vert sans rien voir.
    if not par_source:
        print(
            "\n  AUCUNE MESURE DE QUALITÉ : la vue quarantaine.v_taux_rejet_par_source\n"
            "  est vide. Le seuil ne peut pas être vérifié, et une absence de mesure\n"
            "  n'est pas une absence de rejet.\n"
            "  Lancer un contrôle (python -m quality.controle --source ...), et\n"
            "  vérifier que staging.execution_log existe et est alimentée.\n",
            file=sys.stderr,
        )
        return 1

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
