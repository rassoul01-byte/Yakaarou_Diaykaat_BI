"""Balaye les seuils (reponse, suggestion, marge) sur les scores extraits.

Ne rappelle PAS Elasticsearch : tout se fait en mémoire sur
data/scores_externe.jsonl. Affiche les combinaisons valides
(mauvais_passage == 0 et reponse_a_tort == 0), triées par faux_refus
croissant puis bonnes réponses décroissantes.

Usage :
    docker compose exec app python -m scripts.assistant.balayer_seuils
    docker compose exec app python -m scripts.assistant.balayer_seuils --top 50
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from assistant.garde_fous import Seuils, decider
from assistant.passages import Passage

SCORES = Path("data/scores_externe.jsonl")


def charger(chemin: Path) -> list[dict]:
    return [
        json.loads(ligne)
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip()
    ]


def juger(item: dict, seuils: Seuils) -> str:
    """Verdict d'une question, avec les mêmes règles que assistant.evaluer."""
    passages = [
        Passage(
            id=p["id"],
            theme=p["theme"],
            question="",
            reponse="",
            source=p["source"],
            score=p["score"],
        )
        for p in item["passages"]
    ]
    decision = decider(passages, seuils)

    if item["attendu"] == "refus":
        return "refus correct" if decision.retenu is None else "réponse à tort"

    attendu = item["passage_attendu"]
    if decision.retenu is not None:
        return "bonne réponse" if decision.retenu.id == attendu else "mauvais passage"
    if any(p.id == attendu for p in decision.suggestions):
        return "refus avec bonne suggestion"
    return "faux refus"


def evaluer(jeu: list[dict], seuils: Seuils) -> Counter:
    return Counter(juger(item, seuils) for item in jeu)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", type=Path, default=SCORES)
    p.add_argument("--pas-reponse", type=float, default=0.02)
    p.add_argument("--pas-suggestion", type=float, default=0.02)
    p.add_argument("--pas-marge", type=float, default=0.01)
    p.add_argument("--top", type=int, default=30)
    args = p.parse_args()

    if not args.fichier.exists():
        print(f"Fichier introuvable : {args.fichier}", file=sys.stderr)
        print("Lance d'abord : python -m scripts.assistant.mesurer_scores", file=sys.stderr)
        return 1

    jeu = charger(args.fichier)
    print(f"{len(jeu)} questions chargées depuis {args.fichier}\n")

    resultats = []
    r = 0.20
    while r <= 0.90 + 1e-9:
        s = 0.10
        while s <= r + 1e-9:
            m = 0.00
            while m <= 0.30 + 1e-9:
                seuils = Seuils(
                    reponse=round(r, 4),
                    suggestion=round(s, 4),
                    marge=round(m, 4),
                )
                compte = evaluer(jeu, seuils)
                if compte["mauvais passage"] == 0 and compte["réponse à tort"] == 0:
                    resultats.append((seuils, compte))
                m += args.pas_marge
            s += args.pas_suggestion
        r += args.pas_reponse

    resultats.sort(key=lambda x: (x[1]["faux refus"], -x[1]["bonne réponse"], x[0].marge))

    print(f"{len(resultats)} combinaisons valides (mauvais=0, à tort=0)\n")
    if not resultats:
        print("AUCUNE COMBINAISON VALIDE. Il faut élargir la grille de balayage.")
        return 1

    print(
        f"{'reponse':>8} {'suggest':>8} {'marge':>7} | "
        f"{'bonne':>6} {'sugg':>5} {'faux':>5} {'hors':>5}"
    )
    print("-" * 62)
    for seuils, c in resultats[: args.top]:
        print(
            f"{seuils.reponse:>8.3f} {seuils.suggestion:>8.3f} {seuils.marge:>7.3f} | "
            f"{c['bonne réponse']:>6} {c['refus avec bonne suggestion']:>5} "
            f"{c['faux refus']:>5} {c['refus correct']:>5}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
