"""Cherche dans le catalogue produits.

Usage :
    docker compose exec app python -m recherche.chercher "chaise de bureu"
    docker compose exec app python -m recherche.chercher "lampe" --categorie 2060
    docker compose exec app python -m recherche.chercher "lampe" --langue fr --taille 5

Options de réglage (pour comparer les réglages et justifier le choix final) :
    --tolerance 0|1|2|AUTO     fautes tolérées par mot
    --prefixe N                premières lettres qui doivent être exactes
    --operateur and|or         tous les mots, ou un seul

Code de sortie : 0 si la recherche aboutit (au moins une fiche trouvée),
1 sinon — erreur d'Elasticsearch, requête invalide ou aucun résultat. Le
message dit lequel des trois.

⚠️ Aucun filtre de prix : le catalogue n'en contient pas (docs/contrats/recherche.md).
"""

from __future__ import annotations

import argparse
import sys

from elasticsearch.exceptions import ApiError, TransportError

from .client import adresse, connexion
from .moteur import (
    OPERATEUR,
    PREFIXE_EXACT,
    SEUIL_REPONSE_MS,
    TAILLE_PAR_DEFAUT,
    TOLERANCE,
    Reponse,
    rechercher,
)

MESSAGE_PRIX = (
    "Le catalogue ne contient aucun prix : le filtre par prix n'est pas pris en charge.\n"
    "Filtres disponibles : --categorie et --langue (voir docs/contrats/recherche.md)."
)


def afficher(reponse: Reponse) -> None:
    print(
        f"\nRecherche : « {reponse.texte} » — {reponse.total} fiche(s), "
        f"{reponse.temps_serveur_ms} ms côté serveur, {reponse.temps_total_ms:.0f} ms au total\n"
    )
    for rang, r in enumerate(reponse.resultats, start=1):
        print(
            f"  {rang:>2}. {r.product_id:<12} {r.designation[:60]:<60} "
            f"[{r.categorie_code or '-'}]  score {r.score:.1f}"
        )
    if reponse.total > len(reponse.resultats):
        print(f"\n  … {reponse.total - len(reponse.resultats)} autre(s) fiche(s) non affichée(s).")


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Recherche dans le catalogue produits.")
    analyseur.add_argument("texte", help="ce que l'acheteur a tapé")
    analyseur.add_argument("--categorie", help="code de catégorie (prdtypecode)")
    analyseur.add_argument("--langue", help="langue de la fiche, par exemple fr")
    analyseur.add_argument("--taille", type=int, default=TAILLE_PAR_DEFAUT)
    analyseur.add_argument("--tolerance", default=TOLERANCE)
    analyseur.add_argument("--prefixe", type=int, default=PREFIXE_EXACT)
    analyseur.add_argument("--operateur", choices=("and", "or"), default=OPERATEUR)
    # Reconnus pour pouvoir répondre clairement, absents de l'aide.
    analyseur.add_argument("--prix-min", type=float, help=argparse.SUPPRESS)
    analyseur.add_argument("--prix-max", type=float, help=argparse.SUPPRESS)
    arguments = analyseur.parse_args(argv)

    if arguments.prix_min is not None or arguments.prix_max is not None:
        print(f"ERREUR : {MESSAGE_PRIX}", file=sys.stderr)
        return 1

    try:
        reponse = rechercher(
            connexion(),
            arguments.texte,
            categorie=arguments.categorie,
            langue=arguments.langue,
            taille=arguments.taille,
            tolerance=arguments.tolerance,
            prefixe_exact=arguments.prefixe,
            operateur=arguments.operateur,
        )
    except ValueError as erreur:
        print(f"ERREUR : requête invalide ({erreur})", file=sys.stderr)
        return 1
    except (ApiError, TransportError) as erreur:
        print(
            f"ERREUR : Elasticsearch n'a pas répondu ({erreur.__class__.__name__})",
            file=sys.stderr,
        )
        print(f"Vérifier que le service tourne : {adresse()}", file=sys.stderr)
        return 1

    afficher(reponse)

    if reponse.temps_total_ms > SEUIL_REPONSE_MS:
        print(f"\nAttention : réponse au-dessus de la seconde ({reponse.temps_total_ms:.0f} ms).")

    if not reponse.aboutit:
        print("\nAucune fiche ne correspond à cette recherche.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
