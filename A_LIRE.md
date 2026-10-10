# Correctif frontend et performance — 10 octobre

Décompresser à la racine du dépôt, par-dessus les fichiers existants.

```powershell
Expand-Archive -Path .\correctif_frontend.zip -DestinationPath . -Force
```

## Ce qu'il faut lancer dans l'ordre

```powershell
# 1. La migration SQL. Elle ne touche à aucune donnée : trois vues remplacées.
python scripts/appliquer_sql.py

# 2. Les dépendances du front ont changé (recharts retiré, police ajoutée).
docker compose up -d --force-recreate frontend

# 3. Vérifier.
python -m pytest -m "not integration" -q          # 808 attendus
python -m pytest -m integration tests/integration tests/indicateurs tests/quality -q   # 83 + 2 ignorés
```

Puis ouvrir http://localhost:5173.

## Ce qui a changé, et pourquoi

### 1. La page du tableau de bord était lente à cause d'un seul nombre

Le « 711 clients » du segment coûtait **2,1 s sur les 2,7 s de SQL de la page**,
et 1,18 million de pages tampon — neuf gigaoctets de trafic mémoire pour compter
711 lignes.

La cause n'était pas le volume. `v_segment_a_retenir` lisait
`v_historique_client`, qui calcule les seize variables du modèle de ré-achat
dans sept CTE ; le segment n'en utilise que cinq colonnes, toutes issues de la
première. Les six autres étaient calculées puis jetées. Et la CTE `croisement`,
référencée sept fois donc matérialisée, empêchait le filtre sur la date de
descendre : les cinq fenêtres d'évaluation étaient croisées avec les 96 096
personnes, 185 359 lignes écrites sur disque, pour n'en garder qu'une à la fin.

`sql/028_socle_client.sql` fusionne `croisement` et `passe` en une vue,
`dwh.v_socle_client`. `v_historique_client` et `v_segment_a_retenir` s'y
assoient tous les deux.

| | avant | après |
|---|---|---|
| `COUNT(*)` sur le segment | 2 118 / 2 114 / 1 998 ms | **77 / 76 / 77 ms** |
| lecture complète de l'historique (modèle) | 5 600 / 5 737 ms | 5 212 / 5 556 ms |

Mesuré sur un entrepôt reconstitué au volume réel : 99 441 commandes,
111 853 lignes, 96 096 personnes, 99 224 avis, 103 417 paiements.

**Preuve d'équivalence.** Somme MD5 du résultat entier de
`v_historique_client` — 185 359 lignes × 19 colonnes, les cinq dates de
référence — identique avant et après :
`43f3e48aa4ce0a3bf79c5acb9de1d01c`. Idem pour le segment. Aucun chiffre publié
ne bouge.

Le dictionnaire des indicateurs est repris en conséquence : la formule du
segment nomme maintenant `dwh.v_socle_client`.

### 2. Trois autres causes de lenteur, hors SQL

- **`npm ci` tournait à chaque `docker compose up`**, alors que le volume
  `frontend_node_modules` garde l'installation. Une à trois minutes avant que
  Vite écoute, à chaque relance de la pile. Il ne tourne plus que si la somme
  du verrou a changé.
- **La police venait de `fonts.googleapis.com`**, par un `<link>` bloquant au
  rendu. Sur un réseau lent — une salle de soutenance — la page restait
  blanche le temps de la réponse. Elle est maintenant servie avec
  l'application (`@fontsource-variable/familjen-grotesk`), aucune requête ne
  sort.
- **`recharts` était déclaré et utilisé nulle part.** Retiré : 39 paquets en
  moins, et le paquet final passe de ~700 ko à 254 ko.

### 3. La typographie

Le fichier portait vingt tailles en dur, de 9 px à 56 px, et les deux tiers du
texte vivaient entre 10 et 13 px. Elles passent par une échelle de six crans
nommés par leur rôle (`--t-etiquette` à `--t-titre`), basée sur 16 px, plancher
à 12,5 px réservé aux capitales. Changer une taille se fait à un seul endroit.

Au passage, **46 classes CSS mortes** ont été retirées : la barre latérale
remplacée par la barre du haut, les cartes d'indicateurs remplacées par celles
de la vue générale. Vérifié qu'aucun `className`, y compris construit
dynamiquement, ne les nommait. `index.css` passe de 1 303 à 740 lignes.

### 4. L'animation

Une seule famille de mouvements — monter et apparaître — déclinée :

- les blocs de la page entrent en cascade, 90 ms d'écart ;
- les dix chiffres montent de zéro à leur valeur, en finissant sur la valeur
  **exacte** (un arrondi sur la dernière image afficherait 13 493 151,55) ;
- les barres de catégories poussent de la gauche, décalées de 60 ms ;
- les liaisons du schéma se tracent **dans l'ordre du pipeline** : sources,
  contrôle, entrepôt, usages, puis la descente rouge vers la quarantaine.
  C'est le seul endroit où l'animation porte une information.

`prefers-reduced-motion: reduce` éteint tout et laisse l'état final : le
réglage système « réduire les animations » existe pour les personnes que le
mouvement rend malades.

### 5. L'ordre de la page

Le chiffre d'affaires passe **avant** le schéma. Le schéma occupait six cents
pixels et poussait la figure principale sous la ligne de flottaison en
1440 × 900.

### 6. Le nom

**Leeral** — « éclairer, rendre clair » en wolof. Appliqué là où le jury le
lit : l'interface, le titre de l'onglet, la couverture de la présentation.
**Pas** dans les identifiants techniques — le nom de la base `dataflow360`, les
services Docker, le paquet Python, les variables d'environnement. Renommer
ceux-là quelques heures avant une démonstration, c'est risquer la démonstration
pour un gain nul : le jury ne les voit pas.

Si tu veux le renommage complet, c'est un travail à faire **après** la
soutenance, et je peux te l'écrire en un script.

## Vérifié comment

- 808 tests unitaires, 83 d'intégration sur un PostgreSQL 16 réel où les
  28 migrations ont été appliquées à neuf.
- `oxlint` et `tsc -b` propres, `ruff check` et `ruff format --check` propres.
- La page construite, servie avec une fausse API aux vrais chiffres, et
  photographiée à 1280 × 800, 1440 × 900 et 1920 × 1080 : aucun débordement
  horizontal, aucune erreur console, le compteur arrive bien sur
  13 493 151,56.
