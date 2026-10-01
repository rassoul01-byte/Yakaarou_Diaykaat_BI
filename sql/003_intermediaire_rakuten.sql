-- DataFlow360 — Migration 003
-- F1.6 : zone intermédiaire — catalogue produits Rakuten (SIGIR eCom 2020)
--
-- Une seule table pour train et test, distinguée par la colonne `jeu`,
-- plutôt que deux tables séparées : les deux jeux partagent exactement
-- la même structure, seule prdtypecode diffère (absente sur le test).

CREATE TABLE IF NOT EXISTS staging.rakuten_produits (
    index_ligne    INTEGER     NOT NULL,   -- index d'origine du CSV, clé de correspondance train/test
    jeu            TEXT        NOT NULL,   -- 'train' ou 'test'
    designation    TEXT        NOT NULL,
    description    TEXT,                   -- souvent vide, contient du HTML brut
    productid      TEXT        NOT NULL,
    imageid        TEXT        NOT NULL,
    prdtypecode    INTEGER,                -- absent pour le jeu de test
    PRIMARY KEY (jeu, index_ligne)
);

CREATE INDEX IF NOT EXISTS idx_rakuten_productid
    ON staging.rakuten_produits (productid);
