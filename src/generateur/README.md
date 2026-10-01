# Générateur d'événements de navigation

Ce paquet fabrique un flux d'événements de navigation (`page_vue`, `recherche`, `ajout_panier`, `achat`) conformes au **contrat d'événement v1**, puis les publie sur le bus Kafka. Une partie des événements est volontairement défectueuse, pour éprouver le contrôle du flux (dès ce sprint) et la recherche (Sprint 4).

```bash
docker compose exec app python -m generateur --debit 20 --duree 300 --graine 42
```

---

## 1. Organisation des fichiers

```
src/generateur/
├── __init__.py      # façade : ce que le reste du projet peut importer
├── donnees.py       # lit les fichiers réels (catalogue Rakuten, clients Olist)
├── simulateur.py    # le cœur : fabrique les événements, sans aucune entrée/sortie
├── __main__.py      # la ligne de commande : lit les options, publie sur le bus
└── README.md        # ce document

tests/generateur/
└── test_generateur.py   # vérifie forme, reproductibilité, taux et volume, sans Kafka
```

Le découpage suit une idée simple : **séparer ce qui est pur de ce qui touche au monde extérieur.**

| Couche | Fichier | Touche à… |
|---|---|---|
| Pure (aucune E/S) | `simulateur.py` | rien : ni fichier, ni Kafka, ni horloge réelle |
| Lecture de fichiers | `donnees.py` | le disque, uniquement en lecture |
| Bord du système | `__main__.py` | les arguments, l'horloge réelle, le bus Kafka |

Grâce à cela, les tests exercent tout le cœur avec de petites listes en mémoire, sans Kafka ni fichiers.

```
 fichiers CSV ──► donnees.py ──► listes Python ──┐
                                                  ▼
 options CLI ──► __main__.py ──► simulateur.py (Generateur) ──► événements
                      │                                             │
                      └──────────► common.bus.Publieur ◄────────────┘
                                          │
                       navigation.evenements  /  navigation.rebut
```

---

## 2. `__init__.py`

Réexporte les cinq noms utiles : `Generateur`, `Parametres`, `Evenement`, `Statistiques`, `est_invalide`. Un autre module écrit `from generateur import Generateur` sans connaître le détail des fichiers.

---

## 3. `donnees.py` : les données réelles

Il rend le flux crédible. Deux fonctions, toutes deux en lecture seule, avec le module `csv` de la bibliothèque standard.

**`charger_produits(chemin)`** lit le catalogue Rakuten et renvoie une liste `[(id_produit, designation), ...]`.
- Colonnes lues : `productid` et `designation` (modifiables par paramètres).
- Une ligne est gardée seulement si `productid` ne contient que des chiffres et si la désignation est non vide. Les doublons d'identifiant sont ignorés (le premier gagne).
- L'identifiant **reste du texte**, jamais converti en nombre, comme l'impose le contrat.

**`charger_clients(chemin)`** lit le fichier clients Olist et renvoie la liste des `customer_unique_id` distincts.
- Seule la colonne `customer_unique_id` est lue. La colonne `customer_id`, qui identifie une **commande**, n'est jamais utilisée : c'est la règle « identifiant de personne, jamais de commande ».
- Une valeur n'est gardée que si elle fait exactement 32 caractères hexadécimaux.

Dans les deux cas, un fichier sans aucune ligne exploitable lève une `ValueError` explicite.

---

## 4. `simulateur.py` : le cœur

C'est le fichier important. Il ne fait **aucune entrée/sortie**. Tout le hasard vient d'un unique `random.Random(graine)`, et le temps est simulé : c'est ce qui rend deux lancements identiques avec la même graine.

### 4.1 Les briques

| Élément | Rôle |
|---|---|
| `Parametres` | Les réglages : graine, date de début, événements par jour simulé, proportions par type, taux de défauts, etc. Il valide ses valeurs dès la création (taux entre 0 et 1, types connus, date avec fuseau…). |
| `Evenement` | Un couple `(contenu, defaut)`. `contenu` est le dictionnaire envoyé sur le bus. `defaut` est le nom du défaut injecté, ou `None`. Le nom du défaut n'est **jamais** dans le message : c'est une information de test, hors contrat (un champ inconnu ferait refuser le message). |
| `Statistiques` | Compte les événements par type et par défaut, et compare ce que le bus a accepté ou refusé avec ce que le générateur attendait. |
| `Generateur` | Produit le flux infini d'événements (voir 4.2). |
| `_Session` | Mémoire d'une session : identifiant, client éventuel, dernier produit vu, produit au panier. |
| `est_invalide(defaut)` | Dit si un défaut viole le contrat (donc part au rebut). |
| `mots_de_designation(texte)` | Découpe une désignation en mots : minuscules, entités HTML décodées (`&amp;`), ponctuation retirée, mots d'au moins 2 lettres, 12 mots au maximum. |

