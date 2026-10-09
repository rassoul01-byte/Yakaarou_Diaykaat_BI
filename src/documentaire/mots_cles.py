"""Mots-clés candidats pour chaque passage de la foire aux questions.

Contrat : docs/contrats/faq.md
Lancement : python -m documentaire.mots_cles [--par-passage 6] [--json]

Le script PROPOSE des mots, il n'écrit rien dans faq.jsonl : une personne
valide les mots avant qu'ils entrent dans la base. Un mot est retenu s'il
distingue un passage des autres : les mots présents partout (« commande »,
« compte ») sont écartés, les mots de la question comptent plus que ceux de
la réponse.
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

FICHIER_PAR_DEFAUT = Path("docs/documentaire/faq.jsonl")

# Un mot présent dans plus de cette part des passages ne distingue rien.
PART_MAX_PASSAGES = 0.15
POIDS_QUESTION = 3
LONGUEUR_MIN = 4

MOTS_VIDES = frozenset(
    """
    alors apres aucun aucune aussi autre autres avec avez avoir avons beaucoup
    cela celle celles celui cette ceux chaque comme comment dans dont donc elle
    elles encore entre est etes etre faire fait faut leur leurs mais meme mes
    moins notre nous parce pour pourquoi plus puis quand quel quelle quelles
    quels que quoi sans sera seront ses sont sous sur tous tout toute toutes
    tres votre vos vous suis lieu doit doivent doivent peut peux peuvent ensuite
    arrive arrivent grande grand avant lors ainsi voir etat deja tant
    """.split()
)


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _racine(mot: str) -> str:
    """Racine grossière : sans accents, sans pluriel (statuts -> statut)."""
    mot = _sans_accents(mot.lower())
    if mot in MOTS_VIDES:
        return mot
    if len(mot) > LONGUEUR_MIN and mot.endswith(("s", "x")):
        mot = mot[:-1]
    return mot


def _mots(texte: str) -> list[tuple[str, str]]:
    """(racine, forme d'origine) des mots utiles d'un texte."""
    resultat = []
    for forme in re.findall(r"[^\W\d_]+", texte.lower()):
        racine = _racine(forme)
        if len(racine) >= LONGUEUR_MIN and racine not in MOTS_VIDES:
            resultat.append((racine, forme))
    return resultat


def charger(chemin: Path) -> list[dict]:
    with chemin.open(encoding="utf-8") as fichier:
        return [json.loads(ligne) for ligne in fichier if ligne.strip()]


def proposer(entrees: list[dict], par_passage: int = 6) -> dict[str, list[dict]]:
    """Pour chaque passage : les mots les plus distinctifs, du plus au moins net."""
    comptes: dict[str, Counter] = {}
    formes: dict[str, Counter] = {}
    for entree in entrees:
        compte: Counter = Counter()
        for racine, forme in _mots(entree["question"]):
            compte[racine] += POIDS_QUESTION
            formes.setdefault(racine, Counter())[forme] += 1
        for racine, forme in _mots(entree["reponse"]):
            compte[racine] += 1
            formes.setdefault(racine, Counter())[forme] += 1
        comptes[entree["id"]] = compte

    total = len(entrees)
    presence = Counter(racine for compte in comptes.values() for racine in compte)
    partages = {
        racine: sorted(i for i, c in comptes.items() if racine in c)
        for racine, n in presence.items()
        if n > 1
    }
    seuil = max(2, int(total * PART_MAX_PASSAGES))

    propositions: dict[str, list[dict]] = {}
    for entree in entrees:
        candidats = []
        for racine, poids in comptes[entree["id"]].items():
            if presence[racine] > seuil:
                continue
            # Plus le mot est rare dans la FAQ, plus il vaut.
            score = poids * (total / presence[racine])
            candidats.append(
                {
                    "mot": formes[racine].most_common(1)[0][0],
                    "score": round(score, 1),
                    "dans_la_question": racine in {r for r, _ in _mots(entree["question"])},
                    "partage_avec": [i for i in partages.get(racine, []) if i != entree["id"]],
                }
            )
        candidats.sort(key=lambda c: (-c["score"], c["mot"]))
        propositions[entree["id"]] = candidats[:par_passage]
    return propositions


def _afficher(entrees: list[dict], propositions: dict[str, list[dict]]) -> None:
    for entree in entrees:
        print(f"{entree['id']}  {entree['question']}")
        for c in propositions[entree["id"]]:
            note = f"  (aussi dans {', '.join(c['partage_avec'])})" if c["partage_avec"] else ""
            print(f"    - {c['mot']}{note}")
        print()


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--fichier", type=Path, default=FICHIER_PAR_DEFAUT)
    parseur.add_argument("--par-passage", type=int, default=6)
    parseur.add_argument("--json", action="store_true", help="sortie JSON")
    args = parseur.parse_args(argv)

    entrees = charger(args.fichier)
    propositions = proposer(entrees, args.par_passage)
    if args.json:
        print(json.dumps(propositions, ensure_ascii=False, indent=2))
    else:
        _afficher(entrees, propositions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
