"""Vérifie que les quatre services répondent, et dit pourquoi quand ils ne répondent pas.

    python scripts/diagnostic_connexions.py

Pourquoi ce script existe. Le 2026-10-10, 73 tests d'intégration ont échoué
sur la même ligne illisible :

    UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 97

Sous Windows en français, libpq rend ses messages d'erreur dans la langue du
système, en cp1252. psycopg2 les décode en UTF-8 et s'étrangle sur le premier
caractère accentué — l'octet 0xe9, un « é ». La vraie cause disparaît derrière
le plantage du décodeur. Ici, elle était double : le port publié était 5433 et
non 5432, et un PostgreSQL étranger occupait le 5432, qui répondait
« authentification par mot de passe échouée ».

Ce script attrape `UnicodeDecodeError`, relit les octets bruts en cp1252 et
affiche le message en clair. Il rend aussi 1 si un service manque, pour servir
de contrôle avant de lancer la suite d'intégration.
"""

from __future__ import annotations

import os
import socket
import sys
from urllib.parse import urlsplit

from common.config import load_settings, provenance

# Les octets rendus par libpq quand le système n'est pas en anglais. cp1252
# couvre le français et l'essentiel de l'Europe de l'Ouest ; `replace` garantit
# qu'on affiche quelque chose plutôt que de replanter sur le diagnostic.
ENCODAGE_DE_SECOURS = "cp1252"

# Au-delà, le message est tronqué : il s'agit de nommer la cause, pas de
# recopier une trace.
LONGUEUR_MAXIMALE = 120


def _en_clair(erreur: BaseException) -> str:
    """Le message d'une exception, y compris quand c'est le décodage qui a échoué.

    Première ligne seulement : pymongo joint toute sa description de topologie,
    qui noie le « Connection refused » dans dix lignes de détail.
    """
    if isinstance(erreur, UnicodeDecodeError):
        message = erreur.object.decode(ENCODAGE_DE_SECOURS, errors="replace")
    else:
        message = str(erreur)

    message = message.strip()
    if not message:
        return type(erreur).__name__

    message = message.splitlines()[0].strip()
    # pymongo joint toute sa description de topologie sur une seule ligne :
    # le « Connection refused » utile se noie dans deux cents caractères de
    # détail qui ne servent qu'à lui.
    return message if len(message) <= LONGUEUR_MAXIMALE else message[:LONGUEUR_MAXIMALE] + " […]"


def _port_ouvert(hote: str, port: int, delai: float = 3.0) -> str | None:
    """None si le port accepte une connexion, sinon la raison."""
    try:
        with socket.create_connection((hote, port), timeout=delai):
            return None
    except OSError as erreur:
        return _en_clair(erreur)


def _verifier_postgres(dsn: str) -> str | None:
    import psycopg2

    try:
        psycopg2.connect(dsn, connect_timeout=5).close()
        return None
    except Exception as erreur:  # noqa: BLE001 — tout échec doit être lisible
        return _en_clair(erreur)


def _verifier_mongo(uri: str) -> str | None:
    try:
        from pymongo import MongoClient
    except ImportError:
        return "pymongo n'est pas installé"

    try:
        MongoClient(uri, serverSelectionTimeoutMS=3000).admin.command("ping")
        return None
    except Exception as erreur:  # noqa: BLE001
        return _en_clair(erreur)


def _verifier_elasticsearch(url: str) -> str | None:
    morceaux = urlsplit(url)
    return _port_ouvert(morceaux.hostname or "127.0.0.1", morceaux.port or 9200)


def _verifier_kafka(adresse: str) -> str | None:
    hote, _, port = adresse.rpartition(":")
    return _port_ouvert(hote or "127.0.0.1", int(port or 29092))


def main() -> int:
    """Affiche l'état des quatre services. Rend 1 si l'un d'eux manque."""
    parametres = load_settings()

    controles = (
        (
            "PostgreSQL",
            parametres.postgres_dsn,
            "POSTGRES_DSN",
            "POSTGRES_PORT",
            _verifier_postgres,
        ),
        ("MongoDB", parametres.mongo_uri, "MONGO_URI", "MONGO_PORT", _verifier_mongo),
        ("Elasticsearch", parametres.es_url, "ES_URL", "ES_PORT", _verifier_elasticsearch),
        ("Kafka", parametres.kafka_bootstrap, "KAFKA_BOOTSTRAP", "KAFKA_PORT", _verifier_kafka),
    )

    manquants = []
    forcees = []
    for nom, adresse, variable_complete, variable_port, verifier in controles:
        # Le mot de passe n'a rien à faire dans une sortie qu'on recopie.
        lisible = adresse.split("@")[-1] if "@" in adresse else adresse
        # L'adresse complète prime : si elle est posée, c'est elle qu'on suit,
        # et le port du `.env` n'est même pas lu.
        if os.getenv(variable_complete):
            origine = provenance(variable_complete)
            forcees.append(variable_complete)
        else:
            origine = provenance(variable_port)

        motif = verifier(adresse)
        etat = "OK      " if motif is None else "ABSENT  "
        print(f"  {etat} {nom:<14} {lisible}")
        print(f"           source : {origine}")
        if motif is not None:
            print(f"           -> {motif}")
            manquants.append(nom)

    print()
    if forcees:
        print("Attention : une variable d'environnement écrase le fichier .env —")
        print(f"  {', '.join(forcees)}")
        print("Posée pour un essai, elle survit à toute la session du terminal.")
        print(f"  Pour la retirer :  Remove-Item Env:{forcees[0]}   (PowerShell)")
        print(f"                     unset {forcees[0]}             (bash)")
        print()

    if manquants:
        print(f"{len(manquants)} service(s) injoignable(s) : {', '.join(manquants)}")
        print("Vérifier `docker compose ps` : la colonne PORTS donne le port réellement")
        print("publié, et le `.env` doit porter le même.")
        return 1

    print("Les quatre services répondent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
