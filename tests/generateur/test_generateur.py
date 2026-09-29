"""Tests du générateur : forme des événements, reproductibilité, taux, volume. Aucun Kafka."""

import re
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from itertools import islice

import pytest

from generateur import Generateur, Parametres, Statistiques, est_invalide
from generateur.__main__ import analyser_arguments
from generateur.simulateur import (
    DEFAUTS_INVALIDES,
    DEFAUTS_VALIDES,
    mots_de_designation,
)

MAINTENANT = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
CHAMPS = {
    "version_contrat",
    "id_evenement",
    "type",
    "horodatage",
    "id_session",
    "customer_unique_id",
    "id_produit",
    "requete",
}
HEX32 = re.compile(r"^[0-9a-f]{32}$")

PRODUITS = [
    (str(3_000_000_000 + i), d)
    for i, d in enumerate(
        [
            "Chaise de bureau ergonomique noire",
            "Lampe de chevet en bois &amp; métal",
            "Bouilloire électrique inox 1,7 L",
            "Tapis de yoga antidérapant vert",
            "Casque audio sans fil Bluetooth",
            "Table basse scandinave chêne clair",
            "Perceuse visseuse 18V avec deux batteries",
            "Sac à dos randonnée 40 litres imperméable",
        ]
        * 6
    )
]
CLIENTS = [uuid.UUID(int=i * 7919 + 1).hex for i in range(50)]


def erreurs_contrat(e: dict) -> list[str]:
    """Reformulation indépendante des règles du contrat v1 (le code de common/evenements.py fait foi)."""
    err = []
    if set(e) != CHAMPS:
        return [f"champs : {sorted(set(e) ^ CHAMPS)}"]
    if e["version_contrat"] != 1:
        err.append("version")
    try:
        uuid.UUID(e["id_evenement"])
    except (ValueError, TypeError, AttributeError):
        err.append("id_evenement")
    if e["type"] not in ("page_vue", "recherche", "ajout_panier", "achat"):
        err.append("type")
    if not isinstance(e["id_session"], str) or not e["id_session"]:
        err.append("id_session")
    try:
        h = datetime.fromisoformat(e["horodatage"].replace("Z", "+00:00"))
        if h.tzinfo is None:
            err.append("horodatage sans fuseau")
        elif h < datetime(2016, 1, 1, tzinfo=UTC):
            err.append("horodatage trop ancien")
        elif h > MAINTENANT + timedelta(hours=24):
            err.append("horodatage dans le futur")
    except (ValueError, TypeError, AttributeError):
        err.append("horodatage illisible")
    c, p, r = e["customer_unique_id"], e["id_produit"], e["requete"]
    if c is not None and not (isinstance(c, str) and HEX32.match(c)):
        err.append("customer_unique_id")
    if p is not None and not (isinstance(p, str) and p.isdigit()):
        err.append("id_produit")
    t = e["type"]
    if t in ("page_vue", "ajout_panier") and (p is None or r is not None):
        err.append("produit obligatoire / requete interdite")
    if t == "recherche" and (p is not None or not r):
        err.append("requete obligatoire / produit interdit")
    if t == "achat" and (c is None or r is not None):
        err.append("client obligatoire / requete interdite")
    return err


def flux(n, **kw):
    graine = kw.pop("graine", 42)
    return list(
        islice(
            Generateur(PRODUITS, CLIENTS, Parametres(graine=graine, **kw)).evenements(),
            n,
        )
    )


# --------------------------------------------------------------- reproductibilité


def test_meme_graine_memes_evenements():
    assert flux(3000, graine=42, taux_defauts=0.1) == flux(3000, graine=42, taux_defauts=0.1)


def test_graines_differentes_evenements_differents():
    assert flux(200, graine=1) != flux(200, graine=2)


# ------------------------------------------------------------- conformité au contrat


def test_evenements_sans_defaut_conformes():
    for evt in flux(5000, taux_defauts=0):
        assert evt.defaut is None
        assert erreurs_contrat(evt.contenu) == [], evt.contenu


def test_defauts_valides_restent_conformes_et_invalides_sont_detectes():
    evenements = flux(20_000, taux_defauts=0.3)
    vus = Counter(e.defaut for e in evenements)
    assert set(vus) - {None} == set(DEFAUTS_VALIDES) | set(
        DEFAUTS_INVALIDES
    )  # tous les défauts apparaissent
    for evt in evenements:
        if est_invalide(evt.defaut):
            assert erreurs_contrat(evt.contenu), (evt.defaut, evt.contenu)
        else:
            assert erreurs_contrat(evt.contenu) == [], (evt.defaut, evt.contenu)


