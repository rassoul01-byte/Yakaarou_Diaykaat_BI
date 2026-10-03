# Contrat — Table de correspondance des produits

**Projet :** DataFlow360  
**Sprint :** Sprint 3  
**Fonctionnalité :** F1.9 — Table de correspondance des produits  
**Responsable :** Mouhameth DIOP  
**Relectrice :** Aissata DIALLO  
**Module :** `src/integration/correspondance.py`

## 1. Objectif

Construire une table de correspondance entre les produits vendus dans la boutique Olist et les fiches produits du catalogue Rakuten.

Les deux jeux de données ne partagent pas d'identifiant produit commun. La correspondance repose donc sur l'affinité de catégorie, puis sur une affectation déterministe d'une fiche du catalogue à chaque produit vendu.

Aucun produit vendu ne doit être supprimé à cause d'une absence de correspondance.

> **Portée de ce rattachement.** Faute d'identifiant commun, la fiche affectée à
> un produit vendu est choisie **arbitrairement à l'intérieur d'une catégorie
> compatible**. Le lien entre un produit précis et une fiche précise n'a donc
> aucune valeur métier : il permet d'illustrer la chaîne d'enrichissement du
> catalogue, et rien de plus. **Seule la correspondance de catégorie est
> significative**, et aucun constat ne sera tiré du couple produit-fiche
> lui-même. Cette limite est reprise dans `docs/dictionnaire_indicateurs.md`.

## 2. Résultat attendu

La table produite contient **une ligne par produit vendu**.

Le périmètre attendu est de **32 951 produits Olist**.

Les produits qui ne disposent d'aucune catégorie compatible sont rattachés à la catégorie `inconnu`. Les **610 produits Olist sans catégorie** font notamment partie de ce cas et doivent être conservés.

## 3. Structure de la table

| Champ | Type logique | Contenu |
|---|---|---|
| `id_produit` | texte | Identifiant du produit vendu tel qu'il figure dans la boutique |
| `id_fiche` | texte / vide | Identifiant de la fiche du catalogue affectée ; vide si le produit n'est rattaché à aucune |
| `categorie_boutique` | texte | Catégorie du produit vendu, après normalisation |
| `categorie_catalogue` | texte | Code de catégorie du catalogue mis en relation, ou `inconnu` |
| `rattache` | booléen | `true` si le produit est rattaché à une fiche, sinon `false` |

## 4. Principe de construction

La construction se fait en deux étapes.

### 4.1. Étape 1 — Correspondance des catégories

Les catégories Olist normalisées sont mises en relation avec les **27 catégories du catalogue Rakuten**.

Le catalogue Rakuten fournit des codes de catégorie. Un libellé lisible est associé à chaque code à partir d'un échantillon de désignations du catalogue.

Le mapping des catégories est conservé dans un fichier versionné et relu par l'équipe.

> **Implémentation retenue :** le mapping sera stocké dans `docs/mappings/olist_rakuten_categories.csv` afin que la règle soit versionnée séparément du code Python.

Règle de décision :

1. une catégorie Olist présentant une catégorie Rakuten compatible est associée à celle-ci ;
2. lorsqu'aucune catégorie Rakuten compatible n'est défendable, la valeur `categorie_catalogue` est `inconnu` ;
3. `inconnu` n'est pas une catégorie fourre-tout : il est utilisé lorsqu'il n'existe réellement aucune catégorie catalogue compatible, ou lorsqu'aucune catégorie Olist n'est disponible.

### 4.2. Étape 2 — Affectation d'une fiche

Pour chaque produit vendu dont la catégorie possède une correspondance, une fiche du catalogue Rakuten appartenant à cette catégorie est choisie.

L'affectation doit être **déterministe** :

- les produits sont traités dans un ordre déterminé par leur identifiant ;
- la sélection utilise une graine fixe ;
- deux exécutions sur les mêmes données doivent produire exactement la même table.

L'affectation ne repose pas sur une similarité textuelle entre le nom du produit Olist et la désignation Rakuten.

## 5. Conservation des données

Aucun produit vendu n'est supprimé par la correspondance.

Un produit peut donc produire :

- une ligne rattachée avec `rattache = true` et une `id_fiche` renseignée ;
- une ligne non rattachée avec `rattache = false`, `id_fiche` vide et `categorie_catalogue = inconnu`.

Toute fiche référencée dans `id_fiche` doit exister dans le catalogue Rakuten nettoyé.

## 6. Contrôles et erreurs

La commande doit vérifier que toutes les catégories du catalogue Rakuten attendues par le mapping sont présentes.

Si une catégorie du catalogue est absente de la table de correspondance, la commande :

1. signale l'anomalie ;
2. ne produit pas une correspondance partielle silencieuse ;
3. se termine avec le code de sortie `1`.

Le **taux de rattachement par catégorie** et le nombre de produits `inconnu` sont calculés à chaque construction. Sa définition complète figure dans `docs/dictionnaire_indicateurs.md`.

Ces informations sont affichées en ligne de commande et enregistrées dans `staging.execution_log`.

## 7. Commande de référence

```bash
docker compose exec app python -m integration.correspondance
```

La commande doit être exécutable depuis l'environnement conteneurisé du projet et retourner un code de sortie cohérent avec le résultat du traitement.

## 8. Tests attendus

Les tests doivent couvrir au minimum les cas suivants :

- produit avec catégorie compatible et fiche affectée ;
- produit sans catégorie ;
- catégorie absente du mapping ;
- vérification de l'existence de la fiche affectée ;
- déterminisme : deux lancements produisent exactement la même correspondance ;
- conservation du nombre total de produits vendus.

## 9. Critères de réussite F1.9

Le livrable est considéré comme terminé lorsque :

- la table contient **32 951 lignes**, une par produit vendu ;
- aucun produit n'est perdu ;
- les produits sans catégorie compatible sont conservés sous `inconnu` ;
- le nombre de produits `inconnu` est cohérent avec les **610 produits sans catégorie** ;
- chaque `id_fiche` renseignée existe dans le catalogue nettoyé ;
- le taux de rattachement par catégorie est affiché et journalisé ;
- deux exécutions successives donnent la même table ;
- les tests couvrent les cas nominaux et les erreurs prévues ;
- la commande se termine avec un code de sortie explicite.

## 10. Hors périmètre

Ce livrable ne comprend pas :

- le chargement de la table de correspondance dans l'entrepôt ;
- le modèle en étoile ;
- les indicateurs de ventes ;
- le tableau de bord ;
- un rapprochement par similarité de texte.

Le chargement dans l'entrepôt relève du livrable F1.10.

## 11. Dépendances

La table de correspondance dépend de :

- `staging.olist_products` après transformation et normalisation des catégories ;
- `staging.rakuten_produits` après nettoyage du catalogue ;
- du mapping versionné des catégories Olist vers Rakuten.

Le livrable F1.10 utilisera ensuite cette table pour alimenter la dimension produit de l'entrepôt.