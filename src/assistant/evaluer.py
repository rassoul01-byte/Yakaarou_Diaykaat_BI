"""Évalue l'assistant sur un jeu de questions fixé.

    docker compose exec app python -m assistant.evaluer
    docker compose exec app python -m assistant.evaluer --jeu tests/assistant/jeu_de_questions.jsonl
    docker compose exec app python -m assistant.evaluer --journal   # + journal de l'évaluation

Chaque question porte ce qu'on attend : une réponse (avec le bon passage) ou un refus.
Ce qui se mesure, du plus grave au moins grave :

  réponse à tort      une question hors base reçoit une réponse : l'assistant affirme
                      ce qu'il ne sait pas. Doit valoir 0.
  mauvais passage     une question couverte reçoit la réponse d'un AUTRE passage :
                      une réponse fausse, citée. Doit valoir 0.
  faux refus          une question couverte est refusée sans suggestion : on perd un client.
  bien orientée       une question couverte reçoit la réponse attendue, ou un refus qui
                      suggère le bon passage.

Le taux de réponses ancrées vaut 100 % par construction (une réponse sans citation ne peut
pas être construite). Il est mesuré ici sur le jeu, pas sur des exemples choisis.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .assistant import Reponse, repondre
from .fabrique import creer_retrouveur
from .garde_fous import Seuils
from .journal import JOURNAL_EVALUATION, JournalFichier
from .retrouveur import Retrouveur

JEU = Path(__file__).resolve().parents[2] / "tests" / "assistant" / "jeu_de_questions.jsonl"


def lire_jeu(chemin: Path = JEU) -> list[dict]:
    return [
        json.loads(ligne)
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip()
    ]


def juger(question: dict, reponse: Reponse) -> str:
    """Le verdict d'une question : un des mots de la liste du module."""
    if question["attendu"] == "refus":
        return "refus correct" if reponse.refus else "réponse à tort"
    if not reponse.refus:
        return (
            "bonne réponse" if reponse.passages[0].id == question["passage"] else "mauvais passage"
        )
    if any(p.id == question["passage"] for p in reponse.suggestions):
        return "refus avec bonne suggestion"
    return "faux refus"


def evaluer(
    retrouveur: Retrouveur, jeu: list[dict], seuils: Seuils | None = None, journal=None
) -> list[tuple[dict, Reponse, str]]:
    return [
        (q, (r := repondre(q["question"], retrouveur, seuils=seuils, journal=journal)), juger(q, r))
        for q in jeu
    ]


def synthese(resultats: list[tuple[dict, Reponse, str]]) -> dict[str, int]:
    verdicts = Counter(v for _, _, v in resultats)
    couvertes = [x for x in resultats if x[0]["attendu"] == "reponse"]
    refus_attendus = [x for x in resultats if x[0]["attendu"] == "refus"]
    return {
        "questions": len(resultats),
        "couvertes": len(couvertes),
        "hors_base": len(refus_attendus),
        "bonne réponse": verdicts["bonne réponse"],
        "refus avec bonne suggestion": verdicts["refus avec bonne suggestion"],
        "faux refus": verdicts["faux refus"],
        "mauvais passage": verdicts["mauvais passage"],
        "refus correct": verdicts["refus correct"],
        "réponse à tort": verdicts["réponse à tort"],
        "ancrées": sum(1 for _, r, _ in resultats if r.refus or r.passages),
    }


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Évalue l'assistant sur un jeu de questions fixé."
    )
    analyseur.add_argument("--jeu", type=Path, default=JEU)
    analyseur.add_argument("--detail", action="store_true", help="liste les questions mal traitées")
    analyseur.add_argument(
        "--journal",
        nargs="?",
        const=JOURNAL_EVALUATION,
        type=Path,
        help="écrit chaque échange dans ce journal (défaut : celui de l'évaluation), à charger "
        "ensuite par assistant.charger_journal --source evaluation",
    )
    arguments = analyseur.parse_args(argv)

    journal = None
    if arguments.journal:
        arguments.journal.unlink(missing_ok=True)  # l'évaluation est un instantané, pas un cumul
        journal = JournalFichier(arguments.journal)

    retrouveur = creer_retrouveur()
    resultats = evaluer(retrouveur, lire_jeu(arguments.jeu), journal=journal)
    s = synthese(resultats)

    print(
        f"\nÉvaluation — {s['questions']} questions ({s['couvertes']} couvertes, {s['hors_base']} hors base)"
    )
    print(f"recherche : {retrouveur.nom}, seuils {retrouveur.seuils}\n")
    print(f"  Questions couvertes ({s['couvertes']})")
    print(f"    bonne réponse                 {s['bonne réponse']:>3}")
    print(f"    refus avec bonne suggestion   {s['refus avec bonne suggestion']:>3}")
    print(f"    faux refus                    {s['faux refus']:>3}")
    print(f"    MAUVAIS PASSAGE               {s['mauvais passage']:>3}   <- doit valoir 0")
    print(f"  Questions hors base ({s['hors_base']})")
    print(f"    refus correct                 {s['refus correct']:>3}")
    print(f"    RÉPONSE À TORT                {s['réponse à tort']:>3}   <- doit valoir 0")
    print(f"\n  réponses ancrées (citation ou refus) : {s['ancrées']}/{s['questions']}\n")

    par_categorie: dict[str, Counter] = defaultdict(Counter)
    for q, _, v in resultats:
        par_categorie[q["categorie"]][v] += 1
    print("  Par catégorie :")
    for categorie, compte in par_categorie.items():
        print(f"    {categorie:<28} " + ", ".join(f"{n} {v}" for v, n in compte.most_common()))

    if arguments.detail:
        print("\n  À regarder :")
        for q, r, v in resultats:
            if v in ("faux refus", "mauvais passage", "réponse à tort"):
                cite = r.passages[0].id if r.passages else (r.motif or "")
                print(f"    [{v}] {q['question']}  -> {cite}")
    print()
    return 0 if not (s["mauvais passage"] or s["réponse à tort"]) else 1


if __name__ == "__main__":
    sys.exit(main())
