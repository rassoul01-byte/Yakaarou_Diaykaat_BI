# Protocole — modèle de ré-achat

**Fonctionnalités :** F3.2 à F3.6
**Responsable :** Ndeye Penda SARR · **Relecteur :** Bachir DEME
**Module :** `src/prediction/`

Ce document fixe **ce qu'on prédit, sur quelles données, et comment on le mesure** — avant d'écrire une ligne de code. Il est publié en premier parce que les variables du livrable 1 en dépendent : sans date de référence connue, on ne sait pas quoi calculer.

---

## 1. Ce qu'on prédit

> **Ce client passera-t-il une nouvelle commande dans les 180 jours qui suivent la date de référence ?**

Une réponse par oui ou par non, et un score entre 0 et 1 qui dit à quel point le modèle en est sûr.

**Pourquoi 180 jours.** L'historique Olist couvre septembre 2016 à octobre 2018, soit vingt-cinq mois. Une fenêtre de six mois laisse assez de passé pour décrire un client et assez d'avenir pour observer s'il revient. Une fenêtre plus courte rendrait la classe positive encore plus rare ; une fenêtre plus longue amputerait la période d'entraînement.

**Pourquoi « nouvelle commande » et non « achat ».** Le ré-achat se lit dans l'entrepôt, sur des commandes réelles. Les événements de navigation sont du trafic simulé : les utiliser ici fabriquerait un modèle entraîné sur de l'invention.

---

## 2. Les deux dates qui structurent tout

| | |
|---|---|
| **Date de référence** | **30 septembre 2017** |
| Période d'observation | tout ce qui précède cette date |
| Période de vérité | les 180 jours qui suivent, jusqu'au 29 mars 2018 |

**Un client est « positif »** s'il a passé au moins une commande entre le 1er octobre 2017 et le 29 mars 2018.

**Il entre dans le jeu** s'il a passé au moins une commande **avant** la date de référence. Un client dont la première commande est postérieure n'a pas d'historique : on ne peut rien prédire à son sujet.

⚠️ **Toutes les variables se calculent sur la période d'observation uniquement.** C'est la règle qui compte le plus, et la section suivante explique pourquoi.

---

## 3. Le découpage est temporel, jamais aléatoire

**La règle :** on entraîne sur l'avant, on évalue sur l'après.

| | Période d'observation | Période de vérité |
|---|---|---|
| **Entraînement** | avant le 31 mars 2017 | 1ᵉʳ avril → 27 septembre 2017 |
| **Évaluation** | avant le 30 septembre 2017 | 1ᵉʳ octobre 2017 → 29 mars 2018 |

**Pourquoi c'est la décision la plus importante du livrable.** Un découpage aléatoire mélangerait des clients observés en 2018 avec des clients observés en 2016. Le modèle apprendrait sur des périodes qu'il est censé prédire — il verrait l'avenir. Ses résultats seraient **excellents et entièrement faux**, et rien dans les chiffres ne le signalerait.

C'est l'erreur classique sur données temporelles, et elle invalide tout le livrable sans prévenir.

**Conséquence pratique :** aucune fonction de découpage aléatoire n'est utilisée. Le jeu d'évaluation est construit par la date, pas tiré au sort.

---

## 4. Les variables attendues — ce que Bachir calcule

Une ligne par **`customer_unique_id`** — l'identifiant de personne, jamais `customer_id` qui change à chaque commande.

| Variable | Calcul, sur la période d'observation |
|---|---|
| `commandes` | nombre de commandes retenues |
| `montant_total` | somme des prix des lignes d'article |
| `montant_moyen` | montant total ÷ commandes |
| `premier_achat`, `dernier_achat` | dates extrêmes |
| `recence_jours` | jours entre le dernier achat et la date de référence |
| `anciennete_jours` | jours entre le premier achat et la date de référence |
| `note_moyenne` | moyenne des notes données, `null` si le client n'en a donné aucune |
| `avis_donnes` | nombre d'avis |
| `delai_livraison_moyen` | moyenne des jours entre achat et livraison |
| `livraisons_en_retard` | commandes livrées après la date estimée |
| `categories_distinctes` | catégories différentes achetées |
| `etat` | état brésilien du client, pour la localisation |

**Le périmètre des commandes est celui du dictionnaire** : commandes annulées et indisponibles exclues, comme pour le chiffre d'affaires. Deux définitions du mot « commande » dans le même projet seraient la garantie d'un désaccord.

⚠️ **Aucune variable ne doit contenir d'information postérieure à la date de référence.** Un `dernier_achat` qui tomberait après le 30 septembre 2017 révélerait la réponse au modèle. **Un test doit le vérifier**, pas une relecture.

---

## 5. Le déséquilibre, et comment on le traite

La grande majorité des clients Olist n'ont commandé qu'une fois : la classe positive — les clients qui reviennent — est **très minoritaire**.

**Deux conséquences.**

**L'exactitude est interdite comme mesure.** Un modèle qui répondrait « il ne reviendra pas » à tout le monde afficherait plus de 95 % d'exactitude et serait rigoureusement inutile. Ce chiffre ne doit apparaître nulle part — ni dans le rapport, ni dans la soutenance.

**On rééquilibre par pondération des classes.** La classe rare pèse davantage à l'entraînement, ce qui force le modèle à s'y intéresser. On ne duplique pas d'exemples et on n'en supprime pas : la pondération ne fabrique aucune donnée.

---

## 6. Ce qu'on mesure

| Mesure | Ce qu'elle dit |
|---|---|
| **Rappel** sur la classe positive | Part des clients qui sont revenus que le modèle avait identifiés |
| **Précision** sur la classe positive | Part des clients annoncés comme revenant qui sont réellement revenus |
| **Matrice de confusion** | Les quatre nombres, en clair |
| **Comparaison à une règle naïve** | « tous négatifs », et « positif si le client a déjà commandé deux fois » |

**La règle naïve est le juge.** Un modèle qui ne fait pas mieux qu'une règle en une ligne ne sert à rien — et c'est un résultat qu'on publie tel quel, pas qu'on cache.

**Le compromis rappel/précision est un choix métier.** Viser large retient plus de clients à risque mais sollicite des gens qui seraient revenus seuls ; viser étroit rate des départs. Le seuil retenu est écrit au dictionnaire avec ce qu'il coûte en faux positifs.

---

## 7. Ce qui est livré avec le modèle

- la matrice de confusion, le rappel et la précision sur la classe rare ;
- les **variables les plus influentes**, pour que le modèle soit explicable ;
- la comparaison aux deux règles naïves ;
- **une page sur les limites** : ce que le modèle ne sait pas, et ce qu'on ne doit pas en conclure ;
- une commande qui expose les scores.

**Reproductibilité** : graine fixée, deux entraînements successifs donnent exactement les mêmes chiffres.

---

## 8. Ce que ce modèle ne pourra pas dire

**Il ne dit pas pourquoi un client part.** Il repère une ressemblance avec des clients partis auparavant, ce qui n'est pas une cause.

**Il est entraîné sur un marchand brésilien en 2016-2018.** Les comportements d'achat y sont ceux de ce marché et de cette époque.

**Une commande unique est la norme dans ce jeu**, pas une anomalie : la plateforme Olist regroupe de nombreux vendeurs et beaucoup d'acheteurs n'y passent qu'une fois. Un rappel faible n'est pas nécessairement un mauvais modèle — c'est peut-être un comportement peu prévisible.

Ces trois limites vont au dossier de conception. **Elles seront la première question du jury**, bien avant le choix de l'algorithme.
