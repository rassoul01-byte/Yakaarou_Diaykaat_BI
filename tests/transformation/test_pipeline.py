"""Tests de pipeline.py, sans base de données réelle.

Comme tests/quality/test_quarantaine.py : de faux curseur et fausse connexion
vérifient que les bonnes requêtes partent avec les bons paramètres. Le
comportement réel contre PostgreSQL est à vérifier en conteneur — ces tests ne
le remplacent pas, voir README.md.
"""

from __future__ import annotations

import pandas as pd

from transformation.pipeline import (
    journaliser,
    transformer_categories,
    transformer_geolocation,
    transformer_rakuten,
)


class FauxCurseur:
    """Empile les requêtes exécutées ; répond aux deux formes utilisées ici :
    fetchone() après un SELECT COUNT(*), rowcount après un DELETE/UPDATE."""

    def __init__(self, comptage=None, rowcount=0):
        self.appels = []
        self._comptage = comptage
        self.rowcount = rowcount

    def execute(self, requete, params=None):
        self.appels.append(("execute", requete, params))

    def fetchone(self):
        return (self._comptage,)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FausseConnexion:
    def __init__(self, curseur):
        self._curseur = curseur
        self.commit_effectue = False
        self.rollback_effectue = False

    def cursor(self):
        return self._curseur

    def commit(self):
        self.commit_effectue = True

    def rollback(self):
        self.rollback_effectue = True

    def close(self):
        pass


def test_transformer_geolocation_compte_et_commit(monkeypatch):
    curseur = FauxCurseur(comptage=1_000_163, rowcount=261_831)
    cnx = FausseConnexion(curseur)

    resultat = transformer_geolocation(cnx)

    assert resultat.lignes_lues == 1_000_163
    assert resultat.lignes_supprimees == 261_831
    assert resultat.lignes_ecrites == 1_000_163 - 261_831
    assert cnx.commit_effectue is True
    requetes = [appel[1] for appel in curseur.appels]
    assert any("DELETE FROM staging.olist_geolocation" in r for r in requetes)
    assert any("SELECT COUNT(*)" in r for r in requetes)


def test_transformer_geolocation_second_passage_ne_supprime_rien():
    curseur = FauxCurseur(comptage=738_332, rowcount=0)
    cnx = FausseConnexion(curseur)

    resultat = transformer_geolocation(cnx)

    assert resultat.lignes_supprimees == 0
    assert resultat.lignes_ecrites == resultat.lignes_lues


def test_transformer_categories_normalise_et_ecrit(monkeypatch):
    lignes = pd.DataFrame(
        {
            "product_id": ["p1", "p2", "p3"],
            "product_category_name": ["Beauté Santé", None, "informatica"],
        }
    )
    monkeypatch.setattr("transformation.pipeline.pd.read_sql", lambda requete, cnx: lignes)
    appel = {}

    def faux_execute_values(curseur, requete, valeurs):
        appel["requete"] = requete
        appel["valeurs"] = valeurs

    monkeypatch.setattr("transformation.pipeline.execute_values", faux_execute_values)
    curseur = FauxCurseur(rowcount=3)
    cnx = FausseConnexion(curseur)

    resultat = transformer_categories(cnx)

    assert resultat.lignes_lues == 3
    assert resultat.lignes_ecrites == 3
    assert appel["valeurs"] == [
        ("p1", "beaute sante"),
        ("p2", None),
        ("p3", "informatica"),
    ]
    assert "UPDATE staging.olist_products" in appel["requete"]
    assert cnx.commit_effectue is True


def test_transformer_rakuten_decode_detecte_la_langue_et_signale_les_doublons(monkeypatch):
    lignes = pd.DataFrame(
        {
            "jeu": ["train", "train", "test"],
            "index_ligne": [1, 2, 3],
            "designation": [
                "id&eacute;es cr&eacute;atives",
                "id&eacute;es cr&eacute;atives",  # même désignation qu'au-dessus : signalé, pas supprimé
                "Stainless steel kitchen set, very practical",
            ],
            "description": ["<p>texte</p>", None, None],
        }
    )
    monkeypatch.setattr("transformation.pipeline.pd.read_sql", lambda requete, cnx: lignes)
    appel = {}

    def faux_execute_values(curseur, requete, valeurs):
        appel["requete"] = requete
        appel["valeurs"] = valeurs

    monkeypatch.setattr("transformation.pipeline.execute_values", faux_execute_values)
    curseur = FauxCurseur(rowcount=3)
    cnx = FausseConnexion(curseur)

    resultat = transformer_rakuten(cnx)

    # les désignations décodées, sans balisage
    valeurs = appel["valeurs"]
    assert valeurs[0][2] == "idées créatives"  # designation décodée
    assert valeurs[0][3] == "texte"  # description décodée, sans <p>
    assert resultat.lignes_ecrites == 3
    assert "2 désignation(s) dupliquée(s)" in resultat.message
    assert "non supprimées" in resultat.message
    assert cnx.commit_effectue is True


def test_journaliser_une_panne_ne_leve_pas(monkeypatch):
    import psycopg2

    from transformation.pipeline import ResultatTransformation

    def connexion_en_panne():
        raise psycopg2.OperationalError("base injoignable")

    monkeypatch.setattr("transformation.pipeline.connexion", connexion_en_panne)

    resultat = ResultatTransformation("test", 10, 10, 0, "ok")
    journaliser(resultat, "olist")  # ne doit lever aucune exception


def test_le_compte_des_lignes_modifiees_couvre_toutes_les_pages(monkeypatch):
    # Régression : execute_values découpe en pages de 100 et rowcount ne
    # gardait que la dernière (16 fiches annoncées sur 84 916).
    curseur = FauxCurseur()

    def faux_execute_values(curseur, requete, valeurs):
        curseur.appels.append(("execute_values", requete, valeurs))
        curseur.rowcount = len(valeurs)

    monkeypatch.setattr("transformation.pipeline.execute_values", faux_execute_values)
    monkeypatch.setattr(
        "transformation.pipeline.pd.read_sql",
        lambda *_args, **_kwargs: pd.DataFrame(
            {"product_id": [f"p{i}" for i in range(250)], "product_category_name": ["Beleza"] * 250}
        ),
    )

    resultat = transformer_categories(FausseConnexion(curseur))

    assert resultat.lignes_ecrites == 250
    assert [len(appel[2]) for appel in curseur.appels] == [100, 100, 50]
