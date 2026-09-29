# Rôles et responsabilités — GROUPE 2

**Projet :** DataFlow360 — plateforme data d'un e-commerçant
**Arrêté le :** Sprint 0
**Révision :** toute modification est validée en réunion de sprint et reportée dans ce fichier.

Ce document fixe qui fait quoi et qui décide quoi. Il complète la section consacrée à l'organisation dans le dossier de conception, dont il est la version de travail : en cas d'écart, c'est ce fichier qui fait foi, et le dossier est mis à jour.

---

## 1. L'équipe

| Membre | Rôle de conduite | Périmètre technique | Dossier dans `src/` |
|---|---|---|---|
| **Bachir DEME** | Product Owner | Recherche, Machine Learning et intelligence artificielle | `search/`, `ml/` |
| **Mouhameth DIOP** | Scrum Master | Acquisition et flux d'événements | `acquisition/`, `streaming/` |
| **Ndeye Penda SARR** | Conception et documentation | Orchestration et restitution décisionnelle | `dags/`, `common/` |
| **Seydina WADE** | — | Stockage, qualité des données et intégration continue | `quality/`, `.github/workflows/` |
| **Aissata DIALLO** | — | Transformation et intégration | `transformation/`, `integration/` |

Les rôles de conduite s'ajoutent au périmètre technique, ils ne le remplacent pas. Bachir et Mouhameth développent au même titre que les autres.

---

## 2. Responsable unique et travail collectif

Chaque tâche du backlog porte **un responsable unique**, qui répond de son avancement et qui saura l'expliquer à la soutenance.

Cela ne signifie pas qu'il travaille seul. Chaque sprint mobilise l'équipe entière : les autres membres relisent les demandes de fusion, aident au déblocage, testent et complètent la documentation. La colonne « Responsable » du backlog indique **qui pilote, non qui travaille**.

Cette règle sert la contribution de chacun plutôt qu'elle ne la limite : si tout le monde touche à tout, l'historique du dépôt ne permet plus de dire ce que chacun a fait, et personne ne peut répondre pour son propre travail.

---

## 3. Les rôles de conduite

### Product Owner — Bachir DEME

**Ce qu'il fait**

- Détient le backlog : il en fixe les priorités et les fait évoluer.
- Décide de ce qui entre et de ce qui sort d'un sprint.
- Tient le tableau Trello : contenu des cartes, priorités et affectations. Il en a la charge depuis le Sprint 1.
- En fin de sprint, accepte ou refuse chaque fonctionnalité livrée : une fonctionnalité qui fonctionne mais ne répond pas au besoin auquel elle est rattachée n'est pas acceptée.
- Décide de l'abandon d'une tâche de priorité P3 lorsque le calendrier se tend.

**Ce qu'il ne fait pas**

- Il n'attribue pas les tâches : la répartition suit les périmètres techniques.
- Il ne décide pas des choix techniques internes à un périmètre.

### Scrum Master — Mouhameth DIOP

**Ce qu'il fait**

- Anime les réunions d'ouverture et de clôture de sprint, ainsi que le point à mi-parcours.
- Veille à ce que le tableau reflète l'avancement réel, et alerte le Product Owner dès qu'une carte est en retard sur la réalité.
- Suit les enchaînements de tâches et alerte dès qu'un retard menace la suite.
- Lève les blocages ou les fait remonter à l'équipe.

**Ce qu'il ne fait pas**

- Il ne décide pas des priorités ni du contenu du tableau : c'est le Product Owner.
- Il n'est pas responsable de l'avancement des autres : chacun répond de ses propres tâches.

### Conception et documentation — Ndeye Penda SARR

- Garante de la cohérence entre le dossier de conception et ce qui est réellement construit.
- Toute décision technique prise en cours de route est reportée dans le dossier : il ne doit jamais diverger de la réalisation.
- Prépare les supports de restitution de fin de sprint et de soutenance.

---

## 4. Les périmètres techniques

