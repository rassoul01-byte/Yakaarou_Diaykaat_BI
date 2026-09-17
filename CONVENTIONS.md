# Conventions de Travail de l'Équipe — DataFlow360

Ce document définit les règles obligatoires de collaboration sur le dépôt Git. Il garantit la traçabilité du code, évite les conflits et assure l'alignement avec les exigences de la plateforme[cite: 1].

---

### 1. Comment nommer une branche ?

Toute branche doit être créée depuis la dernière version de `develop` et respecter la syntaxe suivante :

`<type>/<code-fonctionnalite>-<description-courte>`

* **`type`** : `feat` (nouvelle fonctionnalité), `fix` (correction de bug), `test` (règles de qualité/tests), `docs` (documentation), `chore` (Docker/configuration).
* **`code-fonctionnalite`** : Le code officiel issu du backlog (ex. : `F1.1`, `F6.4`, `F1.5`)[cite: 1].
* **`description-courte`** : Mots en minuscules séparés par des tirets.

> **Exemples :**  
> `feat/F1.1-collecte-commandes-olist`[cite: 1]  
> `feat/F6.4-docker-compose-socle`[cite: 1]  
> `fix/F1.7-decodage-balises-html`[cite: 1]

---

### 2. Comment écrire un message de commit ?

Chaque commit doit représenter une unité logique de travail cohérente et respecter la syntaxe conventionnelle :

`<type>(<perimetre>): <action claire à l'infinitif>`

* **`type`** : `feat`, `fix`, `test`, `refactor`, `docs`, `chore`.
* **`perimetre`** : Composant ou service concerné (`ingest`, `storage`, `postgres`, `mongo`, `quality`, `transform`, `search`, `docker`, etc.).

> **Exemples :**  
> `feat(storage): initialisation des schemas bruts postgresql`  
> `test(quality): ajout regle unicite sur identifiants avis clients`[cite: 1]  
> `fix(transform): filtrage des lignes geolocalisation dupliquees`[cite: 1]

---

### 3. Comment ouvrir et faire relire une demande de fusion (Pull Request) ?

1. **Branche cible :** Toujours pointer vers **`develop`** (aucun push direct sur `main` ou `develop`).
2. **Synchronisation locale :** Avant d'ouvrir la PR, mettre à jour sa branche locale avec les derniers changements de `develop` (`git merge origin/develop`) pour résoudre les éventuels conflits sur son poste.
3. **Titre de la PR :** Commencer obligatoirement par le code du backlog (ex. : `[F1.5] Mise en place des règles Great Expectations`)[cite: 1].
4. **Description obligatoire :** Indiquer brièvement :
   * Ce qui a été réalisé.
   * La commande pour tester en local.
   * Les impacts éventuels sur Docker ou `.env`.
5. **Revue croisée :** Assigner **au moins un relecteur issu d'un autre périmètre**[cite: 1] (ex. : AD relit MD, SW relit NPS, BD relit SW)[cite: 1]. La fusion ne peut se faire qu'après au moins une approbation explicite.

---

### 4. À quelles conditions une tâche est considérée comme terminée (DoD) ?

Une tâche du backlog ne peut être passée dans la colonne **"Terminé"** sur Trello que si :

1. Le code répond au besoin exact de la fonctionnalité associée[cite: 1].
2. Le composant s'exécute et fonctionne correctement dans le conteneur Docker[cite: 1].
3. Les tests unitaires ou contrôles de qualité associés s'exécutent sans erreur[cite: 1].
4. La Pull Request a été relue, validée et fusionnée dans `develop`[cite: 1].
5. La documentation (ou dictionnaire des données) a été mise à jour si la tâche le nécessitait[cite: 1].
6. La branche de travail a été supprimée après la fusion.

---

### ⚠️ Règles d'or complémentaires pour l'équipe :

* **Zéro donnée sur Git :** Interdiction formelle de commiter des fichiers `.csv`, `.parquet` ou des dumps SQL[cite: 1]. Les données résident uniquement dans le dossier local non-versionné `data/`[cite: 1].
* **Zéro secret dans le code :** Mots de passe, URLs de connexion et clés d'API passent exclusivement par le fichier local `.env`. Toute nouvelle variable doit être documentée dans `.env.example`.
* **Unicité Trello :** Une tâche = un seul responsable identifié[cite: 1]. La carte doit être déplacée dans "En cours" avant de créer sa branche[cite: 1].
* **Fidélité au dossier :** Tout changement d'architecture ou de règle par rapport au dossier de conception doit être consigné par écrit afin que la documentation ne diverge jamais de la réalisation[cite: 1].
