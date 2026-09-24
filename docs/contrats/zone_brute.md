# Contrat — Organisation de la zone brute

**Auteur : Aissata DIALLO · Attendu par : Mouhameth (Livrable 1) · Sprint 1**

Ce document fixe l'arborescence de la zone brute, le format de ses
manifestes, et la règle qui la gouverne. Il doit être lu avant d'écrire
le moindre fichier dans `data/raw/`.

## 1. La règle d'or

**Dans la zone brute, rien n'est jamais modifié ni supprimé.**

Un fichier une fois écrit dans `data/raw/` reste tel quel pour toute la
durée du projet. Pour corriger une erreur en amont, on ajoute une
nouvelle ingestion ou une nouvelle tranche horaire — on ne réécrit
jamais une ingestion existante. C'est cette règle qui rend la
plateforme *rejouable* : à tout moment, on peut relancer les
transformations du Sprint 2 depuis la zone brute et retomber sur les
mêmes résultats.

Une seule exception : une tranche horaire d'événements peut recevoir
des événements supplémentaires **tant qu'elle correspond à l'heure en
cours** (le fichier grossit par ajout). Une fois l'heure passée, elle
est considérée close et n'est plus jamais rouverte.

## 2. Séparation sources / zone brute

```
data/
├── sources/            ce que les systèmes sources « livrent »
│   ├── olist/
│   └── rakuten/
└── raw/                 la zone brute — alimentée par la plateforme,
    │                     jamais modifiée
    ├── lots/            ingestions par lots, une par exécution
    └── evenements/      archive horaire des événements du bus
```

`data/sources/` joue le rôle des systèmes de l'e-commerçant : c'est là
que le script de récupération (Sprint 0) dépose ce qu'il télécharge.
`data/raw/` est la mémoire de la plateforme : chaque entrée y est
datée, décrite, et jamais modifiée (flux F-01 du dossier de
conception).

## 3. Zone brute des lots

```
data/raw/lots/<source>/ingestion=<horodatage>/
├── <fichier_1>
├── <fichier_2>
└── manifeste.json
```

- `<source>` : `olist`, `rakuten`, ...
- `<horodatage>` : format `AAAAMMJJTHHMMSS`, heure de l'ingestion.
- Les fichiers sont des copies **à l'identique** des fichiers de
  `data/sources/<source>/`.
- `manifeste.json` décrit chaque fichier du dossier (voir §5).

Le Livrable 1 (Mouhameth) crée ces ingestions. Le Livrable 4 (ce
document) les liste et vérifie leur intégrité, sans jamais les modifier.

## 4. Zone brute des événements

```
data/raw/evenements/navigation.evenements/date=<AAAA-MM-JJ>/
├── heure=<HH>.jsonl
├── heure=<HH>.manifeste.json
├── heure=<HH>.jsonl
└── heure=<HH>.manifeste.json
```

- Un fichier `heure=HH.jsonl` par heure, un événement JSON par ligne
  (format du contrat d'événement, docs/contrats/evenements.md).
- Le regroupement se fait sur l'**horodatage de l'événement**, pas sur
  l'heure d'archivage.
- `heure=HH.manifeste.json` est recalculé à chaque écriture dans la
  tranche correspondante (voir §5).

## 5. Format du manifeste

Un objet JSON unique, commun aux lots et aux tranches d'événements :

```json
{
  "source": "olist",
  "ingestion": "20260922T101500",
  "fichiers": [
    {
      "nom": "olist_orders_dataset.csv",
      "lignes": 99441,
      "octets": 8737252,
      "sha256": "…"
    }
  ]
}
```

- `source` : nom de la source (`olist`, `rakuten`) ou du sujet Kafka
  archivé (`navigation.evenements`) selon le cas.
- `ingestion` : l'horodatage du lot, ou `<date>T<heure>` pour une
  tranche d'événements.
- `fichiers` : un objet par fichier du dossier, avec son nom, son
  nombre de lignes, sa taille en octets et son empreinte SHA-256.

## 6. Vérification

`zone_brute verifier` recalcule l'empreinte SHA-256 de chaque fichier
listé dans chaque manifeste et la compare à la valeur enregistrée.
Toute différence, ou tout fichier manquant, est signalée et fait
sortir la commande avec le code **1**.

## 7. Rejeu

- **Lots** : le rejeu du Sprint 2 consiste à relire les fichiers d'une
  ingestion existante — `verifier` garantit qu'ils sont fiables avant
  de les relire.
- **Événements** : `zone_brute rejouer --date AAAA-MM-JJ --heure HH`
  republie chaque événement d'une tranche archivée sur le sujet dédié
  `navigation.rejeu`, jamais sur `navigation.evenements`, pour ne pas
  faire compter deux fois les mêmes événements par les consommateurs
  du flux normal.
