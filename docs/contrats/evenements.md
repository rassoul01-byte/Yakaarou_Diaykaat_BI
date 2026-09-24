# Contrat d'événement — navigation

**Version du contrat : 1**
**Responsable : Ndeye Penda SARR · F1.3**
**Code correspondant : `src/common/evenements.py`**

Ce contrat fixe ce qui circule sur le bus d'événements : les sujets, le format d'un message, et les garanties offertes à ceux qui les lisent. Tous les producteurs et tous les consommateurs s'y conforment. Le module `src/common/evenements.py` en est la traduction exécutable : **en cas de doute, c'est le code qui fait foi, et ce document est corrigé.**

---

## 1. Pourquoi un contrat

Le générateur, l'archivage de la zone brute, puis au Sprint 4 les compteurs du jour et le journal des recherches, sont écrits par quatre personnes différentes. Sans format commun écrit, un champ renommé d'un côté casse silencieusement tous les autres : aucun programme ne plante, les chiffres deviennent simplement faux.

Le contrat rend ces ruptures **visibles** : un message qui ne le respecte pas est écarté vers un sujet de rebut, avec la raison de son refus.

---

## 2. Les sujets

| Sujet | Rôle | Qui publie | Qui lit | Rétention |
|---|---|---|---|---|
| `navigation.evenements` | Les événements valides | Le générateur — Bachir | L'archivage — Aissata ; au Sprint 4, les compteurs et le journal des recherches — Mouhameth | 7 jours |
| `navigation.rebut` | Les messages refusés, avec leurs motifs | Automatiquement, par le bus | Le contrôle de qualité du flux | 30 jours |
| `navigation.rejeu` | Les événements archivés et republiés | Le rejeu de la zone brute — Aissata | Tout consommateur qui doit retraiter une période | 7 jours |

Chaque sujet a **3 partitions** et un facteur de réplication de 1, puisque le bus ne compte qu'un seul serveur. Le rebut est conservé plus longtemps que les autres : c'est la matière de l'analyse des défauts.

Le sujet de rejeu est séparé du sujet principal **à dessein** : des événements rejoués sur `navigation.evenements` seraient comptés une seconde fois par les compteurs du jour.

---

## 3. La clé du message

La clé de chaque message est son **`id_session`**, encodé en UTF-8.

Kafka range tous les messages d'une même clé dans la même partition : **les événements d'une même session sont donc lus dans l'ordre où ils ont été publiés.** Aucun ordre n'est garanti entre deux sessions différentes.

---

## 4. Le format d'un événement

Un objet JSON encodé en UTF-8, avec **exactement** les huit champs suivants. Les champs facultatifs sont présents avec la valeur `null` : chaque événement a toujours la même forme, ce qui simplifie l'archivage.

| Champ | Type | Règle |
|---|---|---|
| `version_contrat` | entier | Vaut `1` |
| `id_evenement` | texte | Un UUID. Identifie l'événement de manière unique |
| `type` | texte | `page_vue`, `recherche`, `ajout_panier` ou `achat` |
| `horodatage` | texte | Date et heure ISO 8601 **avec fuseau horaire**, par exemple `2026-09-22T10:15:03.412Z` |
| `id_session` | texte | Non vide |
| `customer_unique_id` | texte ou `null` | 32 caractères hexadécimaux : l'identifiant de **personne** Olist, jamais l'identifiant de commande |
| `id_produit` | texte ou `null` | Uniquement des chiffres : l'identifiant d'une fiche du catalogue Rakuten. **Toujours du texte, jamais un nombre** |
| `requete` | texte ou `null` | Le texte tapé dans le moteur de recherche |

### Ce qui dépend du type

| Type | `id_produit` | `requete` | `customer_unique_id` |
|---|---|---|---|
| `page_vue` | obligatoire | `null` | facultatif |
| `recherche` | `null` | obligatoire, non vide | facultatif |
| `ajout_panier` | obligatoire | `null` | facultatif |
| `achat` | facultatif | `null` | **obligatoire** |

Un achat exige un client identifié : on ne peut pas acheter sans compte.

### L'horodatage

