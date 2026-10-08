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
### Taux de rejet global

| | |
|---|---|
| **Définition** | Part des lignes rejetées sur l'ensemble des sources, dernière exécution de chacune |
| **Formule** | `somme(lignes rejetées) ÷ somme(lignes lues) × 100` |
| **Granularité** | Plateforme entière |
| **Source des données** | `quarantaine.v_taux_rejet_par_source` |
| **Calcul** | `quarantaine.v_taux_rejet_global` |
| **Seuil d'alerte** | **5 %**, comme le taux par source |

**Pourquoi il existe.** Le tableau de bord affichait la **moyenne des taux par
source** — 0,02 % avec les trois sources actuelles —, qui donne le même poids à
une source de 1,5 million de lignes et à une source de 85 000. Le taux global,
lui, se calcule sur le total des lignes : **0,062 %**. Un taux ne se moyenne
pas, il se recalcule.

**Un doublon à connaître.** `catalogue` et `rakuten` déposent le même fichier
sous deux noms : ses 84 916 lignes comptent deux fois au dénominateur. Compté
une seule fois, le taux global serait de 0,066 %. L'écart est faible ; le
chiffre affiché est celui de `quarantaine.v_taux_rejet_global`, sur les trois
sources.

**Ce qu'il ne dit pas.** Il ne remplace pas le taux par source : une source
isolée peut dépasser 5 % sans que le global bouge, parce qu'elle pèse peu. **Le
seuil d'alerte reste celui de chaque source** ; le global sert à présenter
l'état d'ensemble, jamais à décider d'un arrêt.


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
peut avoir passé plusieurs commandes. La dépense par client n'est pas un
indicateur publié ; seul l'historique d'achat (`montant_total` de
`dwh.v_historique_client`) la porte, pour le segment du Sprint 5.

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

## Indicateurs temps réel et supervision — Sprint 4

> ⚠️ **Les indicateurs de navigation reposent sur un trafic simulé.** Le
> générateur produit les événements : aucune personne réelle ne visite ce site.
> La mention doit apparaître **partout** où ces chiffres s'affichent — rapport,
> tableau de bord, soutenance. Un indicateur de navigation présenté sans cette
> précision est un chiffre faux.

### Compteurs du jour

| | |
|---|---|
| **Définition** | Sessions, pages vues, recherches, ajouts au panier et achats de la journée, mis à jour à mesure que les événements arrivent |
| **Formule** | Comptage des événements du jour, dédoublonnés sur `id_evenement` |
| **Granularité** | Journée en cours, rafraîchie à chaque lecture du bus |
| **Source des données** | Le bus d'événements, sujet `navigation.evenements` |
| **Calcul** | `staging.v_activite_par_jour` |
| **Consultation** | `python -m compteurs` |
| **Seuil d'alerte** | Aucun en propre — ils alimentent l'alerte sur chute des ventes |

**Pourquoi aucun montant.** Un événement d'achat ne porte pas de prix — ni le
contrat d'événements, ni le catalogue produits n'en contiennent. Ces compteurs
mesurent donc l'**activité**, jamais le chiffre d'affaires. Un montant temps
réel serait un chiffre inventé.

**Ce qu'ils ne disent pas.** Le chiffre d'affaires reste celui de l'entrepôt,
disponible le lendemain. Les deux ne se comparent pas : l'un compte des achats,
l'autre des euros. Ces compteurs **ne passent pas par l'entrepôt** — ce sont
deux chemins pour deux usages, l'un répondant à « que se passe-t-il
maintenant », l'autre à « qu'avons-nous vendu ».

**Un événement reçu deux fois ne compte qu'une fois** : la clé primaire sur
`id_evenement` s'en charge. Le bus garantit « au moins une fois », pas
« exactement une fois ». Et les événements rejoués circulent sur un sujet
séparé, précisément pour que les compteurs ne les additionnent pas.

---

### Taux de conversion

