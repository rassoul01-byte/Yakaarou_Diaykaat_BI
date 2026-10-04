# Contrat — Base documentaire : la foire aux questions

**Statut** : brouillon · **Responsable** : Seydina WADE · **Relecteur** : Mouhameth DIOP · **Fonctionnalité** : F5.1 · **Sprint** : 4

La foire aux questions est la matière première de l'assistant du Sprint 5. Ce contrat fixe son format avant qu'elle soit écrite, pour que l'assistant puisse la lire telle quelle.

## 1. Où se trouvent les fichiers

| Élément | Emplacement |
|---|---|
| Les questions-réponses | `docs/documentaire/faq.jsonl` |
| La commande de vérification | `src/documentaire/verifier.py` |

## 2. Le format : une question par ligne

Le fichier est au format JSON Lines : **une ligne = un objet JSON = une question-réponse**. Une ligne se lit, se vérifie et se charge indépendamment des autres, et elle correspond naturellement à un morceau de texte à indexer au Sprint 5.

| Champ | Contenu | Obligatoire |
|---|---|---|
| `id` | identifiant unique : `liv-01`, `ret-03`, `pai-02`, `cmd-05`, `cpt-04` | oui |
| `theme` | `livraison`, `retours`, `paiement`, `commande` ou `compte` | oui |
| `question` | la question, telle qu'un client la poserait | oui |
| `reponse` | la réponse complète, en français, sans renvoi vers une autre question | oui |
| `source` | d'où vient la réponse (voir §3) | oui |
| `maj` | date de dernière mise à jour, au format `AAAA-MM-JJ` | oui |

Exemple (une seule ligne dans le fichier) :

```json
{"id": "liv-01", "theme": "livraison", "question": "Combien de temps faut-il pour recevoir ma commande ?", "reponse": "Le délai dépend de la région. À titre indicatif, il est calculé à partir des commandes déjà livrées.", "source": "donnee:fait_commande.delai_livraison_jours", "maj": "2026-10-05"}
```

## 3. Le champ `source`

Une réponse écrite à la main doit pouvoir être justifiée. Deux formes sont acceptées :

- `donnee:<table.colonne>` : la réponse s'appuie sur un chiffre réel de l'entrepôt (par exemple `donnee:fait_commande.delai_livraison_jours`). C'est la forme à privilégier pour la livraison, le paiement et le statut des commandes.
- `politique:<nom>` : la réponse décrit une règle de la boutique décidée pour le projet (par exemple `politique:retours`). Chaque politique est résumée une fois dans `docs/documentaire/politiques.md`, et les réponses la citent sans la contredire.

## 4. Volume et répartition

| Critère | Valeur |
|---|---|
| Total | entre 30 et 50 questions, **cible : 40** |
| Par thème | au moins 5, **cible : 8** |
| Thèmes | livraison, retours, paiement, commande, compte |

## 5. La commande de vérification

```bash
docker compose exec app python -m documentaire.verifier
```

Elle renvoie le code **1** et un message clair si l'un de ces contrôles échoue, sinon le code **0** :

- chaque ligne est un JSON valide avec les six champs, aucun vide ;
- les `id` sont uniques ;
- le `theme` est l'un des cinq autorisés ;
- le préfixe de l'`id` correspond au thème (`liv` pour livraison, `ret`, `pai`, `cmd`, `cpt`) ;
- la `source` commence par `donnee:` ou `politique:` ;
- la date `maj` est valide ;
- le total est entre 30 et 50, et chaque thème en compte au moins 5 ;
- aucune question n'apparaît deux fois.

Elle affiche aussi le compte par thème.

## 6. Critères de réussite

- La commande de vérification renvoie le code 0 sur le fichier final.
- Chaque question-réponse a un thème et une source.
- Le volume cible est atteint : 40 questions, 8 par thème.
- Les réponses citant une donnée sont cohérentes avec l'entrepôt.
- Les tests de la commande de vérification passent, avec un cas par contrôle qui échoue.

## 7. Hors périmètre

Aucune vectorisation, aucun assistant, aucune recherche sémantique : Sprint 5. Aucune traduction : les réponses sont en français.

## 8. Points à trancher

- [ ] **Format JSON Lines** : il se vérifie bien, mais il est moins agréable à écrire à la main qu'un tableau. À valider avec l'équipe, car le Sprint 5 le lira.
- [ ] **Place des politiques** : un fichier `politiques.md` résume les règles de la boutique, ou les réponses portent directement la règle.
- [ ] **Validation du contenu** : qui relit la justesse des réponses fondées sur des données.
