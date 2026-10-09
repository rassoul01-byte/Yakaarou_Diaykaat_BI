"""Le chargement du journal dans PostgreSQL : sans doublon, sans donnée personnelle, sans silence.

Ce que ces tests protègent : le taux de réponses ancrées que lit Power BI vient de cette table.
Une ligne comptée deux fois, une question non masquée ou une ligne illisible avalée en silence
fausseraient le chiffre ou fuiteraient une donnée.
"""

import json
from datetime import UTC, date, datetime

import psycopg2.extras
import pytest

from assistant import charger_journal as cj
from assistant import evaluer as evaluation
from assistant.assistant import repondre
from assistant.journal import JournalMemoire, entree
from tests.assistant.test_assistant import FauxRetrouveur, passage


def une_entree(**surcharges):
    base = {
        "horodatage": "2026-10-07T09:00:00+00:00",
        "question": "Quel délai pour un retour ?",
        "refus": False,
        "motif": None,
        "passages_cites": ["ret-01"],
        "score_meilleur": 0.9,
        "suggestions": [],
        "duree_ms": 12.4,
        "retrouveur": "faux",
    }
    return {**base, **surcharges}


def ecrire(chemin, entrees, brut=()):
    lignes = [json.dumps(e, ensure_ascii=False) for e in entrees] + list(brut)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


# --- Une entrée devient une ligne --------------------------------------------


def test_une_entree_valide_donne_une_ligne_complete():
    ligne = cj.en_ligne(une_entree(), "usage", "id-1")

    assert len(ligne) == len(cj.CHAMPS)
    assert dict(zip(cj.CHAMPS, ligne, strict=True)) == {
        "id_echange": "id-1",
        "source": "usage",
        "horodatage": datetime(2026, 10, 7, 9, 0, tzinfo=UTC),
        "jour": date(2026, 10, 7),
        "question": "Quel délai pour un retour ?",
        "refus": False,
        "motif": None,
        "passages_cites": ["ret-01"],
        "score_meilleur": 0.9,
        "suggestions": [],
        "duree_ms": 12,
        "retrouveur": "faux",
        # `une_entree()` ne les porte pas : un journal d'avant la migration 023 se
        # charge quand même, avec l'origine par défaut.
        "origine": "saisie",
        "reformulation": None,
    }


def test_le_jour_est_celui_du_temps_universel():
    ligne = cj.en_ligne(une_entree(horodatage="2026-10-07T23:30:00-02:00"), "usage", "id-1")

    assert ligne[3] == date(2026, 10, 8)  # 23 h 30 à UTC-2 = 1 h 30 le lendemain, UTC


def test_un_horodatage_sans_fuseau_est_lu_comme_universel():
    ligne = cj.en_ligne(une_entree(horodatage="2026-10-07T09:00:00"), "usage", "id-1")

    assert ligne[2] == datetime(2026, 10, 7, 9, 0, tzinfo=UTC)


def test_la_question_est_masquee_une_seconde_fois():
    ligne = cj.en_ligne(une_entree(question="écrivez à marie@exemple.com svp"), "usage", "id-1")

    assert ligne[4] == "écrivez à [email] svp"


def test_un_refus_sans_passage_est_une_entree_valide():
    ligne = cj.en_ligne(
        une_entree(refus=True, motif="hors_base", passages_cites=[], score_meilleur=None),
        "usage",
        "id-1",
    )

    assert ligne[5] is True
    assert ligne[7] == [] and ligne[8] is None


@pytest.mark.parametrize(
    ("surcharge", "cause"),
    [
        ({"refus": "non"}, "refus"),
        ({"refus": None}, "refus"),
        ({"question": ""}, "question"),
        ({"horodatage": "hier"}, "horodatage"),
        ({"horodatage": None}, "horodatage"),
        ({"passages_cites": "ret-01"}, "passages_cites"),
        ({"suggestions": [1, 2]}, "suggestions"),
        ({"score_meilleur": "haut"}, "score_meilleur"),
        ({"duree_ms": True}, "duree_ms"),
        ({"retrouveur": None}, "retrouveur"),
        ({"origine": "ailleurs"}, "origine"),
        ({"reformulation": 12}, "reformulation"),
    ],
)
def test_une_entree_invalide_est_refusee_avec_sa_cause(surcharge, cause):
    with pytest.raises(ValueError, match=cause):
        cj.en_ligne(une_entree(**surcharge), "usage", "id-1")


