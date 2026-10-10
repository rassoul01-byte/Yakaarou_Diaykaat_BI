"""Analyse les scores bruts du retrouveur externe.

Pour chaque question couverte (attendu=reponse), affiche le rang et le score
du passage attendu. Révèle si le retrouveur ramène le bon passage (rang bas)
ou s'il est noyé parmi les mauvais.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCORES = Path("data/scores_externe.jsonl")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", type=Path, default=SCORES)
    p.add_argument("--top", type=int, default=52)
    args = p.parse_args()

    jeu = [
        json.loads(ligne)
        for ligne in args.fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip()
    ]

    print(f"{len(jeu)} questions analysées\n")

    couvertes = [q for q in jeu if q["attendu"] == "reponse"]
    print(f"Questions couvertes ({len(couvertes)}) :\n")
    print(f"{'id':<5} {'attendu':<8} {'rang':>5} {'score':>7}  {'top 3 scores'}")
    print("-" * 80)

    rangs = []
    scores_attendus = []
    for q in couvertes[: args.top]:
        attendu = q["passage_attendu"]
        passages = q["passages"]
        rang = next((i for i, p in enumerate(passages, 1) if p["id"] == attendu), None)
        score = next((p["score"] for p in passages if p["id"] == attendu), None)
        top3 = " ".join(f"{p['score']:.3f}" for p in passages[:3])

        rangs.append(rang if rang is not None else 99)
        if score is not None:
            scores_attendus.append(score)

        rang_s = str(rang) if rang else "absent"
        score_s = f"{score:.4f}" if score is not None else "  --"
        print(f"{q['id']:<5} {attendu:<8} {rang_s:>5} {score_s:>7}  {top3}")

    print()
    print("Rang du passage attendu — distribution :")
    from collections import Counter

    compte = Counter(rangs)
    for rang in sorted(compte):
        label = f"rang {rang}" if rang < 99 else "absent"
        print(f"  {label:<10} : {compte[rang]} questions")

    if scores_attendus:
        print()
        print("Score du passage attendu :")
        print(f"  min    : {min(scores_attendus):.4f}")
        print(f"  max    : {max(scores_attendus):.4f}")
        print(f"  moyen  : {sum(scores_attendus) / len(scores_attendus):.4f}")
        print(f"  médian : {sorted(scores_attendus)[len(scores_attendus) // 2]:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
