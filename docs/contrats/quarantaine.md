# Contrat de quarantaine — F1.6

La quarantaine contient les enregistrements rejetés par le contrôle
qualité.

Une ligne de quarantaine doit permettre de répondre à quatre questions :

1. Quelle est la source ?
2. Quelle ingestion a produit le rejet ?
3. Quelle règle a été violée ?
4. Où retrouver l'enregistrement d'origine ?

## Contrat d'enregistrement

Chaque rejet fourni au module `quality.quarantaine` contient :

| Champ | Obligatoire | Description |
|---|---|---|
| `source` | Oui | Source de la donnée : `olist`, `rakuten`, `evenements`, etc. |
| `ingestion` | Oui | Identifiant de l'ingestion |
| `fichier` | Non | Fichier d'origine |
| `ligne_origine` | Non | Ligne ou position dans la source |
| `regle` | Oui | Identifiant de la règle violée |
| `gravite` | Oui | `bloquante` ou `non bloquante` |
| `donnees_brutes` | Oui | Enregistrement rejeté conservé tel quel |
| `horodatage` | Automatique | Date d'enregistrement du rejet |

## Stockage PostgreSQL

Les données sont stockées dans :

`quarantaine.rejets`

Le stockage conserve les noms historiques du schéma SQL :

- `regle` est stocké dans `regle_violee` ;
- `donnees_brutes` est stocké dans `enregistrement`.

La quarantaine est append-only : les anciens rejets ne sont pas supprimés
lors d'une nouvelle exécution du contrôle qualité.

## Enregistrement par lots

Le moteur de qualité appelle :

`quality.quarantaine.enregistrer_rejets()`

avec plusieurs rejets à la fois.

Le module utilise une insertion PostgreSQL par lots afin d'éviter un
INSERT séparé pour chaque ligne rejetée.

## Alimentation par le contrôle qualité

`quality.chargement.charger()` traduit les lignes rejetées par les règles
**bloquantes** du catalogue au format ci-dessus :

- `fichier` : nom du fichier dans l'ingestion (ex. `orders.csv`) ;
- `ligne_origine` : position de l'enregistrement dans ce fichier, à partir
  de 1, en-tête exclu ;
- `donnees_brutes` : l'enregistrement tel que lu dans la zone brute, une
  cellule vide devenant `null`.

L'insertion se fait dans la même transaction que le chargement de staging
et du journal (`enregistrer_rejets(..., valider=False)`).

**Relancer une ingestion** : la quarantaine étant append-only, rien n'est
supprimé ; les rejets d'une règle déjà enregistrés pour la même source et
la même ingestion ne sont pas réinsérés. Le journal de l'exécution compte
malgré tout les rejets détectés, pour que son taux de rejet reste exact.

## Consultation

Exemples :

```bash
docker compose exec app python -m quality.quarantaine --source olist --limite 20
docker compose exec app python -m quality.quarantaine --regle OLIST_AVIS_02

### 6. Test

Dans `tests/quality/test_quarantaine.py` :

```python
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


def test_enregistrer_rejets_vide_ne_se_connecte_pas():
    assert enregistrer_rejets([]) == 0