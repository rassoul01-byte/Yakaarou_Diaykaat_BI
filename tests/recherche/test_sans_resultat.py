"""Tests des requêtes sans résultat (F4.5), sans Elasticsearch ni base.

Le journal est une simple liste, et le client un faux qui répond « rien » pour
les requêtes qu'on lui désigne.
"""

import pytest

from recherche.sans_resultat import Bilan, RequeteJournal, trouver_sans_resultat


def requete(texte, occurrences, jours=1):
    return RequeteJournal(requete=texte, occurrences=occurrences, jours=jours)


class FauxClient:
    """Répond « zéro fiche » aux requêtes de `introuvables`, « une fiche » aux autres."""

    def __init__(self, introuvables=()):
        self.introuvables = set(introuvables)
        self.lots = []

    def msearch(self, searches):
        textes = [
            corps["query"]["bool"]["must"][0]["multi_match"]["query"] for corps in searches[1::2]
        ]
        self.lots.append(textes)
        return {
            "responses": [
                {
                    "took": 1,
                    "hits": {"total": {"value": 0 if t in self.introuvables else 1}, "hits": []},
                }
                for t in textes
            ]
        }


def test_seules_les_requetes_sans_resultat_sont_gardees():
    journal = [requete("lampe", 10), requete("bcdfghjk", 3), requete("chaise", 7)]
    bilan = trouver_sans_resultat(FauxClient({"bcdfghjk"}), journal)
    assert [r.requete for r in bilan.sans_resultat] == ["bcdfghjk"]
    assert bilan.analysees == 3


def test_le_classement_va_de_la_plus_frequente_a_la_moins_frequente():
    journal = [requete("zzz", 2), requete("aaa", 9), requete("mmm", 5)]
    bilan = trouver_sans_resultat(FauxClient({"zzz", "aaa", "mmm"}), journal)
    assert [r.requete for r in bilan.sans_resultat] == ["aaa", "mmm", "zzz"]


def test_a_frequence_egale_l_ordre_est_alphabetique_donc_stable():
    journal = [requete("bbb", 4), requete("aaa", 4)]
    bilan = trouver_sans_resultat(FauxClient({"aaa", "bbb"}), journal)
    assert [r.requete for r in bilan.sans_resultat] == ["aaa", "bbb"]


def test_le_journal_est_rejoue_par_lots():
    journal = [requete(f"requete{i}", 1) for i in range(5)]
    client = FauxClient()
    trouver_sans_resultat(client, journal, taille_lot=2)
    assert [len(lot) for lot in client.lots] == [2, 2, 1]


def test_un_journal_vide_n_appelle_pas_elasticsearch():
    client = FauxClient()
    bilan = trouver_sans_resultat(client, [])
    assert client.lots == []
    assert bilan.analysees == 0
    assert bilan.sans_resultat == []


def test_la_part_est_calculee_sur_les_recherches_pas_sur_les_requetes_distinctes():
    # 1 requête distincte sur 2 est sans résultat, mais elle pèse 30 recherches sur 100.
    bilan = trouver_sans_resultat(
        FauxClient({"rare"}), [requete("frequente", 70), requete("rare", 30)]
    )
    assert bilan.occurrences_sans_resultat == 30
    assert bilan.part_des_recherches == pytest.approx(30.0)


def test_la_part_est_indefinie_et_non_nulle_quand_rien_n_est_analyse():
    assert Bilan(0, 0, []).part_des_recherches is None
