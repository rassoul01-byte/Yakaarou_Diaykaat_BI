from pathlib import Path

from zone_brute.lots import lister_ingestions, verifier_ingestions
from zone_brute.manifeste import construire_manifeste, ecrire_manifeste


def _creer_ingestion(racine: Path, source: str, horodatage: str, contenu: str = "id\n1\n2\n"):
    dossier = racine / source / f"ingestion={horodatage}"
    dossier.mkdir(parents=True)
    fichier = dossier / "donnees.csv"
    fichier.write_text(contenu)
    manifeste = construire_manifeste(source, horodatage, [fichier])
    ecrire_manifeste(manifeste, dossier / "manifeste.json")
    return dossier, fichier


def test_lister_ingestions_vide(tmp_path):
    assert lister_ingestions(tmp_path / "inexistant") == []


def test_lister_ingestions_trouve_les_ingestions(tmp_path):
    _creer_ingestion(tmp_path, "olist", "20260922T101500")
    _creer_ingestion(tmp_path, "rakuten", "20260922T101600")
    ingestions = lister_ingestions(tmp_path)
    assert sorted(i.source for i in ingestions) == ["olist", "rakuten"]


def test_verifier_sans_alteration(tmp_path):
    _creer_ingestion(tmp_path, "olist", "20260922T101500")
    assert verifier_ingestions(tmp_path) == []


def test_verifier_detecte_une_alteration(tmp_path):
    _dossier, fichier = _creer_ingestion(tmp_path, "olist", "20260922T101500")
    fichier.write_text("id\n1\n2\n3\n")  # un fichier modifié après coup
    anomalies = verifier_ingestions(tmp_path)
    assert len(anomalies) == 1
    assert anomalies[0].fichier == "donnees.csv"


def test_verifier_detecte_un_fichier_manquant(tmp_path):
    _dossier, fichier = _creer_ingestion(tmp_path, "olist", "20260922T101500")
    fichier.unlink()
    anomalies = verifier_ingestions(tmp_path)
    assert len(anomalies) == 1
    assert anomalies[0].trouve is None
