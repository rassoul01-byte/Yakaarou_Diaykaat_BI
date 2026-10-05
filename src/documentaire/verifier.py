"""Vérification de la foire aux questions.

Contrat : docs/contrats/faq.md
Lancement : python -m documentaire.verifier
Code de sortie : 0 si le fichier est conforme, 1 sinon.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

FICHIER_PAR_DEFAUT = Path("docs/documentaire/faq.jsonl")

# thème -> préfixe de l'identifiant
THEMES = {
    "livraison": "liv",
    "retours": "ret",
    "paiement": "pai",
    "commande": "cmd",
    "compte": "cpt",
}
CHAMPS = ("id", "theme", "question", "reponse", "source", "maj")
PREFIXES_SOURCE = ("donnee:", "politique:")
TOTAL_MIN = 30
TOTAL_MAX = 50
PAR_THEME_MIN = 5


def charger(chemin: Path) -> tuple[list[tuple[int, object]], list[str]]:
    """Lit le fichier ligne par ligne : renvoie les objets JSON et les erreurs de lecture."""
    lignes: list[tuple[int, object]] = []
    erreurs: list[str] = []
    with chemin.open(encoding="utf-8") as fichier:
        for numero, texte in enumerate(fichier, start=1):
            if not texte.strip():
                continue
            try:
                lignes.append((numero, json.loads(texte)))
            except json.JSONDecodeError as exc:
                erreurs.append(f"ligne {numero} : JSON invalide ({exc.msg})")
    return lignes, erreurs


def _texte(entree: dict, champ: str) -> str:
    valeur = entree.get(champ)
    return valeur if isinstance(valeur, str) else ""


def _verifier_entree(numero: int, entree: object) -> list[str]:
    """Contrôles d'une seule ligne : champs, thème, préfixe, source, date."""
    if not isinstance(entree, dict):
        return [f"ligne {numero} : l'entrée n'est pas un objet JSON"]

    erreurs = [
        f"ligne {numero} : champ « {champ} » absent ou vide"
        for champ in CHAMPS
        if not _texte(entree, champ).strip()
    ]
    if erreurs:
        return erreurs

    theme = entree["theme"]
    if theme not in THEMES:
        erreurs.append(f"ligne {numero} : thème inconnu « {theme} »")
    elif entree["id"].split("-")[0] != THEMES[theme]:
        attendu = f"{THEMES[theme]}-"
        erreurs.append(
            f"ligne {numero} : le préfixe de l'id « {entree['id']} » ne correspond pas "
            f"au thème « {theme} » (attendu « {attendu} »)"
        )

    prefixe, _, reste = entree["source"].partition(":")
    if f"{prefixe}:" not in PREFIXES_SOURCE or not reste.strip():
        erreurs.append(
            f"ligne {numero} : source « {entree['source']} » invalide "
            "(attendu « donnee:... » ou « politique:... »)"
        )

    maj = entree["maj"]
    try:
        if len(maj) != 10:
            raise ValueError
        date.fromisoformat(maj)
    except ValueError:
        erreurs.append(f"ligne {numero} : date « {maj} » invalide (attendu AAAA-MM-JJ)")
    return erreurs


def verifier(lignes: list[tuple[int, object]]) -> list[str]:
    """Renvoie la liste des erreurs ; une liste vide signifie un fichier conforme."""
    erreurs: list[str] = []
    for numero, entree in lignes:
        erreurs.extend(_verifier_entree(numero, entree))

    entrees = [entree for _, entree in lignes if isinstance(entree, dict)]

    identifiants = Counter(_texte(e, "id") for e in entrees if _texte(e, "id"))
    for identifiant, nombre in identifiants.items():
        if nombre > 1:
            erreurs.append(f"id « {identifiant} » en double ({nombre} fois)")

    questions = Counter(
        _texte(e, "question").strip().lower() for e in entrees if _texte(e, "question")
    )
    for question, nombre in questions.items():
        if nombre > 1:
            erreurs.append(f"la question « {question} » apparaît {nombre} fois")

    total = len(lignes)
    if not TOTAL_MIN <= total <= TOTAL_MAX:
        erreurs.append(f"total de {total} question(s) : attendu entre {TOTAL_MIN} et {TOTAL_MAX}")

    par_theme = Counter(_texte(e, "theme") for e in entrees)
    for theme in THEMES:
        if par_theme[theme] < PAR_THEME_MIN:
            erreurs.append(
                f"thème « {theme} » : {par_theme[theme]} question(s), "
                f"au moins {PAR_THEME_MIN} attendues"
            )
    return erreurs


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Vérifie la foire aux questions.")
    parseur.add_argument("--fichier", type=Path, default=FICHIER_PAR_DEFAUT)
    args = parseur.parse_args(argv)

    if not args.fichier.is_file():
        print(f"ERREUR : fichier introuvable : {args.fichier}")
        return 1

    lignes, erreurs = charger(args.fichier)
    erreurs += verifier(lignes)

    par_theme = Counter(_texte(e, "theme") for _, e in lignes if isinstance(e, dict))
    print(f"Foire aux questions : {args.fichier}")
    for theme in THEMES:
        print(f"  {theme:<10} {par_theme[theme]:>3}")
    print(f"  {'total':<10} {len(lignes):>3}")

    if erreurs:
        print(f"\n{len(erreurs)} erreur(s) :")
        for message in erreurs:
            print(f"  - {message}")
        return 1
    print("\nFichier conforme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
