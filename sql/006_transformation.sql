-- DataFlow360 — Migration 006
-- F1.7/F1.8 : colonnes écrites par la transformation (Sprint 2, Aissata)
--
-- Deux colonnes ajoutées, jamais de colonne supprimée ni renommée :
-- - product_category_name_norm : libellé de catégorie normalisé (minuscules,
--   sans accents), clé de rapprochement du catalogue Rakuten au Sprint 3.
--   product_category_name d'origine n'est pas touchée, elle reste affichable.
-- - langue : langue détectée de la fiche produit Rakuten (ISO 639-1), ou
--   'inconnue'. Un attribut du produit, jamais un filtre : le catalogue
--   reste entier.

ALTER TABLE staging.olist_products
    ADD COLUMN IF NOT EXISTS product_category_name_norm TEXT;

ALTER TABLE staging.rakuten_produits
    ADD COLUMN IF NOT EXISTS langue TEXT;
