# Séquence de démonstration — supervision des ventes et du flux

Ce que la démonstration montre : le DAG `supervision` (`dags/supervision.py`) juge chaque heure la journée en cours. Il signale une chaîne arrêtée, puis se tait quand le flux d'événements tourne et que les achats sont au niveau habituel.

⚠️ Le trafic est **simulé** : l'alerte démontre le dispositif, elle ne détecte rien de réel. Un événement d'achat ne porte aucun montant.

Toutes les commandes se lancent depuis la racine du dépôt, la plateforme étant démarrée (`docker compose ps`, voir le README).

---

## À savoir avant de commencer

### Le générateur date ses événements du 01/09/2026 par défaut

Sans `--debut`, les événements tombent le 1er septembre 2026, et non le jour de la démonstration. La commande d'exemple du README (`--graine 42`) n'alimente donc pas la journée en cours. Rejouée avec la même graine, elle produit en plus les mêmes identifiants, que le consommateur écarte comme doublons.

La séquence ci-dessous fixe donc `--debut` à minuit UTC du jour même, et ne donne **aucune** graine.

### L'heure de la présentation compte

Les heures sont en **UTC**, qui est aussi l'heure de Dakar.

- **Avant 12 h** : l'alerte ne se prononce pas sur la journée en cours. Rien n'est signalé, quel que soit le nombre d'achats.
- **À partir de 12 h** : les achats déjà faits dans la journée sont comparés à la moyenne d'une journée **complète** (mêmes jours de semaine précédents). Sous 60 %, l'alerte se déclenche. À un débit constant de 30 000 événements par jour, une journée normale reste sous 60 % jusque vers 14 h 25. La séquence utilise donc un rythme simulé de 50 000 événements par jour.

Le contrôle « flux interrompu » ne dépend pas de l'heure : sans aucun événement depuis plus d'un jour, `surveiller_ventes` est rouge, le matin comme l'après-midi.

### Le générateur a un plafond

Le générateur refuse (code de sortie 2) une simulation qui dépasserait l'heure réelle moins 5 minutes :

```
débit × durée  ≤  50 000 × (minutes écoulées depuis minuit UTC − 5) / 1440
```

Avec `--debit 300`, la durée à choisir selon l'heure de lancement :

| Heure UTC du lancement | Événements au plus | `--duree` | Événements publiés | Achats attendus (≈ 5 %, moins les défauts) |
|---|---|---|---|---|
| 08 h 00 | 16 493 | `54` | 16 200 | ≈ 770 |
| 09 h 00 | 18 576 | `61` | 18 300 | ≈ 870 |
| 10 h 00 | 20 659 | `68` | 20 400 | ≈ 970 |
| 11 h 00 | 22 743 | `75` | 22 500 | ≈ 1 070 |
| 12 h 00 | 24 826 | `82` | 24 600 | ≈ 1 170 |
| 13 h 05 | 27 083 | `90` | 27 000 | ≈ 1 280 |
| 14 h 00 | 28 993 | `96` | 28 800 | ≈ 1 370 |

Prendre la ligne de l'heure **déjà passée** : entre 13 h 05 et 14 h, garder `--duree 90`.

### Sous Git Bash (Windows)

Si un chemin comme `/app/...` devient `C:/Program Files/Git/app/...`, préfixer la commande par `MSYS_NO_PATHCONV=1`. PowerShell n'a pas ce problème.

---

## Nettoyage, à faire avant la démonstration

Les tests d'intégration du bus (`tests/common/test_bus.py`) laissent des groupes Kafka `test-*` qui ne lisent jamais. Leur retard monte à chaque publication : après trois générations, `surveiller_flux` les signalerait à tort comme « en décrochage ».

1. Lister les groupes concernés :

   ```bash
   docker compose exec kafka bash -c '/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list | grep "^test-"'
   ```

2. Les supprimer :

   ```bash
   docker compose exec kafka bash -c 'for g in $(/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list | grep "^test-"); do /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --delete --group "$g"; done'
   ```

3. Facultatif : retirer aussi leur historique. `surveiller_flux` lit ses relevés dans `staging.retard_flux` ; sans cette commande, les groupes supprimés restent affichés avec leurs anciens relevés, figés, sans jamais déclencher d'alerte.

   ```bash
   docker compose exec postgres psql -U dataflow -d dataflow360 -c "DELETE FROM staging.retard_flux WHERE groupe LIKE 'test-%';"
   ```

