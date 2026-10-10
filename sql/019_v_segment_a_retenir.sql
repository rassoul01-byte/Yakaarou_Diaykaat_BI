-- Segment a retenir (livrable 5).
-- Regle retenue : au moins deux commandes a la date de reference.
-- Choisie apres lecture de l'evaluation du modele (voir dictionnaire et
-- docs/contrats/modele.md). Source : dwh.v_historique_client.
-- Une ligne par personne, a la date de reference la plus recente.

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