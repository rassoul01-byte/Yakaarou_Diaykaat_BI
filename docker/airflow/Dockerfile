ARG AIRFLOW_VERSION=2.10.2
FROM apache/airflow:${AIRFLOW_VERSION}-python3.11

# Dépendances du projet dans un venv à part : aucun conflit avec celles d'Airflow
COPY requirements.txt requirements.lock /tmp/
RUN python -m venv /home/airflow/venv-projet \
 && /home/airflow/venv-projet/bin/pip install --no-cache-dir \
      -r /tmp/requirements.txt -c /tmp/requirements.lock
