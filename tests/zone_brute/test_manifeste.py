from zone_brute.manifeste import (
    compter_enregistrements,
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
    assert manifeste["fichiers"][0]["lignes"] == 2  # deux lignes de données, en-tête exclu

    chemin_manifeste = tmp_path / "manifeste.json"
    ecrire_manifeste(manifeste, chemin_manifeste)
    assert lire_manifeste(chemin_manifeste) == manifeste


def test_compter_enregistrements_exclut_l_entete_csv(tmp_path):
    fichier = tmp_path / "orders.csv"
    fichier.write_text("order_id,statut\na,delivered\nb,shipped\n", encoding="utf-8")
    assert compter_lignes(fichier) == 3  # lignes physiques
    assert compter_enregistrements(fichier) == 2  # lignes de données


def test_compter_enregistrements_compte_un_champ_multiligne_une_seule_fois(tmp_path):
    fichier = tmp_path / "order_reviews.csv"
    fichier.write_text(
        'review_id,message\nr1,"très bien\nlivré vite"\nr2,\n',
        encoding="utf-8",
    )
    assert compter_lignes(fichier) == 4
    assert compter_enregistrements(fichier) == 2


def test_compter_enregistrements_csv_vide_ou_en_tete_seul(tmp_path):
    vide = tmp_path / "vide.csv"
    vide.write_text("", encoding="utf-8")
    entete = tmp_path / "entete.csv"
    entete.write_text("a,b\n", encoding="utf-8")
    assert compter_enregistrements(vide) == 0
    assert compter_enregistrements(entete) == 0


def test_compter_enregistrements_jsonl_une_ligne_par_evenement(tmp_path):
    fichier = tmp_path / "heure=10.jsonl"
    fichier.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    assert compter_enregistrements(fichier) == 2
