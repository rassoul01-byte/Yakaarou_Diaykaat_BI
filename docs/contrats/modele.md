# Contrat du modèle de ré-achat (F3.2 à F3.6)

Protocole publié par Ndeye Penda (livrable 2, Sprint 5). Il est lu par Bachir
(variables) et Seydina. Toute modification passe par une PR qui touche ce fichier.

## Ce qu'on prédit

> « Ce client passera-t-il une nouvelle commande dans les 180 jours qui suivent
> la date de référence ? »

Une ligne par client (`customer_unique_id`, jamais un identifiant de commande)
et par date de référence. La réponse observée est `a_rachete` (1 = est revenu).

## Découpage temporel — jamais aléatoire

**Le protocole qui porte la décision** (`python -m prediction`, une fenêtre) :

| Rôle | Date de référence | Réponse observée sur |
|---|---|---|
| Entraînement | 2017-03-31 | `(2017-03-31 ; 2017-09-27]` |
| Évaluation | 2017-09-30 | `(2017-09-30 ; 2018-03-29]` |

Les deux fenêtres de réponse ne se recouvrent pas : trois jours les séparent.
C'est ce protocole, et lui seul, qui fonde le choix de retenir la règle plutôt
que le modèle.

**Le protocole exploratoire** (`prediction.evaluer_multi`,
`prediction.comparer_algorithmes`) entraîne au 2017-03-31 et évalue sur les
autres dates de `dwh.v_dates_reference`, élargie à cinq fenêtres par `sql/021`,
puis agrège par sommes avec un intervalle de Wilson unique
(`prediction.statistiques.pooler`).

⚠️ **Deux de ces fenêtres sont contaminées, et leurs résultats ne doivent pas
être présentés comme une mesure.** Les populations sont strictement emboîtées —
tout client de l'entraînement se retrouve dans chaque fenêtre postérieure — et
les fenêtres de réponse se recouvrent :

| Date de référence | Fenêtre de réponse | Recouvrement avec l'entraînement |
|---|---|---|
| 2016-12-31 | `(2016-12-31 ; 2017-06-29]` | 90 jours, **et antérieure à l'entraînement** |
| 2017-03-31 *(entraînement)* | `(2017-03-31 ; 2017-09-27]` | — |
| 2017-06-30 | `(2017-06-30 ; 2017-12-27]` | **89 jours** |
| 2017-09-30 | `(2017-09-30 ; 2018-03-29]` | aucun |
| 2017-12-31 | `(2017-12-31 ; 2018-06-29]` | aucun |

Pour la fenêtre du 2017-06-30, un client sans achat entre mars et juin a une
étiquette d'entraînement égale à son étiquette d'évaluation, avec des variables
identiques à un décalage constant de 91 jours près. Un modèle assez souple pour
retenir un client — une forêt sans profondeur bornée, sur 75 positifs — peut
l'exploiter. L'intervalle poolé est par ailleurs **trop étroit** : les fenêtres
partagent leurs clients, donc l'effectif effectif est bien inférieur à la somme
des ciblés.

**L'entraînement ne voit jamais la réponse de la période d'évaluation** dans le
protocole mono-fenêtre. Aucune fonction de découpage aléatoire n'existe dans le
code, et un test le vérifie.

## Contrat de la vue `dwh.v_historique_client` (livrable 1, Bachir)

La vue publie **19 colonnes** depuis `sql/022_features_enrichies.sql`. Le
modèle n'en lit que **13** : la clé, la date de référence, les 11 variables
ci-dessous et la réponse (`prediction/donnees.py`, constante `VARIABLES`).

⚠️ **Les six variables ajoutées par `sql/022`** — `ecart_type_intervalles`,
`ratio_commandes_recentes`, `ecart_type_notes`, `ecart_delai_estime_reel`,
`velocite_achat`, `part_paiement_credit_card` — **ne sont lues par aucun code**.
Elles restent en base pour un usage futur ; les ajouter au modèle demande de les
inscrire dans `VARIABLES`, de refaire l'évaluation et de reprendre ce tableau.
Un essai les ayant incluses a dégradé le résultat (5,07× → 4,44× au top 250,
commit `8cf7b2e`), d'où le retour aux variables d'origine.

Colonnes lues par le modèle, dans cet ordre :