### 4.2 Fabrication d'un événement (`Generateur._suivant`)

Chaque appel suit toujours les mêmes étapes, dans cet ordre :

1. **Avancer l'horloge simulée.** L'écart suit une loi exponentielle, dont la moyenne vaut `86 400 s ÷ evenements_par_jour`. Les événements arrivent donc de façon irrégulière, comme dans la réalité, et une journée simulée contient environ le volume demandé.
2. **Choisir le type** (`page_vue`, `recherche`, `ajout_panier`, `achat`) par tirage pondéré selon les proportions.
3. **Choisir la session** : avec la probabilité `proba_nouvelle_session` (ou s'il n'y en a aucune), on en ouvre une nouvelle (`s-000001`, `s-000002`…). Sinon on reprend une session active au hasard. Une nouvelle session est identifiée dès le départ avec la probabilité `part_clients_connus`, sinon elle est anonyme.
4. **Remplir les champs selon le type** :
   - `page_vue` : un produit du catalogue, mémorisé comme « dernier produit vu ».
   - `recherche` : une requête construite depuis le catalogue (voir 4.3).
   - `ajout_panier` : dans 70 % des cas le dernier produit vu, sinon un autre produit ; il est mémorisé comme « au panier ».
   - `achat` : si la session est anonyme, un client est tiré (la personne « se connecte » en cours de session) ; le produit acheté est celui du panier, qui est ensuite vidé.
5. **Assembler le dictionnaire** avec exactement les huit champs du contrat. L'identifiant `id_evenement` est un UUID v4 fabriqué à partir du générateur seedé, donc reproductible ; l'horodatage est en UTC, suffixe `Z`, millisecondes.
6. **Injecter un défaut** avec la probabilité `taux_defauts` (voir 4.4).
7. **Éventuellement clore la session** avec la probabilité `proba_fin_session`.

Le `customer_unique_id` de la session est recopié sur tous ses événements, pas seulement sur l'achat.

### 4.3 Les produits et les requêtes

- **Produit** : le choix suit une loi de puissance (`indice = taille × aléa³`) : quelques produits sont très consultés, la plupart très peu. C'est plus réaliste qu'un tirage uniforme.
- **Requête** : on prend un produit, on extrait 2 à 4 mots consécutifs de sa désignation nettoyée, et on les joint par des espaces. Une requête est donc toujours faite de vrais mots du catalogue.

### 4.4 Les défauts volontaires

Deux familles, avec une conséquence différente pour le bus :

**Défauts qui restent valides** (le bus les laisse passer ; ils servent à éprouver la recherche au Sprint 4). Ils ne s'appliquent qu'aux événements `recherche`.

| Défaut | Ce que ça fait |
|---|---|
| `faute_frappe` | Altère un mot de 4 lettres ou plus : suppression, doublement, transposition ou remplacement d'une lettre. Le résultat est toujours différent de l'original. |
| `requete_introuvable` | Remplace la requête par 6 à 10 consonnes sans voyelle : aucun mot réel ne peut correspondre. |

**Défauts qui violent le contrat** (le bus doit les écarter vers `navigation.rebut`). Ils peuvent toucher n'importe quel type.

| Défaut | Ce que ça fait |
|---|---|
| `champ_manquant` | Retire le champ obligatoire du type : mis à `null`, supprimé entièrement, ou, pour une recherche, vide (`""`). |
| `horodatage_sans_fuseau` | Enlève le `Z` : `2026-09-01T00:00:03.030`. |
| `horodatage_futur` | Ajoute 18 000 à 36 000 jours (50 à 100 ans), donc toujours dans le futur **réel**, quelle que soit la date de début simulée. |
| `horodatage_ancien` | Une date antérieure au 1er janvier 2016. |
| `horodatage_illisible` | Un format non ISO : `01/09/2026 00:00`. |

À l'intérieur d'un événement défectueux, le défaut est tiré à parts égales parmi ceux qui s'appliquent à son type.

### 4.5 `Statistiques`

`enregistrer(evenement, accepte)` compte l'événement et, si le bus a répondu, compare :
- `rebutes_a_tort` : un événement que nous jugeons valide a été refusé ;
- `acceptes_a_tort` : un événement que nous jugeons invalide a été accepté.

La propriété `coherent` est vraie quand ces deux compteurs valent zéro : c'est le critère « les événements défectueux sont bien écartés, et eux seuls ».

---

## 5. `__main__.py` : la ligne de commande

