# Contrat — Index de recherche du catalogue

**Fonctionnalité :** F4.1 — Indexer le catalogue produits
**Responsable :** Ndeye Penda SARR · **Relecteur :** Bachir DEME
**Module :** `src/recherche/indexation.py` · **Service :** `elasticsearch`

---

## 1. Ce que l'index contient

Une entrée par fiche du catalogue nettoyé, soit **84 916 documents**, lus dans `staging.rakuten_produits` **après transformation** — balisage décodé, langue détectée.

⚠️ **Jamais depuis la zone brute.** L'index sert la recherche d'un acheteur : il ne doit contenir que des données contrôlées et normalisées. Une fiche dont la désignation porte encore `id&eacute;es` ne doit pas être indexée.

---

## 2. Le document indexé

| Champ | Type Elasticsearch | Source | Rôle |
|---|---|---|---|
| `product_id` | `keyword` | `productid` | Identifiant d'origine, jamais analysé |
| `index_ligne` | `integer` | `index_ligne` | Position d'origine dans le catalogue |
| `designation` | `text` (analyseur `francais`) | `designation` | **Le champ de recherche principal** |
| `description` | `text` (analyseur `francais`) | `description` | Recherche secondaire, souvent vide |
| `categorie_code` | `keyword` | `prdtypecode` | **Filtre** par catégorie |
| `langue` | `keyword` | `langue` | Filtre, et diagnostic |
| `a_description` | `boolean` | calculé | 35 % des fiches n'en ont pas : le savoir évite d'interpréter un silence |

**`keyword` ou `text`, et pourquoi.** Un champ `text` est découpé en mots pour la recherche ; un champ `keyword` est conservé tel quel pour filtrer et compter. Chercher « lampe » dans une désignation exige `text` ; filtrer sur la catégorie 2060 exige `keyword`. Se tromper de type rend le champ inutilisable dans l'un des deux usages.

---

## 3. L'analyseur

Un analyseur `francais` : minuscules, suppression des accents, mots vides français, et racinisation légère.

**Ce qu'il permet concrètement :**

- `LAMPE`, `lampe` et `Lampe` donnent le même résultat ;
- `éclairage` est trouvé par `eclairage` — c'est ce qui sauve les recherches tapées sans accent ;
- `lampes` trouve `lampe`.

⚠️ **La tolérance aux fautes de frappe n'est pas ici.** `bureu` → `bureau` relève de la requête, pas de l'index : c'est le livrable de Bachir (F4.2). L'index fournit les champs, la requête décide de sa souplesse.

---

## 4. Les commandes

```bash
docker compose exec app python -m recherche.indexer
docker compose exec app python -m recherche.indexer --recreer
docker compose exec app python -m recherche.etat
```

| Commande | Ce qu'elle fait |
|---|---|
| `indexer` | Indexe tout le catalogue. **Idempotente** : relancer deux fois donne le même index |
| `indexer --recreer` | Supprime l'index et le reconstruit — à utiliser quand la structure change |
| `etat` | Nombre de documents, taille de l'index, date de dernière indexation |

**Codes de sortie :** 0 si l'index est conforme, 1 si le nombre de documents indexés diffère du nombre de fiches en zone intermédiaire. C'est ce code que la tâche Airflow lit.

L'identifiant du document est **`jeu:index_ligne`**, la clé primaire de la
table d'origine — et non `product_id`, dont rien ne garantit l'unicité dans le
catalogue. Réindexer écrase donc la fiche au lieu d'en créer une seconde :
**c'est tout le mécanisme d'idempotence de ce module**, il n'y en a pas d'autre.
---

## 5. Ce que le moteur de recherche peut attendre

C'est la partie qui engage vis-à-vis de Bachir. **Elle est figée** : son moteur peut être écrit contre ce contrat avant que l'index n'existe.

- **Nom de l'index** : `catalogue`
- **Adresse** : `http://elasticsearch:9200`, variable `ES_URL`
- **Recherche plein texte** sur `designation` et `description`, la désignation pesant davantage
- **Filtres** sur `categorie_code` et `langue`
- **Chaque résultat** porte `product_id`, `designation`, `categorie_code`, et le score attribué par Elasticsearch

Un index d'essai de vingt fiches aux mêmes champs suffit pour développer et tester le moteur.

---

## 6. Critères de réussite

- **84 916 documents** indexés, soit le nombre de fiches en zone intermédiaire.
- Une recherche sur un mot **accentué sans accent** trouve les fiches correspondantes — c'est le décodage du Sprint 2 qui le permet.
- **Réindexer deux fois** donne exactement le même nombre de documents.
- `--recreer` sur un index existant n'en laisse aucune trace de l'ancien.
- Le **temps de réponse** d'une recherche simple reste sous la seconde.
- La mémoire d'Elasticsearch est relevée **après indexation** et transmise à l'équipe.

⚠️ **Le point de vigilance du sprint** : Elasticsearch est limité à 512 Mo de tas par la composition, et occupait déjà 1,03 Go au repos. 84 916 documents vont le faire grossir. **Ne touchez pas à `ES_JAVA_OPTS` sans en parler au groupe** : c'est la mémoire de tout le monde.

---

## 7. Ce qui n'est pas dans ce livrable

La tolérance aux fautes de frappe, les filtres de prix, les requêtes sans résultat : **F4.2, F4.3 et F4.5, chez Bachir**. L'index fournit la matière, pas l'intelligence de la recherche.

La réindexation automatique dans Airflow — **F4.7** — appelle la commande décrite ici ; la tâche elle-même est un autre livrable. (F4.6 est une autre fonctionnalité : mesurer l'évolution du taux de requêtes sans résultat. Les deux ont été confondues pendant le Sprint 4 ; le backlog fait foi.)

---

## 8. Faire évoluer le contrat

Ajouter un champ se fait par une demande de fusion sur ce document **et** sur le module. ⚠️ **Tout changement de structure impose un `--recreer`** : Elasticsearch ne modifie pas le type d'un champ existant. C'est la raison pour laquelle cette structure est discutée avant d'être écrite, et non l'inverse.
