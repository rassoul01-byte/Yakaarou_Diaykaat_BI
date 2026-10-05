"""Requêtes sans résultat (F4.5) : ce que les visiteurs cherchent et ne trouvent pas.

Usage :
    docker compose exec app python -m recherche.sans_resultat
    docker compose exec app python -m recherche.sans_resultat --top 50 --analyser 500

Principe :
    1. lire les requêtes les plus fréquentes (`staging.v_requetes_frequentes`,
       regroupement du journal alimenté par `python -m compteurs`) ;
    2. rejouer chaque requête dans l'index avec **la même recherche que
       l'acheteur** (`moteur.rechercher_plusieurs`) ;
    3. garder celles qui ne ramènent rien, classées par fréquence.

⚠️ Les requêtes du générateur sont tirées des désignations du catalogue : elles
ressemblent à des fragments de titres (« 01h20 échelle alloy mini ») plutôt
qu'à des recherches humaines. Le dispositif est juste, les requêtes ne le sont
pas. À dire en démonstration — et c'est noté au dictionnaire.

Code de sortie : 0 si l'analyse a pu être menée à terme (même s'il y a des
requêtes sans résultat), 1 si le journal ou Elasticsearch est inaccessible.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import psycopg2
import psycopg2.extras
from elasticsearch.exceptions import ApiError, TransportError

from common.config import load_settings

from .client import adresse, connexion
from .moteur import rechercher_plusieurs

TAILLE_LOT = 50  # requêtes par envoi : assez pour aller vite, peu pour ménager la mémoire

# Le regroupement par requête, toutes journées confondues, est une vue
# versionnée (sql/016_vue_requetes_frequentes.sql) : le calcul ne vit pas dans
# le code. Ce module ne fait que la lire, puis rejouer les requêtes.
REQUETE_JOURNAL = """
    SELECT requete, occurrences, jours
    FROM staging.v_requetes_frequentes
    ORDER BY occurrences DESC, requete
    LIMIT %(limite)s
"""


@dataclass(frozen=True)
class RequeteJournal:
    requete: str
    occurrences: int
    jours: int


@dataclass(frozen=True)
class Bilan:
    analysees: int  # requêtes distinctes rejouées
    occurrences_analysees: int  # nombre total de recherches qu'elles représentent
    sans_resultat: list[RequeteJournal]  # classées par fréquence décroissante

    @property
    def occurrences_sans_resultat(self) -> int:
        return sum(r.occurrences for r in self.sans_resultat)

    @property
    def part_des_recherches(self) -> float | None:
        """Part des recherches (pas des requêtes distinctes) restées sans résultat.

        None si rien n'a été analysé : un taux sur zéro recherche est
        indéfini, pas égal à 0 %.
        """
        if not self.occurrences_analysees:
            return None
        return 100.0 * self.occurrences_sans_resultat / self.occurrences_analysees


def lire_journal(limite: int = 200, dsn: str | None = None) -> list[RequeteJournal]:
    """Les requêtes les plus fréquentes du journal, toutes journées confondues."""
    with (
        psycopg2.connect(dsn or load_settings().postgres_dsn) as connexion_pg,
        connexion_pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as curseur,
    ):
        curseur.execute(REQUETE_JOURNAL, {"limite": limite})
        return [RequeteJournal(**ligne) for ligne in curseur.fetchall()]


def trouver_sans_resultat(client, journal: list[RequeteJournal], taille_lot: int = TAILLE_LOT):
    """Rejoue le journal dans l'index et garde ce qui ne ramène rien."""
    sans_resultat: list[RequeteJournal] = []
    for debut in range(0, len(journal), taille_lot):
        lot = journal[debut : debut + taille_lot]
        # taille=0 : on ne veut que le nombre de fiches, pas les fiches.
        reponses = rechercher_plusieurs(client, [r.requete for r in lot], taille=0)
        sans_resultat += [r for r, rep in zip(lot, reponses, strict=True) if not rep.aboutit]

    sans_resultat.sort(key=lambda r: (-r.occurrences, r.requete))
    return Bilan(
        analysees=len(journal),
        occurrences_analysees=sum(r.occurrences for r in journal),
        sans_resultat=sans_resultat,
    )


def afficher(bilan: Bilan, top: int) -> None:
    print("\nRequêtes sans résultat\n")
    if not bilan.analysees:
        print("  Journal vide.")
        print("  Lancer le générateur, puis : python -m compteurs\n")
        return

    print(f"  requêtes distinctes analysées : {bilan.analysees}")
    print(f"  sans résultat                 : {len(bilan.sans_resultat)}")
    part = bilan.part_des_recherches
    print(f"  part des recherches           : {'indéfinie' if part is None else f'{part:.1f} %'}\n")

    if bilan.sans_resultat:
        print(f"  {'Requête':<50}{'Occurrences':>12}{'Jours':>7}")
        for r in bilan.sans_resultat[:top]:
            print(f"  {r.requete[:49]:<50}{r.occurrences:>12}{r.jours:>7}")
    print(
        "\n  Trafic simulé : les requêtes sont des fragments de titres du catalogue,"
        "\n  pas des recherches humaines. Le dispositif est juste, les requêtes ne le sont pas.\n"
    )


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Requêtes sans résultat.")
    analyseur.add_argument("--top", type=int, default=20, help="requêtes affichées")
    analyseur.add_argument("--analyser", type=int, default=200, help="requêtes rejouées")
    arguments = analyseur.parse_args(argv)

    try:
        journal = lire_journal(arguments.analyser)
        bilan = trouver_sans_resultat(connexion(), journal)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire le journal ({premiere})", file=sys.stderr)
        return 1
    except (ApiError, TransportError) as erreur:
        print(
            f"ERREUR : Elasticsearch n'a pas répondu ({erreur.__class__.__name__})",
            file=sys.stderr,
        )
        print(f"Vérifier que le service tourne : {adresse()}", file=sys.stderr)
        return 1

    afficher(bilan, arguments.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
