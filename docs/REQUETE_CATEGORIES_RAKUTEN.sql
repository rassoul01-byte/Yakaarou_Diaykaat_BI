-- Trois désignations par catégorie du catalogue Rakuten, avec le volume.
--
-- À quoi ça sert : le fichier de correspondance rattache 21 catégories Olist
-- sur 74. Pour décider si une catégorie non rattachée peut l'être, il faut
-- voir ce que contient réellement chaque code Rakuten — pas le deviner.
--
--   docker compose exec postgres psql -U dataflow -d dataflow360 \
--     -f /app/docs/REQUETE_CATEGORIES_RAKUTEN.sql
--
-- Ou, plus simple, en copiant la requête ci-dessous dans psql.

WITH echantillon AS (
    SELECT
        prdtypecode,
        designation,
        ROW_NUMBER() OVER (PARTITION BY prdtypecode ORDER BY length(designation) DESC) AS rang,
        COUNT(*)    OVER (PARTITION BY prdtypecode) AS fiches
    FROM staging.rakuten_produits
    WHERE prdtypecode IS NOT NULL
      AND designation IS NOT NULL
      AND btrim(designation) <> ''
)
SELECT
    prdtypecode  AS code,
    fiches,
    left(designation, 70) AS exemple
FROM echantillon
WHERE rang <= 3
ORDER BY fiches DESC, code, rang;
