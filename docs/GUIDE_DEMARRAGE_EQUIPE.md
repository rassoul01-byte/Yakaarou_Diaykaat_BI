# Mettre son poste à jour et faire tourner la plateforme

**GROUPE 2 · DataFlow360**
**Sprint 0 clôturé — étiquette `v0.1` · Sprint 1 en cours**

Ce guide sert à deux choses : remettre un poste au niveau de `develop`, et réaliser la **vérification croisée** de fin de sprint. Un sprint n'est terminé que lorsque les cinq membres obtiennent le même résultat, chacun sur sa propre machine.

Il est mis à jour à chaque sprint : la section 1 dit ce que contient `develop`, la section 10 garde la trace des vérifications.

---

## 1. Ce que contient `develop`

Tout le travail en cours est sur **`develop`**, qui est la branche par défaut du dépôt. `main` ne reçoit `develop` qu'à la clôture d'un sprint, avec une étiquette de version.

### Sprint 0 — organisation et préparation, étiquette `v0.1`

| Élément | Où | Apporté par |
|---|---|---|
| Exclusion du dossier `data/` | `.gitignore` | Seydina |
| Conventions de travail | `CONVENTIONS.md` | Seydina |
| Socle Python : dépendances, configuration des tests, premiers tests | `requirements*.txt`, `pyproject.toml`, `src/common/`, `tests/` | Ndeye Penda |
| Image du conteneur de travail | `docker/app/Dockerfile` | Ndeye Penda |
| Composition des six services | `docker-compose.yml`, `.env.example` | Bachir |
| Création des bases et des schémas | `docker/postgres/init/01-databases.sql` | Bachir |
| Script de récupération des données | `scripts/download_data.py` | Bachir |
| Rôles, schéma d'architecture, ce guide | `docs/` | Ndeye Penda |
| Description du projet | `README.md` | Aissata |

### Sprint 1 — acquisition et stockage brut, en cours

| Élément | Où | Apporté par |
|---|---|---|
| Contrat d'événement et bus Kafka | `docs/contrats/evenements.md`, `src/common/`, `scripts/creer_sujets.py`, `scripts/etat_bus.py` | Ndeye Penda |
| Générateur d'événements de navigation | `src/generateur/` | Bachir |
| Zone brute : archivage, vérification, rejeu | `docs/contrats/zone_brute.md`, `src/zone_brute/` | Aissata |
| Zones de stockage et migrations SQL | `docs/contrats/zones_stockage.md`, `sql/`, `scripts/appliquer_sql.py` | Seydina |
| Chargement par lots des commandes et du catalogue | `src/acquisition/` | Mouhameth |

Deux règles sont **appliquées par GitHub**, et non plus seulement écrites : personne ne pousse directement sur `main` ni sur `develop`, et toute demande de fusion exige l'approbation d'un autre membre.

---

## 2. Prérequis

- **Git**
- **Docker Desktop, lancé.** Ouvrir l'application et attendre que son statut indique *Engine running*. Vérifier avec `docker version` : la sortie doit contenir une section `Client` **et** une section `Server`.
- **Environ 4 Go de mémoire vive disponibles.** Relevé réel sur le poste de Ndeye Penda : **3,1 Go** pour les sept conteneurs, dont un peu plus de 1 Go pour Elasticsearch et 0,9 Go pour le serveur web d'Airflow. Les 4 Go laissent une marge.
- **Une bonne connexion pour le premier lancement** : les images des six services représentent plusieurs gigaoctets. Elles restent ensuite sur le poste.

Inutile d'installer PostgreSQL, MongoDB, Kafka ou Elasticsearch : tout tourne dans Docker. Et la version de Python installée sur votre poste n'a pas d'importance, le conteneur utilise la sienne.

---

## 3. Récupérer le dépôt

### Cas A — Tu as déjà cloné le dépôt

C'est le cas de la plupart d'entre vous. Depuis le dossier du dépôt :

```bash
git remote -v
```

✅ L'adresse doit être `https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI.git`. 🛑 Si rien ne s'affiche, ce dossier n'est pas relié au dépôt : passe au **cas B**.

```bash
git status
```

