-- Les rejets par règle et par gravité portent sur la DERNIÈRE ingestion.
--
-- Le défaut corrigé : quarantaine.rejets conserve les rejets de toutes les
-- ingestions passées. Les deux vues les additionnaient donc toutes, et
-- affichaient 3 219 rejets là où la dernière exécution en comptait 1 073 —
-- trois ingestions de la boutique, trois fois les mêmes motifs.
--
-- Les proportions restaient justes, les valeurs absolues non : un tableau de
-- bord qui affiche un nombre de rejets doit afficher celui d'aujourd'hui, pas
-- la somme de l'histoire. Le taux de rejet par source, lui, n'a jamais eu ce
-- défaut : il lit le journal des exécutions, pas la table des rejets.

-- Quelle ingestion fait foi pour chaque source.
-- Les rejets antérieurs à la migration 004 n'ont pas d'identifiant
-- d'ingestion : ils ne peuvent être rattachés à aucune exécution, et sont
-- écartés plutôt que comptés au hasard.
CREATE OR REPLACE VIEW quarantaine.v_derniere_ingestion AS
SELECT source, MAX(ingestion) AS ingestion
FROM quarantaine.rejets
WHERE ingestion IS NOT NULL
GROUP BY source;

CREATE OR REPLACE VIEW quarantaine.v_taux_rejet_par_regle AS
WITH retenus AS (
    SELECT r.*
    FROM quarantaine.rejets AS r
    JOIN quarantaine.v_derniere_ingestion AS d
      ON d.source = r.source AND d.ingestion = r.ingestion
),
total AS (
    SELECT source, COUNT(*) AS rejets_source FROM retenus GROUP BY source
)
-- Les colonnes gardent leur ordre d'origine et `ingestion` est ajoutée à la
-- fin : une colonne insérée au milieu casserait les visuels déjà construits.
SELECT
    r.source,
    r.regle_violee                       AS regle,
    r.gravite,
    COUNT(*)                             AS rejets,
    MIN(r.horodatage)                    AS premier_rejet,
    MAX(r.horodatage)                    AS dernier_rejet,
    ROUND(100.0 * COUNT(*) / t.rejets_source, 2) AS part_des_rejets_pourcent,
    r.ingestion
FROM retenus AS r
JOIN total AS t ON t.source = r.source
GROUP BY r.source, r.ingestion, r.regle_violee, r.gravite, t.rejets_source;

CREATE OR REPLACE VIEW quarantaine.v_rejets_par_gravite AS
SELECT
    r.source,
    r.gravite,
    COUNT(*)                        AS rejets,
    COUNT(DISTINCT r.regle_violee)  AS regles_concernees,
    r.ingestion
FROM quarantaine.rejets AS r
JOIN quarantaine.v_derniere_ingestion AS d
  ON d.source = r.source AND d.ingestion = r.ingestion
GROUP BY r.source, r.ingestion, r.gravite;

-- Toute la quarantaine reste consultable, sans filtre : une ligne rejetée il y
-- a trois ingestions n'a pas disparu, elle n'entre simplement plus dans les
-- compteurs du jour.
CREATE OR REPLACE VIEW quarantaine.v_rejets_historique AS
SELECT source, ingestion, regle_violee AS regle, gravite,
       COUNT(*) AS rejets, MIN(horodatage) AS premier_rejet, MAX(horodatage) AS dernier_rejet
FROM quarantaine.rejets
GROUP BY source, ingestion, regle_violee, gravite;

COMMENT ON VIEW quarantaine.v_taux_rejet_par_regle IS
    'Rejets par regle, derniere ingestion de chaque source.';
COMMENT ON VIEW quarantaine.v_rejets_par_gravite IS
    'Rejets par gravite, derniere ingestion de chaque source.';
COMMENT ON VIEW quarantaine.v_rejets_historique IS
    'Tous les rejets conserves, toutes ingestions confondues.';
