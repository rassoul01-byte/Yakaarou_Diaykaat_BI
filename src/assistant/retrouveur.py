"""La recherche de passages, derrière une interface.

L'assistant ne sait pas comment on retrouve un passage : il appelle `retrouver(question, k)`
et reçoit des passages triés du plus au moins proche, chacun avec son score (contrat
docs/contrats/passages.md, §7). Deux réalisations :

  RetrouveurDepannage  recherche lexicale en mémoire (TF-IDF), écrite pour ne pas être
                       bloqué. PROVISOIRE : la version de démonstration est celle de
                       Seydina (F5.2), branchée via RetrouveurExterne.
  RetrouveurExterne    adaptateur vers la recherche de Seydina, qui rend le JSON du §7.

Chaque recherche porte ses propres seuils : un score n'a pas la même échelle d'une
recherche à l'autre (une proximité lexicale ne ressemble pas à un cosinus).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .garde_fous import Seuils
from .lexique import etendre
from .passages import FAQ, Passage, charger
from .texte import normaliser


class Retrouveur(Protocol):
    nom: str
    seuils: Seuils

    def retrouver(self, question: str, k: int = 3) -> list[Passage]:
        """Les k passages les plus proches, du meilleur au moins bon. Peut être vide."""
        ...


# Réglés sur le jeu de questions PROVISOIRE (tests/assistant/jeu_de_questions.jsonl, 52 questions),
# par validation croisée sur ses deux moitiés ; à refaire sur le jeu gelé. Réglage prudent :
# aucune réponse à tort ni aucun mauvais passage sur les deux moitiés. Son coût : l'assistant
# ne répond directement qu'à environ une question couverte sur trois, et suggère pour la plupart
# des autres. Voir docs/contrats/assistant.md, §6.
SEUILS_DEPANNAGE = Seuils(reponse=0.35, suggestion=0.18, marge=0.12)


class RetrouveurDepannage:
    """Recherche lexicale en mémoire : mots (avec bigrammes) et lettres (tolère les fautes)."""

    nom = "depannage-tfidf"

    def __init__(self, passages: list[Passage], seuils: Seuils = SEUILS_DEPANNAGE) -> None:
        self.passages = list(passages)
        self.seuils = seuils
        textes = [normaliser(f"{p.question} {p.reponse}") for p in self.passages]
        self._mots = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2)).fit(textes)
        self._lettres = TfidfVectorizer(
            sublinear_tf=True, analyzer="char_wb", ngram_range=(3, 5)
        ).fit(textes)
        self._matrice_mots = self._mots.transform(textes)
        self._matrice_lettres = self._lettres.transform(textes)

    @classmethod
    def depuis_faq(
        cls, chemin: Path = FAQ, seuils: Seuils = SEUILS_DEPANNAGE
    ) -> RetrouveurDepannage:
        return cls(charger(chemin), seuils)

    def retrouver(self, question: str, k: int = 3) -> list[Passage]:
        etendue = etendre(question)
        if not etendue:
            return []
        scores = (
            cosine_similarity(self._mots.transform([etendue]), self._matrice_mots)[0]
            + cosine_similarity(self._lettres.transform([etendue]), self._matrice_lettres)[0]
        ) / 2
        ordre = scores.argsort()[::-1][:k]
        return [
            self.passages[i].avec_score(round(float(scores[i]), 4)) for i in ordre if scores[i] > 0
        ]


# ---------------------------------------------------- le contrat de Seydina (§7)


class ReponseContratInvalide(ValueError):
    """La recherche a répondu dans un format qui n'est pas celui de passages.md, §7."""


def depuis_contrat(reponse: dict) -> list[Passage]:
    """Convertit le JSON du §7 en passages, en vérifiant ce que le contrat promet."""
    try:
        resultats = reponse["resultats"]
        passages = [
            Passage(
                id=r["id"],
                theme=r["theme"],
                question=r["question"],
                reponse=r["reponse"],
                source=r["source"],
                score=float(r["score"]),
            )
            for r in resultats
        ]
    except (KeyError, TypeError, ValueError) as erreur:
        raise ReponseContratInvalide(f"réponse hors contrat : {erreur!r}") from erreur
    if any(not 0 <= p.score <= 1 for p in passages):
        raise ReponseContratInvalide("un score sort de l'intervalle [0, 1]")
    if [p.score for p in passages] != sorted((p.score for p in passages), reverse=True):
        raise ReponseContratInvalide("les passages ne sont pas triés par score décroissant")
    return passages


class RetrouveurExterne:
    """Adaptateur : branche la recherche de Seydina (`documentaire.rechercher`) derrière l'interface.

    `recherche(question, k)` doit rendre le JSON du §7. Les seuils sont OBLIGATOIRES : ils se
    mesurent sur le jeu de questions fixé (passages.md, §8), ils ne se devinent pas.
    """

    nom = "documentaire"

    def __init__(self, recherche: Callable[[str, int], dict], seuils: Seuils) -> None:
        self._recherche = recherche
        self.seuils = seuils

    def retrouver(self, question: str, k: int = 3) -> list[Passage]:
        return depuis_contrat(self._recherche(question, k))[:k]
