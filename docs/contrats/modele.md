# Contrat du modèle de ré-achat (F3.2 à F3.6)

Protocole publié par Ndeye Penda (livrable 2, Sprint 5). Il est lu par Bachir
(variables) et Seydina. Toute modification passe par une PR qui touche ce fichier.

## Ce qu'on prédit

> « Ce client passera-t-il une nouvelle commande dans les 180 jours qui suivent
> la date de référence ? »

Une ligne par client (`customer_unique_id`, jamais un identifiant de commande)
et par date de référence. La réponse observée est `a_rachete` (1 = est revenu).

## Découpage temporel — jamais aléatoire

| Rôle | Date de référence | Réponse observée sur |
|---|---|---|
| Entraînement | 2017-03-31 | les 180 jours suivants |
| Évaluation | 2017-09-30 | les 180 jours suivants |

L'entraînement ne voit jamais la période d'évaluation. Un découpage aléatoire
mélangerait des périodes : le modèle apprendrait ce qu'il doit prédire, et ses
résultats seraient excellents et faux. Aucune fonction de découpage aléatoire
n'existe dans le code, et un test le vérifie.

## Contrat de la vue `dwh.v_historique_client` (livrable 1, Bachir)

Colonnes attendues, dans cet ordre de lecture :

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
