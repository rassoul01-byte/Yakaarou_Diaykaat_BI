"""Tests du contrat d'événement.

Ils n'ont besoin d'aucun service : la validation est une fonction pure.
L'heure de référence est fixée, pour que les tests donnent toujours le même résultat.
"""

from datetime import UTC, datetime

import pytest

from common.evenements import (
    CHAMPS,
    TYPES,
    horodatage_iso,
    lire_horodatage,
    nouvel_evenement,
    valider,
)

MAINTENANT = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
CLIENT = "861eff4711a542e4b93843c6dd7febb0"


def evenement(**modifications) -> dict:
    """Un événement valide de type recherche, modifiable champ par champ."""
    base = {
        "version_contrat": 1,
        "id_evenement": "7f3c2e1a-8b4d-4c21-9f0e-2a6b5d8c1e37",
        "type": "recherche",
        "horodatage": "2026-09-22T10:15:03.412Z",
        "id_session": "s-000123",
        "customer_unique_id": None,
        "id_produit": None,
        "requete": "chaise de bureu ergonomique",
    }
    base.update(modifications)
    return base


def motifs(evt) -> list[str]:
    return valider(evt, maintenant=MAINTENANT)


# --- Les exemples du contrat sont valides ------------------------------------


def test_l_exemple_de_recherche_du_contrat_est_valide():
    assert motifs(evenement()) == []


@pytest.mark.parametrize(
    "type_, champs",
    [
        ("page_vue", {"id_produit": "3804725264", "requete": None}),
        ("ajout_panier", {"id_produit": "3804725264", "requete": None}),
        ("achat", {"customer_unique_id": CLIENT, "requete": None}),
    ],
)
def test_chaque_type_d_evenement_a_une_forme_valide(type_, champs):
    assert motifs(evenement(type=type_, **champs)) == []


def test_un_evenement_construit_par_nouvel_evenement_est_valide():
    evt = nouvel_evenement("page_vue", "s-1", id_produit="42", horodatage=MAINTENANT)
    assert set(evt) == set(CHAMPS)
    assert motifs(evt) == []


def test_deux_evenements_construits_n_ont_pas_le_meme_identifiant():
    a = nouvel_evenement("recherche", "s-1", requete="x")
    b = nouvel_evenement("recherche", "s-1", requete="x")
    assert a["id_evenement"] != b["id_evenement"]


# --- Structure --------------------------------------------------------------


def test_un_message_qui_n_est_pas_un_objet_est_refuse():
    assert motifs(["pas", "un", "objet"]) == ["le message n'est pas un objet JSON"]


def test_un_champ_absent_est_signale():
    evt = evenement()
    del evt["id_session"]
    assert "champ(s) absent(s) : id_session" in motifs(evt)


def test_un_champ_inconnu_est_refuse_pour_attraper_les_fautes_de_frappe():
    evt = evenement()
    evt["horodatge"] = evt.pop("horodatage")
    resultat = motifs(evt)
    assert "champ(s) inconnu(s) : horodatge" in resultat
    assert "champ(s) absent(s) : horodatage" in resultat


def test_tous_les_motifs_sont_signales_pas_seulement_le_premier():
    evt = evenement(type="inconnu", id_session="", id_evenement="pas-un-uuid")
    assert len(motifs(evt)) >= 3


# --- Champs -----------------------------------------------------------------


@pytest.mark.parametrize("version", [2, "1", True])
def test_la_version_du_contrat_doit_valoir_exactement_1(version):
    assert "version_contrat doit valoir 1" in motifs(evenement(version_contrat=version))


def test_un_type_inconnu_est_refuse():
    assert "type inconnu : 'clic'" in motifs(evenement(type="clic"))


def test_les_quatre_types_du_contrat_sont_connus():
    assert TYPES == ("page_vue", "recherche", "ajout_panier", "achat")


def test_un_identifiant_d_evenement_doit_etre_un_uuid():
    assert "id_evenement doit être un UUID" in motifs(evenement(id_evenement="abc"))


@pytest.mark.parametrize("session", ["", "   ", None, 123])
def test_la_session_doit_etre_un_texte_non_vide(session):
    assert "id_session doit être un texte non vide" in motifs(evenement(id_session=session))


def test_un_identifiant_produit_numerique_est_refuse_car_il_doit_etre_du_texte():
    evt = evenement(type="page_vue", id_produit=3804725264, requete=None)
    assert "id_produit doit être du texte, pas un nombre" in motifs(evt)


def test_un_identifiant_produit_non_numerique_est_refuse():
    evt = evenement(type="page_vue", id_produit="AB12", requete=None)
    assert "id_produit ne doit contenir que des chiffres" in motifs(evt)


@pytest.mark.parametrize("client", ["123", "861EFF4711A542E4B93843C6DD7FEBB0", 42])
def test_le_client_doit_avoir_le_format_d_un_customer_unique_id(client):
    attendu = "customer_unique_id doit compter 32 caractères hexadécimaux"
    assert attendu in motifs(evenement(customer_unique_id=client))


# --- Horodatage -------------------------------------------------------------


def test_un_horodatage_sans_fuseau_est_refuse():
    assert "horodatage sans fuseau horaire" in motifs(evenement(horodatage="2026-09-22T10:15:03"))


def test_un_horodatage_illisible_est_refuse():
    assert any("illisible" in m for m in motifs(evenement(horodatage="hier soir")))


def test_un_horodatage_avant_2016_est_refuse():
    assert "horodatage antérieur au 1er janvier 2016" in motifs(
        evenement(horodatage="2015-12-31T23:59:59Z")
    )


def test_un_horodatage_trop_loin_dans_le_futur_est_refuse():
    assert "horodatage plus de 24 heures dans le futur" in motifs(
        evenement(horodatage="2026-09-24T12:00:00Z")
    )


def test_un_horodatage_de_l_historique_olist_est_accepte():
    assert motifs(evenement(horodatage="2017-03-15T14:02:11Z")) == []


def test_un_horodatage_ecrit_par_le_module_suit_le_format_du_contrat():
    texte = horodatage_iso(datetime(2026, 9, 22, 10, 15, 3, 412000, tzinfo=UTC))
    assert texte == "2026-09-22T10:15:03.412Z"
    assert lire_horodatage(texte).tzinfo is not None


# --- Règles propres à chaque type -------------------------------------------


def test_une_recherche_sans_requete_est_refusee():
    assert "requete obligatoire pour un événement recherche" in motifs(evenement(requete="  "))


def test_une_page_vue_sans_produit_est_refusee():
    evt = evenement(type="page_vue", requete=None)
    assert "id_produit obligatoire pour un événement page_vue" in motifs(evt)


def test_une_page_vue_avec_une_requete_est_refusee():
    evt = evenement(type="page_vue", id_produit="42")
    assert "requete doit être null pour un événement page_vue" in motifs(evt)


def test_un_achat_sans_client_identifie_est_refuse():
    evt = evenement(type="achat", requete=None)
    assert "customer_unique_id obligatoire pour un événement achat" in motifs(evt)
