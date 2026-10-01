"""Tests de la configuration centralisée.

Premier vrai test du projet : il vérifie un comportement dont tous les
autres modules dépendront.
"""

from pathlib import Path

from common.config import load_settings


def test_valeurs_par_defaut_sans_environnement(monkeypatch):
    for nom in ("POSTGRES_DSN", "MONGO_URI", "ES_URL", "KAFKA_BOOTSTRAP", "DATA_DIR"):
        monkeypatch.delenv(nom, raising=False)

    s = load_settings()

    assert s.es_url == "http://localhost:9200"
    assert s.data_dir == Path("data")


def test_une_variable_d_environnement_l_emporte(monkeypatch):
    monkeypatch.setenv("ES_URL", "http://elasticsearch:9200")

    assert load_settings().es_url == "http://elasticsearch:9200"


def test_les_zones_de_donnees_se_deduisent_du_dossier_racine(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "/app/data")

    s = load_settings()

    assert s.raw_dir == Path("/app/data/raw")
    assert s.quarantine_dir == Path("/app/data/quarantine")


def test_la_configuration_est_figee():
    s = load_settings()
    try:
        s.es_url = "autre"
    except AttributeError:
        return
    raise AssertionError("la configuration ne doit pas être modifiable après lecture")
