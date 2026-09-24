import json

import pytest

from zone_brute.evenements import (
    _chemin_manifeste,
    _chemin_tranche,
    archiver_evenements,
    rejouer_tranche,
)


def _evenement(id_evenement, horodatage, id_session="s-1"):
    return {
        "version_contrat": 1,
        "id_evenement": id_evenement,
        "type": "page_vue",
        "horodatage": horodatage,
        "id_session": id_session,
        "customer_unique_id": None,
        "id_produit": "P123",
    }


def test_archiver_regroupe_par_tranche_horaire(tmp_path):
    evenements = [
        _evenement("e1", "2026-09-22T10:15:03.412Z"),
        _evenement("e2", "2026-09-22T10:45:00.000Z"),
        _evenement("e3", "2026-09-22T11:05:00.000Z"),
    ]
    chemins = archiver_evenements(evenements, racine=tmp_path)
    assert len(chemins) == 2  # heure=10 et heure=11

    tranche_10 = _chemin_tranche(tmp_path / "date=2026-09-22", "10")
    lignes = tranche_10.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 2

    manifeste_10 = json.loads(_chemin_manifeste(tmp_path / "date=2026-09-22", "10").read_text())
    assert manifeste_10["fichiers"][0]["lignes"] == 2


def test_archiver_ajoute_sans_ecraser(tmp_path):
    archiver_evenements([_evenement("e1", "2026-09-22T10:00:00Z")], racine=tmp_path)
    archiver_evenements([_evenement("e2", "2026-09-22T10:05:00Z")], racine=tmp_path)
    tranche = _chemin_tranche(tmp_path / "date=2026-09-22", "10")
    lignes = tranche.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 2


def test_rejouer_republie_chaque_evenement(tmp_path):
    archiver_evenements(
        [
            _evenement("e1", "2026-09-22T10:00:00Z", id_session="s-1"),
            _evenement("e2", "2026-09-22T10:05:00Z", id_session="s-2"),
        ],
        racine=tmp_path,
    )
    publies = []

    def faux_publieur(sujet, cle, message):
        publies.append((sujet, cle, message))

    compte = rejouer_tranche("2026-09-22", "10", faux_publieur, racine=tmp_path)
    assert compte == 2
    assert all(sujet == "navigation.rejeu" for sujet, _cle, _message in publies)
    assert {cle for _sujet, cle, _message in publies} == {"s-1", "s-2"}


def test_rejouer_tranche_absente_leve_une_erreur(tmp_path):
    with pytest.raises(FileNotFoundError):
        rejouer_tranche("2026-09-22", "23", lambda s, c, m: None, racine=tmp_path)
