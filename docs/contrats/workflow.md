# Contrat du workflow quotidien

**Statut** : brouillon · **Auteur** : Seydina WADE · **Relectrice** : Ndeye Penda SARR · **Fonctionnalité** : F6.1
**Fichier du workflow** : `dags/quotidien.py` · **Identifiant Airflow** : `quotidien`

Ce document fixe, avant que les autres livrables n'existent, le nom de chaque commande, l'ordre des tâches et ce qui compte comme un échec. Chaque livrable du Sprint 3 doit se terminer par la commande listée ici.

## 1. Ordre des tâches

```
acquisition ──► contrôle olist ───┐
                                  ├──► rapport de rejet (seuil 5 %) ──► transformation
                contrôle rakuten ─┘                                          │
                                                                             ▼
                          vérification ◄── chargement ◄── correspondance ◄───┘
```

Les deux contrôles s'exécutent en parallèle. La transformation d'olist et celle de rakuten s'enchaînent dans la même tâche.

## 2. Tâches, commandes et conditions d'échec

| # | Tâche | Commande | Échec si | Livrable |
|---|-------|----------|----------|----------|
| 1 | `acquisition` | `python -m acquisition --source boutique` | code de sortie ≠ 0 | Sprint 1 |
| 2a | `controle_olist` | `python -m quality.controle --source olist` | code de sortie ≠ 0 | Sprint 2 |
| 2b | `controle_rakuten` | `python -m quality.controle --source rakuten` | code de sortie ≠ 0 | Sprint 2 |
| 3 | `rapport_rejet` | `python -m quality.rapport --seuil 5` | une source dépasse 5 % | Sprint 2 |
| 4 | `transformation` | `python -m transformation --source olist` puis `--source rakuten` | code de sortie ≠ 0 | Sprint 2 |
| 5 | `correspondance` | `python -m integration.correspondance` | catégorie du catalogue absente (code 1) | F1.9 |
| 6 | `chargement` | `python -m integration.chargement` | code de sortie ≠ 0 | F1.10 |
| 7 | `verification` | `python -m integration.verifier` | fait orphelin ou comptage différent (code 1) | F1.10 |

Toutes les commandes sont lancées par une tâche Bash d'Airflow, dans l'image `dataflow360-airflow`, qui embarque les dépendances du projet dans un environnement virtuel séparé (`/home/airflow/venv-projet`) et monte `src/` et `data/`. Dans le DAG, `python` désigne donc `/home/airflow/venv-projet/bin/python`, et chaque tâche commence par `cd /opt/airflow` pour que les chemins relatifs `data/...` fonctionnent.

## 3. Codes de sortie

| Code | Signification |
|------|---------------|
| `0` | Succès, y compris « rien de nouveau à traiter » |
| `1` | Échec métier (seuil dépassé, anomalie détectée) |
| autre | Erreur technique (exception, service injoignable) |

Airflow ne distingue pas `1` des autres codes non nuls : tout code ≠ 0 marque la tâche en échec.

## 4. Paramètres du workflow

| Paramètre | Valeur |
|-----------|--------|
| Planification | une fois par jour |
| Reprises automatiques | 2 par tâche |
| Exécuteur | local |
| Métadonnées | base dédiée `airflow`, sur la même instance PostgreSQL que l'entrepôt |
| Création du DAG | en pause par défaut : `airflow dags unpause quotidien` avant le premier déclenchement |
| Rattrapage | désactivé (`catchup=False`) : pas de rejeu des dates passées |
| Seuil de rejet | 5 % (variable, abaissable pour les tests, par exemple 0,1) |

Prérequis : les migrations sont appliquées hors du workflow (python scripts/appliquer_sql.py, réflexe du guide de mise à jour). Le DAG ne les lance pas.

## 5. Comportements garantis

1. **Arrêt sur seuil.** Si `rapport_rejet` échoue, `transformation`, `correspondance`, `chargement` et `verification` ne sont pas exécutées (état « upstream_failed »). Le chargement du jour n'a pas lieu.
2. **Reprise.** Après correction, on relance à partir de la tâche en échec (effacement de son état et de celui des tâches en aval). Les tâches précédentes ne sont pas refaites, l'acquisition en particulier.
3. **Rejeu sans effet.** Un second déclenchement sans nouvelle donnée réussit. `acquisition` renvoie le code 0 sans créer d'ingestion, et l'entrepôt reste strictement identique : `chargement` est idempotent.

## 6. Points à trancher avec l'équipe

- [ ] **Choix de l'ingestion par `controle`.** Sans option `--ingestion`, le contrôle doit lire la plus récente. À vérifier avec `python -m quality.controle --help`. Si ce n'est pas le cas, la tâche doit récupérer l'identifiant produit par `acquisition`.
- [ ] **Rejeu et contrôle.** Quand `acquisition` ne crée rien, le contrôle rejoue-t-il l'ingestion déjà contrôlée ou est-il sauté ? Comportement souhaité : sans effet sur l'entrepôt, sans doublon en quarantaine.
- [ ] **Transformation d'olist.** Confirmer que `python -m transformation --source olist` existe, seule la source `rakuten` ayant été vérifiée à ce jour.
- [ ] **Commandes de F1.9 et F1.10.** `integration.correspondance`, `integration.chargement` et `integration.verifier` n'existent pas encore : elles sont remplacées par des tâches factices jusqu'à la fusion des livrables correspondants.
- [ ] **Accès d'Airflow aux modules.** Valider à la réunion d'ouverture la solution proposée : image Airflow dédiée (`docker/airflow/Dockerfile`) avec les dépendances du projet dans un environnement virtuel séparé, `src/` monté, tâches Bash, sans accès au démon Docker. Conséquence pour l'équipe : `docker compose build app` ne reconstruit pas Airflow, le réflexe devient `docker compose build`.
- [ ] **Droits sur `data/`.** Le conteneur `app` tourne en root, Airflow en utilisateur `airflow` : vérifier que l'acquisition peut écrire dans `data/raw/`.
- [ ] **Mémoire.** Relever la consommation au repos et pendant une exécution (le pic est dans le scheduler, pas au repos), puis la transmettre à l'équipe avec le `free -h` de chaque poste.

## 7. Vérification du contrat

| Scénario | Commande | Résultat attendu |
|----------|----------|------------------|
| Déclenchement manuel | `docker compose exec airflow-webserver airflow dags trigger quotidien` | toutes les tâches au vert, dans l'ordre |
| Second déclenchement | idem | succès, aucune ingestion créée, comptages inchangés |
| Seuil à 0,1 | idem, seuil abaissé | arrêt à `rapport_rejet`, tâches suivantes non exécutées |
| Retour au seuil normal | relance depuis la tâche en échec | chaîne terminée, sans refaire `acquisition` |