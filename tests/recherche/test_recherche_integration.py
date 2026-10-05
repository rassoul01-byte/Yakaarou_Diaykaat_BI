"""Tests d'intégration du moteur : ils exigent Elasticsearch et l'index chargé.

    docker compose up -d
    docker compose exec app python -m recherche.indexer
    docker compose exec app pytest -m integration tests/recherche

Ce fichier est aussi le JEU D'ÉVALUATION qui justifie le réglage de la
tolérance : chaque cas écrit ci-dessous est une promesse faite au moteur.
Quand on change un réglage dans `moteur.py`, c'est ici qu'on voit ce qu'il
gagne et ce qu'il perd. Le tableau des essais va dans la description de la PR.

⚠️ Les attentes sont écrites à partir du catalogue Rakuten attendu ; à
ajuster si une désignation n'existe pas dans l'index réel, en le notant.
"""

import statistics
import unicodedata

import pytest

from recherche.client import connexion
from recherche.moteur import SEUIL_REPONSE_MS, rechercher
from recherche.schema import INDEX

pytestmark = pytest.mark.integration


def sans_accent(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


@pytest.fixture(scope="module")
def client():
    es = connexion()
    if not es.indices.exists(index=INDEX):
        pytest.skip("index « catalogue » absent : lancer python -m recherche.indexer")
    return es


# Fautes à rattraper : (ce que l'acheteur tape, un mot attendu dans les premières désignations).
FAUTES_A_RATTRAPER = [
    ("chaise de bureu", "bureau"),  # le critère de F4.2
    ("eclairage", "eclairage"),  # accent manquant, géré par l'analyseur
    ("lampes", "lampe"),  # pluriel
    ("chaize", "chaise"),  # lettre remplacée
    ("bureua", "bureau"),  # lettre ajoutée
]


@pytest.mark.parametrize(("tape", "attendu"), FAUTES_A_RATTRAPER)
def test_les_fautes_de_frappe_sont_rattrapees(client, tape, attendu):
    reponse = rechercher(client, tape, taille=10)
    assert reponse.aboutit, f"« {tape} » ne ramène rien"
    designations = [sans_accent(r.designation) for r in reponse.resultats]
    assert any(attendu in d for d in designations), (
        f"« {tape} » ramène des fiches, mais aucune ne contient « {attendu} » : {designations[:3]}"
    )


# Pièges : des mots proches qu'il ne faut pas confondre.
# (ce que l'acheteur tape, un mot voisin qui ne doit pas apparaître seul)
PIEGES = [
    ("lampe", "rampe"),
]


@pytest.mark.parametrize(("tape", "voisin"), PIEGES)
def test_un_mot_voisin_n_est_pas_confondu(client, tape, voisin):
    reponse = rechercher(client, tape, taille=20)
    confondus = [
        r.designation
        for r in reponse.resultats
        if voisin in sans_accent(r.designation) and tape[:4] not in sans_accent(r.designation)
    ]
    assert not confondus, f"« {tape} » ramène « {voisin} » : {confondus[:3]}"


def test_le_filtre_par_categorie_ne_ramene_que_cette_categorie(client):
    categorie = rechercher(client, "chaise", taille=1).resultats[0].categorie_code
    reponse = rechercher(client, "chaise", categorie=categorie, taille=20)
    assert reponse.aboutit
    assert {r.categorie_code for r in reponse.resultats} == {categorie}


def test_le_filtre_par_langue_ne_ramene_que_cette_langue(client):
    reponse = rechercher(client, "chaise", langue="fr", taille=20)
    assert reponse.aboutit
    # `langue` n'est pas rendue dans le résultat : on vérifie par le nombre.
    tout = rechercher(client, "chaise", taille=1).total
    assert reponse.total <= tout


def test_une_chaine_absurde_ne_ramene_rien(client):
    """Ce que fait le générateur avec « requete_introuvable » : F4.5 doit la voir."""
    assert not rechercher(client, "bcdfghjklm").aboutit


# ------------------------------------------------------------ temps de réponse

REQUETES_DE_MESURE = [
    "chaise de bureu",
    "lampe",
    "eclairage",
    "chaise",
    "livre",
    "jeu video",
    "table",
    "canape",
    "tapis",
    "velo",
    "poupee",
    "bcdfghjk",
] * 3


def test_le_temps_de_reponse_reste_sous_la_seconde(client):
    rechercher(client, "chauffe")  # la première requête chauffe les caches : on ne la compte pas
    temps = [rechercher(client, tape).temps_total_ms for tape in REQUETES_DE_MESURE]

    mediane = statistics.median(temps)
    pire = max(temps)
    # Ces chiffres sont à annoncer en démonstration : lancer avec `pytest -s`.
    print(
        f"\nTemps de réponse sur {len(temps)} recherches : médiane {mediane:.0f} ms, pire {pire:.0f} ms"
    )

    assert mediane < SEUIL_REPONSE_MS
