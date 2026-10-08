# Dossier de conception — DataFlow360

**Projet :** plateforme data d'un e-commerçant — GROUPE 2, Orange Digital Center, promotion 8
**Version :** mise à jour de clôture du Sprint 5, rédigée le 7 octobre 2026 et mise à jour le 8 octobre (gel du jeu de questions)
**Statut :** reflète le dépôt tel qu'il est. En cas d'écart avec un contrat de `docs/contrats/`, le contrat fait foi et ce dossier est corrigé.

Ce dossier répond à une question : **qu'est-ce qui a été prévu, qu'est-ce qui a été réalisé, et pourquoi l'écart.** Il ne décrit pas l'architecture en détail : celle-ci est dans le [README](../README.md) et dans [`docs/architecture/`](architecture/). Chaque décision renvoie au document du dépôt qui la porte.

---

## 1. Le projet en trois lignes

Une entreprise de commerce en ligne pilote son activité avec des jours de retard, subit le départ de ses clients sans le comprendre, laisse ses acheteurs échouer dans la recherche produit et sature son service client. Nous construisons sa plateforme de données, pas son site : un référentiel unique et contrôlé, puis quatre usages qui le consomment.

| # | Besoin | Ce qui est livré |
|---|---|---|
| 1 | Un référentiel unique, contrôlé et fiable | Entrepôt en étoile `dwh`, taux de rejet mesuré, quarantaine |
| 2 | Piloter l'activité en quasi temps réel | Indicateurs de ventes, compteurs du jour, alerte sur les ventes |
| 3 | Anticiper le départ des clients | Modèle de ré-achat (résultat négatif publié) et segment à retenir par règle |
| 4 | Une recherche produit pertinente | Recherche tolérante aux fautes, filtre par catégorie et par langue |
| 5 | Alléger le service client | Assistant qui sélectionne et cite des passages, avec garde-fous |

---

## 2. Écarts entre le prévu et le réalisé

| # | Prévu | Réalisé | Pourquoi | Où c'est documenté |
|---|---|---|---|---|
| E1 | Contrôle qualité avec Great Expectations | **Pandera** | Voir la note sous le tableau | `src/quality/controle.py` |
| E2 | Relier les produits vendus (Olist) aux fiches du catalogue (Rakuten) | Rattachement **arbitraire mais déterministe à l'intérieur d'une catégorie** | Les deux jeux ne partagent aucun identifiant produit. Seule la correspondance de catégorie est défendable | `contrats/correspondance.md`, `contrats/entrepot.md` |
| E3 | Appeler les services publics (jours fériés, taux de change) | **Service référentiel local** qui sert ce qui a été conservé en zone brute | La démonstration fonctionne sans Internet ; la chaîne reste rejouable si un service disparaît | `contrats/referentiel.md` |
| E4 | Compteurs du jour avec chiffre d'affaires | **Compteurs d'activité, sans aucun montant** | Un événement d'achat ne porte pas de prix : un chiffre d'affaires en temps réel serait un montant inventé | `sql/015_compteurs_du_jour.sql`, `contrats/evenements.md` |
| E5 | Recherche avec filtre de prix | **Filtre de prix abandonné** ; la commande refuse `--prix-min` et `--prix-max` avec un message | Le catalogue ne contient aucun prix, et le lien produit vendu ↔ fiche étant arbitraire (E2), en tirer un prix inventerait un montant | `contrats/recherche.md` |
| E6 | Modèle de ré-achat comme base du segment à retenir | **Segment = règle « au moins deux commandes »** ; le modèle reste livré comme résultat négatif | À volume égal (711 clients), la règle retrouve 32 retours, le modèle 18 | §3.1 et `contrats/modele.md` |
| E7 | Responsabilités du Sprint 5 telles que prévues | **Deux livrables déplacés** | Départ d'Aissata DIALLO ; livrable du modèle non réalisé par son porteur prévu et repris par Ndeye Penda SARR | §5 et `ROLES.md`, §4.3 |

**Note sur E1.** Le dépôt ne consigne pas le motif d'origine du choix de Pandera ; seul le fait est établi (le contrôle valide les DataFrames pandas avec Pandera, et Great Expectations n'est utilisé nulle part). *Le motif est à confirmer par l'équipe avant la soutenance.*

**Une limite commune à E2, E4 et E5.** Ces trois écarts viennent de la même cause : les sources ne se recouvrent pas. Chaque fois, la plateforme a choisi de **ne pas produire un chiffre qu'elle aurait dû inventer**. C'est une position de conception, pas un oubli.