| | |
|---|---|
| **Définition** | Part des sessions de navigation qui se sont terminées par un achat |
| **Formule** | `sessions avec au moins un événement « achat » ÷ sessions totales × 100` |
| **Granularité** | Journée en cours, et par jour |
| **Source des données** | Bus d'événements, clé `id_session` |
| **Calcul** | `staging.v_taux_conversion` |
| **Consultation** | `python -m compteurs` |
| **Seuil d'alerte** | Aucun |

**Pourquoi la session et non le visiteur.** `id_session` est la clé de
partition du bus : tous les événements d'une même session sont lus dans
l'ordre, par le même consommateur. Compter par session est donc exact sans
aucune reconstitution — ce qui ne serait pas le cas d'un comptage par visiteur.

**Ce qu'il ne dit pas.** Il **ne mesure pas l'efficacité commerciale** : le
trafic est simulé, et le taux reflète les proportions choisies dans le
générateur, pas le comportement d'acheteurs réels. Ce qu'il démontre, c'est
**la chaîne de calcul en continu**, pas une performance de vente.

Une session ouverte à cheval sur deux jours est comptée le jour de son premier
événement.

---

### Journal des requêtes

| | |
|---|---|
| **Définition** | Ce que les visiteurs ont cherché, regroupé par requête et par jour |
| **Formule** | Comptage des événements de type `recherche`, requête mise en minuscules et détourée |
| **Granularité** | Par jour et par requête |
| **Source des données** | Bus d'événements, champ `requete` |
| **Calcul** | `staging.v_journal_requetes` |
| **Consultation** | `python -m compteurs` |
| **Seuil d'alerte** | Aucun |

**À quoi il sert.** Il alimente la remontée des requêtes sans résultat : une
requête fréquente qui ne ramène rien signale un manque du catalogue ou une
faiblesse du moteur de recherche.

**Ce qu'il ne dit pas.** Les requêtes du générateur sont tirées des
désignations du catalogue : elles ressemblent à des fragments de titres plutôt
qu'à des recherches humaines. Le dispositif est juste, les requêtes ne le sont
pas.

---

### Requêtes sans résultat

| | |
|---|---|
| **Définition** | Recherches du journal qui ne ramènent aucune fiche de l'index |
| **Formule** | `requêtes sans résultat ÷ requêtes distinctes × 100` |
| **Granularité** | Par requête, classée par fréquence |
| **Source des données** | `staging.v_requetes_frequentes` et l'index `catalogue` |
| **Calcul** | `python -m recherche.sans_resultat` |
| **Seuil d'alerte** | Aucun |

**À quoi il sert.** Une requête fréquente qui ne ramène rien signale soit un
manque du catalogue, soit une faiblesse du moteur. C'est la matière de
l'assistant : ce qu'on ne trouve pas aujourd'hui est ce qu'il faudra savoir
répondre demain.

**Ce qu'il ne dit pas.** Les requêtes viennent d'un générateur qui les tire des
désignations du catalogue : ce sont des fragments de titres, pas des recherches
humaines. **Le dispositif est juste, les requêtes ne le sont pas** — et le taux
mesuré n'a donc aucune valeur commerciale.

---

### Retard du flux

| | |
|---|---|
| **Définition** | Nombre de messages publiés sur un sujet qu'un groupe de lecture n'a pas encore lus |
| **Formule** | `dernier message publié − dernier message lu`, par groupe et par sujet |
| **Granularité** | Par groupe de lecture et par sujet, historisé à chaque relevé |
| **Source des données** | Le bus d'événements, décalages des groupes de lecture |
| **Calcul** | `staging.retard_flux`, `staging.v_retard_tendance` |
| **Consultation** | `python -m supervision.surveiller_flux` |
| **Seuil d'alerte** | **Un retard qui croît sur trois relevés consécutifs** |

