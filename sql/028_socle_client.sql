-- Le socle client : une passe d'agrégation, lisible par tout le monde.
--
-- CE QUE CETTE MIGRATION CORRIGE
--
-- Le tableau de bord affiche un seul nombre tiré du segment — « 711 clients » —
-- et pour l'obtenir il lançait :
--
--     SELECT COUNT(*) FROM dwh.v_segment_a_retenir
--
-- Mesuré sur un entrepôt au volume réel (99 441 commandes, 111 853 lignes,
-- 96 096 personnes, 99 224 avis, 103 417 paiements) : **2,1 secondes**, et
-- 1,18 million de pages tampon lues — neuf gigaoctets de trafic mémoire pour
-- compter 711 lignes. Sur les 2,7 s de SQL de la page, le segment en pesait 2,1.
--
-- Deux causes, et aucune n'est le volume des données.
--
-- 1. `v_segment_a_retenir` lit `v_historique_client`, qui calcule les seize
--    variables du modèle de ré-achat dans sept CTE : une fenêtre glissante sur
--    les intervalles entre commandes, une jointure sur les avis, une sur les
--    paiements, une sur les catégories, et la cible à 180 jours. Le segment
--    n'utilise que cinq colonnes, toutes issues de la première CTE. Les six
--    autres étaient calculées puis jetées — PostgreSQL ne sait pas supprimer
--    une jointure externe sur une sous-requête agrégée, même si aucune de ses
--    colonnes n'est lue.
--
-- 2. La CTE `croisement` est référencée sept fois, donc matérialisée. Le
--    prédicat `date_reference = '2017-09-30'` ne peut pas y descendre : les
--    cinq fenêtres d'évaluation (`sql/021`) étaient croisées avec les 96 096
--    personnes — 185 359 lignes, écrites sur disque faute de mémoire de tri —
--    pour n'en garder qu'une à la fin.
--
-- CE QUE FAIT LA CORRECTION
--
-- `croisement` et `passe` fusionnent en une vue : `dwh.v_socle_client`. Le
-- `GROUP BY` produit exactement les mêmes groupes que le `DISTINCT` du
-- croisement — même source, même filtre — et calcule les agrégats dans la même
-- passe au lieu de rejoindre une CTE matérialisée. Un prédicat sur
-- `date_reference` descend alors jusqu'au `WHERE`.
--
-- Au-dessus du socle, rien ne change de nom ni de contenu :
--
--   dwh.v_socle_client        NOUVEAU. Une ligne par personne et par date de
--                             référence : commandes, montants, premier et
--                             dernier achat, livraisons en retard, délai subi,
--                             et les trois variables dérivées du même passage.
--   dwh.v_historique_client   mêmes 19 colonnes, mêmes 185 359 lignes, mêmes
--                             valeurs — vérifié par somme MD5 sur le résultat
--                             entier, identique avant et après.
--   dwh.v_segment_a_retenir   mêmes 5 colonnes, mêmes lignes. Lit le socle
--                             directement : plus de détour par les variables
--                             du modèle, qu'il n'a jamais utilisées.
--
-- Mesures sur le même entrepôt, trois exécutions chacune :
--
--   COUNT(*) sur le segment            2 118 / 2 114 / 1 998 ms  →  77 / 76 / 77 ms
--   lecture complète de l'historique     5 600 / 5 737 ms        →  5 212 / 5 556 ms
--
-- Le segment est vingt-sept fois plus rapide ; l'entraînement du modèle, qui
-- lit tout l'historique, n'est pas pénalisé.
--
-- CE QUE CETTE MIGRATION NE FAIT PAS
--
-- Elle ne touche à aucune définition métier. Le périmètre des commandes reste
-- `dwh.v_commandes_retenues`, la règle du segment reste `commandes >= 2` à la
-- date de `dwh.v_date_segment`, et la règle anti-fuite reste entière : toutes
-- les variables ne lisent que ce qui était connu à la date de référence, seule
-- `a_rachete` regarde après. Le compte des commandes vit maintenant à **un
-- seul endroit** — le socle — au lieu d'être recalculé dans la CTE `passe` pour
-- le modèle et relu à travers elle pour le segment.

-- Ordre des dépendances : le segment, puis l'historique, puis le socle.
DROP VIEW IF EXISTS dwh.v_segment_a_retenir;
DROP VIEW IF EXISTS dwh.v_historique_client;
DROP VIEW IF EXISTS dwh.v_socle_client;

