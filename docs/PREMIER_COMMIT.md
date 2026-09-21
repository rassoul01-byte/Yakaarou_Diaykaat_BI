# Sprint 0 — Le premier commit de chacun

**Objectif :** que chaque membre fasse son premier commit, par une branche et une demande de fusion relue, avant d'en avoir réellement besoin.

Cinq premiers commits, aucun conflit possible — chacun écrit dans son propre dossier — et la preuve que le circuit **branche → relecture → fusion** fonctionne pour les cinq.

---

## 1. L'ordre

1. **Le dépôt existe**, avec les branches `main` et `develop` — tâche de Seydina.
2. **Le socle Python est fusionné dans `develop`** — tâche de Ndeye Penda. Il crée `src/`, `tests/`, les fichiers de dépendances et la configuration de pytest. Les quatre autres commits en dépendent.
3. **Les quatre autres membres** créent leur dossier, **en parallèle**. Aucun ne dépend des autres.

---

## 2. Qui fait quoi

| Membre | Branche | Dossiers à créer | Relecteur |
|---|---|---|---|
| Ndeye Penda SARR | `chore/S0-socle-python` | socle complet, `src/common/`, `dags/` | Aissata DIALLO |
| Mouhameth DIOP | `chore/S0-perimetre-acquisition` | `src/acquisition/`, `src/streaming/` | Seydina WADE |
| Seydina WADE | `chore/S0-perimetre-qualite` | `src/quality/` | Mouhameth DIOP |
| Aissata DIALLO | `chore/S0-perimetre-transformation` | `src/transformation/`, `src/integration/` | Ndeye Penda SARR |
| Bachir DEME | `chore/S0-perimetre-recherche-ia` | `src/search/`, `src/ml/` | Aissata DIALLO |

Le relecteur est le suppléant désigné dans `docs/ROLES.md`. C'est volontaire : relire les demandes de fusion d'un périmètre est la façon la plus simple d'en garder la connaissance.

---

## 3. Les commandes

Exemple pour Mouhameth. Chacun remplace le nom de branche et les dossiers par les siens.

```bash
# 1. Partir de la dernière version de develop
git checkout develop
git pull

# 2. Créer sa branche
git checkout -b chore/S0-perimetre-acquisition

# 3. Créer ses dossiers, chacun avec un fichier vide et un README
mkdir -p src/acquisition src/streaming
touch src/acquisition/__init__.py src/streaming/__init__.py
# puis écrire src/acquisition/README.md et src/streaming/README.md (modèle plus bas)

# 4. Vérifier que rien ne casse
pytest

# 5. Committer et pousser
git add src/acquisition src/streaming
git commit -m "chore(acquisition): creer les dossiers du perimetre"
git push -u origin chore/S0-perimetre-acquisition
```

Puis, sur GitHub : ouvrir une demande de fusion **vers `develop`**, intitulée `[S0] Création des dossiers du périmètre acquisition`, et désigner son relecteur.

Le format des branches, des commits et des titres de PR est celui de `CONVENTIONS.md`, qui fait foi. Le Sprint 0 y bénéficie d'une exception : le code `S0` remplace le code du backlog.

Le fichier `__init__.py` vide n'est pas décoratif : c'est lui qui fait du dossier un module Python importable. Sans lui, `from acquisition import …` échouera au Sprint 1.

---

## 4. Le modèle de README

Chacun écrit le sien, avec ses mots. C'est le seul contenu du commit : il doit dire ce que le dossier contiendra, pas comment ce sera codé.

```markdown
# <nom du dossier> — <périmètre en quelques mots>

**Responsable :** <nom>
**Suppléant :** <nom>

## Ce que contiendra ce dossier

<deux ou trois phrases : quel traitement, quelle entrée, quelle sortie>

## Fonctionnalités portées

<codes du backlog, par exemple F1.1, F1.2, F1.3>

## Dépendances prévues

<bibliothèques qui seront ajoutées à requirements.txt, et à quel sprint>
```

---

## 5. Ce que le relecteur vérifie

- La branche part bien de `develop` et vise bien `develop`, pas `main`.
- Le message de commit respecte `CONVENTIONS.md` : type, périmètre, action à l'infinitif.
- Le dossier contient un `__init__.py` et un README complet.
- Les fonctionnalités citées sont bien celles du backlog attribuées à ce membre.
- Aucun fichier ne sort du dossier du périmètre.

S'il manque quelque chose, le relecteur **commente et demande une modification** plutôt que de corriger lui-même. Le but de l'exercice est que chacun passe par tout le circuit.

---

## 6. Critère de réussite

Le Sprint 0 est validé sur ce point lorsque l'historique de `develop` montre **cinq demandes de fusion, cinq auteurs différents, chacune relue par un membre d'un autre périmètre.**

C'est la première trace, dans le dépôt, de la contribution de chacun — exactement ce que l'évaluation demande de pouvoir identifier.
