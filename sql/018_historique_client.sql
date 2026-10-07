-- Historique d'achat par client, pour le modèle de ré-achat (F3.1).
--
-- Protocole : docs/contrats/modele.md
--
-- Une ligne par **personne et par date de référence**, avec la réponse
-- observée. Deux dates suffisent : une pour entraîner, une pour évaluer.
--
-- La règle qui gouverne tout ce fichier : **on ne regarde que ce qui était
-- connu à la date de référence.** Une seule variable qui connaîtrait l'avenir
-- rendrait le modèle excellent et faux, sans que rien ne le signale.
--
-- La date de référence vaut le DÉBUT du jour (minuit) : un achat du jour même
-- appartient à l'avenir, donc à la cible, jamais aux variables.

-- Les deux dates du protocole. Les changer ici les change partout.
CREATE OR REPLACE VIEW dwh.v_dates_reference AS
SELECT * FROM (VALUES
    (DATE '2017-03-31'),
    (DATE '2017-09-30')
) AS dates(date_reference);

-- Les commandes retenues : même périmètre que le chiffre d'affaires.
-- Annulées et indisponibles exclues — deux définitions du mot « commande »
-- dans le même projet seraient la garantie d'un désaccord.
-- Limite connue : le statut est le statut FINAL de la commande, connu après la
-- date de référence. Une commande passée avant elle puis annulée plus tard en
-- est exclue (voir la page « Limites » de docs/contrats/modele.md).
CREATE OR REPLACE VIEW dwh.v_commandes_retenues AS
SELECT
    c.order_id,
    c.client_id,
    cl.customer_unique_id,
    cl.etat,
    c.date_achat,
    c.date_livraison_client,
    c.date_livraison_estimee,
    c.delai_livraison_jours
FROM dwh.fait_commande AS c
JOIN dwh.dim_client AS cl ON cl.client_id = c.client_id
WHERE c.statut NOT IN ('canceled', 'unavailable')
  AND c.a_une_ligne_article;

-- Le montant d'une commande, **frais de port exclus**, comme dwh.v_ventes_retenues.
CREATE OR REPLACE VIEW dwh.v_montant_commande AS
SELECT order_id, SUM(prix) AS montant, COUNT(DISTINCT produit_id) AS produits
FROM dwh.fait_ligne_commande
GROUP BY order_id;

-- CREATE OR REPLACE ne peut pas retirer une colonne d'une vue existante : on la
-- supprime d'abord. Rien ne dépend d'elle, et la migration reste rejouable.
DROP VIEW IF EXISTS dwh.v_segment_a_retenir;
DROP VIEW IF EXISTS dwh.v_historique_client;