| Membre | Ce dont il ou elle répond | Fonctionnalités portées | Nombre |
|---|---|---|---|
| **Bachir DEME** | Composition des conteneurs, recherche en texte libre et filtres, modèle de prédiction du ré-achat, analyse de sentiment, chaîne complète de l'assistant | F3.2, F3.3, F3.4, F3.5, F3.6, F4.2, F4.3, F4.5, F4.7, F5.3, F5.4, F5.5, F5.6, F6.4 | 14 |
| **Ndeye Penda SARR** | Orchestration quotidienne et reprises, dictionnaire des indicateurs, tableau de bord, alertes, journalisation des exécutions | F2.1, F2.2, F2.3, F2.6, F2.7, F3.7, F4.6, F5.7, F6.1, F6.2, F6.3 | 11 |
| **Seydina WADE** | Zones de stockage et leurs schémas, règles de validation, quarantaine, taux de rejet, base documentaire, intégration continue et tests automatisés | F1.4, F1.5, F1.6, F1.11, F5.1, F5.2, F6.5 | 7 |
| **Aissata DIALLO** | Normalisation, décodage du balisage, détection de langue, déduplication, correspondance des produits, schéma en étoile, indexation du catalogue | F1.7, F1.8, F1.9, F1.10, F3.1, F4.1, F5.1 | 7 |
| **Mouhameth DIOP** | Chargement par lots, générateur d'événements, rejeu chronologique, bus d'événements, consommateur, compteurs du jour, journal des recherches | F1.1, F1.2, F1.3, F2.4, F2.5, F4.4 | 6 |

**Tâche partagée :** la rédaction de la foire aux questions (F5.1) est confiée à Seydina WADE et Aissata DIALLO. Elle est délibérément confiée à deux membres qui ne développent pas l'assistant, pour qu'elle ne dépende pas du calendrier de Bachir.

### 4.1 Rééquilibrage effectué en conception

Le périmètre initial de Bachir comptait dix-neuf fonctionnalités, soit près du double de tout autre membre. Six tâches périphériques ont été redistribuées en conception, chacune vers le membre dont elle prolonge naturellement le travail.

| Code | Fonctionnalité | Transférée à | Motif |
|---|---|---|---|
| F4.1 | Indexer le catalogue produits nettoyé | Aissata DIALLO | Elle produit le catalogue nettoyé en F1.7 : l'indexer en est la suite directe |
| F3.1 | Constituer l'historique d'achat par client | Aissata DIALLO | Agrégation sur le schéma en étoile qu'elle construit elle-même |
| F5.2 | Constituer la base documentaire | Seydina WADE | Elle s'assemble dans MongoDB, dont elle a la charge |
| F4.4 | Journaliser chaque requête de recherche | Mouhameth DIOP | Une requête de recherche est un événement, c'est le flux qu'il produit déjà |
| F4.6 | Mesurer le taux de requêtes sans résultat | Ndeye Penda SARR | Indicateur, donc rattaché au dictionnaire des indicateurs |
| F5.7 | Journaliser les questions et mesurer le volume traité | Ndeye Penda SARR | Même logique, et prolonge la journalisation des exécutions (F6.2) |

Bachir conserve le cœur de son périmètre : la recherche en texte libre et ses filtres, l'intégralité du modèle de rétention, et toute la chaîne de l'assistant. Il est déchargé de la plomberie qui l'entoure — indexation, journalisation et mesures.

### 4.2 Deux ajustements du Sprint 0

| Code | Fonctionnalité | Attribuée à | Motif |
|---|---|---|---|
| F6.4 | Démarrer la plateforme par conteneurs | Bachir DEME | Il écrit le fichier de composition des conteneurs au Sprint 0 |
| F6.5 | Exécuter automatiquement les tests à chaque contribution | Seydina WADE | L'intégration continue exécute d'abord les tests des règles de qualité, qui relèvent de son périmètre |

Répartition finale : Bachir 14, Ndeye Penda 11, Seydina 7, Aissata 7, Mouhameth 6.

---

## 5. Qui décide quoi

