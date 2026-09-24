# common — éléments partagés

**Responsable :** Ndeye Penda SARR
**Suppléante :** Aissata DIALLO

Ce dossier contient ce que tous les périmètres utilisent, et que personne ne
doit réécrire dans son coin :

- `config.py` — lecture centralisée de la configuration. Aucun module ne lit
  `os.environ` directement : tout passe par `load_settings()`.
- `evenements.py` — le contrat des événements de navigation, en code :
  construction d'un événement conforme (`nouvel_evenement`) et validation
  (`valider`). Il traduit `docs/contrats/evenements.md`.
- `bus.py` — la publication et la lecture sur le bus Kafka. Le `Publieur`
  envoie au rebut, avec leurs motifs, les événements qui ne respectent pas le
  contrat ; `consommer` lit un sujet message par message.
- *à venir* — journalisation des exécutions, qui alimente la table
  `staging.execution_log` (F6.2).

Règle : un changement dans ce dossier touche tout le monde. Toute demande de
fusion qui le modifie est annoncée à l'équipe avant d'être fusionnée.
