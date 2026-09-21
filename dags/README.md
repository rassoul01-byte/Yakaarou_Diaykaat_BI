# dags — workflows Airflow

**Responsable :** Ndeye Penda SARR
**Suppléante :** Aissata DIALLO

Ce dossier contiendra les workflows qui orchestrent la chaîne quotidienne :
collecte, contrôle qualité, transformation, intégration, réindexation.

Il est monté directement dans les conteneurs Airflow par `docker-compose.yml`.
Un workflow n'exécute aucun calcul lui-même : il appelle les fonctions des
modules de `src/`, dans le bon ordre, et gère les reprises en cas d'échec.

Premier workflow prévu au Sprint 3 (F6.1).
