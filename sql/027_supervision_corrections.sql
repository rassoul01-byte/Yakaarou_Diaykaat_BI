-- Trois corrections aux vues de supervision et de rejet.
--
-- Aucune ne change ce que les vues publient en fonctionnement normal : elles
-- corrigent des cas limites qui, chacun, font mentir un chiffre en silence.

-- 1. Un échec sans statut n'était pas compté comme un échec.
--
-- `statut <> 'succes'` vaut NULL quand `statut` est NULL, donc la ligne ne
-- passe pas le filtre. Une exécution interrompue avant d'avoir écrit son
-- statut — précisément le cas d'une panne brutale — n'apparaissait pas dans
-- le compte des échecs. `IS DISTINCT FROM` traite NULL comme une valeur.
CREATE OR REPLACE VIEW staging.v_profil_etapes AS
SELECT
    pipeline,
    etape,
    source,
    COUNT(*)                                                 AS executions,
    COUNT(*) FILTER (WHERE statut IS DISTINCT FROM 'succes') AS echecs,
    ROUND(AVG(duree_secondes)::numeric, 1)                   AS duree_moyenne_secondes,
    MAX(duree_secondes)                                      AS duree_maximale_secondes,
    ROUND(AVG(lignes_lues)::numeric, 0)                      AS lignes_lues_moyenne,
    MAX(demarre_a)                                           AS derniere_execution
FROM staging.v_executions
GROUP BY pipeline, etape, source;

-- Même raison pour les échecs récents : une panne sans statut doit se voir.
-- `termine_a IS NOT NULL` est retiré — c'est lui qui masquait les exécutions
-- interrompues, celles qui n'ont jamais eu le temps de se terminer.
--
-- `termine_a` est ajoutée **en dernier** : un remplacement de vue ne peut
-- qu'allonger la liste des colonnes, jamais en insérer une au milieu.
CREATE OR REPLACE VIEW staging.v_echecs AS
SELECT pipeline, etape, source, demarre_a, duree_secondes, statut, message, termine_a
FROM staging.v_executions
WHERE statut IS DISTINCT FROM 'succes'
ORDER BY demarre_a DESC;

-- 2. Le volume par jour dépendait du fuseau de la session qui interroge.
--
-- `demarre_a` est un TIMESTAMPTZ ; `demarre_a::date` le convertit dans le
-- fuseau de la SESSION. Le même chiffre changeait donc selon le client —
-- Power BI, psql, l'API. Tout le reste de la plateforme compte en UTC :
-- `staging.evenements_du_jour.jour` est écrit en UTC par l'ingestion, et
-- `src/indicateurs/lecture.py` lit ses heures avec `AT TIME ZONE 'UTC'`.
-- `duree_totale_secondes` est conservée : la retirer ferait échouer le
-- remplacement, et priverait la supervision du temps cumulé par pipeline.
CREATE OR REPLACE VIEW staging.v_volume_par_jour AS
SELECT
    (demarre_a AT TIME ZONE 'UTC')::date    AS jour,
    pipeline,
    COUNT(*)                                AS executions,
    SUM(lignes_lues)                        AS lignes_lues,
    SUM(lignes_ecrites)                     AS lignes_ecrites,
    SUM(lignes_rejetees)                    AS lignes_rejetees,
    ROUND(SUM(duree_secondes)::numeric, 1)  AS duree_totale_secondes
FROM staging.v_executions
GROUP BY (demarre_a AT TIME ZONE 'UTC')::date, pipeline;

-- 3. Départage déterministe des exécutions à égalité d'horodatage.
--
-- `DISTINCT ON (...) ORDER BY ..., demarre_a DESC` sans dernier critère rend
-- une ligne arbitraire quand deux exécutions partagent le même `demarre_a`.
-- `src/quality/rapport.py` départage déjà par `id DESC` ; les deux lectures du
-- même concept doivent suivre la même règle.
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
ORDER BY pipeline, etape, COALESCE(source, ''), demarre_a DESC, id DESC;

COMMENT ON VIEW staging.v_profil_etapes IS
    'Comportement habituel de chaque etape. Un statut NULL compte comme un echec.';
COMMENT ON VIEW staging.v_echecs IS
    'Echecs recents, y compris les executions interrompues sans statut ni fin.';
COMMENT ON VIEW staging.v_volume_par_jour IS
    'Volume traite par jour UTC, independant du fuseau de la session qui interroge.';
COMMENT ON VIEW staging.v_derniere_execution IS
    'Derniere execution de chaque etape, departagee par id en cas d egalite d horodatage.';
