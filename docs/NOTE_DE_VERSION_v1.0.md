# Note de version — v1.0

**DataFlow360** · GROUPE 2 · Orange Digital Center, promotion 8
**Version :** v1.0, fin du Sprint 5 — « Intelligence artificielle et finalisation »
**Précédente :** v0.5 (fin du Sprint 4, 5 octobre 2026)

v1.0 est la version finale du projet : les cinq besoins du dossier sont couverts, du référentiel unique jusqu'à l'assistant. Quatre personnes livrent le périmètre de cinq.

> **En une phrase.** Des données brutes de deux systèmes sans identifiant commun, jusqu'à un tableau de bord, un moteur de recherche et un assistant qui cite ses sources.

---

## Ce que couvre la version

| # | Besoin | État dans v1.0 |
|---|---|---|
| 1 | Un référentiel unique, contrôlé et fiable | Livré (depuis v0.4) |
| 2 | Piloter l'activité en quasi temps réel | Livré (depuis v0.5) ; compteurs d'activité, sans montant |
| 3 | Anticiper le départ des clients | **Nouveau** : modèle de ré-achat et segment à retenir |
| 4 | Une recherche produit pertinente | Livré (depuis v0.5) ; sans filtre de prix |
| 5 | Alléger le service client | **Nouveau** : base documentaire vectorisée et assistant |

---

## Nouveautés depuis v0.5

### Anticiper le départ des clients (besoin 3)

- **Historique d'achat par client** : la vue `dwh.v_historique_client` calcule, par personne et à une date de référence, le nombre de commandes, les montants, la récence, l'ancienneté, la note moyenne, le délai de livraison subi et les catégories achetées. Aucune variable ne connaît l'avenir.
- **Modèle de ré-achat** (`python -m prediction`) : « ce client repassera-t-il commande dans les 180 jours ? ». Régression logistique, découpage **temporel** (entraînement au 2017-03-31, évaluation au 2017-09-30), classes pondérées, graine fixée. Les scores sortent par `python -m prediction.scorer`.
- **Segment à retenir** : la vue `dwh.v_segment_a_retenir`, construite sur la règle « au moins deux commandes » (voir plus bas pourquoi pas le modèle).

### Alléger le service client (besoin 5)

- **Base documentaire vectorisée** : la foire aux questions découpée en passages portant leur thème et leur source, vectorisée (fastembed, 384 dimensions) et indexée dans Elasticsearch ; réindexation idempotente.
- **Assistant à ancrage documentaire** (`python -m assistant`) : il **sélectionne et cite** des passages, il ne génère aucun texte. Avant la recherche, des règles refusent ce que la base ne contient jamais (prix, commande précise, remboursement personnalisé). Après la recherche, les scores décident : répondre, suggérer sans affirmer, ou refuser. Chaque réponse affiche ses sources.
- **Journal de l'assistant**, avec masquage des e-mails, téléphones et identifiants, d'où se calcule le taux de réponses ancrées.
- **Évaluation sur un jeu de questions fixé** (`python -m assistant.evaluer`) : bonne réponse, refus avec bonne suggestion, faux refus, mauvais passage, réponse à tort.

### Restitution et documentation

- Dictionnaire des indicateurs complété : probabilité de ré-achat, segment à retenir, taux de réponses ancrées.
- Dossier de conception à jour (`docs/dossier_conception.md`) : écarts entre le prévu et le réalisé, décisions, dette.
- `ROLES.md` révisé (§4.3) après le départ d'Aissata DIALLO et la reprise du modèle.

---

## Résultats à connaître

Ils sont publiés tels quels, y compris quand ils sont défavorables.

**Le modèle ne fait pas mieux que la règle simple.** Évaluation au 2017-09-30 : 26 190 clients, 413 qui reviennent (1,58 %).

| | Rappel | Précision | F1 | Clients signalés |
|---|---|---|---|---|
| Tous négatifs | 0 | 0 | 0 | 0 |
| Deux commandes ou plus | 0,077 | 0,045 | 0,057 | 711 |
| Modèle (seuil 0,5) | 0,324 | 0,021 | 0,039 | 6 503 |

