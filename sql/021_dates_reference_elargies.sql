-- Élargissement de dwh.v_dates_reference à 5 fenêtres d'évaluation.
--
-- Règle : une date de référence est valide si date_reference + 180 jours
-- <= MAX(date_achat dans dwh.v_commandes_retenues). Sinon la cible est
-- tronquée (on n'a pas encore vu si le client a racheté), et le taux de
-- rachat mesuré est artificiellement bas.
--
-- Les données Olist couvrent 2016-09 à 2018-09-03. MAX(achat) - 180 j
-- donne 2018-03-07. Les dates 2018-03-31 et 2018-06-30 sont donc exclues.
--
-- Cette vue remplace celle créée dans sql/018_historique_client.sql.

CREATE OR REPLACE VIEW dwh.v_dates_reference AS
SELECT * FROM (VALUES
    (DATE '2016-12-31'),  -- 118 j d'historique, 611 j d'avenir
    (DATE '2017-03-31'),  -- 208 j d'historique, 521 j d'avenir
    (DATE '2017-06-30'),  -- 299 j d'historique, 430 j d'avenir
    (DATE '2017-09-30'),  -- 391 j d'historique, 338 j d'avenir
    (DATE '2017-12-31')   -- 483 j d'historique, 246 j d'avenir
) AS dates(date_reference);

COMMENT ON VIEW dwh.v_dates_reference IS
    'Cinq fenêtres d''évaluation pour le modèle de ré-achat. Une date est '
    'valide si date_reference + 180 jours <= MAX(date_achat). Voir sql/021.';
