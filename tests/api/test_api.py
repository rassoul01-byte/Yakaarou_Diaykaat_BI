"""L'API de la démo : les trois endpoints, sans Elasticsearch.

La recherche est remplacée par un faux moteur : on teste le contrat HTTP
(codes, formes, erreurs), pas la qualité de la recherche.
"""

import json
import os
from pathlib import Path

import pytest
from elastic_transport import ConnectionError as EsConnectionError
from elastic_transport import ConnectionTimeout
from fastapi.testclient import TestClient

import api.main as principal
from api.routers import assistant as router_assistant
from api.routers import recherche as router_recherche
from assistant.garde_fous import Seuils
from assistant.passages import ErreurCorpus, Passage
from assistant.retrouveur import ReponseContratInvalide
from recherche.moteur import Reponse, Resultat

client = TestClient(principal.app, raise_server_exceptions=False)


class FauxRetrouveur:
    nom = "faux"
    seuils = Seuils(reponse=0.8, suggestion=0.3, marge=0.0)

    def __init__(self, passages=()):
        self.passages = list(passages)

    def retrouver(self, question, k=3):
        return self.passages[:k]


def passage(id_="liv-03", score=0.9):
    return Passage(
        id_,
        "livraison",
        "Comment suivre ma commande ?",
        "Voir la rubrique commandes.",
        "politique:livraison",
        score,
    )  # fmt: skip


@pytest.fixture(autouse=True)
def _client_es_neuf():
    """Le client Elasticsearch du router est mis en cache pour toute la durée
    du service. En test, chacun doit repartir d'un client neuf, sinon le
    premier qui l'obtient le fige pour les suivants.

    Vidé à l'entrée seulement : à la sortie, `client_es` peut encore être le
    remplaçant posé par un `monkeypatch` que pytest n'a pas défait.
    """
    router_recherche.client_es.cache_clear()


def avec_retrouveur(monkeypatch, retrouveur):
    monkeypatch.setattr(router_assistant, "creer_retrouveur", lambda: retrouveur)


def faux_moteur(resultats=None, total=0, temps_ms=10):
    """Fabrique une fonction `rechercher` compatible avec l'API."""
    resultats = resultats or []

    def _rechercher(client_es, texte, **options):
        return Reponse(
            texte=texte,
            resultats=resultats,
            total=total or len(resultats),
            temps_serveur_ms=temps_ms,
            temps_total_ms=temps_ms,
        )

    return _rechercher


# --------------------------------------------------------------- santé


def test_sante():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# --------------------------------------------------------------- assistant


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
    [
        {"question": ""},
        {"question": "x" * 501},
        {"question": "ok", "k": 0},
        {"question": "ok", "k": 11},
        {"question": "ok", "origine": "ailleurs"},
        {"question": "ok", "reformulation": "x" * 501},
        {},
    ],
)  # fmt: skip
def test_assistant_valide_ses_entrees(corps):
    assert client.post("/api/assistant/ask", json=corps).status_code == 422


# ------------------------------------------------- journal des échanges


def _lignes_du_journal():
    chemin = Path(os.environ["ASSISTANT_JOURNAL"])
    if not chemin.exists():
        return []
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    return [json.loads(ligne) for ligne in lignes if ligne.strip()]


def test_chaque_echange_est_journalise(monkeypatch):
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.95)]))
    client.post("/api/assistant/ask", json={"question": "Comment suivre ma commande ?"})
    lignes = _lignes_du_journal()
    assert len(lignes) == 1
    assert lignes[0]["passages_cites"] == ["liv-03"]
    assert lignes[0]["origine"] == "saisie" and lignes[0]["reformulation"] is None


def test_une_suggestion_cliquee_journalise_la_formulation_du_client(monkeypatch):
    """C'est l'étiquette que le coach demande : ce que le client a écrit, et ce qui l'a servi."""
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.95)]))
    r = client.post(
        "/api/assistant/ask",
        json={
            "question": "Comment suivre ma commande ?",
            "origine": "suggestion",
            "reformulation": "ou en est mon paquet",
        },
    )
    assert r.status_code == 200 and r.json()["refus"] is False
    (ligne,) = _lignes_du_journal()
    assert ligne["origine"] == "suggestion"
    assert ligne["reformulation"] == "ou en est mon paquet"
    assert ligne["passages_cites"] == ["liv-03"]


def test_une_suggestion_cliquee_repond_meme_sous_le_seuil(monkeypatch):
    """Sans ça, un clic peut mener à une seconde hésitation (cas liv-08, score 0,7993)."""
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.2)]))
    r = client.post(
        "/api/assistant/ask",
        json={
            "question": "Comment suivre ma commande ?",
            "origine": "suggestion",
            "reformulation": "ou en est mon paquet",
            "passage": "liv-03",
        },
    )
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["refus"] is False
    assert [p["id"] for p in corps["passages"]] == ["liv-03"]
    assert corps["passages"][0]["score"] == pytest.approx(0.2)


