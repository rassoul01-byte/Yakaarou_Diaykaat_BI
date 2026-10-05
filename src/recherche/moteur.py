"""Moteur de recherche du catalogue : F4.2 (fautes de frappe) et F4.3 (filtres).

Le moteur interroge l'index `catalogue` décrit dans docs/contrats/index.md.
Il ne touche jamais à l'index : l'analyseur gère déjà les accents, les
majuscules et le pluriel ; **la tolérance aux fautes se règle ici, dans la
requête.**

Deux fonctions publiques :

    rechercher(client, "chaise de bureu")            une recherche
    rechercher_plusieurs(client, [texte1, texte2])   plusieurs, en un seul envoi
                                                     (sert à F4.5)

⚠️ PAS DE FILTRE DE PRIX (décision F4.3). Le catalogue Rakuten ne contient aucun
prix, et le lien entre un produit Olist (qui a un prix) et une fiche du
catalogue est arbitraire (docs/contrats/correspondance.md). Afficher un prix
sur une fiche serait un montant inventé. On filtre donc par catégorie et par
langue seulement, et on le dit. Voir docs/contrats/recherche.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .schema import INDEX

# --------------------------------------------------------------------------
# Réglages. Ils se justifient, ils ne se devinent pas : les valeurs ci-dessous
# sont un POINT DE DÉPART, à confirmer par le jeu d'évaluation
# (tests/recherche/test_recherche_integration.py) puis à noter dans la PR.
# --------------------------------------------------------------------------

# La désignation pèse trois fois plus que la description (contrat d'index, §5).
CHAMPS_RECHERCHE = ("designation^3", "description")

# Nombre de fautes tolérées par mot. « AUTO » : 0 faute pour 1-2 lettres,
# 1 faute pour 3 à 5 lettres, 2 fautes à partir de 6 lettres.
#   trop haut -> « lampe » ramène « rampe »
#   trop bas  -> « bureu » ne ramène pas « bureau »
TOLERANCE = "AUTO"

# Nombre de premières lettres qui doivent être exactes. À 1, « rampe » ne peut
# plus être confondu avec « lampe » (la première lettre diffère), au prix d'une
# faute sur la première lettre qui ne sera pas rattrapée.
PREFIXE_EXACT = 1

# « and » : tous les mots de la requête doivent être trouvés (résultats précis).
# « or » : un seul mot suffit (plus de résultats, plus de bruit).
OPERATEUR = "and"

# Les correspondances sans faute passent devant les correspondances approchées.
BONUS_EXACT = 2

TAILLE_PAR_DEFAUT = 10
TAILLE_MAX = 50

# Le temps de réponse visé : sous la seconde.
SEUIL_REPONSE_MS = 1000

CHAMPS_RENDUS = ["product_id", "designation", "categorie_code"]


class ErreurRecherche(RuntimeError):
    """Elasticsearch a répondu, mais pas par un résultat exploitable."""


@dataclass(frozen=True)
class Resultat:
    product_id: str
    designation: str
    categorie_code: str | None
    score: float


@dataclass(frozen=True)
class Reponse:
    texte: str
    resultats: list[Resultat]
    total: int  # nombre de fiches qui correspondent, pas seulement celles rendues
    temps_serveur_ms: int  # mesuré par Elasticsearch (« took »)
    temps_total_ms: float  # mesuré ici, réseau compris : c'est ce que voit l'acheteur

    @property
    def aboutit(self) -> bool:
        """Vrai si la recherche ramène au moins une fiche."""
        return self.total > 0


# ---------------------------------------------------------------- la requête


def construire_requete(
    texte: str,
    *,
    categorie: str | None = None,
    langue: str | None = None,
    taille: int = TAILLE_PAR_DEFAUT,
    tolerance: str | None = TOLERANCE,
    prefixe_exact: int = PREFIXE_EXACT,
    operateur: str = OPERATEUR,
) -> dict:
    """Construit le corps de la recherche. Ne contacte pas Elasticsearch.

    C'est ici que tout se décide, et c'est pour cela que cette fonction est
    séparée : elle se teste sans service, et F4.5 la réutilise telle quelle
    pour que « sans résultat » veuille dire la même chose que pour l'acheteur.

    `tolerance=None` désactive les fautes (recherche exacte), utile pour
    comparer les réglages.
    """
    texte = (texte or "").strip()
    if not texte:
        raise ValueError("requête vide")
    if not 0 <= taille <= TAILLE_MAX:
        raise ValueError(f"taille hors limites (0 à {TAILLE_MAX}) : {taille}")

    # Recherche approchée : celle qui rattrape « bureu ».
    approchee = {
        "query": texte,
        "fields": list(CHAMPS_RECHERCHE),
        "operator": operateur,
    }
    if tolerance is not None:
        approchee["fuzziness"] = tolerance
        approchee["prefix_length"] = prefixe_exact

    # Recherche exacte : elle ne sert qu'à faire monter les fiches sans faute.
    exacte = {
        "query": texte,
        "fields": list(CHAMPS_RECHERCHE),
        "operator": operateur,
        "boost": BONUS_EXACT,
    }

    # Un filtre restreint les résultats sans changer leur classement.
    filtres = []
    if categorie:
        filtres.append({"term": {"categorie_code": str(categorie)}})
    if langue:
        filtres.append({"term": {"langue": langue}})

    return {
        "size": taille,
        "track_total_hits": True,
        "_source": CHAMPS_RENDUS,
        "query": {
            "bool": {
                "must": [{"multi_match": approchee}],
                "should": [{"multi_match": exacte}],
                "filter": filtres,
            }
        },
    }


# --------------------------------------------------------------- les réponses


def _lire_reponse(texte: str, brut, temps_total_ms: float) -> Reponse:
    if brut.get("error"):
        raise ErreurRecherche(str(brut["error"]))
    hits = brut["hits"]
    resultats = [
        Resultat(
            product_id=h["_source"].get("product_id", ""),
            designation=h["_source"].get("designation", ""),
            categorie_code=h["_source"].get("categorie_code"),
            score=float(h.get("_score") or 0.0),
        )
        for h in hits["hits"]
    ]
    return Reponse(
        texte=texte,
        resultats=resultats,
        total=hits["total"]["value"],
        temps_serveur_ms=int(brut.get("took", 0)),
        temps_total_ms=temps_total_ms,
    )


def rechercher(client, texte: str, **options) -> Reponse:
    """Une recherche. `options` : voir `construire_requete`.

    Lève ValueError si la requête est vide, et laisse passer les erreurs de
    connexion d'Elasticsearch (c'est à la commande de les présenter).
    """
    corps = construire_requete(texte, **options)
    debut = time.perf_counter()
    brut = client.search(
        index=INDEX,
        query=corps["query"],
        size=corps["size"],
        track_total_hits=corps["track_total_hits"],
        source=corps["_source"],
    )
    ecoule = (time.perf_counter() - debut) * 1000
    return _lire_reponse(texte, brut, ecoule)


def rechercher_plusieurs(client, textes: list[str], **options) -> list[Reponse]:
    """Plusieurs recherches en un seul envoi (`msearch`), dans l'ordre des textes.

    Sert à F4.5 : analyser des centaines de requêtes en autant d'allers-retours
    serait lent. Chaque recherche utilise la **même** requête que `rechercher`.
    """
    if not textes:
        return []
    envoi: list[dict] = []
    for texte in textes:
        envoi.append({"index": INDEX})
        envoi.append(construire_requete(texte, **options))

    debut = time.perf_counter()
    brut = client.msearch(searches=envoi)
    ecoule = (time.perf_counter() - debut) * 1000

    reponses = brut["responses"]
    if len(reponses) != len(textes):
        raise ErreurRecherche(f"{len(reponses)} réponse(s) pour {len(textes)} requête(s)")
    # Le temps d'un lot est partagé : on le rapporte à chaque recherche.
    par_recherche = ecoule / len(textes)
    return [_lire_reponse(t, r, par_recherche) for t, r in zip(textes, reponses, strict=True)]
