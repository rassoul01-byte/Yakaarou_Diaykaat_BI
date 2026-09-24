"""Tests du bus d'événements.

Les premiers tests remplacent Kafka par un faux producteur qui enregistre ce
qu'on lui envoie : ils vérifient l'aiguillage entre sujet principal et rebut,
sans aucun service démarré.

Les tests marqués « integration » font un véritable aller-retour avec Kafka.
Ils se lancent avec :  docker compose exec app python -m pytest -m integration
"""

import json
import uuid

import pytest

from common.bus import Publieur, consommer, creer_sujets
from common.evenements import (
    SUJET_EVENEMENTS,
    SUJET_REBUT,
    SUJET_REJEU,
    nouvel_evenement,
)


class FauxProducteur:
    """Remplace le producteur Kafka : garde les messages au lieu de les envoyer."""

    def __init__(self):
        self.envois = []

    def produce(self, sujet, key=None, value=None, on_delivery=None):
        self.envois.append(
            {
                "sujet": sujet,
                "cle": key.decode() if key else None,
                "valeur": json.loads(value),
            }
        )

    def poll(self, delai):
        return 0

    def flush(self, delai):
        return 0


@pytest.fixture
def faux():
    return FauxProducteur()


def test_un_evenement_valide_part_sur_le_sujet_principal_avec_la_session_pour_cle(faux):
    evt = nouvel_evenement("recherche", "s-42", requete="lampe")
    assert Publieur(producteur=faux).publier(evt) is True
    assert faux.envois == [{"sujet": SUJET_EVENEMENTS, "cle": "s-42", "valeur": evt}]


def test_un_evenement_invalide_part_au_rebut_avec_ses_motifs(faux):
    evt = nouvel_evenement("page_vue", "s-42")  # une page vue sans produit
    publieur = Publieur(producteur=faux)

    assert publieur.publier(evt) is False
    (envoi,) = faux.envois
    assert envoi["sujet"] == SUJET_REBUT
    assert envoi["cle"] == "s-42"
    assert "id_produit obligatoire pour un événement page_vue" in envoi["valeur"]["motifs"]
    assert envoi["valeur"]["evenement_brut"] == evt
    assert "recu_le" in envoi["valeur"]
    assert (publieur.publies, publieur.rebutes) == (0, 1)


def test_un_texte_qui_n_est_pas_du_json_part_au_rebut(faux):
    assert Publieur(producteur=faux).publier("{ceci n'est pas du json") is False
    (envoi,) = faux.envois
    assert envoi["sujet"] == SUJET_REBUT
    assert envoi["cle"] is None
    assert envoi["valeur"]["evenement_brut"] == "{ceci n'est pas du json"


def test_un_evenement_valide_ecrit_en_json_est_publie(faux):
    evt = nouvel_evenement("recherche", "s-7", requete="table basse")
    assert Publieur(producteur=faux).publier(json.dumps(evt)) is True
    assert faux.envois[0]["sujet"] == SUJET_EVENEMENTS


def test_le_sujet_principal_peut_etre_celui_du_rejeu(faux):
    evt = nouvel_evenement("recherche", "s-7", requete="table basse")
    Publieur(producteur=faux, sujet_principal=SUJET_REJEU).publier(evt)
    assert faux.envois[0]["sujet"] == SUJET_REJEU


def test_les_compteurs_suivent_les_publications(faux):
    publieur = Publieur(producteur=faux)
    publieur.publier(nouvel_evenement("recherche", "s-1", requete="x"))
    publieur.publier(nouvel_evenement("recherche", "s-1", requete="y"))
    publieur.publier(nouvel_evenement("achat", "s-1"))  # achat sans client : rebut
    assert (publieur.publies, publieur.rebutes) == (2, 1)


# --- Aller-retour réel avec Kafka --------------------------------------------


def _chercher(sujet: str, trouve) -> object | None:
    """Relit un sujet depuis le début avec un groupe neuf, jusqu'à trouver le message voulu."""
    groupe = f"test-{uuid.uuid4()}"
    for message in consommer(sujet, groupe, arret_apres_inactivite=10):
        if trouve(message.valeur):
            return message
    return None


@pytest.mark.integration
def test_aller_retour_reel_sur_le_sujet_principal():
    creer_sujets()
    evt = nouvel_evenement("recherche", f"s-test-{uuid.uuid4()}", requete="aller-retour")
    with Publieur() as publieur:
        assert publieur.publier(evt)

    message = _chercher(
        SUJET_EVENEMENTS,
        lambda v: isinstance(v, dict) and v.get("id_evenement") == evt["id_evenement"],
    )
    assert message is not None, "l'événement publié n'a pas été relu"
    assert message.cle == evt["id_session"]
    assert message.valeur == evt


@pytest.mark.integration
def test_aller_retour_reel_vers_le_rebut():
    creer_sujets()
    evt = nouvel_evenement("page_vue", f"s-test-{uuid.uuid4()}")  # sans produit
    with Publieur() as publieur:
        assert not publieur.publier(evt)

    message = _chercher(
        SUJET_REBUT,
        lambda v: (
            isinstance(v, dict)
            and isinstance(v.get("evenement_brut"), dict)
            and v["evenement_brut"].get("id_evenement") == evt["id_evenement"]
        ),
    )
    assert message is not None, "l'événement refusé n'a pas été retrouvé dans le rebut"
    assert "id_produit obligatoire pour un événement page_vue" in message.valeur["motifs"]


@pytest.mark.integration
def test_creer_les_sujets_deux_fois_ne_produit_aucune_erreur():
    creer_sujets()
    assert set(creer_sujets().values()) == {"existe déjà"}