CREATE VIEW dwh.v_historique_client AS
WITH croisement AS (
    -- Chaque personne ayant déjà commandé, pour chacune des deux dates.
    SELECT DISTINCT c.customer_unique_id, d.date_reference
    FROM dwh.v_commandes_retenues AS c
    CROSS JOIN dwh.v_dates_reference AS d
    WHERE c.date_achat <= d.date_reference
),
passe AS (
    -- Tout ce qui était connu à la date de référence, et rien d'autre.
    SELECT
        x.customer_unique_id,
        x.date_reference,
        COUNT(DISTINCT c.order_id)                       AS commandes,
        COALESCE(SUM(m.montant), 0)                      AS montant_total,
        MIN(c.date_achat)                                AS premier_achat,
        MAX(c.date_achat)                                AS dernier_achat,
        COUNT(DISTINCT c.order_id) FILTER (
            WHERE c.date_livraison_client <= x.date_reference
              AND c.date_livraison_client > c.date_livraison_estimee
        )                                                AS livraisons_en_retard,
        -- Une livraison postérieure à la date de référence n'est pas encore
        -- connue : son délai ne doit pas entrer dans la moyenne.
        AVG(c.delai_livraison_jours) FILTER (
            WHERE c.date_livraison_client <= x.date_reference
        )                                                AS delai_livraison_moyen
    FROM croisement AS x
    JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = x.customer_unique_id
     AND c.date_achat <= x.date_reference
    LEFT JOIN dwh.v_montant_commande AS m ON m.order_id = c.order_id
    GROUP BY x.customer_unique_id, x.date_reference
),
categories AS (
    SELECT
        x.customer_unique_id,
        x.date_reference,
        COUNT(DISTINCT p.categorie) AS categories_distinctes
    FROM croisement AS x
    JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = x.customer_unique_id AND c.date_achat <= x.date_reference
    JOIN dwh.fait_ligne_commande AS l ON l.order_id = c.order_id
    JOIN dwh.dim_produit AS p ON p.produit_id = l.produit_id
    WHERE p.categorie IS NOT NULL AND p.categorie <> 'inconnu'
    GROUP BY x.customer_unique_id, x.date_reference
),
notes AS (
    -- Les avis vivent en zone intermédiaire : l'entrepôt ne les porte pas.
    -- Une note n'est connue qu'à la date de la RÉPONSE, pas à celle de l'envoi
    -- du questionnaire (review_creation_date) : filtrer sur celle-ci ferait
    -- entrer dans les variables une note donnée après la date de référence.
    SELECT
        x.customer_unique_id,
        x.date_reference,
        AVG(a.review_score)            AS note_moyenne,
        COUNT(DISTINCT a.review_id)    AS avis_donnes
    FROM croisement AS x
    JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = x.customer_unique_id AND c.date_achat <= x.date_reference
    JOIN staging.olist_order_reviews AS a ON a.order_id = c.order_id
    WHERE a.review_answer_timestamp <= x.date_reference
    GROUP BY x.customer_unique_id, x.date_reference
),
avenir AS (
    -- **La réponse observée** : le client a-t-il commandé dans les 180 jours ?
    -- C'est la seule partie de cette vue qui regarde après la date de
    -- référence, et elle ne sert qu'à la cible — jamais aux variables.
    SELECT
        x.customer_unique_id,
        x.date_reference,
        COUNT(c.order_id) > 0 AS a_rachete
    FROM croisement AS x
    LEFT JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = x.customer_unique_id
     AND c.date_achat >  x.date_reference
     AND c.date_achat <= x.date_reference + INTERVAL '180 days'
    GROUP BY x.customer_unique_id, x.date_reference
)
SELECT
    p.customer_unique_id,
    p.date_reference,
    p.commandes,
    ROUND(p.montant_total, 2)                                   AS montant_total,
    ROUND(p.montant_total / NULLIF(p.commandes, 0), 2)          AS montant_moyen,
    (p.date_reference - p.dernier_achat::date)                  AS recence_jours,
    (p.date_reference - p.premier_achat::date)                  AS anciennete_jours,
    ROUND(n.note_moyenne, 2)                                    AS note_moyenne,
    COALESCE(n.avis_donnes, 0)                                  AS avis_donnes,
    ROUND(p.delai_livraison_moyen, 1)                           AS delai_livraison_moyen,
    p.livraisons_en_retard,
    COALESCE(c.categories_distinctes, 0)                        AS categories_distinctes,
    COALESCE(a.a_rachete, false)                                AS a_rachete
FROM passe AS p
LEFT JOIN categories AS c
       ON c.customer_unique_id = p.customer_unique_id AND c.date_reference = p.date_reference
LEFT JOIN notes AS n
       ON n.customer_unique_id = p.customer_unique_id AND n.date_reference = p.date_reference
LEFT JOIN avenir AS a
       ON a.customer_unique_id = p.customer_unique_id AND a.date_reference = p.date_reference;

COMMENT ON VIEW dwh.v_historique_client IS
    'Variables du modele de re-achat, par personne et par date de reference, avec la cible.';
COMMENT ON VIEW dwh.v_commandes_retenues IS
    'Commandes du perimetre du chiffre d affaires : annulees et indisponibles exclues.';