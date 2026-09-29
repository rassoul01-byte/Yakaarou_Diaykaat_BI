"""Tests du script de récupération des données.

Aucun test n'accède au réseau : le téléchargement depuis le Drive est remplacé
par une copie de fichiers construits localement. Ce qui est vérifié, c'est tout
ce qui l'entoure — extraction, rangement, vérification, décision de télécharger.
"""

import importlib.util
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "download_data", RACINE / "scripts" / "download_data.py"
)
dd = importlib.util.module_from_spec(_spec)
sys.modules["download_data"] = dd  # requis pour que les dataclass du script se résolvent
_spec.loader.exec_module(dd)

# Petite référence de test : deux fichiers Olist et le catalogue, de quelques lignes.
REFERENCE_TEST = [
    dd.FichierAttendu("olist", "olist_orders_dataset.csv", 3, 2),
    dd.FichierAttendu("olist", "olist_sellers_dataset.csv", 2, 2),
    dd.FichierAttendu("rakuten", "rakuten_catalogue_produits.csv", 4, 3),
]


def _ecrire_csv(chemin: Path, lignes: int, colonnes: int) -> None:
    pd.DataFrame({f"c{i}": range(lignes) for i in range(colonnes)}).to_csv(chemin, index=False)


def _faux_drive(dossier: Path) -> dict[str, Path]:
    """Construit localement les deux fichiers que le Drive servirait."""
    dossier.mkdir(parents=True, exist_ok=True)
    orders, sellers = dossier / "orders.csv", dossier / "sellers.csv"
    _ecrire_csv(orders, 3, 2)
    _ecrire_csv(sellers, 2, 2)
    archive = dossier / "Dataset-Olist.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        # Le vrai zip range ses fichiers dans un sous-dossier : on reproduit ce cas.
        zf.write(orders, "Dataset-Olist/olist_orders_dataset.csv")
        zf.write(sellers, "Dataset-Olist/olist_sellers_dataset.csv")
        zf.writestr("__MACOSX/._olist_orders_dataset.csv", "parasite")
        zf.writestr("Dataset-Olist/LISEZMOI.txt", "non csv")
    catalogue = dossier / "rakuten_catalogue_produits.csv"
    _ecrire_csv(catalogue, 4, 3)
    return {"olist": archive, "rakuten": catalogue}


@pytest.fixture
def environnement(tmp_path, monkeypatch):
    """Zone de données isolée, référence réduite, téléchargement simulé."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setattr(dd, "REFERENCE", REFERENCE_TEST)

    faux = _faux_drive(tmp_path / "drive")
    par_id = {dd.DRIVE_IDS_PAR_DEFAUT[s]: f for s, f in faux.items()}
    appels = []

    def faux_telecharger(identifiant, destination):
        appels.append(identifiant)
        destination.write_bytes(par_id[identifiant].read_bytes())

    monkeypatch.setattr(dd, "telecharger", faux_telecharger)
    return data_dir, appels


def test_extraction_retrouve_les_csv_dans_un_sous_dossier(tmp_path):
    faux = _faux_drive(tmp_path / "drive")
    sortie = tmp_path / "sortie"
    sortie.mkdir()

    extraits = dd.extraire_csv(faux["olist"], sortie)

    assert sorted(extraits) == ["olist_orders_dataset.csv", "olist_sellers_dataset.csv"]
    assert not (sortie / "LISEZMOI.txt").exists()


def test_poste_vierge_tout_est_telecharge_range_et_verifie(environnement):
    data_dir, appels = environnement

    assert dd.main([]) == 0
    assert len(appels) == 2
    assert (data_dir / "sources" / "olist" / "olist_orders_dataset.csv").exists()
    assert (data_dir / "sources" / "rakuten" / "rakuten_catalogue_produits.csv").exists()
    assert (data_dir / "quarantine").is_dir() and (data_dir / "models").is_dir()


def test_second_lancement_ne_retelecharge_rien(environnement):
    _, appels = environnement
    dd.main([])
    appels.clear()

    assert dd.main([]) == 0
    assert appels == []


def test_seule_la_source_defaillante_est_retelechargee(environnement):
    data_dir, appels = environnement
    dd.main([])
    appels.clear()
    (data_dir / "sources" / "rakuten" / "rakuten_catalogue_produits.csv").unlink()

    assert dd.main([]) == 0
    assert appels == [dd.DRIVE_IDS_PAR_DEFAUT["rakuten"]]


def test_un_fichier_tronque_est_detecte(environnement):
    data_dir, _ = environnement
    dd.main([])
    _ecrire_csv(data_dir / "sources" / "olist" / "olist_orders_dataset.csv", 1, 2)

    assert dd.main(["--verifier"]) == 1


def test_le_mode_verification_ne_telecharge_jamais(environnement):
    _, appels = environnement

    assert dd.main(["--verifier"]) == 1
    assert appels == []


def test_la_reference_couvre_les_dix_fichiers_sources():
    assert len(dd.REFERENCE) == 10
    assert sum(f.source == "olist" for f in dd.REFERENCE) == 9
