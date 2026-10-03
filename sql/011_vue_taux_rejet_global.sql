-- Le taux de rejet de la plateforme entière, toutes sources confondues.
--
-- Pourquoi une vue plutôt qu'une moyenne dans le tableau de bord : la moyenne
-- des taux par source traite 1,5 million de lignes Olist et 85 000 fiches
-- Rakuten comme équivalentes, et donne 0,04 % au lieu de 0,065 %. Un taux se
-- calcule sur le total des lignes, jamais en moyennant des taux.
--
-- La vue s'appuie sur v_taux_rejet_par_source, qui ne retient que la dernière
-- exécution de chaque source : le chiffre reflète donc l'état courant de la
-- plateforme, pas son historique cumulé.

CREATE OR REPLACE VIEW quarantaine.v_taux_rejet_global AS
SELECT
    COUNT(*)                     AS sources,
    SUM(lignes_lues)             AS lignes_lues,
    SUM(lignes_rejetees)         AS lignes_rejetees,
    CASE
        WHEN COALESCE(SUM(lignes_lues), 0) = 0 THEN NULL
        ELSE ROUND(100.0 * SUM(lignes_rejetees) / SUM(lignes_lues), 3)
    END AS taux_rejet_pourcent
FROM quarantaine.v_taux_rejet_par_source;

COMMENT ON VIEW quarantaine.v_taux_rejet_global IS
    'Taux de rejet toutes sources, derniere execution de chacune.';