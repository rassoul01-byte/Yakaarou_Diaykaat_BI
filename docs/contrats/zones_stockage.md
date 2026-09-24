# Contrat — Règles des zones de stockage

**Auteur : Seydina WADE · Attendu par : Mouhameth (Livrable 5) · Sprint 1**

Ce document fixe les règles de vie des trois zones de PostgreSQL —
quarantaine, intermédiaire, entrepôt — et les conventions de migration
qui les font évoluer. Il doit être lu avant d'écrire la moindre requête
qui modifie leur structure.

## 1. La règle d'or de chaque zone

Les trois zones ne suivent pas la même règle : les confondre est l'erreur
la plus coûteuse qu'on puisse faire sur ce périmètre.

| Zone | Schéma PostgreSQL | Règle |
|---|---|---|
| Quarantaine | `quarantaine` | **Jamais purgée.** Un enregistrement rejeté y reste pour toute la durée du projet, au même titre que la zone brute ne modifie jamais un fichier. |
| Intermédiaire | `staging` | **Écrasée à chaque exécution.** Elle ne contient que le résultat du dernier passage du pipeline — ce n'est pas un historique, c'est un espace de travail. |
| Entrepôt | `dwh` | **Historisée.** Modèle en étoile : les faits s'accumulent, les dimensions évoluent sans perdre les versions passées (Sprint 3, Aissata). |

## 2. La zone de quarantaine

### Ce qu'elle contient

`quarantaine.rejets` est une table unique, générique à toutes les
sources — pas une table par fichier comme la zone intermédiaire. Un
enregistrement rejeté, quelle que soit sa provenance (Olist, Rakuten,
flux d'événements), y prend la même forme :

| Colonne | Rôle |
|---|---|
| `source` | D'où vient l'enregistrement (`olist`, `rakuten`, `navigation.evenements`) |
| `fichier` | Nom du fichier d'origine, quand il y en a un |
| `ligne_origine` | Numéro de ligne ou position dans la source |
| `regle_violee` | Identifiant de la règle de qualité enfreinte (catalogue de règles, F1.5) |
| `gravite` | `bloquant` ou `avertissement` |
| `enregistrement` | L'enregistrement rejeté tel quel, en JSON |
| `horodatage` | Quand le rejet a eu lieu |

### Pourquoi une table générique plutôt qu'une table par source

La zone intermédiaire distingue une table par fichier source, parce
qu'elle sert à charger des données structurées vers l'entrepôt : les
types précis y comptent. La quarantaine, elle, sert à **examiner ce qui
n'est pas rentré** — sa forme importe moins que sa traçabilité. Une
table unique en JSON évite d'avoir à faire évoluer son schéma à chaque
nouvelle source, et permet de calculer le taux de rejet (F1.11) toutes
sources confondues, d'une seule requête.

### Qui y écrit, qui la lit

- **Écriture** : le contrôle de conformité (F1.5, Sprint 2) et la
  validation du flux d'événements (`src/common/evenements.py`, niveau 4
  de la stratégie de qualité) y insèrent chaque rejet.
- **Lecture** : le calcul du taux de rejet (F1.11) et toute
  investigation manuelle sur un rejet précis.
- **Jamais de suppression ni de mise à jour** : conforme à la règle
  d'or de la section 1. Corriger une règle de qualité ne réécrit pas
  les rejets passés, elle change seulement le comportement futur.

## 3. La zone intermédiaire

### Ce qu'elle contient

Le schéma `staging` regroupe une table par fichier source, avec des
types explicites plutôt que du texte brut :

- `olist_orders`, `olist_order_items`, `olist_products`,
  `olist_customers`, `olist_geolocation`, `olist_order_payments`,
  `olist_order_reviews`, `olist_sellers` — une table par fichier du
  jeu de données Olist.
- `rakuten_produits` — catalogue produits Rakuten (SIGIR eCom 2020),
  train et test réunis, distingués par la colonne `jeu`.
- `product_category_translation` — référentiel fixe fourni avec le
  jeu de données Olist, inclus ici par simplicité.
- `execution_log` — table de suivi des exécutions, distincte des
  tables de données : elle n'est jamais écrasée, elle s'enrichit
  d'une ligne par exécution (voir section 5).

### La convention de typage

- Un identifiant, un code postal, ou tout champ qui peut commencer par
  un zéro reste en `TEXT` — jamais en nombre.
- Une date avec heure en `TIMESTAMP`, une date seule en `DATE`.
- Un montant en `NUMERIC`, jamais en `FLOAT` : un flottant arrondit,
  un `NUMERIC` conserve la valeur exacte.
- Une clé primaire quand la source en fournit une identifiable ;
  une clé composite quand une ligne n'est unique que par la
  combinaison de plusieurs champs (ex. `order_id` +
  `payment_sequential`).

