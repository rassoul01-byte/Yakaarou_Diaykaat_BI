# Contrat — L'assistant client local

**Statut** : stable (seuils mesurés le 2026-10-07 sur le jeu gelé, §6) · points ouverts au §9 · **Responsable** : Bachir DEME · **Relecteur** : Seydina WADE · **Fonctionnalités** : F5.3 à F5.6 · **Sprint** : 5
**Modules** : `src/assistant/` · **Lecteurs** : Seydina (recherche de passages), Ndeye Penda (journal, taux d'ancrage), la personne chargée de l'interface

---

## 1. Ce que fait l'assistant, en une phrase

Il **sélectionne et cite** : il retrouve des passages de la foire aux questions et répond avec le texte du passage retenu, suivi de sa citation, ou il refuse. **Il ne rédige rien.**

Conséquence : une réponse est exacte par construction. « Aucune réponse ne contient d'information absente des passages cités » n'est pas vérifié après coup, c'est impossible à violer : une réponse qui n'est pas exactement le texte de ses passages ne peut pas être construite (invariant de `Reponse`, testé).

> Ce qui est entraîné et réglé par l'équipe : la recherche de passages, le lexique métier, les règles de refus et les seuils. Ce qui ne l'est pas : un modèle qui génère du texte. Le corpus fait environ 1 300 mots, trop peu pour cela, et un texte généré ne garantirait rien.

---

## 2. Ce qu'il répond et ce qu'il refuse

**Il répond** aux questions **générales** couvertes par les passages de `docs/documentaire/faq.jsonl` (40 passages, 5 thèmes).

**Il refuse**, avec un texte fixe qui renvoie au service client :

| Motif | Quand | Étape |
|---|---|---|
| `prix` | Le client demande un prix (« Combien coûte… ? »). Le catalogue n'en contient aucun | Règle, avant la recherche |
| `commande_precise` | La question porte un identifiant (commande, colis, paiement) | Règle, avant la recherche |
| `remboursement_personnalise` | Un remboursement chiffré ou à la première personne (« rembourse-moi », « 50 euros ») | Règle, avant la recherche |
| `question_invalide` | Question vide, sans mot, ou de plus de 500 caractères | Règle, avant la recherche |
| `aucun_passage` | La recherche ne ramène rien | Après la recherche |
| `hors_base` | Le meilleur passage est trop éloigné | Après la recherche |
| `incertain` | Le meilleur passage est moyen, ou deux passages sont trop proches pour choisir : l'assistant **propose jusqu'à trois questions** au lieu de deviner | Après la recherche |

**La frontière « général » ou « personnel ».** « Quel est le délai de remboursement ? » est général : la base répond. « Rembourse-moi 50 euros pour la commande 8f3a2c » est personnel : la base ne peut rien en dire. Les règles ne refusent que sur un **signe explicite** (un identifiant, un montant, un impératif). Dans le doute, elles laissent passer et le seuil de la recherche tranche. Le jeu de questions contient des questions générales voisines des règles (« Combien coûte un retour ? ») précisément pour vérifier qu'elles ne sont pas refusées à tort.

**Un refus est une réponse correcte, pas une erreur.** Les textes de refus sont écrits dans `compositeur.py`. Aucun ne contient d'adresse, de numéro de téléphone ni de lien : le corpus n'en contient pas, et on n'en invente pas.

---

## 3. Le format de réponse (ce que reçoit l'interface)

```json
{
  "question": "Comment suivre ma commande ?",
  "refus": false,
  "motif": null,
  "reponse": "Le statut de votre commande est visible dans la rubrique commandes de votre compte. […] [liv-03]",
  "passages": [
    {"id": "liv-03", "theme": "livraison", "question": "Comment suivre ma commande ?",
     "source": "donnee:fait_commande.statut", "score": 0.61}
  ],
  "suggestions": [],
  "duree_ms": 12
}
```

| Champ | Contenu |
|---|---|
| `refus` | `true` pour un refus, `false` pour une réponse |
| `motif` | Le motif du tableau du §2 si `refus`, sinon `null` |
| `reponse` | Le texte à afficher : le passage plus sa citation, ou le texte fixe du refus |
| `passages` | Les passages qui **fondent** la réponse ; **vide pour tout refus** |
| `suggestions` | Les questions proposées quand `motif` vaut `incertain` ; sinon vide |
| `duree_ms` | Temps de traitement |

**Ce que l'interface envoie** (`POST /api/assistant/ask`)

| Champ | Contenu | Obligatoire |
|---|---|---|
| `question` | La question posée, 1 à 500 caractères | oui |
| `k` | Nombre de passages à considérer (1 à 10, défaut 3) | non |
| `origine` | `saisie`, `exemple` ou `suggestion` — d'où vient la question (défaut `saisie`) | non |
| `reformulation` | Ce que l'utilisateur avait écrit avant de cliquer une suggestion | non |

`origine` et `reformulation` **ne changent pas la réponse** : ils ne servent qu'au journal (§5). Quand l'utilisateur clique une suggestion, l'interface envoie la question du passage en `question` et **ses mots à lui** en `reformulation` ; ailleurs, `reformulation` est nulle, car la question *est* déjà sa formulation.

**Règles pour l'interface**

- **Afficher les passages utilisés** (thème, question, source) pour chaque réponse : c'est un garde-fou du livrable, pas un détail de présentation.
- **Distinguer un refus d'une panne** : un refus est une réponse normale. Quand `suggestions` n'est pas vide, les afficher comme des choix.
- **Les suggestions doivent être cliquables**, et le clic repose la question du passage avec `origine: "suggestion"`. Affichées en texte mort, elles montrent à l'utilisateur la réponse qu'il cherche sans lui donner le moyen de l'ouvrir — et le couple (ses mots, le passage qui lui convenait) est perdu.
- **Les questions d'exemple de la page doivent être des questions que la recherche traite bien.** Une page qui propose une question qu'elle rate se discrédite seule.
- **Passer par `assistant.repondre()`** (ou `python -m assistant --json`), jamais par une copie de la logique : c'est ce qui garantit que le journal voit tous les échanges, avec son masquage.
- **Rien ne doit être chargé depuis Internet** : l'assistant est local.

**Code de sortie de la commande** : `0` si l'assistant répond **ou refuse** ; `1` si une panne technique l'en empêche (foire aux questions illisible, journal impossible à écrire). C'est l'inverse de `recherche.chercher`, car ici un refus est le bon comportement.

---

## 4. L'interface de la recherche de passages

L'assistant n'appelle pas une recherche en particulier : il appelle `retrouver(question, k)` (`assistant.retrouveur.Retrouveur`) et reçoit des passages triés du plus au moins proche, avec leur score entre 0 et 1. Format : celui de `docs/contrats/passages.md`, §7.

| Réalisation | Rôle |
|---|---|
| `RetrouveurDepannage` | Recherche lexicale en mémoire (mots et lettres, plus le lexique métier). **Provisoire**, écrite pour ne pas être bloqué |
| `RetrouveurExterne` | Adaptateur vers `documentaire.rechercher` de Seydina, qui rend le JSON du §7. **C'est cette version qui part en démonstration** |

L'adaptateur **vérifie** ce que promet le contrat : champs présents, scores entre 0 et 1, tri décroissant. Une réponse hors contrat lève une erreur au lieu d'être devinée.

**Les seuils sont propres à chaque recherche** : un score lexical ne ressemble pas à un cosinus. `RetrouveurExterne` **exige** ses seuils (pas de valeur par défaut) : ils se mesurent sur le jeu fixé, comme le demande `passages.md`, §8.

---

## 5. Le journal (pour le taux de réponses ancrées, F5.7)

Une ligne JSON par échange, dans `data/assistant/journal.jsonl` (variable `ASSISTANT_JOURNAL`) :

| Champ | Contenu |
|---|---|
| `horodatage` | Date et heure UTC |
| `question` | La question, **après masquage** |
| `refus`, `motif` | Comme dans le §3 |
| `passages_cites` | Les identifiants des passages (pas leur texte) |
| `score_meilleur` | Score du passage cité, ou `null` |
| `suggestions` | Identifiants proposés |
| `duree_ms`, `retrouveur` | Temps de traitement et nom de la recherche |
| `origine` | `saisie`, `exemple` ou `suggestion` (§3) |
| `reformulation` | Les mots de l'utilisateur avant un clic sur une suggestion, **après masquage** ; `null` sinon |

**Masquage avant écriture** : adresses e-mail, numéros de téléphone, identifiants (mots d'au moins 5 caractères contenant un chiffre) et nombres de 4 chiffres ou plus. Un client peut taper son numéro de commande dans la question : il n'atteint jamais le fichier (test automatique). La `reformulation` est masquée de la même façon — c'est aussi du texte tapé par un client.

**À quoi sert la provenance.** Sur le jeu gelé du 2026-10-07, la recherche trouve le bon passage pour la grande majorité des questions couvertes mais le seuil ne permet d'en affirmer qu'une fraction : pour les autres, l'assistant propose. Chaque clic sur une suggestion est donc une étiquette posée par un humain — *cette formulation voulait dire ce passage* — et c'est la seule source de vocabulaire **client** dont nous disposions. Les mots de la foire aux questions, eux, sont déjà dans l'index (`documentaire.mots_cles` les en extrait).

**Rien n'entre dans `faq.jsonl` automatiquement.** La vue `staging.v_reformulations` sert à une relecture humaine, pour deux raisons : le masquage peut abîmer une formulation (`iphone13` devient `[identifiant]`), et un journal appliqué sans relecture serait une porte d'entrée — une phrase tapée exprès finirait indexée.

**Taux de réponses ancrées** (dictionnaire) = échanges citant au moins un passage, plus les refus polis, divisé par les échanges. Il vaut 100 % **par construction** : il est mesuré sur le jeu de questions fixé, et le journal permet de le recalculer sur l'usage réel.


**Chargement dans PostgreSQL (décidé le 2026-10-08).** Power BI ne lit pas le fichier : il lit des vues PostgreSQL, comme pour toutes les autres pages, par le compte en lecture seule. Le journal est donc chargé dans `staging.journal_assistant` (migration `020_journal_assistant.sql`) par `python -m assistant.charger_journal` :

| Source | Contenu | Chargement |
|---|---|---|
| `evaluation` | Le jeu gelé rejoué par `assistant.evaluer --journal` : c'est la **mesure** du dictionnaire | Remplace l'évaluation précédente : un rejeu ne gonfle pas les chiffres |
| `usage` | Les questions posées à la main, par exemple en démonstration | Ajoute sans jamais doubler : une ligne déjà chargée (même empreinte) est ignorée |

La question est masquée une seconde fois au chargement. Une ligne illisible est signalée avec son numéro, jamais ignorée en silence. Les vues `staging.v_taux_ancrage` (par jour) et `staging.v_taux_ancrage_global` donnent, pour chaque source : les échanges, les réponses directes, les refus et le taux. Comme il vaut 100 % par construction, la page doit montrer les **réponses directes et les refus**, pas seulement le pourcentage.

La migration `023_journal_provenance.sql` ajoute les colonnes `origine` et `reformulation`, plus deux vues :

| Vue | Contenu |
|---|---|
| `staging.v_reformulations` | Les paires (formulation du client, passage retenu), avec le nombre d'échanges : la liste à relire avant d'enrichir la foire aux questions |
| `staging.v_part_suggestions` | La part des échanges servis via une suggestion plutôt que directement. C'est l'indicateur qui doit **baisser** à mesure que la base s'enrichit |

Un journal écrit avant cette migration se charge sans erreur : l'origine manquante vaut `saisie`.

---
## 6. Seuils

Mesurés sur le jeu **gelé** le 2026-10-07 (empreinte SHA256 :
`786dada1d1874e139d0376b7ff148c957762ffa16a77d1524f99c3700f4e0dbd`),
avec la recherche documentaire (`documentaire.rechercher`, retrouveur
`RetrouveurExterne`).

| Seuil | Valeur |
|---|---|
| `reponse` | 0,84 |
| `suggestion` | 0,20 |
| `marge` | 0,00 |

### Résultats obtenus sur le jeu gelé (62 questions, 31 couvertes)

| Verdict | Nombre |
|---|---|
| Bonne réponse directe | 6 |
| Refus avec bonne suggestion | 23 |
| Faux refus | 2 |
| Refus correct (hors base) | 31 |
| **Mauvais passage** | **0** ✅ |
| **Réponse à tort** | **0** ✅ |

Ces zéros valent **sur ce jeu**, pas au-delà : voir « Limites connues » ci-dessous.

### Justification de la marge à 0

Le retrouveur vectoriel produit des cosinus très proches entre les top
passages (écart médian top 1 / top 2 ≈ 0,02). Une marge non nulle
éliminerait des réponses correctes sans gain mesurable en précision.

### Limites connues

- **2 faux refus inévitables** : q05 (« J'ai reçu le mauvais article ») et
  s07 (« Ma commande passée en 2026 est arrivée cassée »). Leur passage
  attendu n'apparaît pas dans le top 5 du retrouveur — aucun seuil ne peut
  les sauver. C'est une limite du retrouveur actuel.
- **« 0 sur le jeu » n'est pas une garantie.** Les seuils ont été réglés sur ce jeu,
  qui ne compte que 31 questions couvertes : zéro mauvais passage et zéro réponse à
  tort ne sont pas assurés sur des questions que personne n'a vues. Une validation
  croisée sur deux moitiés du jeu (réglage sur l'une, mesure sur l'autre) a d'ailleurs
  donné une erreur grave pour certains réglages voisins.
- **Le seuil de réponse est proche d'une erreur connue.** À la collecte du 7 octobre,
  le plus haut score d'un premier résultat faux était de 0,8391 (« Combien coûte un
  retour ? »), soit moins de 0,001 sous le seuil de 0,84. Un réglage à 0,85 aurait un
  peu plus de marge de sécurité, au prix de quelques réponses directes en moins.
- **Piste d'amélioration (Sprint 6)** : ajouter un reranker cross-encoder
  après la recherche vectorielle.

### Pour refaire le réglage

```bash
docker compose exec app python -m scripts.assistant.mesurer_scores
docker compose exec app python -m scripts.assistant.analyser_scores
docker compose exec app python -m scripts.assistant.balayer_seuils --top 30
```

---

## 7. Les commandes

```bash
docker compose exec app python -m assistant "Comment suivre ma commande ?"
docker compose exec app python -m assistant "Combien coûte un canapé ?" --json
docker compose exec app python -m assistant.evaluer --detail
```

`--sans-journal` évite l'écriture du journal.

Pour alimenter la page Assistant de Power BI :

```bash
docker compose exec app python -m assistant.evaluer --journal
docker compose exec app python -m assistant.charger_journal --source evaluation
docker compose exec app python -m assistant.charger_journal --source usage
```

---

## 8. Limites connues

- L'assistant ne comprend que le **français** : une question dans une autre langue est le plus souvent refusée (`hors_base`).
- Il ne répond **jamais** sur un prix, une commande précise ou un remboursement personnalisé, et ne donne aucune coordonnée : il renvoie au « service client » sans l'identifier, le corpus n'en contenant pas.
- Les chiffres que citent certains passages (délai moyen, parts de commandes) viennent de l'entrepôt au moment de l'écriture de la foire aux questions. L'assistant les restitue, il ne les recalcule jamais ; ils peuvent vieillir (`maj` dans `faq.jsonl`).
- Une question qui mêle deux thèmes reçoit au mieux la réponse du passage le plus proche, ou des suggestions.

---

## 9. Points ouverts

| Point | Avec qui | Échéance |
|---|---|---|
| ~~Brancher `documentaire.rechercher` derrière `RetrouveurExterne` et mesurer ses seuils sur le jeu gelé~~ | Seydina | **fait le 2026-10-07** (`fabrique.py`, seuils au §6) |
| ~~Dix questions pièges, écrites sans que l'auteur les voie, puis gel du jeu~~ | Seydina | **fait le 2026-10-07** (62 questions, empreinte au §6) |
| ~~Format du journal : confirmer qu'il suffit au calcul du taux d'ancrage et où il est lu~~ | Ndeye Penda | **décidé le 2026-10-08** : le journal est chargé dans PostgreSQL (§5, migration 020), lu par Power BI via `staging.v_taux_ancrage` |
| Format de réponse (§3) : confirmer qu'il suffit à l'interface | Responsable de l'interface | dès la lecture de ce contrat |
| Libellé exact du « service client » dans les refus | Product Owner | avant la démonstration |