C'est le seul fichier qui touche à l'horloge réelle et à Kafka. Il ne contient aucune logique de génération.

| Fonction | Rôle |
|---|---|
| `analyser_arguments` | Définit et lit les options (tableau ci-dessous). |
| `_proportions` | Convertit `page_vue=0.5,recherche=0.3` en dictionnaire. |
| `_date` | Convertit une date ISO 8601 en date avec fuseau (UTC si rien n'est précisé). |
| `main` | Orchestre le lancement (voir ci-dessous). |

**Déroulement de `main` :**
1. Lit les options et fixe la graine (tirée au hasard et **affichée** si `--graine` est absent, pour pouvoir rejouer).
2. Calcule le nombre d'événements : `débit × durée`.
3. Vérifie que la fin de la simulation ne dépasse pas l'heure réelle, sinon le contrat refuserait les horodatages : le script s'arrête avec le code 2.
4. Charge les données et crée le `Generateur`.
5. Importe `common.bus.Publieur` **à ce moment-là seulement**, pour que les tests n'aient pas besoin de Kafka.
6. Pour chaque événement : attend le bon moment (`départ + i ÷ débit`, sauf avec `--sans-pause`), publie, puis enregistre la réponse du bus (`True` ou `False`) dans les statistiques.
7. Affiche le bilan ; en cas d'incohérence, le message `INCOHÉRENCE` sort sur l'erreur standard et le code de retour vaut 1.

| Option | Défaut | Rôle |
|---|---|---|
| `--debit` | 20 | Événements par seconde **réelle** |
| `--duree` | 300 | Durée réelle en secondes |
| `--graine` | aléatoire, affichée | Rend le lancement reproductible |
| `--taux-defauts` | 0.05 | Part des événements défectueux |
| `--proportions` | 0.50 / 0.30 / 0.15 / 0.05 | Parts de `page_vue`, `recherche`, `ajout_panier`, `achat` |
| `--evenements-par-jour` | 30 000 | Rythme **simulé** (le dossier vise 10 000 à 50 000) |
| `--debut` | 2026-09-01 | Début de la simulation, obligatoirement dans le passé |
| `--catalogue` | `data/rakuten/X_train_update.csv` (ou `CATALOGUE_RAKUTEN`) | Fichier Rakuten |
| `--clients` | `data/olist/olist_customers_dataset.csv` (ou `CLIENTS_OLIST`) | Fichier Olist |
| `--sans-pause` | désactivé | Publie sans respecter le débit |

Deux notions à ne pas confondre : le **débit** règle la vitesse réelle de publication, alors que `--evenements-par-jour` règle l'écart entre les horodatages simulés. Avec les valeurs par défaut, 6 000 événements sont publiés en 5 minutes, et leurs horodatages couvrent environ 4 h 48 de temps simulé.

Codes de retour : `0` tout va bien, `1` incohérence avec le bus, `2` date de début trop récente.

---

## 6. `tests/generateur/test_generateur.py`

Aucun Kafka, aucun fichier : le catalogue et les clients sont de petites listes écrites dans le test. Le fichier contient aussi `erreurs_contrat`, une relecture indépendante des règles du contrat, qui joue le rôle du bus.

| Test | Ce qu'il vérifie |
|---|---|
| reproductibilité | Même graine ⇒ mêmes événements ; graines différentes ⇒ événements différents |
| conformité | Sans défaut, tous les événements respectent le contrat ; parmi les défauts, ceux dits invalides sont bien détectés et ceux dits valides restent conformes |
| achat | Toujours un client identifié |
| données | Produits et clients viennent bien des listes fournies ; requêtes faites de mots du catalogue ; une faute de frappe sort du vocabulaire |
| taux | Le taux de défauts et les proportions de types sont respectés (à quelques points près) |
| volume | Pour 10 000, 30 000 et 50 000 événements par jour, les horodatages couvrent environ 24 h et croissent ; 50 000 événements ont tous un identifiant unique |
| divers | Paramètres invalides refusés ; `Statistiques` détecte les incohérences ; la ligne de commande du dossier est bien analysée |

Pour les lancer, `src` doit figurer dans le chemin de pytest (par exemple `pythonpath = src`) :

```bash
pytest tests/generateur
```

---

## 7. Points à valider avec le reste de l'équipe

- L'appel `publieur.publier(evt.contenu)` suppose que `Publieur.publier` accepte un dictionnaire.
- `erreurs_contrat` (dans les tests) reformule le contrat : il faut le confronter à la validation de `src/common/evenements.py`, qui fait foi.
- Les chemins par défaut des deux fichiers de données sont des hypothèses.
