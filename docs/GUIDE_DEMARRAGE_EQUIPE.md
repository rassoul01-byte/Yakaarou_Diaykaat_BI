# Mettre son poste à jour et faire tourner la plateforme

**GROUPE 2 · DataFlow360 · Sprint 0**
**État du dépôt au 21 septembre**

Ce guide sert à deux choses : remettre chaque poste au niveau des modifications du jour, et réaliser la **vérification croisée** qui clôt le Sprint 0. Le Sprint 0 est terminé quand les cinq membres obtiennent le même résultat, chacun sur sa propre machine.

---

## 1. Ce qui a changé aujourd'hui

Tout se trouve sur la branche **`develop`**. `main` n'a pas bougé et c'est normal : elle ne recevra `develop` qu'à la fin du sprint.

| Élément                                                            | Où                                                                               | Apporté par |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------ |
| Exclusion du dossier`data/`                                        | `.gitignore`                                                                    | Seydina      |
| Socle Python : dépendances, configuration des tests, premiers tests | `requirements*.txt`, `pyproject.toml`, `src/common/`, `tests/`, `dags/` | Ndeye Penda  |
| Image du conteneur de travail                                        | `docker/app/Dockerfile`                                                         | Ndeye Penda  |
| Composition des six services                                         | `docker-compose.yml`, `.env.example`                                          | Bachir       |
| Création des bases et des schémas                                  | `docker/postgres/init/01-databases.sql`                                         | Bachir       |
| Script de récupération des données                                | `scripts/download_data.py`, `tests/scripts/`                                  | Bachir       |

Deux règles sont désormais **appliquées par GitHub**, et non plus seulement écrites :

- personne ne peut pousser directement sur `main` ni sur `develop` ;
- toute demande de fusion exige l'approbation d'un autre membre.

---

## 2. Prérequis

- **Git**
- **Docker Desktop**, lancé. Vérifier avec `docker compose version` — la commande s'écrit avec une espace.
- **Environ 4 Go de mémoire vive disponibles.** Le relevé exact est dans la PR de Bachir.
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

`git fetch --prune` fait disparaître de ta copie les branches supprimées sur GitHub.

### Cas B — Clone neuf

Pour un poste qui n'a jamais eu le dépôt, ou une copie trop abîmée pour être réparée :

```bash
git clone https://github.com/rassoul01-byte/Yakaarou_Diaykaat_BI.git
cd Yakaarou_Diaykaat_BI
git checkout develop
```

Si un dossier du même nom existe déjà, ajoute un nom à la fin de la première commande, par exemple `… .git dataflow360`, puis `cd dataflow360`.

### Vérifier que tout est arrivé

```bash
git log --oneline -5
```

✅ Les derniers commits parlent du socle Python, de la composition des services et du script de récupération.

---

## 4. Configurer son poste

### Créer son fichier d'environnement

```bash
cp .env.example .env
```

`cp` fonctionne aussi sous PowerShell. Le fichier `.env` est propre à ton poste et **ne doit jamais être commité** — il est exclu par le `.gitignore`.

⚠️ Si `.env.example` est introuvable, vérifie que tu es bien sur `develop` : il n'existe pas sur `main`.

### Vérifier que les ports sont libres

Si PostgreSQL ou MongoDB sont déjà installés sur ton poste pour un autre cours, ils occupent les ports dont la plateforme a besoin. C'est arrivé chez Bachir pour les deux.

Sous **Windows**, dans PowerShell :

```powershell
netstat -ano | findstr ":5432 :27017 :9200 :8080 :29092"
```

Sous **Linux** :

```bash
ss -ltn | grep -E ':(5432|27017|9200|8080|29092)\b'
```

Chaque ligne affichée est un port déjà pris. Change-le **dans ton `.env`**, jamais dans `docker-compose.yml` :

| Port occupé | Ligne à modifier dans`.env` |
| ------------ | ------------------------------ |
| 5432         | `POSTGRES_PORT=5433`         |
| 27017        | `MONGO_PORT=27018`           |
| 8080         | `AIRFLOW_PORT=8081`          |
| 9200         | `ES_PORT=9201`               |
| 29092        | `KAFKA_PORT=29093`           |

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

| Service                | État attendu              |
| ---------------------- | -------------------------- |
| postgres, mongodb      | `healthy`                |
| elasticsearch, kafka   | `healthy` ou `running` |
| airflow-init           | **`exited (0)`**   |
| airflow-webserver      | `healthy`                |
| airflow-scheduler, app | `running`                |

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

---

## 8. Les pannes rencontrées aujourd'hui, et leur solution

Toutes ces pannes sont réellement arrivées pendant la mise en place. Si l'une d'elles t'arrive, la solution est connue.

