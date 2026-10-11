"""Supervision horaire Nataal Retail : alerte sur les ventes, puis retard du flux.

Deux tâches, chaque heure :

- `surveiller_ventes` lance `compteurs.surveiller_ventes --jours 1`. La
  supervision horaire juge **la journée en cours** : sans `--jours 1`, le module
  signale toute journée en chute de ses dix derniers jours, et une seule chute
  passée laisserait la tâche rouge à chaque lancement pendant dix jours. Les
  jours passés restent signalés par l'alerte de la vue générale
  (`/api/indicateurs`, dix derniers jours) et par
  `python -m compteurs.surveiller_ventes` lancé à la main.
- `surveiller_flux` lance `supervision.surveiller_flux`, qui ajoute un relevé du
  retard de chaque groupe Kafka dans `staging.retard_flux`.

Une alerte est un échec métier, comme un rapport de rejet au-dessus du seuil :
aucune des deux tâches n'est rejouée. Rejouer `surveiller_flux` ajouterait en
plus des relevés, qui fausseraient la tendance qu'il surveille.

`surveiller_flux` part même si les ventes sont en alerte (`all_done`) : une chute
des ventes ne doit pas masquer un consommateur arrêté, souvent sa cause.
Conséquence : Airflow jugeant un lancement sur sa dernière tâche, le lancement
reste vert quand seule `surveiller_ventes` alerte. Le verdict sur les ventes se
lit sur la case de cette tâche.

Le DAG est en pause à sa création : il ne tourne qu'une fois activé dans Airflow.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# Python du projet (venv séparé de celui d'Airflow) et dossier de travail,
# comme dans dags/quotidien.py.
PY = "/home/airflow/venv-projet/bin/python"
PREFIXE = f"cd /opt/airflow && {PY}"

COMMANDES = {
    "surveiller_ventes": f"{PREFIXE} -m compteurs.surveiller_ventes --jours 1",
    "surveiller_flux": f"{PREFIXE} -m supervision.surveiller_flux",
}

# Une alerte rejouée reste une alerte : aucune reprise.
REPRISES = {"surveiller_ventes": 0, "surveiller_flux": 0}


def tache(nom: str, **options) -> BashOperator:
    return BashOperator(
        task_id=nom,
        bash_command=COMMANDES[nom],
        retries=REPRISES.get(nom, 2),
        **options,
    )


with DAG(
    dag_id="supervision",
    description="Supervision horaire : alerte sur les ventes du jour, retard du flux",
    schedule="@hourly",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["dataflow360"],
) as dag:
    surveiller_ventes = tache("surveiller_ventes")
    surveiller_flux = tache("surveiller_flux", trigger_rule="all_done")

    surveiller_ventes >> surveiller_flux