Ne pas relancer `pytest -m integration` après le nettoyage : il recrée des groupes `test-*`.

---

## Déroulé

### Étape 0 — Préparer

Faire le nettoyage ci-dessus, puis s'assurer que les sujets Kafka existent :

```bash
docker compose exec app python scripts/creer_sujets.py
```

Le DAG `supervision` reste **en pause** : `airflow dags test` le lance sans l'activer.

### Étape 1 — État de départ : la chaîne est arrêtée

```bash
docker compose exec airflow-scheduler airflow dags test supervision
```

**Résultat attendu**

- `surveiller_ventes` : **rouge**, « AUCUN FLUX DEPUIS … JOUR(S) — dernier jour connu … ».
- `surveiller_flux` : **vert**, « Aucun lecteur ne décroche ». Il tourne malgré l'échec qui précède (`all_done`).
- Le **lancement** est marqué en **succès** : Airflow juge un lancement sur sa dernière tâche, ici `surveiller_flux`. Le verdict sur les ventes se lit sur la **tâche** `surveiller_ventes`, pas sur la couleur du lancement.

**Ce qu'on dit** : l'alerte parle quand la chaîne est arrêtée. Un flux interrompu ne produit aucune chute visible : sans ce contrôle, l'alerte se tairait précisément quand tout est tombé.

### Étape 2 — Générer le trafic de la journée

Choisir `--duree` dans le tableau du plafond (ici, lancement après 13 h 05 UTC) :

```bash
docker compose exec app bash -c 'python -m generateur --debut "$(date -u +%Y-%m-%dT00:00:00Z)" --evenements-par-jour 50000 --debit 300 --duree 90 --sans-pause'
```

**Résultat attendu** : `graine=… événements=27000 du <aujourd'hui> au <aujourd'hui> ~13:00`, puis le bilan de publication. Environ 5 % des événements sont volontairement défectueux et partent dans `navigation.rebut`.

### Étape 3 — Facultatif : le retard monte

Relancer la commande de l'étape 1.

**Résultat attendu**

- `surveiller_flux` : **vert**. Le retard de `compteurs-du-jour` sur `navigation.evenements` affiche environ 25 700. Une seule hausse ne suffit pas : il faut trois relevés de suite à la hausse pour parler de décrochage.
- `surveiller_ventes` : toujours **rouge**. Les événements sont sur le bus, mais pas encore comptés.

### Étape 4 — Consommer le bus

```bash
docker compose exec app python -m compteurs
```

**Résultat attendu** : « Bus lu : … message(s), … retenu(s), … illisible(s), … déjà connu(s). », puis l'activité du jour, avec la mention du trafic simulé. Le retard de `compteurs-du-jour` retombe à environ 0.

### Étape 5 — La supervision repasse au vert

Relancer la commande de l'étape 1.

**Résultat attendu**

- `surveiller_ventes` : **vert**.
  - Après 12 h : environ 1 300 achats pour environ 1 400 à 1 500 habituels, soit à peu près 90 %, au-dessus du seuil de 60 %.
  - Avant 12 h : l'alerte ne se prononce pas sur la journée en cours.
- `surveiller_flux` : **vert**.
- Le lancement est en **succès**, comme à l'étape 1 : la différence se voit sur la tâche `surveiller_ventes`, passée du rouge au vert.

### Étape 6 — Facultatif : pourquoi `--jours 1`

```bash
docker compose exec app python -m compteurs.surveiller_ventes
```