| Symptôme                                                                                                                    | Cause                                                                    | Solution                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| `address already in use` ou `port is already allocated`                                                                  | Un autre programme utilise le port                                       | Changer le port dans`.env`, section 4                                                                               |
| `airflow-init` qui redémarre en boucle ; journaux : `database "airflow" does not exist`                                 | La base Airflow n'a pas été créée au premier démarrage              | `docker compose down -v`, puis `docker compose up -d`. Le script de création ne s'exécute que sur une base vide |
| `Permission non accordée` en écrivant dans `scripts/`, `data/` ou `docker/postgres/` — **Linux uniquement** | Docker a créé le dossier lui-même, en tant que root                   | `sudo chown -R $USER:$USER <dossier>`                                                                               |
| `.env.example` introuvable après un téléchargement                                                                      | Le fichier a perdu son point en route et s'appelle`env.example`        | Le renommer en`.env.example`                                                                                        |
| `git pull` dit « déjà à jour » mais des fichiers manquent                                                             | Tu es sur`main` au lieu de `develop`                                 | `git checkout develop`                                                                                              |
| Un commit parti sur`develop` au lieu de ta branche                                                                         | La branche n'avait pas été créée avant le commit                     | Demander de l'aide avant de pousser : le commit se déplace sans rien perdre                                          |
| `Select-String` introuvable                                                                                                | Commande PowerShell tapée dans un terminal Linux                        | Utiliser`grep`. Les commandes `git` et `docker` sont identiques partout                                         |
| Une commande échoue et la suivante s'exécute quand même                                                                   | Plusieurs commandes collées d'un coup s'enchaînent malgré les erreurs | **S'arrêter à la première erreur**, avant de continuer                                                       |

Pour tout arrêter : `docker compose down` conserve les données. `docker compose down -v` **efface toutes les bases** : à ne lancer qu'en le voulant.

---

## 9. La situation de chacun

### Ndeye Penda — Windows, PowerShell

**Fait :** le socle Python est fusionné dans `develop`.

**À faire :**

1. Vérifier sur GitHub l'état de la PR **`[S0] Rôles de l'équipe et schéma d'architecture`**. Si elle est encore ouverte, contrôler que sa base est `develop` et la faire approuver. Sans elle, le schéma affiché par le README est introuvable.
2. Vérifier que la PR du Dockerfile, devenue inutile, est fusionnée ou fermée.
3. Mettre sa copie à jour — **cas A** — puis supprimer les branches locales devenues inutiles :

   ```powershell
   git branch
   git branch -d chore/S0-socle-python fix/S0-ajouter-dockerfile
   ```

   Si Git refuse avec `-d`, c'est que la branche n'a pas été fusionnée : vérifier avant de forcer.
4. Installer et lancer Docker Desktop s'il ne l'est pas, puis dérouler les sections 4 à 7.

Le dossier `.venv` créé à la racine pour les tests locaux peut rester : il est exclu par le `.gitignore`.

### Seydina — Linux

**Fait :** exclusion de `data/`, protection des branches, dépôt rendu public.

**À faire :**

1. Travailler **uniquement dans `~/yakaarou-propre`**, le seul clone correctement relié au dépôt. Les dossiers `~/Téléchargements/dataflow360-repo` et l'ancien `~/Yakaarou_Diaykaat_BI` peuvent être supprimés : ce qu'ils contenaient d'utile est repris par le script de Bachir.
2. Pousser la correction de `CONVENTIONS.md`, branche `docs/S0-corriger-conventions`.
3. Dans *Settings → General*, définir **`develop` comme branche par défaut**. C'est ce qui évitera les PR envoyées vers `main` par erreur.
4. Supprimer les anciennes branches `feature/…`, `README.md` et `rassoul01-byte-patch-1`, si ce n'est pas déjà fait.
5. Dérouler les sections 4 à 7.

### Bachir — Linux

**Fait :** la composition des services et le script de récupération. Son poste est la **référence** : tout y tourne.

**À noter :** dans son `.env`, les ports sont `POSTGRES_PORT=5433` et `MONGO_PORT=27018`.

**À faire :** faire fusionner la PR du script si elle ne l'est pas encore, puis supprimer ses branches locales fusionnées.

### Mouhameth — Scrum Master

**À faire :**

1. **Cas A**, puis sections 4 à 7.
2. Recueillir les résultats de la vérification croisée des cinq membres — tableau de la section 10 — et mettre Trello à jour.

### Aissata — README

**À faire :** le **cas B, clone neuf**, même si le dépôt est déjà sur son poste. C'est la vérification exigée pour le README : *une personne doit pouvoir démarrer la plateforme en suivant uniquement ce fichier*. Elle déroule les sections 3 à 7 en notant chaque étape qui bloque ou qui n'est pas claire, puis corrige le README en conséquence avant de le proposer en PR.

La section 8 de ce guide contient toute la matière de la partie *Problèmes fréquents* du README.

---

## 10. Vérification croisée — à remplir par chacun

Chaque membre transmet sa ligne au Scrum Master.

| Membre           | Système | Dépôt à jour | Services démarrés | 22 tests | Données 10/10 | `data/` absent de `git status` | Ports modifiés | Mémoire relevée |
| ---------------- | -------- | --------------- | ------------------- | -------- | -------------- | ---------------------------------- | --------------- | ----------------- |
| Ndeye Penda SARR | Windows  | ✅              | ✅                  |          |                |                                    |                 |                   |
| Seydina WADE     | Linux    |                 |                     |          |                |                                    |                 |                   |
| Bachir DEME      | Linux    | ✅              | ✅                  |          |                |                                    | 5433, 27018     |                   |
| Mouhameth DIOP   |          |                 |                     |          |                |                                    |                 |                   |
| Aissata DIALLO   |          |                 |                     |          |                |                                    |                 |                   |

**Le Sprint 0 est terminé quand les cinq lignes sont complètes.** Ce jour-là : une PR `develop → main` intitulée `[S0] Fin du Sprint 0`, et une étiquette `v0.1` pour marquer l'étape.
