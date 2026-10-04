-- Historisation du retard des lecteurs du bus (F6.3).
--
-- `scripts/etat_bus.py` photographie le bus à un instant donné : c'est utile
-- pour regarder, inutile pour surveiller. Un retard de mille messages ne dit
-- rien en soi — ce qui compte, c'est **s'il se résorbe**. D'où une table : sans
-- historique, il n'y a pas de tendance, et sans tendance il n'y a rien à
-- surveiller.

CREATE TABLE IF NOT EXISTS staging.retard_flux (
    id         BIGSERIAL   PRIMARY KEY,
    releve_a   TIMESTAMPTZ NOT NULL DEFAULT now(),
    groupe     TEXT        NOT NULL,
    sujet      TEXT        NOT NULL,
    retard     BIGINT      NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_retard_flux_groupe
    ON staging.retard_flux (groupe, sujet, releve_a DESC);

-- Le dernier relevé de chaque lecteur : l'état courant du flux.
CREATE OR REPLACE VIEW staging.v_retard_courant AS
SELECT DISTINCT ON (groupe, sujet)
    groupe, sujet, retard, releve_a
FROM staging.retard_flux
ORDER BY groupe, sujet, releve_a DESC;

-- Les trois derniers relevés de chaque lecteur, avec leur rang.
-- C'est sur eux que se lit la tendance : trois hausses consécutives signalent
-- un lecteur qui décroche, là où un retard stable signale seulement un flux
-- chargé.
CREATE OR REPLACE VIEW staging.v_retard_tendance AS
SELECT groupe, sujet, retard, releve_a, rang
FROM (
    SELECT
        groupe, sujet, retard, releve_a,
        ROW_NUMBER() OVER (PARTITION BY groupe, sujet ORDER BY releve_a DESC) AS rang
    FROM staging.retard_flux
) AS releves
WHERE rang <= 3;

COMMENT ON TABLE staging.retard_flux IS
    'Releves successifs du retard de chaque lecteur du bus.';
COMMENT ON VIEW staging.v_retard_courant IS
    'Dernier releve de chaque lecteur.';
COMMENT ON VIEW staging.v_retard_tendance IS
    'Trois derniers releves par lecteur, pour juger si le retard se resorbe.';
