# Script de la vidéo explicative — DataFlow360

**Livrable :** vidéo explicative retraçant l'ensemble du projet, de sa conception jusqu'au résultat final.
**Durée visée :** 18 minutes, dans la fourchette demandée de 15 à 20.
**Structure :** les cinq étapes imposées, dans l'ordre.

> **La règle qui décide du contenu.** Le coach écrit : *« Il n'est pas nécessaire de montrer chaque ligne de code. La vidéo doit privilégier l'explication de la démarche et des choix techniques. »* Chaque fois qu'on hésite entre montrer et expliquer, on explique.

---

## Avant d'enregistrer

| À faire | Pourquoi |
|---|---|
| `docker compose up -d` puis `python scripts/diagnostic_connexions.py` | Les quatre services doivent répondre avant la première prise |
| `python -m generateur --debit 20 --duree 600 --debut <il y a 5 jours>` | Sans plusieurs journées d'événements, l'alerte sur les ventes ne montre rien |
| Une recherche à blanc | La première requête Elasticsearch prend une seconde, les suivantes dix millisecondes |
| Le chargement des sources fait **la veille** | Pas le jour de l'enregistrement |
| Résolution d'écran en 1920×1080, notifications coupées | Une notification en plein cadre oblige à tout refaire |
| Zoom du terminal à 150 %, du navigateur à 125 % | Le texte doit être lisible sur un téléphone |

**Enregistrer par étape, pas d'une traite.** Cinq fichiers séparés, assemblés ensuite. Une erreur à la quatorzième minute ne doit pas coûter les treize précédentes.

---

## Étape 1 — Présentation du projet · 2 min · Ndeye Penda

| | |
|---|---|
| **À l'écran** | Slides *cover* et *equipe* |
| **Ton** | Posé, on plante le décor |

**Ce qu'on dit**

- Le nom : DataFlow360. Le groupe : GROUPE 2, promotion 8 du Développement Data à l'Orange Digital Center.
- Les membres, un par un, avec leur périmètre : Bachir DEME (recherche et assistant, Product Owner), Mouhameth DIOP (acquisition et flux, Scrum Master), Ndeye Penda SARR (orchestration, restitution, modèle), Seydina WADE (stockage, qualité, intégration continue), Aissata DIALLO (transformation et intégration, départ au Sprint 3).
- Le domaine : **e-commerce et distribution**.
- Le problème métier, en une phrase : *une entreprise de commerce en ligne produit ses données dans des systèmes séparés et de qualité inégale, et ne sait donc ni piloter son activité à temps, ni comprendre le départ de ses clients.*
- L'objectif de la solution : **construire sa plateforme de données** — collecter, contrôler, consolider, puis exposer à travers quatre usages.
- Dire tout de suite ce qu'on ne fait pas : *nous ne construisons pas le site marchand. La boutique est une source pour nous, pas un livrable.*

---

## Étape 2 — Recherche et analyse du besoin · 3 min · Seydina

| | |
|---|---|
| **À l'écran** | Slides *a-probleme*, *a-perimetre*, *b-besoins* · puis le tableau d'inventaire des sources du dossier (§3.2) |
| **Ton** | Factuel, on montre qu'on a mesuré avant de construire |

**Ce qu'on dit**

- **Le contexte étudié** : quatre symptômes, tous mesurables — pas de vue consolidée, des départs clients incompris, une recherche qui échoue, un support saturé.
- **La problématique identifiée** : le premier symptôme commande les trois autres. Sans référentiel unique, on ne peut ni anticiper, ni améliorer, ni répondre autrement qu'à l'intuition.
- **Les besoins utilisateurs** : cinq besoins, traduits en 44 fonctionnalités numérotées de F1.1 à F6.5. Montrer un code, par exemple F1.5, et dire qu'on le retrouve dans la branche, le commit, le contrat et les tests.
- **Les recherches effectuées** : nous avons mesuré les sources avant de les utiliser. Donner trois chiffres :
  - 261 831 lignes de géolocalisation strictement dupliquées sur 1 000 163, soit 26 %
  - 63,6 % des descriptions produits contiennent des entités HTML
  - **96,88 % des clients n'ont passé qu'une seule commande**
- **Les principales conclusions** : ces mesures ont changé la conception. La dernière a changé la cible du modèle — prédire un départ n'avait aucun sens, nous prédisons un nouvel achat. Et deux identifiants client de portée différente nous ont imposé une règle : *toute agrégation par client se fait sur l'identifiant de personne.*

