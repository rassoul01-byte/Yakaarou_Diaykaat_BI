-- Les vues qui calculent les indicateurs de ventes.
--
-- C'est ici, et nulle part ailleurs, que vivent les formules : le rapport en
-- ligne de commande et le tableau de bord mettent en forme ce que ces vues
-- calculent, ils ne recalculent rien. Deux formules pour un même indicateur,
-- c'est deux chiffres différents à la soutenance.
--
-- Définitions complètes : docs/dictionnaire_indicateurs.md
--
-- Trois décisions de périmètre, à confirmer par le Product Owner. Elles sont
-- regroupées dans la vue ci-dessous pour qu'un changement d'avis ne touche
-- qu'un seul endroit :
--   1. les frais de port sont EXCLUS du chiffre d'affaires ;
--   2. les commandes annulées et indisponibles sont EXCLUES ;
--   3. une commande sans ligne d'article pèse zéro et ne compte pas.

-- Le socle : une ligne par ligne d'article retenue dans le chiffre d'affaires.
-- Changer le périmètre des ventes, c'est changer cette vue, et elle seule.
CREATE OR REPLACE VIEW dwh.v_ventes_retenues AS
SELECT
    l.order_id,
    l.order_item_id,
    l.produit_id,
    l.vendeur_id,
    l.date_id,
    d.date        AS jour,
    d.annee,
    d.mois,
    d.semaine_iso,
    l.prix,
    l.frais_port,
    l.quantite,
    c.statut
FROM dwh.fait_ligne_commande AS l
JOIN dwh.fait_commande       AS c USING (order_id)
JOIN dwh.dim_date            AS d ON d.date_id = l.date_id
WHERE c.statut NOT IN ('canceled', 'unavailable');

-- Chiffre d'affaires, commandes et panier moyen, par jour.
CREATE OR REPLACE VIEW dwh.v_ventes_par_jour AS
SELECT
    jour,
    annee,
    mois,
    SUM(prix)                      AS chiffre_affaires,
    COUNT(DISTINCT order_id)       AS commandes,
    SUM(quantite)                  AS articles,
    SUM(frais_port)                AS frais_port,
    ROUND(SUM(prix) / COUNT(DISTINCT order_id), 2) AS panier_moyen
FROM dwh.v_ventes_retenues
GROUP BY jour, annee, mois;

CREATE OR REPLACE VIEW dwh.v_ventes_par_semaine AS
SELECT
    annee,
    semaine_iso,
    MIN(jour)                      AS debut_semaine,
    SUM(prix)                      AS chiffre_affaires,
    COUNT(DISTINCT order_id)       AS commandes,
    ROUND(SUM(prix) / COUNT(DISTINCT order_id), 2) AS panier_moyen
FROM dwh.v_ventes_retenues
GROUP BY annee, semaine_iso;

CREATE OR REPLACE VIEW dwh.v_ventes_par_mois AS
SELECT
    annee,
    mois,
    SUM(prix)                      AS chiffre_affaires,
    COUNT(DISTINCT order_id)       AS commandes,
    SUM(quantite)                  AS articles,
    ROUND(SUM(prix) / COUNT(DISTINCT order_id), 2) AS panier_moyen
FROM dwh.v_ventes_retenues
GROUP BY annee, mois;

-- Les produits les plus vendus. La ligne « inconnu » des dimensions apparaît
-- comme n'importe quel produit : un classement qui cache ce qu'il ignore
-- donne une fausse impression de complétude.
CREATE OR REPLACE VIEW dwh.v_produits_les_plus_vendus AS
SELECT
    p.id_produit_olist,
    p.categorie,
    p.categorie_catalogue,
    p.rattache,
    SUM(v.prix)                    AS chiffre_affaires,
    SUM(v.quantite)                AS articles,
    COUNT(DISTINCT v.order_id)     AS commandes
FROM dwh.v_ventes_retenues AS v
JOIN dwh.dim_produit       AS p ON p.produit_id = v.produit_id
GROUP BY p.id_produit_olist, p.categorie, p.categorie_catalogue, p.rattache;

CREATE OR REPLACE VIEW dwh.v_categories_les_plus_vendues AS
SELECT
    COALESCE(NULLIF(p.categorie, ''), 'inconnu') AS categorie,
    SUM(v.prix)                    AS chiffre_affaires,
    SUM(v.quantite)                AS articles,
    COUNT(DISTINCT v.order_id)     AS commandes,
    COUNT(DISTINCT p.id_produit_olist) AS produits
FROM dwh.v_ventes_retenues AS v
JOIN dwh.dim_produit       AS p ON p.produit_id = v.produit_id
GROUP BY COALESCE(NULLIF(p.categorie, ''), 'inconnu');

-- Le total de référence : c'est lui qu'on recoupe avec la somme des mois.
CREATE OR REPLACE VIEW dwh.v_ventes_totales AS
SELECT
    SUM(prix)                      AS chiffre_affaires,
    COUNT(DISTINCT order_id)       AS commandes,
    SUM(quantite)                  AS articles,
    MIN(jour)                      AS premier_jour,
    MAX(jour)                      AS dernier_jour,
    ROUND(SUM(prix) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS panier_moyen
FROM dwh.v_ventes_retenues;

COMMENT ON VIEW dwh.v_ventes_retenues IS
    'Perimetre des ventes : frais de port exclus, commandes annulees et indisponibles exclues.';
