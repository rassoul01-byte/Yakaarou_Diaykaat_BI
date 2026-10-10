-- La date de référence du segment à retenir est un CHOIX, pas un maximum.
--
-- Le problème corrigé ici. `sql/019` filtrait le segment sur
-- `MAX(date_reference)` de `dwh.v_dates_reference`. Tant que cette vue
-- s'arrêtait au 2017-09-30, les deux coïncidaient. `sql/021` l'a élargie à
-- cinq fenêtres d'évaluation pour le modèle, portant ce maximum au
-- 2017-12-31 — et a donc déplacé le segment sans que personne le demande.
--
-- Conséquence : tous les chiffres publiés (711 clients, 32 ré-achats,
-- 4,5 % contre 1,58 %, soit 2,85 fois mieux) sont mesurés au 2017-09-30 et
-- figurent dans quatre documents — docs/dictionnaire_indicateurs.md,
-- docs/contrats/modele.md, docs/dossier_conception.md et le README. L'API
-- lit la vue en direct (src/indicateurs/lecture.py), donc le tableau de bord
-- affichait un effectif et une date que la documentation contredit.
--
-- La correction ne consiste pas à remettre le maximum au 2017-09-30 : ce
-- serait reproduire la même fragilité, où ajouter une fenêtre d'évaluation
-- déplace un livrable. Les deux besoins sont distincts et doivent avoir
-- chacun leur vue :
--
--   dwh.v_dates_reference  les fenêtres sur lesquelles le modèle s'évalue.
--                          Élargir cette liste est sans effet sur le segment.
--   dwh.v_date_segment     la date à laquelle le segment est publié. Un seul
--                          endroit à changer, et la changer oblige à refaire
--                          l'évaluation et à reprendre les quatre documents.

CREATE OR REPLACE VIEW dwh.v_date_segment AS
SELECT DATE '2017-09-30' AS date_reference;

COMMENT ON VIEW dwh.v_date_segment IS
    'Date de reference du segment publie. Choix documente, pas un maximum : '
    'la changer impose de refaire l evaluation et de reprendre le dictionnaire, '
    'le contrat du modele, le dossier de conception et le README.';

-- Remplace la définition de sql/019, reprise à l'identique par sql/022.
CREATE OR REPLACE VIEW dwh.v_segment_a_retenir AS
SELECT
    h.customer_unique_id,
    h.date_reference,
    h.commandes,
    h.montant_total,
    h.recence_jours
FROM dwh.v_historique_client AS h
WHERE h.commandes >= 2
  AND h.date_reference = (SELECT date_reference FROM dwh.v_date_segment);

COMMENT ON VIEW dwh.v_segment_a_retenir IS
    'Segment a retenir : personnes avec au moins 2 commandes a la date de '
    'dwh.v_date_segment (2017-09-30). Regle simple retenue plutot que le modele, '
    'apres lecture de l evaluation. Voir sql/024.';
