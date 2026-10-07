import numpy as np
import pandas as pd

from prediction.__main__ import afficher
from prediction.modele import entrainer, evaluer, influences

COLONNES = ["commandes", "montant_total", "recence_jours"]


def _jeu(n=600, graine=1):
    rng = np.random.default_rng(graine)
    commandes = rng.integers(1, 4, n)
    montant = commandes * rng.uniform(50, 150, n)
    recence = rng.integers(1, 300, n)
    probabilite = 0.02 + 0.08 * (commandes >= 2)
    cible = pd.Series((rng.random(n) < probabilite).astype(int))
    x = pd.DataFrame({"commandes": commandes, "montant_total": montant, "recence_jours": recence})
    return x, cible


def test_evaluer_remplit_le_classement():
    x, y = _jeu()
    ev = evaluer(entrainer(x, y), x, y)
    c = ev.classement
    assert c["revenus"] == int(y.sum())
    assert c["volume_regle"] == int((x["commandes"] >= 2).sum())
    assert 0 <= c["capture_part"] <= 1


def test_evaluer_sans_client_revenu_ne_plante_pas():
    x, y = _jeu()
    modele = entrainer(x, y)
    ev = evaluer(modele, x, pd.Series(np.zeros(len(x), dtype=int)))
    assert ev.classement == {}


def test_evaluer_est_reproductible():
    x, y = _jeu()
    a = evaluer(entrainer(x, y), x, y)
    b = evaluer(entrainer(x, y), x, y)
    assert a.classement == b.classement
    assert (a.rappel, a.precision, a.f1) == (b.rappel, b.precision, b.f1)


def test_les_mesures_existantes_ne_changent_pas():
    x, y = _jeu()
    ev = evaluer(entrainer(x, y), x, y)
    assert ev.vrais_positifs + ev.faux_negatifs == ev.positifs_reels
    assert set(ev.naives) == {"tous negatifs", "deux commandes ou plus"}


def test_le_rapport_affiche_le_classement_et_la_mise_en_garde(capsys):
    x, y = _jeu()
    modele = entrainer(x, y)
    afficher(evaluer(modele, x, y), influences(modele, x))
    sortie = capsys.readouterr().out
    assert "Qualité du classement" in sortie
    assert "À volume égal" in sortie
    assert "ne se\n  lisent pas un à un" in sortie
    assert "L'exactitude n'est pas calculée" in sortie


def test_le_rapport_sans_classement_reste_valide(capsys):
    x, y = _jeu()
    modele = entrainer(x, y)
    ev = evaluer(modele, x, pd.Series(np.zeros(len(x), dtype=int)))
    afficher(ev, influences(modele, x))
    assert "Qualité du classement" not in capsys.readouterr().out