| Colonne | Définition (calculée **à la date de référence**, jamais après) |
|---|---|
| `customer_unique_id` | identifiant de la personne |
| `date_reference` | date de référence de la ligne |
| `commandes` | nombre de commandes passées jusqu'à la date |
| `montant_total`, `montant_moyen` | montants cumulés et moyens des commandes passées |
| `recence_jours` | jours entre le dernier achat et la date de référence (≥ 0) |
| `anciennete_jours` | jours entre le premier achat et la date de référence (≥ 0) |
| `note_moyenne` | note moyenne donnée (NULL si aucun avis) |
| `avis_donnes` | nombre d'avis donnés |
| `delai_livraison_moyen` | délai de livraison moyen subi, en jours |
| `livraisons_en_retard` | nombre de livraisons en retard subies |
| `categories_distinctes` | nombre de catégories achetées |
| `a_rachete` | 1 si une nouvelle commande tombe dans les 180 jours suivants, sinon 0 |

Une commande présente deux fois ne compte qu'une fois. Un client à commande
unique est décrit normalement : c'est la majorité. Le code refuse un jeu dont la
récence ou l'ancienneté est négative : c'est le signe qu'une variable connaît
l'avenir.

## Déséquilibre

La grande majorité des clients n'ont commandé qu'une fois. Les classes sont
**pondérées** (`class_weight="balanced"`) : aucun exemple n'est dupliqué ni
supprimé.

## Mesures

- Rappel, précision et F1 **sur la classe rare** (les clients qui reviennent).
  Ils sont calculés au seuil de 0,5, qui est arbitraire.
- Matrice de confusion.
- **L'exactitude n'est jamais calculée** : « il ne reviendra pas » pour tout le
  monde donnerait plus de 95 % et serait inutile.
- Juges : deux règles en une ligne — « tous négatifs » et « deux commandes ou
  plus ». Le modèle doit les battre **au F1** : comparer le seul rappel
  déclarerait gagnante la règle qui répond « revient » à tout le monde.
- **Qualité du classement, indépendante du seuil** (`prediction.classement`) :
  précision moyenne comparée au taux de base, part des retours captés dans les
  10 % de clients les mieux classés comparée au hasard (10 %), et rappel **à
  volume égal** : le modèle est limité au même nombre de clients signalés que la
  règle « deux commandes ou plus ». Sans cette dernière mesure, un modèle qui
  signale beaucoup plus de clients paraît meilleur par simple effet de volume.
- Si le modèle ne bat pas les règles, le résultat se publie tel quel.

## Reproductibilité

Graine fixée (`GRAINE = 42`) : deux entraînements donnent exactement les mêmes
chiffres.

## Commandes

```text
docker compose exec app python -m prediction                  # entraîne et évalue
docker compose exec app python -m prediction.scorer           # scores, du plus au moins à risque
docker compose exec app python -m prediction.scorer --csv scores.csv
docker compose exec app python -m prediction --fabrique       # jeu fabriqué de 200 lignes
```

`--fabrique` sert au développement : ses résultats ne veulent rien dire et
n'entrent dans aucun document.

## Résultats mesurés (exécution du 2026-10-07, vraies données)

Entraînement au 2017-03-31 : 5 233 clients, 75 qui reviennent (1,4 %).
Évaluation au 2017-09-30 : 26 190 clients, 413 qui reviennent (1,58 %).

| | Rappel | Précision | F1 | Clients signalés |
|---|---|---|---|---|
| Tous négatifs | 0 | 0 | 0 | 0 |
| Deux commandes ou plus | 0,077 | 0,045 | 0,057 | 711 |
| Modèle (seuil 0,5) | 0,324 | 0,021 | 0,039 | 6 503 |

Matrice de confusion du modèle : 134 clients revenus bien repérés, 279 manqués,
6 369 signalés à tort, 19 408 correctement écartés.

**Le modèle ne fait pas mieux que la règle « deux commandes ou plus » au F1.**
Ce résultat est publié tel quel.

Qualité du classement :

| Mesure | Valeur | Repère |
|---|---|---|
| Précision moyenne | 0,022 | taux de base 0,016 (soit 1,4 fois) |
| Retours dans les 10 % les mieux classés (2 619 clients) | 56 sur 413 (13,6 %) | hasard : 10 % |
| À volume égal (711 clients), règle | 32 retours (7,7 %) | hasard : environ 11 |
| À volume égal (711 clients), modèle | 18 retours (4,4 %) | hasard : environ 11 |

