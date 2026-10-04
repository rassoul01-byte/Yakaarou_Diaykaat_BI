# Contrat — Source fichiers : exports d'avis clients

**Statut** : brouillon, à valider par l'équipe avant tout code · **Responsable** : Seydina WADE · **Relecteur** : Mouhameth DIOP
**Sprint** : 4 · **Source** : « fichiers historiques », la cinquième des cinq sources du dossier
**Modules concernés** : `src/acquisition/`, `src/quality/`, `scripts/charger_boutique.py`, `sql/boutique/schema.sql`, `dags/quotidien.py`

## 1. Pourquoi ce contrat

Les avis clients arrivent aujourd'hui par la base boutique (source SQL), alors qu'ils représentent la source « fichiers historiques ». Tant que `order_reviews` reste dans la boutique, la même donnée entre par deux sources et l'argument des cinq sources tombe.

Ce contrat fait entrer les avis **uniquement** par dépôt de fichiers, et fait sortir `order_reviews` de la base boutique.

## 2. Le dépôt de fichiers

| Élément | Valeur |
|---|---|
| Dossier de dépôt | `data/sources/avis/` |
| Format | CSV, UTF-8, une ligne d'en-tête |
| Colonnes (7) | `review_id`, `order_id`, `review_score`, `review_comment_title`, `review_comment_message`, `review_creation_date`, `review_answer_timestamp` |
| Nombre de fichiers | un ou plusieurs : le contrat accepte N fichiers `*.csv` dans le dossier |
| Premier dépôt | copie de `data/sources/olist/olist_order_reviews_dataset.csv` (99 224 lignes) |

Le fichier d'origine reste dans `data/sources/olist/` : `scripts/download_data.py` continue de le télécharger et de le vérifier. Seule sa destination change.

## 3. Acquisition

```bash
docker compose exec app python -m acquisition --source avis
```

Même mécanique que la source rakuten : les CSV de `data/sources/avis/` sont copiés **à l'identique** vers

```
data/raw/lots/avis/ingestion=<AAAAMMJJTHHMMSS>/
```

avec un `manifeste.json`. Si le contenu est identique à la dernière ingestion, la commande répond « aucun changement depuis la dernière ingestion » et renvoie le code **0**. Toute autre erreur renvoie un code ≠ 0.

## 4. Contrôle de qualité

```bash
docker compose exec app python -m quality.controle --source avis --ingestion <identifiant>
```

Les trois règles d'avis quittent le contrôle d'olist et passent à la source `avis`. Leurs identifiants **ne changent pas** (`OLIST_AVIS_01`, `02`, `03`), pour ne pas casser l'historique de la quarantaine ni les vues de rejet.

| Règle | Gravité | Effet | Volume mesuré |
|---|---|---|---|
| `OLIST_AVIS_01` | bloquante | contrôle de l'identifiant d'avis `review_id` (fonction `controler_review_id`) ; texte exact de la condition à reporter depuis `rules.py` | 814 rejets |
| `OLIST_AVIS_02` | bloquante | une commande ne conserve qu'un seul avis | 243 rejets |
| `OLIST_AVIS_03` | non bloquante | l'absence de commentaire ne rejette pas l'avis, elle le marque | 57 612 marqués |

Résultat attendu pour le premier dépôt : 99 224 lignes lues, **98 167 valides**, **1 057 rejetées** (taux de rejet de 1,07 %, sous le seuil de 5 %). Les lignes valides sont écrites dans `staging.olist_order_reviews` : le nom de la table est conservé, aucune migration n'est nécessaire.

## 5. Sortie de `order_reviews` de la base boutique

| Élément | Avant | Après |
|---|---|---|
| Fichiers extraits par l'acquisition boutique | 9 | **8** |
| Lignes lues par la boutique | 1 550 922 | **1 451 698** |
| Rejets du contrôle olist | 1 073 | **16** (`OLIST_COMMANDES_02` : 8, `OLIST_ARTICLES_02` : 8) |
| Rejets de la source `avis` | — | **1 057** |

Fichiers à modifier : `src/acquisition/boutique.py` (liste des tables), `scripts/charger_boutique.py` (table chargée), `sql/boutique/schema.sql` (table), `src/quality/controle.py` (lecture et règles d'avis), `src/quality/chargement.py` (chargement du staging), la documentation (`src/acquisition/README.md`, `docs/contrats/quarantaine.md`, `docs/contrats/zones_stockage.md`) et les tests concernés.

⚠️ **Ces chiffres changent pour toute l'équipe** : les valeurs de référence du guide de mise à jour (1 073 rejets, 9 fichiers) ne sont plus valables après cette modification. Elle doit être annoncée avant la fusion.

## 6. Workflow quotidien

Deux tâches s'ajoutent au DAG, qui passe de neuf à onze tâches :

| Tâche | Commande |
|---|---|
| `acquisition_avis` | `python -m acquisition --source avis` |
| `controle_avis` | `python -m quality.controle --source avis --ingestion <dernière ingestion de data/raw/lots/avis>` |

`rapport_rejet` attend les trois contrôles (olist, rakuten, avis). `docs/contrats/workflow.md` est mis à jour dans la même PR.

## 7. Critères de réussite

- Une ingestion d'avis est vérifiable comme les autres : dossier horodaté, manifeste, 99 224 lignes lues.
- Relancer l'acquisition sans nouveau dépôt renvoie « aucun changement » avec le code 0, et ne crée aucune ingestion.
- Relancer le contrôle sur la même ingestion ne duplique pas la quarantaine.
- `python -m quality.rapport` affiche une ligne `avis` avec son taux de rejet.
- La base boutique ne contient plus `order_reviews`, et l'acquisition boutique ne lit plus que huit fichiers.
- `ruff check .`, `ruff format --check .` et `pytest` passent.

## 8. Hors périmètre

Aucune analyse de sentiment (Sprint 5). Aucun chargement des avis dans l'entrepôt ni dans MongoDB. Aucun changement de la source rakuten.

## 9. Points à trancher

- [ ] **Accord de l'équipe** sur la sortie de `order_reviews` de la boutique, avant tout code (impact sur les valeurs de référence).
- [ ] **Découpage de l'export** : un seul fichier, ou un fichier par mois pour montrer des dépôts successifs à la démonstration. Le contrat accepte les deux.
- [ ] **Règle `OLIST_AVIS_01`** : texte exact de la condition, à relire dans `src/quality/rules.py` (`git grep -n -A8 OLIST_AVIS_01 src/quality/rules.py`).
- [ ] **Droits de dépôt** : après alignement des droits sur l'utilisateur 50000, un dépôt depuis le poste hôte nécessite `docker compose cp` ou `sudo`. L'acquisition n'a besoin que de la lecture.
