# Mettre son poste à jour et faire tourner la plateforme

**GROUPE 2 · DataFlow360 · Sprint 0**
**État du dépôt au 21 septembre, fin de journée**

Ce guide sert à deux choses : remettre chaque poste au niveau des modifications du jour, et réaliser la **vérification croisée** qui clôt le Sprint 0. Le Sprint 0 est terminé quand les cinq membres obtiennent le même résultat, chacun sur sa propre machine.

---

## 1. Ce qui a changé aujourd'hui

Tout se trouve sur la branche **`develop`**. `main` n'a pas bougé et c'est normal : elle ne recevra `develop` qu'à la fin du sprint.

| Élément | Où | Apporté par |
|---|---|---|
| Exclusion du dossier `data/` | `.gitignore` | Seydina |
| Socle Python : dépendances, configuration des tests, premiers tests | `requirements*.txt`, `pyproject.toml`, `src/common/`, `tests/`, `dags/` | Ndeye Penda |
| Image du conteneur de travail | `docker/app/Dockerfile` | Ndeye Penda |
| Composition des six services | `docker-compose.yml`, `.env.example` | Bachir |
| Création des bases et des schémas | `docker/postgres/init/01-databases.sql` | Bachir |
| Script de récupération des données | `scripts/download_data.py`, `tests/scripts/` | Bachir |
| Rôles, schéma d'architecture, ce guide | `docs/` | Ndeye Penda |

Deux règles sont désormais **appliquées par GitHub**, et non plus seulement écrites :
- personne ne peut pousser directement sur `main` ni sur `develop` ;
- toute demande de fusion exige l'approbation d'un autre membre.

Les branches fusionnées aujourd'hui ont toutes été supprimées : sur GitHub, il ne reste que `main` et `develop`.

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

⚠️ **La commande `git checkout develop` est indispensable.** Tant que `develop` n'est pas la branche par défaut du dépôt, un clone s'ouvre sur `main`, qui ne contient presque rien. Seydina va changer ce réglage ; en attendant, ne sautez pas cette ligne.

Si un dossier du même nom existe déjà, ajoute un nom à la fin de la première commande, par exemple `… .git dataflow360`, puis `cd dataflow360`.

### Vérifier que tout est arrivé

```bash
git log --oneline -5
```

✅ Les derniers commits parlent du socle Python, de la composition des services, du script de récupération et de la documentation.

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

✅ La première liste contient une base **`airflow`**. La seconde montre les schémas `dwh`, `raw_quarantine` et `staging`.

```bash
docker compose exec app python -m pytest
```

✅ **22 passed** : les 15 tests du socle et les 7 du script de récupération.

Dans ton navigateur, en adaptant le port si tu l'as changé :
- http://localhost:9200 → Elasticsearch affiche son numéro de version ;
- http://localhost:8080 → Airflow, identifiant `admin`, mot de passe `changeme_en_local`.

---

## 7. Récupérer les données

```bash
docker compose exec app python scripts/download_data.py
```

✅ Le téléchargement de l'archive Olist et du catalogue Rakuten, puis **« 10 fichier(s) sur 10 conforme(s) »**. Les fichiers apparaissent dans `data/raw/` sur ton poste.

Relance la commande une seconde fois : ✅ *« rien à télécharger »*.

Enfin :

```bash
git status
```

✅ **`data/` ne doit pas apparaître.** C'est la preuve que les 174 Mo de données ne partiront jamais sur GitHub.

Et pour relever la mémoire consommée, à reporter dans le tableau de la section 10 :

```bash
docker stats --no-stream
```

---

## 8. Les pannes rencontrées aujourd'hui, et leur solution

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

## 9. La situation de chacun

### Ndeye Penda — Windows, PowerShell

**Fait :** le socle Python, les rôles et responsabilités, le schéma d'architecture et ce guide sont dans `develop`. **Vérification croisée réussie** : la plateforme tourne sur son poste, 22 tests passés, données 10 sur 10, avec PostgreSQL sur le port 5433. Ses branches fusionnées sont supprimées.