def test_achat_toujours_avec_client_identifie():
    achats = [e.contenu for e in flux(20_000, taux_defauts=0) if e.contenu["type"] == "achat"]
    assert achats and all(HEX32.match(a["customer_unique_id"]) for a in achats)


# ----------------------------------------------------------------- données crédibles


def test_identifiants_et_clients_viennent_des_donnees():
    ids = {pid for pid, _ in PRODUITS}
    for evt in flux(5000, taux_defauts=0):
        c = evt.contenu
        assert c["id_produit"] is None or c["id_produit"] in ids
        assert c["customer_unique_id"] is None or c["customer_unique_id"] in CLIENTS


def test_requetes_construites_depuis_les_designations():
    vocabulaire = {m for _, d in PRODUITS for m in mots_de_designation(d)}
    recherches = [
        e.contenu["requete"] for e in flux(5000, taux_defauts=0) if e.contenu["type"] == "recherche"
    ]
    assert recherches
    for requete in recherches:
        assert set(requete.split()) <= vocabulaire


def test_fautes_de_frappe_changent_la_requete():
    vocabulaire = {m for _, d in PRODUITS for m in mots_de_designation(d)}
    fautives = [e for e in flux(20_000, taux_defauts=0.5) if e.defaut == "faute_frappe"]
    assert fautives
    assert all(not set(e.contenu["requete"].split()) <= vocabulaire for e in fautives)


# ------------------------------------------------------------------ taux réglables


def test_taux_de_defauts_respecte():
    evenements = flux(20_000, taux_defauts=0.10)
    taux = sum(e.defaut is not None for e in evenements) / len(evenements)
    assert 0.09 < taux < 0.11


def test_proportions_des_types_respectees():
    props = {"page_vue": 0.4, "recherche": 0.4, "ajout_panier": 0.1, "achat": 0.1}
    evenements = flux(20_000, proportions=props, taux_defauts=0)
    comptes = Counter(e.contenu["type"] for e in evenements)
    for type_, attendu in props.items():
        assert abs(comptes[type_] / 20_000 - attendu) < 0.02


# ------------------------------------------------------------------------- volume


@pytest.mark.parametrize("par_jour", [10_000, 30_000, 50_000])
def test_une_journee_simulee_correspond_au_volume_vise(par_jour):
    evenements = flux(par_jour, evenements_par_jour=par_jour, taux_defauts=0)
    horodatages = [
        datetime.fromisoformat(e.contenu["horodatage"].replace("Z", "+00:00")) for e in evenements
    ]
    assert horodatages == sorted(horodatages)
    duree = horodatages[-1] - horodatages[0]
    assert timedelta(hours=22) < duree < timedelta(hours=26)


def test_cinquante_mille_evenements_conformes():
    evenements = flux(50_000, evenements_par_jour=50_000, taux_defauts=0)
    assert len(evenements) == 50_000
    assert len({e.contenu["id_evenement"] for e in evenements}) == 50_000  # identifiants uniques


# --------------------------------------------------------------------- divers


def test_parametres_invalides_refuses():
    with pytest.raises(ValueError):
        Parametres(taux_defauts=1.5)
    with pytest.raises(ValueError):
        Parametres(proportions={"inconnu": 1})
    with pytest.raises(ValueError):
        Parametres(debut=datetime(2026, 9, 1))  # sans fuseau


def test_statistiques_detectent_les_incoherences():
    stats = Statistiques()
    valide, invalide = None, None
    for e in flux(2000, taux_defauts=0.3):
        if e.defaut is None and valide is None:
            valide = e
        if est_invalide(e.defaut) and invalide is None:
            invalide = e
    stats.enregistrer(valide, accepte=True)
    stats.enregistrer(invalide, accepte=False)
    assert stats.coherent
    stats.enregistrer(valide, accepte=False)
    assert not stats.coherent


def test_ligne_de_commande_du_dossier():
    a = analyser_arguments(["--debit", "20", "--duree", "300", "--graine", "42"])
    assert (a.debit, a.duree, a.graine) == (20, 300, 42)
    a = analyser_arguments(["--proportions", "page_vue=0.7,achat=0.3"])
    assert a.proportions == {"page_vue": 0.7, "achat": 0.3}
