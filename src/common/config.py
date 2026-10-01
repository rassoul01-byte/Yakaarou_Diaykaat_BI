"""Lecture centralisée de la configuration.

Tous les modules lisent leurs paramètres ici, et jamais directement dans
os.environ. Les noms des variables sont ceux déclarés dans docker-compose.yml :
un paramètre ne doit exister qu'à un seul endroit.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Valeurs par défaut valables sur un poste de développement, hors conteneur.
# Elles reprennent celles de .env.example et ne contiennent aucun vrai secret.
_DEFAUTS = {
    "POSTGRES_DSN": "postgresql://dataflow:changeme_en_local@localhost:5432/dataflow360",
    "MONGO_URI": "mongodb://dataflow:changeme_en_local@localhost:27017/catalogue?authSource=admin",
    "ES_URL": "http://localhost:9200",
    "KAFKA_BOOTSTRAP": "localhost:29092",
    "DATA_DIR": "data",
}


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


def _lire(nom: str) -> str:
    return os.getenv(nom) or _DEFAUTS[nom]


def load_settings() -> Settings:
    """Construit la configuration à partir de l'environnement.

    Une variable d'environnement définie l'emporte toujours sur la valeur
    par défaut : c'est ce qui permet au même code de tourner sur un poste
    et dans un conteneur sans modification.
    """
    return Settings(
        postgres_dsn=_lire("POSTGRES_DSN"),
        mongo_uri=_lire("MONGO_URI"),
        es_url=_lire("ES_URL"),
        kafka_bootstrap=_lire("KAFKA_BOOTSTRAP"),
        data_dir=Path(_lire("DATA_DIR")),
    )
