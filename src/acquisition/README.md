# acquisition — la source SQL

**Responsable :** Mouhameth DIOP · repris pour le Sprint 1 par Ndeye Penda
**Fonctionnalité :** F1.1 · **Source :** SQL — la base `boutique`

Ce module lit le **système de gestion de l'e-commerçant** et dépose ce qu'il lit
dans la zone brute, sans rien transformer.

## Les deux moitiés

**La source** — une base PostgreSQL `boutique`, distincte de `dataflow360`,
remplie une fois par `scripts/charger_boutique.py`. Sa structure est dans
`sql/boutique/schema.sql`. Ce script **ne fait pas partie du pipeline** : il
simule l'existence du système de la boutique.

**L'acquisition** — `python -m acquisition` extrait les huit tables par
requêtes SQL et écrit le résultat dans
`data/raw/lots/boutique/ingestion=<horodatage>/`, avec son manifeste.

```bash
docker compose exec app python scripts/charger_boutique.py   # une seule fois
docker compose exec app python -m acquisition
docker compose exec app python -m acquisition --depuis 2018-01-01
```

## Ce qu'il faut savoir

| | |
|---|---|
| **La lecture de la source est isolée** | Tout ce qui sait que les données viennent d'une base est dans `boutique.py`. Le reste ignore leur provenance : au Sprint 2, les fichiers d'avis réutiliseront `ingestion.py` sans le modifier |
| **Rien n'est écrit si rien n'a changé** | L'extraction est préparée à l'écart, ses empreintes comparées à celles de la dernière ingestion, et déplacée seulement si elle apporte du nouveau |
| **Le manifeste n'est pas recalculé ici** | Il est construit par `zone_brute.manifeste`, celui d'Aissata : la compatibilité avec sa vérification est garantie par construction |
| **La connexion est déduite** | Même serveur que la plateforme, autre base. `BOUTIQUE_DSN` permet de pointer ailleurs si la source déménage |
| **`--depuis` ne filtre que les commandes** | Les référentiels — produits, vendeurs, catégories — n'ont pas de date de création : ils sont toujours extraits en entier |
| **Le journal n'est pas bloquant** | Une panne de journalisation est signalée, pas fatale : les données sont déjà dans la zone brute |

## Ce que le module ne fait pas

Aucun contrôle de qualité, aucune transformation, aucun chargement dans la zone
intermédiaire : la zone brute reçoit la donnée **telle qu'elle est dans la
boutique**. Le contrôle arrive au Sprint 2.