À nombre de clients signalés égal (711), la règle retrouve 32 retours et le modèle 18. Le classement du modèle contient un signal faible (13,6 % des retours dans les 10 % les mieux classés, pour 10 % attendus au hasard), pas davantage. L'exactitude n'est jamais calculée : répondre « il ne reviendra pas » à tout le monde en donnerait plus de 95 %.

**Le segment à retenir** compte 711 clients : 32 ont recommandé dans les 180 jours, 679 seraient sollicités pour rien (4,5 % de réussite contre 1,58 % au hasard, soit 2,85 fois mieux). Il ne retrouve que 7,7 % des retours : ce n'est pas une liste de clients perdus. La décision de retenir la règle plutôt que le modèle a été prise après lecture de l'évaluation, sur une seule date d'évaluation et 75 retours à l'entraînement ; l'écart est suggestif, pas démontré.

**Le taux de réponses ancrées vaut 100 % par construction** : l'assistant ne peut pas produire une réponse sans citation. La mesure confirme le dispositif, elle ne prouve ni la justesse des réponses ni la qualité de la recherche.

---

## Écarts par rapport au prévu

Détail et motifs : `docs/dossier_conception.md`, §2.

- Contrôle qualité avec **Pandera** (et non Great Expectations).
- Rattachement des produits vendus aux fiches du catalogue **arbitraire à l'intérieur d'une catégorie** : les deux jeux n'ont aucun identifiant commun.
- **Service référentiel local** pour les jours fériés et les taux de change.
- Compteurs du jour **sans aucun montant** : un événement d'achat ne porte pas de prix.
- **Filtre de prix abandonné** dans la recherche : le catalogue n'en contient pas.
- Segment à retenir par règle, et non par le modèle.

---

## Limites connues

- **Jeu de questions de l'assistant** : au moment de cette note, il n'est pas encore gelé (date et empreinte) ; les seuils de l'assistant et de la recherche sont à mesurer sur le jeu gelé, et le taux d'ancrage n'a pas de valeur officielle avant ce gel. *À mettre à jour avant de taguer si le gel est fait.*
- `docs/contrats/assistant.md` et `docs/contrats/passages.md` restent au statut « brouillon » tant que les seuils ne sont pas écrits.
- **Tableau de bord Power BI** : la page « Qualité » est livrée ; les pages ventes, compteurs du jour (« trafic simulé »), segment à retenir et ancrage restent à finaliser.
- Le DAG `quotidien` (10 tâches) ne lance ni la prédiction ni l'index des passages : ils se lancent à la main.
- Couverture du fichier de correspondance des catégories partielle ; requêtes du générateur d'événements peu réalistes ; prix absent du catalogue.
- Modèle évalué à une seule date ; ses résultats sont fragiles à quelques points près.
- « Délai de livraison moyen » et « note moyenne » ne figurent pas encore au dictionnaire des indicateurs.

---

## Équipe

| Membre | Rôle de conduite | Part de la v1.0 |
|---|---|---|
| Bachir DEME | Product Owner | Historique d'achat et variables, assistant et garde-fous |
| Ndeye Penda SARR | Conception et documentation | Modèle de ré-achat, segment, dictionnaire, tableau de bord, dossier de conception |
| Seydina WADE | — | Base documentaire vectorisée, qualité, intégration continue |
| Mouhameth DIOP | Scrum Master | Acquisition et flux d'événements (versions précédentes) |
| Aissata DIALLO | — | A quitté le projet ; ses livrables antérieurs sont conservés (`ROLES.md`, §4.3) |

---

## Démarrer et vérifier

Le démarrage de la plateforme, le circuit par lots et le workflow Airflow sont décrits dans le [README](../README.md) ; tous les contrats sont dans [`docs/contrats/`](contrats/).

Avant une démonstration : charger plusieurs journées d'événements avec `--debut`, faire une recherche à blanc pour réveiller Elasticsearch, et charger les systèmes sources la veille.

## Historique des versions

| Version | Contenu |
|---|---|
| v0.1 | Sprint 0 — organisation et préparation |
| v0.2 | Sprint 1 — acquisition et stockage brut |
| v0.3 | Sprint 2 — qualité et transformation |
| v0.4 | Sprint 3 — entrepôt, indicateurs et orchestration |
| v0.5 | Sprint 4 — temps réel, recherche et supervision |
| **v1.0** | **Sprint 5 — intelligence artificielle et finalisation** |
