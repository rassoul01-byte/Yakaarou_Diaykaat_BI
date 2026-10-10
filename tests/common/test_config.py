"""Tests de la configuration centralisée.

Premier vrai test du projet : il vérifie un comportement dont tous les
autres modules dépendront.
"""

from pathlib import Path

import pytest

from common import config
from common.config import load_settings

PARAMETRES = (
    "POSTGRES_DSN",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_PORT",
    "MONGO_URI",
    "MONGO_USER",
    "MONGO_PASSWORD",
    "MONGO_DB",
    "MONGO_PORT",
    "ES_URL",
    "ES_PORT",
    "KAFKA_BOOTSTRAP",
    "KAFKA_PORT",
    "DATA_DIR",
)


@pytest.fixture
def sans_fichier_env(monkeypatch):
    """Neutralise le `.env` du poste : un test ne dépend pas de la machine.

    Sans cela, la suite passerait ou échouerait selon le `.env` de chacun —
    le contraire d'un test.
    """
    monkeypatch.setattr(config, "_fichier_env", lambda: {})


@pytest.fixture
def env_vide(monkeypatch, sans_fichier_env):
    for nom in PARAMETRES:
        monkeypatch.delenv(nom, raising=False)


def test_valeurs_par_defaut_sans_environnement(env_vide):
    s = load_settings()

    assert s.es_url == "http://127.0.0.1:9200"
    assert s.data_dir == Path("data")


def test_les_defauts_visent_l_adresse_que_docker_compose_publie(env_vide):
    """`127.0.0.1` et jamais `localhost` : la nuance compte sous Windows.

    docker-compose.yml publie chaque service sur `127.0.0.1:<port>`, en IPv4.
    `localhost` se résout d'abord en `::1` sous Windows, que personne n'écoute.
    """
    s = load_settings()

    for adresse in (s.postgres_dsn, s.mongo_uri, s.es_url, s.kafka_bootstrap):
        assert "localhost" not in adresse
        assert "127.0.0.1" in adresse


def test_une_variable_d_environnement_l_emporte(monkeypatch, sans_fichier_env):
    monkeypatch.setenv("ES_URL", "http://elasticsearch:9200")

    assert load_settings().es_url == "http://elasticsearch:9200"


# --- Le fichier .env --------------------------------------------------------


def test_le_port_du_fichier_env_est_celui_utilise(monkeypatch):
    """Le défaut de ce test : viser 5432 quand le poste publie sur 5433.

    `docker compose` lit le `.env` depuis toujours ; le Python lancé depuis un
    poste ne le lisait pas. Sur un poste où `POSTGRES_PORT=5433`, les tests
    d'intégration tombaient sur le PostgreSQL installé en natif sur le 5432 —
    une base étrangère au projet.
    """
    for nom in PARAMETRES:
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr(config, "_fichier_env", lambda: {"POSTGRES_PORT": "5433"})

    assert "127.0.0.1:5433" in load_settings().postgres_dsn


def test_l_environnement_l_emporte_sur_le_fichier_env(monkeypatch):
    """C'est ainsi que le conteneur garde la main : il définit ses variables."""
    monkeypatch.setattr(config, "_fichier_env", lambda: {"POSTGRES_PORT": "5433"})
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://u:p@postgres:5432/base")

    assert load_settings().postgres_dsn == "postgresql://u:p@postgres:5432/base"


def test_le_fichier_env_fournit_aussi_l_identifiant_et_la_base(monkeypatch):
    for nom in PARAMETRES:
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr(
        config,
        "_fichier_env",
        lambda: {
            "POSTGRES_USER": "lecture",
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_DB": "entrepot",
            "POSTGRES_PORT": "6543",
        },
    )

    assert load_settings().postgres_dsn == "postgresql://lecture:secret@127.0.0.1:6543/entrepot"


def test_un_fichier_env_absent_ne_fait_pas_echouer(monkeypatch, tmp_path):
    """Un poste sans `.env` doit fonctionner sur les valeurs de secours."""
    config._fichier_env.cache_clear()
    monkeypatch.setattr(config, "FICHIER_ENV", tmp_path / "pas_de_env")
    try:
        for nom in PARAMETRES:
            monkeypatch.delenv(nom, raising=False)

        assert "127.0.0.1:5432" in load_settings().postgres_dsn
    finally:
        config._fichier_env.cache_clear()


def test_le_fichier_env_est_lu_depuis_la_racine_du_depot(monkeypatch, tmp_path):
    """La lecture passe par le vrai fichier, pas par une valeur en dur."""
    config._fichier_env.cache_clear()
    fichier = tmp_path / ".env"
    fichier.write_text("POSTGRES_PORT=5544\n", encoding="utf-8")
    monkeypatch.setattr(config, "FICHIER_ENV", fichier)
    try:
        for nom in PARAMETRES:
            monkeypatch.delenv(nom, raising=False)

        assert "127.0.0.1:5544" in load_settings().postgres_dsn
    finally:
        config._fichier_env.cache_clear()


# --- D'où vient la valeur ---------------------------------------------------


def test_la_provenance_nomme_la_variable_d_environnement(monkeypatch, sans_fichier_env):
    """Une variable posée pour un essai survit à toute la session du terminal.

    Elle écrase alors le `.env` sans rien dire, et on cherche la panne du
    mauvais côté pendant une heure. Le diagnostic doit pouvoir la nommer.
    """
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://u:p@127.0.0.1:5432/base")

    assert config.provenance("POSTGRES_DSN") == "variable d'environnement POSTGRES_DSN"


def test_la_provenance_nomme_le_fichier_env(monkeypatch):
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.setattr(config, "_fichier_env", lambda: {"POSTGRES_PORT": "5433"})

    assert config.provenance("POSTGRES_PORT") == "fichier .env (POSTGRES_PORT)"


def test_la_provenance_dit_quand_c_est_la_valeur_de_secours(env_vide):
    assert config.provenance("POSTGRES_PORT") == "valeur par défaut"


# --- Les autres services ----------------------------------------------------


def test_les_quatre_services_suivent_la_meme_regle(monkeypatch):
    for nom in PARAMETRES:
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr(
        config,
        "_fichier_env",
        lambda: {"POSTGRES_PORT": "1", "MONGO_PORT": "2", "ES_PORT": "3", "KAFKA_PORT": "4"},
    )

    s = load_settings()

    assert "127.0.0.1:1" in s.postgres_dsn
    assert "127.0.0.1:2" in s.mongo_uri
    assert s.es_url == "http://127.0.0.1:3"
    assert s.kafka_bootstrap == "127.0.0.1:4"


def test_les_zones_de_donnees_se_deduisent_du_dossier_racine(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "/app/data")

    s = load_settings()

    assert s.raw_dir == Path("/app/data/raw")
    assert s.quarantine_dir == Path("/app/data/quarantine")


def test_la_configuration_est_figee():
    s = load_settings()
    try:
        s.es_url = "autre"
    except Exception:
        return
    raise AssertionError("Settings doit être immuable")
