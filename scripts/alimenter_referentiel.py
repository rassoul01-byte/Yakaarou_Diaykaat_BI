"""Alimente le service référentiel depuis les services publics.

À lancer une fois, en ligne. Les réponses sont conservées dans la zone brute :
ensuite, la plateforme n'a plus besoin d'Internet, y compris le jour de la
démonstration.

Usage :
    docker compose exec app python scripts/alimenter_referentiel.py
    docker compose exec app python scripts/alimenter_referentiel.py --annees 2016 2017 2018
    docker compose exec app python scripts/alimenter_referentiel.py --forcer

Code de sortie : 0 si tout est conservé, 1 si un service public n'a pas répondu.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx  # noqa: E402

from referentiel.depot import chemin_feries, chemin_taux, ecrire  # noqa: E402
from referentiel.sources import recuperer_feries, recuperer_taux  # noqa: E402

# L'historique Olist couvre septembre 2016 à octobre 2018.
ANNEES_PAR_DEFAUT = (2016, 2017, 2018)
DEBUT_TAUX = date(2016, 9, 1)
FIN_TAUX = date(2018, 10, 31)
DEVISE_PAR_DEFAUT = "EUR"


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Alimente le service référentiel.")
    analyseur.add_argument(
        "--annees", type=int, nargs="+", default=list(ANNEES_PAR_DEFAUT), help="années des fériés"
    )
    analyseur.add_argument("--devise", default=DEVISE_PAR_DEFAUT, help="devise d'arrivée")
    analyseur.add_argument(
        "--forcer", action="store_true", help="récupérer même si c'est déjà conservé"
    )
    analyseur.add_argument("--racine", type=Path, help="racine de la zone brute")
    arguments = analyseur.parse_args(argv)

    try:
        for annee in arguments.annees:
            destination = chemin_feries(annee, arguments.racine)
            if destination.exists() and not arguments.forcer:
                print(f"  fériés {annee:<6} déjà conservés")
                continue
            feries = recuperer_feries(annee)
            ecrire(destination, feries)
            print(f"  fériés {annee:<6} {len(feries)} jours conservés")

        destination = chemin_taux(DEBUT_TAUX, FIN_TAUX, arguments.devise, arguments.racine)
        if destination.exists() and not arguments.forcer:
            print(f"  taux BRL→{arguments.devise}  déjà conservés")
        else:
            reponse = recuperer_taux(DEBUT_TAUX, FIN_TAUX, arguments.devise)
            ecrire(destination, reponse)
            print(f"  taux BRL→{arguments.devise}  {len(reponse['rates'])} jours conservés")

    except (httpx.HTTPError, ValueError) as erreur:
        print(f"ERREUR : un service public n'a pas répondu ({erreur})", file=sys.stderr)
        print("Les données déjà conservées restent utilisables.", file=sys.stderr)
        return 1

    print("\nRéférentiel à jour. Service : docker compose up -d referentiel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