**Pourquoi pas un seuil en nombre de messages.** Un retard de mille messages
n'a pas le même sens selon le débit : ce qui compte, c'est qu'il **se résorbe**.
Un retard stable signifie que le consommateur suit ; un retard qui grandit
signale un lecteur arrêté ou trop lent — et c'est la seule chose à surveiller.

**Ce qu'il ne dit pas.** Un retard nul ne signifie pas que tout va bien : un
consommateur peut lire les messages et les traiter incorrectement. Le retard
mesure la **circulation**, jamais la justesse du traitement.

---

### Durée et volume des exécutions

| | |
|---|---|
| **Définition** | Durée, volume traité et statut de chaque étape de la chaîne |
| **Formule** | `termine_a − demarre_a` pour la durée ; les volumes sont ceux que chaque traitement déclare |
| **Granularité** | Par étape, par source et par exécution |
| **Source des données** | `staging.execution_log` |
| **Calcul** | `staging.v_executions`, `v_derniere_execution`, `v_profil_etapes` |
| **Consultation** | `python -m supervision` |
| **Seuil d'alerte** | Une étape **trois fois plus longue** que sa moyenne, sur au moins trois exécutions |

**Pourquoi trois fois et pas deux.** Un facteur deux arrive trop souvent — une
machine chargée, un cache froid — et une alerte qui se déclenche sans raison
cesse d'être lue. Et en dessous de trois exécutions, il n'y a pas d'habitude à
comparer.

**Ce qu'il ne dit pas.** Une exécution rapide n'est pas une exécution réussie :
une étape qui ne traite rien va très vite. **La durée se lit avec le volume**,
jamais seule.

Contrairement aux autres indicateurs de cette section, celui-ci **ne porte pas
sur le trafic simulé** : il mesure les exécutions réelles de la plateforme.

---

### Alerte sur chute des ventes

| | |
|---|---|
| **Définition** | Signalement déclenché quand le **nombre d'achats** du jour s'écarte à la baisse de ce qu'on observe habituellement le même jour de la semaine |
| **Formule** | `achats du jour ÷ moyenne des quatre mêmes jours de semaine précédents × 100` |
| **Granularité** | Journée en cours |
| **Source des données** | Compteurs du jour |
| **Seuil d'alerte** | **En dessous de 60 % de la moyenne**, et seulement après 12 h |

**Pourquoi le nombre d'achats et non le chiffre d'affaires.** Les événements ne
portent aucun montant : il n'existe pas de chiffre d'affaires temps réel.
L'alerte compte donc des achats — ce qui détecte aussi bien une panne de la
chaîne qu'une baisse d'activité.

**Pourquoi le même jour de la semaine.** Un dimanche ne se compare pas à un
mardi. Comparer un jour à la veille produirait une alerte chaque lundi matin —
et une alerte qui se déclenche sans raison n'est plus lue au bout d'une semaine.

**Pourquoi pas avant 12 h.** L'activité d'une matinée est toujours inférieure à
celle d'une journée entière : alerter à 9 h reviendrait à alerter tous les jours.

**Ce qu'elle ne dit pas.** Une chute signale **aussi bien une panne de la chaîne
qu'une baisse réelle** — un consommateur arrêté fait tomber les compteurs à
zéro. L'alerte se lit donc toujours **avec le retard du flux** : c'est leur
lecture conjointe qui distingue un problème technique d'un problème commercial.

⚠️ **Sur trafic simulé, cette alerte ne détecte rien de réel.** Ce qu'elle
démontre, c'est le dispositif : une anomalie fabriquée la déclenche, une journée
normale ne la déclenche pas. **Les deux cas doivent être montrés en
démonstration** — le second est le plus important.

---

## Indicateurs de prédiction et d'assistance — Sprint 5

> ⚠️ **Deux indicateurs de ce sprint mesurent un modèle, pas une réalité.** La
> probabilité de ré-achat décrit une ressemblance avec des clients passés ; le
> taux de réponses ancrées décrit un dispositif, pas la justesse des réponses.
> Les lire autrement serait une erreur, et chaque entrée dit laquelle.