✅ *« rien à valider, la copie de travail est propre »*. 🛑 Si des fichiers modifiés apparaissent et que tu veux les garder, crée d'abord une branche pour eux : `git checkout -b chore/S0-mon-travail-en-cours`, puis `git add` et `git commit`.

Puis la mise à jour :

```bash
git checkout develop
git pull
git fetch --prune
```

`git fetch --prune` fait disparaître de ta copie les branches supprimées sur GitHub. Tu peux ensuite supprimer tes propres branches locales déjà fusionnées avec `git branch -d <nom>` : Git refuse de supprimer une branche dont le contenu n'est pas dans `develop`, donc aucun risque de perte.

### Cas B — Clone neuf

Pour un poste qui n'a jamais eu le dépôt, ou une copie trop abîmée pour être réparée :

```bash
git clone https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI.git
cd Yakaarou_Diaykaat_BI
git checkout develop
```

`develop` étant la branche par défaut du dépôt, un clone s'ouvre directement dessus : la dernière commande ne fait que le confirmer.

Si un dossier du même nom existe déjà, ajoute un nom à la fin de la première commande, par exemple `… .git dataflow360`, puis `cd dataflow360`.

### Vérifier que tout est arrivé

```bash
git log --oneline -5
```

✅ Les derniers commits correspondent aux demandes de fusion les plus récentes du sprint en cours.

---

## 4. Configurer son poste

### Créer son fichier d'environnement

```bash
cp .env.example .env
```

`cp` fonctionne aussi sous PowerShell. Le fichier `.env` est propre à ton poste et **ne doit jamais être commité** — il est exclu par le `.gitignore`.

⚠️ Si `.env.example` est introuvable, vérifie que tu es bien sur `develop` : il n'existe pas sur `main`.

### Vérifier que les ports sont libres

Si PostgreSQL ou MongoDB sont déjà installés sur ton poste pour un autre cours, ils occupent les ports dont la plateforme a besoin. C'est arrivé chez Bachir pour les deux, et chez Ndeye Penda pour PostgreSQL.

Sous **Windows**, dans PowerShell :

```powershell
netstat -ano | findstr ":5432 :27017 :9200 :8080 :29092"
```

Sous **Linux** :

```bash
ss -ltn | grep -E ':(5432|27017|9200|8080|29092)\b'
```

Chaque ligne affichée est un port déjà pris. Change-le **dans ton `.env`**, jamais dans `docker-compose.yml` :

| Port occupé | Ligne à modifier dans `.env` |
|---|---|
| 5432 | `POSTGRES_PORT=5433` |
| 27017 | `MONGO_PORT=27018` |
| 8080 | `AIRFLOW_PORT=8081` |
| 9200 | `ES_PORT=9201` |
| 29092 | `KAFKA_PORT=29093` |

Sous Windows, modifie `.env` avec VS Code (`code .env`) plutôt qu'avec une commande PowerShell, qui peut changer l'encodage du fichier.

Ce changement ne touche que l'accès depuis ton ordinateur. À l'intérieur de Docker, les services continuent de se parler sur leurs ports d'origine.

---

## 5. Lancer la plateforme

```bash
docker compose up -d --build
```

Attends deux à trois minutes, puis :

```bash
docker compose ps
```

✅ Ce que tu dois voir :

| Service | État attendu |
|---|---|
| postgres, mongodb | `healthy` |
| elasticsearch, kafka | `healthy` ou `running` |
| airflow-init | **`exited (0)`** |
| airflow-webserver | `healthy` |
| airflow-scheduler, app | `running` |

⚠️ **`airflow-init` arrêté avec le code 0, c'est normal.** Il prépare la base d'Airflow puis s'arrête. Le code 0 signifie qu'il a réussi.

---

## 6. Vérifier que tout fonctionne

```bash
docker compose exec postgres psql -U dataflow -d dataflow360 -c "\l"
docker compose exec postgres psql -U dataflow -d dataflow360 -c "\dn"
```

✅ La première liste contient une base **`airflow`**. La seconde montre les schémas du projet : la zone intermédiaire, l'entrepôt et la quarantaine.

