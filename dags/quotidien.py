"""Workflow quotidien DataFlow360 — contrat : docs/contrats/workflow.md

Chaque tâche lance sa commande par un BashOperator. Une tâche est « factice »
(elle réussit toujours) tant que son nom n'est pas dans REELLES : on la
remplace une à une au fil des fusions, sans toucher au reste du DAG.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# Python du projet (venv séparé de celui d'Airflow) et dossier de travail,
# pour que les chemins relatifs data/... fonctionnent.
PY = "/home/airflow/venv-projet/bin/python"
PREFIXE = f"cd /opt/airflow && {PY}"

# Seuil de rejet lu dans une variable Airflow, 5 par défaut :
#   airflow variables set seuil_rejet 0.05
SEUIL = "{{ var.value.get('seuil_rejet', '5') }}"


def derniere(source: str) -> str:
    """Identifiant de l'ingestion la plus récente d'une source.

    Le contrôle d'une source par lot exige --ingestion, et l'acquisition ne
    crée pas de lot quand rien n'a changé : on lit donc les dossiers.
    """
    return f"$(ls data/raw/lots/{source} | sed -n 's/^ingestion=//p' | sort | tail -1)"


# Tâches dont la vraie commande est branchée. Ajouter un nom ici quand le
# livrable correspondant est fusionné.
REELLES = {
    "acquisition",
    "acquisition_rakuten",
    "controle_olist",
    "controle_rakuten",
    "rapport_rejet",
    "transformation",
}

COMMANDES = {
    "acquisition": f"{PREFIXE} -m acquisition --source boutique",
    "acquisition_rakuten": f"{PREFIXE} -m acquisition --source rakuten",
    "controle_olist": (
        f"{PREFIXE} -m quality.controle --source olist --ingestion {derniere('boutique')}"
    ),
    "controle_rakuten": (
        f"{PREFIXE} -m quality.controle --source rakuten --ingestion {derniere('rakuten')}"
    ),
    "rapport_rejet": f"{PREFIXE} -m quality.rapport --seuil {SEUIL}",
    "transformation": (
        f"{PREFIXE} -m transformation --source olist && "
        f"{PREFIXE} -m transformation --source rakuten"
    ),
    "correspondance": f"{PREFIXE} -m integration.correspondance",
    "chargement": f"{PREFIXE} -m integration.chargement",
    "verification": f"{PREFIXE} -m integration.verifier",
}

# Un rapport qui dépasse le seuil est un échec métier : le rejouer ne sert à rien.
REPRISES = {"rapport_rejet": 0}


def tache(nom: str) -> BashOperator:
    commande = COMMANDES[nom] if nom in REELLES else f"echo 'tâche factice : {nom}'"
    return BashOperator(
        task_id=nom,
        bash_command=commande,
        retries=REPRISES.get(nom, 2),
    )


with DAG(
    dag_id="quotidien",
    description="Chaîne quotidienne : acquisition, qualité, transformation, entrepôt",
    schedule="@daily",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["dataflow360", "sprint3"],
) as dag:
    acquisition = tache("acquisition")
    acquisition_rakuten = tache("acquisition_rakuten")
    controle_olist = tache("controle_olist")
    controle_rakuten = tache("controle_rakuten")
    rapport_rejet = tache("rapport_rejet")
    transformation = tache("transformation")
    correspondance = tache("correspondance")
    chargement = tache("chargement")
    verification = tache("verification")

    acquisition >> controle_olist
    acquisition_rakuten >> controle_rakuten
    [controle_olist, controle_rakuten] >> rapport_rejet
    rapport_rejet >> transformation >> correspondance >> chargement >> verification