**Résultat attendu** : sans `--jours 1`, la commande parcourt les dix derniers jours et signale la chute du 08/10/2026 (233 achats, 16,3 % de l'habituel) tant que ce jour est dans la fenêtre, jusqu'au 18/10/2026.

**Ce qu'on dit** : la supervision horaire juge la journée en cours. Les jours passés restent visibles dans l'alerte de la vue générale (`/api/indicateurs`, dix derniers jours) et par cette commande lancée à la main.

### Montrer le DAG dans l'interface Airflow plutôt qu'en ligne de commande

Activer d'abord `supervision` dans http://localhost:8080, puis le déclencher : un lancement déclenché sur un DAG en pause reste en file d'attente. Dans la vue en grille, regarder la case de la **tâche** `surveiller_ventes` : le lancement, lui, reste vert tant que `surveiller_flux` réussit. **Le remettre en pause après la démonstration**, sinon il tourne chaque heure et accumule des tâches rouges dès que le flux s'arrête.

---

## Si la présentation a lieu le matin (avant 12 h UTC)

- **Étape 1 inchangée** : `surveiller_ventes` est rouge, car le contrôle « flux interrompu » ne dépend pas de l'heure.
- **Étape 2** : réduire `--duree` selon le tableau du plafond (par exemple `--duree 68` à 10 h). Lancée trop tôt avec `--duree 90`, la commande est refusée avec le code 2.
- **Étape 5** : `surveiller_ventes` est vert parce que l'alerte ne juge pas une journée avant midi, **et non** parce que les achats atteignent le niveau habituel. Le dire tel quel : c'est la règle de midi (`HEURE_MINIMALE = 12` dans `src/compteurs/alerte.py`), voulue pour qu'une matinée ne soit pas comparée à une journée entière.
- **Le verdict sur le seuil de 60 %** ne peut pas être montré en direct le matin. Le montrer par l'étape 6 : la chute du 08/10/2026 est une journée complète, signalée sous le seuil.

---

## Plan de secours

### Un service ne répond pas

- Vérifier l'état : `docker compose ps`. Relancer ce qui est arrêté : `docker compose up -d`.
- Journaux d'un service : `docker compose logs --tail 30 <service>`.
- Kafka met jusqu'à une minute à redevenir `healthy`. Relancer ensuite `python scripts/creer_sujets.py`.

### `airflow dags test` ne démarre pas (étapes 1, 3, 5)

Lancer les deux modules directement : ce sont les mêmes commandes que celles du DAG, avec les mêmes verdicts.

```bash
docker compose exec app python -m compteurs.surveiller_ventes --jours 1
docker compose exec app python -m supervision.surveiller_flux
```

Le code de sortie fait le verdict : 0 = rien à signaler, 1 = alerte.

### Le générateur refuse avec le code 2 (étape 2)

La simulation dépasserait l'heure réelle : réduire `--duree` selon le tableau du plafond.

### Le générateur échoue sur Kafka (étape 2)

Kafka n'est pas prêt. Attendre `healthy` dans `docker compose ps`, relancer `python scripts/creer_sujets.py`, puis la génération.

### `compteurs` lit 0 message ou n'en retient aucun (étape 4)

- **« déjà connu(s) » élevé** : les événements ont déjà été comptés, typiquement après une génération rejouée avec la même graine. Relancer l'étape 2 sans `--graine`.
- **0 message lu** : la génération n'a rien publié, ou un autre `compteurs` les a déjà lus. Vérifier le retard du groupe :

  ```bash
  docker compose exec kafka bash -c '/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group compteurs-du-jour'
  ```

### `surveiller_ventes` reste rouge à l'étape 5

- **« AUCUN FLUX »** : les événements n'ont pas été comptés. Refaire l'étape 4.
- **Niveau sous 60 % après midi** : la génération était trop courte pour l'heure. C'est le **bon** verdict, et il se présente comme tel : l'alerte compare la journée en cours à une journée complète. Pour repasser au vert, générer un complément sans graine, dans la limite du plafond, puis refaire les étapes 4 et 5.

### `surveiller_flux` est rouge

- **Un groupe `test-*` décroche** : refaire le nettoyage, puis relancer la commande de l'étape 1.
- **`compteurs-du-jour` décroche** : le consommateur ne suit pas. Lancer `python -m compteurs` (étape 4), puis relancer la commande de l'étape 1.

### Rien ne fonctionne en direct

- **Lancement de référence** : dans Airflow, DAG `supervision`, lancement `manual__2026-10-10T23:54:20` du 10/10/2026, marqué en succès. On y voit la tâche `surveiller_ventes` rouge (flux interrompu) et `surveiller_flux` verte après elle. Ce lancement a été fait par `airflow dags test` : ses journaux ont été affichés dans le terminal et ne sont pas consultables dans l'interface. Pour les verdicts eux-mêmes, lancer les deux modules à la main (voir plus haut).
- **Tableau de bord** : les captures de `docs/captures/`, dont la page « Temps réel ».
- **Les règles dans le code** : `dags/supervision.py` (docstring) et `src/compteurs/alerte.py` (seuil de 60 %, règle de midi, flux interrompu).
