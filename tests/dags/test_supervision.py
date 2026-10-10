"""Contrôles statiques du DAG de supervision.

Airflow n'est pas installé dans l'environnement de test (il tourne dans sa propre
image) : on lit le fichier avec `ast`, sans l'importer.
"""

import ast
from pathlib import Path

DAG = Path(__file__).resolve().parents[2] / "dags" / "supervision.py"
ARBRE = ast.parse(DAG.read_text(encoding="utf-8"))


def _affectation(nom: str) -> ast.expr:
    for noeud in ARBRE.body:
        if isinstance(noeud, ast.Assign) and any(
            isinstance(c, ast.Name) and c.id == nom for c in noeud.targets
        ):
            return noeud.value
    raise AssertionError(f"{nom} introuvable dans {DAG.name}")


def _bloc_dag() -> ast.With:
    return next(n for n in ARBRE.body if isinstance(n, ast.With))


def _parametres_du_dag() -> dict[str, ast.expr]:
    appel = _bloc_dag().items[0].context_expr
    return {k.arg: k.value for k in appel.keywords}


def _taches_creees() -> dict[str, dict[str, ast.expr]]:
    """{nom de la tâche: options passées à `tache`}."""
    return {
        n.value.args[0].value: {k.arg: k.value for k in n.value.keywords}
        for n in _bloc_dag().body
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Call)
        and getattr(n.value.func, "id", "") == "tache"
    }


def _commandes() -> dict[str, str]:
    """Commandes, avec le préfixe remplacé par un repère lisible."""
    commandes = {}
    for cle, valeur in zip(
        _affectation("COMMANDES").keys, _affectation("COMMANDES").values, strict=True
    ):
        morceaux = [m.value if isinstance(m, ast.Constant) else "<PREFIXE>" for m in valeur.values]
        commandes[cle.value] = "".join(morceaux)
    return commandes


def test_pas_de_rattrapage_ni_de_lancements_simultanes():
    parametres = _parametres_du_dag()
    assert parametres["catchup"].value is False
    assert parametres["max_active_runs"].value == 1


def test_le_dag_est_en_pause_a_sa_creation():
    assert _parametres_du_dag()["is_paused_upon_creation"].value is True


def test_lancement_horaire_et_meme_tag_que_le_quotidien():
    parametres = _parametres_du_dag()
    assert parametres["dag_id"].value == "supervision"
    assert parametres["schedule"].value == "@hourly"
    assert [e.value for e in parametres["tags"].elts] == ["dataflow360"]


def test_chaque_tache_creee_a_une_commande():
    assert set(_taches_creees()) == set(_commandes()) == {"surveiller_ventes", "surveiller_flux"}


def test_les_ventes_ne_jugent_que_la_journee_en_cours():
    assert _commandes()["surveiller_ventes"] == "<PREFIXE> -m compteurs.surveiller_ventes --jours 1"
    assert _commandes()["surveiller_flux"] == "<PREFIXE> -m supervision.surveiller_flux"


def test_aucune_tache_n_est_rejouee():
    reprises = _affectation("REPRISES")
    assert {k.value: v.value for k, v in zip(reprises.keys, reprises.values, strict=True)} == {
        "surveiller_ventes": 0,
        "surveiller_flux": 0,
    }


def test_le_flux_est_releve_meme_si_les_ventes_sont_en_alerte():
    options = _taches_creees()["surveiller_flux"]
    assert options["trigger_rule"].value == "all_done"


def test_les_ventes_passent_avant_le_flux():
    dependances = [
        n.value
        for n in _bloc_dag().body
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.BinOp)
    ]
    assert len(dependances) == 1
    dependance = dependances[0]
    assert isinstance(dependance.op, ast.RShift)
    assert (dependance.left.id, dependance.right.id) == ("surveiller_ventes", "surveiller_flux")
