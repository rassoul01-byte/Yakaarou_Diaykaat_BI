-- DataFlow360 — Migration 002
-- F1.6 : zone intermédiaire — une table par fichier source, types explicites
--
-- Convention : les identifiants (id, code postal) restent en TEXT pour ne
-- jamais perdre un zéro initial. Les dates en DATE ou TIMESTAMP selon la
-- précision fournie par la source. Les montants en NUMERIC.
-- Cette zone est écrasée à chaque exécution du pipeline (cf.
-- docs/contrats/zones_stockage.md) : pas de clés étrangères entre tables
-- ici, elles arriveront dans l'entrepôt (Sprint 3).

CREATE TABLE IF NOT EXISTS staging.olist_orders (
    order_id                        TEXT        PRIMARY KEY,
    customer_id                     TEXT        NOT NULL,
    order_status                    TEXT        NOT NULL,
    order_purchase_timestamp        TIMESTAMP   NOT NULL,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP   NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.olist_order_items (
    order_id             TEXT          NOT NULL,
    order_item_id        INTEGER       NOT NULL,
    product_id           TEXT          NOT NULL,
    seller_id            TEXT          NOT NULL,
    shipping_limit_date  TIMESTAMP     NOT NULL,
    price                NUMERIC(10,2) NOT NULL,
    freight_value        NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS staging.olist_products (
    product_id                  TEXT        PRIMARY KEY,
    product_category_name       TEXT,
    product_name_lenght         INTEGER,
    product_description_lenght  INTEGER,
    product_photos_qty          INTEGER,
    product_weight_g            NUMERIC(10,2),
    product_length_cm           NUMERIC(10,2),
    product_height_cm           NUMERIC(10,2),
    product_width_cm            NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS staging.olist_customers (
    customer_id                TEXT        PRIMARY KEY,
    customer_unique_id         TEXT        NOT NULL,
    customer_zip_code_prefix   TEXT        NOT NULL,
    customer_city              TEXT        NOT NULL,
    customer_state             TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customers_unique_id
    ON staging.olist_customers (customer_unique_id);

CREATE TABLE IF NOT EXISTS staging.olist_geolocation (
    geolocation_zip_code_prefix   TEXT            NOT NULL,
    geolocation_lat               NUMERIC(15,12)  NOT NULL,
    geolocation_lng               NUMERIC(15,12)  NOT NULL,
    geolocation_city              TEXT            NOT NULL,
    geolocation_state             TEXT            NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_geolocation_zip
    ON staging.olist_geolocation (geolocation_zip_code_prefix);

CREATE TABLE IF NOT EXISTS staging.olist_order_payments (
    order_id              TEXT          NOT NULL,
    payment_sequential    INTEGER       NOT NULL,
    payment_type          TEXT          NOT NULL,
    payment_installments  INTEGER       NOT NULL,
    payment_value         NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE INDEX IF NOT EXISTS idx_payments_order
    ON staging.olist_order_payments (order_id);

CREATE TABLE IF NOT EXISTS staging.olist_order_reviews (
    review_id                    TEXT        NOT NULL,
    order_id                     TEXT        NOT NULL,
    review_score                 INTEGER     NOT NULL,
    review_comment_title         TEXT,
    review_comment_message       TEXT,
    review_creation_date         TIMESTAMP   NOT NULL,
    review_answer_timestamp      TIMESTAMP   NOT NULL,
    PRIMARY KEY (review_id, order_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_order
    ON staging.olist_order_reviews (order_id);

CREATE TABLE IF NOT EXISTS staging.olist_sellers (
    seller_id                TEXT        PRIMARY KEY,
    seller_zip_code_prefix   TEXT        NOT NULL,
    seller_city              TEXT        NOT NULL,
    seller_state             TEXT        NOT NULL
);

-- Référentiel fixe fourni avec le dataset (pas une donnée d'ingestion),
-- inclus ici par simplicité pour ce sprint.
CREATE TABLE IF NOT EXISTS staging.product_category_translation (
    product_category_name          TEXT   PRIMARY KEY,
    product_category_name_english  TEXT   NOT NULL
);
