"""Contrôles statiques du DAG quotidien.

Airflow n'est pas installé dans l'environnement de test (il tourne dans sa propre
image) : on lit le fichier avec `ast`, sans l'importer.
"""

import ast
from pathlib import Path

DAG = Path(__file__).resolve().parents[2] / "dags" / "quotidien.py"
ARBRE = ast.parse(DAG.read_text(encoding="utf-8"))


def _affectation(nom: str) -> ast.expr:
    for noeud in ARBRE.body:
        if isinstance(noeud, ast.Assign) and any(
            isinstance(c, ast.Name) and c.id == nom for c in noeud.targets
        ):
            return noeud.value
    raise AssertionError(f"{nom} introuvable dans {DAG.name}")


def _taches_creees() -> set[str]:
    corps = next(n for n in ARBRE.body if isinstance(n, ast.With)).body
    return {
        n.value.args[0].value
        for n in corps
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Call)
        and getattr(n.value.func, "id", "") == "tache"
    }


def test_chaque_tache_reelle_a_une_commande():
    reelles = {e.value for e in _affectation("REELLES").elts}
    commandes = {k.value for k in _affectation("COMMANDES").keys}
    assert reelles <= commandes


def test_chaque_tache_creee_a_une_commande():
    commandes = {k.value for k in _affectation("COMMANDES").keys}
    assert _taches_creees() <= commandes


def test_taches_documentaire_et_prediction_branchees():
    reelles = {e.value for e in _affectation("REELLES").elts}
    assert {"indexation_passages", "scores_reachat"} <= reelles
    assert {"indexation_passages", "scores_reachat"} <= _taches_creees()
