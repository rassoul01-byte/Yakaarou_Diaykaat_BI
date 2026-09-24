"""Point d'entrée : python -m generateur --debit 20 --duree 300 --graine 42"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from itertools import islice

from .donnees import charger_clients, charger_produits
from .simulateur import (
    PROPORTIONS_DEFAUT,
    Generateur,
    Parametres,
    Statistiques,
)


def _proportions(texte: str) -> dict[str, float]:
    """'page_vue=0.5,recherche=0.3' -> {'page_vue': 0.5, 'recherche': 0.3}"""
    resultat = {}
    for morceau in texte.split(","):
        nom, _, valeur = morceau.partition("=")
        resultat[nom.strip()] = float(valeur)
    return resultat


def _date(texte: str) -> datetime:
    d = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="generateur", description="Générateur d'événements de navigation")
    p.add_argument("--debit", type=float, default=20.0, help="événements par seconde RÉELLE (défaut 20)")
    p.add_argument("--duree", type=float, default=300.0, help="durée réelle en secondes (défaut 300)")
    p.add_argument("--graine", type=int, default=None, help="graine aléatoire ; tirée au sort et affichée si absente")
    p.add_argument("--taux-defauts", type=float, default=0.05, help="part des événements défectueux (défaut 0.05)")
    p.add_argument(
        "--proportions",
        type=_proportions,
        default=dict(PROPORTIONS_DEFAUT),
        help="ex. page_vue=0.5,recherche=0.3,ajout_panier=0.15,achat=0.05",
    )
    p.add_argument("--evenements-par-jour", type=int, default=30_000, help="rythme SIMULÉ (dossier : 10 000 à 50 000)")
    p.add_argument("--debut", type=_date, default=Parametres().debut, help="début de la simulation, ISO 8601 (passé)")
    p.add_argument("--catalogue", default=os.environ.get("CATALOGUE_RAKUTEN", "data/rakuten_catalogue_produits.csv"))
    p.add_argument("--clients", default=os.environ.get("CLIENTS_OLIST", "data/Dataset-Olist/olist_customers_dataset.csv"))
    p.add_argument("--sans-pause", action="store_true", help="publie aussi vite que possible, sans respecter le débit")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    a = analyser_arguments(argv)
    graine = a.graine if a.graine is not None else secrets.randbits(32)
    total = round(a.debit * a.duree)

    parametres = Parametres(
        graine=graine,
        debut=a.debut,
        evenements_par_jour=a.evenements_par_jour,
        proportions=a.proportions,
        taux_defauts=a.taux_defauts,
    )
    fin_simulee = parametres.debut + timedelta(seconds=total * 86_400 / a.evenements_par_jour)
    if fin_simulee > datetime.now(timezone.utc) - timedelta(minutes=5):
        print("Erreur : la simulation dépasserait l'heure réelle ; choisissez un --debut plus ancien.", file=sys.stderr)
        return 2

    generateur = Generateur(charger_produits(a.catalogue), charger_clients(a.clients), parametres)
    print(f"graine={graine} événements={total} du {parametres.debut:%Y-%m-%d} au {fin_simulee:%Y-%m-%d %H:%M}")

    from common.bus import Publieur  # import tardif : les tests n'ont pas besoin de Kafka

    stats = Statistiques()
    depart = time.monotonic()
    with Publieur() as publieur:
        for i, evt in enumerate(islice(generateur.evenements(), total)):
            if not a.sans_pause:
                reste = depart + i / a.debit - time.monotonic()
                if reste > 0:
                    time.sleep(reste)
            stats.enregistrer(evt, publieur.publier(evt.contenu))

    print(f"publiés={stats.total} acceptés={stats.acceptes} rebutés={stats.rebutes}")
    print(f"par type : {dict(stats.par_type)}")
    print(f"défauts injectés : {dict(stats.par_defaut)}")
    if not stats.coherent:
        print(
            f"INCOHÉRENCE : {stats.rebutes_a_tort} événement(s) valide(s) rebuté(s), "
            f"{stats.acceptes_a_tort} événement(s) invalide(s) accepté(s).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
