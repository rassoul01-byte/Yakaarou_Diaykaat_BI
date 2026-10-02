# Dictionnaire des indicateurs

**GROUPE 2 · DataFlow360**
**Responsable : Ndeye Penda SARR**

Ce document est la **référence unique** de tout chiffre présenté par la
plateforme. Un indicateur qui n'y figure pas ne doit apparaître ni dans un
rapport, ni dans un tableau de bord, ni dans une soutenance.

Chaque entrée précise six choses : ce que l'indicateur mesure, comment il se
calcule, à quel niveau de détail, d'où viennent ses données, son seuil d'alerte
s'il en a un, et ce qu'il ne dit pas. **Cette dernière ligne est la plus
importante** : c'est elle qui évite qu'un chiffre soit lu pour ce qu'il n'est pas.

---

## Indicateurs de qualité — Sprint 2

### Taux de rejet

| | |
|---|---|
| **Définition** | Part des lignes écartées par le contrôle de qualité, parmi celles qui ont été lues |
| **Formule** | `lignes rejetées ÷ lignes lues × 100` |
| **Granularité** | Par source et par exécution. Se décline par règle |
| **Source des données** | `staging.execution_log` pour les volumes, `quarantaine.rejets` pour les motifs |
| **Calcul** | `quarantaine.v_taux_rejet_par_source` |
| **Seuil d'alerte** | **5 %**. Au-delà, le chargement du jour est interrompu et examiné |
| **Consultation** | `python -m quality.rapport --seuil 5` |

**Ce que comptent les volumes.** Pour le pipeline `qualite`, une ligne du
journal par exécution de `quality.controle` : `lignes_lues` = tous les
enregistrements des fichiers de l'ingestion contrôlée, `lignes_rejetees` = les
lignes envoyées en quarantaine par les règles bloquantes, `lignes_ecrites` =
les lignes chargées en staging. Les lignes supprimées silencieusement (doublons
stricts) ne sont ni rejetées ni écrites : leur compte est dans la colonne
`message` (JSON, détail par règle). Relancer une ingestion ajoute une exécution,
qui entre dans le taux cumulé.

**Ce qu'il ne dit pas.** Un taux de rejet élevé ne signifie pas que les données
se sont dégradées : il signale aussi bien une **règle trop stricte** qu'une
source qui a changé de format. C'est un signal à examiner, jamais un verdict.

**Cas particulier — aucune ligne lue.** Le taux vaut alors *indéfini*, et non
zéro. Afficher 0 % laisserait croire que tout va bien, alors que rien n'a été
contrôlé. Le rapport affiche `—` et un avertissement.

**Règle du seuil.** Le dossier dit « au-delà de 5 % » : une source exactement à
5 % n'est pas en dépassement.

---

### Taux de rejet par règle

| | |
|---|---|
| **Définition** | Nombre de lignes rejetées par chaque règle du catalogue, et part que cette règle représente dans les rejets de sa source |
| **Formule** | `rejets de la règle ÷ rejets de la source × 100` |
| **Granularité** | Par source, par règle et par gravité |
| **Source des données** | `quarantaine.rejets` |
| **Calcul** | `quarantaine.v_taux_rejet_par_regle` |
| **Seuil d'alerte** | Aucun. C'est un outil de diagnostic |

**À quoi il sert.** Le taux par source dit *qu'il y a un problème* ; celui-ci
dit *lequel*. Une règle qui concentre à elle seule l'essentiel des rejets est
presque toujours une règle mal écrite.

---

### Répartition des rejets par gravité

| | |
|---|---|
| **Définition** | Nombre de lignes rejetées selon la gravité de la règle violée : bloquante ou non bloquante |
| **Granularité** | Par source et par gravité |
| **Source des données** | `quarantaine.rejets` |
| **Calcul** | `quarantaine.v_rejets_par_gravite` |

**Ce qu'il ne dit pas.** Les lignes supprimées **silencieusement** — les
doublons stricts — n'apparaissent pas ici : elles ne sont pas rejetées mais
écartées, et leur compte figure dans le journal des exécutions.

---

