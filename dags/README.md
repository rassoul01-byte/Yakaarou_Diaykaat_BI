# dags — workflows Airflow

**Responsable :** Ndeye Penda SARR
**Suppléante :** Aissata DIALLO

Ce dossier contiendra les workflows qui orchestrent la chaîne quotidienne :
collecte, contrôle qualité, transformation, intégration, réindexation.

Il est monté directement dans les conteneurs Airflow par `docker-compose.yml`.
Un workflow n'exécute aucun calcul lui-même : il appelle les fonctions des
modules de `src/`, dans le bon ordre, et gère les reprises en cas d'échec.

Premier workflow prévu au Sprint 3 (F6.1).

## Dépendances des conteneurs Airflow

Aujourd'hui, aucun workflow n'existe : l'image `apache/airflow` est utilisée
telle quelle, sans dépendance ajoutée.

Le jour où un workflow appellera un module de `src/`, l'image Airflow devra
fournir ce que ce module importe réellement — et seulement cela, pas tout
`requirements.txt` : Airflow a ses propres contraintes de versions. Par
exemple, appeler `quality.controle` exigera `pandera` ; appeler la
transformation Rakuten exigera `langdetect`. Les ajouter alors dans la même
demande de fusion que le workflow, aux versions de `requirements.lock`.
