"""Tests des compteurs du jour.

Le point sensible : le bus garantit qu'un message arrive **au moins** une fois.
Un même événement peut donc être reçu deux fois, et les compteurs ne doivent
pas le compter deux fois. Cette garantie est portée par la clé primaire de la
table ; ici, on vérifie que rien dans le code ne la contourne.
"""

from datetime import datetime

import pytest

from compteurs.consommateur import CHAMPS, GROUPE, en_ligne


def evenement(
    identifiant="e-1",
    type_="page_vue",
    horodatage="2026-09-01T10:15:03.412Z",
    session="s-000123",
    client=None,
    produit="1234",
    requete=None,
):
    return {
        "version_contrat": 1,
        "id_evenement": identifiant,
        "type": type_,
        "horodatage": horodatage,
        "id_session": session,
        "customer_unique_id": client,
        "id_produit": produit,
        "requete": requete,
    }


# --- La transformation en ligne ---------------------------------------------


def test_un_evenement_valide_donne_une_ligne_complete():
    ligne = en_ligne(evenement())

    assert ligne is not None
    assert len(ligne) == len(CHAMPS)
    assert ligne[0] == "e-1"


def test_l_horodatage_est_lu_avec_son_fuseau():
    ligne = en_ligne(evenement(horodatage="2026-09-01T10:15:03.412Z"))

    assert ligne[2] == datetime.fromisoformat("2026-09-01T10:15:03.412+00:00")


def test_le_jour_est_deduit_de_l_horodatage():
    # C'est lui qui regroupe les compteurs, pas la date de réception.
    assert en_ligne(evenement(horodatage="2026-09-01T23:59:00Z"))[3].isoformat() == "2026-09-01"


def test_un_achat_conserve_son_client():
    ligne = en_ligne(evenement(type_="achat", client="a" * 32, produit=None))

    assert ligne[1] == "achat"
    assert ligne[5] == "a" * 32


def test_une_recherche_conserve_sa_requete():
    ligne = en_ligne(evenement(type_="recherche", produit=None, requete="chaise de bureu"))

    assert ligne[7] == "chaise de bureu"


# --- Ce qui est ignoré ------------------------------------------------------


@pytest.mark.parametrize(
    "manquant",
    ["id_evenement", "type", "horodatage", "id_session"],
    ids=["sans identifiant", "sans type", "sans horodatage", "sans session"],
)
def test_un_evenement_incomplet_est_ignore(manquant):
    # Ignoré, pas rejeté : le rebut est le travail du bus, pas des compteurs.
    incomplet = evenement()
    incomplet[manquant] = None

    assert en_ligne(incomplet) is None


def test_un_horodatage_illisible_est_ignore():
    assert en_ligne(evenement(horodatage="hier matin")) is None


def test_un_message_qui_n_est_pas_un_objet_est_ignore():
    assert en_ligne("ceci n'est pas un événement") is None
    assert en_ligne(None) is None


# --- Le nom du groupe -------------------------------------------------------


def test_le_groupe_de_lecture_porte_un_nom_stable():
    # C'est ce nom qu'affiche la surveillance du retard du flux : le changer
    # ferait repartir la lecture de zéro et perdrait l'historique de retard.
    assert GROUPE == "compteurs-du-jour"
