"""Tests de la source documentaire.

Le point qui compte : un champ absent n'est pas un champ vide. C'est la raison
d'être du choix de MongoDB pour cette source, et c'est ce que le contrôle de
qualité devra savoir lire.

Aucun test n'a besoin de MongoDB : les fonctions travaillent sur des
dictionnaires, et la collection est remplacée par un faux.
"""

import csv

import pytest

from acquisition.catalogue import COLONNES, charger, document, extraire, ligne_plate, nom_base


def ligne_source(index=1, description="Une belle lampe", code="2060"):
    return {
        "index_ligne": str(index),
        "jeu": "train",
        "productid": f"p{index}",
        "imageid": f"i{index}",
        "designation": "Lampe de bureau",
        "description": description,
        "prdtypecode": code,
    }


class FausseCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.vide = False
        self.index = []

    def delete_many(self, filtre):
        self.vide = True
        self.documents = []

    def insert_many(self, lot):
        self.documents.extend(lot)

    def create_index(self, champ):
        self.index.append(champ)

    def find(self, filtre, projection):
        return self

    def sort(self, ordre):
        return iter(self.documents)


class FausseBase(dict):
    pass


# --- Le document : ce qui est absent n'est pas vide --------------------------


def test_une_fiche_avec_description_porte_le_champ():
    assert document(ligne_source())["description"] == "Une belle lampe"


def test_une_fiche_sans_description_n_a_pas_le_champ():
    # Et non : description = "". C'est tout l'intérêt de la base documentaire.
    doc = document(ligne_source(description=""))

    assert "description" not in doc


def test_une_description_faite_d_espaces_est_traitee_comme_absente():
    assert "description" not in document(ligne_source(description="   "))


def test_une_fiche_sans_categorie_n_a_pas_le_champ():
    assert "prdtypecode" not in document(ligne_source(code=""))


def test_le_code_categorie_est_un_entier():
    # Dans MongoDB on garde le type ; c'est à l'indexation d'en faire un filtre.
    assert document(ligne_source(code="2060"))["prdtypecode"] == 2060


def test_les_champs_obligatoires_sont_toujours_presents():
    doc = document(ligne_source(description="", code=""))

    assert set(doc) == {"index_ligne", "jeu", "productid", "imageid", "designation"}


def test_la_colonne_d_index_du_fichier_livre_est_acceptee():
    # Le fichier source nomme la colonne « source_index », la zone
    # intermédiaire « index_ligne » : les deux doivent passer.
    ligne = {
        "source_index": "7",
        "productid": "p7",
        "imageid": "i7",
        "designation": "Lampe",
        "description": "",
        "prdtypecode": "2060",
    }

    assert document(ligne)["index_ligne"] == 7


def test_un_fichier_sans_colonne_d_index_dit_ce_qu_il_a_trouve():
    with pytest.raises(KeyError, match="source_index"):
        document({"productid": "p1", "designation": "Lampe"})


def test_le_jeu_vaut_train_quand_le_fichier_ne_le_precise_pas():
    # Le fichier livré n'a pas de colonne « jeu ».
    ligne = {"source_index": "1", "productid": "p1", "imageid": "i1", "designation": "Lampe"}

    assert document(ligne)["jeu"] == "train"


# --- La remise à plat pour la zone brute ------------------------------------


def test_un_champ_absent_devient_une_colonne_vide_et_un_marqueur():
    plat = ligne_plate({"index_ligne": 1, "productid": "p1", "designation": "Lampe"})

    assert plat["description"] == ""
    assert plat["a_description"] == "non"


def test_un_champ_present_est_marque_comme_tel():
    plat = ligne_plate(
        {"index_ligne": 1, "productid": "p1", "designation": "Lampe", "description": "Texte"}
    )

    assert plat["a_description"] == "oui"


def test_la_remise_a_plat_produit_toutes_les_colonnes_attendues():
    plat = ligne_plate({"index_ligne": 1, "productid": "p1", "designation": "Lampe"})

    assert set(plat) == set(COLONNES)


# --- Le chargement -----------------------------------------------------------


def test_la_collection_est_videe_avant_d_etre_remplie(tmp_path):
    # Un chargement initial, pas une synchronisation : deux exécutions donnent
    # exactement la même collection.
    fichier = tmp_path / "catalogue.csv"
    _ecrire(fichier, [ligne_source(1), ligne_source(2, description="")])
    base = FausseBase(produits=FausseCollection([{"ancien": True}]))

    inseres = charger(fichier, base)

    assert inseres == 2
    assert base["produits"].vide is True
    assert len(base["produits"].documents) == 2


def test_le_chargement_respecte_les_lots(tmp_path):
    fichier = tmp_path / "catalogue.csv"
    _ecrire(fichier, [ligne_source(i) for i in range(5)])
    base = FausseBase(produits=FausseCollection())

    assert charger(fichier, base, par_lot=2) == 5


def test_des_index_sont_crees_pour_la_recherche(tmp_path):
    fichier = tmp_path / "catalogue.csv"
    _ecrire(fichier, [ligne_source(1)])
    base = FausseBase(produits=FausseCollection())

    charger(fichier, base)

    assert "productid" in base["produits"].index


# --- L'extraction vers la zone brute ----------------------------------------


def test_l_extraction_ecrit_un_fichier_lisible_par_le_controle(tmp_path):
    base = FausseBase(
        produits=FausseCollection(
            [
                {"index_ligne": 1, "productid": "p1", "designation": "Lampe", "description": "Oui"},
                {"index_ligne": 2, "productid": "p2", "designation": "Table"},
            ]
        )
    )
    destination = tmp_path / "catalogue_produits.csv"

    lignes = extraire(base, destination)

    assert lignes == 2
    contenu = list(csv.DictReader(destination.open(encoding="utf-8")))
    assert [ligne["a_description"] for ligne in contenu] == ["oui", "non"]
    assert contenu[1]["description"] == ""


def test_une_collection_vide_produit_un_fichier_avec_son_entete(tmp_path):
    destination = tmp_path / "catalogue_produits.csv"

    assert extraire(FausseBase(produits=FausseCollection()), destination) == 0
    assert destination.read_text(encoding="utf-8").strip() == ",".join(COLONNES)


# --- L'adresse de la base ----------------------------------------------------


@pytest.mark.parametrize(
    "uri, attendu",
    [
        ("mongodb://u:p@mongodb:27017/catalogue?authSource=admin", "catalogue"),
        ("mongodb://mongodb:27017/catalogue", "catalogue"),
        ("mongodb://mongodb:27017/", "catalogue"),
    ],
)
def test_le_nom_de_la_base_est_extrait_de_l_adresse(uri, attendu):
    assert nom_base(uri) == attendu


def _ecrire(fichier, lignes):
    with fichier.open("w", encoding="utf-8", newline="") as flux:
        redacteur = csv.DictWriter(flux, fieldnames=list(lignes[0]))
        redacteur.writeheader()
        redacteur.writerows(lignes)
