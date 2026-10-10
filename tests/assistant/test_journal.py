"""Le journal : il sert à mesurer, et il ne contient jamais de donnée personnelle."""

import json
from datetime import UTC, datetime

import pytest

from assistant.assistant import repondre
from assistant.journal import JournalFichier, JournalMemoire, entree, masquer
from tests.assistant.test_assistant import FauxRetrouveur, passage


@pytest.mark.parametrize(
    ("brut", "masque"),
    [
        ("écrivez à marie.dupont@exemple.com svp", "écrivez à [email] svp"),
        ("ma commande 8f3a2c9d1e est perdue", "ma commande [identifiant] est perdue"),
        ("mon numéro est +221 77 123 45 67", "mon numéro est [telephone]"),
        ("colis n°123456", "colis n°[nombre]"),
        ("Comment suivre ma commande ?", "Comment suivre ma commande ?"),
        ("retour sous 14 jours", "retour sous 14 jours"),
    ],
)
def test_masquage(brut, masque):
    assert masquer(brut) == masque


def test_une_entree_porte_les_champs_du_contrat():
    reponse = repondre("Quel délai ?", FauxRetrouveur([passage()]))
    ligne = entree(reponse, "faux", maintenant=datetime(2026, 10, 6, 9, 0, tzinfo=UTC))
    assert ligne == {
        "horodatage": "2026-10-06T09:00:00+00:00",
        "question": "Quel délai ?",
        "refus": False,
        "motif": None,
        "passages_cites": ["ret-01"],
        "score_meilleur": 0.9,
        "suggestions": [],
        "duree_ms": reponse.duree_ms,
        "retrouveur": "faux",
        "origine": "saisie",
        "reformulation": None,
    }


def test_un_refus_est_distinct_d_une_affirmation_dans_le_journal():
    ligne = entree(repondre("Combien coûte un canapé ?", FauxRetrouveur()), "faux")
    assert ligne["refus"] is True and ligne["motif"] == "prix"
    assert ligne["passages_cites"] == [] and ligne["score_meilleur"] is None


def test_le_fichier_recoit_une_ligne_json_par_echange(tmp_path):
    journal = JournalFichier(tmp_path / "sous" / "journal.jsonl")
    repondre("Quel délai ?", FauxRetrouveur([passage()]), journal=journal)
    repondre("Combien coûte un canapé ?", FauxRetrouveur(), journal=journal)
    lignes = [
        json.loads(ligne) for ligne in journal.chemin.read_text(encoding="utf-8").splitlines()
    ]
    assert [ligne["refus"] for ligne in lignes] == [False, True]


def test_une_donnee_personnelle_tapee_par_le_client_n_atteint_jamais_le_fichier(tmp_path):
    journal = JournalFichier(tmp_path / "journal.jsonl")
    question = "Ma commande 8f3a2c9d1e n'arrive pas, écrivez à marie.dupont@exemple.com ou +221 77 123 45 67"
    repondre(question, FauxRetrouveur([passage()]), journal=journal)
    contenu = journal.chemin.read_text(encoding="utf-8")
    for secret in ("8f3a2c9d1e", "marie.dupont", "exemple.com", "77 123 45 67"):
        assert secret not in contenu


def test_le_chemin_du_journal_vient_de_l_environnement(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSISTANT_JOURNAL", str(tmp_path / "ailleurs.jsonl"))
    assert JournalFichier().chemin == tmp_path / "ailleurs.jsonl"


def test_le_journal_en_memoire_garde_les_entrees():
    journal = JournalMemoire()
    repondre("Quel délai ?", FauxRetrouveur([passage()]), journal=journal)
    assert len(journal.entrees) == 1


def test_le_journal_ne_recopie_ni_la_reponse_ni_le_texte_des_passages():
    """Seuls les identifiants des passages sont gardés : la réponse se retrouve par eux."""
    reponse = repondre("Quel délai ?", FauxRetrouveur([passage()]))
    contenu = json.dumps(entree(reponse, "faux"), ensure_ascii=False)
    assert "Vous avez 14 jours" not in contenu


# ------------------------------------------------- provenance de la question


def test_une_suggestion_cliquee_garde_la_formulation_du_client():
    """Le couple (formulation du client, passage retenu) est ce qui rend le journal utile."""
    reponse = repondre(
        "Quel délai ?",
        FauxRetrouveur([passage()]),
        origine="suggestion",
        reformulation="combien de jours pour renvoyer un truc",
    )
    ligne = entree(
        reponse,
        "faux",
        origine="suggestion",
        reformulation="combien de jours pour renvoyer un truc",
    )
    assert ligne["origine"] == "suggestion"
    assert ligne["reformulation"] == "combien de jours pour renvoyer un truc"
    assert ligne["passages_cites"] == ["ret-01"]


def test_la_reformulation_est_masquee_comme_la_question(tmp_path):
    journal = JournalFichier(tmp_path / "journal.jsonl")
    repondre(
        "Quel délai ?",
        FauxRetrouveur([passage()]),
        journal=journal,
        origine="suggestion",
        reformulation="ma commande 8f3a2c9d1e, écrivez à marie.dupont@exemple.com",
    )
    contenu = journal.chemin.read_text(encoding="utf-8")
    for secret in ("8f3a2c9d1e", "marie.dupont", "exemple.com"):
        assert secret not in contenu
    assert "[identifiant]" in contenu and "[email]" in contenu


def test_une_origine_inconnue_leve_plutot_que_d_ecrire_n_importe_quoi():
    reponse = repondre("Quel délai ?", FauxRetrouveur([passage()]))
    with pytest.raises(ValueError, match="origine inconnue"):
        entree(reponse, "faux", origine="ailleurs")


def test_une_question_tapee_n_a_pas_de_reformulation():
    """Sans ça, la vue des paires compterait la question comme sa propre reformulation."""
    ligne = entree(repondre("Quel délai ?", FauxRetrouveur([passage()])), "faux")
    assert ligne["origine"] == "saisie" and ligne["reformulation"] is None
