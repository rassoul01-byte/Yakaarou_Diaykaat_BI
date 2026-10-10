"""Lecture centralisée de la configuration.

Tous les modules lisent leurs paramètres ici, et jamais directement dans
os.environ. Les noms des variables sont ceux déclarés dans docker-compose.yml :
un paramètre ne doit exister qu'à un seul endroit.

Trois sources, dans cet ordre de priorité :

  1. une variable d'environnement définie — c'est ainsi que les conteneurs
     reçoivent leurs adresses, et elle l'emporte toujours ;
  2. le fichier `.env` du dépôt, celui que lit déjà `docker compose` ;
  3. les valeurs de secours ci-dessous, celles de `.env.example`.

Pourquoi le `.env` a été ajouté ici. `docker compose` le lit depuis toujours,
mais le Python lancé depuis un poste ne le lisait pas : les tests d'intégration
visaient donc le port 5432 en dur, quel que soit le `POSTGRES_PORT` du
développeur. Sur un poste où `POSTGRES_PORT=5433`, ils tombaient sur un
PostgreSQL **étranger** installé sur le 5432, qui refusait l'authentification.
Le danger n'était pas l'échec : si le mot de passe avait concordé, la suite
aurait tourné contre la mauvaise base sans que rien ne le signale.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values

RACINE_PROJET = Path(__file__).resolve().parents[2]
FICHIER_ENV = RACINE_PROJET / ".env"

# Valeurs de secours, quand ni l'environnement ni le `.env` ne renseignent.
# Elles reprennent celles de .env.example et ne contiennent aucun vrai secret.
_DEFAUTS = {
    "POSTGRES_USER": "dataflow",
    "POSTGRES_PASSWORD": "changeme_en_local",
    "POSTGRES_DB": "dataflow360",
    "POSTGRES_PORT": "5432",
    "MONGO_USER": "dataflow",
    "MONGO_PASSWORD": "changeme_en_local",
    "MONGO_DB": "catalogue",
    "MONGO_PORT": "27017",
    "ES_PORT": "9200",
    "KAFKA_PORT": "29092",
    "DATA_DIR": "data",
}

# `127.0.0.1` et non `localhost` : docker-compose.yml publie chaque service sur
# `127.0.0.1:<port>`, en IPv4 seulement. Les deux adresses sont équivalentes
# sous Linux, mais sous Windows `localhost` se résout d'abord en `::1`, que
# personne n'écoute. Autant viser l'adresse effectivement publiée.
HOTE_LOCAL = "127.0.0.1"


@dataclass(frozen=True)
class Settings:
    """Paramètres de connexion et chemins, figés une fois lus."""

    postgres_dsn: str
    mongo_uri: str
    es_url: str
    kafka_bootstrap: str
    data_dir: Path

    @property
    def raw_dir(self) -> Path:
        """Zone brute : donnée telle que reçue, jamais modifiée."""
        return self.data_dir / "raw"

    @property
    def quarantine_dir(self) -> Path:
        """Enregistrements rejetés par le contrôle qualité."""
        return self.data_dir / "quarantine"


@lru_cache(maxsize=1)
def _fichier_env() -> dict[str, str]:
    """Le `.env` du dépôt, lu une fois. Absent ou illisible : dictionnaire vide.

    `dotenv_values` ne touche pas à `os.environ` : la lecture reste sans effet
    de bord, et l'environnement garde la priorité.
    """
    if not FICHIER_ENV.is_file():
        return {}
    try:
        return {nom: valeur for nom, valeur in dotenv_values(FICHIER_ENV).items() if valeur}
    except OSError:
        return {}


def _lire(nom: str) -> str:
    """La valeur du paramètre : environnement, puis `.env`, puis secours."""
    return os.getenv(nom) or _fichier_env().get(nom) or _DEFAUTS[nom]


def provenance(nom: str) -> str:
    """D'où vient la valeur de ce paramètre : pour le dire, pas pour décider.

    Une variable d'environnement l'emporte sur le `.env`, et c'est voulu —
    c'est ainsi que les conteneurs imposent leurs adresses. Mais une variable
    posée à la main pour un essai survit à toute la session du terminal, et
    continue d'écraser le `.env` longtemps après qu'on l'a oubliée. Un
    diagnostic qui affiche une adresse sans dire d'où elle sort laisse
    chercher ailleurs.
    """
    if os.getenv(nom):
        return f"variable d'environnement {nom}"
    if _fichier_env().get(nom):
        return f"fichier .env ({nom})"
    return "valeur par défaut"


def _dsn_postgres() -> str:
    """L'adresse PostgreSQL, composée comme docker-compose.yml la compose.

    `POSTGRES_DSN` défini l'emporte : c'est ce que reçoivent les conteneurs,
    où l'hôte est `postgres` et le port toujours 5432. Sinon on la reconstruit
    pour un poste, avec le port réellement publié sur la machine.
    """
    complet = os.getenv("POSTGRES_DSN") or _fichier_env().get("POSTGRES_DSN")
    if complet:
        return complet
    return (
        f"postgresql://{_lire('POSTGRES_USER')}:{_lire('POSTGRES_PASSWORD')}"
        f"@{HOTE_LOCAL}:{_lire('POSTGRES_PORT')}/{_lire('POSTGRES_DB')}"
    )


def _uri_mongo() -> str:
    """Même règle pour MongoDB. `authSource=admin` : le compte vit dans `admin`."""
    complet = os.getenv("MONGO_URI") or _fichier_env().get("MONGO_URI")
    if complet:
        return complet
    return (
        f"mongodb://{_lire('MONGO_USER')}:{_lire('MONGO_PASSWORD')}"
        f"@{HOTE_LOCAL}:{_lire('MONGO_PORT')}/{_lire('MONGO_DB')}?authSource=admin"
    )


def _url_elasticsearch() -> str:
    complet = os.getenv("ES_URL") or _fichier_env().get("ES_URL")
    return complet or f"http://{HOTE_LOCAL}:{_lire('ES_PORT')}"


def _adresse_kafka() -> str:
    complet = os.getenv("KAFKA_BOOTSTRAP") or _fichier_env().get("KAFKA_BOOTSTRAP")
    return complet or f"{HOTE_LOCAL}:{_lire('KAFKA_PORT')}"


def load_settings() -> Settings:
    """Construit la configuration à partir de l'environnement, puis du `.env`.

    Une variable d'environnement définie l'emporte toujours : c'est ce qui
    permet au même code de tourner sur un poste et dans un conteneur sans
    modification.
    """
    return Settings(
        postgres_dsn=_dsn_postgres(),
        mongo_uri=_uri_mongo(),
        es_url=_url_elasticsearch(),
        kafka_bootstrap=_adresse_kafka(),
        data_dir=Path(_lire("DATA_DIR")),
    )