---

## 3. Les trois décisions du jour 1 du Sprint 5

Ce sont celles que le jury interrogera, bien plus que le code.

### 3.1 Qu'est-ce qu'on prédit ?

**Décision.** « Ce client passera-t-il une nouvelle commande dans les 180 jours qui suivent la date de référence ? », par client (`customer_unique_id`, jamais un identifiant de commande), avec un **découpage temporel** : entraînement à la date de référence 2017-03-31, évaluation au 2017-09-30. L'entraînement ne voit jamais la période d'évaluation.

**Motif.** Un découpage aléatoire mélange les périodes : le modèle apprendrait ce qu'il doit prédire et ses résultats seraient excellents et faux. Aucune fonction de découpage aléatoire n'existe dans le code, et un test le vérifie. La vue `dwh.v_historique_client` calcule chaque variable à la date de référence ; le code refuse un jeu à récence ou ancienneté négative, signe qu'une variable connaît l'avenir.

### 3.2 Comment traite-t-on le déséquilibre ?

**Décision.** Classes **pondérées** (`class_weight="balanced"`), aucun exemple dupliqué ni supprimé. **L'exactitude n'est jamais calculée.** On mesure le rappel, la précision et le F1 sur la classe rare, contre deux règles de référence : « tous négatifs » et « deux commandes ou plus ».

**Motif.** Seuls 1,4 à 1,6 % des clients reviennent : répondre « il ne reviendra pas » à tout le monde donnerait plus de 95 % d'exactitude et serait inutile. Comparer le seul rappel déclarerait gagnante la règle qui répond « revient » à tout le monde, d'où le F1 et le rappel **à volume égal**.

**Résultat (exécution du 2026-10-07, vraies données).**

| | Rappel | Précision | F1 | Clients signalés |
|---|---|---|---|---|
| Tous négatifs | 0 | 0 | 0 | 0 |
| Deux commandes ou plus | 0,077 | 0,045 | 0,057 | 711 |
| Modèle (seuil 0,5) | 0,324 | 0,021 | 0,039 | 6 503 |

Le modèle ne bat pas la règle au F1, et à 711 clients signalés il retrouve 18 retours contre 32 pour la règle. Son classement contient un signal faible (13,6 % des retours dans les 10 % du haut, pour 10 % attendus au hasard), pas davantage. **Ce résultat est publié tel quel** ; les limites sont écrites dans `contrats/modele.md`.

**Conséquence : le segment à retenir.** C'est la règle `commandes >= 2` (`dwh.v_segment_a_retenir`) : 711 clients, dont 32 ont recommandé dans les 180 jours et 679 seraient sollicités pour rien (4,5 % de réussite, contre 1,58 % au hasard, soit 2,85 fois mieux). Il ne retrouve que 7,7 % des retours. Ce n'est pas une liste de clients perdus.

**Ce qu'il faut dire honnêtement au jury.** La règle existait avant les résultats, mais la décision de la retenir a été prise **après** lecture de l'évaluation. Une seule date d'évaluation a été mesurée, et 75 retours seulement sont disponibles à l'entraînement. L'écart est suggestif, pas démontré. L'alternative écartée (250 clients aux scores les plus hauts : 14 retours, 5,6 %) est plus précise mais repose sur 14 clients.

### 3.3 Que fait l'assistant quand il ne sait pas ?

**Décision.** Il le dit et renvoie au service client. Il ne devine jamais, et chaque réponse cite les passages sur lesquels elle s'appuie.

**Mise en œuvre.**
- L'assistant **sélectionne et cite**, il ne génère aucun texte : une réponse est exacte par construction, et une réponse sans citation ne peut pas être construite.
- **Avant la recherche**, des règles déterministes refusent ce que la base ne contiendra jamais : un prix, une commande précise, un remboursement personnalisé.
- **Après la recherche**, les scores décident : répondre, suggérer sans affirmer, ou refuser. Il n'y a pas de filtre en amont dans la recherche : un seul endroit à régler (`contrats/passages.md`, §8).
- Un refus est une réponse correcte, pas un échec.

**Ce que mesure le « taux de réponses ancrées », et ce qu'il ne mesure pas.** Il vaut 100 % par construction : il confirme le dispositif, il ne prouve ni la justesse des réponses ni la qualité de la recherche. Les chiffres qui renseignent sur celle-ci (réponse à tort, mauvais passage, faux refus) sont calculés par `python -m assistant.evaluer` et doivent valoir 0 pour les deux premiers.

