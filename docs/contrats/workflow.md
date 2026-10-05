# Contrat du workflow quotidien

**Statut** : brouillon à jour au 2 octobre 2026 · **Auteur** : Seydina WADE · **Relectrice** : Ndeye Penda SARR · **Fonctionnalité** : F6.1
**Fichier du workflow** : `dags/quotidien.py` · **Identifiant Airflow** : `quotidien`

Ce document fixe, avant que les autres livrables n'existent, le nom de chaque commande, l'ordre des tâches et ce qui compte comme un échec. Chaque livrable du Sprint 3 doit se terminer par la commande listée ici.

## 1. Ordre des tâches (neuf tâches)

```
acquisition (boutique) ──► contrôle olist ───┐
                                             ├──► rapport de rejet (seuil 5 %) ──► transformation
acquisition rakuten ────► contrôle rakuten ──┘                                          │
                                                                                        ▼
                                     vérification ◄── chargement ◄── correspondance ◄───┘
```

Les deux branches (olist et rakuten) s'exécutent en parallèle jusqu'au rapport de rejet. La transformation d'olist et celle de rakuten s'enchaînent dans la même tâche.

## 2. Tâches, commandes et conditions d'échec

| # | Tâche | Commande | Échec si | État | Durée mesurée |
|---|-------|----------|----------|------|---------------|
| 1a | `acquisition` | `python -m acquisition --source boutique` | code ≠ 0 | branchée | ~4 s |
| 1b | `acquisition_catalogue` | `python -m acquisition --source catalogue` | code ≠ 0 | branchée | ~3 s |
| 2a | `controle_olist` | `python -m quality.controle --source olist --ingestion <dernière ingestion de data/raw/lots/boutique>` | code ≠ 0 | branchée | ~17 s |
| 2b | `controle_catalogue` | `python -m quality.controle --source catalogue --ingestion <dernière ingestion de data/raw/lots/catalogue>` | code ≠ 0 | branchée | ~6 s |
| 3 | `rapport_rejet` | `python -m quality.rapport --seuil 5` | une source dépasse le seuil | branchée | ~1 s |
| 4 | `transformation` | `python -m transformation --source olist` puis `--source rakuten` | code ≠ 0 | branchée | ~8 min 45 s (dont ~8 min 40 s pour la détection de langue de rakuten) |
| 5a | `correspondance` | `python -m integration.correspondance` | catégorie du catalogue absente (code 1) | branchée | ~20 s |
| 5b | `reindexation` | `python -m recherche.indexer` | index non conforme (code 1) | branchée | ~40 s |
| 6 | `chargement` | `python -m integration.chargement` | code ≠ 0 | branchée | ~1 min |
| 7 | `verification` | `python -m integration.verifier` | fait orphelin ou comptage différent (code 1) | branchée | ~10 s |

⚠️ **La réindexation et la correspondance avancent en parallèle.** La première
lit `staging.rakuten_produits`, la seconde alimente l'entrepôt : elles n'ont
aucun lien, et une réindexation lente ne doit pas retarder les chiffres de
vente.

⚠️ **Le chargement initial des systèmes sources se fait à la main** —
`charger_boutique.py` pour la base SQL, `charger_catalogue_mongo.py` pour la
base documentaire. La chaîne quotidienne **consomme** les sources, elle ne les
remplit pas : c'est le rôle des systèmes amont, que la plateforme n'administre
pas.

Durée de la chaîne mesurée avec les trois dernières tâches factices : environ 9 min 15 s, dominée par la transformation de rakuten.

Les commandes sont lancées par une tâche Bash d'Airflow, dans l'image `dataflow360-airflow`, qui embarque les dépendances du projet dans un environnement virtuel séparé (`/home/airflow/venv-projet`) et monte `src/` et `data/`. Dans le DAG, `python` désigne donc `/home/airflow/venv-projet/bin/python`, et chaque tâche commence par `cd /opt/airflow` pour que les chemins relatifs `data/...` fonctionnent.

**Pourquoi `--ingestion` est passé explicitement.** Le contrôle d'une source par lot refuse de choisir une ingestion lui-même. Le DAG lit donc le dossier `data/raw/lots/<source>` pour retrouver la plus récente, ce qui fonctionne aussi quand l'acquisition ne crée rien.

## 3. Codes de sortie

| Code | Signification |
|------|---------------|
| `0` | Succès, y compris « aucun changement depuis la dernière ingestion » |
| `1` | Échec métier (seuil dépassé, anomalie détectée) |
| autre | Erreur technique (exception, droits, service injoignable) |

Airflow ne distingue pas `1` des autres codes non nuls : tout code ≠ 0 marque la tâche en échec.

## 4. Paramètres du workflow