-- ---------------------------------------------------------------- le socle
--
-- Une ligne par personne et par date de référence, pour toute personne ayant
-- commandé avant cette date. Tout ce qui se calcule en une passe sur les
-- commandes du client est ici ; ce qui demande une autre table est au-dessus.
CREATE VIEW dwh.v_socle_client AS
SELECT
    c.customer_unique_id,
    d.date_reference,
    COUNT(DISTINCT c.order_id)                       AS commandes,
    COALESCE(SUM(m.montant), 0)                      AS montant_total,
    MIN(c.date_achat)                                AS premier_achat,
    MAX(c.date_achat)                                AS dernier_achat,

    -- Une livraison postérieure à la date de référence n'est pas encore connue :
    -- ni son retard, ni son délai n'entrent dans les variables.
    COUNT(DISTINCT c.order_id) FILTER (
        WHERE c.date_livraison_client <= d.date_reference
          AND c.date_livraison_client > c.date_livraison_estimee
    )                                                AS livraisons_en_retard,
    AVG(c.delai_livraison_jours) FILTER (
        WHERE c.date_livraison_client <= d.date_reference
    )                                                AS delai_livraison_moyen,

    -- Part des commandes passées dans les 90 derniers jours.
    COUNT(DISTINCT c.order_id) FILTER (
        WHERE c.date_achat > d.date_reference - INTERVAL '90 days'
    )::numeric / NULLIF(COUNT(DISTINCT c.order_id), 0)
                                                     AS ratio_commandes_recentes,

    -- Écart moyen entre livraison réelle et livraison estimée, en jours.
    -- Positif = en retard.
    AVG(
        EXTRACT(EPOCH FROM (c.date_livraison_client - c.date_livraison_estimee)) / 86400
    ) FILTER (
        WHERE c.date_livraison_client <= d.date_reference
    )                                                AS ecart_delai_estime_reel,

    -- Vélocité d'achat : commandes par mois depuis le premier achat.
    -- GREATEST évite la division par zéro pour les clients d'un seul jour.
    COUNT(DISTINCT c.order_id)::numeric / GREATEST(
        EXTRACT(EPOCH FROM (d.date_reference - MIN(c.date_achat))) / 86400 / 30, 1
    )                                                AS velocite_achat
FROM dwh.v_commandes_retenues AS c
CROSS JOIN dwh.v_dates_reference AS d
LEFT JOIN dwh.v_montant_commande AS m ON m.order_id = c.order_id
WHERE c.date_achat <= d.date_reference
GROUP BY c.customer_unique_id, d.date_reference;

COMMENT ON VIEW dwh.v_socle_client IS
    'Socle du modele et du segment : une ligne par personne et par date de '
    'reference, agregee en une passe sur ses commandes retenues. Le compte de '
    'commandes vit ici et nulle part ailleurs. Voir sql/028.';