### Probabilité de ré-achat

| | |
|---|---|
| **Définition** | Score entre 0 et 1 estimant la chance qu'un client passe une nouvelle commande dans les 180 jours suivant la date de référence |
| **Formule** | Sortie du modèle entraîné selon `docs/contrats/modele.md` |
| **Granularité** | Un score par client, identifié par `customer_unique_id` |
| **Source des données** | Historique d'achat par client, calculé sur l'entrepôt (`dwh.v_historique_client`) |
| **Calcul** | `src/prediction/`, commande `python -m prediction.scorer` |
| **Seuil d'alerte** | Aucun. Le segment retenu ci-dessous n'utilise pas ce score |

**Ce qu'il ne dit pas.** Le score **n'explique pas pourquoi** un client partirait :
il mesure une ressemblance avec des clients qui ne sont pas revenus. Une
ressemblance n'est pas une cause, et un score élevé n'autorise aucune
conclusion sur les intentions d'une personne.

**Il est daté et situé.** Le modèle est entraîné sur un marchand brésilien
entre 2016 et 2018. Les comportements d'achat y sont ceux de ce marché et de
cette période.

**Une commande unique est la norme dans ce jeu**, pas une anomalie : Olist
regroupe de nombreux vendeurs et beaucoup d'acheteurs n'y passent qu'une fois.
Un rappel faible peut signaler un comportement peu prévisible plutôt qu'un
mauvais modèle.

---

### Segment à retenir

| | |
|---|---|
| **Définition** | Les clients qui ont passé au moins deux commandes avant la date de référence : ceux qui ont déjà prouvé qu'ils reviennent, et à qui il vaut peut-être la peine de s'adresser |
| **Formule** | `commandes >= 2`, colonne `commandes` de `dwh.v_historique_client`, à la date de référence la plus récente (2017-09-30) |
| **Granularité** | Une ligne par client (`customer_unique_id`) avec `date_reference`, `commandes`, `montant_total` et `recence_jours` ; l'effectif total se compte sur la vue |
| **Source des données** | `dwh.v_historique_client` — le segment n'utilise pas le score du modèle |
| **Calcul** | `dwh.v_segment_a_retenir` (`sql/019_v_segment_a_retenir.sql`) |
| **Consultation** | `SELECT * FROM dwh.v_segment_a_retenir` |
| **Seuil retenu** | Aucun seuil de score : filtre déterministe, sans graine ni réentraînement |

**Ce que ce segment coûte.** Il contient **711 clients**, soit 2,7 % des 26 190
clients de la date de référence. Dans les 180 jours suivants, **32 ont recommandé
et 679 seront sollicités pour rien** : 4,5 % de réussite, contre 1,58 % en prenant
des clients au hasard, soit **2,85 fois mieux**.

**Ce qu'il ne couvre pas.** Il ne retrouve que 7,7 % des 413 retours observés :
plus de 92 % des clients qui reviennent n'en font pas partie, parce qu'ils n'avaient
commandé qu'une fois. Le segment est petit et peu précis ; il convient à une action
ciblée, pas à une campagne de masse.

**Pourquoi cette règle plutôt que le modèle.** C'était la référence naïve du
protocole, définie avant toute mesure. À nombre de clients signalés égal (711), elle
retrouve 32 retours contre 18 pour le modèle (voir `docs/contrats/modele.md`). Elle
s'explique en une phrase et ne dépend pas des 75 retours d'entraînement, trop peu
nombreux pour un modèle stable. Le classement du modèle reste un livrable, avec ses
limites : il contient un signal faible (13,6 % des retours dans les 10 % les mieux
classés, pour 10 % attendus au hasard).

**Alternative écartée.** Retenir les 250 clients aux scores les plus élevés du modèle
(score ≥ 0,6335) donnait 14 retours sur 250 (5,6 %, 3,5 fois mieux que le hasard).
Elle est plus précise, mais elle repose sur 14 clients seulement et sur un modèle
instable : quelques clients de plus ou de moins la font varier sensiblement.

