from quality.quarantaine import enregistrer_rejets


class FauxCurseur:
    description = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FausseConnexion:
    def __init__(self):
        self.commit_effectue = False
        self.rollback_effectue = False
        self.fermee = False

    def cursor(self):
        return FauxCurseur()

    def commit(self):
        self.commit_effectue = True

    def rollback(self):
        self.rollback_effectue = True

    def close(self):
        self.fermee = True


def test_enregistrer_rejets_accepte_un_lot(monkeypatch):
    connexion = FausseConnexion()
    appel = {}

    def faux_execute_values(curseur, requete, lignes, page_size):
        appel["lignes"] = lignes
        appel["page_size"] = page_size
        appel["requete"] = requete

    monkeypatch.setattr(
        "quality.quarantaine.execute_values",
        faux_execute_values,
    )

    rejets = [
        {
            "source": "olist",
            "ingestion": "olist-2026-09-28-001",
            "fichier": "olist_orders_dataset.csv",
            "ligne_origine": 42,
            "regle": "OLIST_COMMANDES_01",
            "gravite": "bloquante",
            "donnees_brutes": {"order_id": "abc"},
        },
        {
            "source": "olist",
            "ingestion": "olist-2026-09-28-001",
            "fichier": "olist_orders_dataset.csv",
            "ligne_origine": 51,
            "regle": "OLIST_COMMANDES_02",
            "gravite": "non bloquante",
            "donnees_brutes": {"order_id": "def"},
        },
    ]

    resultat = enregistrer_rejets(rejets, connexion=connexion)

    assert resultat == 2
    assert len(appel["lignes"]) == 2
    assert appel["page_size"] == 500
    assert "INSERT INTO quarantaine.rejets" in appel["requete"]
    assert connexion.commit_effectue is True


def test_enregistrer_rejets_vide():
    assert enregistrer_rejets([]) == 0