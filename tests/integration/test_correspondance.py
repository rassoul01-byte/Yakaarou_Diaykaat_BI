"""Tests unitaires de F1.9 sans connexion PostgreSQL réelle.

Ces tests étaient marqués `integration` alors qu'ils n'ouvrent aucune
connexion et tournent en un dixième de seconde. Le marqueur les écartait de
l'intégration continue (`pytest -m "not integration"`), qui perdait donc toute
la couverture de la correspondance — y compris le test de déterminisme, qui
est la garantie centrale de `docs/contrats/correspondance.md`.
"""

from pathlib import Path

import pytest

from integration.correspondance import (
    CorrespondanceError,
    charger_mapping,
    construire_correspondance,
    verifier_mapping,
)


def test_charger_mapping(tmp_path: Path):
    fichier = tmp_path / "mapping.csv"
    fichier.write_text(
        "categorie_olist,categorie_rakuten,justification\n"
        "livros_tecnicos,10,Livres\n"
        "brinquedos,1280,Jouets\n"
        "inconnu,inconnu,Aucune correspondance\n",
        encoding="utf-8",
    )

    mapping = charger_mapping(fichier)

    assert mapping == {
        "livros_tecnicos": "10",
        "brinquedos": "1280",
        "inconnu": "inconnu",
    }


def test_categorie_absente_du_mapping():
    produits = [
        ("p1", "brinquedos"),
        ("p2", "telefonia"),
    ]

    mapping = {
        "brinquedos": "1280",
    }

    fiches = {
        "1280": ["f1"],
    }

    with pytest.raises(CorrespondanceError, match="telefonia"):
        verifier_mapping(produits, mapping, fiches)


def test_categorie_rakuten_absente_du_catalogue():
    produits = [
        ("p1", "brinquedos"),
    ]

    mapping = {
        "brinquedos": "1280",
    }

    fiches = {
        "10": ["f1"],
    }

    with pytest.raises(CorrespondanceError, match="1280"):
        verifier_mapping(produits, mapping, fiches)


def test_produit_sans_correspondance_est_conserve():
    produits = [
        ("p1", "brinquedos"),
        ("p2", "inconnu"),
    ]

    mapping = {
        "brinquedos": "1280",
        "inconnu": "inconnu",
    }

    fiches = {
        "1280": ["f1", "f2"],
    }

    lignes = construire_correspondance(
        produits,
        mapping,
        fiches,
    )

    assert len(lignes) == 2
    assert lignes[1] == (
        "p2",
        None,
        "inconnu",
        "inconnu",
        False,
    )


def test_determinisme():
    produits = [
        ("p3", "brinquedos"),
        ("p1", "brinquedos"),
        ("p2", "brinquedos"),
    ]

    mapping = {
        "brinquedos": "1280",
    }

    fiches = {
        "1280": ["f1", "f2", "f3"],
    }

    premiere = construire_correspondance(
        produits,
        mapping,
        fiches,
        seed=36019,
    )

    deuxieme = construire_correspondance(
        produits,
        mapping,
        fiches,
        seed=36019,
    )

    assert premiere == deuxieme


def test_nombre_total_conserve():
    produits = [
        ("p1", "brinquedos"),
        ("p2", "brinquedos"),
        ("p3", "inconnu"),
        ("p4", "inconnu"),
    ]

    mapping = {
        "brinquedos": "1280",
        "inconnu": "inconnu",
    }

    fiches = {
        "1280": ["f1"],
    }

    lignes = construire_correspondance(
        produits,
        mapping,
        fiches,
    )

    assert len(lignes) == len(produits)
