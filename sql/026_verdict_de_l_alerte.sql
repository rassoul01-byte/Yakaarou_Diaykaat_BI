-- Le verdict de l'alerte descend dans la vue.
--
-- Le problème corrigé ici. `staging.v_alerte_ventes` publiait les ingrédients
-- — achats, moyenne habituelle, jours comparés — mais pas le niveau ni le
-- dépassement du seuil, qui vivaient uniquement dans `src/compteurs/alerte.py`.
-- Trois conséquences :
--
--   1. L'alerte était la SEULE entrée du dictionnaire des indicateurs sans
--      ligne « Calcul », alors que le document impose que tout calcul vive
--      dans une vue versionnée.
--   2. Power BI ne pouvait pas afficher le verdict : la page « Temps réel »
--      portait une narration écrite à la main à côté du tableau, qui ment dès
--      le premier rafraîchissement.
--   3. La fenêtre glissante n'était couverte par aucun test, faute de pouvoir
--      interroger un résultat.
--
-- Ce qui reste en Python, et pourquoi. La règle de midi dépend du moment où
-- l'on pose la question, pas de la donnée : une vue ne peut pas la porter. Le
-- seuil, lui, est ici — et un test (`test_le_seuil_sql_et_le_seuil_python_sont_le_meme`)
-- vérifie que la constante Python lui reste égale. Deux définitions
-- divergentes d'un même indicateur sont, selon le dictionnaire lui-même, « la
-- première cause de désaccord en réunion ».

CREATE OR REPLACE VIEW staging.v_alerte_ventes AS
WITH compare AS (
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
    FROM staging.v_achats_par_jour
)
SELECT
    jour,
    jour_semaine,
    achats,
    achats_habituels,
    jours_compares,
    -- Arrondi pour l'affichage seulement.
    ROUND(100.0 * achats / NULLIF(achats_habituels, 0), 1) AS niveau_pourcent,
    -- Au moins deux jours de référence, et une moyenne non nulle.
    (jours_compares >= 2 AND COALESCE(achats_habituels, 0) > 0) AS comparable,
    -- Le seuil s'applique à la valeur EXACTE, pas à l'arrondi : 240 achats
    -- contre 400,25 habituels donnent 59,96 %, qui s'arrondit à 60,0 % et
    -- passerait à travers une comparaison sur la valeur affichée.
    (
        jours_compares >= 2
        AND COALESCE(achats_habituels, 0) > 0
        AND 100.0 * achats / achats_habituels < 60.0
    ) AS sous_le_seuil,
    -- Une journée en cours est incomplète : c'est l'équivalent, côté données,
    -- de la règle de midi que porte `compteurs.alerte`.
    (jour < CURRENT_DATE) AS jour_complet
FROM compare;

COMMENT ON VIEW staging.v_alerte_ventes IS
    'Achats du jour compares a la moyenne des memes jours de semaine precedents, '
    'avec le niveau, le franchissement du seuil de 60 % et le fait que la journee '
    'soit complete. Seuil defini ici, une seule fois. Voir sql/026.';
