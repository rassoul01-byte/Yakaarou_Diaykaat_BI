-- DataFlow360 — initialisation de PostgreSQL
-- Exécuté automatiquement au tout premier démarrage du conteneur,
-- et uniquement à celui-là. Pour le rejouer :  docker compose down -v

-- Base de métadonnées d'Airflow, séparée des données du projet
CREATE DATABASE airflow;

-- Les trois zones de la base du projet.
-- Ce sont trois schémas aux règles différentes, et non un seul espace :
--   raw_quarantine : jamais purgé, conserve les rejets et leur motif
--   staging        : écrasé à chaque exécution du pipeline
--   dwh            : historisé, modèle en étoile
\connect dataflow360

CREATE SCHEMA IF NOT EXISTS raw_quarantine;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dwh;

COMMENT ON SCHEMA raw_quarantine IS 'Enregistrements rejetes par le controle qualite, avec leur motif. Jamais purge.';
COMMENT ON SCHEMA staging        IS 'Zone de travail entre controle qualite et integration. Ecrasee a chaque execution.';
COMMENT ON SCHEMA dwh            IS 'Entrepot analytique : table de faits et dimensions. Historise.';

-- Table de suivi des executions, alimentee par tous les traitements.
-- Sert a la supervision et au calcul du taux de rejet (F1.11, F6.2).
CREATE TABLE IF NOT EXISTS staging.execution_log (
    id              BIGSERIAL PRIMARY KEY,
    pipeline        TEXT        NOT NULL,
    etape           TEXT        NOT NULL,
    source          TEXT,
    demarre_a       TIMESTAMPTZ NOT NULL DEFAULT now(),
    termine_a       TIMESTAMPTZ,
    lignes_lues     BIGINT,
    lignes_ecrites  BIGINT,
    lignes_rejetees BIGINT,
    statut          TEXT        NOT NULL DEFAULT 'en_cours',
    message         TEXT
);

CREATE INDEX IF NOT EXISTS idx_execution_log_pipeline
    ON staging.execution_log (pipeline, demarre_a DESC);
