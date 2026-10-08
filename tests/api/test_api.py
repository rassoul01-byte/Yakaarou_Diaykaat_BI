"""L'API de la démo : les trois endpoints, sans Elasticsearch.

La recherche est remplacée par un faux retrouveur : on teste le contrat HTTP
(codes, formes, erreurs), pas la qualité de la recherche.
"""

import pytest
from fastapi.testclient import TestClient

import api.main as principal
from assistant.garde_fous import Seuils
from assistant.journal import JournalMemoire
from assistant.passages import ErreurCorpus, Passage
from assistant.retrouveur import ReponseContratInvalide

client = TestClient(principal.app, raise_server_exceptions=False)


class FauxRetrouveur:
    nom = "faux"
    seuils = Seuils(reponse=0.8, suggestion=0.3, marge=0.0)

    def __init__(self, passages=()):
        self.passages = list(passages)

    def retrouver(self, question, k=3):
        return self.passages[:k]


@pytest.fixture(autouse=True)
def _journal_en_memoire(monkeypatch):
    """Les tests n'écrivent jamais le vrai journal, que l'API le branche ou non."""
    monkeypatch.setattr(
        principal, "JournalFichier", lambda *a, **k: JournalMemoire(), raising=False
    )


def passage(id_="liv-03", score=0.9):
    return Passage(
        id_, "livraison", "Comment suivre ma commande ?", "Voir la rubrique commandes.",
        "politique:livraison", score,
    )  # fmt: skip


def avec_retrouveur(monkeypatch, retrouveur):
    monkeypatch.setattr(principal, "creer_retrouveur", lambda: retrouveur)


def test_sante():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_assistant_repond_avec_sa_source(monkeypatch):
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.95)]))
    r = client.post("/api/assistant/ask", json={"question": "Comment suivre ma commande ?"})
    assert r.status_code == 200
    corps = r.json()
    assert corps["refus"] is False
    assert corps["motif"] is None
    assert [p["id"] for p in corps["passages"]] == ["liv-03"]
    assert corps["passages"][0]["source"] == "politique:livraison"


def test_assistant_refuse_un_prix_sans_rien_citer(monkeypatch):
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.95)]))
    r = client.post("/api/assistant/ask", json={"question": "Combien coûte un canapé ?"})
    assert r.status_code == 200
    corps = r.json()
    assert corps["refus"] is True
    assert corps["passages"] == []
    assert corps["motif"]


def test_assistant_refuse_hors_base_sans_rien_citer(monkeypatch):
    avec_retrouveur(monkeypatch, FauxRetrouveur([]))
    r = client.post("/api/assistant/ask", json={"question": "Quel temps fait-il demain ?"})
    assert r.status_code == 200
    assert r.json()["refus"] is True
    assert r.json()["passages"] == []


def test_assistant_refus_avec_suggestions(monkeypatch):
    """Un refus qui hésite propose des suggestions : l'API doit les renvoyer, pas planter."""
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.5)]))
    r = client.post("/api/assistant/ask", json={"question": "Où est mon colis ?"})
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["refus"] is True
    assert [s["id"] for s in corps["suggestions"]] == ["liv-03"]


@pytest.mark.parametrize(
    "corps",
    [{"question": ""}, {"question": "x" * 501}, {"question": "ok", "k": 0}, {"question": "ok", "k": 11}, {}],
)  # fmt: skip
def test_assistant_valide_ses_entrees(corps):
    assert client.post("/api/assistant/ask", json=corps).status_code == 422


@pytest.mark.parametrize(
    "erreur, code",
    [
        (ErreurCorpus("illisible"), 500),
        (ConnectionError("injoignable"), 503),
        (ReponseContratInvalide("hors contrat"), 502),
    ],
)
def test_assistant_traduit_les_pannes_en_codes_http(monkeypatch, erreur, code):
    def panne():
        raise erreur

    monkeypatch.setattr(principal, "creer_retrouveur", panne)
    r = client.post("/api/assistant/ask", json={"question": "Comment suivre ma commande ?"})
    assert r.status_code == code
    assert "detail" in r.json()


def test_recherche_renvoie_le_resultat_de_la_recherche(monkeypatch):
    attendu = {"question_posee": "colis", "resultats": []}
    monkeypatch.setattr(principal, "connexion", lambda: object())
    monkeypatch.setattr(principal, "rechercher", lambda client_es, q, k: attendu)
    r = client.post("/api/recherche", json={"q": "colis"})
    assert r.status_code == 200
    assert r.json() == attendu


def test_recherche_elasticsearch_injoignable_donne_503(monkeypatch):
    def panne():
        raise ConnectionError("down")

    monkeypatch.setattr(principal, "connexion", panne)
    assert client.post("/api/recherche", json={"q": "colis"}).status_code == 503


@pytest.mark.parametrize("corps", [{"q": ""}, {"q": "x" * 301}, {"q": "ok", "k": 21}, {}])
def test_recherche_valide_ses_entrees(corps):
    assert client.post("/api/recherche", json=corps).status_code == 422
