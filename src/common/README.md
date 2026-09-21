# common — éléments partagés

**Responsable :** Ndeye Penda SARR
**Suppléante :** Aissata DIALLO

Ce dossier contient ce que tous les périmètres utilisent, et que personne ne
doit réécrire dans son coin :

- `config.py` — lecture centralisée de la configuration. Aucun module ne lit
  `os.environ` directement : tout passe par `load_settings()`.
- *à venir* — journalisation des exécutions, qui alimente la table
  `staging.execution_log` (F6.2).
- *à venir* — ouverture des connexions aux trois bases.

Règle : un changement dans ce dossier touche tout le monde. Toute demande de
fusion qui le modifie est annoncée à l'équipe avant d'être fusionnée.