> Conclure l'étape ainsi : **les défauts des sources sont une ressource, pas un obstacle.** Ils donnent au contrôle qualité une matière réelle et rendent le taux de rejet mesurable.

---

## Étape 3 — Conception de la solution · 4 min 30 · Ndeye Penda

| | |
|---|---|
| **À l'écran** | Slides *b-sources*, *b-contrainte*, **le schéma d'architecture** (`docs/architecture/`), *b-architecture*, *b-choix* |
| **Ton** | C'est le cœur de la note : l'architecture doit être **expliquée visuellement** |

**Ce qu'on dit**

**Les données et leurs sources** — cinq sources de cinq natures différentes, une par membre : SQL, temps réel, API, NoSQL, fichiers. Dire que les cinq existent à la fin du Sprint 4, et que les avis sont sortis de la base de la boutique quand la source fichiers a existé, sinon la même donnée entrait par deux chemins.

**Le cycle de vie des données** — quatre zones aux règles différentes, et ce sont des engagements vérifiés par des tests :

| Zone | Règle |
|---|---|
| Zone brute | **Immuable**, jamais modifiée, empreintes SHA-256 |
| Quarantaine | **En ajout seul**, jamais purgée |
| Zone intermédiaire | **Écrasée** à chaque exécution |
| Entrepôt | **Historisé** en SCD2 |

**L'architecture générale** — rester sur le schéma et suivre la donnée avec le curseur. Les trois circuits :
- **A, par lots, chaque jour** : sources → zone brute → contrôle → transformation → intégration → entrepôt.
- **B, en continu** : générateur → bus Kafka → consommateur → compteurs du jour. **Ne passe pas par l'entrepôt**, et dire pourquoi : c'est la seule voie qui exige une réponse immédiate.
- **C, documentaire** : catalogue nettoyé → index de recherche ; foire aux questions → passages → vecteurs → assistant.

**La justification des choix** — s'arrêter sur deux, en montrant qu'un refus se justifie aussi :
- **MinIO écarté** pour la zone brute : 174 Mo de fichiers statiques, une seule machine, aucun accès concurrent. Un volume partagé suffit. *Une technologie étudiée n'est pas une technologie due.*
- **Pandera à la place de Great Expectations**, décidé au Sprint 2 : le rapport de validation faisait double emploi avec notre taux de rejet, et notre vraie question était « quelles lignes, pour quelle règle », pas « est-ce conforme ».

**Le rôle du ML et de l'IA** — annoncer honnêtement ce qui sera détaillé à l'étape 4 : un modèle de ré-achat qui ne bat pas la règle simple, et un assistant qui ne génère rien.

> La contrainte à ne pas oublier dans cette étape : **les deux jeux ne partagent aucun identifiant produit.** Elle explique trois de nos écarts, et il vaut mieux l'énoncer ici que la subir en question.

---

## Étape 4 — Réalisation technique · 4 min 30 · Bachir et Mouhameth

| | |
|---|---|
| **À l'écran** | L'arborescence de `src/`, un contrat de `docs/contrats/`, le DAG dans Airflow, la page Actions de GitHub, la sortie de `pytest` |
| **Ton** | Montrer la démarche, pas le code ligne à ligne |

**Ce qu'on dit**

**L'organisation du projet** *(Mouhameth)* — six sprints, un responsable unique par tâche, une branche et une demande de fusion relue par un membre d'un autre périmètre. Dire que **quatorze fonctionnalités sur quarante-quatre ont changé de mains**, chacune avec son motif écrit.

**La structure du code** *(Mouhameth)* — montrer `src/` : un dossier par périmètre, donc par responsable. Chaque module se lance en ligne de commande et rend un code de sortie. C'est ce qui a permis à Airflow de les appeler tels quels au Sprint 3, sans rien réécrire.

**Les pipelines et les traitements** *(Mouhameth)* — les quatre étapes du circuit par lots. S'arrêter sur deux décisions :
- zone intermédiaire, quarantaine et journal écrits **dans une seule transaction** ;
- la **vérification** est une étape à part entière — un entrepôt chargé sans être vérifié n'est pas livré.

**Les bases de données** *(Mouhameth)* — PostgreSQL pour l'entrepôt en étoile, MongoDB pour le catalogue à structure irrégulière, Elasticsearch pour la recherche lexicale et vectorielle. Une phrase par choix, pas plus.