**Seuils et résultats mesurés (jeu gelé le 2026-10-07).** Seuils : réponse 0,84, suggestion 0,20, marge 0,00 (`contrats/assistant.md`, §6). Sur 62 questions, dont 31 couvertes par la base : 6 bonnes réponses directes, 23 refus avec bonne suggestion, 31 refus corrects (hors base), 2 faux refus, **0 mauvais passage, 0 réponse à tort**. **Ces zéros valent sur ce jeu, pas au-delà** : les seuils ont été réglés sur lui, et une validation croisée sur deux moitiés a donné une erreur grave pour certains réglages voisins. Le seuil de réponse est à moins de 0,001 d'une erreur connue (0,8391, pour « Combien coûte un retour ? »). Les deux faux refus (q05 et s07) viennent d'un passage absent du top 5 du retrouveur : aucun seuil ne peut les sauver. Piste de suite : un reranker après la recherche vectorielle.

---

## 4. Décisions de conception qui structurent la plateforme

| Décision | Motif | Source |
|---|---|---|
| Trois circuits : lots quotidiens, flux continu, documentaire | Seul le flux d'événements exige une réponse immédiate ; il alimente les compteurs **sans passer par l'entrepôt** | README |
| Les usages ne retournent jamais à la source : ils lisent le référentiel | Un seul endroit où la donnée est contrôlée | README |
| Zone brute **immuable**, empreintes SHA-256 contrôlables | Rejouabilité et preuve | README, `zone_brute.md` |
| Staging, quarantaine et journal écrits dans **une seule transaction** | Un échec ne laisse rien à moitié chargé | README, `src/quality/chargement.py` |
| L'index de recherche est lu depuis staging **après transformation**, jamais depuis la zone brute | Une fiche encore balisée (`id&eacute;es`) ne doit pas être indexée | `recherche.md`/`index.md` |
| Recherche : première lettre exacte, tolérance aux fautes dans la requête | `lampe` et `rampe` ne sont distants que d'une lettre. Prix : une faute sur la première lettre n'est pas rattrapée | `recherche.md` |
| Restitution par un compte PostgreSQL en lecture seule | Power BI ne peut rien modifier | README |
| Identifiant de personne (`customer_unique_id`), jamais de commande, pour tout ce qui concerne un client | Un client est une personne, pas une commande | `modele.md` |
| Le journal de l'assistant masque e-mails, téléphones et identifiants avant écriture | Aucune donnée personnelle dans le journal | `src/assistant/journal.py` |

---

## 5. Déplacement des responsabilités

Le détail et les motifs sont dans [`ROLES.md`](ROLES.md), §4.3. En résumé :

| Livrable | Prévu pour | Réalisé par | Cause |
|---|---|---|---|
| Historique d'achat et variables (F3.1) | Aissata DIALLO | Bachir DEME | Départ d'Aissata DIALLO en cours de projet |
| Modèle de ré-achat (F3.2 à F3.6) | Mouhameth DIOP | Ndeye Penda SARR | Livrable non réalisé par son porteur prévu, repris par Ndeye Penda SARR |

**Le départ d'Aissata DIALLO.** Aissata DIALLO a quitté le projet au Sprint 3 : Ndeye Penda SARR a repris sa part des Sprints 3 et 4, puis Bachir DEME celle du Sprint 5 (l'historique d'achat). Un départ en cours de projet s'explique, il ne se découvre pas à la soutenance. Ce qu'elle avait livré avant de partir (normalisation, décodage, langue, déduplication, correspondance, schéma en étoile, indexation du catalogue, rédaction de la foire aux questions avec Seydina) reste crédité. Quatre personnes livrent le périmètre de cinq : c'est un argument, pas une faiblesse.

**Le risque que cela crée.** Les deux chaînes du Sprint 5 ne sont plus parallèles : Bachir est au départ des deux (variables, puis assistant), Ndeye Penda à l'arrivée des deux (modèle, segment, tableau de bord). La mesure retenue : Bachir livre les variables en premier, et Ndeye Penda avance sur un jeu fabriqué de 200 lignes aux mêmes colonnes puis branche le vrai.

---

## 6. Dette technique assumée

Ce qui reste est noté, pas corrigé : le Sprint 5 n'ajoute aucune amélioration des sprints précédents.

