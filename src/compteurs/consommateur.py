"""Consommation du bus et alimentation des compteurs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import psycopg2
import psycopg2.extras

from common.config import load_settings
from common.evenements import SUJET_EVENEMENTS

GROUPE = "compteurs-du-jour"
TAILLE_LOT = 200

CHAMPS = (
    "id_evenement",
    "type",
    "horodatage",
    "jour",
    "id_session",
    "customer_unique_id",
    "id_produit",
    "requete",
)

# ON CONFLICT DO NOTHING : un même événement reçu deux fois ne compte qu'une
# fois. Le bus garantit « au moins une fois », pas « exactement une fois » ;
# c'est donc à l'écriture de trancher, et la clé primaire le fait pour nous.
INSERTION = """
    INSERT INTO staging.evenements_du_jour
        (id_evenement, type, horodatage, jour, id_session, customer_unique_id,
         id_produit, requete)
    VALUES %s
    ON CONFLICT (id_evenement) DO NOTHING
"""


@dataclass(frozen=True)
class Bilan:
    lus: int
    retenus: int
    ignores: int  # messages illisibles ou incomplets

    @property
    def doublons(self) -> int:
        """Messages valides déjà connus : reçus une seconde fois."""
        return 0  # renseigné par le compteur d'insertions, voir alimenter()


def en_ligne(evenement: dict) -> tuple | None:
    """Transforme un événement en ligne prête à insérer, ou None s'il est inutilisable.

    Un message sans identifiant, sans type ou sans horodatage lisible ne peut
    pas être compté : il est ignoré, pas rejeté. Le rebut est le travail du bus,
    pas celui des compteurs.
    """
    if not isinstance(evenement, dict):
        return None

    identifiant = evenement.get("id_evenement")
    type_ = evenement.get("type")
    horodatage = evenement.get("horodatage")
    session = evenement.get("id_session")
    if not (identifiant and type_ and horodatage and session):
        return None

    try:
        instant = datetime.fromisoformat(str(horodatage).replace("Z", "+00:00"))
    except ValueError:
        return None

    return (
        identifiant,
        type_,
        instant,
        instant.date(),
        session,
        evenement.get("customer_unique_id"),
        evenement.get("id_produit"),
        evenement.get("requete"),
    )


def alimenter(messages, dsn: str | None = None, taille_lot: int = TAILLE_LOT) -> Bilan:
    """Lit les messages et alimente la table des événements du jour."""
    lus = retenus = ignores = 0
    lot: list = []

    connexion = psycopg2.connect(dsn or load_settings().postgres_dsn)
    try:
        with connexion.cursor() as curseur:
            for message in messages:
                lus += 1
                ligne = en_ligne(getattr(message, "valeur", message))
                if ligne is None:
                    ignores += 1
                    continue
                lot.append(ligne)
                if len(lot) >= taille_lot:
                    retenus += _ecrire(curseur, lot)
                    connexion.commit()
                    lot = []
            retenus += _ecrire(curseur, lot)
        connexion.commit()
    finally:
        connexion.close()

    return Bilan(lus=lus, retenus=retenus, ignores=ignores)


def _ecrire(curseur, lot: list) -> int:
    """Écrit un lot et renvoie le nombre de lignes réellement insérées.

    `page_size` vaut la taille du lot : par défaut, execute_values découperait
    en pages de 100 et `rowcount` ne refléterait que la dernière — le compte
    des doublons serait faux sans que rien ne le signale.
    """
    if not lot:
        return 0
    psycopg2.extras.execute_values(curseur, INSERTION, lot, page_size=len(lot))
    return curseur.rowcount


def consommer_le_bus(duree: float = 30.0, depuis_le_debut: bool = True):
    """Lit le sujet des événements et s'arrête après un temps sans message."""
    from common.bus import consommer

    return consommer(
        sujet=SUJET_EVENEMENTS,
        groupe=GROUPE,
        depuis_le_debut=depuis_le_debut,
        arret_apres_inactivite=duree,
    )
