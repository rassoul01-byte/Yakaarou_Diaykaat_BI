"""Tests du chargement QUALITY → PostgreSQL, sans base de données.

Une fausse connexion enregistre les requêtes dans l'ordre : on vérifie la
séquence de la transaction (vidage, copie, quarantaine, journal, validation)
et l'annulation en cas d'échec. Le comportement réel contre PostgreSQL est
couvert par tests/quality/test_integration_qualite.py.
"""

import json

import pytest

from quality.chargement import (
    COLONNES_STAGING,
    TABLES_PAR_SOURCE,
    charger,
    message_journal,
    preparer_rejets,
    verifier_tables,
)
from quality.controle import controler

from .conftest import INGESTION_OLIST, NB_LIVREES_SANS_DATE


class FauxCurseur:
    def __init__(self, connexion):
        self.connexion = connexion
        self._resultat = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, requete, parametres=None):
        self.connexion.journal.append(("execute", " ".join(requete.split())))
        if "SELECT DISTINCT regle_violee" in requete:
            self._resultat = [(r,) for r in self.connexion.regles_deja_presentes]
        elif "RETURNING id" in requete:
            if self.connexion.echouer_au_journal:
                raise RuntimeError("panne simulée")
            self._resultat = [(42,)]

    def fetchall(self):
        return self._resultat

    def fetchone(self):
        return self._resultat[0]

    def copy_expert(self, requete, tampon):
        self.connexion.journal.append(("copy", requete))
        self.connexion.copies[requete.split()[1].split("(")[0]] = tampon.getvalue()


class FausseConnexion:
    def __init__(self, regles_deja_presentes=(), echouer_au_journal=False):
        self.journal = []
        self.copies = {}
        self.rejets_inseres = []
        self.regles_deja_presentes = list(regles_deja_presentes)
        self.echouer_au_journal = echouer_au_journal
        self.commit_effectue = False
        self.rollback_effectue = False

    def cursor(self):
        return FauxCurseur(self)

    def commit(self):
        self.commit_effectue = True

    def rollback(self):
        self.rollback_effectue = True

    def close(self):
        pass


@pytest.fixture
def resultat_olist(ingestion_olist, racine_brute):
    return controler("olist", INGESTION_OLIST, racine_brute)


@pytest.fixture
def faux_execute_values(monkeypatch):
    appels = []

    def enregistrer(curseur, requete, lignes, page_size):
        appels.append(lignes)
        curseur.connexion.journal.append(("execute_values", "INSERT INTO quarantaine.rejets"))

    monkeypatch.setattr("quality.quarantaine.execute_values", enregistrer)
    return appels


# --- Préparation ----------------------------------------------------------------


def test_les_colonnes_de_staging_couvrent_les_tables_de_chaque_source():
    for tables in TABLES_PAR_SOURCE.values():
        assert set(tables) <= set(COLONNES_STAGING)


def test_les_rejets_suivent_le_contrat_de_quarantaine(resultat_olist):
    rejets = preparer_rejets(resultat_olist)
    commandes = [r for r in rejets if r["regle"] == "OLIST_COMMANDES_02"]

    assert len(commandes) == NB_LIVREES_SANS_DATE
    premier = commandes[0]
    assert premier["source"] == "olist"
    assert premier["ingestion"] == INGESTION_OLIST
    assert premier["fichier"] == "orders.csv"
    assert premier["gravite"] == "bloquante"
    # o01 est le premier enregistrement du fichier, en-tête exclu
    assert premier["ligne_origine"] == 1
    assert premier["donnees_brutes"]["order_id"] == "o01"
    # une cellule vide devient un vrai null JSON, pas NaN
    assert premier["donnees_brutes"]["order_delivered_customer_date"] is None
    json.dumps(premier["donnees_brutes"], allow_nan=False)


def test_la_ligne_d_origine_suit_l_enregistrement_a_travers_les_filtres(resultat_olist):
    rejets = preparer_rejets(resultat_olist)
    (avis_02,) = [r for r in rejets if r["regle"] == "OLIST_AVIS_02"]

    # r03 est le 4e enregistrement de order_reviews.csv
    assert avis_02["donnees_brutes"]["review_id"] == "r03"
    assert avis_02["ligne_origine"] == 4


def test_le_message_du_journal_detaille_chaque_regle(resultat_olist):
    message = json.loads(message_journal(resultat_olist, 11, 0))

    assert message["ingestion"] == INGESTION_OLIST
    assert message["lignes_supprimees"] == 1
    assert len(message["controles"]) == 10  # dont OLIST_ARTICLES_02


def test_un_resultat_incomplet_est_refuse(resultat_olist):
    del resultat_olist.valides["olist_order_reviews"]

    with pytest.raises(ValueError, match="olist_order_reviews"):
        verifier_tables(resultat_olist)


# --- La transaction -----------------------------------------------------------


def test_la_transaction_vide_copie_met_en_quarantaine_journalise_puis_valide(
    resultat_olist, faux_execute_values
):
    connexion = FausseConnexion()

    bilan = charger(resultat_olist, connexion=connexion)

    etapes = [genre for genre, _ in connexion.journal]
    assert connexion.journal[0][1].startswith("TRUNCATE staging.olist_customers")
    assert etapes.count("copy") == 9  # une table par copie, inchangé
    assert etapes.index("execute_values") > max(i for i, e in enumerate(etapes) if e == "copy")
    assert "INSERT INTO staging.execution_log" in connexion.journal[-1][1]
    assert connexion.commit_effectue is True
    assert bilan.rejets_inseres == resultat_olist.lignes_rejetees
    assert bilan.execution_id == 42
    # les 8 commandes rejetées ne sont pas dans la copie de staging.olist_orders
    copie_commandes = connexion.copies["staging.olist_orders"]
    assert all(f"o{i:02d}," not in copie_commandes for i in range(1, NB_LIVREES_SANS_DATE + 1))


def test_une_panne_annule_tout_le_chargement(resultat_olist, faux_execute_values):
    connexion = FausseConnexion(echouer_au_journal=True)

    with pytest.raises(RuntimeError):
        charger(resultat_olist, connexion=connexion)

    assert connexion.rollback_effectue is True
    assert connexion.commit_effectue is False


def test_les_rejets_deja_enregistres_pour_l_ingestion_ne_sont_pas_reinseres(
    resultat_olist, faux_execute_values
):
    connexion = FausseConnexion(regles_deja_presentes=["OLIST_COMMANDES_02"])

    bilan = charger(resultat_olist, connexion=connexion)

    (lignes,) = faux_execute_values
    regles_inserees = {ligne[4] for ligne in lignes}
    assert "OLIST_COMMANDES_02" not in regles_inserees
    assert bilan.rejets_deja_presents == NB_LIVREES_SANS_DATE
    assert bilan.rejets_inseres == resultat_olist.lignes_rejetees - NB_LIVREES_SANS_DATE
    # le journal compte toujours les rejets détectés par cette exécution
    assert bilan.lignes_rejetees == resultat_olist.lignes_rejetees


def test_sans_validation_la_transaction_reste_a_l_appelant(resultat_olist, faux_execute_values):
    connexion = FausseConnexion()

    charger(resultat_olist, connexion=connexion, valider=False)

    assert connexion.commit_effectue is False
    assert connexion.rollback_effectue is False
