"""Contrat des événements de navigation et leur validation.

Ce module est la traduction exécutable de docs/contrats/evenements.md. Il est
utilisé par tous ceux qui produisent ou lisent des événements : le générateur,
le bus, l'archivage de la zone brute, puis les compteurs du jour.

La validation correspond au niveau 4 de la stratégie de qualité : elle
s'applique à chaque message du flux, avant qu'il n'atteigne un consommateur.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

VERSION_CONTRAT = 1

SUJET_EVENEMENTS = "navigation.evenements"
SUJET_REBUT = "navigation.rebut"
SUJET_REJEU = "navigation.rejeu"

TYPES = ("page_vue", "recherche", "ajout_panier", "achat")

CHAMPS = (
    "version_contrat",
    "id_evenement",
    "type",
    "horodatage",
    "id_session",
    "customer_unique_id",
    "id_produit",
    "requete",
)

# Bornes de plausibilité de l'horodatage : pas avant le début de l'historique
# Olist, pas trop loin dans le futur.
HORODATAGE_MIN = datetime(2016, 1, 1, tzinfo=UTC)
TOLERANCE_FUTUR = timedelta(hours=24)

# Exigences qui dépendent du type d'événement.
OBLIGATOIRE, INTERDIT, FACULTATIF = "obligatoire", "interdit", "facultatif"
REGLES_PAR_TYPE = {
    "page_vue": {"id_produit": OBLIGATOIRE, "requete": INTERDIT, "customer_unique_id": FACULTATIF},
    "recherche": {"id_produit": INTERDIT, "requete": OBLIGATOIRE, "customer_unique_id": FACULTATIF},
    "ajout_panier": {
        "id_produit": OBLIGATOIRE,
        "requete": INTERDIT,
        "customer_unique_id": FACULTATIF,
    },
    "achat": {"id_produit": FACULTATIF, "requete": INTERDIT, "customer_unique_id": OBLIGATOIRE},
}

_FORMAT_CLIENT = re.compile(r"[0-9a-f]{32}")
_FORMAT_PRODUIT = re.compile(r"[0-9]+")


# --------------------------------------------------------------------------- #
# Horodatage
# --------------------------------------------------------------------------- #


def horodatage_iso(moment: datetime | None = None) -> str:
    """Écrit un horodatage au format du contrat : UTC, suffixe Z, millisecondes."""
    moment = moment or datetime.now(UTC)
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def lire_horodatage(texte: str) -> datetime:
    """Lit un horodatage ISO 8601. Lève ValueError s'il est illisible ou sans fuseau."""
    moment = datetime.fromisoformat(texte)
    if moment.tzinfo is None:
        raise ValueError("horodatage sans fuseau horaire")
    return moment


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


def nouvel_evenement(
    type_: str,
    id_session: str,
    *,
    customer_unique_id: str | None = None,
    id_produit: str | None = None,
    requete: str | None = None,
    horodatage: datetime | None = None,
) -> dict:
    """Construit un événement complet : version, identifiant unique et horodatage compris.

    Le résultat n'est pas validé ici : le bus s'en charge au moment de publier.
    """
    return {
        "version_contrat": VERSION_CONTRAT,
        "id_evenement": str(uuid.uuid4()),
        "type": type_,
        "horodatage": horodatage_iso(horodatage),
        "id_session": id_session,
        "customer_unique_id": customer_unique_id,
        "id_produit": id_produit,
        "requete": requete,
    }


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def valider(evenement: object, maintenant: datetime | None = None) -> list[str]:
    """Contrôle un événement contre le contrat.

    Renvoie la liste de TOUS les motifs de refus — une liste vide signifie que
    l'événement est valide. Tous les motifs sont signalés, pas seulement le
    premier, pour que l'analyse du rebut soit utile.

    Le paramètre `maintenant` permet de fixer l'heure de référence, notamment
    dans les tests.
    """
    if not isinstance(evenement, dict):
        return ["le message n'est pas un objet JSON"]

    maintenant = maintenant or datetime.now(UTC)
    motifs: list[str] = []

    inconnus = sorted(set(evenement) - set(CHAMPS))
    if inconnus:
        motifs.append(f"champ(s) inconnu(s) : {', '.join(inconnus)}")
    absents = [champ for champ in CHAMPS if champ not in evenement]
    if absents:
        motifs.append(f"champ(s) absent(s) : {', '.join(absents)}")

    motifs += _controler_champs(evenement, maintenant)
    motifs += _controler_regles_du_type(evenement)
    return motifs


def est_valide(evenement: object) -> bool:
    return not valider(evenement)


def _controler_champs(evt: dict, maintenant: datetime) -> list[str]:
    motifs = []

    if "version_contrat" in evt:
        version = evt["version_contrat"]
        # type() et non isinstance() : en Python, True est un entier et vaut 1.
        if type(version) is not int or version != VERSION_CONTRAT:
            motifs.append(f"version_contrat doit valoir {VERSION_CONTRAT}")

    if "id_evenement" in evt and not _est_uuid(evt["id_evenement"]):
        motifs.append("id_evenement doit être un UUID")

    if "type" in evt and evt["type"] not in TYPES:
        motifs.append(f"type inconnu : {evt['type']!r}")

    if "horodatage" in evt:
        motifs += _controler_horodatage(evt["horodatage"], maintenant)

    if "id_session" in evt:
        session = evt["id_session"]
        if not isinstance(session, str) or not session.strip():
            motifs.append("id_session doit être un texte non vide")

    client = evt.get("customer_unique_id")
    if client is not None and not (isinstance(client, str) and _FORMAT_CLIENT.fullmatch(client)):
        motifs.append("customer_unique_id doit compter 32 caractères hexadécimaux")

    produit = evt.get("id_produit")
    if produit is not None:
        if not isinstance(produit, str):
            motifs.append("id_produit doit être du texte, pas un nombre")
        elif not _FORMAT_PRODUIT.fullmatch(produit):
            motifs.append("id_produit ne doit contenir que des chiffres")

    requete = evt.get("requete")
    if requete is not None and not isinstance(requete, str):
        motifs.append("requete doit être du texte")

    return motifs


def _controler_horodatage(valeur: object, maintenant: datetime) -> list[str]:
    if not isinstance(valeur, str):
        return ["horodatage doit être du texte au format ISO 8601"]
    try:
        moment = lire_horodatage(valeur)
    except ValueError as erreur:
        if "fuseau" in str(erreur):
            return ["horodatage sans fuseau horaire"]
        return [f"horodatage illisible : {valeur!r}"]
    if moment < HORODATAGE_MIN:
        return ["horodatage antérieur au 1er janvier 2016"]
    if moment > maintenant + TOLERANCE_FUTUR:
        return ["horodatage plus de 24 heures dans le futur"]
    return []


def _controler_regles_du_type(evt: dict) -> list[str]:
    type_ = evt.get("type")
    if type_ not in REGLES_PAR_TYPE:
        return []
    motifs = []
    for champ, exigence in REGLES_PAR_TYPE[type_].items():
        valeur = evt.get(champ)
        vide = valeur is None or (isinstance(valeur, str) and not valeur.strip())
        if exigence == OBLIGATOIRE and vide:
            motifs.append(f"{champ} obligatoire pour un événement {type_}")
        elif exigence == INTERDIT and valeur is not None:
            motifs.append(f"{champ} doit être null pour un événement {type_}")
    return motifs


def _est_uuid(valeur: object) -> bool:
    if not isinstance(valeur, str):
        return False
    try:
        uuid.UUID(valeur)
    except ValueError:
        return False
    return True
