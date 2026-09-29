-- Structure de la base « boutique » — le système de gestion de l'e-commerçant.
--
-- Cette base est une SOURCE, pas une zone de stockage de la plateforme : elle
-- représente le système qui produit les commandes. La plateforme la lit, elle
-- n'y écrit jamais.
--
-- Les noms de tables et de colonnes sont ceux du système d'origine : c'est la
-- transformation, au Sprint 2, qui les normalisera.
--
-- Deux choix à connaître :
--   * les identifiants sont du TEXTE, jamais des nombres — les codes postaux
--     brésiliens commencent souvent par un zéro, qu'un type numérique perdrait ;
--   * aucune contrainte de clé étrangère. Une source réelle en aurait, mais
--     elles rejetteraient silencieusement les lignes incohérentes que le
--     contrôle de qualité doit justement détecter au Sprint 2.

CREATE TABLE IF NOT EXISTS customers (
    customer_id              text PRIMARY KEY,
    customer_unique_id       text NOT NULL,
    customer_zip_code_prefix text,
    customer_city            text,
    customer_state           text
);

CREATE TABLE IF NOT EXISTS orders (
    order_id                      text PRIMARY KEY,
    customer_id                   text,
    order_status                  text,
    order_purchase_timestamp      timestamp,
    order_approved_at             timestamp,
    order_delivered_carrier_date  timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id            text,
    order_item_id       integer,
    product_id          text,
    seller_id           text,
    shipping_limit_date timestamp,
    price               numeric(12, 2),
    freight_value       numeric(12, 2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS order_payments (
    order_id             text,
    payment_sequential   integer,
    payment_type         text,
    payment_installments integer,
    payment_value        numeric(12, 2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS products (
    product_id                 text PRIMARY KEY,
    product_category_name      text,
    product_name_lenght        integer,
    product_description_lenght integer,
    product_photos_qty         integer,
    product_weight_g           integer,
    product_length_cm          integer,
    product_height_cm          integer,
    product_width_cm           integer
);

CREATE TABLE IF NOT EXISTS sellers (
    seller_id              text PRIMARY KEY,
    seller_zip_code_prefix text,
    seller_city            text,
    seller_state           text
);

-- Pas de clé primaire : cette table contient volontairement des doublons
-- stricts — 261 831 sur 1 000 163 — que la déduplication traitera au Sprint 2.
CREATE TABLE IF NOT EXISTS geolocation (
    geolocation_zip_code_prefix text,
    geolocation_lat             double precision,
    geolocation_lng             double precision,
    geolocation_city            text,
    geolocation_state           text
);

CREATE TABLE IF NOT EXISTS category_translation (
    product_category_name         text PRIMARY KEY,
    product_category_name_english text
);

-- L'index qui rend l'extraction incrémentale rapide : c'est sur cette colonne
-- que porte le filtre --depuis.
CREATE INDEX IF NOT EXISTS idx_orders_achat ON orders (order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_order_items_commande ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_order_payments_commande ON order_payments (order_id);
CREATE INDEX IF NOT EXISTS idx_geolocation_cp ON geolocation (geolocation_zip_code_prefix);
