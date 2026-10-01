# Transformation — F1.7, F1.8 (Sprint 2)

**Responsable : Aissata DIALLO · Relectrice : Ndeye Penda**

Normalisation, décodage du balisage, détection de langue et déduplication,
appliquées aux lignes qui ont passé le contrôle qualité (F1.5, Seydina).

## Ce qui est fait et testé sans base de données (44 tests)

- `balisage.py` — décodage des entités HTML et suppression des balises
  (`id&eacute;es` → `idées`).
- `normalisation.py` — dates en ISO 8601, montants à deux décimales
  (`Decimal`, jamais `float`), libellés en minuscules sans accents.
- `langue.py` — détection de langue (`langdetect`), graine fixée à 0 pour
  que deux exécutions donnent toujours le même résultat.
- `deduplication.py` — déduplication avec comptage, stricte ou sur clé métier.

```bash
PYTHONPATH=src python3 -m pytest tests/transformation
```

## Ce qui est fait mais PAS testé contre un vrai PostgreSQL

`pipeline.py` et `__main__.py` branchent ces fonctions sur `staging` :

- `transformer_geolocation` — supprime les doublons stricts de
  `staging.olist_geolocation` (défaut mesuré : 261 831 lignes sur 1 000 163).
  Suppression en SQL pur (`DELETE ... WHERE ctid NOT IN (SELECT MIN(ctid) ...
  GROUP BY ...)`), pas en pandas : la table n'a pas de clé primaire et fait
  un million de lignes, inutile de tout charger en mémoire pour ça.
- `transformer_categories` — écrit `staging.olist_products.product_category_name_norm`
  (nouvelle colonne, migration `sql/006_transformation.sql`), la clé de
  rapprochement que le Sprint 3 utilisera. La colonne d'origine n'est jamais
  modifiée.
- `transformer_rakuten` — décode `designation` et `description`, écrit
  `staging.rakuten_produits.langue` (nouvelle colonne, même migration).
  Les 2 651 doublons de désignation sur des produits différents
  sont **comptées et signalées dans le message, jamais supprimées** — c'est
  ce que dit le dossier de conception (section 3.3) : les identifiants
  produits sont uniques, seul le libellé se répète.

Je n'ai pas de PostgreSQL ici pour vérifier ces trois fonctions en
conditions réelles. Elles sont testées avec de faux curseur/connexion
(`tests/transformation/test_pipeline.py`), sur le même modèle que
`tests/quality/test_quarantaine.py` de Mouhameth — ces tests vérifient que
la bonne requête part avec les bons paramètres, pas que PostgreSQL
l'exécute correctement.

**Un bug réel a été trouvé et corrigé grâce à ces tests avec de vrais
DataFrames** (pas de purs mocks) : pandas 3 représente une valeur NULL lue
depuis PostgreSQL comme `NaN` (un flottant), pas comme `None`. Sans
correction, `psycopg2` aurait tenté d'écrire `NaN` dans une colonne `TEXT`
— une vraie erreur PostgreSQL au premier passage sur une description vide.
La correction (`astype(object).where(pd.notna(...), None)`) est commentée
directement dans `pipeline.py`, aux deux endroits concernés.

## À faire avant la démonstration

1. `PYTHONPATH=src python3 scripts/appliquer_sql.py` pour appliquer la
   migration 006 (nouvelles colonnes).
2. Une fois le moteur de Seydina (F1.5) disponible et `staging` peuplée :
   ```bash
   docker compose exec app python -m transformation --source olist
   docker compose exec app python -m transformation --source rakuten
   ```
3. Vérifier concrètement :
   - `SELECT COUNT(*) FROM staging.olist_geolocation;` avant/après — l'écart
     doit être proche de 261 831 au premier passage, 0 au second.
   - `SELECT langue, COUNT(*) FROM staging.rakuten_produits GROUP BY langue;`
     — aucune ligne à NULL, une proportion de `fr` proche de 62 %.
   - Une fiche connue pour contenir `id&eacute;es` ou une balise : vérifier
     qu'elle ressort décodée.
4. **Doublons stricts de géolocalisation — constaté le 30/09/2026** : le
   contrôle qualité (OLIST_GEOLOCALISATION_01, gravité « silencieuse ») les
   retire avant `staging` et compte les 261 831 lignes dans son journal
   (`message`, champ `lignes_supprimees`). `transformer_geolocation` trouve
   donc 0 doublon : ce n'est pas un bug, c'est une sécurité sans risque à
   relancer, et les lignes ne sont comptées qu'une fois.

Vérifié contre un vrai PostgreSQL 16 le 30/09/2026 (chaîne complète sur
l'ingestion Olist réelle) : deux corrections ont suivi — la suppression des
doublons de géolocalisation (`NOT IN` sur `ctid`, plus de dix minutes,
remplacé par `ROW_NUMBER()`) et le compte des lignes modifiées, qui ne
gardait que la dernière page d'`execute_values`.
5. Ajouter `langdetect` à `requirements.txt` (pas encore fait dans ce paquet,
   à faire dans la PR).

## Hors périmètre (rappel du sprint)

Aucun rapprochement Olist/Rakuten (Sprint 3), aucun chargement dans
l'entrepôt.
