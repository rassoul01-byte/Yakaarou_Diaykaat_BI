-- Alerte sur chute des ventes (F2.7).
--
-- L'alerte compare le nombre d'ACHATS du jour à ce qu'on observe habituellement
-- le même jour de la semaine. Pas le chiffre d'affaires : les événements ne
-- portent aucun montant, ni le contrat d'événements ni le catalogue n'en
-- contiennent. Un chiffre d'affaires temps réel serait un chiffre inventé.
--
-- Pourquoi le même jour de la semaine : un dimanche ne se compare pas à un
-- mardi. Comparer à la veille déclencherait une alerte chaque lundi matin, et
-- une alerte qui crie sans raison n'est plus lue au bout d'une semaine.

CREATE OR REPLACE VIEW staging.v_achats_par_jour AS
SELECT
    jour,
    EXTRACT(ISODOW FROM jour)::int       AS jour_semaine,
    COUNT(*) FILTER (WHERE type = 'achat') AS achats,
    COUNT(DISTINCT id_session)             AS sessions
FROM staging.evenements_du_jour
GROUP BY jour;

-- Pour chaque jour, la moyenne des quatre mêmes jours de semaine précédents.
-- Quatre : assez pour lisser un jour creux, assez peu pour que l'alerte réagisse
-- encore à une tendance récente.
CREATE OR REPLACE VIEW staging.v_alerte_ventes AS
SELECT
    jour,
    jour_semaine,
    achats,
    ROUND(AVG(achats) OVER (
        PARTITION BY jour_semaine
        ORDER BY jour
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    )::numeric, 1) AS achats_habituels,
    COUNT(*) OVER (
        PARTITION BY jour_semaine
        ORDER BY jour
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS jours_compares
FROM staging.v_achats_par_jour;

COMMENT ON VIEW staging.v_achats_par_jour IS
    'Achats et sessions par jour, avec le jour de la semaine.';
COMMENT ON VIEW staging.v_alerte_ventes IS
    'Achats du jour compares a la moyenne des memes jours de semaine precedents.';
