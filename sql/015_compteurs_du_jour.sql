-- Compteurs du jour, alimentés en continu par le bus (F2.5, F2.4, F4.4).
--
-- Ces compteurs ne passent PAS par l'entrepôt : c'est la voie continue du
-- dossier de conception. Ils répondent à « que se passe-t-il maintenant »,
-- quand l'entrepôt répond à « qu'avons-nous vendu ».
--
-- ⚠️ Aucun montant ici. Un événement d'achat ne porte pas de prix — le contrat
-- d'événements n'en prévoit pas, et le catalogue produits n'en contient pas.
-- Les compteurs mesurent donc l'ACTIVITÉ, jamais le chiffre d'affaires. Un
-- chiffre d'affaires temps réel serait un montant inventé.

-- Chaque événement retenu, une fois et une seule.
-- La clé primaire porte sur id_evenement : un message reçu deux fois — ce que
-- le bus autorise explicitement — ne compte qu'une fois. C'est toute la
-- protection contre le double comptage, et elle est dans la base, pas dans le
-- code.
CREATE TABLE IF NOT EXISTS staging.evenements_du_jour (
    id_evenement        TEXT        PRIMARY KEY,
    type                TEXT        NOT NULL,
    horodatage          TIMESTAMPTZ NOT NULL,
    jour                DATE        NOT NULL,
    id_session          TEXT        NOT NULL,
    customer_unique_id  TEXT,
    id_produit          TEXT,
    requete             TEXT,
    recu_a              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evenements_jour ON staging.evenements_du_jour (jour, type);
CREATE INDEX IF NOT EXISTS idx_evenements_session ON staging.evenements_du_jour (id_session);

-- L'activité par jour : le compteur principal.
CREATE OR REPLACE VIEW staging.v_activite_par_jour AS
SELECT
    jour,
    COUNT(*)                                             AS evenements,
    COUNT(DISTINCT id_session)                           AS sessions,
    COUNT(*) FILTER (WHERE type = 'page_vue')            AS pages_vues,
    COUNT(*) FILTER (WHERE type = 'recherche')           AS recherches,
    COUNT(*) FILTER (WHERE type = 'ajout_panier')        AS ajouts_panier,
    COUNT(*) FILTER (WHERE type = 'achat')               AS achats,
    COUNT(DISTINCT customer_unique_id)                   AS clients_identifies
FROM staging.evenements_du_jour
GROUP BY jour;

-- Le taux de conversion : part des sessions qui se terminent par un achat.
-- Le comptage se fait par session, et non par visiteur : id_session est la clé
-- de partition du bus, donc tous les événements d'une session sont lus dans
-- l'ordre par le même consommateur. Aucune reconstitution n'est nécessaire.
CREATE OR REPLACE VIEW staging.v_taux_conversion AS
WITH sessions AS (
    SELECT
        jour,
        id_session,
        BOOL_OR(type = 'achat') AS a_achete
    FROM staging.evenements_du_jour
    GROUP BY jour, id_session
)
SELECT
    jour,
    COUNT(*)                                   AS sessions,
    COUNT(*) FILTER (WHERE a_achete)           AS sessions_avec_achat,
    ROUND(100.0 * COUNT(*) FILTER (WHERE a_achete) / NULLIF(COUNT(*), 0), 2)
        AS taux_conversion_pourcent
FROM sessions
GROUP BY jour;

-- Le journal des requêtes (F4.4) : ce que les visiteurs cherchent.
-- Les requêtes sans résultat seront croisées avec l'index au Sprint 4 (F4.5) ;
-- ici, on conserve d'abord ce qui est demandé.
CREATE OR REPLACE VIEW staging.v_journal_requetes AS
SELECT
    jour,
    lower(btrim(requete))                AS requete,
    COUNT(*)                             AS occurrences,
    COUNT(DISTINCT id_session)           AS sessions,
    MAX(horodatage)                      AS derniere_recherche
FROM staging.evenements_du_jour
WHERE type = 'recherche' AND requete IS NOT NULL AND btrim(requete) <> ''
GROUP BY jour, lower(btrim(requete));

COMMENT ON TABLE staging.evenements_du_jour IS
    'Evenements de navigation retenus, dedoublonnes sur id_evenement.';
COMMENT ON VIEW staging.v_activite_par_jour IS
    'Compteurs d activite par jour. Aucun montant : les evenements n en portent pas.';
COMMENT ON VIEW staging.v_taux_conversion IS
    'Part des sessions terminees par un achat, par jour.';
COMMENT ON VIEW staging.v_journal_requetes IS
    'Ce que les visiteurs cherchent, par jour et par requete.';
