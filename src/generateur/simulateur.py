"""Simulation déterministe des événements de navigation (contrat v1).

Ce module ne fait aucune entrée/sortie : ni Kafka, ni fichier, ni horloge
réelle. Tout le hasard vient d'un seul `random.Random(graine)`, et l'horloge
est simulée. Deux lancements avec les mêmes paramètres, la même graine et les
mêmes données produisent donc exactement les mêmes événements.
"""

from __future__ import annotations

import html
import re
import string
import uuid
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from random import Random
from typing import NamedTuple

VERSION_CONTRAT = 1
TYPES = ("page_vue", "recherche", "ajout_panier", "achat")
PROPORTIONS_DEFAUT = {
    "page_vue": 0.50,
    "recherche": 0.30,
    "ajout_panier": 0.15,
    "achat": 0.05,
}

# Défauts qui restent des événements VALIDES au sens du contrat : ils servent à
# éprouver la recherche (Sprint 4). Le bus doit les laisser passer.
DEFAUTS_VALIDES = ("faute_frappe", "requete_introuvable")

# Défauts qui violent le contrat : le bus doit les écarter vers `navigation.rebut`.
DEFAUTS_INVALIDES = (
    "champ_manquant",
    "horodatage_sans_fuseau",
    "horodatage_futur",
    "horodatage_ancien",
    "horodatage_illisible",
)

_CHAMP_OBLIGATOIRE = {
    "page_vue": "id_produit",
    "recherche": "requete",
    "ajout_panier": "id_produit",
    "achat": "customer_unique_id",
}

_MOTS = re.compile(r"[^\W_]{2,}")


def est_invalide(defaut: str | None) -> bool:
    """Vrai si le défaut rend l'événement non conforme au contrat."""
    return defaut in DEFAUTS_INVALIDES


@dataclass
class Parametres:
    graine: int = 42
    # Date de début FIXE par défaut (et non « maintenant ») : sinon deux lancements
    # à des jours différents ne produiraient pas les mêmes événements. Elle doit
    # rester passée : le contrat refuse plus de 24 h dans le futur.
    debut: datetime = datetime(2026, 9, 1, tzinfo=UTC)
    evenements_par_jour: int = 30_000  # cible du dossier : 10 000 à 50 000
    proportions: dict[str, float] = field(default_factory=lambda: dict(PROPORTIONS_DEFAUT))
    taux_defauts: float = 0.05  # part des événements qui portent un défaut
    part_clients_connus: float = 0.40  # part des sessions identifiées dès le départ
    proba_nouvelle_session: float = 0.15
    proba_fin_session: float = 0.08

    def __post_init__(self) -> None:
        if self.debut.tzinfo is None:
            raise ValueError("debut doit avoir un fuseau horaire")
        if self.evenements_par_jour <= 0:
            raise ValueError("evenements_par_jour doit être positif")
        inconnus = set(self.proportions) - set(TYPES)
        if inconnus:
            raise ValueError(f"types inconnus dans les proportions : {sorted(inconnus)}")
        if any(p < 0 for p in self.proportions.values()) or sum(self.proportions.values()) <= 0:
            raise ValueError("les proportions doivent être positives, de somme non nulle")
        for nom in (
            "taux_defauts",
            "part_clients_connus",
            "proba_nouvelle_session",
            "proba_fin_session",
        ):
            if not 0 <= getattr(self, nom) <= 1:
                raise ValueError(f"{nom} doit être compris entre 0 et 1")


class Evenement(NamedTuple):
    contenu: dict  # ce qui part sur le bus
    defaut: str | None  # défaut volontaire injecté, ou None (information de test, hors contrat)


