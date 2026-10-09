-- Provenance de la question dans le journal de l'assistant.
--
-- Pourquoi : l'assistant hésite souvent. Sur le jeu gelé du 2026-10-07, il trouve le bon
-- passage pour 29 des 31 questions couvertes mais n'en affirme qu'une douzaine ; pour les
-- autres il propose des suggestions. Quand un client clique une suggestion, il nous dit
-- quelque chose qu'aucune mesure ne donne : SA formulation voulait dire CE passage.
--
-- Ces deux colonnes gardent ce couple :
--   origine        'saisie' (tapée), 'exemple' (question d'exemple de la page),
--                  'suggestion' (il a tapé autre chose, puis cliqué une suggestion).
--   reformulation  ce qu'il avait tapé avant de cliquer, masqué comme la question.
--                  Nulle pour 'saisie' et 'exemple' : la question EST la formulation,
--                  et la compter deux fois gonflerait la vue ci-dessous.
--
-- Rien n'entre dans docs/documentaire/faq.jsonl automatiquement : la vue sert à une
-- RELECTURE humaine (contrat faq.md, §3 — une réponse doit pouvoir être justifiée).
-- Un journal non relu est aussi une porte d'entrée : une phrase tapée exprès pourrait
-- se retrouver indexée.

ALTER TABLE staging.journal_assistant
    ADD COLUMN IF NOT EXISTS origine TEXT NOT NULL DEFAULT 'saisie'
        CHECK (origine IN ('saisie', 'exemple', 'suggestion')),
    ADD COLUMN IF NOT EXISTS reformulation TEXT;

-- Les paires à relire : une formulation de client, le passage qui l'a satisfait.
-- `echanges` compte combien de fois la même formulation a mené au même passage — une
-- formulation vue plusieurs fois mérite d'entrer dans la base avant une vue une fois.
CREATE OR REPLACE VIEW staging.v_reformulations AS
SELECT
    reformulation,
    passages_cites[1]  AS passage_retenu,
    COUNT(*)           AS echanges,
    MIN(jour)          AS premier_jour,
    MAX(jour)          AS dernier_jour
FROM staging.journal_assistant
WHERE source = 'usage'
  AND origine = 'suggestion'
  AND reformulation IS NOT NULL
  AND NOT refus
  AND cardinality(passages_cites) > 0
GROUP BY reformulation, passages_cites[1];

-- Combien l'assistant doit encore deviner : la part des échanges où le client a dû
-- passer par une suggestion plutôt que d'être servi du premier coup. C'est l'indicateur
-- qui doit baisser à mesure que la base documentaire s'enrichit.
CREATE OR REPLACE VIEW staging.v_part_suggestions AS
SELECT
    source,
    jour,
    COUNT(*)                                            AS echanges,
    COUNT(*) FILTER (WHERE origine = 'suggestion')      AS via_suggestion,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE origine = 'suggestion') / NULLIF(COUNT(*), 0),
        2
    )                                                   AS part_suggestion_pourcent
FROM staging.journal_assistant
GROUP BY source, jour;

COMMENT ON COLUMN staging.journal_assistant.origine IS
    'D ou vient la question : saisie, exemple ou suggestion cliquee.';
COMMENT ON COLUMN staging.journal_assistant.reformulation IS
    'Ce que le client avait tape avant de cliquer une suggestion (masque). Null sinon.';
COMMENT ON VIEW staging.v_reformulations IS
    'Paires (formulation du client, passage retenu) a relire avant enrichissement de la FAQ.';
COMMENT ON VIEW staging.v_part_suggestions IS
    'Part des echanges servis via une suggestion plutot que directement, par jour.';
