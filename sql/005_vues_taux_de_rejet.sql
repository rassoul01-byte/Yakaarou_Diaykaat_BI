-- Les vues qui calculent le taux de rejet.
--
-- Elles croisent deux tables : le journal des exécutions, qui sait combien de
-- lignes ont été lues, et la quarantaine, qui sait lesquelles ont été rejetées
-- et pourquoi.
--
-- Ce sont des vues, pas des tables : le chiffre est toujours recalculé à la
-- demande, il ne peut donc jamais être périmé.
--
-- Définitions complètes : docs/dictionnaire_indicateurs.md

-- Une ligne par exécution du contrôle de qualité, avec son taux de rejet.
CREATE OR REPLACE VIEW quarantaine.v_taux_rejet_par_execution AS
SELECT
    e.id                AS execution_id,
    e.source,
    e.demarre_a,
    e.termine_a,
    e.statut,
    COALESCE(e.lignes_lues, 0)     AS lignes_lues,
    COALESCE(e.lignes_ecrites, 0)  AS lignes_ecrites,
    COALESCE(e.lignes_rejetees, 0) AS lignes_rejetees,
    CASE
        WHEN COALESCE(e.lignes_lues, 0) = 0 THEN NULL
        ELSE ROUND(100.0 * COALESCE(e.lignes_rejetees, 0) / e.lignes_lues, 2)
    END AS taux_rejet_pourcent
FROM staging.execution_log AS e
WHERE e.pipeline = 'qualite';

-- Le taux de rejet de la dernière exécution de chaque source, et l'historique
-- cumulé : c'est la vue que lit le rapport en ligne de commande.
CREATE OR REPLACE VIEW quarantaine.v_taux_rejet_par_source AS
WITH derniere AS (
    SELECT DISTINCT ON (source)
        source, execution_id, demarre_a, lignes_lues, lignes_rejetees, taux_rejet_pourcent
    FROM quarantaine.v_taux_rejet_par_execution
    ORDER BY source, demarre_a DESC
),
cumul AS (
    SELECT
        source,
        COUNT(*)                     AS executions,
        SUM(lignes_lues)             AS lignes_lues_total,
        SUM(lignes_rejetees)         AS lignes_rejetees_total
    FROM quarantaine.v_taux_rejet_par_execution
    GROUP BY source
)
SELECT
    d.source,
    d.execution_id       AS derniere_execution,
    d.demarre_a          AS derniere_le,
    d.lignes_lues,
    d.lignes_rejetees,
    d.taux_rejet_pourcent,
    c.executions,
    CASE
        WHEN COALESCE(c.lignes_lues_total, 0) = 0 THEN NULL
        ELSE ROUND(100.0 * c.lignes_rejetees_total / c.lignes_lues_total, 2)
    END AS taux_rejet_cumule_pourcent
FROM derniere AS d
JOIN cumul AS c USING (source);

-- Quelles règles rejettent le plus. Le rapport s'en sert pour dire non
-- seulement « ça rejette », mais « ça rejette à cause de cette règle-là ».
CREATE OR REPLACE VIEW quarantaine.v_taux_rejet_par_regle AS
WITH total AS (
    SELECT source, COUNT(*) AS rejets_source FROM quarantaine.rejets GROUP BY source
)
SELECT
    r.source,
    r.regle_violee                       AS regle,
    r.gravite,
    COUNT(*)                             AS rejets,
    MIN(r.horodatage)                    AS premier_rejet,
    MAX(r.horodatage)                    AS dernier_rejet,
    ROUND(100.0 * COUNT(*) / t.rejets_source, 2) AS part_des_rejets_pourcent
FROM quarantaine.rejets AS r
JOIN total AS t ON t.source = r.source
GROUP BY r.source, r.regle_violee, r.gravite, t.rejets_source;

-- La répartition par gravité : ce qui a été bloqué, ce qui est seulement signalé.
CREATE OR REPLACE VIEW quarantaine.v_rejets_par_gravite AS
SELECT
    source,
    gravite,
    COUNT(*)                  AS rejets,
    COUNT(DISTINCT regle_violee) AS regles_concernees
FROM quarantaine.rejets
GROUP BY source, gravite;

COMMENT ON VIEW quarantaine.v_taux_rejet_par_source IS
    'Taux de rejet par source : lignes rejetees / lignes lues. Seuil d alerte : 5%.';
