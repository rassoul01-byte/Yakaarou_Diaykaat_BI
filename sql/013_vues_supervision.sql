-- Vues de supervision des exécutions (F6.2).
--
-- La table staging.execution_log est alimentée par tous les traitements depuis
-- le Sprint 1 : acquisition, contrôle, transformation, intégration. Ce qui
-- manquait, c'est une lecture d'exploitation — combien de temps a duré chaque
-- étape, quel volume elle a traité, et laquelle a échoué.
--
-- Rien n'est recalculé ici que la table ne contienne déjà : ces vues ne font
-- que la rendre lisible.

-- Chaque exécution, avec sa durée. C'est la vue de base, les autres en dérivent.
CREATE OR REPLACE VIEW staging.v_executions AS
SELECT
    id,
    pipeline,
    etape,
    source,
    demarre_a,
    termine_a,
    -- Une exécution en cours n'a pas de durée : afficher zéro laisserait croire
    -- qu'elle a été instantanée.
    CASE
        WHEN termine_a IS NULL THEN NULL
        ELSE ROUND(EXTRACT(EPOCH FROM (termine_a - demarre_a))::numeric, 1)
    END AS duree_secondes,
    lignes_lues,
    lignes_ecrites,
    lignes_rejetees,
    statut,
    message
FROM staging.execution_log;

-- La dernière exécution de chaque étape : l'état courant de la plateforme.
CREATE OR REPLACE VIEW staging.v_derniere_execution AS
SELECT DISTINCT ON (pipeline, etape, COALESCE(source, ''))
    pipeline,
    etape,
    source,
    demarre_a,
    duree_secondes,
    lignes_lues,
    lignes_ecrites,
    lignes_rejetees,
    statut
FROM staging.v_executions
ORDER BY pipeline, etape, COALESCE(source, ''), demarre_a DESC;

-- Le comportement habituel d'une étape : combien de temps elle prend, quel
-- volume elle traite, et à quelle fréquence elle échoue.
CREATE OR REPLACE VIEW staging.v_profil_etapes AS
SELECT
    pipeline,
    etape,
    source,
    COUNT(*)                                        AS executions,
    COUNT(*) FILTER (WHERE statut <> 'succes')      AS echecs,
    ROUND(AVG(duree_secondes)::numeric, 1)          AS duree_moyenne_secondes,
    MAX(duree_secondes)                             AS duree_maximale_secondes,
    ROUND(AVG(lignes_lues)::numeric, 0)             AS lignes_lues_moyenne,
    MAX(demarre_a)                                  AS derniere_execution
FROM staging.v_executions
GROUP BY pipeline, etape, source;

-- Les échecs récents, pour qu'une panne ne se découvre pas par hasard.
CREATE OR REPLACE VIEW staging.v_echecs AS
SELECT pipeline, etape, source, demarre_a, duree_secondes, statut, message
FROM staging.v_executions
WHERE statut <> 'succes' AND termine_a IS NOT NULL
ORDER BY demarre_a DESC;

-- Le volume traité par jour : ce que la plateforme avale réellement.
CREATE OR REPLACE VIEW staging.v_volume_par_jour AS
SELECT
    demarre_a::date                     AS jour,
    pipeline,
    COUNT(*)                            AS executions,
    SUM(lignes_lues)                    AS lignes_lues,
    SUM(lignes_ecrites)                 AS lignes_ecrites,
    SUM(lignes_rejetees)                AS lignes_rejetees,
    ROUND(SUM(duree_secondes)::numeric, 1) AS duree_totale_secondes
FROM staging.v_executions
GROUP BY demarre_a::date, pipeline;

COMMENT ON VIEW staging.v_executions IS
    'Toutes les executions, avec leur duree.';
COMMENT ON VIEW staging.v_derniere_execution IS
    'Derniere execution de chaque etape : etat courant de la plateforme.';
COMMENT ON VIEW staging.v_profil_etapes IS
    'Comportement habituel de chaque etape : duree, volume, taux d echec.';
COMMENT ON VIEW staging.v_echecs IS
    'Executions terminees en echec, la plus recente en premier.';