Lecture : le modèle retrouve plus de clients que la règle (134 contre 32)
uniquement parce qu'il en signale neuf fois plus. À nombre de clients signalés
égal, la règle fait mieux. Le classement du modèle contient un signal faible
(13,6 % des retours dans les 10 % du haut, pour 10 % attendus au hasard), pas
davantage.

## Limites

- **`proba_retour` n'est pas une probabilité, c'est un score de classement.**
  Le modèle est entraîné avec `class_weight="balanced"`, qui recalibre sur un
  *a priori* de 50 % au lieu du taux réel de 1,58 %. Un score de 0,6335 — le
  seuil du top 250 — ne veut donc pas dire « 63 % de chances de revenir ». Le
  score sert à ordonner, et c'est ainsi qu'il est utilisé partout : top N,
  rang, segment. Aucune mesure de calibration n'a été faite.
- **Le garde-fou `verifier_absence_de_fuite` ne peut pas se déclencher sur les
  données réelles.** Il teste que `recence_jours` et `anciennete_jours` sont
  positives ; or la vue filtre `date_achat <= date_reference`, donc elles le
  sont par construction. C'est un contrôle de cohérence d'un jeu fabriqué, pas
  une détection de fuite. Le vrai contrôle anti-fuite est
  `test_scorer.py::test_la_cible_de_la_periode_scoree_n_influence_pas_les_scores`,
  qui falsifie la réponse et vérifie que les scores ne bougent pas.
- **Le statut final d'une commande est connu après la date de référence.**
  `v_commandes_retenues` écarte les commandes annulées ou indisponibles : une
  commande passée avant la date puis annulée après en est exclue, donc l'avenir
  modifie les variables passées. Limite assumée, documentée dans `sql/018`.
- **Les hyperparamètres ont été choisis sur le jeu d'évaluation.** Quatre
  valeurs de `C` comparées, aucun jeu de validation, aucune validation croisée.
  La conclusion étant négative — aucun réglage ne bat la règle — le biais ne
  gonfle pas le résultat publié ; il interdirait en revanche de publier un
  gain obtenu de cette façon.
- **Les écarts entre algorithmes ne sont pas significatifs.** 120 comparaisons
  sur le même jeu sans correction de multiplicité, des intervalles marginaux
  là où les comparaisons sont appariées, et un classement piloté par le top
  0,5 % et le top 250 — ce dernier reposant sur 14 retours.
- **Trois des douze algorithmes comparés n'ont aucun traitement du
  déséquilibre** (`GradientBoosting`, `AdaBoost`, `Bagging`) : ni `class_weight`
  ni `sample_weight`. La comparaison mêle donc deux traitements de la classe
  rare.
- Le modèle est une régression logistique : il capte des tendances, pas des
  interactions fines entre variables.
- Il décrit un comportement passé de 2017 ; il ne dit rien d'un client dont
  l'historique est très court ou absent de la période.
- Une probabilité n'est pas une certitude : le segment à retenir choisit un
  seuil, et ce seuil se paie en faux positifs.
- Une corrélation n'est pas une cause : une variable influente n'explique pas
  *pourquoi* un client revient, et ne justifie aucune action individuelle.
- Seuls 75 clients reviennent dans la période d'entraînement : l'estimation est
  instable. Une seule date d'évaluation (413 retours) : les écarts de quelques
  points entre le modèle et la règle sont fragiles.
- Rappel, précision et F1 sont mesurés au seuil arbitraire de 0,5, avec des
  classes pondérées : ce seuil signale environ un client sur quatre.
- Les coefficients ne se lisent pas un à un. `montant_total` et `montant_moyen`
  se compensent presque exactement (l'un vaut l'autre multiplié par
  `commandes`). `recence_jours` et `anciennete_jours` sont identiques pour un
  client à commande unique : leur écart n'existe que pour ceux qui ont déjà
  racheté, et le modèle apprend en partie « a déjà racheté ».
- 98 % des clients ne reviennent pas : le haut de la liste de risque de départ
  ne départage presque personne. Le segment du livrable 5 ne doit pas s'appuyer
  sur ce risque seul : il le croise avec la valeur du client, ou bascule vers
  une règle simple documentée.

## Décision sur le segment (F3.7)

Le modèle ne battant pas la règle « deux commandes ou plus » à volume égal
(18 retours contre 32 sur 711 clients), le segment à retenir est cette règle
simple, documentée dans `docs/dictionnaire_indicateurs.md`. La décision a été
prise après lecture de l'évaluation du 2017-09-30. Le modèle reste livré comme
résultat négatif honnête.