@dataclass
class Statistiques:
    total: int = 0
    par_type: Counter = field(default_factory=Counter)
    par_defaut: Counter = field(default_factory=Counter)
    acceptes: int = 0
    rebutes: int = 0
    rebutes_a_tort: int = 0  # valide selon nous, mais refusé par le bus
    acceptes_a_tort: int = 0  # invalide selon nous, mais accepté par le bus

    def enregistrer(self, evt: Evenement, accepte: bool | None = None) -> None:
        self.total += 1
        self.par_type[evt.contenu.get("type", "?")] += 1
        if evt.defaut:
            self.par_defaut[evt.defaut] += 1
        if accepte is None:
            return
        if accepte:
            self.acceptes += 1
            self.acceptes_a_tort += est_invalide(evt.defaut)
        else:
            self.rebutes += 1
            self.rebutes_a_tort += not est_invalide(evt.defaut)

    @property
    def coherent(self) -> bool:
        return self.rebutes_a_tort == 0 and self.acceptes_a_tort == 0


class _Session:
    __slots__ = ("client", "dernier_produit", "id", "panier")

    def __init__(self, id_session: str, client: str | None) -> None:
        self.id = id_session
        self.client = client
        self.dernier_produit: str | None = None
        self.panier: str | None = None


def _iso(t: datetime) -> str:
    """Format du contrat : UTC, suffixe Z, millisecondes."""
    return t.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def mots_de_designation(designation: str) -> tuple[str, ...]:
    """Mots exploitables d'une désignation (minuscules, sans ponctuation ni entités HTML)."""
    return tuple(_MOTS.findall(html.unescape(designation).lower()))[:12]


