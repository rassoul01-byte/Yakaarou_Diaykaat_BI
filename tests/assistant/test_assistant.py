"""L'assistant de bout en bout : répondre avec une citation, ou refuser. Jamais une affirmation sans source."""

import json

import pytest

from assistant import compositeur, garde_fous
from assistant.assistant import Reponse, repondre
from assistant.garde_fous import Seuils
from assistant.journal import JournalMemoire
from assistant.passages import Passage, charger
from assistant.retrouveur import RetrouveurDepannage


class FauxRetrouveur:
    """Une recherche dont on maîtrise les résultats ; elle compte ses appels."""

    nom = "faux"
    seuils = Seuils(reponse=0.5, suggestion=0.3, marge=0.1)

    def __init__(self, passages=()):
        self.passages = list(passages)
        self.appels = 0

    def retrouver(self, question, k=3):
        self.appels += 1
        return self.passages[:k]


def passage(id_="ret-01", score=0.9):
    return Passage(
        id_, "retours", "Quel délai ?", "Vous avez 14 jours.", "politique:retours", score
    )


@pytest.fixture(scope="module")
def reel():
    return RetrouveurDepannage.depuis_faq()


# ------------------------------------------------------------- répondre


def test_une_question_couverte_recoit_le_texte_du_passage_et_sa_citation():
    reponse = repondre("Quel délai ?", FauxRetrouveur([passage()]))
    assert not reponse.refus and reponse.motif is None
    assert reponse.reponse == "Vous avez 14 jours. [ret-01]"
    assert [p.id for p in reponse.passages] == ["ret-01"]


def test_une_question_hors_base_est_refusee_sans_rien_inventer():
    reponse = repondre("Quelle est la capitale du Brésil ?", FauxRetrouveur([passage(score=0.05)]))
    assert reponse.refus and reponse.motif == garde_fous.HORS_BASE
    assert reponse.reponse == compositeur.refuser(garde_fous.HORS_BASE)
    assert reponse.passages == []


def test_un_passage_incertain_propose_au_lieu_d_affirmer():
    proches = [passage("a", 0.42), passage("b", 0.4)]
    reponse = repondre("Une question floue", FauxRetrouveur(proches))
    assert reponse.refus and reponse.motif == garde_fous.INCERTAIN
    assert [p.id for p in reponse.suggestions] == ["a", "b"] and reponse.passages == []


def test_une_regle_de_refus_evite_meme_la_recherche():
    retrouveur = FauxRetrouveur([passage()])
    reponse = repondre("Quel est le prix de la chaise de bureau ?", retrouveur)
    assert reponse.refus and reponse.motif == garde_fous.PRIX
    assert retrouveur.appels == 0


@pytest.mark.parametrize("question", ["", "   ", None, "x" * 501])
def test_une_question_invalide_est_un_refus_pas_une_exception(question):
    assert repondre(question, FauxRetrouveur()).motif == garde_fous.QUESTION_INVALIDE


def test_la_question_est_nettoyee_des_espaces():
    assert repondre("  Quel délai ?  ", FauxRetrouveur([passage()])).question == "Quel délai ?"


def test_une_panne_de_la_recherche_remonte_elle_n_est_pas_un_refus():
    class EnPanne(FauxRetrouveur):
        def retrouver(self, question, k=3):
            raise ConnectionError("recherche injoignable")

    with pytest.raises(ConnectionError):
        repondre("Quel délai ?", EnPanne())


def test_les_seuils_peuvent_etre_imposes_pour_une_mesure():
    strict = Seuils(reponse=0.95, suggestion=0.9, marge=0.0)
    assert repondre("Quel délai ?", FauxRetrouveur([passage(score=0.9)]), seuils=strict).refus


# ------------------------------------- l'invariant : pas d'affirmation sans source


def test_une_reponse_sans_passage_ne_peut_pas_exister():
    with pytest.raises(ValueError):
        Reponse(question="q", refus=False, motif=None, reponse="Vous avez 14 jours.", passages=[])


def test_une_reponse_qui_ajoute_du_texte_au_passage_ne_peut_pas_exister():
    with pytest.raises(ValueError):
        Reponse("q", False, None, "Vous avez 14 jours. [ret-01] Et 30 jours aussi.", [passage()])


def test_un_refus_ne_cite_aucun_passage_et_porte_un_motif():
    with pytest.raises(ValueError):
        Reponse("q", True, None, "Je ne sais pas.")
    with pytest.raises(ValueError):
        Reponse("q", True, garde_fous.HORS_BASE, "Je ne sais pas.", passages=[passage()])


# ------------------------------------------------ le format publié (contrat §3)


def test_le_format_de_sortie_est_celui_du_contrat_et_se_serialise_en_json():
    sortie = repondre("Quel délai ?", FauxRetrouveur([passage()])).en_dict()
    assert set(sortie) == {
        "question",
        "refus",
        "motif",
        "reponse",
        "passages",
        "suggestions",
        "duree_ms",
    }
    assert set(sortie["passages"][0]) == {"id", "theme", "question", "source", "score"}
    assert json.loads(json.dumps(sortie, ensure_ascii=False)) == sortie