| Paramètre | Valeur |
|-----------|--------|
| Planification | une fois par jour |
| Reprises automatiques | 2 par tâche, sauf `rapport_rejet` (aucune : un seuil dépassé est un échec métier que la relance ne corrige pas) |
| Exécuteur | local |
| Métadonnées | base dédiée `airflow`, sur la même instance PostgreSQL que l'entrepôt |
| Création du DAG | en pause par défaut : `airflow dags unpause quotidien` avant le premier déclenchement |
| Rattrapage | désactivé (`catchup=False`) |
| Seuil de rejet | variable Airflow `seuil_rejet`, 5 par défaut |
| Prérequis | migrations appliquées hors du workflow (`python scripts/appliquer_sql.py`), droits d'écriture de l'utilisateur `airflow` sur `data/` |

## 5. Comportements garantis

1. **Arrêt sur seuil. Validé.** Avec `seuil_rejet = 0.05` (le taux olist est de 0,07 %), `rapport_rejet` échoue avec le code 1 et les quatre tâches suivantes passent en `upstream_failed` : le chargement du jour n'a pas lieu. Attention, un seuil de 0,1 ne déclencherait rien, le taux étant inférieur.
2. **Reprise. Validée.** Après retour au seuil de 5, `airflow tasks clear quotidien -t '^rapport_rejet$' -d -y -s <début> -e <fin>` relance depuis la tâche en échec : les acquisitions et contrôles gardent leurs heures d'origine, ils ne sont pas refaits.
3. **Rejeu sans effet.** Partiellement validé : les deux acquisitions répondent « aucun changement » avec le code 0. À valider quand le chargement sera branché : second déclenchement sans nouvelle donnée, comptages de l'entrepôt identiques. Le rejeu d'un contrôle sur la même ingestion ne duplique pas la quarantaine : `quarantaine.rejets` reste à 2 130 lignes après plusieurs exécutions du contrôle olist sur la même ingestion.

## 6. Ressources mesurées

| Mesure | Valeur |
|--------|--------|
| Airflow au repos (webserver + scheduler) | environ 550 Mio |
| Scheduler pendant l'exécution | pic d'au moins 1,17 Gio (relevé partiel : la fin de la détection de langue n'est pas couverte) |
| Services du projet au repos (8 conteneurs) | environ 3 Gio sur 14,76 Gio |

Chaque poste de l'équipe doit relever `free -h` avant la journée d'intégration. Le swap sature sur le poste de l'auteur, avec 4,5 Gio disponibles : c'est le risque principal à confirmer sur les autres machines.

## 7. Points à trancher avec l'équipe

- [x] **Choix de l'ingestion par `controle`.** Réponse : l'option `--ingestion` est obligatoire pour les deux sources, le DAG la lit dans `data/raw/lots/<source>`.
- [x] **Transformation d'olist.** Confirmée : `--source {olist,rakuten}`.
- [x] **Accès d'Airflow aux modules.** Image dédiée (`docker/airflow/Dockerfile`), dépendances dans un venv séparé, `src/` et `data/` montés, aucun accès au démon Docker. Conséquence : `docker compose build app` ne reconstruit pas Airflow, le réflexe devient `docker compose build`.
- [x] **Droits sur `data/`.** L'utilisateur `airflow` ne pouvait pas écrire dans `data/raw/lots/` (créé par le conteneur `app`, en root). Correction : `sudo chmod -R a+rwX data`. À annoncer à toute l'équipe.
- [x] **Doublons de quarantaine au rejeu d'un contrôle.** Aucun doublon : `quarantaine.rejets` reste à 2 130 lignes après plusieurs exécutions du contrôle olist sur la même ingestion.
- [ ] **Commandes de F1.9 et F1.10.** `integration.correspondance`, `integration.chargement` et `integration.verifier` n'existent pas encore : tâches factices jusqu'à la fusion.
- [ ] **Lignes d'article sans commande parente.** 8 lignes de `staging.olist_order_items` n'ont pas de commande dans `staging.olist_orders` (commandes rejetées par `OLIST_COMMANDES_02`) : le comptage attendu par la vérification dépend de la décision du livrable 2.

## 8. Vérification du contrat

| Scénario | Commande | Résultat attendu |
|----------|----------|------------------|
| Déclenchement manuel | `docker compose exec airflow-webserver airflow dags trigger quotidien` | neuf tâches au vert, dans l'ordre |
| Second déclenchement | idem | succès, aucune ingestion créée, comptages inchangés |
| Seuil bas | `airflow variables set seuil_rejet 0.05`, puis déclenchement | arrêt à `rapport_rejet`, tâches suivantes `upstream_failed` |
| Retour au seuil normal | `airflow variables set seuil_rejet 5`, puis `airflow tasks clear` (voir §5) | chaîne terminée, sans refaire les acquisitions |
