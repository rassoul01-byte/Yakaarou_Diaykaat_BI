-- Journal de l'assistant, chargé dans PostgreSQL pour le taux de réponses ancrées (F5.7).
--
-- Le journal est écrit en fichier (.jsonl) par l'assistant, puis chargé ici par
-- `python -m assistant.charger_journal`. Power BI lit les vues, comme pour toutes les
-- autres pages : par le compte en lecture seule, jamais par un chemin de fichier.
--
-- Le journal ne contient aucune donnée personnelle : la question est masquée avant
-- d'être écrite (docs/contrats/assistant.md, §5), et le chargeur la masque une seconde fois.
--
-- Deux sources, qui ne se mélangent jamais :
--   'evaluation'  le jeu de questions gelé, rejoué par `assistant.evaluer --journal` : c'est
--                 la MESURE du dictionnaire (taux mesuré sur un jeu fixé).
--   'usage'       les questions posées à la main, par exemple en démonstration.

-- Un échange, une ligne. La clé primaire est une empreinte de la ligne du journal :
-- recharger le même fichier n'ajoute rien. C'est toute la protection contre les doublons,
-- et elle est dans la base, pas dans le code.
CREATE TABLE IF NOT EXISTS staging.journal_assistant (
    id_echange       TEXT             PRIMARY KEY,
    source           TEXT             NOT NULL CHECK (source IN ('usage', 'evaluation')),
    horodatage       TIMESTAMPTZ      NOT NULL,
    jour             DATE             NOT NULL,
    question         TEXT             NOT NULL,
    refus            BOOLEAN          NOT NULL,
    motif            TEXT,
    passages_cites   TEXT[]           NOT NULL DEFAULT '{}',
    score_meilleur   DOUBLE PRECISION,
    suggestions      TEXT[]           NOT NULL DEFAULT '{}',
    duree_ms         INTEGER,
    retrouveur       TEXT             NOT NULL,
    charge_a         TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_journal_assistant_jour
    ON staging.journal_assistant (source, jour);

-- Le taux de réponses ancrées, par source et par jour.
-- Un échange est ancré s'il cite au moins un passage, ou s'il est un refus poli : un refus
-- est conforme au contrat de l'assistant (dictionnaire). Ce qui ne doit jamais exister,
-- c'est une réponse affirmative sans passage à l'appui.
CREATE OR REPLACE VIEW staging.v_taux_ancrage AS
SELECT
    source,
    jour,
    COUNT(*)                                                         AS echanges,
    COUNT(*) FILTER (WHERE NOT refus)                                AS reponses_directes,
    COUNT(*) FILTER (WHERE refus)                                    AS refus,
    COUNT(*) FILTER (WHERE refus OR cardinality(passages_cites) > 0) AS echanges_ancres,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE refus OR cardinality(passages_cites) > 0)
              / NULLIF(COUNT(*), 0),
        2
    )                                                                AS taux_ancrage_pourcent
FROM staging.journal_assistant
GROUP BY source, jour;

-- Le même taux sur toute la période, en une ligne par source. Un taux ne se moyenne pas :
-- il se recalcule, d'où cette vue plutôt qu'une moyenne des taux journaliers.
CREATE OR REPLACE VIEW staging.v_taux_ancrage_global AS
SELECT
    source,
    COUNT(*)                                                         AS echanges,
    COUNT(*) FILTER (WHERE NOT refus)                                AS reponses_directes,
    COUNT(*) FILTER (WHERE refus)                                    AS refus,
    COUNT(*) FILTER (WHERE refus OR cardinality(passages_cites) > 0) AS echanges_ancres,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE refus OR cardinality(passages_cites) > 0)
              / NULLIF(COUNT(*), 0),
        2
    )                                                                AS taux_ancrage_pourcent,
    MIN(jour)                                                        AS premier_jour,
    MAX(jour)                                                        AS dernier_jour
FROM staging.journal_assistant
GROUP BY source;

COMMENT ON TABLE staging.journal_assistant IS
    'Journal de l assistant (masque avant ecriture), charge depuis le fichier .jsonl.';
COMMENT ON VIEW staging.v_taux_ancrage IS
    'Taux de reponses ancrees par source et par jour (dictionnaire : Taux de reponses ancrees).';
COMMENT ON VIEW staging.v_taux_ancrage_global IS
    'Taux de reponses ancrees sur toute la periode, une ligne par source.';
