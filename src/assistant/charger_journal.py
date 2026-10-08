"""Charge le journal de l'assistant dans PostgreSQL, pour le taux de réponses ancrées (F5.7).

    docker compose exec app python -m assistant.charger_journal --source evaluation
    docker compose exec app python -m assistant.charger_journal --source usage

Le journal reste un fichier .jsonl écrit par l'assistant (docs/contrats/assistant.md, §5). Ce
chargeur le copie dans `staging.journal_assistant`, que Power BI lit par les vues
`staging.v_taux_ancrage` et `staging.v_taux_ancrage_global`.

Deux sources, qui ne se mélangent jamais :

  evaluation  le jeu gelé rejoué par `assistant.evaluer --journal` : c'est la MESURE du
              dictionnaire. Chaque évaluation est un instantané : le chargement REMPLACE les
              lignes précédentes de cette source, pour qu'un rejeu ne gonfle pas les chiffres.
  usage       les questions posées à la main. Le chargement AJOUTE, sans jamais doubler : une
              ligne déjà chargée (même empreinte) est ignorée, donc on peut relancer sans risque.

La question est masquée une seconde fois au chargement : le fichier peut venir d'ailleurs que
de l'assistant, et la base ne doit jamais contenir de donnée personnelle.

Code de sortie : 0 si le chargement a eu lieu, 1 si le fichier est absent ou la base inaccessible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import psycopg2
import psycopg2.extras

from common.config import load_settings

from .journal import JOURNAL_DEFAUT, JOURNAL_EVALUATION, masquer

SOURCES = ("usage", "evaluation")

CHAMPS = (
    "id_echange",
    "source",
    "horodatage",
    "jour",
    "question",
    "refus",
    "motif",
    "passages_cites",
    "score_meilleur",
    "suggestions",
    "duree_ms",
    "retrouveur",
)

INSERTION = f"""
    INSERT INTO staging.journal_assistant ({", ".join(CHAMPS)})
    VALUES %s
    ON CONFLICT (id_echange) DO NOTHING
