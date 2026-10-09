-- Enrichissement de dwh.v_historique_client avec 6 nouvelles features.
--
-- But : améliorer la discrimination du modèle de ré-achat sans changer
-- ni la cible, ni la méthode (régression logistique, mêmes dates).
-- Voir la phase 0 pour la ligne de base : le modèle ne bat pas la règle
-- « deux commandes ou plus » sur le poolé, l'avantage au top 100 (2017-09-30)
-- n'est pas établi (intervalles de confiance chevauchants).
--
-- Nouvelles variables :
--   ecart_type_intervalles       STDDEV des jours entre commandes
--   ratio_commandes_recentes     commandes 90 derniers jours / total
--   ecart_type_notes             STDDEV des review_score
--   ecart_delai_estime_reel      moyenne (date_livraison - date_estimee)
--   velocite_achat               commandes / mois depuis le 1er achat
--   part_paiement_credit_card    part des paiements par carte de crédit
--
-- Règle anti-fuite : toutes les features utilisent uniquement des données
-- connues à la date de référence (date_achat, date_livraison_client et
-- review_answer_timestamp <= date_reference).

-- La vue v_segment_a_retenir dépend de v_historique_client : on les supprime
-- dans l'ordre des dépendances avant de recréer. CREATE OR REPLACE VIEW ne
-- peut pas ajouter de colonne à une vue existante (PostgreSQL refuse).
DROP VIEW IF EXISTS dwh.v_segment_a_retenir;
DROP VIEW IF EXISTS dwh.v_historique_client;

