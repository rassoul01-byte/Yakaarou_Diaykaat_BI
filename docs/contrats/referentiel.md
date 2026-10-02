# Contrat — Service référentiel

**Responsable :** Ndeye Penda SARR · **Relectrice :** Aissata DIALLO
**Source :** API — la cinquième des cinq sources du projet
**Module :** `src/referentiel/` · **Service :** `referentiel`

---

## 1. Ce que c'est

Deux données que la plateforme ne produit pas et ne peut pas deviner :

- **les jours fériés brésiliens**, qui expliquent les creux de ventes ;
- **les taux de change historiques du réal**, qui permettent d'afficher le chiffre d'affaires en euros.

Elles viennent de deux services publics gratuits, sans clé d'authentification :

| Service | Ce qu'il fournit |
|---|---|
| **BrasilAPI** — `brasilapi.com.br/api/feriados/v1/{annee}` | Les jours fériés nationaux d'une année |
| **Frankfurter** — `api.frankfurter.dev` | Les taux quotidiens de la Banque centrale européenne, réal compris |

---

## 2. Pourquoi un service local plutôt que des appels directs

**La plateforme n'appelle jamais un service extérieur.** Elle interroge un service local, alimenté une fois, qui sert ce qui a été conservé dans la zone brute.

Trois raisons :

- **La démonstration fonctionne sans Internet.** Le jour de la soutenance, quinze personnes partagent la même connexion : un appel qui part dehors est un risque inutile.
- **La chaîne reste rejouable.** Les réponses brutes sont conservées comme n'importe quelle autre source : si un service public disparaît, les données restent.
- **C'est ce qui se fait en entreprise.** On ne s'adresse pas au fournisseur externe depuis chaque module ; on passe par un service interne qui centralise et met en cache.

---

## 3. Les routes

| Route | Ce qu'elle renvoie |
|---|---|
| `GET /sante` | Ce que le service a en mémoire : années disponibles, nombre de taux par devise |
| `GET /feries/{annee}` | Les jours fériés de l'année, tels que BrasilAPI les a renvoyés |
| `GET /taux?date=AAAA-MM-JJ&devise=EUR` | Le taux du réal vers la devise, à cette date |

### Un exemple de chaque

```json
GET /feries/2017
{
  "annee": 2017,
  "nombre": 12,
  "feries": [{ "date": "2017-02-28", "name": "Carnaval", "type": "national" }]
}
```

```json
GET /taux?date=2017-03-18
{
  "date_demandee": "2017-03-18",
  "date_effective": "2017-03-16",
  "base": "BRL",
  "devise": "EUR",
  "taux": 0.3038
}
```

⚠️ **`date_demandee` et `date_effective` peuvent différer**, et c'est normal : les marchés de change ne cotent ni les week-ends ni les jours fériés bancaires. Le service renvoie alors le taux du **dernier jour ouvré précédent**, et dit lequel. Un montant converti doit toujours pouvoir être expliqué.

### Les erreurs

| Cas | Réponse |
|---|---|
| Année non conservée | `404`, avec la commande à lancer pour l'obtenir |
| Devise non conservée | `404` |
| Date antérieure à tout ce qui est conservé | `404` |

Le service **ne va jamais chercher** ce qui lui manque : il ne sort pas sur Internet.

---

## 4. Alimenter le service

À lancer **une fois, en ligne** :

```bash
docker compose exec app python scripts/alimenter_referentiel.py
docker compose exec app python scripts/alimenter_referentiel.py --annees 2016 2017 2018
docker compose exec app python scripts/alimenter_referentiel.py --forcer
```

Les réponses sont conservées telles quelles dans la zone brute :

```
data/raw/referentiel/
├── feries/annee=2016.json
├── feries/annee=2017.json
├── feries/annee=2018.json
└── taux/BRL-EUR_2016-09-01_2018-10-31.json
```

La période des taux couvre l'historique Olist, de septembre 2016 à octobre 2018.

**Codes de sortie :** 0 si tout est conservé, 1 si un service public n'a pas répondu — les données déjà conservées restent alors utilisables.

---

## 5. Interroger le service depuis un autre module

Personne n'écrit d'appel HTTP à la main :

```python
from datetime import date
from referentiel.client import jours_feries, taux_du_jour

feries = jours_feries(2017)          # [date(2017, 1, 1), date(2017, 2, 28), …]
taux = taux_du_jour(date(2017, 3, 15))   # 0.3024
```

`jours_feries` renvoie des dates, directement utilisables pour la colonne « jour férié » de `dim_date`. L'adresse du service se règle par la variable `REFERENTIEL_URL`, dont la valeur par défaut est celle du conteneur.

---

## 6. Ce que cette source n'est pas

**Ce n'est pas une source de données métier.** Les jours fériés et les taux **enrichissent** la donnée des ventes ; ils ne la remplacent pas et n'en produisent aucune. Aucun indicateur ne se calcule à partir d'eux seuls.

**Le taux appliqué est celui du jour de la commande**, jamais le taux du jour où l'on consulte le tableau de bord. Un chiffre d'affaires converti doit rester le même d'un mois sur l'autre.

---

## 7. Faire évoluer le contrat

Ajouter une route ou une devise se fait par une demande de fusion sur ce document **et** sur `src/referentiel/`. La période couverte par les taux suit l'historique des commandes : si l'historique s'étend, la période aussi.