-- -------------------------------------------------------------- l'historique
--
-- Le socle, plus ce qui exige une autre table : les intervalles entre
-- commandes, les catégories, les avis, les paiements, et la cible observée.
-- Mêmes colonnes et mêmes valeurs que sql/022.
CREATE VIEW dwh.v_historique_client AS
WITH intervalles AS (
    -- Écart-type des intervalles entre commandes consécutives. Le LAG
    -- partitionne par (client, date_reference) pour que chaque fenêtre ait son
    -- propre calcul — sinon les commandes d'une autre date de référence
    -- contamineraient la fenêtre courante.
    SELECT customer_unique_id, date_reference, STDDEV(jours_entre) AS ecart_type_intervalles
    FROM (
        SELECT
            c.customer_unique_id,
            d.date_reference,
            EXTRACT(EPOCH FROM (
                c.date_achat - LAG(c.date_achat) OVER (
                    PARTITION BY c.customer_unique_id, d.date_reference
                    ORDER BY c.date_achat
                )
            )) / 86400 AS jours_entre
        FROM dwh.v_commandes_retenues AS c
        CROSS JOIN dwh.v_dates_reference AS d
        WHERE c.date_achat <= d.date_reference
    ) AS sous_requete
    WHERE jours_entre IS NOT NULL
    GROUP BY customer_unique_id, date_reference
),
categories AS (
    SELECT
        c.customer_unique_id,
        d.date_reference,
        COUNT(DISTINCT p.categorie) AS categories_distinctes
    FROM dwh.v_commandes_retenues AS c
    CROSS JOIN dwh.v_dates_reference AS d
    JOIN dwh.fait_ligne_commande AS l ON l.order_id = c.order_id
    JOIN dwh.dim_produit AS p ON p.produit_id = l.produit_id
    WHERE c.date_achat <= d.date_reference
      AND p.categorie IS NOT NULL AND p.categorie <> 'inconnu'
    GROUP BY c.customer_unique_id, d.date_reference
),
notes AS (
    -- Les avis vivent en zone intermédiaire : l'entrepôt ne les porte pas.
    -- Une note n'est connue qu'à la date de la RÉPONSE, pas à celle de l'envoi
    -- du questionnaire (review_creation_date) : filtrer sur celle-ci ferait
    -- entrer dans les variables une note donnée après la date de référence.
    SELECT
        c.customer_unique_id,
        d.date_reference,
        AVG(a.review_score)         AS note_moyenne,
        COUNT(DISTINCT a.review_id) AS avis_donnes,
        STDDEV(a.review_score)      AS ecart_type_notes
    FROM dwh.v_commandes_retenues AS c
    CROSS JOIN dwh.v_dates_reference AS d
    JOIN staging.olist_order_reviews AS a ON a.order_id = c.order_id
    WHERE c.date_achat <= d.date_reference
      AND a.review_answer_timestamp <= d.date_reference
    GROUP BY c.customer_unique_id, d.date_reference
),
paiements AS (
    -- Part des paiements par carte de crédit dans l'historique du client.
    SELECT
        c.customer_unique_id,
        d.date_reference,
        COUNT(*) FILTER (WHERE p.payment_type = 'credit_card')::numeric
            / NULLIF(COUNT(*), 0) AS part_paiement_credit_card
    FROM dwh.v_commandes_retenues AS c
    CROSS JOIN dwh.v_dates_reference AS d
    JOIN staging.olist_order_payments AS p ON p.order_id = c.order_id
    WHERE c.date_achat <= d.date_reference
    GROUP BY c.customer_unique_id, d.date_reference
),
avenir AS (
    -- **La réponse observée** : le client a-t-il commandé dans les 180 jours ?
    -- C'est la seule partie de cette vue qui regarde après la date de
    -- référence, et elle ne sert qu'à la cible — jamais aux variables.
    SELECT
        s.customer_unique_id,
        s.date_reference,
        COUNT(c.order_id) > 0 AS a_rachete
    FROM dwh.v_socle_client AS s
    LEFT JOIN dwh.v_commandes_retenues AS c
      ON c.customer_unique_id = s.customer_unique_id
     AND c.date_achat >  s.date_reference
     AND c.date_achat <= s.date_reference + INTERVAL '180 days'
    GROUP BY s.customer_unique_id, s.date_reference
)
SELECT
    p.customer_unique_id,
    p.date_reference,
    p.commandes,
    ROUND(p.montant_total, 2)                                    AS montant_total,
    ROUND(p.montant_total / NULLIF(p.commandes, 0), 2)           AS montant_moyen,
    (p.date_reference - p.dernier_achat::date)                   AS recence_jours,
    (p.date_reference - p.premier_achat::date)                   AS anciennete_jours,
    ROUND(n.note_moyenne, 2)                                     AS note_moyenne,
    COALESCE(n.avis_donnes, 0)                                   AS avis_donnes,
    ROUND(p.delai_livraison_moyen, 1)                            AS delai_livraison_moyen,
    p.livraisons_en_retard,
    COALESCE(c.categories_distinctes, 0)                         AS categories_distinctes,
    ROUND(COALESCE(i.ecart_type_intervalles, 0)::numeric, 2)     AS ecart_type_intervalles,
    ROUND(COALESCE(p.ratio_commandes_recentes, 0)::numeric, 4)   AS ratio_commandes_recentes,
    ROUND(COALESCE(n.ecart_type_notes, 0)::numeric, 2)           AS ecart_type_notes,
    ROUND(COALESCE(p.ecart_delai_estime_reel, 0)::numeric, 1)    AS ecart_delai_estime_reel,
    ROUND(COALESCE(p.velocite_achat, 0)::numeric, 4)             AS velocite_achat,
    ROUND(COALESCE(pa.part_paiement_credit_card, 0)::numeric, 4) AS part_paiement_credit_card,
    COALESCE(a.a_rachete, false)                                 AS a_rachete
FROM dwh.v_socle_client AS p
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
    'et par date de reference, avec la cible a_rachete a 180 jours. Assise sur '
    'dwh.v_socle_client depuis sql/028 : memes colonnes, memes valeurs.';

-- ----------------------------------------------------------------- le segment
--
-- La règle est inchangée : au moins deux commandes, à la date publiée par
-- `dwh.v_date_segment`. Elle lit le socle et non l'historique, parce qu'elle
-- n'a jamais eu besoin des variables du modèle.
CREATE VIEW dwh.v_segment_a_retenir AS
SELECT
    s.customer_unique_id,
    s.date_reference,
    s.commandes,
    ROUND(s.montant_total, 2)                  AS montant_total,
    (s.date_reference - s.dernier_achat::date) AS recence_jours
FROM dwh.v_socle_client AS s
WHERE s.commandes >= 2
  AND s.date_reference = (SELECT date_reference FROM dwh.v_date_segment);

COMMENT ON VIEW dwh.v_segment_a_retenir IS
    'Segment a retenir : personnes avec au moins 2 commandes a la date de '
    'dwh.v_date_segment (2017-09-30). Regle simple retenue plutot que le '
    'modele, apres lecture de l evaluation. Lit dwh.v_socle_client : memes '
    'lignes qu avant sql/028, 27 fois plus vite.';
