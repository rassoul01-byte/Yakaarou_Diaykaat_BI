# Conventions de Travail de l'Équipe — DataFlow360

Ce document définit les règles obligatoires de collaboration sur le dépôt Git. Il garantit la traçabilité du code, évite les conflits et assure l'alignement avec le dossier de conception.

---

### 1. Comment nommer une branche ?

Toute branche doit être créée depuis la dernière version de `develop` et respecter la syntaxe suivante :

`<type>/<code-fonctionnalite>-<description-courte>`

* **`type`** : `feat` (nouvelle fonctionnalité), `fix` (correction de bug), `test` (ajout ou modification de tests), `docs` (documentation), `chore` (Docker, configuration, outillage).
* **`code-fonctionnalite`** : Le code officiel issu du backlog (ex. : `F1.1`, `F6.4`, `F1.5`).
* **`description-courte`** : Mots en minuscules séparés par des tirets.

> **Exemples :**
> `feat/F1.1-collecte-commandes-olist`
> `feat/F6.4-docker-compose-socle`
> `fix/F1.7-decodage-balises-html`

**Exception — Sprint 0 :** les tâches d'organisation du Sprint 0 ne portent pas de code du backlog. Elles utilisent le code `S0` à la place.

> **Exemple :** `chore/S0-socle-python`

---

### 2. Comment écrire un message de commit ?

Chaque commit doit représenter une unité logique de travail cohérente et respecter la syntaxe conventionnelle :

`<type>(<perimetre>): <action claire à l'infinitif>`

* **`type`** : `feat`, `fix`, `test`, `refactor`, `docs`, `chore`.
* **`perimetre`** : Le dossier concerné, tel qu'il existe dans le dépôt : `acquisition`, `streaming`, `quality`, `transformation`, `integration`, `search`, `ml`, `common`, `dags`, ainsi que `docker`, `ci` et `docs` pour ce qui sort de `src/`.

> **Exemples :**
> `feat(quality): ajouter la regle d'unicite sur les identifiants d'avis`
> `test(quality): verifier le rejet des avis en double`
> `fix(transformation): filtrer les lignes de geolocalisation dupliquees`
> `chore(docker): limiter la memoire allouee a elasticsearch`

**Ne pas confondre `feat` et `test` pour la qualité.** Écrire une règle de qualité, c'est livrer une fonctionnalité du backlog : c'est un `feat`. Écrire le test qui vérifie que cette règle rejette bien ce qu'elle doit rejeter, c'est un `test`. La distinction est la même que dans la section CI/CD du dossier de conception.

---

### 3. Comment ouvrir et faire relire une demande de fusion (Pull Request) ?

1. **Branche cible :** Toujours pointer vers **`develop`** (aucun push direct sur `main` ou `develop`).
2. **Synchronisation locale :** Avant d'ouvrir la PR, récupérer puis intégrer les derniers changements de `develop` pour résoudre les éventuels conflits sur son poste :
   ```bash
   git fetch origin
   git merge origin/develop
   ```

   Le `fetch` n'est pas facultatif : sans lui, on fusionne une version périmée de `develop` et les conflits réapparaissent au moment de la PR.
3. **Titre de la PR :** Commencer obligatoirement par le code du backlog (ex. : `[F1.5] Mise en place des règles Great Expectations`), ou par `[S0]` pour une tâche du Sprint 0.
4. **Description obligatoire :** Indiquer brièvement :
   * Ce qui a été réalisé.
   * La commande pour tester en local.
   * Les impacts éventuels sur Docker ou `.env`.
5. **Revue croisée :** Assigner **au moins un relecteur issu d'un autre périmètre**. Le relecteur privilégié est le suppléant désigné dans `docs/Roles Et Responsabilites.md` : relire les PR d'un périmètre est la façon la plus simple d'en garder la connaissance. La fusion ne peut se faire qu'après au moins une approbation explicite.

---

### 4. À quelles conditions une tâche est considérée comme terminée (DoD) ?

Une tâche du backlog ne peut être passée dans la colonne **« Terminé »** sur Trello que si :

1. Le code répond au besoin exact de la fonctionnalité associée.
2. Le composant s'exécute et fonctionne correctement dans le conteneur Docker.
3. Les tests unitaires ou contrôles de qualité associés s'exécutent sans erreur.
4. La Pull Request a été relue, validée et fusionnée dans `develop`.
5. La documentation (ou dictionnaire des données) a été mise à jour si la tâche le nécessitait.
6. La branche de travail a été supprimée après la fusion.

---

### ⚠️ Règles d'or complémentaires pour l'équipe :

* **Zéro donnée sur Git :** Interdiction formelle de commiter des fichiers `.csv`, `.parquet` ou des dumps SQL. Les données résident uniquement dans le dossier local non versionné `data/`.
  **Seule exception :** les jeux d'essai des tests, placés dans `tests/fixtures/`. Ils font quelques dizaines de lignes, pèsent quelques kilo-octets, et doivent être versionnés pour que les tests s'exécutent à l'identique chez chacun et dans la chaîne d'intégration continue.
* **Zéro secret dans le code :** Mots de passe, URLs de connexion et clés d'API passent exclusivement par le fichier local `.env`. Toute nouvelle variable doit être documentée dans `.env.example`.
* **Unicité Trello :** Une tâche = un seul responsable identifié. La carte doit être déplacée dans « En cours » avant de créer sa branche.
* **Chacun commite son propre travail :** un travail rédigé par un membre est commité depuis le compte de ce membre, même lorsqu'il serait plus rapide qu'un autre le fasse à sa place. L'historique du dépôt est ce qui rend la contribution de chacun visible.
* **Fidélité au dossier :** Tout changement d'architecture ou de règle par rapport au dossier de conception doit être consigné par écrit afin que la documentation ne diverge jamais de la réalisation.