def test_la_reformulation_est_masquee_une_seconde_fois():
    """Le fichier peut venir d'ailleurs que de l'assistant : la base ne doit rien recevoir."""
    ligne = cj.en_ligne(
        une_entree(origine="suggestion", reformulation="ma commande 8f3a2c9d1e est perdue"),
        "usage",
        "id-1",
    )
    colonnes = dict(zip(cj.CHAMPS, ligne, strict=True))
    assert colonnes["origine"] == "suggestion"
    assert colonnes["reformulation"] == "ma commande [identifiant] est perdue"


def test_l_entree_ecrite_par_l_assistant_se_charge_telle_quelle():
    # Le format du §5 du contrat : ce que `journal.entree` écrit, le chargeur le lit.
    reponse = repondre("Quel délai ?", FauxRetrouveur([passage()]))

    ligne = cj.en_ligne(entree(reponse, "faux"), "usage", "id-1")

    assert ligne[7] == ["ret-01"] and ligne[5] is False


# --- L'empreinte : la protection contre les doublons --------------------------


def test_l_empreinte_est_stable_d_un_chargement_a_l_autre():
    assert cj.empreinte("usage", "ligne", 0) == cj.empreinte("usage", "ligne", 0)


def test_l_empreinte_distingue_la_source_et_le_rang():
    toutes = {
        cj.empreinte("usage", "ligne", 0),
        cj.empreinte("evaluation", "ligne", 0),
        cj.empreinte("usage", "ligne", 1),
        cj.empreinte("usage", "autre ligne", 0),
    }

    assert len(toutes) == 4


# --- La lecture du fichier -----------------------------------------------------


def test_la_lecture_compte_les_lignes_et_ignore_les_lignes_vides(tmp_path):
    chemin = tmp_path / "journal.jsonl"
    chemin.write_text(
        json.dumps(une_entree()) + "\n\n" + json.dumps(une_entree(question="Autre ?")) + "\n",
        encoding="utf-8",
    )

    lignes, bilan = cj.lire(chemin, "usage")

    assert (bilan.lues, len(lignes), bilan.illisibles) == (2, 2, [])


def test_une_ligne_illisible_est_signalee_avec_son_numero_jamais_avalee(tmp_path):
    chemin = ecrire(
        tmp_path / "journal.jsonl",
        [une_entree()],
        brut=["{pas du json", "[1, 2]", json.dumps(une_entree(refus="non"))],
    )

    lignes, bilan = cj.lire(chemin, "usage")

    assert len(lignes) == 1
    assert [numero for numero, _ in bilan.illisibles] == [2, 3, 4]
    assert "refus" in bilan.illisibles[2][1]
    assert bilan.lues == 4


def test_deux_echanges_identiques_restent_deux_echanges(tmp_path):
    chemin = ecrire(tmp_path / "journal.jsonl", [une_entree(), une_entree()])

    lignes, _ = cj.lire(chemin, "usage")

    assert lignes[0][0] != lignes[1][0]


def test_relire_le_meme_fichier_redonne_les_memes_identifiants(tmp_path):
    chemin = ecrire(
        tmp_path / "journal.jsonl", [une_entree(), une_entree(), une_entree(question="B ?")]
    )

    premiere, _ = cj.lire(chemin, "usage")
    seconde, _ = cj.lire(chemin, "usage")

    assert [ligne[0] for ligne in premiere] == [ligne[0] for ligne in seconde]


# --- L'écriture en base (simulée) ----------------------------------------------