def test_un_refus_incertain_publie_ses_suggestions_dans_le_format():
    sortie = repondre("Floue", FauxRetrouveur([passage("a", 0.42), passage("b", 0.4)])).en_dict()
    assert sortie["suggestions"] == [
        {"id": "a", "question": "Quel délai ?"},
        {"id": "b", "question": "Quel délai ?"},
    ]


def test_chaque_echange_est_journalise():
    journal = JournalMemoire()
    repondre("Quel délai ?", FauxRetrouveur([passage()]), journal=journal)
    repondre("Combien coûte un canapé ?", FauxRetrouveur(), journal=journal)
    assert [e["refus"] for e in journal.entrees] == [False, True]
    assert journal.entrees[0]["passages_cites"] == ["ret-01"]
    assert journal.entrees[1]["motif"] == garde_fous.PRIX


# ------------------------------- les critères de réussite du livrable 4, en vrai


@pytest.mark.parametrize(
    ("question", "attendu"),
    [
        ("Comment suivre ma commande ?", "liv-03"),
        ("Qu'est-ce qu'un boleto ?", "pai-02"),
        ("Comment demander un retour ?", "ret-03"),
    ],
)
def test_trois_questions_couvertes_recoivent_une_reponse_juste_avec_citation(
    reel, question, attendu
):
    reponse = repondre(question, reel)
    original = next(p for p in charger() if p.id == attendu)
    assert not reponse.refus
    assert reponse.passages[0].id == attendu
    assert reponse.reponse == f"{original.reponse} [{attendu}]"
    assert reponse.passages[0].source == original.source


@pytest.mark.parametrize(
    "question",
    [
        "Quel est le prix de la chaise de bureau ?",
        "Où est ma commande numéro 8f3a2c ?",
        "Je veux être remboursé de 50 euros pour ma commande",
    ],
)
def test_trois_questions_hors_base_recoivent_un_refus_pas_une_invention(reel, question):
    reponse = repondre(question, reel)
    assert reponse.refus and not reponse.passages
    assert "service client" in reponse.reponse


def test_aucune_reponse_ne_contient_un_mot_absent_du_passage_cite(reel):
    """« Aucune réponse ne contient d'information absente des passages cités », sur toute la base."""
    for p in charger():
        reponse = repondre(p.question, reel)
        if not reponse.refus:
            assert (
                reponse.reponse.removesuffix(f" [{reponse.passages[0].id}]")
                == reponse.passages[0].reponse
            )


# ------------------------------------- le passage choisi par l'utilisateur
#
# Mesuré sur la recherche vectorielle le 2026-10-09 : « Que faire si mon colis arrive
# endommagé ? », qui est le texte EXACT de liv-08, sort première à 0,7993 — très loin
# devant la deuxième (0,5719) — et reste sous le seuil de 0,84. Un clic sur une
# suggestion menait donc à une seconde hésitation.


def test_un_passage_choisi_est_servi_meme_sous_le_seuil():
    """Le seuil départage ce que personne n'a départagé ; ici l'utilisateur l'a fait."""
    sous_le_seuil = passage(score=0.2)  # seuils.reponse vaut 0,5 pour FauxRetrouveur
    reponse = repondre("Quel délai ?", FauxRetrouveur([sous_le_seuil]), passage_choisi="ret-01")
    assert not reponse.refus
    assert [p.id for p in reponse.passages] == ["ret-01"]


def test_un_passage_choisi_garde_son_vrai_score():
    """On ne maquille pas la proximité en 1,0 sous prétexte que l'utilisateur a cliqué."""
    reponse = repondre(
        "Quel délai ?", FauxRetrouveur([passage(score=0.2)]), passage_choisi="ret-01"
    )
    assert reponse.passages[0].score == pytest.approx(0.2)


def test_un_passage_choisi_reste_le_texte_exact_de_la_foire_aux_questions():
    retenu = passage(score=0.2)
    reponse = repondre("Quel délai ?", FauxRetrouveur([retenu]), passage_choisi="ret-01")
    assert reponse.reponse == compositeur.composer(retenu)


def test_un_identifiant_absent_des_resultats_ne_change_rien():
    """On ne sert que ce que la recherche a rendu : pas de passage sorti de nulle part."""
    reponse = repondre(
        "Quel délai ?", FauxRetrouveur([passage(score=0.2)]), passage_choisi="cpt-99"
    )
    assert reponse.refus


def test_un_passage_choisi_ne_contourne_pas_le_filtre_d_avant():
    """Un clic ne doit pas servir de laissez-passer pour une question hors périmètre."""
    reponse = repondre(
        "Je veux être remboursé de 50 euros",
        FauxRetrouveur([passage(score=0.9)]),
        passage_choisi="ret-01",
    )
    assert reponse.refus and reponse.motif == garde_fous.REMBOURSEMENT_PERSONNALISE


def test_cliquer_chaque_question_de_la_base_donne_sa_reponse(reel):
    """Le cas d'usage réel : une suggestion cliquée répond toujours, pour les 40 passages."""
    for p in charger():
        reponse = repondre(p.question, reel, passage_choisi=p.id)
        assert not reponse.refus, f"{p.id} refusée alors qu'elle a été choisie"
        assert reponse.passages[0].id == p.id