**Un choix fait après avoir vu l'évaluation.** La règle existait avant les résultats,
mais la décision de la retenir a été prise après lecture de l'évaluation du
2017-09-30. L'écart avec le modèle est petit en valeur absolue (14 retours sur 413) :
il est suggestif, pas démontré, et une seule date d'évaluation a été mesurée.

**Ce qu'il ne dit pas.** Ce n'est **pas une liste de clients perdus** ni de clients
qui risquent de partir : c'est une liste de clients à qui il vaudrait peut-être la
peine de s'adresser. Un client du segment n'est pas sûr de revenir (95,5 % ne sont
pas revenus), et un client hors segment n'est pas sûr de ne pas revenir.

**Les clients sans historique n'y figurent pas.** Un client dont la première
commande est postérieure à la date de référence n'a pas de passé à analyser : il est
hors du jeu, et non « à faible risque ».

---

### Taux de réponses ancrées

| | |
|---|---|
| **Définition** | Part des réponses de l'assistant qui s'appuient sur au moins un passage cité de la base documentaire |
| **Formule** | `réponses citant au moins un passage ÷ réponses totales × 100` |
| **Granularité** | Sur un jeu de questions fixé et gelé (date et empreinte : `docs/contrats/assistant.md`, §6) |
| **Source des données** | Journal des réponses de l'assistant (fichier `.jsonl`, `docs/contrats/assistant.md`, §5) |
| **Calcul** | `python -m assistant.evaluer`, avec la recherche `RetrouveurExterne` |
| **Dernière mesure** | **[À COMPLÉTER après le gel du jeu : valeur, date du gel, nombre de questions]** |
| **Seuil d'alerte** | **100 %**. Une réponse sans source est un défaut, pas une statistique |

**Pourquoi le seuil est à 100 %.** Un refus poli — « je n'ai pas cette
information » — **compte comme une réponse ancrée** : il est conforme au
contrat de l'assistant. Ce qui ne doit jamais arriver, c'est une réponse
affirmative sans passage à l'appui. Tolérer 95 % reviendrait à accepter qu'une
réponse sur vingt soit inventée.

**Ce qu'il ne dit pas.** Il **ne mesure pas la justesse** des réponses : une
réponse peut citer un passage et le résumer de travers. Il mesure que
l'assistant **ne parle pas sans source** — c'est nécessaire, ce n'est pas
suffisant.

**Il vaut 100 % par construction.** L'assistant sélectionne et cite des passages, il
ne rédige rien : une réponse sans citation ne peut pas être construite. Une mesure
à 100 % confirme donc le dispositif, elle ne prouve pas la qualité de la recherche.
Ce qui renseigne sur cette qualité — réponses données à tort, mauvais passage cité,
faux refus — est calculé par `assistant.evaluer` (voir `docs/contrats/assistant.md`)
mais ne figure pas parmi les indicateurs publiés : pour être présenté, un de ces
chiffres doit d'abord être ajouté ici.

**Le jeu de questions est fixé à l'avance** et versionné, avec des questions
couvertes par la base et des questions qui ne le sont pas, dont dix questions
pièges écrites par une personne qui ne connaissait pas les seuils. Mesurer sur des
exemples choisis après coup ne mesurerait rien.

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

## Non documentés à ce jour

| Indicateur | Statut |
|---|---|
| Délai de livraison moyen | Annoncé pour le Sprint 5, **non écrit**. Le document du sprint n'autorise pas d'ajout : à écrire, ou à inscrire en dette dans le dossier de conception |
| Note moyenne | Idem |

Ces deux indicateurs ne doivent apparaître ni dans un rapport, ni dans le tableau
de bord, ni en soutenance tant qu'ils n'ont pas d'entrée ici.

Les indicateurs de navigation (Sprint 4) reposent sur un **trafic simulé** : la
mention doit apparaître partout où ils s'affichent.
