# Contrat — Passages : la base documentaire vectorisée

**Statut** : brouillon · **Responsable** : Seydina WADE · **Relecteur** : Bachir DEME · **Fonctionnalité** : F5.2 · **Sprint** : 5

Ce contrat fixe ce que l'assistant de Bachir reçoit de la recherche de passages, avant que l'indexation soit écrite. Il prolonge `docs/contrats/faq.md` (F5.1) : la foire aux questions est la matière, les passages en sont la forme indexée.

## 1. Où se trouvent les éléments

| Élément | Emplacement |
|---|---|
| Source des passages | `docs/documentaire/faq.jsonl` (inchangée) |
| Politiques citées | `docs/documentaire/politiques.md` |
| Indexation | `src/documentaire/indexer.py` |
| Recherche | `src/documentaire/rechercher.py` |
| Index Elasticsearch | `faq_passages` |

## 2. Le découpage : un passage = une question-réponse

La foire aux questions est déjà découpée : **une ligne de `faq.jsonl` = un passage**. Il n'y a pas de découpage supplémentaire, parce que chaque réponse est complète et sans renvoi vers une autre question (règle du contrat F5.1). Un passage répond donc seul, et peut être cité seul.

Conséquence : le nombre de passages est le nombre de lignes de `faq.jsonl` (40 attendus).

## 3. Le passage indexé

| Champ | Contenu | Origine |
|---|---|---|
| `id` | identifiant du passage, par exemple `liv-01` | `id` de la ligne |
| `theme` | `livraison`, `retours`, `paiement`, `commande` ou `compte` | `theme` |
| `question` | la question d'origine | `question` |
| `reponse` | la réponse complète | `reponse` |
| `source` | `donnee:<table.colonne>` ou `politique:<nom>` | `source` |
| `maj` | date de mise à jour, `AAAA-MM-JJ` | `maj` |
| `texte` | `question` + saut de ligne + `reponse` : le texte réellement vectorisé | calculé |
| `vecteur` | représentation vectorielle de `texte` | calculé |

Pourquoi vectoriser la question **et** la réponse : une question de client reformulée ressemble à la fois à la question d'origine et aux mots de la réponse. Vectoriser les deux donne plus de chances de retrouver le bon passage.

## 4. Le modèle de vecteurs

Le même modèle sert à l'indexation et à la recherche : en changer impose `--recreer`.

| Point | Choix |
|---|---|
| Bibliothèque | `fastembed` |
| Modèle | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (multilingue, la FAQ est en français) |
| Dimension | 384 |
| Similarité | cosinus |

Vérifié dans `TextEmbedding.list_supported_models()` du conteneur. Alternatives disponibles si la qualité de recherche est insuffisante : `paraphrase-multilingual-mpnet-base-v2` (768) ou `multilingual-e5-large` (1024), plus lourds. **À valider avec Bachir.**

Limite connue : ce modèle ne lit qu'environ 128 mots par texte. Les réponses plus longues sont tronquées à la vectorisation (le texte complet reste dans l'index et dans les résultats).

## 5. L'index Elasticsearch

- Nom : `faq_passages`.
- `vecteur` : type `dense_vector`, 384 dimensions, similarité cosinus, indexé pour la recherche kNN.
- `id`, `theme`, `source` : type `keyword`.
- `question`, `reponse`, `texte` : type `text`.
- `maj` : type `date`.

## 6. L'idempotence de la réindexation

- L'identifiant du document Elasticsearch **est** l'`id` du passage. Réindexer un passage le remplace, il ne le duplique pas.
- Après indexation, les passages présents dans l'index mais absents de `faq.jsonl` sont supprimés : l'index reflète exactement le fichier.
- Lancer l'indexation deux fois de suite donne le même nombre de passages et les mêmes contenus.
- Avant d'indexer, `python -m documentaire.verifier` doit passer. L'indexeur refuse de lui-même un fichier illisible, un champ vide ou un identifiant en double : dans ces cas rien n'est indexé.

## 7. La recherche : ce que reçoit l'assistant

Entrée : une question en texte libre, et un nombre de passages à renvoyer (`k`, 3 par défaut).

Sortie : une liste de passages triés par pertinence décroissante, au format suivant.

```json
{
  "question_posee": "Quand vais-je recevoir mon colis ?",
  "resultats": [
    {
      "id": "liv-01",
      "theme": "livraison",
      "question": "Combien de temps faut-il pour recevoir ma commande ?",
      "reponse": "Le délai dépend de la région. À titre indicatif, il est calculé à partir des commandes déjà livrées.",
      "source": "donnee:fait_commande.delai_livraison_jours",
      "score": 0.82
    }
  ]
}
```

Règles :

- Chaque résultat porte sa `source`. L'assistant l'affiche telle quelle dans ses citations.
- `score` est celui d'Elasticsearch pour la similarité cosinus, soit (1 + cosinus) / 2 : entre 0 et 1, plus il est haut, plus le passage est proche.
- La liste peut être **vide** ou ne contenir que de faibles scores. C'est à l'assistant de décider qu'il ne sait pas.
- La recherche ne rédige jamais de réponse. Elle renvoie des passages, rien d'autre.

## 8. Le seuil « je ne sais pas »

Le seuil de score sous lequel aucun passage n'est considéré comme pertinent est une **décision partagée** avec Bachir, parce qu'elle commande le refus de l'assistant.

- Proposition : le fixer en mesurant les scores sur un jeu de questions couvertes et un jeu de questions hors base (prix, commande en cours, remboursement personnalisé), puis en choisissant la valeur qui sépare les deux.
- Le seuil choisi, et le jeu qui a servi à le choisir, sont écrits ici une fois décidés.

Seuil retenu : *à renseigner*.

## 9. Les commandes

```bash
docker compose exec app python -m documentaire.verifier
docker compose exec app python -m documentaire.indexer             # idempotent
docker compose exec app python -m documentaire.indexer --recreer   # si la structure change
docker compose exec app python -m documentaire.rechercher "ma question" -k 3
```

La recherche affiche le JSON du §7 ; code de sortie 0 même sans résultat, 1 si Elasticsearch ne répond pas.

## 10. Critères de réussite

- Les 40 passages sont indexés, chacun avec sa source.
- Une question posée autrement que dans la FAQ retrouve le bon passage dans les trois premiers résultats.
- Chaque passage remonte avec sa source.
- Réindexer deux fois donne le même état (test automatique).
- Un passage retiré de `faq.jsonl` disparaît de l'index à la réindexation.

## 11. Points ouverts

| Point | Avec qui | Échéance |
|---|---|---|
| Validation du modèle de vecteurs (MiniLM multilingue, 384) | Bachir | jour 3 |
| Seuil « je ne sais pas » | Bachir | quand l'assistant tourne sur les passages réels |
| Relecteur : `faq.md` indique Mouhameth DIOP, ce contrat Bachir DEME | équipe | à aligner dans `ROLES.md` |
