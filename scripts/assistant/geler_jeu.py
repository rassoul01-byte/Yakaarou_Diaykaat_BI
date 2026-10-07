"""Valide le jeu de questions et calcule son empreinte de gel.

Vérifie que le fichier JSONL est bien formé, puis écrit un fichier compagnon
jeu_de_questions.gel.json avec la date et le SHA256. Ce fichier est la
référence : toute modification du jeu invalide l'empreinte.

Usage :
    python -m scripts.assistant.geler_jeu
    python -m scripts.assistant.geler_jeu --verifier
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

JEU = Path("tests/assistant/jeu_de_questions.jsonl")
GEL = JEU.with_suffix(".gel.json")

CHAMPS_OBLIGATOIRES = {"id", "question", "attendu", "passage", "categorie", "origine"}
ATTENDUS_VALIDES = {"reponse", "refus"}


def lire_lignes(chemin: Path) -> list[str]:
    return [ligne for ligne in chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]


def valider(chemin: Path) -> tuple[bool, list[str]]:
    """Vérifie le format du jeu. Retourne (ok, liste d'erreurs)."""
    erreurs: list[str] = []
    ids_vus: set[str] = set()

    for i, ligne in enumerate(lire_lignes(chemin), 1):
        try:
            q = json.loads(ligne)
        except json.JSONDecodeError as e:
            erreurs.append(f"ligne {i} : JSON invalide ({e})")
            continue

        manquants = CHAMPS_OBLIGATOIRES - set(q)
        if manquants:
            erreurs.append(f"ligne {i} : champs manquants {sorted(manquants)}")
            continue

        if q["id"] in ids_vus:
            erreurs.append(f"ligne {i} : id dupliqué {q['id']!r}")
        ids_vus.add(q["id"])

        if q["attendu"] not in ATTENDUS_VALIDES:
            erreurs.append(
                f"ligne {i} : attendu invalide {q['attendu']!r} "
                f"(attendu : {sorted(ATTENDUS_VALIDES)})"
            )

        if q["attendu"] == "reponse" and not q["passage"]:
            erreurs.append(f"ligne {i} : attendu='reponse' mais passage vide")

        if q["attendu"] == "refus" and q["passage"] is not None:
            erreurs.append(
                f"ligne {i} : attendu='refus' mais passage={q['passage']!r} (devrait être null)"
            )

    return (not erreurs, erreurs)


def sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def geler(chemin: Path) -> int:
    ok, erreurs = valider(chemin)
    if not ok:
        print("Jeu invalide, gel refusé :", file=sys.stderr)
        for e in erreurs:
            print(f"  - {e}", file=sys.stderr)
        return 1

    lignes = lire_lignes(chemin)
    empreinte = sha256(chemin)
    meta = {
        "date_gel": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha256": empreinte,
        "nb_questions": len(lignes),
        "fichier": chemin.name,
    }
    GEL.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Jeu gelé : {len(lignes)} questions")
    print(f"  SHA256 : {empreinte}")
    print(f"  Métadonnées : {GEL}")
    return 0


def verifier(chemin: Path) -> int:
    if not GEL.exists():
        print(f"{GEL} absent : le jeu n'a jamais été gelé.", file=sys.stderr)
        return 1
    meta = json.loads(GEL.read_text(encoding="utf-8"))
    empreinte_actuelle = sha256(chemin)
    if empreinte_actuelle != meta["sha256"]:
        print(
            f"Le jeu a été modifié depuis le gel du {meta['date_gel']} :\n"
            f"  gelé   : {meta['sha256']}\n"
            f"  actuel : {empreinte_actuelle}",
            file=sys.stderr,
        )
        return 1
    print(f"Jeu conforme au gel du {meta['date_gel']} ({meta['nb_questions']} questions).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--verifier", action="store_true")
    p.add_argument("--jeu", type=Path, default=JEU)
    args = p.parse_args()
    return verifier(args.jeu) if args.verifier else geler(args.jeu)


if __name__ == "__main__":
    sys.exit(main())
