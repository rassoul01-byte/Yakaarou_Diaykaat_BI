"""Extrait les scores du retrouveur externe sur le jeu, une fois pour toutes.

Sortie : un JSONL où chaque ligne porte la question, l'attendu, et la liste
ordonnée des passages avec leur score. Ce fichier sert ensuite à balayer les
seuils en mémoire, sans rappeler Elasticsearch.

Usage :
    # Dans le conteneur (ES doit être peuplé) :
    docker compose exec app python -m scripts.assistant.mesurer_scores

    # Sortie par défaut :
    data/scores_externe.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from assistant.evaluer import lire_jeu
from assistant.fabrique import creer_retrouveur

JEU = Path("tests/assistant/jeu_de_questions.jsonl")
SORTIE = Path("data/scores_externe.jsonl")
K = 5


def main() -> int:
    p = argparse.ArgumentParser(description="Extrait les scores du retrouveur.")
    p.add_argument("--jeu", type=Path, default=JEU)
    p.add_argument("--sortie", type=Path, default=SORTIE)
    p.add_argument("-k", type=int, default=K, help="passages ramenés par question")
    args = p.parse_args()

    if not args.jeu.exists():
        print(f"Jeu introuvable : {args.jeu}", file=sys.stderr)
        return 1

    jeu = lire_jeu(args.jeu)
    retrouveur = creer_retrouveur()
    print(
        f"Retrouveur : {retrouveur.nom} — seuils {retrouveur.seuils}",
        file=sys.stderr,
    )
    print(f"Jeu        : {args.jeu} ({len(jeu)} questions)", file=sys.stderr)
    print(f"Sortie     : {args.sortie}", file=sys.stderr)
    print("", file=sys.stderr)

    args.sortie.parent.mkdir(parents=True, exist_ok=True)

    with args.sortie.open("w", encoding="utf-8") as f:
        for i, q in enumerate(jeu, 1):
            passages = retrouveur.retrouver(q["question"], k=args.k)
            ligne = {
                "id": q["id"],
                "question": q["question"],
                "attendu": q["attendu"],
                "passage_attendu": q.get("passage"),
                "categorie": q.get("categorie"),
                "passages": [
                    {"id": p.id, "score": p.score, "theme": p.theme, "source": p.source}
                    for p in passages
                ],
            }
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            marqueur = "" if passages else "  (aucun passage)"
            print(
                f"  [{i:>2}/{len(jeu)}] {q['id']:<5} {q['question'][:45]:<45}{marqueur}",
                file=sys.stderr,
            )

    print(f"\nScores écrits dans {args.sortie}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
