"""Le compositeur : le texte d'une réponse est celui du passage, et les refus ne promettent rien."""

import re

import pytest

from assistant import compositeur, garde_fous
from assistant.passages import charger

MOTIFS = [
    garde_fous.PRIX,
    garde_fous.COMMANDE_PRECISE,
    garde_fous.REMBOURSEMENT_PERSONNALISE,
    garde_fous.QUESTION_INVALIDE,
    garde_fous.AUCUN_PASSAGE,
    garde_fous.HORS_BASE,
    garde_fous.INCERTAIN,
]


def test_la_reponse_est_le_texte_du_passage_suivi_de_sa_citation():
    passage = charger()[0]
    assert compositeur.composer(passage) == f"{passage.reponse} [{passage.id}]"


def test_la_reponse_ne_contient_rien_d_autre_que_le_passage():
    for passage in charger():
        sans_citation = compositeur.composer(passage).removesuffix(f" [{passage.id}]")
        assert sans_citation == passage.reponse


def test_chaque_motif_de_refus_a_un_texte_et_aucun_texte_n_est_orphelin():
    assert set(compositeur.REFUS) == set(MOTIFS)


@pytest.mark.parametrize("motif", [m for m in MOTIFS if m != garde_fous.QUESTION_INVALIDE])
def test_un_refus_renvoie_au_service_client(motif):
    assert "service client" in compositeur.refuser(motif)


@pytest.mark.parametrize("motif", MOTIFS)
def test_un_refus_n_invente_ni_adresse_ni_telephone_ni_lien(motif):
    """Le corpus ne contient aucun contact : un refus n'en fabrique pas."""
    texte = compositeur.refuser(motif)
    assert not re.search(r"@|https?://|www\.|\d{4,}|\d[\d .-]{7,}\d", texte)


def test_le_refus_incertain_invite_a_choisir_parmi_des_suggestions():
    assert "l'une de celles-ci" in compositeur.refuser(garde_fous.INCERTAIN)
