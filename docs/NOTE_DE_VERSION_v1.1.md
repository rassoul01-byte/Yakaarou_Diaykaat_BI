# Note de version — v1.1

**Nataal Retail** · GROUPE 2 · Orange Digital Center, promotion 8
**Version :** v1.1, version de clôture après le Sprint 5
**Précédente :** v1.0 (fin du Sprint 5, 10 octobre 2026)

v1.1 n'ajoute aucun besoin : les cinq besoins étaient couverts en v1.0. Elle rassemble les six demandes de fusion intégrées depuis (#142 à #147) : le nom du projet, des correctifs de l'environnement de test, l'orchestration de la surveillance, la documentation de clôture et un tableau de bord dont les deux derniers chiffres écrits à la main sont désormais calculés.

> **En une phrase.** La même plateforme qu'en v1.0, sous le nom Nataal Retail, avec une surveillance horaire orchestrée et un tableau de bord qui ne contient plus aucun chiffre écrit en dur.

---

## Ce que couvre la version

| # | Besoin | État dans v1.1 |
|---|---|---|
| 1 | Un référentiel unique, contrôlé et fiable | Livré (depuis v0.4) |
| 2 | Piloter l'activité en quasi temps réel | Livré (depuis v0.5) ; **nouveau** : alerte sur les ventes et retard du flux lancés chaque heure par le DAG `supervision` |
| 3 | Anticiper le départ des clients | Livré (depuis v1.0) |
| 4 | Une recherche produit pertinente | Livré (depuis v0.5) ; sans filtre de prix |
| 5 | Alléger le service client | Livré (depuis v1.0) |

---

## Nouveautés depuis v1.0

### Nom du projet : Nataal Retail (#142)

- Le projet s'appelle désormais **Nataal Retail** dans tout ce qui s'affiche : titre de l'onglet et métadonnées de l'application web, barre du haut, assistant, vue générale, titres des deux API, README et documentation.
- **Aucun identifiant technique n'a changé** : dépôt `Yakaarou_Diaykaat_BI`, base `dataflow360`, services et images Docker, sujets et groupes Kafka, index Elasticsearch, variables d'environnement, chemins. Les migrations SQL déjà appliquées ne sont pas modifiées.

### Orchestration de la surveillance (#144)

- **Second DAG Airflow, `supervision`** (`dags/supervision.py`) : chaque heure, `compteurs.surveiller_ventes --jours 1`, puis `supervision.surveiller_flux`.
- La supervision horaire juge **la journée en cours** ; les jours passés restent visibles dans l'alerte de la vue générale et par la commande lancée à la main.
- `surveiller_flux` part même si les ventes sont en alerte (`all_done`) : une chute des ventes ne masque pas un consommateur arrêté.
- Aucune reprise (`retries=0`) : une alerte est un verdict, pas une panne. Pas de rattrapage au démarrage (`catchup=False`, `max_active_runs=1`).
- Le DAG est **en pause à sa création** (`is_paused_upon_creation=True`) : il ne tourne qu'une fois activé dans Airflow.
- La séquence de démonstration et son plan de secours sont dans `docs/SEQUENCE_DEMO.md`.

### Tableau de bord (#147)

- **Les deux chiffres écrits en dur sont branchés sur les vues** : le taux de réponses ancrées de la page « Assistant » lit `staging.v_taux_ancrage_global`, le verdict de l'alerte de la page « Temps réel » lit `staging.v_alerte_ventes`. Ils suivent désormais le rafraîchissement.
- **Thème Nataal Retail** : `dashboards/theme/nataal-retail-theme.json`, et pages titrées « Nataal Retail ».
- Les six captures de `docs/captures/` sont mises à jour dans la même demande de fusion que le tableau de bord.

### Environnement de test et workflow (#143)

- `docker compose exec app python -m pytest`, la commande de vérification du README, s'exécute désormais en entier : le conteneur `app` monte `dags/` et le script d'initialisation de PostgreSQL, que deux fichiers de tests lisent.
- Commentaire du DAG `quotidien` corrigé : le seuil de rejet s'exprime en pourcentage (`airflow variables set seuil_rejet 5`).
- README : ports 8001 et 5173 ajoutés à la vérification des ports ; migrations à appliquer (`python scripts/appliquer_sql.py`) après chaque `git pull` et avant de lancer le DAG.