class FauxCurseur:
    """Une table à clé primaire : ON CONFLICT DO NOTHING, et un journal des requêtes."""

    def __init__(self, base):
        self.base = base
        self.rowcount = 0

    def execute(self, requete, parametres=()):
        self.base.requetes.append((" ".join(requete.split()), parametres))
        if requete.lstrip().startswith("DELETE"):
            source = parametres[0]
            self.base.lignes = {k: v for k, v in self.base.lignes.items() if v[1] != source}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FausseBase:
    def __init__(self):
        self.lignes = {}
        self.requetes = []
        self.ferme = False

    def cursor(self):
        return FauxCurseur(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def close(self):
        self.ferme = True


@pytest.fixture
def base(monkeypatch):
    fausse = FausseBase()
    monkeypatch.setattr(cj.psycopg2, "connect", lambda dsn: fausse)

    def faux_execute_values(curseur, _requete, lot, page_size):
        assert page_size == len(lot)  # sans cela, rowcount ne compterait que la dernière page
        nouvelles = [ligne for ligne in lot if ligne[0] not in curseur.base.lignes]
        curseur.base.lignes.update({ligne[0]: ligne for ligne in nouvelles})
        curseur.rowcount = len(nouvelles)

    monkeypatch.setattr(psycopg2.extras, "execute_values", faux_execute_values)
    return fausse


def test_charger_deux_fois_le_meme_journal_n_ajoute_rien(tmp_path, base):
    chemin = ecrire(tmp_path / "journal.jsonl", [une_entree(), une_entree(question="B ?")])

    premier = cj.charger(chemin, "usage", dsn="faux")
    second = cj.charger(chemin, "usage", dsn="faux")

    assert (premier.inserees, premier.deja_presentes) == (2, 0)
    assert (second.inserees, second.deja_presentes) == (0, 2)
    assert len(base.lignes) == 2
    assert base.ferme


def test_un_usage_ne_supprime_jamais_de_lignes(tmp_path, base):
    chemin = ecrire(tmp_path / "journal.jsonl", [une_entree()])

    cj.charger(chemin, "usage", dsn="faux")

    assert not any(requete.startswith("DELETE") for requete, _ in base.requetes)


def test_une_evaluation_remplace_l_evaluation_precedente(tmp_path, base):
    premiere = ecrire(tmp_path / "e1.jsonl", [une_entree(), une_entree(question="B ?")])
    seconde = ecrire(tmp_path / "e2.jsonl", [une_entree(question="C ?")])

    cj.charger(premiere, "evaluation", dsn="faux")
    cj.charger(seconde, "evaluation", dsn="faux")

    assert [ligne[4] for ligne in base.lignes.values()] == ["C ?"]


def test_une_evaluation_ne_touche_pas_aux_lignes_d_usage(tmp_path, base):
    cj.charger(ecrire(tmp_path / "u.jsonl", [une_entree()]), "usage", dsn="faux")
    cj.charger(ecrire(tmp_path / "e.jsonl", [une_entree(question="B ?")]), "evaluation", dsn="faux")

    assert {ligne[1] for ligne in base.lignes.values()} == {"usage", "evaluation"}


def test_les_lignes_illisibles_ne_bloquent_pas_le_chargement_des_autres(tmp_path, base):
    chemin = ecrire(tmp_path / "journal.jsonl", [une_entree()], brut=["{casse"])

    bilan = cj.charger(chemin, "usage", dsn="faux")

    assert (bilan.inserees, len(bilan.illisibles)) == (1, 1)


# --- La commande -------------------------------------------------------------------


def test_un_journal_absent_est_une_erreur_claire(tmp_path, capsys):
    code = cj.main(["--source", "evaluation", "--journal", str(tmp_path / "absent.jsonl")])

    assert code == 1
    assert "introuvable" in capsys.readouterr().err


def test_la_commande_affiche_le_bilan(tmp_path, base, capsys):
    chemin = ecrire(tmp_path / "journal.jsonl", [une_entree()], brut=["{casse"])

    code = cj.main(["--journal", str(chemin)])
    sortie = capsys.readouterr().out

    assert code == 0
    assert "ajoutées           : 1" in sortie
    assert "illisibles         : 1" in sortie
    assert "ligne 2" in sortie


def test_chaque_source_a_son_journal_par_defaut(monkeypatch):
    monkeypatch.delenv("ASSISTANT_JOURNAL", raising=False)

    assert cj.chemin_du_journal("evaluation").name == "journal_evaluation.jsonl"
    assert cj.chemin_du_journal("usage").name == "journal.jsonl"


# --- L'évaluation écrit son journal ---------------------------------------------


def test_l_evaluation_journalise_un_echange_par_question():
    jeu = [
        {"question": "Quel délai ?", "attendu": "reponse", "passage": "ret-01", "categorie": "x"},
        {"question": "Combien coûte un canapé ?", "attendu": "refus", "categorie": "x"},
    ]
    journal = JournalMemoire()

    evaluation.evaluer(FauxRetrouveur([passage()]), jeu, journal=journal)

    assert len(journal.entrees) == 2


def test_evaluer_sans_journal_n_ecrit_rien(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASSISTANT_RETROUVEUR", "depannage")

    evaluation.main([])

    assert not (tmp_path / "data").exists()


def test_evaluer_avec_journal_ecrit_un_instantane_pas_un_cumul(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSISTANT_RETROUVEUR", "depannage")
    chemin = tmp_path / "journal_evaluation.jsonl"

    evaluation.main(["--journal", str(chemin)])
    premiere = len(chemin.read_text(encoding="utf-8").splitlines())
    evaluation.main(["--journal", str(chemin)])
    seconde = len(chemin.read_text(encoding="utf-8").splitlines())

    assert premiere == seconde == len(evaluation.lire_jeu())
