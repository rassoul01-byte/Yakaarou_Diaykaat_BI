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
- Matrice de confusion.
- **L'exactitude n'est jamais calculée** : « il ne reviendra pas » pour tout le
  monde donnerait plus de 95 % et serait inutile.
- Juges : deux règles en une ligne — « tous négatifs » et « deux commandes ou
  plus ». Le modèle doit les battre **au F1** : comparer le seul rappel
  déclarerait gagnante la règle qui répond « revient » à tout le monde.
- Si le modèle ne les bat pas, le résultat se publie tel quel.

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

## Limites (à compléter avec les chiffres réels après branchement)

- Le modèle est une régression logistique : il capte des tendances, pas des
  interactions fines entre variables.
- Il décrit un comportement passé de 2017 ; il ne dit rien d'un client dont
  l'historique est très court ou absent de la période.
- Une probabilité n'est pas une certitude : le segment à retenir choisit un
  seuil, et ce seuil se paie en faux positifs.
- Une corrélation n'est pas une cause : une variable influente n'explique pas
  *pourquoi* un client revient, et ne justifie aucune action individuelle.
- Les résultats mesurés (rappel, précision, F1 face aux règles naïves) :
  _à reporter ici après l'exécution sur les vraies variables_.