"""


@dataclass
class Bilan:
    lues: int = 0
    inserees: int = 0
    illisibles: list[tuple[int, str]] = field(default_factory=list)

    @property
    def deja_presentes(self) -> int:
        return self.lues - len(self.illisibles) - self.inserees


def chemin_du_journal(source: str, chemin: Path | str | None = None) -> Path:
    if chemin:
        return Path(chemin)
    if source == "evaluation":
        return JOURNAL_EVALUATION
    return Path(os.environ.get("ASSISTANT_JOURNAL") or JOURNAL_DEFAUT)


def _texte(entree: dict, cle: str) -> str:
    valeur = entree.get(cle)
    if not isinstance(valeur, str) or not valeur.strip():
        raise ValueError(f"« {cle} » absent ou vide")
    return valeur


def _liste(entree: dict, cle: str) -> list[str]:
    valeur = entree.get(cle, [])
    if not isinstance(valeur, list) or not all(isinstance(x, str) for x in valeur):
        raise ValueError(f"« {cle} » doit être une liste d'identifiants")
    return valeur


def _horodatage(texte: str) -> datetime:
    try:
        instant = datetime.fromisoformat(texte)
    except ValueError as erreur:
        raise ValueError(f"horodatage illisible : {texte!r}") from erreur
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def empreinte(source: str, ligne: str, rang: int) -> str:
    """Identifie une ligne du journal : stable d'un chargement à l'autre.

    `rang` compte les lignes identiques déjà vues dans le même fichier : deux échanges
    réellement identiques (même seconde, même question) restent deux échanges, et un
    rechargement donne les mêmes empreintes.
    """
    return hashlib.sha256(f"{source}\n{ligne}\n{rang}".encode()).hexdigest()[:40]


def en_ligne(entree: dict, source: str, id_echange: str) -> tuple:
    """Une entrée du journal devient une ligne de la table. Lève ValueError si elle est invalide."""
    if not isinstance(entree.get("refus"), bool):
        raise ValueError("« refus » doit être vrai ou faux")
    instant = _horodatage(_texte(entree, "horodatage")).astimezone(UTC)
    score = entree.get("score_meilleur")
    if score is not None and (isinstance(score, bool) or not isinstance(score, int | float)):
        raise ValueError("« score_meilleur » doit être un nombre ou null")
    duree = entree.get("duree_ms")
    if duree is not None and (isinstance(duree, bool) or not isinstance(duree, int | float)):
        raise ValueError("« duree_ms » doit être un nombre ou null")
    return (
        id_echange,
        source,
        instant,
        instant.date(),
        masquer(_texte(entree, "question")),
        entree["refus"],
        entree.get("motif"),
        _liste(entree, "passages_cites"),
        score,
        _liste(entree, "suggestions"),
        None if duree is None else round(duree),
        _texte(entree, "retrouveur"),
    )


def lire(chemin: Path, source: str) -> tuple[list[tuple], Bilan]:
    """Lit le journal. Une ligne illisible est signalée, jamais ignorée en silence."""
    bilan = Bilan()
    lignes: list[tuple] = []
    vues: Counter = Counter()
    with chemin.open(encoding="utf-8") as fichier:
        for numero, brute in enumerate(fichier, start=1):
            texte = brute.strip()
            if not texte:
                continue
            bilan.lues += 1
            try:
                entree = json.loads(texte)
                if not isinstance(entree, dict):
                    raise ValueError("une ligne doit être un objet JSON")
                lignes.append(en_ligne(entree, source, empreinte(source, texte, vues[texte])))
            except ValueError as erreur:  # json.JSONDecodeError en est un
                bilan.illisibles.append((numero, str(erreur)))
            vues[texte] += 1
    return lignes, bilan


def _ecrire(curseur, lot: list[tuple]) -> int:
    """Insère le lot et renvoie le nombre de lignes réellement ajoutées.

    `page_size=len(lot)` : sans cela, execute_values découpe en pages de 100 et `rowcount`
    ne refléterait que la dernière.
    """
    if not lot:
        return 0
    psycopg2.extras.execute_values(curseur, INSERTION, lot, page_size=len(lot))
    return curseur.rowcount


def charger(chemin: Path, source: str, dsn: str | None = None) -> Bilan:
    """Charge le journal en une transaction : tout est écrit, ou rien."""
    lignes, bilan = lire(chemin, source)
    connexion = psycopg2.connect(dsn or load_settings().postgres_dsn)
    try:
        with connexion, connexion.cursor() as curseur:
            if source == "evaluation":
                # Un instantané remplace le précédent : rejouer l'évaluation ne gonfle rien.
                curseur.execute(
                    "DELETE FROM staging.journal_assistant WHERE source = %s", (source,)
                )
            bilan.inserees = _ecrire(curseur, lignes)
    finally:
        connexion.close()
    return bilan


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Charge le journal de l'assistant dans PostgreSQL."
    )
    analyseur.add_argument("--source", choices=SOURCES, default="usage")
    analyseur.add_argument(
        "--journal", type=Path, help="fichier .jsonl (défaut : celui de la source)"
    )
    arguments = analyseur.parse_args(argv)

    chemin = chemin_du_journal(arguments.source, arguments.journal)
    if not chemin.exists():
        print(f"ERREUR : journal introuvable : {chemin}", file=sys.stderr)
        if arguments.source == "evaluation":
            print("Le produire : python -m assistant.evaluer --journal", file=sys.stderr)
        return 1

    try:
        bilan = charger(chemin, arguments.source)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : chargement impossible ({premiere})", file=sys.stderr)
        print(
            "Vérifier que la migration 020 est appliquée (scripts/appliquer_sql.py).",
            file=sys.stderr,
        )
        return 1

    print(f"\nJournal {arguments.source} : {chemin}")
    print(f"  lignes lues        : {bilan.lues}")
    print(f"  ajoutées           : {bilan.inserees}")
    print(f"  déjà présentes     : {bilan.deja_presentes}")
    print(f"  illisibles         : {len(bilan.illisibles)}")
    for numero, cause in bilan.illisibles[:10]:
        print(f"    ligne {numero} : {cause}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
