"""`GET /api/indicateurs` : le contrat HTTP, sans PostgreSQL.

La lecture des vues et le calcul de l'alerte sont remplacés par des faux : on
teste la forme de la réponse, les codes d'erreur et la validation des
paramètres, pas le contenu des vues. Leur couverture vit dans
tests/indicateurs/ et tests/integration/.
"""

import psycopg2
import pytest
from fastapi.testclient import TestClient

import api.main as principal
from api.routers import indicateurs as router_indicateurs
from compteurs.alerte import Verdict

client = TestClient(principal.app, raise_server_exceptions=False)


def donnees_completes() -> dict:
    """Une réponse plausible, aux vraies valeurs du projet."""
    return {
        "ventes": {
            "chiffre_affaires": 13493151.56,
            "commandes": 98191,
            "articles": 112650,
            "panier_moyen": 137.42,
            "premier_jour": "2016-09-04",
            "dernier_jour": "2018-10-17",
        },
        "categories": [
            {
                "categorie": "beleza_saude",
                "chiffre_affaires": 1255695.13,
                "articles": 9465,
                "commandes": 8836,
            }
        ],
        "qualite": {
            "sources": 3,
            "lignes_lues": 1730645,
            "lignes_rejetees": 1073,
            "taux_rejet_pourcent": 0.062,
        },
        "motifs_de_rejet": [{"regle": "prix_positif", "gravite": "bloquant", "rejets": 412}],
        "jour": {
            "jour": "2026-10-08",
            "sessions": 3638,
            "pages_vues": 16102,
            "recherches": 5699,
            "ajouts_panier": 884,
            "achats": 233,
            "sessions_avec_achat": 219,
            "taux_conversion_pourcent": 6.02,
        },
        "achats_par_heure": [{"heure": h, "achats": 0} for h in range(24)],
        "segment": {"clients": 711, "date_reference": "2017-09-30"},
        "chaine": [
            {
                "pipeline": "qualite",
                "etape": "controle",
                "source": "olist_commandes",
                "duree_secondes": 64.0,
                "lignes_lues": 99441,
                "lignes_rejetees": 412,
                "statut": "succes",
                "demarre_a": "2026-10-08T21:52:03+00:00",
            }
        ],
    }


def donnees_vides() -> dict:
    """Ce que renvoie une base montée mais jamais chargée."""
    return {
        "ventes": None,
        "categories": [],
        "qualite": None,
        "motifs_de_rejet": [],
        "jour": None,
        "achats_par_heure": [],
        "segment": None,
        "chaine": [],
    }


def avec(monkeypatch, donnees=None, alertes=()):
    monkeypatch.setattr(
        router_indicateurs,
        "collecter_pour_la_page",
        lambda **_: donnees if donnees is not None else donnees_completes(),
    )
    monkeypatch.setattr(router_indicateurs, "collecter_alertes", lambda **_: list(alertes))


def verdict(achats=233, habituels=1433.3, jours_compares=4, heure=22):
    from datetime import date

    return Verdict(
        jour=date(2026, 10, 8),
        achats=achats,
        habituels=habituels,
        jours_compares=jours_compares,
        heure=heure,
    )


# --------------------------------------------------------------- forme


def test_renvoie_les_blocs_de_la_page(monkeypatch):
    avec(monkeypatch)
    r = client.get("/api/indicateurs")
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["ventes"]["chiffre_affaires"] == 13493151.56
    assert corps["ventes"]["panier_moyen"] == 137.42
    assert corps["categories"][0]["categorie"] == "beleza_saude"
    assert corps["qualite"]["taux_rejet_pourcent"] == 0.062
    assert corps["jour"]["achats"] == 233
    assert corps["segment"]["clients"] == 711
    assert corps["chaine"][0]["statut"] == "succes"


def test_le_drapeau_trafic_simule_est_toujours_vrai(monkeypatch):
    """La page ne doit pas pouvoir afficher les compteurs sans la mention."""
    avec(monkeypatch)
    assert client.get("/api/indicateurs").json()["trafic_simule"] is True


def test_les_vingt_quatre_heures_sont_renvoyees(monkeypatch):
    """Un axe qui saute de 3 h à 7 h mentirait sur la forme de la journée."""
    avec(monkeypatch)
    heures = client.get("/api/indicateurs").json()["achats_par_heure"]
    assert [h["heure"] for h in heures] == list(range(24))


# --------------------------------------------------------------- base vide


def test_une_base_vide_donne_200_et_des_blocs_nuls(monkeypatch):
    """Pas encore de données n'est pas une panne : la page doit pouvoir le dire."""
    avec(monkeypatch, donnees=donnees_vides())
    r = client.get("/api/indicateurs")
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["ventes"] is None
    assert corps["jour"] is None
    assert corps["segment"] is None
    assert corps["categories"] == []
    assert corps["chaine"] == []