```bash
docker compose exec app python -m pytest
```

✅ **Aucun échec.** Le nombre de tests augmente à chaque sprint : note-le au moment de ta vérification, il fait partie de ta ligne du tableau.

Les tests qui ont besoin des services démarrés sont ignorés par défaut. Pour les lancer :

```bash
docker compose exec app python -m pytest -m integration
```

Dans ton navigateur, en adaptant le port si tu l'as changé :
- http://localhost:9200 → Elasticsearch affiche son numéro de version ;
- http://localhost:8080 → Airflow, identifiant `admin`, mot de passe `changeme_en_local`.

---

## 7. Récupérer les données

```bash
docker compose exec app python scripts/download_data.py
```

✅ Le téléchargement de l'archive Olist et du catalogue Rakuten, puis **« 10 fichier(s) sur 10 conforme(s) »**. Les fichiers apparaissent dans `data/sources/` sur ton poste.

Relance la commande une seconde fois : ✅ *« rien à télécharger »*.

Enfin :

```bash
git status
```

✅ **`data/` ne doit pas apparaître.** C'est la preuve que les 174 Mo de données ne partiront jamais sur GitHub.

Et pour relever la mémoire consommée, à reporter dans le tableau de la section 11 :

```bash
docker stats --no-stream
```

---

## 8. Les commandes ajoutées par le Sprint 1

Une fois la plateforme démarrée et les données récupérées, ces commandes mettent en marche ce que le Sprint 1 a construit. Les options exactes de chacune sont décrites dans les contrats et les README de `docs/` et de `src/`.

| Étape | Commande | Ce qu'elle fait | À lire |
|---|---|---|---|
| Préparer les zones de stockage | `docker compose exec app python scripts/appliquer_sql.py` | Applique les migrations qui n'ont pas encore été passées, sans effacer les données | `docs/contrats/zones_stockage.md` |
| Créer les sujets du bus | `docker compose exec app python scripts/creer_sujets.py` | Crée les sujets Kafka du contrat ; sans effet s'ils existent déjà | `docs/contrats/evenements.md` |
| Produire des événements | `docker compose exec app python -m generateur …` | Simule le trafic du site et publie sur le bus | `src/generateur/README.md` |
| Regarder le bus | `docker compose exec app python scripts/etat_bus.py` | Sujets, nombre de messages, retard de chaque lecteur | `docs/contrats/evenements.md` |
| Alimenter et vérifier la zone brute | `docker compose exec app python -m zone_brute …` | Archive les événements, vérifie les empreintes, rejoue une période | `docs/contrats/zone_brute.md` |
| Charger les fichiers sources | `docker compose exec app python -m acquisition …` | Dépose commandes et catalogue dans la zone brute, avec leur manifeste | contrat de la zone brute |

⚠️ **Ces commandes s'enchaînent dans cet ordre.** Créer les sujets avant de lancer le générateur, et appliquer les migrations avant d'attendre quoi que ce soit des zones de stockage.

---

## 9. Les pannes rencontrées, et leur solution

Toutes ces pannes sont réellement arrivées pendant la mise en place. Si l'une d'elles t'arrive, la solution est connue.

| Symptôme | Cause | Solution |
|---|---|---|
| `failed to connect to the docker API` ou `dockerDesktopLinuxEngine` introuvable | Docker Desktop n'est pas lancé | Ouvrir Docker Desktop, attendre *Engine running*, puis relancer |
| `address already in use` ou `port is already allocated` | Un autre programme utilise le port | Changer le port dans `.env`, section 4 |
| `airflow-init` qui ne se termine jamais ; journaux : `database "airflow" does not exist` | La base Airflow n'a pas été créée au premier démarrage | `docker compose down -v`, puis `docker compose up -d`. Le script de création ne s'exécute que sur une base vide |
| `Permission non accordée` en écrivant dans `scripts/`, `data/` ou `docker/postgres/` — **Linux uniquement** | Docker a créé le dossier lui-même, en tant que root | `sudo chown -R $USER:$USER <dossier>` |
| `.env.example` introuvable après un téléchargement | Le fichier a perdu son point en route et s'appelle `env.example` | Le renommer en `.env.example` |
| `git pull` dit « déjà à jour » mais des fichiers manquent | Tu es sur `main` au lieu de `develop` | `git checkout develop` |
| Une PR partie vers `main` au lieu de `develop` | GitHub propose `main` tant qu'elle est la branche par défaut | Toujours vérifier la **base** avant de créer la PR ; sur une PR ouverte, **Modifier** permet de la changer |
| Un commit parti sur `develop` au lieu de ta branche | La branche n'avait pas été créée avant le commit | Demander de l'aide avant de pousser : le commit se déplace sans rien perdre |
| `Select-String` introuvable | Commande PowerShell tapée dans un terminal Linux | Utiliser `grep`. Les commandes `git` et `docker` sont identiques partout |
| Une commande échoue et la suivante s'exécute quand même | Plusieurs commandes collées d'un coup s'enchaînent malgré les erreurs | **S'arrêter à la première erreur**, avant de continuer |