**Les modèles ML et IA** *(Bachir)* — le point de franchise de la vidéo :
- découpage **temporel**, jamais aléatoire ; un test vérifie qu'aucune fonction de découpage aléatoire n'existe ;
- l'exactitude **n'est jamais calculée** — avec 1,5 % de positifs, répondre « non » à tous donnerait 95 % ;
- le résultat : à volume égal, la règle retrouve 32 retours, le modèle 18. **Nous publions ce résultat tel quel**, et le segment livré est la règle.
- l'assistant **sélectionne et cite**, il ne génère rien. Une réponse est exacte par construction. Sur le jeu gelé : 0 mauvais passage, 0 réponse à tort — *et dire que ces zéros valent sur ce jeu, pas au-delà.*

**L'API** *(Bachir)* — FastAPI devant la recherche et l'assistant, consommée par l'application React.

**Docker** *(Bachir)* — onze services, versions épinglées, chaque port publié sur l'adresse locale uniquement.

**CI/CD et tests** *(Bachir)* — trois travaux indépendants, 890 tests. Raconter l'histoire du troisième travail : *quatre défauts de migration ont atteint notre base alors que la suite était verte, parce qu'aucun test ne touchait une vraie base. Nous avons ajouté 82 tests d'intégration PostgreSQL à la chaîne, et deux garde-fous sur les migrations.*

---

## Étape 5 — Démonstration de la solution · 4 min · toute l'équipe

| | |
|---|---|
| **À l'écran** | Le terminal, Airflow, l'application web, Power BI |
| **Ton** | Rythmé. Chaque geste montre un résultat, aucun temps mort |

**L'ordre, qui est celui du parcours de la donnée**

| Qui | Ce qu'on montre | Ce qu'il faut voir à l'écran |
|---|---|---|
| **Seydina** | `python -m quality.controle --source olist` puis `python -m quality.quarantaine --regle OLIST_AVIS_02` | Les lignes lues, écrites, rejetées. Puis une ligne rejetée **avec son motif**, et le fichier d'origine |
| **Ndeye Penda** | Le DAG `quotidien` dans Airflow, déclenché | Les treize tâches passent au vert dans l'ordre |
| **Ndeye Penda** | `python -m generateur` dans un terminal, `python -m compteurs` dans l'autre | Les compteurs **montent en direct**. Dire « sur trafic simulé » |
| **Bachir** | `chaise de bureu` dans la recherche | Des chaises de bureau remontent malgré la faute |
| **Bachir** | Une question couverte, puis une question hors base | L'assistant **cite ses passages**, puis **refuse** et renvoie au service client |
| **Ndeye Penda** | Power BI, les six pages | Ventes, Produits, Temps réel, **Qualité**, Segment, Assistant |

**Comment lancer la solution** — le dire une fois, au début de l'étape : `docker compose up -d`, puis `scripts/appliquer_sql.py`. Une commande, onze services.

**La valeur apportée** — fermer avec les trois chiffres :
- un chiffre d'affaires de **13 493 151,56**, recalculé sur les faits et identique au centime à la vue publiée ;
- un segment de **711 clients** à solliciter, 2,85 fois mieux que le hasard ;
- un assistant qui, sur le jeu gelé, n'a **jamais répondu à tort**.

**La phrase de fin**

> *Des données brutes de deux systèmes sans identifiant commun, jusqu'à un tableau de bord, un moteur de recherche et un assistant qui cite ses sources.*

---

## Répartition de la parole

| Membre | Temps | Étapes |
|---|---|---|
| Ndeye Penda SARR | ≈ 7 min | 1, 3, et sa part de la démonstration |
| Bachir DEME | ≈ 4 min | la moitié de 4, et sa part de la démonstration |
| Mouhameth DIOP | ≈ 3 min | la moitié de 4 |
| Seydina WADE | ≈ 4 min | 2, et sa part de la démonstration |

Chacun parle de **son** périmètre : c'est ce qui rend la vidéo crédible, et c'est aussi ce qui prépare les questions du jury, posées au hasard et non au spécialiste.

---

## Trois choses à ne pas faire

1. **Ne pas lire les slides.** La caméra montre la slide, la voix ajoute ce qui n'y est pas écrit — le pourquoi.
2. **Ne pas masquer un échec.** Le résultat négatif du modèle et les 42 tests hors CI sont dans la vidéo, dits par nous. Un jury qui les découvre seul les compte double.
3. **Ne pas enregistrer la démonstration en direct sans filet.** Faire une prise de secours des quatre séquences, écran par écran, avant la prise finale.
