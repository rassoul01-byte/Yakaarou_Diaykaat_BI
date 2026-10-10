"""Le chargement des passages, et le refus d'un corpus invalide."""

import json

import pytest

from assistant.passages import FAQ, ErreurCorpus, Passage, charger


def test_les_quarante_passages_de_la_foire_aux_questions_se_chargent():
    passages = charger()
    assert len(passages) == 40
    assert len({p.id for p in passages}) == 40
    assert {p.theme for p in passages} == {"livraison", "retours", "paiement", "commande", "compte"}
    assert all(p.source.startswith(("donnee:", "politique:")) for p in passages)


def test_un_passage_porte_un_score_nul_tant_qu_il_n_est_pas_retrouve():
    assert charger()[0].score == 0.0
    assert charger()[0].avec_score(0.5).score == 0.5


def test_un_corpus_invalide_est_refuse(tmp_path):
    mauvais = tmp_path / "faq.jsonl"
    mauvais.write_text(json.dumps({"id": "x-01", "question": "Q ?"}) + "\n", encoding="utf-8")
    with pytest.raises(ErreurCorpus):
        charger(mauvais)


def test_un_fichier_absent_est_une_erreur_de_corpus(tmp_path):
    with pytest.raises(ErreurCorpus):
        charger(tmp_path / "absent.jsonl")


def test_le_fichier_charge_est_celui_du_contrat():
    assert FAQ.name == "faq.jsonl" and FAQ.exists()


def test_en_dict_garde_tous_les_champs():
    assert set(Passage("a", "b", "c", "d", "e").en_dict()) == {
        "id", "theme", "question", "reponse", "source", "score",
    }  # fmt: skip