CREATE VIEW dwh.v_historique_client AS
WITH croisement AS (
    -- Chaque personne ayant déjà commandé, pour chacune des dates de référence.
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
        COUNT(DISTINCT c.order_id)  AS commandes,
        COALESCE(SUM(m.montant), 0)  AS montant_total,
        MIN(c.date_achat)  AS premier_achat,
        MAX(c.date_achat)  AS dernier_achat,
        COUNT(DISTINCT c.order_id) FILTER (
            WHERE c.date_livraison_client <= x.date_reference
              AND c.date_livraison_client > c.date_livraison_estimee
        )  AS livraisons_en_retard,
        AVG(c.delai_livraison_jours) FILTER (
            WHERE c.date_livraison_client <= x.date_reference
        )  AS delai_livraison_moyen,

        -- Ratio de commandes dans les 90 derniers jours.
        COUNT(DISTINCT c.order_id) FILTER (
            WHERE c.date_achat > x.date_reference - INTERVAL '90 days'
        )::numeric / NULLIF(COUNT(DISTINCT c.order_id), 0)
            AS ratio_commandes_recentes,

        -- Écart moyen entre la livraison réelle et la livraison estimée
        -- (en jours). Positif = en retard.
        AVG(
            EXTRACT(EPOCH FROM (c.date_livraison_client - c.date_livraison_estimee)) / 86400
        ) FILTER (
            WHERE c.date_livraison_client <= x.date_reference
        )  AS ecart_delai_estime_reel,

        -- Vélocité d'achat : commandes par mois depuis le premier achat.
        -- GREATEST évite la division par zéro pour les clients d'un seul jour.
        COUNT(DISTINCT c.order_id)::numeric / GREATEST(
            EXTRACT(EPOCH FROM (x.date_reference - MIN(c.date_achat))) / 86400 / 30,
            1
        )  AS velocite_achat
    FROM croisement AS x
    JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = x.customer_unique_id
     AND c.date_achat <= x.date_reference
    LEFT JOIN dwh.v_montant_commande AS m ON m.order_id = c.order_id
    GROUP BY x.customer_unique_id, x.date_reference
),
intervalles AS (
    -- Écart-type des intervalles entre commandes consécutives.
    -- Le LAG partitionne par (client, date_reference) pour que chaque
    -- fenêtre ait son propre calcul — sinon les commandes futures d'une
    -- autre date de référence contamineraient la fenêtre courante.
    SELECT
        customer_unique_id,
        date_reference,
        STDDEV(jours_entre)  AS ecart_type_intervalles
    FROM (
        SELECT
            c.customer_unique_id,
            x.date_reference,
            EXTRACT(EPOCH FROM (
                c.date_achat - LAG(c.date_achat) OVER (
                    PARTITION BY c.customer_unique_id, x.date_reference
                    ORDER BY c.date_achat
                )
            )) / 86400  AS jours_entre
        FROM croisement AS x
        JOIN dwh.v_commandes_retenues AS c
          ON c.customer_unique_id = x.customer_unique_id
         AND c.date_achat <= x.date_reference
    ) AS sous_requete
    WHERE jours_entre IS NOT NULL
    GROUP BY customer_unique_id, date_reference
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
        COUNT(DISTINCT a.review_id)    AS avis_donnes,
        STDDEV(a.review_score)          AS ecart_type_notes
    FROM croisement AS x
    JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = x.customer_unique_id AND c.date_achat <= x.date_reference
    JOIN staging.olist_order_reviews AS a ON a.order_id = c.order_id
    WHERE a.review_answer_timestamp <= x.date_reference
    GROUP BY x.customer_unique_id, x.date_reference
),
paiements AS (
    -- Part des paiements par carte de crédit dans l'historique du client.
    -- Un client qui n'a jamais commandé n'apparaît pas ici (LEFT JOIN plus bas).
    SELECT
        x.customer_unique_id,
        x.date_reference,
        COUNT(*) FILTER (WHERE p.payment_type = 'credit_card')::numeric
            / NULLIF(COUNT(*), 0)  AS part_paiement_credit_card
    FROM croisement AS x
    JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = x.customer_unique_id AND c.date_achat <= x.date_reference
    JOIN staging.olist_order_payments AS p ON p.order_id = c.order_id
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
    ROUND(p.montant_total, 2)         AS montant_total,
    ROUND(p.montant_total / NULLIF(p.commandes, 0), 2)         AS montant_moyen,
    (p.date_reference - p.dernier_achat::date)         AS recence_jours,
    (p.date_reference - p.premier_achat::date)         AS anciennete_jours,
    ROUND(n.note_moyenne, 2)         AS note_moyenne,
    COALESCE(n.avis_donnes, 0)         AS avis_donnes,
    ROUND(p.delai_livraison_moyen, 1)         AS delai_livraison_moyen,
    p.livraisons_en_retard,
    COALESCE(c.categories_distinctes, 0)         AS categories_distinctes,
    -- Nouvelles features
    ROUND(COALESCE(i.ecart_type_intervalles, 0)::numeric, 2)
        AS ecart_type_intervalles,
    ROUND(COALESCE(p.ratio_commandes_recentes, 0)::numeric, 4)
        AS ratio_commandes_recentes,
    ROUND(COALESCE(n.ecart_type_notes, 0)::numeric, 2)
        AS ecart_type_notes,
    ROUND(COALESCE(p.ecart_delai_estime_reel, 0)::numeric, 1)
        AS ecart_delai_estime_reel,
    ROUND(COALESCE(p.velocite_achat, 0)::numeric, 4)
        AS velocite_achat,
    ROUND(COALESCE(pa.part_paiement_credit_card, 0)::numeric, 4)
        AS part_paiement_credit_card,
    COALESCE(a.a_rachete, false)         AS a_rachete
FROM passe AS p
LEFT JOIN intervalles AS i
       ON i.customer_unique_id = p.customer_unique_id AND i.date_reference = p.date_reference
LEFT JOIN categories AS c
       ON c.customer_unique_id = p.customer_unique_id AND c.date_reference = p.date_reference
LEFT JOIN notes AS n
       ON n.customer_unique_id = p.customer_unique_id AND n.date_reference = p.date_reference
LEFT JOIN paiements AS pa
       ON pa.customer_unique_id = p.customer_unique_id AND pa.date_reference = p.date_reference
LEFT JOIN avenir AS a
       ON a.customer_unique_id = p.customer_unique_id AND a.date_reference = p.date_reference;

COMMENT ON VIEW dwh.v_historique_client IS
    'Variables du modele de re-achat enrichies (16 variables), par personne '
    'et par date de reference, avec la cible a_rachete a 180 jours.';

-- v_segment_a_retenir : recréée à l'identique (elle dépendait de la vue
-- précédente, qui vient d'être remplacée).
CREATE OR REPLACE VIEW dwh.v_segment_a_retenir AS
SELECT
    h.customer_unique_id,
    h.date_reference,
    h.commandes,
    h.montant_total,
    h.recence_jours
FROM dwh.v_historique_client AS h
WHERE h.commandes >= 2
  AND h.date_reference = (SELECT MAX(date_reference) FROM dwh.v_dates_reference);

COMMENT ON VIEW dwh.v_segment_a_retenir IS
    'Segment a retenir : personnes avec au moins 2 commandes a la date de reference la plus recente. Regle simple retenue plutot que le modele.';