| Dette | Conséquence | Statut |
|---|---|---|
| DAG `quotidien` : 10 tâches, **aucune pour la prédiction ni pour l'index des passages** | Le modèle et l'index des passages se lancent à la main | Assumée |
| Couverture du fichier de correspondance des catégories | Une partie des produits est rattachée à `inconnu` | Assumée |
| Requêtes du générateur d'événements peu réalistes | Les compteurs du jour et les requêtes sans résultat sont indicatifs | Assumée |
| Prix absent du catalogue | Pas de filtre de prix, pas de montant en temps réel (E4, E5) | Assumée, voir §2 |
| « Délai de livraison moyen » et « note moyenne » absents du dictionnaire des indicateurs | Variables utilisées par le modèle, non publiées comme indicateurs | **Décision : inscrits en dette**, à valider par le Product Owner. Le document du sprint n'autorise aucun ajout ; leurs définitions existent comme variables de `dwh.v_historique_client` (`contrats/modele.md`). Ils n'apparaissent ni dans un rapport ni dans le tableau de bord tant qu'ils n'ont pas d'entrée au dictionnaire |
| Modèle évalué à **une seule date**, 75 retours à l'entraînement | Écarts de quelques points fragiles | Limite écrite dans `modele.md` |
| Tableau de bord Power BI : seule la page « Qualité » est livrée | Pages ventes, compteurs du jour (« trafic simulé »), segment à retenir et ancrage à construire | **À terminer avant la démonstration** |

---

## 7. État du Sprint 5 à la date de rédaction

À mettre à jour avant la soutenance : ce paragraphe vieillit vite.

| Élément | État le 8 octobre 2026 |
|---|---|
| Variables d'historique (`v_historique_client`) | Fait |
| Modèle de ré-achat, protocole, limites | Fait ; résultat négatif publié |
| Segment à retenir (`v_segment_a_retenir`) | Fait |
| Base documentaire vectorisée et recherche | Fait |
| Assistant et garde-fous | Branché sur la recherche vectorielle par défaut |
| Jeu de questions gelé (date, empreinte) | **Gelé le 2026-10-07** : 62 questions, dont 31 couvertes ; empreinte SHA256 dans `contrats/assistant.md`, §6 |
| Seuils de l'assistant et de la recherche | **Mesurés sur le jeu gelé** : 0,84 / 0,20 / 0,00 (`contrats/assistant.md`, §6) ; l'ancien seuil provisoire de 0,67 est retiré |
| Taux de réponses ancrées | **100 % (62/62)**, relevé le 2026-10-08 sur le jeu gelé : 6 réponses directes citant un passage et 56 refus, comptés comme ancrés (dictionnaire, ligne « Dernière mesure ») |
| `assistant.md` et `passages.md` | Statut « brouillon » **levé** (PR #112) ; les points ouverts restent listés dans chaque contrat |
| Tableau de bord final | Page « Qualité » seule |
| Démonstration chronométrée, captures de secours | À faire |
| Note de version v1.0 | Rédigée (`NOTE_DE_VERSION_v1.0.md`) ; fusion dans `main` et tag `v1.0` à faire |

---

## 8. Démonstration finale et plan de secours

Dix minutes, dans l'ordre du parcours de la donnée :

| Qui | Ce qui est montré |
|---|---|
| Seydina | Une donnée entre, une règle la rejette, le motif est consultable |
| Ndeye Penda | La chaîne quotidienne passe au vert dans Airflow ; les compteurs du jour montent pendant que le générateur tourne |
| Bachir | Une recherche avec faute de frappe aboutit ; l'assistant répond en citant ses sources, puis refuse une question hors base |
| Ndeye Penda | Le tableau de bord : ventes, qualité, temps réel, segment à retenir |

**Avant la démonstration.** Plusieurs journées d'événements avec `--debut`, sinon l'alerte sur les ventes ne montre rien. Une recherche à blanc pour réveiller Elasticsearch (première requête : environ une seconde, ensuite dix millisecondes). Le chargement des systèmes sources fait la veille.

**Si le direct échoue.** Captures et enregistrement : un jury pardonne une panne de réseau, pas l'absence de preuve. La démonstration est répétée au moins deux fois, chronométrée, sur un poste neuf.

**À dire en une phrase.** Des données brutes de deux systèmes sans identifiant commun, jusqu'à un tableau de bord, un moteur de recherche et un assistant qui cite ses sources.
