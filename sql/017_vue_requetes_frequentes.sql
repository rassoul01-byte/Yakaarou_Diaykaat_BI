-- Les requêtes les plus fréquentes, toutes journées confondues.
--
-- v_journal_requetes regroupe par jour ; la recherche des requêtes sans
-- résultat a besoin du total sur l'ensemble des jours : une requête tapée
-- trois fois sur trois jours différents compte pour trois.
CREATE OR REPLACE VIEW staging.v_requetes_frequentes AS
SELECT
    requete,
    SUM(occurrences)::bigint  AS occurrences,
    COUNT(*)::bigint          AS jours,
    MAX(derniere_recherche)   AS derniere_recherche
FROM staging.v_journal_requetes
GROUP BY requete;

COMMENT ON VIEW staging.v_requetes_frequentes IS
    'Requetes regroupees toutes journees confondues, pour la detection des recherches sans resultat.';