### Documentation de clôture (#145, #146)

- README : Sprint 5 clos, état final du projet.
- Dossier de conception, `ROLES.md`, script de la vidéo et commentaires de l'intégration continue alignés sur le dépôt : décompte des tests, tests restés hors CI (MinIO, écarté du projet, n'en concerne aucun), crédit de la source NoSQL, causes des transferts de livrables, qui a réalisé quoi d'après l'historique Git, orchestration de la surveillance.
- Rôle d'Aissata DIALLO décrit selon la formulation qu'elle a validée : relectrice à distance depuis le Sprint 3.
- `A_LIRE.md` supprimé.

---

## Chiffres vérifiés

Relevés sur `develop` au commit `a145e16`, le dernier avant cette note.

| Mesure | Valeur | Source |
|---|---|---|
| Tests | **948** : 816 unitaires, 132 d'intégration | `pytest --collect-only` |
| Tests d'intégration lancés en CI | 85 (PostgreSQL) | `pytest --collect-only -m integration tests/integration tests/indicateurs tests/quality` |
| Tests d'intégration hors CI | 47 (Elasticsearch, Kafka, base PostgreSQL préparée) | 132 − 85 |
| Intégration continue | **Verte sur les 3 jobs** : `controle`, `integration-postgres`, `frontend` | GitHub Actions, exécution 38157194188 sur `a145e16` |
| DAG Airflow | 2 : `quotidien` (13 tâches, `@daily`), `supervision` (2 tâches, `@hourly`, en pause à la création) | `dags/` |

Depuis v1.0, les 8 nouveaux tests sont ceux de `tests/dags/test_supervision.py`.

---

## Limites connues

Ce que v1.1 change par rapport aux limites de v1.0 :

- **Corrigée** — tableau de bord : le taux de réponses ancrées et le verdict de l'alerte ne sont plus écrits à côté des visuels (#147).
- **Réduite** — surveillance : elle est orchestrée, mais le DAG `supervision` est en pause à sa création, et une fois activé, une alerte ne se voit que par sa tâche rouge dans Airflow, sans autre notification.
- **Inchangée** — 47 tests d'intégration ne tournent qu'en local.
- **Inchangée** — les tests d'intégration du bus publient sur les vrais sujets Kafka et laissent des groupes de lecture `test-*`, à supprimer avant une démonstration (commande dans `docs/SEQUENCE_DEMO.md`).

Les autres limites de la note v1.0 restent valables.

---

## Équipe

| Membre | Rôle de conduite | Part de la v1.1 |
|---|---|---|
| Ndeye Penda SARR | Conception et documentation | Auteure des 30 commits de la version : renommage, correctifs, DAG `supervision`, documentation de clôture, tableau de bord |
| Mouhameth DIOP | Scrum Master | Relecture et fusion de #142 et #143 |
| Seydina WADE | — | Relecture et fusion de #146 |
| Aissata DIALLO | Relectrice à distance depuis le Sprint 3 | Relecture et fusion de #144, #145 et #147 |
| Bachir DEME | Product Owner | — |

---

## Démarrer et vérifier

Le démarrage de la plateforme, les deux DAG et la vérification sont décrits dans le [README](../README.md) ; la démonstration de la supervision dans [`SEQUENCE_DEMO.md`](SEQUENCE_DEMO.md).

## Historique des versions

| Version | Contenu |
|---|---|
| v0.1 | Sprint 0 — organisation et préparation |
| v0.2 | Sprint 1 — acquisition et stockage brut |
| v0.3 | Sprint 2 — qualité et transformation |
| v0.4 | Sprint 3 — entrepôt, indicateurs et orchestration |
| v0.5 | Sprint 4 — temps réel, recherche et supervision |
| v1.0 | Sprint 5 — intelligence artificielle et finalisation |
| **v1.1** | **Clôture — Nataal Retail, surveillance orchestrée, tableau de bord sans chiffre en dur** |