### Lignes marquées et lignes supprimées

| | |
|---|---|
| **Définition** | Lignes **marquées** : conservées mais signalées par une règle non bloquante. Lignes **supprimées** : retirées du flux par une règle silencieuse (doublons stricts). Dans les deux cas, la ligne n'est pas rejetée |
| **Granularité** | Par source et par règle, pour la dernière exécution |
| **Source des données** | `staging.execution_log`, colonne `message` (JSON, clé `controles` : `anomalies` pour les marquées, `lignes_supprimees` pour les supprimées) |
| **Affichage** | `python -m quality.rapport` |
| **Seuil d'alerte** | Aucun |

**Ce qu'il ne dit pas.** Ces lignes ne comptent **pas** dans le taux de rejet : une
commande sans article est conservée, un doublon de géolocalisation est supprimé
sans être rejeté. Un taux de rejet de 0,07 % avec 261 831 lignes supprimées n'est pas
une source « presque parfaite » : les deux chiffres se lisent ensemble.

---

### Évolution du taux de rejet

| | |
|---|---|
| **Définition** | Écart, en points de pourcentage, entre le taux de rejet d'une exécution et celui de l'exécution précédente de la même source |
| **Formule** | `taux(exécution n) − taux(exécution n−1)` |
| **Granularité** | Par source et par exécution |
| **Source des données** | `quarantaine.v_taux_rejet_par_execution` |
| **Affichage** | `python -m quality.rapport` (option `--historique N`, 5 par défaut) |
| **Seuil d'alerte** | Aucun |

**Ce qu'il ne dit pas.** Une variation nulle entre deux exécutions de la **même
ingestion** est normale : rejouer un contrôle donne le même taux. Une hausse
brutale signale plus souvent une source qui a changé qu'une donnée devenue mauvaise.
Sans taux (aucune ligne lue), il n'y a pas de variation.

---

### Taux de rejet cumulé

| | |
|---|---|
| **Définition** | Taux de rejet sur l'ensemble des exécutions d'une source, et non sur la dernière seulement |
| **Formule** | `somme des lignes rejetées ÷ somme des lignes lues × 100` |
| **Granularité** | Par source |
| **Calcul** | `quarantaine.v_taux_rejet_par_source`, colonne `taux_rejet_cumule_pourcent` |

**À quoi il sert.** Comparé au taux de la dernière exécution, il montre si la
qualité **se dégrade ou s'améliore**. Un taux du jour très au-dessus du cumulé
signale un incident récent plutôt qu'un défaut de fond.

---

## Indicateurs de ventes — Sprint 3

> ⚠️ **Trois décisions de périmètre, à confirmer par le Product Owner.**
> Elles sont écrites ici et appliquées dans une seule vue SQL,
> `dwh.v_ventes_retenues` : changer d'avis ne touche qu'un endroit.
>
> 1. **Les frais de port sont exclus** du chiffre d'affaires. Ils dépendent du
>    poids et de la distance, pas de ce qui a été vendu : les inclure ferait
>    varier le chiffre d'affaires sans qu'aucune vente ne change.
> 2. **Les commandes annulées et indisponibles sont exclues.** Une vente qui
>    n'a pas eu lieu n'est pas une vente.
> 3. **Une commande sans ligne d'article pèse zéro** et n'entre pas au
>    dénominateur du panier moyen — les 775 commandes concernées fausseraient
>    la moyenne à la baisse.

### Chiffre d'affaires

| | |
|---|---|
| **Définition** | Somme des prix des articles vendus, sur le périmètre retenu ci-dessus |
| **Formule** | `somme(prix des lignes d'article)` — hors frais de port |
| **Granularité** | Jour, semaine, mois, et total |
| **Source des données** | `dwh.fait_ligne_commande`, filtrée par `dwh.v_ventes_retenues` |
| **Calcul** | `dwh.v_ventes_par_jour`, `_par_semaine`, `_par_mois`, `v_ventes_totales` |
| **Seuil d'alerte** | Aucun ici — l'alerte sur chute de ventes arrive au Sprint 4 |

