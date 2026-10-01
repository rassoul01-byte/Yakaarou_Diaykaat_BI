-- F1.6 : compléter le contrat de quarantaine avec l'identifiant d'ingestion.

ALTER TABLE quarantaine.rejets
    ADD COLUMN IF NOT EXISTS ingestion TEXT;

CREATE INDEX IF NOT EXISTS idx_rejets_ingestion
    ON quarantaine.rejets (ingestion);