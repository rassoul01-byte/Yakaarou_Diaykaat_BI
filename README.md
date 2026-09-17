# 🛒 Yakaarou Diaykaat BI — DataFlow360 (Groupe 2)
### Conception et Réalisation d'une Plateforme Data & IA Complète pour l'E-Commerce & le Retail
**Formation Dev Data — Projet Transversal de Consolidation du Tronc Commun**

---

## 📑 Sommaire
1. [Présentation et Finalité Pédagogique du Projet](#1-présentation-et-finalité-pédagogique-du-projet)
2. [Contexte et Problématique Métier](#2-contexte-et-problématique-métier)
3. [Besoins Métier & Objectifs Stratégiques](#3-besoins-métier--objectifs-stratégiques)
4. [Inventaire Exhaustif des Sources de Données & Volumétrie](#4-inventaire-exhaustif-des-sources-de-données--volumétrie)
5. [Analyse Approfondie des Sources, Contraintes & Décisions Clés](#5-analyse-approfondie-des-sources-contraintes--décisions-clés)
6. [Défauts Réels Mesurés & Stratégie Qualité des Données](#6-défauts-réels-mesurés--stratégie-qualité-des-données)
7. [Cycle de Vie des Données (9 Étapes)](#7-cycle-de-vie-des-données-9-étapes)
8. [Architecture Globale & Les 3 Circuits de Données](#8-architecture-globale--les-3-circuits-de-données)
9. [Choix Technologiques Justifiés & Alternatives Comparées](#9-choix-technologiques-justifiés--alternatives-comparées)
10. [Référentiel Fonctionnel Complet (44 Fonctionnalités : F1.1 à F6.5)](#10-référentiel-fonctionnel-complet-44-fonctionnalités--f11-à-f65)
11. [Organisation de l'Équipe & Matrice des Responsabilités](#11-organisation-de-léquipe--matrice-des-responsabilités)
12. [Règles de Fonctionnement de l'Équipe](#12-règles-de-fonctionnement-de-léquipe)
13. [Backlog Priorisé & Chaînes de Dépendances Critiques](#13-backlog-priorisé--chaînes-de-dépendances-critiques)
14. [Matrice d'Analyse des Risques & Mesures Prévoyantes](#14-matrice-danalyse-des-risques--mesures-prévoyantes)
15. [Planning Opérationnel des Sprints (S0 à S5)](#15-planning-opérationnel-des-sprints-s0-à-s5)
16. [Structure Complète du Répertoire Git](#16-structure-complète-du-répertoire-git)
17. [Guide de Démarrage Rapide & Exploitation Locale](#17-guide-de-démarrage-rapide--exploitation-locale)

---

## 1. Présentation et Finalité Pédagogique du Projet

**DataFlow360** est le projet transversal de consolidation des acquis du tronc commun de la formation **Dev Data**[cite: 2]. Il mobilise l'ensemble des compétences développées en Python, manipulation et stockage des données (relationnelles et NoSQL), traitement batch et streaming, qualité des données, Data Warehouse, Business Intelligence, indexation lexicale, Machine Learning, Intelligence Artificielle, conteneurisation Docker et intégration continue CI/CD[cite: 2].

### Démarche directrice
Une technologie ne doit jamais être intégrée au projet simplement parce qu'elle figure au programme pédagogique ; chaque brique doit répondre à un besoin identifié et être techniquement justifiée[cite: 2] :
$$\text{Domaine} \longrightarrow \text{Problème} \longrightarrow \text{Besoin} \longrightarrow \text{Données} \longrightarrow \text{Contraintes} \longrightarrow \text{Solutions possibles} \longrightarrow \text{Choix \& Justification} \longrightarrow \text{Architecture} \longrightarrow \text{Réalisation} \longrightarrow \text{Exploitation} \text{[cite: 2, 4]}$$

L'objectif final est de démontrer la maîtrise d'une chaîne Data d'entreprise complète et cohérente de bout en bout[cite: 2].

---

## 2. Contexte et Problématique Métier

Le projet est développé pour le compte d'une **entreprise e-commerce en pleine croissance** sur le secteur Retail. Cette entreprise produit ses données dans des systèmes séparés et de qualité inégale. Faute d'une vue consolidée et fiable, elle subit quatre difficultés majeures :
1. **Pilotage avec plusieurs jours de retard :** Faute de centralisation, l'évaluation de l'activité commerciale se fait avec un décalage pénalisant.
2. **Départ non compris des clients (Churn) :** L'entreprise constate la perte de clients sans en comprendre les ressorts ni pouvoir anticiper les départs.
3. **Échecs fréquents dans la recherche produit :** Les données du catalogue comportent des scories qui empêchent les acheteurs de trouver les produits recherchés.
4. **Saturation du service client :** Les équipes support traitent manuellement un volume excessif de requêtes récurrentes et répétitives.

### La Solution
Mettre en place la **plateforme Data & IA unifiée de l'e-commerçant** : un système qui collecte les données dispersées (commandes, catalogue, clics, avis), en contrôle la qualité, les consolide dans un référentiel unique et fiable, puis les valorise à travers 4 cas d'usage métiers : un pilotage en quasi temps réel, l'anticipation du churn/ré-achat, une recherche produit pertinente et un assistant support automatisé.

---

## 3. Besoins Métier & Objectifs Stratégiques

* **Besoin 1 — Référentiel unique, contrôlé et fiable :** Collecter, assainir, valider et unifier l'ensemble des sources dans un schéma dimensionnel en étoile certifié.
* **Besoin 2 — Pilotage en quasi temps réel :** Donner une visibilité immédiate sur les ventes, le chiffre d'affaires, le panier moyen et le taux de conversion, avec alertes automatiques en cas d'anomalie.
* **Besoin 3 — Comprendre et anticiper le départ des clients :** Prédire la probabilité de ré-achat afin d'isoler la population d'acheteurs sur laquelle une action de rétention est rentable.
* **Besoin 4 — Recherche produit pertinente :** Disposer d'un moteur tolérant aux fautes d'orthographe, insensible aux accents et filtrable par facettes (catégories, prix).
* **Besoin 5 — Réduire la charge du service client :** Déployer un assistant conversationnel RAG contraint par une base documentaire interne certifiée (FAQ et fiches produits) pour garantir des réponses fiables et sans hallucination.
* **Besoin Transverse — Industrialisation et Exploitation :** Orchestrer les pipelines quotidiens sous Airflow, superviser les flux, tester automatiquement les contributions et démarrer la plateforme en une seule commande via Docker.

---

## 4. Inventaire Exhaustif des Sources de Données & Volumétrie

L'ensemble des sources représente **environ 174 Mo** (121 Mo pour les commandes et 53 Mo pour le catalogue produits). Cette taille reste compatible avec l'exécution sur des postes de travail mais **interdit formellement le versionnement des données brutes dans le dépôt Git**, qui n'accueille que le code et les scripts de récupération.

| Données | Provenance | Format | Fréquence de production | Volume mesuré | Structure | Niveau de qualité constaté |
|---|---|---|---|---|---|---|
| **Commandes et articles** | Jeu public Olist (Kaggle) | CSV | Statique (Rejeu chronologique accéléré) | 99 441 commandes, 112 650 lignes d'articles | Structuré, tabulaire, relations par clés | **Bonne.** 2 965 dates de livraison manquantes (3,0 %) ; 775 commandes sans aucune ligne d'article. |
| **Paiements** | Jeu public Olist (Kaggle) | CSV | Statique (Chargement unique) | 103 886 lignes de paiement | Structuré : moyen de paiement, mensualités, montant | **Bonne.** 2 961 commandes réglées en plusieurs paiements (à agréger avant jointure). |
| **Clients et géolocalisation** | Jeu public Olist (Kaggle) | CSV | Statique (Chargement unique) | 99 441 lignes clients (96 096 personnes) ; 1 000 163 géolocalisations | Structuré, tabulaire | **Faible sur géolocalisation :** 261 831 lignes strictement dupliquées (26,2 %). Deux identifiants clients à distinguer. |
| **Produits et catégories** | Jeu public Olist (Kaggle) | CSV | Statique (Chargement unique) | 32 951 produits, 73 catégories | Structuré : catégorie, dimensions, nombre de photos | **Bonne.** 610 produits sans catégorie (1,9 %). |
| **Avis clients** | Jeu public Olist (Kaggle) | CSV | Statique (Rejeu avec les commandes) | 99 224 avis (dont 40 977 avec texte, soit 41,3 %) | Semi-structuré : champs fixes et texte libre | **Hétérogène.** 814 identifiants dupliqués, 547 multi-avis, rédigés en portugais. |
| **Catalogue produits** | Rakuten France (SIGIR eCom 2020) | CSV | Statique (Fichier unique reconstitué) | 84 916 fiches, 27 catégories, 53 Mo | Semi-structuré, 6 colonnes | **Moyenne.** 35,1 % sans description ; 63,6 % d'entités HTML ; 62 % en français. |
| **Événements navigation** | Générateur interne (Python/Faker) | JSON | Continu, au fil de l'eau | ≈ 10 000 à 50 000 événements par jour simulé | Semi-structuré : session, page vue, requête, ajout panier | **Maîtrisée.** Défauts injectés volontairement pour tester la chaîne qualité. |
| **Base support (FAQ)** | Rédigée par l'équipe | Markdown ou JSON | Statique, révisions ponctuelles | 30 à 50 questions-réponses sur 5 thèmes | Non structuré : texte libre organisé par thème | **Maîtrisée.** Couverture volontairement limitée au périmètre défini. |
| **Table correspondance** | Construite par l'équipe | CSV | Construction unique, révisions | 32 951 produits vendus rapprochés du catalogue | Structuré : ID produit, ID fiche, catégorie | **Appariement partiel assumé :** Rapprochement par affinité de catégorie. |

---

## 5. Analyse Approfondie des Sources, Contraintes & Décisions Clés

### 5.1 Préparation des fichiers Rakuten
* **Fichier test écarté (13 812 fiches) :** Dépourvu d'étiquettes de catégories (utilisé pour l'évaluation du challenge d'origine), l'intégrer aurait injecté 13 812 produits orphelins sans classification.
* **Images exclues :** Le dossier d'images volumineux a été écarté car aucun des 5 besoins n'exploite la vision par ordinateur, ménageant ainsi la mémoire vive.
* **Fusion préalable :** Les deux fichiers d'entraînement (fiches et catégories) ont été fusionnés sur leur index commun (0 à 84 915, vérifié sans perte ni doublon) pour éviter les dissociations.
* **Conservation brute :** Aucun nettoyage n'a été fait à la fusion (balises HTML conservées) pour respecter le rôle de la zone brute immuable.

### 5.2 Faible taux de ré-achat (Olist) et reformulation ML
* **Constat mesuré :** Sur 96 096 personnes distinctes, **93 099 n'ont passé qu'une commande (96,88 %)**. Seules 2 997 personnes (3,12 %) ont commandé au moins deux fois.
* **Décision ML :** Prédire un départ au sens classique n'aurait pas de sens car la quasi-totalité des clients sont mono-acheteurs. La cible est reformulée : **prédire la probabilité qu'un client effectue un nouvel achat**.
* **Traitement du déséquilibre (97/3) :** Traitement par rééchantillonnage de la population d'entraînement et évaluation sur métriques adaptées (PR-AUC, F1-score) plutôt que l'exactitude brute.

### 5.3 Deux identifiants clients aux portées distinctes
* `customer_id` : Clé de commande régénérée à chaque achat (99 441 valeurs).
* `customer_unique_id` : Identifiant réel de la personne (96 096 valeurs).
* **Règle absolue :** Toute agrégation par client (RFM, rétention, historique) s'effectue exclusivement sur l'identifiant de personne (`customer_unique_id`) pour éviter d'écraser le comportement d'achat.

### 5.4 Langues et particularités textuelles
* **Avis Olist :** Rédigés en portugais ; 58,7 % n'ont pas de texte. L'analyse de sentiment s'effectue avec un modèle multilingue sur les 40 977 avis rédigés.
* **Catalogue Rakuten :** Détection de langue sur 3 000 désignations : 62 % français, 22 % anglais, 6,5 % allemand. L'ensemble est conservé (place de marché réaliste), la langue devient un attribut enrichi et plus de 50 000 fiches restent nativement en français.
* **Balises HTML :** 63,6 % des descriptions comportent des entités HTML et 28,4 % des balises. Un décodage strict est positionné en amont de l'indexation.

### 5.5 Table de réconciliation produits
Olist et Rakuten n'ayant aucune clé commune, le rapprochement est opéré par affinité de catégorie entre les 73 catégories d'articles vendus et les 27 catégories du catalogue. Les articles sans catégorie compatible sont affectés à « inconnu » pour ne pas altérer les volumes de vente.

---

## 6. Défauts Réels Mesurés & Stratégie Qualité des Données

Les défauts mesurés constituent la base du contrat de données Great Expectations :

| Défaut constaté sur les données | Mesure exacte | Règle de qualité appliquée |
|---|---|---|
| **Lignes géolocalisation dupliquées** | 261 831 sur 1 000 163 (26,2 %) | Déduplication sur l'intégralité de la ligne avant chargement, avec comptage des lignes supprimées. |
| **Identifiants d'avis dupliqués** | 814 identifiants | Règle d'unicité : conservation d'un enregistrement unique, mise en quarantaine documentée des doublons. |
| **Commandes avec plusieurs avis** | 547 commandes | Règle de granularité : un seul avis conservé par commande, les autres tracés en quarantaine. |
| **Commandes sans ligne d'article** | 775 commandes | Marquage et exclusion du calcul du CA (une commande sans article pèse zéro). |
| **Paiements multiples par commande** | 2 961 commandes | Agrégation des paiements par commande avant jointure pour éviter la duplication des montants. |
| **Produits sans catégorie** | 610 sur 32 951 (1,9 %) | Rattachement à une catégorie « inconnu » (aucune suppression destructrice). |
| **Dates de livraison manquantes** | 2 965 sur 99 441 (3,0 %) | Complétude conditionnelle : date requise uniquement si le statut de commande vaut « livrée ». |
| **Avis sans texte** | 58 247 sur 99 224 (58,7 %) | Aucun rejet : absence admise, la note quantitative reste exploitée. |
| **Dualité identifiants clients** | 99 441 vs 96 096 | Agrégation client strictement réalisée sur l'identifiant personne. |
| **Entités & balises HTML catalogue** | 63,6 % entités, 28,4 % balises | Décodage des entités et suppression des balises avant indexation Elasticsearch. |
| **Fiches catalogue sans description** | 29 800 sur 84 916 (35,1 %) | Tolérance : la désignation suffit à l'indexation, la description est un enrichissement. |
| **Libellés produits identiques** | 2 651 doublons | Conservation des identifiants uniques ; tracé pour l'analyse de pertinence de la recherche. |
| **Catalogue multilingue** | 62 % FR, 22 % EN, 6,5 % DE (échantillon 3k) | Détection de langue à l'enrichissement et stockage comme attribut sans filtrage destructif. |

---

## 7. Cycle de Vie des Données (9 Étapes)

Le parcours de la donnée se déroule selon 9 étapes coordonnées :
```text
Sources ──► Acquisition ──► Stockage brut ──► Contrôle qualité ──► Transformation ──► Intégration ──► Stockage analytique ──► Analyse/Recherche/IA ──► Visualisation/Action


┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   SOURCES DE DONNÉES                                   │
│    (Fichiers Olist CSV, Catalogue Rakuten CSV, Flux Navigation JSON, Base Support)     │
└───────────────────┬───────────────────┬────────────────────────────────┬───────────────┘
                    │                   │                                │
      [CIRCUIT A : PAR LOTS]  [CIRCUIT B : CONTINU / STREAM]   [CIRCUIT C : DOCUMENTAIRE]
                    │                   │                                │
                    ▼                   ▼                                ▼
               Zone Brute          Apache Kafka                  Catalogue Nettoyé
            (Fichier/MongoDB)   (Bus d'Événements)                 + Base Support
                    │                   │                                │
                    ▼                   ▼                                ▼
            Contrôle Qualité      Consommateurs                 Indexation Lexicale
          (Great Expectations) (Compteurs Journaliers)         (Elasticsearch Moteur)
                    │                   │                                │
           [Rejets Quarantaine]         ▼                                ▼
                    │             Alertes Chutes               Indexation Vectorielle
                    ▼             & Taux Conversion             (Assistant RAG Support)
             Transformations            │                                │
              & Déduplication           │                                │
                    │                   │                                │
                    ▼                   │                                │
           Schéma en Étoile ◄───────────┘                                │
             (PostgreSQL)                                                │
                    │                                                    │
     ┌──────────────┴──────────────┐                                     │
     ▼                             ▼                                     ▼
Tableaux de Bord            Modèle Rétention                     Recherche Floue
Power BI (Ventes/CA)      (Scikit-learn - ML)                 & Support Conversationnel

┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Ndeye Penda SARR (NPS)                                 │
│                   Coordination générale, Gestion Trello, Airflow & BI                  │
└───────────────────┬──────────────────────┬──────────────────────┬──────────────────────┘
                    │                      │                      │
                    ▼                      ▼                      ▼
          ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
          │  Mouhameth DIOP  │   │   Seydina WADE   │   │  Aissata DIALLO  │
          │       (MD)       │   │       (SW)       │   │       (AD)       │
          │  Acquisition &   │   │  Stockage, Docker│   │ Transformation,  │
          │  Streaming Kafka │   │  & Qualité Data  │   │ Schéma en étoile │
          └──────────────────┘   └──────────────────┘   └──────────────────┘
                                           │
                                           ▼
                                 ┌──────────────────┐
                                 │   Bachir DEME    │
                                 │       (BD)       │
                                 │  Elasticsearch,  │
                                 │  ML & RAG Support│
                                 └──────────────────┘

Yakaarou_Diaykaat_BI/
├── .github/
│   └── workflows/
│       └── ci.yml                     # Tests automatisés GitHub Actions
├── config/                            # Fichiers de configuration des services
│   ├── airflow/                       # Profils du scheduler Airflow
│   ├── elasticsearch/                 # Mappings d'indexation
│   ├── kafka/                         # Paramètres du bus et topics
│   └── postgres/                      # Scripts DDL (zones brutes et modèle en étoile)
├── dags/                              # DAGs d'orchestration Airflow (NPS)
│   ├── dag_batch_daily_pipeline.py    # Pipeline quotidien par lots
│   └── dag_reindex_catalogue.py       # Réindexation périodique du catalogue
├── data/                              # DONNÉES LOCALES (STRICTEMENT EXCLU DU DÉPÔT GIT)
│   ├── raw/                           # Données brutes immuables
│   ├── processed/                     # Données nettoyées et réconciliées
│   └── quarantine/                    # Rejets tracés par les règles qualité
├── docker/                            # Fichiers Dockerfile personnalisés
├── docs/                              # Documentation technique et livrables de conception
│   ├── architecture/                  # Schémas détaillés des circuits
│   ├── conception/                    # Dossier complet de Partie 2
│   └── dictionnaire_indicateurs.md    # Définition métier et calculs des KPI
├── notebooks/                         # Notebooks d'exploration (outputs purgés)
├── scripts/                           # Scripts utilitaires
│   ├── download_data.py               # Script de téléchargement des jeux Olist et Rakuten
│   └── init_db.sql                    # Initialisation des bases relationnelles
├── src/                               # Code source de la plateforme
│   ├── acquisition/                   # Ingestion batch et générateur Faker (MD)
│   ├── streaming/                     # Producers et consumers Kafka (MD)
│   ├── quality/                       # Règles Great Expectations et quarantaine (SW)
│   ├── transformation/                # Pipelines de nettoyage, HTML, correspondance (AD)
│   ├── search/                        # Moteur Elasticsearch et journal requêtes (BD)
│   └── ml_ia/                         # Modèle de ré-achat et assistant RAG (BD)
├── tests/                             # Suites de tests automatisés (Pytest)
├── .env.example                       # Modèle des variables d'environnement
├── .gitignore                         # Fichiers exclus du versionnement
├── CONTRIBUTING.md                    # Conventions de travail et workflow Git
├── docker-compose.yml                 # Orchestration des services conteneurisés
├── README.md                          # Ce document
└── requirements.txt                   # Dépendances Python

git clone [https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI.git](https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI.git)
cd Yakaarou_Diaykaat_BI
git checkout develop

cp .env.example .env
# Compléter les identifiants si nécessaire

docker-compose up -d
docker-compose ps

python scripts/download_data.py