- Toujours avec un fuseau horaire. Les producteurs écrivent en **UTC**, avec le suffixe `Z` et la précision à la milliseconde.
- **Plausible** : pas avant le 1er janvier 2016, date antérieure au début de l'historique Olist, et pas plus de **24 heures** dans le futur.

⚠️ **Pour le générateur en mode accéléré** : si une journée simulée défile en quelques minutes, son horloge ne doit pas dépasser l'heure réelle de plus de 24 heures. Le plus simple est de simuler des journées **passées**, en partant d'une date de début fixée en paramètre.

### Les champs inconnus sont refusés

Un champ qui ne figure pas dans ce contrat fait refuser le message. C'est volontaire : une faute de frappe dans un nom de champ — `horodatge` — serait sinon acceptée sans bruit, et le vrai champ manquerait.

---

## 5. Exemples

Une recherche d'un visiteur anonyme — notez la faute de frappe, volontaire, dans la requête :

```json
{
  "version_contrat": 1,
  "id_evenement": "7f3c2e1a-8b4d-4c21-9f0e-2a6b5d8c1e37",
  "type": "recherche",
  "horodatage": "2026-09-22T10:15:03.412Z",
  "id_session": "s-000123",
  "customer_unique_id": null,
  "id_produit": null,
  "requete": "chaise de bureu ergonomique"
}
```

Un achat d'un client identifié :

```json
{
  "version_contrat": 1,
  "id_evenement": "c1a9e7d2-3f58-4b06-8e21-7d4f0b9a6c15",
  "type": "achat",
  "horodatage": "2026-09-22T10:21:47.908Z",
  "id_session": "s-000123",
  "customer_unique_id": "861eff4711a542e4b93843c6dd7febb0",
  "id_produit": null,
  "requete": null
}
```

---

## 6. Le message de rebut

Un message refusé n'est jamais perdu. Il est publié sur `navigation.rebut` sous cette forme :

```json
{
  "motifs": [
    "id_produit obligatoire pour un événement page_vue",
    "horodatage sans fuseau horaire"
  ],
  "recu_le": "2026-09-22T10:15:03.451Z",
  "evenement_brut": { "…": "le message tel qu'il a été reçu" }
}
```

Tous les motifs sont listés, pas seulement le premier. Si le message n'était même pas du JSON lisible, `evenement_brut` contient le texte reçu.

---

## 7. Les garanties pour les consommateurs

**Au moins une fois.** Un consommateur ne valide sa position qu'**après** avoir traité un message. S'il s'arrête en cours de route, il relira ce message au redémarrage. Conséquence : **un même événement peut être reçu deux fois.** Tout consommateur qui compte ou qui stocke doit dédoublonner sur `id_evenement`.

**Ordre par session seulement**, voir la section 3.

**Validation en amont.** Tout message présent sur `navigation.evenements` a passé la validation. Un consommateur peut s'y fier sans revérifier.

---

## 8. Faire évoluer le contrat

- **Ajouter, renommer ou supprimer un champ** change le contrat : `version_contrat` passe à `2`.
- Pendant la transition, les consommateurs acceptent les deux versions ; les producteurs passent ensuite à la nouvelle.
- Toute évolution passe par une demande de fusion sur ce document **et** sur `src/common/evenements.py`, relue par un membre qui consomme les événements.

---

## 9. Utiliser le bus

Publier, depuis le générateur :

```python
from common.bus import Publieur
from common.evenements import nouvel_evenement

with Publieur() as publieur:
    evt = nouvel_evenement("recherche", id_session="s-000123", requete="lampe de chevet")
    publieur.publier(evt)   # renvoie False et part au rebut si l'événement est invalide
```

Lire, depuis l'archivage :

```python
from common.bus import consommer
from common.evenements import SUJET_EVENEMENTS

for message in consommer(SUJET_EVENEMENTS, groupe="archivage-zone-brute"):
    traiter(message.valeur)   # un dictionnaire conforme au contrat
```

Republier sur le sujet de rejeu :

```python
from common.bus import Publieur
from common.evenements import SUJET_REJEU

with Publieur(sujet_principal=SUJET_REJEU) as publieur:
    publieur.publier(evenement_archive)
```

Chaque consommateur choisit un **nom de groupe** qui lui est propre : c'est ce nom qui permet de suivre son retard avec `scripts/etat_bus.py`.
