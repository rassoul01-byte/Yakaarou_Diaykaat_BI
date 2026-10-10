"""La commande `python -m assistant` : codes de sortie et format."""

import json

import pytest

from assistant.__main__ import main
from assistant.passages import ErreurCorpus
from assistant.retrouveur import RetrouveurDepannage


@pytest.fixture(autouse=True)
def journal_isole(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSISTANT_JOURNAL", str(tmp_path / "journal.jsonl"))


def test_une_reponse_affiche_le_texte_et_ses_sources(capsys):
    assert main(["Comment", "suivre", "ma", "commande", "?"]) == 0
    sortie = capsys.readouterr().out
    assert (
        "[liv-03]" in sortie
        and "Sources :" in sortie
        and "donnee:" in sortie
        or "politique:" in sortie
    )


def test_un_refus_sort_avec_le_code_zero(capsys):
    """Un refus est une réponse correcte : ce n'est pas une panne."""
    assert main(["Combien coûte un canapé ?"]) == 0
    assert "service client" in capsys.readouterr().out


def test_la_sortie_json_suit_le_contrat(capsys):
    assert main(["Comment suivre ma commande ?", "--json", "--sans-journal"]) == 0
    sortie = json.loads(capsys.readouterr().out)
    assert set(sortie) == {
        "question",
        "refus",
        "motif",
        "reponse",
        "passages",
        "suggestions",
        "duree_ms",
    }
    assert sortie["refus"] is False and sortie["passages"][0]["id"] == "liv-03"


def test_un_journal_impossible_a_ecrire_est_une_panne_code_un(monkeypatch, tmp_path, capsys):
    # Dossier neutre : le nom ne doit pas contenir « journal »,
    # sinon l'assertion passerait par hasard.
    bloque = tmp_path / "x"
    bloque.write_text("je suis un fichier", encoding="utf-8")
    monkeypatch.setenv("ASSISTANT_JOURNAL", str(bloque / "journal.jsonl"))

    assert main(["Comment suivre ma commande ?"]) == 1
    err = capsys.readouterr().err
    assert "impossible d'écrire le journal" in err
    assert "Elasticsearch" not in err  # la panne est disque, pas réseau


def test_une_foire_aux_questions_illisible_est_une_panne_code_un(monkeypatch, capsys):
    def casse(*_, **__):
        raise ErreurCorpus("faq.jsonl illisible")

    monkeypatch.setattr(RetrouveurDepannage, "depuis_faq", classmethod(casse))
    assert main(["Comment suivre ma commande ?"]) == 1
    assert "ERREUR" in capsys.readouterr().err


def test_panne_elasticsearch_est_une_panne_code_un(monkeypatch, capsys):
    """Une vraie panne ES sort en code 1 avec un message clair, sans stacktrace."""

    def casse(*_, **__):
        raise ConnectionError("hors ligne")

    monkeypatch.setattr("assistant.__main__.creer_retrouveur", casse)

    assert main(["Comment suivre ma commande ?"]) == 1
    err = capsys.readouterr().err
    assert "Elasticsearch" in err
    assert "impossible d'écrire le journal" not in err