**À faire :** relire les PR d'Aissata — son premier commit, puis le README.

### Seydina — Linux

**Fait :** exclusion de `data/`, protection des branches, dépôt rendu public, anciennes branches supprimées.

**À faire :**
1. Dans *Settings → General* : définir **`develop` comme branche par défaut**, et cocher **« Automatically delete head branches »** dans la section *Pull Requests*, pour que chaque branche soit supprimée automatiquement après sa fusion.
2. Pousser la correction de `CONVENTIONS.md`, branche `docs/S0-corriger-conventions`.
3. Travailler **uniquement dans `~/yakaarou-propre`**, le seul clone correctement relié au dépôt. Les dossiers `~/Téléchargements/dataflow360-repo` et l'ancien `~/Yakaarou_Diaykaat_BI` peuvent être supprimés.
4. Dérouler les sections 4 à 7, puis son premier commit — section 11.

### Bachir — Linux

**Fait :** la composition des services et le script de récupération sont fusionnés. Son poste a été le premier à faire tourner toute la plateforme.

**À noter :** dans son `.env`, les ports sont `POSTGRES_PORT=5433` et `MONGO_PORT=27018`.

**À faire :** compléter sa ligne du tableau de la section 10, puis son premier commit — section 11.

### Mouhameth — Scrum Master

**À faire :**
1. **Cas A**, puis sections 4 à 7, puis son premier commit — section 11.
2. Recueillir les résultats de la vérification croisée des cinq membres — tableau de la section 10 — et mettre Trello à jour.

### Aissata — README

**Demain :** le **cas B, clone neuf**, même si le dépôt est déjà sur son poste. Elle déroule les sections 3 à 7 et s'assure que tout fonctionne **avant** de créer le README. C'est la vérification exigée pour ce livrable : *une personne doit pouvoir démarrer la plateforme en suivant uniquement le README*. Elle note chaque étape qui bloque ou qui n'est pas claire, et s'en sert pour corriger le brouillon du README avant de le proposer en PR.

La section 8 de ce guide contient toute la matière de la partie *Problèmes fréquents* du README.

Puis son premier commit — section 11.

---

## 10. Vérification croisée — à remplir par chacun

Chaque membre transmet sa ligne au Scrum Master.

| Membre | Système | Dépôt à jour | Services démarrés | 22 tests | Données 10/10 | `data/` absent de `git status` | Ports modifiés | Mémoire relevée |
|---|---|---|---|---|---|---|---|---|
| Ndeye Penda SARR | Windows | ✅ | ✅ | ✅ | ✅ | ✅ | 5433 | 3,1 Go |
| Seydina WADE | Linux | | | | | | | |
| Bachir DEME | Linux | ✅ | ✅ | ✅ | ✅ | ✅ | 5433, 27018 | |
| Mouhameth DIOP |Linux| ✅ | ✅ | ✅ | ✅ | ✅ | - |3,1GO |
| Aissata DIALLO |Linux| ✅ | ✅ | ✅ | ✅ | ✅ | -  |3,1GO |

**Le Sprint 0 est terminé quand les cinq lignes sont complètes.** Ce jour-là : une PR `develop → main` intitulée `[S0] Fin du Sprint 0`, et une étiquette `v0.1` pour marquer l'étape.

---

## 11. Le premier commit de chacun

Une fois la plateforme en marche chez toi, fais ton **premier commit** en suivant `docs/PREMIER_COMMIT.md` : créer le dossier de ton périmètre dans `src/`, avec son README, par une branche et une demande de fusion.

| Membre | Dossiers à créer |
|---|---|
| Mouhameth | `src/acquisition/`, `src/streaming/` |
| Seydina | `src/quality/` |
| Aissata | `src/transformation/`, `src/integration/` |
| Bachir | `src/search/`, `src/ml/` |

**Ndeye Penda n'est pas concernée** : son socle a été son premier commit, et il a créé ses deux dossiers, `src/common/` et `dags/`.