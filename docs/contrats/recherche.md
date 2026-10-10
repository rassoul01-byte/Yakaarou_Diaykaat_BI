# Contrat — Moteur de recherche du catalogue

**Fonctionnalités :** F4.2 — Recherche tolérante aux fautes · F4.3 — Filtres · F4.5 — Requêtes sans résultat
**Responsable :** Bachir DEME · **Relectrice :** Ndeye Penda SARR
**Modules :** `src/recherche/moteur.py`, `src/recherche/chercher.py`, `src/recherche/sans_resultat.py`

---

## 1. Ce que le moteur s'engage à faire

Interroger l'index `catalogue` (contrat : `docs/contrats/index.md`, section 5) et rendre, pour chaque résultat, `product_id`, `designation`, `categorie_code` et le score attribué par Elasticsearch.

La recherche porte sur `designation` (poids ×3) et `description`. Les correspondances sans faute passent devant les correspondances approchées.

---

## 2. La tolérance aux fautes (F4.2)

L'analyseur de l'index gère les accents, les majuscules et le pluriel. **La tolérance aux fautes est un réglage de la requête**, pas de l'index : changer le réglage ne demande aucune réindexation.

| Réglage | Valeur de départ | Effet |
|---|---|---|
| `tolerance` | `AUTO` | 0 faute pour 1-2 lettres, 1 pour 3-5, 2 à partir de 6 |
| `prefixe_exact` | 1 | La première lettre doit être exacte |
| `operateur` | `and` | Tous les mots de la requête doivent être trouvés |

**Pourquoi la première lettre exacte.** `lampe` et `rampe` sont distants d'une seule lettre : la distance seule ne les sépare pas. Exiger la première lettre le fait. Le prix : une faute sur la première lettre (`hureau`) n'est pas rattrapée.

**Le critère de réussite :** `chaise de bureu` ramène des chaises de bureau, et `lampe` ne ramène pas de rampes.

> **À compléter avant la fusion :** le tableau des essais (réglages comparés, résultat de chaque cas du jeu d'évaluation) et le choix final justifié. Le jeu d'évaluation est dans `tests/recherche/test_recherche_integration.py`.

---

## 3. Les filtres (F4.3) — et ce qui n'y est pas

**Filtres pris en charge :** `categorie_code` et `langue`.

**Filtre de prix : non pris en charge. Décision de périmètre.**

Le catalogue ne contient aucun prix : ni les fiches Rakuten, ni les événements. Les prix existent dans l'entrepôt (`dwh.fait_ligne_commande.prix`), mais pour des produits **Olist**, qui ne sont pas ceux du catalogue indexé. Le lien entre un produit Olist et une fiche Rakuten est choisi arbitrairement à l'intérieur d'une catégorie (`docs/contrats/correspondance.md`) : en tirer un prix pour une fiche serait **un montant inventé**, comme le serait un chiffre d'affaires en temps réel.

La commande refuse donc explicitement `--prix-min` et `--prix-max` avec un message clair, plutôt que de les ignorer en silence.

**Pour les démonstrations :** annoncer que la recherche filtre par catégorie et par langue, et pourquoi pas par prix.

**Limite connue :** `categorie_code` est un code numérique (par exemple 2060). Aucune table de libellés n'est branchée sur le moteur.

---

## 4. Les requêtes sans résultat (F4.5)

`python -m recherche.sans_resultat` lit `staging.v_requetes_frequentes` (le journal regroupé par requête, toutes journées confondues ; migration `sql/017_vue_requetes_frequentes.sql`), rejoue chaque requête avec **la même recherche que l'acheteur** (même fonction de construction), et rend celles qui ne ramènent rien, classées par fréquence décroissante.

Une requête en erreur n'est **pas** comptée comme « sans résultat » : l'analyse échoue plutôt que de mentir.

⚠️ **Les requêtes du générateur** sont tirées des désignations du catalogue : elles ressemblent à des fragments de titres plutôt qu'à des recherches humaines. Le dispositif est juste, les requêtes ne le sont pas.

---

## 5. Les commandes

```bash
docker compose exec app python -m recherche.chercher "chaise de bureu"
docker compose exec app python -m recherche.chercher "lampe" --categorie 2060 --langue fr
docker compose exec app python -m recherche.sans_resultat --top 20
```

| Commande | Code de sortie |
|---|---|
| `chercher` | 0 si la recherche aboutit (au moins une fiche) ; 1 sinon (erreur d'Elasticsearch, requête invalide, ou aucun résultat — le message distingue les trois) |
| `sans_resultat` | 0 si l'analyse est menée à terme ; 1 si le journal ou Elasticsearch est inaccessible |

---

## 6. Critères de réussite

- `chaise de bureu` ramène des chaises de bureau.
- Un mot voisin n'est pas confondu (`lampe` / `rampe`).
- Le filtre par catégorie ne ramène que cette catégorie.
- Le **temps de réponse** d'une recherche reste sous la seconde — mesuré et annoncé (`pytest -m integration -s tests/recherche`).
- Les tests de logique tournent **sans** Elasticsearch ; les autres sont marqués `integration`.
- Le dictionnaire contient l'entrée « Requêtes sans résultat », relue par Ndeye Penda.