Pour tout arrêter : `docker compose down` conserve les données. `docker compose down -v` **efface toutes les bases** : à ne lancer qu'en le voulant.

Docker Desktop consomme de la mémoire même quand rien ne tourne : quitte-le quand tu ne travailles pas sur le projet, et relance-le avant chaque `docker compose up`.

---

## 10. Où en est le projet

| Sprint | Objectif | État |
|---|---|---|
| Sprint 0 | Organisation et préparation | ✅ Clôturé — étiquette `v0.1` |
| Sprint 1 | Acquisition et stockage brut | 🔄 En cours |
| Sprint 2 | Qualité et transformation | À venir |
| Sprint 3 | Intégration, entrepôt et premiers indicateurs | À venir |
| Sprint 4 | Temps réel, recherche et supervision | À venir |
| Sprint 5 | Intelligence artificielle et finalisation | À venir |

Le détail de la répartition et des livrables de chaque sprint est dans les documents de répartition, et le suivi au jour le jour sur Trello, tenu par le Product Owner.

---

## 11. Vérification croisée du Sprint 0

Chaque membre transmet sa ligne au Scrum Master, qui suit l'avancement ; le Product Owner met les cartes Trello à jour.

| Membre | Système | Dépôt à jour | Services démarrés | Tests | Données 10/10 | `data/` absent de `git status` | Ports modifiés | Mémoire relevée |
|---|---|---|---|---|---|---|---|---|
| Ndeye Penda SARR | Windows | ✅ | ✅ | ✅ | ✅ | ✅ | 5433 | 3,1 Go |
| Seydina WADE | Linux | ✅ | ✅ | ✅ | ✅ | ✅ | 5433, 27018 | 3,1 Go |
| Bachir DEME | Linux | ✅ | ✅ | ✅ | ✅ | ✅ | 5433, 27018 | 3,1 Go |
| Mouhameth DIOP | Linux | ✅ | ✅ | ✅ | ✅ | ✅ | aucun | 3,1 Go |
| Aissata DIALLO | Linux | ✅ | ✅ | ✅ | ✅ | ✅ | aucun | 3,1 Go |

**Les cinq lignes sont complètes : la vérification croisée du Sprint 0 est réussie**, sous Linux comme sous Windows, pour environ 3,1 Go de mémoire.

À la fin de chaque sprint suivant, un nouveau tableau est ajouté ici, et la clôture se fait de la même façon : une PR `develop → main` intitulée `[Sx] Fin du Sprint x`, puis une étiquette de version.

---

## 12. Le premier commit de chacun

Une fois la plateforme en marche chez toi, fais ton **premier commit** en suivant `docs/PREMIER_COMMIT.md` : créer le dossier de ton périmètre dans `src/`, avec son README, par une branche et une demande de fusion.

| Membre | Dossiers à créer |
|---|---|
| Mouhameth | `src/acquisition/`, `src/streaming/` |
| Seydina | `src/quality/` |
| Aissata | `src/transformation/`, `src/integration/` |
| Bachir | `src/search/`, `src/ml/` |

**Ndeye Penda n'est pas concernée** : son socle a été son premier commit, et il a créé ses deux dossiers, `src/common/` et `dags/`.
