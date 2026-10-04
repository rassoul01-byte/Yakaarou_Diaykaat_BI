"""Journal des exécutions de la plateforme.

Qu'est-ce qui a tourné, combien de temps, sur quel volume, et qu'est-ce qui a
échoué. C'est la vue d'exploitation : elle ne dit rien des ventes, seulement de
la santé de la chaîne.

Usage :
    docker compose exec app python -m supervision
    docker compose exec app python -m supervision --limite 30
    docker compose exec app python -m supervision --echecs-seulement

Code de sortie : 0 si rien d'anormal, 1 si une anomalie est signalée. C'est ce
code qu'une tâche de surveillance peut lire.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2

from .journal import anomalies, collecter


def _duree(valeur) -> str:
    if valeur is None:
        return "—"
    secondes = float(valeur)
    if secondes < 60:
        return f"{secondes:.1f} s"
    return f"{int(secondes) // 60} min {int(secondes) % 60:02d} s"


def _volume(valeur) -> str:
    return "—" if valeur is None else f"{int(valeur):,}".replace(",", " ")


def afficher(donnees: dict, signalements: list[str]) -> None:
    print("\nDernière exécution de chaque étape\n")
    if not donnees["dernieres"]:
        print("  Aucune exécution enregistrée.")
        print("  Lancer d'abord un traitement : python -m acquisition\n")
        return

    print(f"  {'Pipeline':<16}{'Étape':<22}{'Source':<12}{'Durée':>10}{'Lues':>12}  Statut")
    for ligne in donnees["dernieres"]:
        marque = " " if ligne["statut"] == "succes" else "!"
        print(
            f" {marque}{ligne['pipeline']:<16}{ligne['etape'][:21]:<22}"
            f"{(ligne['source'] or '—')[:11]:<12}{_duree(ligne['duree_secondes']):>10}"
            f"{_volume(ligne['lignes_lues']):>12}  {ligne['statut']}"
        )

    print("\nÉtapes les plus longues\n")
    print(f"  {'Étape':<28}{'Exéc.':>7}{'Échecs':>8}{'Moyenne':>12}{'Maximum':>12}")
    for ligne in donnees["profil"][:10]:
        nom = f"{ligne['pipeline']}/{ligne['etape']}"
        print(
            f"  {nom[:27]:<28}{ligne['executions']:>7}{ligne['echecs']:>8}"
            f"{_duree(ligne['duree_moyenne_secondes']):>12}"
            f"{_duree(ligne['duree_maximale_secondes']):>12}"
        )

    print("\nVolume traité par jour\n")
    print(f"  {'Jour':<13}{'Pipeline':<16}{'Exéc.':>7}{'Lues':>14}{'Rejetées':>11}{'Durée':>12}")
    for ligne in donnees["volume"][:12]:
        print(
            f"  {ligne['jour']:<13}{ligne['pipeline']:<16}{ligne['executions']:>7}"
            f"{_volume(ligne['lignes_lues']):>14}{_volume(ligne['lignes_rejetees']):>11}"
            f"{_duree(ligne['duree_totale_secondes']):>12}"
        )

    if donnees["echecs"]:
        print("\nÉchecs récents\n")
        for ligne in donnees["echecs"][:10]:
            message = (ligne["message"] or "").strip().splitlines()
            premiere = message[0][:70] if message else "(sans message)"
            print(f"  {ligne['demarre_a']:%Y-%m-%d %H:%M}  {ligne['pipeline']}/{ligne['etape']}")
            print(f"      {premiere}")

    print("\nCe qui mérite d'être regardé\n")
    if not signalements:
        print("  Rien à signaler.")
    for signalement in signalements:
        print(f"  ! {signalement}")
    print()


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Journal des exécutions.")
    analyseur.add_argument("--limite", type=int, default=20, help="lignes par section")
    analyseur.add_argument("--jours", type=int, default=7, help="jours de volume affichés")
    analyseur.add_argument(
        "--echecs-seulement", action="store_true", help="n'afficher que les anomalies"
    )
    arguments = analyseur.parse_args(argv)

    try:
        donnees = collecter(arguments.limite, arguments.jours)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire le journal ({premiere})", file=sys.stderr)
        print("Vérifier que les migrations sont appliquées.", file=sys.stderr)
        return 1

    signalements = anomalies(donnees)

    if arguments.echecs_seulement:
        print()
        for signalement in signalements or ["Rien à signaler."]:
            print(f"  {signalement}")
        print()
    else:
        afficher(donnees, signalements)

    return 1 if signalements else 0


if __name__ == "__main__":
    sys.exit(main())