**Ce qu'il ne dit pas.** Ce n'est **pas** le montant encaissé : `montant_paye`
de `fait_commande` inclut les frais de port et les commandes annulées. Les deux
chiffres sont justes et différents — c'est pourquoi ils portent deux noms.

### Nombre de commandes

| | |
|---|---|
| **Définition** | Commandes distinctes ayant au moins une ligne d'article retenue |
| **Formule** | `nombre de order_id distincts` sur le périmètre retenu |
| **Granularité** | Jour, semaine, mois, et total |
| **Calcul** | Mêmes vues que le chiffre d'affaires |

**Ce qu'il ne dit pas.** Une commande annulée existe dans l'entrepôt mais ne
compte pas ici : le total ne correspond donc pas au nombre de lignes de
`fait_commande`.

### Panier moyen

| | |
|---|---|
| **Définition** | Chiffre d'affaires rapporté au nombre de commandes |
| **Formule** | `chiffre d'affaires ÷ nombre de commandes` |
| **Granularité** | Jour, semaine, mois, et total |
| **Calcul** | Mêmes vues |

**Ce qu'il ne dit pas.** Ce n'est pas ce qu'un client dépense : une personne
peut avoir passé plusieurs commandes. La dépense par client viendra avec
l'historique d'achat, au Sprint 5.

### Produits et catégories les plus vendus

| | |
|---|---|
| **Définition** | Classement par chiffre d'affaires, avec le nombre d'articles et de commandes |
| **Granularité** | Produit, et catégorie |
| **Calcul** | `dwh.v_produits_les_plus_vendus`, `dwh.v_categories_les_plus_vendues` |

**Ce qu'il ne dit pas.** Les produits sans catégorie apparaissent sous
`inconnu`, **et c'est volontaire** : un classement qui cache ce qu'il ignore
donne une fausse impression de complétude. La colonne « rattaché » rappelle par
ailleurs que le lien vers une fiche du catalogue est arbitraire dans sa
catégorie — voir le taux de rattachement ci-dessous.

---

## Indicateurs d'intégration — Sprint 3

### Taux de rattachement par catégorie

| | |
|---|---|
| **Définition** | Part des produits vendus dont la catégorie a trouvé une catégorie compatible dans le catalogue |
| **Formule** | `produits rattachés ÷ produits vendus × 100` |
| **Granularité** | Global, et par catégorie de la boutique |
| **Source des données** | Table de correspondance — voir `docs/contrats/correspondance.md` |
| **Seuil d'alerte** | Aucun |

**Ce qu'il ne dit pas.** Il ne mesure **pas** la qualité d'un rapprochement
produit par produit. Les deux jeux de données ne partagent aucun identifiant :
la fiche affectée à un produit est choisie arbitrairement à l'intérieur de sa
catégorie. Un taux de 100 % signifierait que toutes les catégories ont trouvé
une correspondance, **jamais** que les bons produits ont été reconnus.

---

## Comment ajouter un indicateur

1. L'écrire **ici d'abord**, avec les six rubriques, avant d'écrire la moindre requête.
2. Le calcul va dans une **vue SQL versionnée** dans `sql/`, jamais dans le code : le chiffre reste ainsi recalculé à la demande, et jamais périmé.
3. La vue est nommée `v_<indicateur>` et vit dans le schéma de son domaine.
4. Toute modification de définition passe par une demande de fusion sur ce document **et** sur la vue.

⚠️ **Deux indicateurs qui portent le même nom mais se calculent différemment
sont la première cause de désaccord en réunion.** C'est précisément ce que ce
document existe pour empêcher.

---

## À venir

| Sprint | Indicateurs |
|---|---|
| 3 | Chiffre d'affaires, panier moyen, délai de livraison, note moyenne, taux d'appariement du catalogue |
| 4 | Compteurs du jour, taux de conversion, qualité de la recherche |
| 5 | Probabilité de nouvel achat, part des réponses de l'assistant appuyées sur une source |

Les indicateurs des Sprints 4 et 5 portant sur la navigation reposeront sur un
**trafic simulé** : la mention devra apparaître partout où ils s'affichent.
