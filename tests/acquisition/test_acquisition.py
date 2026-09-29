"""Tests de l'acquisition de la source SQL.

Les tests unitaires n'ont besoin d'aucune base : ils portent sur la
construction des requêtes, la connexion déduite et la comparaison de deux
extractions. Les tests marqués « integration » utilisent une vraie base.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from acquisition.boutique import TABLES, dsn_boutique, requete_extraction
from acquisition.ingestion import (
    acquerir,
    derniere_ingestion,
    empreintes,
    horodatage_ingestion,
    lignes_totales,
    racine_lots,
)

# --- La connexion à la source ------------------------------------------------


def test_la_source_est_une_autre_base_du_meme_serveur(monkeypatch):
    monkeypatch.delenv("BOUTIQUE_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://u:p@postgres:5432/dataflow360")

    assert dsn_boutique() == "postgresql://u:p@postgres:5432/boutique"


def test_une_variable_d_environnement_peut_deplacer_la_source(monkeypatch):
    monkeypatch.setenv("BOUTIQUE_DSN", "postgresql://autre:mdp@ailleurs:5432/boutique")

    assert dsn_boutique() == "postgresql://autre:mdp@ailleurs:5432/boutique"


def test_la_base_de_maintenance_sert_a_creer_la_source(monkeypatch):
    monkeypatch.delenv("BOUTIQUE_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://u:p@postgres:5432/dataflow360")
    from acquisition.boutique import dsn_maintenance

    assert dsn_maintenance().endswith("/postgres")


# --- Les requêtes d'extraction ----------------------------------------------


def test_sans_date_la_table_est_extraite_en_entier():
    assert requete_extraction("customers") == "SELECT * FROM customers"


def test_avec_une_date_seules_les_commandes_recentes_sont_extraites():
    requete = requete_extraction("orders", depuis="2017-01-01")

    assert "WHERE order_purchase_timestamp >= %(depuis)s" in requete
    assert "ORDER BY order_purchase_timestamp" in requete


def test_les_referentiels_ignorent_la_date_faute_de_colonne_de_creation():
    assert requete_extraction("products", depuis="2017-01-01") == "SELECT * FROM products"


def test_une_table_inconnue_est_refusee_et_non_concatenee():
    with pytest.raises(ValueError, match="table inconnue"):
        requete_extraction("customers; DROP TABLE orders")


def test_les_huit_tables_de_la_boutique_sont_declarees():
    assert len(TABLES) == 8
    assert "orders" in TABLES and "geolocation" in TABLES


# --- L'ingestion -------------------------------------------------------------


def test_l_horodatage_suit_le_format_du_contrat_de_zone_brute():
    horodatage = horodatage_ingestion(datetime(2026, 9, 25, 14, 3, 7, tzinfo=UTC))

    assert horodatage == "20260925T140307"


def test_les_ingestions_sont_rangees_dans_la_zone_brute(tmp_path):
    assert racine_lots(tmp_path, "boutique") == tmp_path / "raw" / "lots" / "boutique"


def test_deux_extractions_identiques_ont_les_memes_empreintes():
    manifeste = {"fichiers": [{"nom": "orders.csv", "sha256": "abc"}]}

    assert empreintes(manifeste) == {"orders.csv": "abc"}


def test_le_compte_de_lignes_deduit_les_entetes_csv():
    manifeste = {"fichiers": [{"lignes": 100}, {"lignes": 51}]}

    assert lignes_totales(manifeste) == 149  # 99 + 50


def test_sans_ingestion_precedente_il_n_y_a_rien_a_comparer(tmp_path):
    assert derniere_ingestion(tmp_path) is None


def test_la_derniere_ingestion_est_la_plus_recente(tmp_path):
    for horodatage in ("20260101T000000", "20260925T140307", "20260501T120000"):
        dossier = tmp_path / f"ingestion={horodatage}"
        dossier.mkdir()
        (dossier / "manifeste.json").write_text(json.dumps({"fichiers": []}), encoding="utf-8")

    assert derniere_ingestion(tmp_path).name == "ingestion=20260925T140307"


def test_un_dossier_sans_manifeste_est_ignore(tmp_path):
    (tmp_path / "ingestion=20260925T140307").mkdir()

    assert derniere_ingestion(tmp_path) is None


# --- Avec une vraie base -----------------------------------------------------


@pytest.mark.integration
def test_acquisition_reelle_puis_relance_sans_changement(tmp_path):
    premier = acquerir(racine_donnees=tmp_path)
    assert premier.ingestion is not None, premier.message
    assert premier.fichiers == len(TABLES)

    dossier = racine_lots(tmp_path, "boutique") / f"ingestion={premier.ingestion}"
    assert (dossier / "manifeste.json").exists()
    assert (dossier / "orders.csv").exists()

    second = acquerir(racine_donnees=tmp_path)
    assert second.ingestion is None, "une seconde acquisition ne doit rien créer"


@pytest.mark.integration
def test_le_manifeste_respecte_le_contrat_de_la_zone_brute(tmp_path):
    resultat = acquerir(racine_donnees=tmp_path)
    dossier = racine_lots(tmp_path, "boutique") / f"ingestion={resultat.ingestion}"
    manifeste = json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))

    assert manifeste["source"] == "boutique"
    assert manifeste["ingestion"] == resultat.ingestion
    for entree in manifeste["fichiers"]:
        assert {"nom", "lignes", "octets", "sha256"} <= set(entree)
        assert (dossier / entree["nom"]).stat().st_size == entree["octets"]


@pytest.mark.integration
def test_l_extraction_incrementale_ne_ramene_que_les_commandes_recentes(tmp_path):
    complet = acquerir(racine_donnees=tmp_path / "tout")
    partiel = acquerir(racine_donnees=tmp_path / "depuis", depuis="2018-01-01")

    lignes_completes = _lignes(tmp_path / "tout", complet.ingestion, "orders.csv")
    lignes_partielles = _lignes(tmp_path / "depuis", partiel.ingestion, "orders.csv")

    assert 0 < lignes_partielles < lignes_completes


def _lignes(racine: Path, ingestion: str, nom: str) -> int:
    chemin = racine_lots(racine, "boutique") / f"ingestion={ingestion}" / nom
    return sum(1 for _ in chemin.open(encoding="utf-8")) - 1