def test_un_passage_inconnu_ne_force_aucune_reponse(monkeypatch):
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.2)]))
    r = client.post(
        "/api/assistant/ask",
        json={"question": "Comment suivre ma commande ?", "passage": "zzz-99"},
    )
    assert r.status_code == 200
    assert r.json()["refus"] is True


def test_un_journal_inecrivable_ne_casse_pas_la_reponse(monkeypatch):
    """Un disque plein est un problème de mesure, pas un problème de service."""
    avec_retrouveur(monkeypatch, FauxRetrouveur([passage(score=0.95)]))
    monkeypatch.setenv("ASSISTANT_JOURNAL", "/proc/interdit/journal.jsonl")
    r = client.post("/api/assistant/ask", json={"question": "Comment suivre ma commande ?"})
    assert r.status_code == 200
    assert r.json()["refus"] is False


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

    monkeypatch.setattr(router_assistant, "creer_retrouveur", panne)
    r = client.post("/api/assistant/ask", json={"question": "Comment suivre ma commande ?"})
    assert r.status_code == code
    assert "detail" in r.json()


# --------------------------------------------------------------- recherche produits


def test_recherche_renvoie_des_fiches_produit(monkeypatch):
    produit = Resultat(
        product_id="1798749064",
        designation="Chaise de bureau",
        categorie_code="1560",
        score=33.9,
    )
    monkeypatch.setattr(router_recherche, "connexion", lambda: object())
    monkeypatch.setattr(router_recherche, "rechercher", faux_moteur([produit], total=402))

    r = client.post("/api/recherche", json={"q": "chaise"})
    assert r.status_code == 200
    corps = r.json()
    assert corps["question_posee"] == "chaise"
    assert corps["total"] == 402
    assert len(corps["produits"]) == 1
    assert corps["produits"][0]["product_id"] == "1798749064"
    assert corps["produits"][0]["designation"] == "Chaise de bureau"
    assert corps["produits"][0]["categorie_code"] == "1560"
    assert corps["produits"][0]["score"] == 33.9


def test_recherche_transmet_les_filtres(monkeypatch):
    """Les filtres catégorie et langue sont bien passés au moteur."""
    appels: list[dict] = []

    def capturer(client_es, texte, **options):
        appels.append({"texte": texte, **options})
        return Reponse(texte=texte, resultats=[], total=0, temps_serveur_ms=5, temps_total_ms=5)

    monkeypatch.setattr(router_recherche, "connexion", lambda: object())
    monkeypatch.setattr(router_recherche, "rechercher", capturer)

    r = client.post(
        "/api/recherche",
        json={"q": "lampe", "k": 5, "categorie": "2060", "langue": "fr"},
    )
    assert r.status_code == 200
    assert len(appels) == 1
    assert appels[0]["texte"] == "lampe"
    assert appels[0]["taille"] == 5
    assert appels[0]["categorie"] == "2060"
    assert appels[0]["langue"] == "fr"


def test_recherche_elasticsearch_injoignable_donne_503(monkeypatch):
    def panne():
        raise ConnectionError("down")

    monkeypatch.setattr(router_recherche, "connexion", panne)
    assert client.post("/api/recherche", json={"q": "colis"}).status_code == 503


def test_une_requete_faite_d_espaces_est_une_entree_invalide_pas_une_panne(monkeypatch):
    """`min_length=1` compte les espaces : sans ce traitement, c'était un 500.

    Le front protège, mais la documentation interactive de l'API est publique
    et c'est le premier bouton qu'un visiteur presse. Le vrai moteur est
    conservé : c'est lui qui refuse la requête, avant tout appel au service.
    """
    monkeypatch.setattr(router_recherche, "client_es", lambda: None)
    assert client.post("/api/recherche", json={"q": "   "}).status_code == 422


@pytest.mark.parametrize(
    "corps",
    [
        {"q": ""},
        {"q": "x" * 301},
        {"q": "ok", "k": 51},
        {},
    ],
)
def test_recherche_valide_ses_entrees(corps):
    assert client.post("/api/recherche", json=corps).status_code == 422


@pytest.mark.parametrize(
    "erreur",
    [EsConnectionError("down"), ConnectionTimeout("lent"), ConnectionError("down")],
    ids=["es-connexion", "es-delai", "connexion-native"],
)
def test_recherche_panne_d_elasticsearch_donne_503_avec_son_message(monkeypatch, erreur):
    """Les erreurs d'Elasticsearch n'héritent pas du ConnectionError natif :
    elles donnaient un 500 sans le `except` dédié."""

    def panne(*_, **__):
        raise erreur

    monkeypatch.setattr(router_recherche, "connexion", lambda: object())
    monkeypatch.setattr(router_recherche, "rechercher", panne)
    r = client.post("/api/recherche", json={"q": "colis"})
    assert r.status_code == 503
    assert "Elasticsearch indisponible" in r.json()["detail"]
