from zone_brute.manifeste import (
    compter_lignes,
    construire_manifeste,
    ecrire_manifeste,
    lire_manifeste,
    sha256_fichier,
)


def test_sha256_fichier_stable(tmp_path):
    fichier = tmp_path / "a.txt"
    fichier.write_text("bonjour\nzone brute\n")
    assert sha256_fichier(fichier) == sha256_fichier(fichier)


def test_sha256_fichier_detecte_modification(tmp_path):
    fichier = tmp_path / "a.txt"
    fichier.write_text("version 1")
    empreinte_1 = sha256_fichier(fichier)
    fichier.write_text("version 2")
    empreinte_2 = sha256_fichier(fichier)
    assert empreinte_1 != empreinte_2


def test_compter_lignes(tmp_path):
    fichier = tmp_path / "a.csv"
    fichier.write_text("l1\nl2\nl3\n")
    assert compter_lignes(fichier) == 3


def test_construire_et_relire_manifeste(tmp_path):
    fichier = tmp_path / "olist_orders_dataset.csv"
    fichier.write_text("id,valeur\n1,10\n2,20\n")
    manifeste = construire_manifeste("olist", "20260922T101500", [fichier])

    assert manifeste["source"] == "olist"
    assert manifeste["fichiers"][0]["nom"] == "olist_orders_dataset.csv"
    assert manifeste["fichiers"][0]["lignes"] == 3

    chemin_manifeste = tmp_path / "manifeste.json"
    ecrire_manifeste(manifeste, chemin_manifeste)
    assert lire_manifeste(chemin_manifeste) == manifeste
