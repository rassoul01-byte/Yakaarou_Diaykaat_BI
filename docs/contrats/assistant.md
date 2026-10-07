# Contrat — L'assistant client local

**Statut** : brouillon · **Responsable** : Bachir DEME · **Relecteur** : Seydina WADE · **Fonctionnalités** : F5.3 à F5.6 · **Sprint** : 5
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

**Règles pour l'interface**

- **Afficher les passages utilisés** (thème, question, source) pour chaque réponse : c'est un garde-fou du livrable, pas un détail de présentation.
- **Distinguer un refus d'une panne** : un refus est une réponse normale. Quand `suggestions` n'est pas vide, les afficher comme des choix.
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

**Masquage avant écriture** : adresses e-mail, numéros de téléphone, identifiants (mots d'au moins 5 caractères contenant un chiffre) et nombres de 4 chiffres ou plus. Un client peut taper son numéro de commande dans la question : il n'atteint jamais le fichier (test automatique).

**Taux de réponses ancrées** (dictionnaire) = échanges citant au moins un passage, plus les refus polis, divisé par les échanges. Il vaut 100 % **par construction** : il est mesuré sur le jeu de questions fixé, et le journal permet de le recalculer sur l'usage réel.

---

## 6. Évaluation et seuils

`python -m assistant.evaluer` rejoue le jeu `tests/assistant/jeu_de_questions.jsonl` et mesure, du plus grave au moins grave :

| Mesure | Sens | Attendu |
|---|---|---|
| **Réponse à tort** | Une question hors base reçoit une réponse | 0 |
| **Mauvais passage** | Une question couverte reçoit la réponse d'un autre passage : une réponse fausse, citée | 0 |
| Faux refus | Une question couverte est refusée sans suggestion | le plus bas possible |
| Bonne réponse, ou refus avec bonne suggestion | L'assistant oriente vers le bon passage | le plus haut possible |

### Résultat actuel : `RetrouveurDepannage`, seuils 0,35 / 0,18 / marge 0,12

Sur le jeu **provisoire** de 52 questions (27 couvertes, 25 hors base) :

| | |
|---|---|
| Bonne réponse | 9 |
| Refus avec la bonne suggestion | 15 |
| Faux refus | 3 |
| **Mauvais passage** | **0** |
| Refus correct (hors base) | 25 sur 25 |
| **Réponse à tort** | **0** |

### Ce que ces chiffres ne disent pas

- **Le jeu est provisoire.** Je l'ai écrit après avoir lu le corpus, ce qui flatte la mesure. Il doit être **gelé** avant toute mesure définitive, et une partie doit être écrite par quelqu'un d'autre (Seydina : dix questions pièges, sans que je les voie).
- **Les seuils ont été réglés sur ce jeu**, par validation croisée sur ses deux moitiés. Avec 27 questions couvertes, **zéro mauvais passage n'est pas garanti hors échantillon** : un autre réglage essayé en donnait 2 sur la moitié non vue. Le réglage retenu est le plus prudent.
- **Le coût de la prudence est assumé** : la recherche de dépannage ne répond directement qu'à environ une question couverte sur trois (9 sur 27) et suggère pour la plupart des autres. Parmi les 25 questions hors base, 5 reçoivent des suggestions peu pertinentes plutôt qu'un refus sec. C'est la limite d'une recherche lexicale, et ce qu'une recherche sémantique doit améliorer.
- Les trois faux refus actuels : « Quand l'argent sort-il de mon compte ? », « Qui supporte le coût de renvoi du colis ? », « Combien coûte un retour ? ».

### Pour refaire le réglage sur le jeu gelé

1. Geler le jeu (date et empreinte dans la PR), avant toute mesure.
2. Régler les seuils sur une partie, **mesurer sur l'autre**.
3. Choisir le réglage qui garde `réponse à tort` et `mauvais passage` à 0 ; accepter le surcroît de suggestions.
4. Écrire ici les seuils retenus et le jeu qui a servi.

---

## 7. Les commandes

```bash
docker compose exec app python -m assistant "Comment suivre ma commande ?"
docker compose exec app python -m assistant "Combien coûte un canapé ?" --json
docker compose exec app python -m assistant.evaluer --detail
```

`--sans-journal` évite l'écriture du journal.

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
| Brancher `documentaire.rechercher` derrière `RetrouveurExterne` et mesurer ses seuils sur le jeu gelé | Seydina | quand `rechercher.py` existe |
| Dix questions pièges, écrites sans que l'auteur les voie, puis gel du jeu | Seydina | avant le calibrage |
| Format du journal : confirmer qu'il suffit au calcul du taux d'ancrage et où il est lu | Ndeye Penda | avant l'intégration |
| Format de réponse (§3) : confirmer qu'il suffit à l'interface | Responsable de l'interface | dès la lecture de ce contrat |
| Libellé exact du « service client » dans les refus | Product Owner | avant la démonstration |
