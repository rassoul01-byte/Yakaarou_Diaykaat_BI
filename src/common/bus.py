"""Publication et lecture des événements sur le bus Kafka.

- Publieur : publie un événement. S'il ne respecte pas le contrat, il part vers
  le sujet de rebut avec ses motifs, au lieu du sujet principal. Aucun message
  n'est perdu sans trace.
- consommer : lit un sujet et renvoie les messages un par un.
- creer_sujets et etat_du_bus : la logique des scripts du même nom, gardée ici
  pour pouvoir être testée.

Le contrat des messages est décrit dans docs/contrats/evenements.md.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass

from confluent_kafka import (
    TIMESTAMP_NOT_AVAILABLE,
    Consumer,
    ConsumerGroupTopicPartitions,
    KafkaError,
    KafkaException,
    Producer,
    TopicPartition,
)
from confluent_kafka.admin import AdminClient, NewTopic

from common.config import load_settings
from common.evenements import (
    SUJET_EVENEMENTS,
    SUJET_REBUT,
    SUJET_REJEU,
    horodatage_iso,
    valider,
)

journal = logging.getLogger(__name__)

PARTITIONS = 3
_JOUR_MS = 24 * 3600 * 1000

# Sujets du contrat, avec leur durée de conservation.
SUJETS = {
    SUJET_EVENEMENTS: {"retention.ms": str(7 * _JOUR_MS)},
    SUJET_REBUT: {"retention.ms": str(30 * _JOUR_MS)},
    SUJET_REJEU: {"retention.ms": str(7 * _JOUR_MS)},
}

_GROUPE_ETAT = "dataflow360-etat-bus"


def _serveur(bootstrap: str | None) -> str:
    return bootstrap or load_settings().kafka_bootstrap


# --------------------------------------------------------------------------- #
# Publication
# --------------------------------------------------------------------------- #


class Publieur:
    """Publie des événements en appliquant le contrat.

    Un événement valide part sur le sujet principal — navigation.evenements par
    défaut —, avec l'identifiant de session comme clé. Un événement invalide part
    sur navigation.rebut, accompagné de la liste de ses motifs de refus.

    À utiliser de préférence avec « with », qui garantit que tous les messages
    en attente sont envoyés avant la fin du programme.
    """

    def __init__(
        self,
        bootstrap: str | None = None,
        *,
        sujet_principal: str = SUJET_EVENEMENTS,
        client_id: str = "dataflow360",
        producteur: Producer | None = None,
    ) -> None:
        self.sujet_principal = sujet_principal
        self._producteur = producteur or Producer(
            {
                "bootstrap.servers": _serveur(bootstrap),
                "client.id": client_id,
                "acks": "all",
                "enable.idempotence": True,
                "linger.ms": 20,
            }
        )
        self.publies = 0
        self.rebutes = 0
        self.echecs_envoi = 0

    def publier(self, evenement: dict | str | bytes) -> bool:
        """Publie un événement. Renvoie True s'il est valide, False s'il part au rebut.

        Accepte un dictionnaire, ou un texte JSON — utile pour tester le bus à la main.
        """
        if isinstance(evenement, (str, bytes)):
            try:
                evenement = json.loads(evenement)
            except (ValueError, UnicodeDecodeError):
                self._rebuter(evenement, ["message illisible : ce n'est pas du JSON"])
                return False

        motifs = valider(evenement)
        if motifs:
            self._rebuter(evenement, motifs)
            return False

        self._envoyer(self.sujet_principal, evenement["id_session"], evenement)
        self.publies += 1
        return True

    def vider(self, delai: float = 10.0) -> int:
        """Attend l'envoi des messages en attente. Renvoie le nombre de ceux restés en attente."""
        return self._producteur.flush(delai)

    def __enter__(self) -> Publieur:
        return self

    def __exit__(self, *exc: object) -> None:
        restants = self.vider()
        if restants:
            journal.warning("%d message(s) non envoyé(s) à la fermeture du publieur", restants)

    def _rebuter(self, evenement: object, motifs: list[str]) -> None:
        if isinstance(evenement, bytes):
            evenement = evenement.decode("utf-8", errors="replace")
        cle = evenement.get("id_session") if isinstance(evenement, dict) else None
        rebut = {"motifs": motifs, "recu_le": horodatage_iso(), "evenement_brut": evenement}
        self._envoyer(SUJET_REBUT, cle if isinstance(cle, str) else None, rebut)
        self.rebutes += 1

    def _envoyer(self, sujet: str, cle: str | None, valeur: object) -> None:
        arguments = {
            "key": cle.encode("utf-8") if cle else None,
            "value": json.dumps(valeur, ensure_ascii=False, default=str).encode("utf-8"),
            "on_delivery": self._accuser_reception,
        }
        try:
            self._producteur.produce(sujet, **arguments)
        except BufferError:
            # File d'attente locale pleine : on laisse partir des messages, puis on réessaie.
            self._producteur.poll(1.0)
            self._producteur.produce(sujet, **arguments)
        self._producteur.poll(0)

    def _accuser_reception(self, erreur: KafkaError | None, message: object) -> None:
        if erreur is not None:
            self.echecs_envoi += 1
            journal.error("Échec d'envoi sur le bus : %s", erreur)


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MessageRecu:
    sujet: str
    partition: int
    position: int
    cle: str | None
    valeur: object  # un dictionnaire si le message est du JSON lisible, sinon le texte reçu
    horodatage_kafka_ms: int | None