### Ce qui se passe à un nouveau lancement

Cette zone est **écrasée à chaque exécution** du pipeline (Sprint 2,
contrôle de qualité) : elle ne contient que le résultat du dernier
passage, pas un historique des passages précédents. Concrètement, le
chargement videra chaque table avant d'y écrire les lignes validées de
l'exécution en cours — pas de fusion, pas d'ajout incrémental à ce
niveau.

Aucune clé étrangère ne relie les tables entre elles ici : les
contraintes référentielles strictes sont réservées à l'entrepôt
(section 4), où elles ont un sens durable.

## 4. L'entrepôt

Le schéma `dwh` est réservé à ce stade : ce Livrable fixe seulement ses
conventions de nommage. Sa construction — le modèle en étoile lui-même
— revient à Aissata au Sprint 3.

### Ce qui est fixé maintenant

- **Table de faits** : préfixe `fait_`, ex. `fait_commandes`,
  `fait_evenements_navigation`. Une ligne par événement métier
  mesurable (une commande passée, une page vue).
- **Table de dimension** : préfixe `dim_`, ex. `dim_client`,
  `dim_produit`, `dim_date`. Un attribut qui décrit le contexte d'un
  fait, et qui varie plus lentement que lui.
- **Clé de substitution** : chaque dimension porte une clé technique
  `<nom>_id`, générée, distincte de l'identifiant métier d'origine
  (ex. `dim_client.client_id` généré, différent de
  `customer_unique_id` conservé comme attribut).

### Ce qui n'est pas fixé ici

Le détail des colonnes, le grain de chaque table de fait, le type
exact de la clé de substitution, et le traitement des dimensions à
évolution lente restent des décisions du Sprint 3. Ce document ne fixe
qu'un vocabulaire commun, pour qu'aucune table de l'entrepôt ne soit
nommée autrement que par ce préfixe une fois la construction commencée.

### Pourquoi une historisation, contrairement à l'intermédiaire

L'entrepôt s'accumule plutôt que de s'écraser : un tableau de bord doit
pouvoir répondre à « combien de commandes le 3 mars » aussi bien après
la commande suivante qu'avant. C'est ce qui distingue son rôle de celui
de la zone intermédiaire, qui n'existe que pour préparer le prochain
chargement.

## 5. Les migrations

### Pourquoi ce mécanisme

Le script d'initialisation du Sprint 0
(`docker/postgres/init/01-databases.sql`) ne s'exécute qu'une fois, au
tout premier démarrage d'un volume PostgreSQL vide. Pour faire évoluer
la structure des trois zones ensuite — ajouter une table, renommer un
schéma — il faudrait sinon tout effacer avec
`docker compose down -v`, en perdant au passage toute donnée déjà
chargée. Les migrations numérotées évitent ce piège : chacune ne
s'applique qu'une fois, et s'ajoute aux précédentes sans jamais tout
recommencer.

### Convention de nommage

Un fichier par migration, dans `sql/`, numéroté sur trois chiffres et
suivi d'une courte description :
sql/
├── 001_quarantaine.sql
├── 002_intermediaire.sql
└── 003_intermediaire_rakuten.sql

- Le numéro fixe l'ordre d'application — il n'est jamais réutilisé,
  même si une migration est retirée avant d'être fusionnée sur
  `develop`.
- La description tient en un ou deux mots, à la source ou au schéma
  concerné plutôt qu'à la date ou à son auteur.
- Une migration ne modifie qu'un seul souci à la fois : renommer un
  schéma, ou ajouter les tables d'une source, pas les deux — c'est ce
  qui rend chaque PR courte à relire.

### Comment elles s'appliquent

`public.schema_migrations` garde la trace des migrations déjà
appliquées : une ligne par fichier, avec la date. `scripts/appliquer_sql.py`
compare les fichiers de `sql/` à cette table, dans l'ordre, et
n'exécute que ceux qui n'y figurent pas encore.

```bash
PYTHONPATH=src python3 scripts/appliquer_sql.py
```

Lancé une seconde fois sans nouveau fichier, il ne rejoue rien :
[SKIP] 001_quarantaine.sql
[SKIP] 002_intermediaire.sql
[SKIP] 003_intermediaire_rakuten.sql
Migrations terminées.

### Ce qu'une migration ne fait jamais

- Elle ne supprime ni ne modifie une migration déjà appliquée : une
  erreur se corrige par une nouvelle migration, jamais en réécrivant
  un fichier numéroté déjà fusionné sur `develop`.
- Elle ne contient aucune donnée de test ni de démonstration : les
  migrations façonnent la structure, jamais le contenu.
