# Yakaarou Diaykaat BI — DataFlow360

[![CI](https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI/actions/workflows/ci.yml)

**Plateforme data d'un e-commerçant en croissance**
GROUPE 2 · Formation Développement Data, promotion 8 · Orange Digital Center


---

## Le projet

Une entreprise de commerce en ligne produit ses données dans des systèmes séparés et de qualité inégale. Faute d'une vue consolidée et fiable, elle pilote son activité avec plusieurs jours de retard, subit le départ de ses clients sans le comprendre, laisse ses acheteurs échouer dans la recherche produit et sature son service client.

Nous ne construisons pas le site marchand. Nous nous plaçons dans la position de l'équipe data de cette entreprise, et nous construisons sa **plateforme de données** : elle collecte les données dispersées, en contrôle la qualité, les consolide dans un référentiel unique, puis les expose à travers quatre usages.

| # | Besoin | Ce que la plateforme produit |
|---|---|---|
| 1 | Un référentiel unique, contrôlé et fiable | Entrepôt en schéma en étoile, taux de rejet mesuré |
| 2 | Piloter l'activité en quasi temps réel | Tableau de bord, compteurs du jour et alerte sur les ventes |
| 3 | Anticiper le départ des clients | Probabilité de ré-achat et segment de clients à retenir |
| 4 | Une recherche produit pertinente | Moteur tolérant aux fautes, filtre par catégorie |
| 5 | Alléger le service client | Assistant qui sélectionne et cite des passages d'une base documentaire délimitée |

Le premier besoin conditionne les quatre autres : c'est le socle. Les quatre usages consomment le même référentiel et ne retournent jamais chercher leur donnée à la source.

---

## Architecture

![Architecture générale de DataFlow360](docs/architecture/architecture_dataflow360.png)

La donnée suit **trois circuits** :

- **Par lots, chaque jour** — commandes, clients, avis et catalogue traversent la zone brute, le contrôle qualité, la transformation et l'intégration, jusqu'à l'entrepôt. Le DAG Airflow `quotidien` les enchaîne.
- **En continu** — les événements de navigation passent par le bus d'événements et alimentent directement les compteurs de la journée, **sans passer par l'entrepôt**. C'est la seule voie qui exige une réponse immédiate.
- **Documentaire** — le catalogue contrôlé est indexé pour la recherche produit. La foire aux questions, découpée en passages puis vectorisée, est indexée pour l'assistant.

### Technologies

| Rôle | Technologie |
|---|---|
| Collecte par lots | Python, pandas |
| Bus d'événements | Kafka (`confluent-kafka`) |
| Zone brute | Volume Docker partagé |
| Contrôle qualité | Pandera |
| Entrepôt analytique | PostgreSQL |
| Catalogue produits (source documentaire) | MongoDB |
| Recherche lexicale et vectorielle | Elasticsearch |
| Vecteurs de texte | fastembed, modèle `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions) |
| Service référentiel (jours fériés, taux de change) | API locale FastAPI, servie par uvicorn |
| Orchestration | Airflow |
| Restitution | Power BI, via un compte PostgreSQL en lecture seule |
| Prédiction | scikit-learn |
| Assistant | Python : il **sélectionne et cite** des passages, il ne génère aucun texte |
| Conteneurisation | Docker Compose |
| Intégration continue | GitHub Actions (ruff, pytest) |

Le schéma ci-dessus est l'**architecture cible**. Ce qui fonctionne aujourd'hui est décrit dans la section suivante. Les écarts entre le prévu et le réalisé seront consignés dans le dossier de conception, en cours de rédaction.

---

## État actuel

Le projet est au **Sprint 5** (« Intelligence artificielle et finalisation »), en phase de clôture. Les Sprints 0 à 4 sont terminés.

| Usage | État | Code | Contrat |
|---|---|---|---|
| Zone brute et acquisition | Fonctionne | `src/acquisition/`, `src/zone_brute/` | `zone_brute.md` |
| Contrôle qualité, quarantaine, staging | Fonctionne | `src/quality/` | `quarantaine.md`, `zones_stockage.md` |
| Transformation | Fonctionne | `src/transformation/` | — |
| Intégration et entrepôt `dwh` | Fonctionne | `src/integration/`, `sql/007_entrepot.sql` | `correspondance.md`, `entrepot.md` |
| Indicateurs de ventes | Fonctionne | `src/indicateurs/`, `sql/010_vues_indicateurs.sql` | `docs/dictionnaire_indicateurs.md` |
| Flux d'événements et compteurs du jour | Fonctionne ; trafic **simulé**, aucun montant | `src/generateur/`, `src/compteurs/` | `evenements.md` |
| Supervision de la chaîne et du flux | Fonctionne | `src/supervision/` | — |
| Recherche produit | Fonctionne ; pas de filtre de prix (le catalogue n'en contient pas) | `src/recherche/` | `recherche.md`, `index.md` |
| Service référentiel | Fonctionne | `src/referentiel/` | `referentiel.md` |
| Orchestration quotidienne | Fonctionne, 13 tâches (dont les scores de ré-achat et l'index des passages) | `dags/quotidien.py` | `workflow.md` |
| Modèle de ré-achat | Fait ; ne bat pas la règle simple, résultat publié tel quel | `src/prediction/` | `modele.md` |
| Segment à retenir | Fait : vue `dwh.v_segment_a_retenir` | `sql/019_v_segment_a_retenir.sql` | dictionnaire |
| Base documentaire vectorisée (FAQ) | Fait ; indexée chaque jour par le DAG | `src/documentaire/`, `docs/documentaire/` | `faq.md` (brouillon), `passages.md` |
| Assistant | Branché sur la recherche vectorielle par défaut ; seuils mesurés sur le jeu gelé (62 questions) | `src/assistant/` | `assistant.md` |
| Tableau de bord Power BI | Fait : 6 pages (Ventes, Produits, Temps réel, Qualité, Segment, Assistant) | `dashboards/ventes.pbix`, `docs/captures/` | dictionnaire |

Tous les contrats sont dans [`docs/contrats/`](docs/contrats/).

### Circuit par lots

```
data/sources/  ──python -m acquisition [--source rakuten]──▶  data/raw/lots/<source>/ingestion=<id>/   (zone brute + manifeste)
                                                                        │
                                                   python -m quality.controle --source <olist|rakuten> --ingestion <id>
                                                                        │
                                              ┌─────────────────────────┴──────────────────────────┐
                                    lignes valides                                           lignes rejetées (règles bloquantes)
                                              ▼                                                    ▼
                                 PostgreSQL staging.<tables>                          PostgreSQL quarantaine.rejets
                                              │                                                    │
                                              │               staging.execution_log ◀──────────────┘  (une ligne par exécution)
                                              │                          │
                               python -m transformation                python -m quality.rapport --seuil 5
                                 (écrit en place dans staging)
                                              │
                          python -m integration.correspondance
                          python -m integration.chargement   ──▶  entrepôt dwh
                          python -m integration.verifier
```

- Staging, quarantaine et journal sont écrits **dans une seule transaction** (`src/quality/chargement.py`) : un échec ne laisse rien à moitié chargé.
- Relancer le contrôle d'une même ingestion **écrase** staging, **n'ajoute pas** une seconde fois les mêmes rejets à la quarantaine (append-only), et **ajoute** une ligne au journal.
- La seule vérité est PostgreSQL. `--export-csv` écrit en plus une copie d'audit dans `data/audit_qualite/`, que rien ne relit.
- La transformation se relance **après** chaque contrôle : le rechargement de staging remet ses colonnes à NULL.
- La zone brute est immuable : `python -m zone_brute verifier` contrôle les empreintes SHA-256 des ingestions.

### Workflow Airflow

Le DAG `quotidien` (`dags/quotidien.py`, exécution `@daily`) lance chaque étape par une commande `python -m ...` dans un environnement Python séparé. Le seuil de rejet se règle par une variable Airflow : `airflow variables set seuil_rejet 5`.

```
acquisition ───────────▶ controle_olist ────────┐
                                                ├──▶ rapport_rejet ──▶ transformation ─┬──▶ correspondance ──▶ chargement ──▶ verification ──▶ scores_reachat
acquisition_catalogue ─▶ controle_catalogue ────┘                                      └──▶ reindexation ──▶ etat_index

indexation_passages        (sans dépendance amont : part en même temps que les acquisitions)
```

Un rapport de rejet au-dessus du seuil est un échec métier : la tâche n'est pas rejouée. La réindexation du catalogue avance en parallèle du chargement de l'entrepôt, pour qu'une indexation lente ne retarde pas les chiffres de vente, et `etat_index` la contrôle en comparant l'index à la zone intermédiaire.

Deux tâches complètent la chaîne : `indexation_passages` (vérifie puis indexe la FAQ, sans dépendance amont) et `scores_reachat` (écrit tous les scores dans `data/scores_reachat.csv`, après la `verification` de l'entrepôt). L'entraînement et l'évaluation du modèle (`python -m prediction`) restent lancés à la main.

### Recherche produit

L'index Elasticsearch du catalogue (`src/recherche/`) tolère les fautes de frappe et filtre par catégorie. Il n'offre **aucun filtre de prix** : le catalogue source ne contient pas de prix.

```bash
python -m recherche.indexer [--recreer]                  # indexer le catalogue
python -m recherche.etat                                 # comparer l'index à la zone intermédiaire
python -m recherche.chercher "chaise de bureu"           # chercher ; --categorie, --langue, --taille
python -m recherche.sans_resultat                        # requêtes fréquentes sans résultat
```

### Flux d'événements

Un générateur publie des événements de navigation sur Kafka, selon le contrat d'événement v1. Un consommateur les retient une seule fois et alimente les compteurs du jour, lus par des vues SQL.

```bash
python scripts/creer_sujets.py                           # crée les sujets Kafka
python -m generateur --debit 20 --duree 300 --graine 42  # simule du trafic
python -m compteurs                                      # consomme le bus puis affiche l'activité
python -m compteurs.surveiller_ventes                    # alerte sur chute des ventes
python -m supervision                                    # journal des exécutions
python -m supervision.surveiller_flux                    # retard du flux
python -m indicateurs                                    # indicateurs de ventes (--periode jour|mois)
```

⚠️ Le trafic est **simulé** et les compteurs mesurent l'**activité**, jamais un chiffre d'affaires : un événement d'achat ne porte aucun montant. Cette mention accompagne tout chiffre affiché.

### Prédiction et segment à retenir

Le modèle de ré-achat (`src/prediction/`, scikit-learn) estime la chance qu'un client repasse commande dans les 180 jours. Le découpage est temporel, le déséquilibre des classes est traité par pondération, et l'exactitude n'est jamais retenue comme mesure. Le protocole, les résultats et les limites sont dans [`docs/contrats/modele.md`](docs/contrats/modele.md).

```bash
python -m prediction                                     # entraîne et publie l'évaluation
python -m prediction --fabrique                          # même chose sur un jeu de 200 lignes
```

À nombre de clients signalés égal, le modèle fait moins bien que la règle simple « au moins deux commandes ». L'équipe a donc retenu cette règle comme **segment à retenir** : 711 clients à la date de référence 2017-09-30, soit 2,85 fois mieux que le hasard, mais seulement 7,7 % des retours observés. La décision a été prise après lecture de l'évaluation ; le dictionnaire des indicateurs le dit. Le segment est exposé par la vue `dwh.v_segment_a_retenir`.

### Assistant et base documentaire

La base documentaire est une foire aux questions (`docs/documentaire/faq.jsonl`), répartie en cinq thèmes (livraison, retours, paiement, commande, compte). Chaque entrée devient un passage, vectorisé et indexé dans Elasticsearch (index `faq_passages`).

L'assistant **sélectionne et cite** des passages : il ne rédige rien, donc une réponse est exacte par construction. S'il ne trouve pas de passage assez proche, ou si la question sort du périmètre, il refuse et renvoie vers le service client. Un refus est une réponse correcte.

```bash
python -m documentaire.verifier                          # vérifie la FAQ (contrat faq.md)
python -m documentaire.indexer [--recreer]               # indexe les passages
python -m documentaire.rechercher "ma question" -k 5     # affiche le JSON du contrat
python -m assistant "Comment suivre ma commande ?"       # interroge l'assistant (--json, -k, --sans-journal)
python -m assistant.evaluer                              # évalue sur le jeu de questions
```

- Le retrouveur par défaut est **externe** : il passe par la recherche vectorielle d'Elasticsearch. La variable `ASSISTANT_RETROUVEUR=depannage` bascule sur une recherche TF-IDF hors ligne, pour les tests et les diagnostics.
- Chaque échange est écrit dans un journal `.jsonl` local, sauf avec `--sans-journal`.
- `assistant.evaluer` mesure, du plus grave au moins grave : les réponses à tort, les mauvais passages, les faux refus, puis les questions bien orientées. Le taux de réponses ancrées vaut 100 % par construction.
- Le jeu de questions (`tests/assistant/jeu_de_questions.jsonl`, 62 questions dont les dix questions pièges de Seydina) est **gelé** depuis le 2026-10-07 (empreinte dans `tests/assistant/jeu_de_questions.gel.json`).
- Les seuils de l'assistant (0,84 / 0,20 / 0,00) ont été mesurés sur ce jeu gelé : 0 mauvais passage et 0 réponse à tort **sur ce jeu**, ce qui n'est pas une garantie au-delà (limites au §6 de [`assistant.md`](docs/contrats/assistant.md)). Taux de réponses ancrées relevé le 2026-10-08 : 100 % (62/62), voir le dictionnaire des indicateurs. Les seuils de dépannage (0,35 / 0,18 / 0,12) ne servent qu'au retrouveur TF-IDF hors ligne.

### Reste à faire pour clore le Sprint 5

- Construire les pages manquantes du tableau de bord (ventes, compteurs du jour, segment, ancrage).
- Rédiger le dossier de conception, puis publier la version 1.0 : fusion de `develop` dans `main` et tag `v1.0`.

---

## L'équipe

| Membre | Rôle | Périmètre principal |
|---|---|---|
| Bachir DEME | Product Owner | Recherche, Machine Learning, assistant |
| Ndeye Penda SARR | Conception et documentation | Orchestration, restitution décisionnelle, modèle de ré-achat et segment |
| Seydina WADE | Développement | Stockage, qualité des données, intégration continue, base documentaire vectorisée |

Mouhameth DIOP (acquisition et flux d'événements) et Aissata DIALLO (transformation et intégration) ont également contribué aux premiers sprints. Ce qui revenait à Aissata a été redistribué à Bachir et à Ndeye Penda.

Qui fait quoi, qui décide quoi et qui supplée qui : voir [`docs/ROLES.md`](docs/ROLES.md).

---

## Arborescence

```
Yakaarou_Diaykaat_BI/
├── .github/workflows/       intégration continue (ci.yml : ruff, pytest, puis tsc et build du frontend)
├── dags/                    workflow Airflow (quotidien.py)
├── dashboards/              tableau de bord Power BI (ventes.pbix)
├── data/                    données locales — jamais versionnées
│   ├── sources/             fichiers livrés par les sources (Olist, Rakuten)
│   ├── raw/                 zone brute, donnée telle que reçue, jamais modifiée
│   ├── audit_qualite/       copie CSV facultative d'un contrôle (--export-csv)
│   └── models/              modèles entraînés
├── docker/
│   ├── airflow/             image d'Airflow (avec l'environnement Python du projet)
│   ├── app/                 image du conteneur de travail et du service référentiel
│   └── postgres/init/       création des bases et des schémas au premier démarrage
├── frontend/                application web React + TypeScript (Vite) — 3 pages
│   └── src/
│       ├── pages/           vue générale, recherche, assistant
│       ├── components/      barre du haut, squelettes de chargement, bouton de reprise
│       ├── api/             client HTTP de l'API
│       └── types/           miroir TypeScript des schémas Pydantic
├── docs/
│   ├── architecture/        schéma d'architecture
│   ├── captures/            captures du tableau de bord
│   ├── contrats/            contrats des livrables
│   ├── documentaire/        FAQ, politiques, questions pièges
│   ├── mappings/            correspondance des catégories Olist / Rakuten
│   ├── dictionnaire_indicateurs.md
│   ├── ROLES.md             rôles et responsabilités
│   ├── PREMIER_COMMIT.md    guide du premier commit
│   └── GUIDE_DEMARRAGE_EQUIPE.md
├── scripts/                 récupération des données, chargement des sources, migrations, bus, compte Power BI
├── sql/                     migrations PostgreSQL numérotées (quarantaine, staging, entrepôt, vues)
├── src/
│   ├── common/              configuration, accès aux bases, bus d'événements
│   ├── acquisition/         chargement par lots (base boutique, catalogue, fichiers)
│   ├── zone_brute/          lots, manifestes, archivage et rejeu des événements
│   ├── generateur/          générateur d'événements de navigation
│   ├── quality/             règles, contrôle, quarantaine, chargement staging, rapport
│   ├── transformation/      normalisation, déduplication, décodage du texte, langue
│   ├── integration/         correspondance des produits, chargement de l'entrepôt, vérification
│   ├── referentiel/         service référentiel (jours fériés, taux de change)
│   ├── indicateurs/         lecture des indicateurs de ventes
│   ├── compteurs/           compteurs du jour et alerte sur les ventes
│   ├── supervision/         journal des exécutions, retard du flux
│   ├── recherche/           recherche produit (Elasticsearch)
│   ├── documentaire/        FAQ : vérification, indexation, recherche de passages
│   ├── assistant/           assistant à ancrage documentaire, garde-fous, évaluation
│   └── prediction/          modèle de ré-achat, classement, segment à retenir
├── tests/                   un dossier par module de src/
├── .env.example             modèle des variables d'environnement
├── CONVENTIONS.md           conventions de travail de l'équipe
├── docker-compose.yml       les services de la plateforme
├── pyproject.toml           pytest, ruff
├── requirements.txt
├── requirements-dev.txt
└── requirements.lock        versions exactes, appliquées comme contrainte
```

Le dossier `data/` n'existe pas après un clonage : il est exclu du dépôt, et créé par le script de récupération des données.


---

## Démarrer la plateforme

### Prérequis

- **Git**
- **Docker Desktop**, **lancé**. Docker Compose doit être en version 2 ou plus : la commande s'écrit `docker compose`, avec une espace.
- **Environ 4 Go de mémoire vive disponibles.** L'ensemble des services en consomme un peu plus de 3 Go une fois démarré, dont environ 1 Go pour Elasticsearch.
- **Une bonne connexion pour le premier lancement** : les images représentent plusieurs gigaoctets, et le modèle de vecteurs est téléchargé au premier usage de la recherche de passages.

Inutile d'installer PostgreSQL, MongoDB, Kafka ou Elasticsearch, ni une version particulière de Python : tout tourne dans Docker.

### 1. Récupérer le dépôt

```bash
git clone https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI.git
cd Yakaarou_Diaykaat_BI
git checkout develop
```

Le travail en cours se trouve sur `develop`. La branche `main` ne reçoit que les versions stables, en fin de sprint.

### 2. Créer son fichier d'environnement

```bash
cp .env.example .env
```

La commande fonctionne aussi sous PowerShell. Le fichier `.env` est propre à chaque poste et ne doit **jamais** être commité.

### 3. Vérifier que les ports sont libres

Si PostgreSQL ou MongoDB sont déjà installés sur votre ordinateur, ils occupent les ports dont la plateforme a besoin.

Sous **Windows**, dans PowerShell :

```powershell
netstat -ano | findstr ":5432 :27017 :9200 :8080 :29092 :8010"
```

Sous **Linux** ou **macOS** :

```bash
ss -ltn | grep -E ':(5432|27017|9200|8080|29092|8010)\b'
```

Chaque ligne affichée correspond à un port déjà pris. Changez-le **dans votre `.env`**, jamais dans `docker-compose.yml` :

| Port occupé | Ligne à modifier dans `.env` |
|---|---|
| 5432 | `POSTGRES_PORT=5433` |
| 27017 | `MONGO_PORT=27018` |
| 8080 | `AIRFLOW_PORT=8081` |
| 9200 | `ES_PORT=9201` |
| 29092 | `KAFKA_PORT=29093` |
| 8010 | `REFERENTIEL_PORT=8011` (à ajouter dans `.env`) |

Sous Windows, modifiez `.env` avec VS Code plutôt qu'avec une commande PowerShell, qui peut changer l'encodage du fichier.

### 4. Lancer

```bash
docker compose up -d --build
```

Patientez deux à trois minutes, puis :

```bash
docker compose ps
```

| Service | État attendu |
|---|---|
| postgres, mongodb | `healthy` |
| elasticsearch, kafka | `healthy` ou `running` |
| airflow-init | **`exited (0)`** |
| airflow-webserver | `healthy` |
| airflow-scheduler, referentiel, app, api, frontend | `running` |

**`airflow-init` arrêté avec le code 0 est le comportement attendu** : ce service prépare la base d'Airflow puis s'arrête. Le code 0 signifie qu'il a réussi.

### 5. Récupérer les données

Les données ne sont pas dans le dépôt : elles représentent environ 174 Mo. Un script les télécharge depuis l'espace partagé de l'équipe, les range dans la zone brute et vérifie chaque fichier.

```bash
docker compose exec app python scripts/download_data.py
```

Le bilan doit se terminer par **« 10 fichier(s) sur 10 conforme(s) »**. Relancé, le script ne retélécharge rien.

| Option | Effet |
|---|---|
| `--verifier` | vérifie les fichiers présents sans rien télécharger |
| `--forcer` | retélécharge tout, même si tout est conforme |

### 6. Préparer les bases et les sources

À faire une fois, après le premier démarrage. Ces scripts simulent l'existence des systèmes sources de l'e-commerçant ; ils ne font pas partie de la chaîne quotidienne.

```bash
docker compose exec app python scripts/appliquer_sql.py             # migrations SQL
docker compose exec app python scripts/charger_boutique.py          # base source « boutique » (--recharger)
docker compose exec app python scripts/charger_catalogue_mongo.py   # catalogue produits dans MongoDB
docker compose exec app python scripts/creer_sujets.py              # sujets Kafka
docker compose exec app python scripts/alimenter_referentiel.py     # jours fériés et taux de change (en ligne)
docker compose exec app python scripts/creer_compte_lecture.py      # compte en lecture seule pour Power BI
```

Chaque script peut être relancé sans dommage. `alimenter_referentiel.py` est le seul qui exige Internet : ses réponses sont ensuite conservées dans la zone brute.

### 7. Lancer la chaîne quotidienne

Dans Airflow (http://localhost:8080), activez le DAG `quotidien` et lancez-le. Pour dérouler les mêmes étapes à la main :

```bash
docker compose exec app python -m acquisition
docker compose exec app python -m acquisition --source catalogue
docker compose exec app python -m quality.controle --source olist --ingestion <id>
docker compose exec app python -m quality.controle --source catalogue --ingestion <id>
docker compose exec app python -m quality.rapport --seuil 5
docker compose exec app python -m transformation --source olist
docker compose exec app python -m transformation --source rakuten
docker compose exec app python -m recherche.indexer
docker compose exec app python -m integration.correspondance
docker compose exec app python -m integration.chargement
docker compose exec app python -m integration.verifier
```

L'identifiant d'ingestion `<id>` est celui du dossier le plus récent de `data/raw/lots/<source>/`, ou celui que `python -m zone_brute lister` affiche.

La base documentaire de l'assistant ne fait pas partie du DAG. Pour l'alimenter :

```bash
docker compose exec app python -m documentaire.verifier
docker compose exec app python -m documentaire.indexer
```

### 8. Vérifier

```bash
docker compose exec app python -m pytest
```

Tous les tests doivent passer. Les tests marqués `integration` sont ignorés par défaut : ils exigent les services démarrés (PostgreSQL migré, et Elasticsearch pour les passages). Ils se lancent avec `python -m pytest -m integration`. C'est la commande `pytest -m "not integration"` que lance l'intégration continue.

> **Usage local uniquement.** Les ports sont liés à `127.0.0.1`, Elasticsearch tourne sans authentification (`xpack.security.enabled: false`) et les mots de passe de `.env.example` sont des valeurs de démonstration. Ne pas déployer cette configuration telle quelle sur un serveur.

### Accès aux services

| Service | Adresse par défaut |
|---|---|
| Airflow | http://localhost:8080 — identifiant `admin`, mot de passe `changeme_en_local` |
| Elasticsearch | http://localhost:9200 |
| PostgreSQL | `localhost:5432` — utilisateur `dataflow`, base `dataflow360` |
| MongoDB | `localhost:27017` |
| Kafka | `localhost:29092` |
| Service référentiel | http://localhost:8010 |
| API de démonstration | http://localhost:8001 — documentation interactive sur `/docs` |
| Application web | http://localhost:5173 — vue générale, recherche, assistant |

Au premier démarrage, le service `frontend` installe ses dépendances : comptez une à deux minutes avant que l'application réponde. **Le port 5173 n'est pas un détail** : c'est la seule origine autorisée par le CORS de l'API (`src/api/main.py`). En changer impose d'ajouter la nouvelle origine à `allow_origins`.

Si vous avez changé un port dans `.env`, utilisez le vôtre. Les identifiants sont ceux de votre fichier `.env`. Power BI se connecte à PostgreSQL avec le compte de lecture `POWERBI_UTILISATEUR`, dont le mot de passe est `POWERBI_MOTDEPASSE`.

### Arrêter

```bash
docker compose down        # arrête les services, conserve les données
docker compose down -v     # arrête et EFFACE toutes les bases
```

---

## Problèmes fréquents

Toutes ces pannes ont été rencontrées par l'équipe pendant la mise en place.

**`failed to connect to the docker API` ou `dockerDesktopLinuxEngine` introuvable.**
Docker Desktop n'est pas lancé. Ouvrez-le et attendez que son statut indique *Engine running* avant de relancer la commande. La commande `docker version` doit afficher une section `Client` **et** une section `Server`.

**`address already in use` ou `port is already allocated`.**
Un autre programme utilise le port, souvent un PostgreSQL ou un MongoDB installé localement. Changez le port dans `.env`, étape 3.

**`airflow-init` ne se termine jamais ; ses journaux mentionnent `database "airflow" does not exist`.**
La base d'Airflow n'a pas été créée au premier démarrage. Le script de création ne s'exécute que sur une base vide :
```bash
docker compose down -v
docker compose up -d
```

**`Permission non accordée` en écrivant dans `scripts/`, `data/` ou `docker/postgres/` — Linux uniquement.**
Docker a créé le dossier lui-même, en tant qu'administrateur. Reprenez-en la propriété :
```bash
sudo chown -R $USER:$USER <dossier>
```

**`.env.example` introuvable.**
Vérifiez que vous êtes sur `develop` : le fichier n'existe pas sur `main`. S'il a été téléchargé séparément, il a pu perdre son point et s'appeler `env.example` : renommez-le.

**`docker-compose` renvoie une erreur sur le fichier.**
C'est l'ancienne version de l'outil. Utilisez `docker compose`, avec une espace.

**Elasticsearch s'arrête juste après son démarrage, journaux mentionnant `vm.max_map_count`.**
Un réglage système doit être augmenté sur la machine hôte. La procédure est décrite dans la documentation officielle d'Elasticsearch, section *Install Elasticsearch with Docker*.

**L'assistant ou `documentaire.indexer` échoue en parlant d'Elasticsearch.**
L'assistant utilise la recherche vectorielle par défaut : Elasticsearch doit être démarré et les passages indexés (`python -m documentaire.indexer`). Pour travailler hors ligne, lancez-le avec `ASSISTANT_RETROUVEUR=depannage`.

Pour afficher les journaux d'un service : `docker compose logs --tail 30 <service>`.

---

## Contribuer

Chaque contribution passe par une branche partant de `develop`, puis par une demande de fusion approuvée par un autre membre. Les branches `main` et `develop` sont protégées : aucun envoi direct n'y est possible. L'intégration continue vérifie le formatage et l'analyse statique (ruff), puis lance les tests qui n'ont besoin d'aucun service.

Nommage des branches, messages de commit, demandes de fusion et définition de terminé : voir [`CONVENTIONS.md`](CONVENTIONS.md).

---

## Documentation

| Document | Contenu |
|---|---|
| [`CONVENTIONS.md`](CONVENTIONS.md) | Branches, messages de commit, demandes de fusion, définition de terminé |
| [`docs/ROLES.md`](docs/ROLES.md) | Rôles, responsabilités, décisions et suppléances |
| [`docs/dictionnaire_indicateurs.md`](docs/dictionnaire_indicateurs.md) | Définition de chaque indicateur affiché, par sprint |
| [`docs/contrats/`](docs/contrats/) | Contrats des livrables : événements, zone brute, quarantaine, entrepôt, correspondance, recherche, référentiel, workflow, modèle, FAQ, passages, assistant |
| [`docs/documentaire/`](docs/documentaire/) | Foire aux questions, politiques, questions pièges |
| [`docs/captures/`](docs/captures/) | Captures du tableau de bord, pour qui n'a pas Power BI Desktop |
| [`docs/GUIDE_DEMARRAGE_EQUIPE.md`](docs/GUIDE_DEMARRAGE_EQUIPE.md) | Mise à jour des postes et vérification croisée du Sprint 0 |
| [`docs/PREMIER_COMMIT.md`](docs/PREMIER_COMMIT.md) | Guide du premier commit de chaque membre |

Plusieurs modules ont leur propre `README.md` : `src/acquisition/`, `src/common/`, `src/generateur/`, `src/transformation/`.

---

## Avancement

| Sprint | Objectif | État |
|---|---|---|
| Sprint 0 | Organisation et préparation | Terminé |
| Sprint 1 | Acquisition et stockage brut | Terminé |
| Sprint 2 | Qualité et transformation | Terminé |
| Sprint 3 | Intégration, entrepôt et premiers indicateurs | Terminé |
| Sprint 4 | Temps réel, recherche et supervision | Terminé (tag `v0.5`) |
| Sprint 5 | Intelligence artificielle et finalisation | En cours — voir « Reste à faire pour clore le Sprint 5 » (jeu gelé, seuils et taux d'ancrage faits) |

---

## Sources des données

- **Commandes, clients, paiements, livraisons et avis** — Brazilian E-Commerce Public Dataset by Olist, [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- **Catalogue produits** — Rakuten France Multimodal Product Data Classification, Rakuten Institute of Technology, [Challenge Data ENS](https://challengedata.ens.fr/challenges/35). Les fichiers de fiches et de catégories ont été fusionnés par l'équipe en un fichier unique.
- **Jours fériés et taux de change** — services publics gratuits, interrogés une fois puis conservés dans la zone brute
- **Événements de navigation** — générés par l'équipe
- **Base documentaire de support** — rédigée par l'équipe
