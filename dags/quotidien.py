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
    "acquisition_catalogue",
    "controle_olist",
    "controle_catalogue",
    "rapport_rejet",
    "transformation",
    "reindexation",
    "correspondance",
    "chargement",
    "verification",
    "indexation_passages",
    "scores_reachat",
}

COMMANDES = {
    "acquisition": f"{PREFIXE} -m acquisition --source boutique",
    # Le catalogue vient de la base documentaire, et non plus du fichier livré :
    # c'est la source NoSQL du projet. Le chargement initial de MongoDB se fait
    # à la main, comme celui de la base de la boutique — la chaîne quotidienne
    # consomme les systèmes sources, elle ne les remplit pas.
    "acquisition_catalogue": f"{PREFIXE} -m acquisition --source catalogue",
    "controle_olist": (
        f"{PREFIXE} -m quality.controle --source olist --ingestion {derniere('boutique')}"
    ),
    "controle_catalogue": (
        f"{PREFIXE} -m quality.controle --source catalogue --ingestion {derniere('catalogue')}"
    ),
    "rapport_rejet": f"{PREFIXE} -m quality.rapport --seuil {SEUIL}",
    # « rakuten » désigne ici la table staging.rakuten_produits, que la source
    # documentaire alimente désormais : le nom de la table n'a pas changé.
    "transformation": (
        f"{PREFIXE} -m transformation --source olist && "
        f"{PREFIXE} -m transformation --source rakuten"
    ),
    # La réindexation lit staging.rakuten_produits : elle suit la
    # transformation, et n'a aucun lien avec le chargement de l'entrepôt. Les
    # deux avancent donc en parallèle — une réindexation lente ne doit pas
    # retarder les chiffres de vente.
    "reindexation": f"{PREFIXE} -m recherche.indexer",
    # `recherche.indexer` écrase les fiches par leur identifiant, mais ne
    # supprime jamais celles qui ont disparu de la source : son contrôle de
    # conformité compare « envoyé » à « en base », deux fois le même nombre.
    # `recherche.etat` compare l'index à la source et sort 1 si l'un dépasse
    # l'autre — c'est la seule tâche qui voit un document orphelin.
    "etat_index": f"{PREFIXE} -m recherche.etat",
    "correspondance": f"{PREFIXE} -m integration.correspondance",
    "chargement": f"{PREFIXE} -m integration.chargement",
    "verification": f"{PREFIXE} -m integration.verifier",
    # Base documentaire de l'assistant : on vérifie la FAQ avant de l'indexer.
    # L'indexation est idempotente (l'identifiant du passage écrase) ; elle ne
    # dépend d'aucune autre tâche, seulement du fichier faq.jsonl et d'Elasticsearch.
    "indexation_passages": (
        f"{PREFIXE} -m documentaire.verifier && {PREFIXE} -m documentaire.indexer"
    ),
    # Scores de ré-achat de tous les clients, lus dans dwh.v_historique_client :
    # la tâche suit la vérification de l'entrepôt. --top 0 : rien à afficher,
    # le CSV (non versionné, data/ est ignoré) contient tous les scores.
    "scores_reachat": f"{PREFIXE} -m prediction.scorer --top 0 --csv data/scores_reachat.csv",
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
    tags=["dataflow360"],
) as dag:
    acquisition = tache("acquisition")
    acquisition_catalogue = tache("acquisition_catalogue")
    controle_olist = tache("controle_olist")
    controle_catalogue = tache("controle_catalogue")
    rapport_rejet = tache("rapport_rejet")
    transformation = tache("transformation")
    reindexation = tache("reindexation")
    etat_index = tache("etat_index")
    correspondance = tache("correspondance")
    chargement = tache("chargement")
    verification = tache("verification")
    # Sans dépendance amont : elle part en même temps que les deux acquisitions.
    indexation_passages = tache("indexation_passages")
    scores_reachat = tache("scores_reachat")

    acquisition >> controle_olist
    acquisition_catalogue >> controle_catalogue
    [controle_olist, controle_catalogue] >> rapport_rejet
    rapport_rejet >> transformation
    transformation >> [correspondance, reindexation]
    reindexation >> etat_index
    correspondance >> chargement >> verification >> scores_reachat
