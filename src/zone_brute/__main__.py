"""Commandes de la zone brute (Livrable 4, Sprint 1).

    docker compose exec app python -m zone_brute lister
    docker compose exec app python -m zone_brute verifier
    docker compose exec app python -m zone_brute archiver
    docker compose exec app python -m zone_brute rejouer --date 2026-09-22 --heure 10

Branchement au bus (common.bus, Livrable 3, Ndeye Penda) :
- archiver consomme navigation.evenements avec consommer(sujet, groupe, ...),
  qui renvoie des MessageRecu (attribut .valeur = le dictionnaire de
  l'événement). Le groupe de consommateur est fixe (GROUPE_ARCHIVAGE) : Kafka
  retient où on s'est arrêté, donc chaque exécution reprend après la
  précédente sans rien relire ni rien manquer.
- rejouer republie via un Publieur dont le sujet principal est
  navigation.rejeu au lieu de navigation.evenements — les événements passent
  donc par la même validation de contrat qu'à la publication normale.
"""
from __future__ import annotations

import argparse
import sys

from . import evenements as ev
from . import lots

GROUPE_ARCHIVAGE = "dataflow360-zone-brute-archivage"


def _commande_lister(args: argparse.Namespace) -> int:
    ingestions = lots.lister_ingestions()
    if not ingestions:
        print("Aucune ingestion trouvée dans data/raw/lots/.")
        return 0
    for ing in ingestions:
        nb_fichiers = len(ing.manifeste.get("fichiers", []))
        print(f"{ing.source:12s} ingestion={ing.horodatage}  ({nb_fichiers} fichier(s))")
    return 0


def _commande_verifier(args: argparse.Namespace) -> int:
    anomalies = lots.verifier_ingestions()
    if not anomalies:
        print("Aucune altération détectée.")
        return 0
    for a in anomalies:
        trouve = a.trouve or "FICHIER MANQUANT"
        print(
            f"ALTÉRATION  source={a.ingestion.source} ingestion={a.ingestion.horodatage} "
            f"fichier={a.fichier} attendu={a.attendu} trouvé={trouve}"
        )
    return 1


def _commande_archiver(args: argparse.Namespace) -> int:
    try:
        from common.bus import consommer  # Livrable 3, Ndeye Penda
    except ImportError:
        print(
            "Impossible d'importer common.bus.consommer — vérifier que le "
            "Livrable 3 est bien intégré et que confluent_kafka est installé.",
            file=sys.stderr,
        )
        raise

    evenements_recus = [
        message.valeur
        for message in consommer(
            ev.SUJET_SOURCE,
            GROUPE_ARCHIVAGE,
            arret_apres_inactivite=args.inactivite,
        )
        if isinstance(message.valeur, dict)
    ]
    chemins = ev.archiver_evenements(evenements_recus)
    print(f"{len(evenements_recus)} événement(s) archivé(s) dans {len(chemins)} tranche(s).")
    return 0


def _commande_rejouer(args: argparse.Namespace) -> int:
    try:
        from common.bus import Publieur  # Livrable 3, Ndeye Penda
    except ImportError:
        print(
            "Impossible d'importer common.bus.Publieur — vérifier que le "
            "Livrable 3 est bien intégré et que confluent_kafka est installé.",
            file=sys.stderr,
        )
        raise

    # sujet_principal=navigation.rejeu : les événements rejoués repassent par
    # la validation du contrat, mais partent sur un sujet à part pour ne pas
    # être comptés deux fois par les consommateurs du flux normal.
    with Publieur(sujet_principal=ev.SUJET_REJEU) as publieur:
        compte = ev.rejouer_tranche(
            args.date,
            args.heure,
            lambda _sujet, _cle, evenement: publieur.publier(evenement),
        )
    print(f"{compte} événement(s) républié(s) sur {ev.SUJET_REJEU}.")
    return 0


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(prog="zone_brute")
    sous = analyseur.add_subparsers(dest="commande", required=True)

    sous.add_parser(
        "lister", help="Lister les ingestions par lots de la zone brute."
    ).set_defaults(func=_commande_lister)

    sous.add_parser(
        "verifier", help="Vérifier l'intégrité des ingestions par lots."
    ).set_defaults(func=_commande_verifier)

    p_archiver = sous.add_parser(
        "archiver", help="Archiver les événements du bus par tranche horaire."
    )
    p_archiver.add_argument(
        "--inactivite", type=float, default=5.0,
        help="Arrêt après ce nombre de secondes sans nouveau message (défaut : 5).",
    )
    p_archiver.set_defaults(func=_commande_archiver)

    p_rejouer = sous.add_parser(
        "rejouer", help="Republier une tranche archivée sur navigation.rejeu."
    )
    p_rejouer.add_argument("--date", required=True, help="AAAA-MM-JJ")
    p_rejouer.add_argument("--heure", required=True, help="HH")
    p_rejouer.set_defaults(func=_commande_rejouer)

    return analyseur


def main(argv=None) -> int:
    analyseur = construire_analyseur()
    args = analyseur.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