class Generateur:
    """Produit un flux infini et reproductible d'événements de navigation.

    produits : suite de (id_produit, designation) issue du catalogue Rakuten.
    clients  : suite de customer_unique_id Olist (jamais des identifiants de commande).
    """

    def __init__(
        self,
        produits: Sequence[tuple[str, str]],
        clients: Sequence[str],
        parametres: Parametres | None = None,
    ) -> None:
        self.p = parametres or Parametres()
        self._produits = [
            (str(pid), mots) for pid, d in produits if (mots := mots_de_designation(d))
        ]
        if not self._produits:
            raise ValueError("le catalogue ne contient aucun produit exploitable")
        if not clients:
            raise ValueError("il faut au moins un client (un achat exige un client identifié)")
        self._clients = list(clients)
        self._rng = Random(self.p.graine)
        self._types = [t for t in TYPES if self.p.proportions.get(t, 0) > 0]
        self._poids = [self.p.proportions[t] for t in self._types]
        self._t = self.p.debut
        self._pas_moyen = 86_400 / self.p.evenements_par_jour
        self._actives: list[_Session] = []
        self._compteur_sessions = 0

    # ------------------------------------------------------------------ flux

    def evenements(self) -> Iterator[Evenement]:
        while True:
            yield self._suivant()

    def _suivant(self) -> Evenement:
        rng = self._rng
        self._t += timedelta(seconds=rng.expovariate(1 / self._pas_moyen))
        type_ = rng.choices(self._types, weights=self._poids)[0]
        session = self._choisir_session()

        id_produit: str | None = None
        requete: str | None = None
        if type_ == "page_vue":
            id_produit = session.dernier_produit = self._produit()[0]
        elif type_ == "recherche":
            requete = self._requete()
        elif type_ == "ajout_panier":
            if session.dernier_produit and rng.random() < 0.7:
                id_produit = session.dernier_produit
            else:
                id_produit = self._produit()[0]
            session.panier = id_produit
        else:  # achat : un client identifié est obligatoire (connexion en cours de session)
            if session.client is None:
                session.client = rng.choice(self._clients)
            id_produit, session.panier = session.panier, None

        contenu = {
            "version_contrat": VERSION_CONTRAT,
            "id_evenement": str(uuid.UUID(int=rng.getrandbits(128), version=4)),
            "type": type_,
            "horodatage": _iso(self._t),
            "id_session": session.id,
            "customer_unique_id": session.client,
            "id_produit": id_produit,
            "requete": requete,
        }
        defaut = self._appliquer_defaut(contenu) if rng.random() < self.p.taux_defauts else None

        if rng.random() < self.p.proba_fin_session and session in self._actives:
            self._actives.remove(session)
        return Evenement(contenu, defaut)

    # -------------------------------------------------------------- sessions

    def _choisir_session(self) -> _Session:
        rng = self._rng
        if not self._actives or rng.random() < self.p.proba_nouvelle_session:
            self._compteur_sessions += 1
            client = (
                rng.choice(self._clients) if rng.random() < self.p.part_clients_connus else None
            )
            session = _Session(f"s-{self._compteur_sessions:06d}", client)
            self._actives.append(session)
            return session
        return rng.choice(self._actives)

    # ------------------------------------------------------------- catalogue

    def _produit(self) -> tuple[str, tuple[str, ...]]:
        # Quelques produits sont bien plus consultés que les autres (loi de puissance).
        indice = int(len(self._produits) * self._rng.random() ** 3)
        return self._produits[indice]

    def _requete(self) -> str:
        rng = self._rng
        mots = self._produit()[1]
        n = min(len(mots), rng.randint(2, 4))
        debut = rng.randint(0, len(mots) - n)
        return " ".join(mots[debut : debut + n])

    # ---------------------------------------------------------------- défauts

    def _appliquer_defaut(self, evt: dict) -> str:
        rng = self._rng
        candidats = list(DEFAUTS_INVALIDES)
        if evt["type"] == "recherche":
            candidats += DEFAUTS_VALIDES
        defaut = rng.choice(candidats)

        if defaut == "faute_frappe":
            evt["requete"] = self._faute(evt["requete"])
        elif defaut == "requete_introuvable":
            evt["requete"] = "".join(rng.choices("bcdfghjklmnpqrstvwxz", k=rng.randint(6, 10)))
        elif defaut == "champ_manquant":
            champ = _CHAMP_OBLIGATOIRE[evt["type"]]
            modes = ["null", "absent"] + (["vide"] if champ == "requete" else [])
            mode = rng.choice(modes)
            if mode == "absent":
                del evt[champ]
            else:
                evt[champ] = "" if mode == "vide" else None
        elif defaut == "horodatage_sans_fuseau":
            evt["horodatage"] = _iso(self._t).removesuffix("Z")
        elif defaut == "horodatage_futur":
            # Toujours dans le futur RÉEL, quelle que soit la date de début simulée.
            evt["horodatage"] = _iso(self._t + timedelta(days=rng.randint(18_000, 36_000)))
        elif defaut == "horodatage_ancien":
            avant_2016 = datetime(2015, 12, 31, 23, 59, 59, tzinfo=UTC)
            evt["horodatage"] = _iso(avant_2016 - timedelta(days=rng.randint(0, 3_000)))
        else:  # horodatage_illisible
            evt["horodatage"] = self._t.strftime("%d/%m/%Y %H:%M")
        return defaut

    def _faute(self, requete: str) -> str:
        rng = self._rng
        mots = requete.split()
        candidats = [i for i, m in enumerate(mots) if len(m) >= 4] or list(range(len(mots)))
        i = rng.choice(candidats)
        mot = mots[i]
        op = rng.choice(("supprimer", "doubler", "transposer", "remplacer"))
        p = rng.randrange(len(mot))
        if op == "supprimer" and len(mot) > 2:
            nouveau = mot[:p] + mot[p + 1 :]
        elif op == "transposer" and len(mot) >= 2:
            p = min(p, len(mot) - 2)
            nouveau = mot[:p] + mot[p + 1] + mot[p] + mot[p + 2 :]
        elif op == "remplacer":
            nouveau = mot[:p] + rng.choice(string.ascii_lowercase) + mot[p + 1 :]
        else:
            nouveau = mot[: p + 1] + mot[p] + mot[p + 1 :]
        if nouveau == mot:  # remplacement par la même lettre, transposition de lettres identiques
            nouveau = mot + mot[-1]
        mots[i] = nouveau
        return " ".join(mots)