| Type de décision | Qui tranche |
|---|---|
| Priorité d'une fonctionnalité, contenu d'un sprint | Product Owner |
| Acceptation d'une fonctionnalité livrée | Product Owner |
| Abandon d'une tâche de priorité P3 | Product Owner, alerté par le Scrum Master |
| Calendrier, animation, suivi de l'avancement | Scrum Master |
| Choix technique interne à un périmètre | Le responsable du périmètre |
| Choix technique touchant plusieurs périmètres | Décision d'équipe, tranchée en réunion |
| Modification de l'architecture ou du dossier de conception | Ndeye Penda SARR, après accord de l'équipe |
| Fusion d'une contribution | Le relecteur de la demande de fusion |

En cas de désaccord persistant, la décision est prise à la réunion de sprint suivante, et le motif est consigné dans le dossier de conception.

---

## 6. Suppléance

Chaque périmètre a un suppléant désigné, capable de reprendre les tâches en cours en cas d'empêchement. Le suppléant est le relecteur privilégié des demandes de fusion du périmètre : c'est ainsi qu'il en garde la connaissance sans effort supplémentaire.

| Périmètre | Responsable | Suppléant | Raison |
|---|---|---|---|
| Recherche, ML et IA | Bachir DEME | Aissata DIALLO | Elle porte déjà l'indexation du catalogue et l'historique client |
| Acquisition et flux | Mouhameth DIOP | Seydina WADE | La collecte alimente directement les zones de stockage |
| Stockage et qualité | Seydina WADE | Mouhameth DIOP | Réciproque du précédent |
| Transformation et intégration | Aissata DIALLO | Ndeye Penda SARR | L'entrepôt est la source des indicateurs |
| Orchestration et restitution | Ndeye Penda SARR | Aissata DIALLO | Réciproque du précédent |

---

## 7. Règles de fonctionnement

- Une réunion d'équipe en début et en fin de sprint, animée par le Scrum Master : ce qui était prévu, ce qui a été réalisé, ce qui bloque.
- En fin de sprint, le Scrum Master présente ce qui a été fait et le Product Owner indique ce qui est accepté. C'est le moment où les deux rôles s'exercent réellement.
- Une tâche, un responsable unique. Les autres membres contribuent par la relecture, l'aide au déblocage et les tests.
- Toute contribution passe par une branche et une demande de fusion, relue par un membre d'un autre périmètre.
- Une tâche n'est close que lorsqu'elle est testée, relue, fusionnée et documentée — pas lorsque le code fonctionne sur le poste de son auteur.
- Une carte Trello non mise à jour est considérée comme non commencée.
- Les décisions de conception prises en cours de route sont reportées dans le dossier.

---

## 8. Ce qui reste commun à tous

Aucun périmètre n'est étanche.

- **La revue de code est croisée** : personne ne relit uniquement son propre domaine.
- **Git, Docker et les conventions d'équipe** ne sont le périmètre de personne : chacun les applique sur sa propre brique.
- **Une séance de restitution mutuelle** est organisée avant la soutenance. Chaque membre y présente son périmètre aux quatre autres, afin que tous puissent expliquer l'ensemble de la plateforme. Le jury pose ses questions au hasard, pas au spécialiste.

---

## 9. Point de vigilance

Bachir DEME cumule le rôle de Product Owner et le périmètre qui porte les livrables les plus visibles de la démonstration finale : la recherche, le modèle et l'assistant. Le rééquilibrage de la section 4.1 a réduit sa charge, qui reste toutefois la plus élevée de l'équipe, et la concentration des livrables de démonstration demeure.

Deux mesures restent en vigueur :

1. La tâche de priorité P3 qui reste dans son périmètre (F3.6) est désignée comme abandonnable si le calendrier se tend.
2. Aissata DIALLO, sa suppléante, porte désormais l'indexation du catalogue et l'historique client : elle connaît donc déjà une partie de la chaîne et peut en reprendre davantage si nécessaire.

Ces dispositions sont arrêtées à froid, en début de projet, précisément pour ne pas avoir à les décider dans l'urgence.
