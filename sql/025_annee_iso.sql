-- L'année ISO, pour que les semaines s'additionnent.
--
-- Le problème corrigé ici. `dim_date` portait une `semaine_iso` (norme
-- ISO 8601) appariée à une `annee` CIVILE, et `v_ventes_par_semaine`
-- regroupait sur ce couple. Les deux calendriers ne coïncident pas aux
-- frontières d'année :
--
--   2017-01-01   année civile 2017, semaine ISO 52, année ISO 2016
--   2017-12-25   année civile 2017, semaine ISO 52, année ISO 2017
--
-- Le groupe « 2017-S52 » agrégeait donc le 1er janvier avec la semaine de
-- Noël — huit jours pris aux deux extrémités opposées de l'année, dans une
-- seule ligne. Les données Olist couvrent 2016-09 à 2018-09 : le défaut
-- mordait sur les données livrées, et la somme des semaines ne retombait pas
-- sur le chiffre d'affaires total.
--
-- `annee` reste en place : elle est juste, et c'est la bonne colonne pour
-- regrouper par mois ou par trimestre. Seule la semaine change de partenaire.

-- Sur une base neuve, la colonne est déjà déclarée par sql/007 : cet ALTER ne
-- fait rien. Sur une base déjà installée, il l'ajoute — en dernière position,
-- la même qu'en sql/007, pour que la table ait une seule forme possible.
ALTER TABLE dwh.dim_date
    ADD COLUMN IF NOT EXISTS annee_iso INTEGER;

-- Les lignes déjà chargées ne seront pas réécrites par l'intégration :
-- `inserer_dates` fait `ON CONFLICT (date_id) DO NOTHING`. On les complète ici.
--
-- `date_id <> 0` écarte la ligne « inconnu ». Sa date, 1900-01-01, est un
-- remplissage : sql/007 lui donne 0 pour l'année, le mois, la semaine et le
-- jour, précisément pour qu'elle ne se fasse pas passer pour une date réelle.
-- Calculer `EXTRACT(ISOYEAR FROM date)` dessus lui donnerait 1900, et un
-- regroupement par semaine afficherait une ligne « 1900-S0 » là où l'ancienne
-- convention disait « 0-S0 » : une date inconnue déguisée en date connue.
UPDATE dwh.dim_date
   SET annee_iso = EXTRACT(ISOYEAR FROM date)::integer
 WHERE annee_iso IS NULL
   AND date_id <> 0;

UPDATE dwh.dim_date
   SET annee_iso = 0
 WHERE date_id = 0
   AND annee_iso IS DISTINCT FROM 0;

-- Toutes les lignes sont remplies : la colonne devient obligatoire, comme les
-- autres parties de la date. Sans cette contrainte, une insertion qui oublie
-- `annee_iso` ne lèverait aucune erreur et créerait un groupe NULL dans
-- `v_ventes_par_semaine` — une semaine sans nom, dont personne ne verrait
-- qu'elle manque au total.
ALTER TABLE dwh.dim_date
    ALTER COLUMN annee_iso SET NOT NULL;

COMMENT ON COLUMN dwh.dim_date.annee_iso IS
    'Annee ISO 8601, celle a laquelle appartient semaine_iso. Differe de annee '
    'aux frontieres d annee : le 2017-01-01 est en semaine 52 de l annee ISO 2016.';

-- v_ventes_retenues : expose la colonne.
--
-- `CREATE OR REPLACE VIEW` n'autorise que l'AJOUT de colonnes en fin de liste :
-- en insérer une au milieu, en renommer ou en retirer une fait échouer la
-- migration avec « cannot drop columns from view ». `annee_iso` est donc
-- ajoutée en dernier, et l'ordre des colonnes existantes est conservé.
-- La définition est celle de sql/010, reprise à l'identique — colonnes, ordre,
-- jointures et périmètre — avec `d.annee_iso` ajoutée en dernier. Le filtre
-- `statut NOT IN ('canceled', 'unavailable')` est ce qui définit le chiffre
-- d'affaires : l'omettre y ferait entrer les commandes annulées.
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
    c.statut,
    d.annee_iso
FROM dwh.fait_ligne_commande AS l
JOIN dwh.fait_commande       AS c USING (order_id)
JOIN dwh.dim_date            AS d ON d.date_id = l.date_id
WHERE c.statut NOT IN ('canceled', 'unavailable');

-- v_ventes_par_semaine : sa première colonne passe de `annee` à `annee_iso`,
-- ce qu'un remplacement ne permet pas. On la supprime et on la recrée.
-- Aucune autre vue n'en dépend (vérifié sur tout `sql/`) : seule
-- `src/indicateurs/lecture.py` la lit, à l'exécution.
DROP VIEW IF EXISTS dwh.v_ventes_par_semaine;

CREATE VIEW dwh.v_ventes_par_semaine AS
SELECT
    annee_iso,
    semaine_iso,
    MIN(jour)                      AS debut_semaine,
    SUM(prix)                      AS chiffre_affaires,
    COUNT(DISTINCT order_id)       AS commandes,
    ROUND(SUM(prix) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS panier_moyen
FROM dwh.v_ventes_retenues
GROUP BY annee_iso, semaine_iso;

COMMENT ON VIEW dwh.v_ventes_par_semaine IS
    'Ventes par semaine ISO. Regroupe sur (annee_iso, semaine_iso) : avec l annee '
    'civile, le 1er janvier tombait dans la semaine de Noel precedente. Voir sql/025.';