# --------------------------------------------------------------- alerte


def test_sans_journee_signalee_l_alerte_est_nulle(monkeypatch):
    avec(monkeypatch, alertes=[verdict(achats=1400)])
    assert client.get("/api/indicateurs").json()["alerte"] is None


def test_une_journee_sous_le_seuil_remonte_avec_son_seuil(monkeypatch):
    avec(monkeypatch, alertes=[verdict()])
    alerte = client.get("/api/indicateurs").json()["alerte"]
    assert alerte is not None
    assert alerte["jour"] == "2026-10-08"
    assert alerte["achats"] == 233
    assert alerte["achats_habituels"] == 1433.3
    assert alerte["niveau_pourcent"] == 16.3
    assert alerte["seuil_pourcent"] == 60.0
    assert alerte["declenchee"] is True
    assert "seuil" in alerte["message"]


def test_la_journee_signalee_la_plus_recente_gagne(monkeypatch):
    """Une chute passée inaperçue reste une chute, mais on affiche la dernière."""
    from datetime import date

    ancienne = Verdict(date(2026, 10, 1), 200, 1400.0, 4, 23)
    recente = Verdict(date(2026, 10, 8), 233, 1433.3, 4, 22)
    avec(monkeypatch, alertes=[recente, ancienne])
    assert client.get("/api/indicateurs").json()["alerte"]["jour"] == "2026-10-08"


def test_avant_midi_rien_n_est_signale(monkeypatch):
    """La règle de `compteurs.alerte` vaut aussi par l'API : une matinée est
    toujours incomplète."""
    avec(monkeypatch, alertes=[verdict(heure=9)])
    assert client.get("/api/indicateurs").json()["alerte"] is None


# --------------------------------------------------------------- paramètres


def test_les_parametres_sont_transmis_a_la_lecture(monkeypatch):
    appels: list[dict] = []

    def capturer(**options):
        appels.append(options)
        return donnees_completes()

    monkeypatch.setattr(router_indicateurs, "collecter_pour_la_page", capturer)
    monkeypatch.setattr(router_indicateurs, "collecter_alertes", lambda **_: [])

    r = client.get("/api/indicateurs", params={"top": 15, "motifs": 3})
    assert r.status_code == 200
    assert appels == [{"top": 15, "motifs": 3}]


def test_l_heure_est_transmise_a_l_alerte(monkeypatch):
    """Rejouer une situation : `?heure=14` doit arriver jusqu'au verdict."""
    appels: list[dict] = []

    def capturer(**options):
        appels.append(options)
        return []

    monkeypatch.setattr(
        router_indicateurs, "collecter_pour_la_page", lambda **_: donnees_completes()
    )
    monkeypatch.setattr(router_indicateurs, "collecter_alertes", capturer)

    assert client.get("/api/indicateurs", params={"heure": 14}).status_code == 200
    assert appels[0]["heure"] == 14


@pytest.mark.parametrize(
    "parametres",
    [
        {"top": 0},
        {"top": 31},
        {"motifs": 0},
        {"motifs": 21},
        {"heure": -1},
        {"heure": 24},
    ],
)
def test_valide_ses_parametres(parametres):
    assert client.get("/api/indicateurs", params=parametres).status_code == 422


# --------------------------------------------------------------- pannes


def test_postgres_injoignable_donne_503(monkeypatch):
    def panne(**_):
        raise psycopg2.OperationalError("could not connect to server")

    monkeypatch.setattr(router_indicateurs, "collecter_pour_la_page", panne)
    r = client.get("/api/indicateurs")
    assert r.status_code == 503
    assert "PostgreSQL injoignable" in r.json()["detail"]


def test_une_vue_absente_donne_502(monkeypatch):
    """La base répond, mais la migration n'a pas été appliquée : ce n'est pas
    une panne réseau, et le message doit le distinguer."""

    def panne(**_):
        raise psycopg2.errors.UndefinedTable('relation "dwh.v_ventes_totales" does not exist')

    monkeypatch.setattr(router_indicateurs, "collecter_pour_la_page", panne)
    r = client.get("/api/indicateurs")
    assert r.status_code == 502
    assert "Lecture des indicateurs impossible" in r.json()["detail"]


def test_une_panne_de_l_alerte_est_aussi_traduite(monkeypatch):
    """L'alerte ouvre sa propre connexion : elle peut tomber seule."""
    monkeypatch.setattr(
        router_indicateurs, "collecter_pour_la_page", lambda **_: donnees_completes()
    )

    def panne(**_):
        raise psycopg2.OperationalError("down")

    monkeypatch.setattr(router_indicateurs, "collecter_alertes", panne)
    assert client.get("/api/indicateurs").status_code == 503
