-- DataFlow360 — Migration 001
-- F1.6 : renommage du schéma de quarantaine et création de sa table
--
-- Le schéma raw_quarantine a été créé au Sprint 0 (docker/postgres/init/01-databases.sql).
-- Il est renommé ici en `quarantaine`, pour lever toute confusion avec la zone brute
-- (data/raw/), qui est un concept distinct.

ALTER SCHEMA raw_quarantine RENAME TO quarantaine;

COMMENT ON SCHEMA quarantaine IS 'Enregistrements rejetes par le controle qualite, avec leur motif. Jamais purge.';

-- Table générique : un enregistrement rejeté, quelle que soit sa source.
-- Le contenu brut est conservé en JSON pour ne rien perdre de l'original.
CREATE TABLE IF NOT EXISTS quarantaine.rejets (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,   -- ex. 'olist', 'rakuten', 'navigation.evenements'
    fichier         TEXT,                   -- nom du fichier d'origine, si applicable
    ligne_origine   BIGINT,                 -- numéro de ligne ou position dans la source
    regle_violee    TEXT        NOT NULL,   -- identifiant de la règle de qualité violée
    gravite         TEXT        NOT NULL,   -- ex. 'bloquant', 'avertissement'
    enregistrement  JSONB       NOT NULL,   -- l'enregistrement rejeté, tel quel
    horodatage      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rejets_source
    ON quarantaine.rejets (source);

CREATE INDEX IF NOT EXISTS idx_rejets_regle
    ON quarantaine.rejets (regle_violee);