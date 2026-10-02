"""Tests du service référentiel.

Aucun test ne sort sur Internet : les appels aux services publics passent par
un transport remplaçable, et l'API est interrogée sur une zone brute d'essai.
"""

from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from referentiel import api, depot
from referentiel.sources import recuperer_feries, recuperer_taux

FERIES_2017 = [
    {"date": "2017-01-01", "name": "Confraternização mundial", "type": "national"},
    {"date": "2017-02-28", "name": "Carnaval", "type": "national"},
    {"date": "2017-12-25", "name": "Natal", "type": "national"},
]

TAUX = {
    "base": "BRL",
    "rates": {
        "2017-03-14": {"EUR": 0.3011},
        "2017-03-15": {"EUR": 0.3024},
        "2017-03-16": {"EUR": 0.3038},
    },
}


@pytest.fixture
def zone_brute(tmp_path):
    """Une zone brute d'essai, remplie comme le ferait le script d'alimentation."""
    depot.ecrire(depot.chemin_feries(2017, tmp_path), FERIES_2017)
    depot.ecrire(depot.chemin_taux(date(2017, 3, 14), date(2017, 3, 16), "EUR", tmp_path), TAUX)
    return tmp_path


@pytest.fixture
def service(zone_brute):
    api.recharger(zone_brute)
    return TestClient(api.app)


# --- Les appels aux services publics ----------------------------------------


def test_les_feries_sont_recuperes_tels_quels():
    appels = []

    def faux_transport(url, parametres=None):
        appels.append(url)
        return FERIES_2017

    assert recuperer_feries(2017, transport=faux_transport) == FERIES_2017
    assert "2017" in appels[0]


def test_une_reponse_inattendue_sur_les_feries_est_refusee():
    with pytest.raises(ValueError, match="réponse inattendue"):
        recuperer_feries(2017, transport=lambda url, parametres=None: {"erreur": "indisponible"})


def test_les_taux_sont_demandes_en_reals_vers_la_devise():
    recus = {}

    def faux_transport(url, parametres=None):
        recus.update(parametres or {})
        return TAUX

    recuperer_taux(date(2017, 3, 14), date(2017, 3, 16), "EUR", transport=faux_transport)

    assert recus == {"base": "BRL", "symbols": "EUR"}


def test_une_reponse_sans_taux_est_refusee():
    with pytest.raises(ValueError, match="réponse inattendue"):
        recuperer_taux(date(2017, 1, 1), date(2017, 1, 2), transport=lambda u, p=None: {"vide": 1})


# --- La zone brute ----------------------------------------------------------


def test_ce_qui_est_conserve_est_relu_a_l_identique(zone_brute):
    assert depot.charger_feries(zone_brute) == {2017: FERIES_2017}
    assert depot.charger_taux(zone_brute)["EUR"]["2017-03-15"] == 0.3024


def test_une_zone_brute_vide_ne_fait_pas_echouer_le_service(tmp_path):
    assert depot.charger_feries(tmp_path) == {}
    assert depot.charger_taux(tmp_path) == {}


# --- Le service -------------------------------------------------------------


def test_la_sante_annonce_ce_qui_est_disponible(service):
    sante = service.get("/sante").json()

    assert sante["etat"] == "ok"
    assert sante["annees_feries"] == [2017]
    assert sante["taux_par_devise"] == {"EUR": 3}


def test_les_feries_d_une_annee_sont_servis(service):
    reponse = service.get("/feries/2017")

    assert reponse.status_code == 200
    assert reponse.json()["nombre"] == 3
    assert reponse.json()["feries"][1]["name"] == "Carnaval"


def test_une_annee_absente_renvoie_404_avec_la_marche_a_suivre(service):
    reponse = service.get("/feries/2020")

    assert reponse.status_code == 404
    assert "alimenter_referentiel" in reponse.json()["detail"]


def test_le_taux_d_un_jour_ouvre_est_celui_du_jour(service):
    reponse = service.get("/taux", params={"date": "2017-03-15"}).json()

    assert reponse["taux"] == 0.3024
    assert reponse["date_effective"] == "2017-03-15"


def test_un_jour_sans_cotation_retombe_sur_le_dernier_jour_ouvre(service):
    # Les services de change ne publient rien le week-end : on prend la veille,
    # et on dit laquelle.
    reponse = service.get("/taux", params={"date": "2017-03-18"}).json()

    assert reponse["taux"] == 0.3038
    assert reponse["date_effective"] == "2017-03-16"
    assert reponse["date_demandee"] == "2017-03-18"


def test_une_date_anterieure_a_tout_ce_qui_est_conserve_renvoie_404(service):
    assert service.get("/taux", params={"date": "2015-01-01"}).status_code == 404


def test_une_devise_inconnue_renvoie_404(service):
    assert service.get("/taux", params={"date": "2017-03-15", "devise": "XOF"}).status_code == 404


# --- Le client utilisé par les autres modules -------------------------------


def test_le_client_renvoie_des_dates_pretes_pour_la_dimension_temps(service, monkeypatch):
    from referentiel import client

    monkeypatch.setenv("REFERENTIEL_URL", "http://test")
    faux = httpx.Client(transport=httpx.MockTransport(lambda r: _repondre(service, r)))

    feries = client.jours_feries(2017, client=faux)

    assert feries == [date(2017, 1, 1), date(2017, 2, 28), date(2017, 12, 25)]


def test_le_client_convertit_un_montant_a_la_date_de_la_commande(service, monkeypatch):
    from referentiel import client

    monkeypatch.setenv("REFERENTIEL_URL", "http://test")
    faux = httpx.Client(transport=httpx.MockTransport(lambda r: _repondre(service, r)))

    assert client.taux_du_jour(date(2017, 3, 15), client=faux) == 0.3024


def _repondre(service, requete: httpx.Request) -> httpx.Response:
    """Fait suivre l'appel du client au service, sans réseau."""
    reponse = service.get(requete.url.path, params=dict(requete.url.params))
    return httpx.Response(reponse.status_code, json=reponse.json())