def consommer(
    sujet: str,
    groupe: str,
    *,
    depuis_le_debut: bool = True,
    arret_apres_inactivite: float | None = None,
    max_messages: int | None = None,
    bootstrap: str | None = None,
) -> Iterator[MessageRecu]:
    """Lit un sujet et renvoie les messages un par un.

    - groupe : le nom du consommateur. Kafka retient où en est chaque groupe ;
      c'est aussi ce nom qu'affiche scripts/etat_bus.py.
    - depuis_le_debut : pour un groupe qui n'a encore rien lu, partir du plus
      ancien message conservé plutôt que des seuls nouveaux.
    - arret_apres_inactivite : s'arrêter après ce nombre de secondes sans message.
      Par défaut, la lecture ne s'arrête jamais.
    - max_messages : s'arrêter après ce nombre de messages.

    La position n'est validée qu'une fois le message traité, c'est-à-dire quand
    le message suivant est demandé : si le programme s'arrête en cours de
    traitement, le message sera relu. Un même message peut donc être reçu deux
    fois — voir la section 7 du contrat.
    """
    lecteur = Consumer(
        {
            "bootstrap.servers": _serveur(bootstrap),
            "group.id": groupe,
            "auto.offset.reset": "earliest" if depuis_le_debut else "latest",
            "enable.auto.commit": False,
        }
    )
    lecteur.subscribe([sujet])
    recus = 0
    derniere_activite = time.monotonic()
    try:
        while max_messages is None or recus < max_messages:
            message = lecteur.poll(1.0)
            if message is None:
                inactif = time.monotonic() - derniere_activite
                if arret_apres_inactivite is not None and inactif >= arret_apres_inactivite:
                    return
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(message.error())
            derniere_activite = time.monotonic()
            recus += 1
            yield _decoder(message)
            lecteur.commit(message=message, asynchronous=False)
    finally:
        lecteur.close()


def _decoder(message: object) -> MessageRecu:
    cle = message.key().decode("utf-8", errors="replace") if message.key() else None
    brut = message.value() or b""
    try:
        valeur = json.loads(brut)
    except (ValueError, UnicodeDecodeError):
        valeur = brut.decode("utf-8", errors="replace")
    type_horodatage, horodatage = message.timestamp()
    return MessageRecu(
        sujet=message.topic(),
        partition=message.partition(),
        position=message.offset(),
        cle=cle,
        valeur=valeur,
        horodatage_kafka_ms=None if type_horodatage == TIMESTAMP_NOT_AVAILABLE else horodatage,
    )


# --------------------------------------------------------------------------- #
# Administration
# --------------------------------------------------------------------------- #


def creer_sujets(bootstrap: str | None = None, *, admin: AdminClient | None = None) -> dict:
    """Crée les sujets du contrat qui n'existent pas encore.

    Renvoie, pour chaque sujet, « créé » ou « existe déjà ». Peut être relancé
    sans risque autant de fois que voulu.
    """
    admin = admin or AdminClient({"bootstrap.servers": _serveur(bootstrap)})
    demandes = [
        NewTopic(nom, num_partitions=PARTITIONS, replication_factor=1, config=reglages)
        for nom, reglages in SUJETS.items()
    ]
    resultats = {}
    for nom, futur in admin.create_topics(demandes, request_timeout=15).items():
        try:
            futur.result()
            resultats[nom] = "créé"
        except KafkaException as erreur:
            if erreur.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                raise
            resultats[nom] = "existe déjà"
    return resultats


@dataclass(frozen=True)
class EtatSujet:
    nom: str
    partitions: int
    messages: int  # messages actuellement conservés sur le sujet


@dataclass(frozen=True)
class RetardGroupe:
    groupe: str
    sujet: str
    retard: int  # messages publiés que ce groupe n'a pas encore lus


def etat_du_bus(bootstrap: str | None = None, delai: float = 10.0) -> tuple[list, list]:
    """Photographie le bus : les sujets et leur volume, puis le retard de chaque groupe."""
    reglages = {"bootstrap.servers": _serveur(bootstrap)}
    admin = AdminClient(reglages)
    lecteur = Consumer({**reglages, "group.id": _GROUPE_ETAT, "enable.auto.commit": False})
    try:
        hauts = {}
        sujets = []
        for nom, meta in sorted(admin.list_topics(timeout=delai).topics.items()):
            if nom.startswith("__"):  # sujets internes de Kafka
                continue
            total = 0
            for partition in meta.partitions:
                bas, haut = lecteur.get_watermark_offsets(
                    TopicPartition(nom, partition), timeout=delai
                )
                hauts[(nom, partition)] = haut
                total += haut - bas
            sujets.append(EtatSujet(nom, len(meta.partitions), total))

        retards = []
        groupes = admin.list_consumer_groups(request_timeout=delai).result().valid
        for groupe in sorted(g.group_id for g in groupes if g.group_id != _GROUPE_ETAT):
            demande = [ConsumerGroupTopicPartitions(groupe)]
            positions = admin.list_consumer_group_offsets(demande)[groupe].result()
            par_sujet: dict[str, int] = {}
            for tp in positions.topic_partitions:
                haut = hauts.get((tp.topic, tp.partition))
                if tp.offset < 0 or haut is None:  # position jamais validée
                    continue
                par_sujet[tp.topic] = par_sujet.get(tp.topic, 0) + max(haut - tp.offset, 0)
            retards += [RetardGroupe(groupe, s, r) for s, r in sorted(par_sujet.items())]
        return sujets, retards
    finally:
        lecteur.close()
