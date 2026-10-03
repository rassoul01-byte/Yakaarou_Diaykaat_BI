"""Rapport des indicateurs de ventes.

Les mêmes chiffres que le tableau de bord, consultables sans Power BI — et
c'est ainsi qu'on les recoupe : si les deux diffèrent, c'est que quelqu'un a
recalculé une formule au lieu de lire la vue.

Usage :
    docker compose exec app python -m indicateurs
    docker compose exec app python -m indicateurs --periode mois --top 10
    docker compose exec app python -m indicateurs --periode jour --limite 30

Code de sortie : 0 si les indicateurs sont lisibles, 1 sinon.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2

from .lecture import PERIODES, collecter


def _montant(valeur) -> str:
    return "—" if valeur is None else f"{float(valeur):>14,.2f}".replace(",", " ")


def afficher(donnees: dict) -> None:
    totaux = donnees["totaux"]
    print("\nVentes — ensemble de la période\n")
    if not totaux or totaux.get("chiffre_affaires") is None:
        print("  Aucune vente dans l'entrepôt.")
        print("  Lancer d'abord : python -m integration.chargement\n")
        return

    print(f"  Chiffre d'affaires {_montant(totaux['chiffre_affaires'])}")
    print(f"  Commandes          {totaux['commandes']:>14}")
    print(f"  Articles           {totaux['articles']:>14}")
    print(f"  Panier moyen       {_montant(totaux['panier_moyen'])}")
    print(f"  Du {totaux['premier_jour']} au {totaux['dernier_jour']}")

    print(f"\nVentes par {donnees['periode']}\n")
    print(f"  {'Période':<12}{'Chiffre d affaires':>20}{'Commandes':>12}{'Panier moyen':>16}")
    for ligne in donnees["series"]:
        print(
            f"  {ligne['periode']:<12}{_montant(ligne['chiffre_affaires']):>20}"
            f"{ligne['commandes']:>12}{_montant(ligne['panier_moyen']):>16}"
        )

    print("\nCatégories les plus vendues\n")
    print(f"  {'Catégorie':<34}{'Chiffre d affaires':>20}{'Articles':>10}")
    for ligne in donnees["categories"]:
        print(
            f"  {ligne['categorie'][:33]:<34}{_montant(ligne['chiffre_affaires']):>20}"
            f"{ligne['articles']:>10}"
        )

    print("\nProduits les plus vendus\n")
    print(f"  {'Produit':<34}{'Catégorie':<24}{'Chiffre d affaires':>20}")
    for ligne in donnees["produits"]:
        rattache = "" if ligne["rattache"] else "  (non rattaché)"
        print(
            f"  {ligne['id_produit_olist'][:33]:<34}"
            f"{(ligne['categorie'] or 'inconnu')[:23]:<24}"
            f"{_montant(ligne['chiffre_affaires']):>20}{rattache}"
        )
    print()


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Indicateurs de ventes.")
    analyseur.add_argument("--periode", choices=PERIODES, default="mois")
    analyseur.add_argument("--limite", type=int, default=12, help="périodes affichées")
    analyseur.add_argument("--top", type=int, default=10, help="produits et catégories affichés")
    arguments = analyseur.parse_args(argv)

    try:
        donnees = collecter(arguments.periode, arguments.limite, arguments.top)
    except psycopg2.Error as erreur:
        premiere = str(erreur).strip().splitlines()[0]
        print(f"ERREUR : impossible de lire les indicateurs ({premiere})", file=sys.stderr)
        print("Vérifier que les migrations sont appliquées et l'entrepôt chargé.", file=sys.stderr)
        return 1

    afficher(donnees)
    return 0


if __name__ == "__main__":
    sys.exit(main())
