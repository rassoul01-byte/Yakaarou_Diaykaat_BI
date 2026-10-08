# Captures du tableau de bord

Pour qui n'a pas Power BI Desktop — correcteur compris.
Le fichier source est `dashboards/ventes.pbix`.

| Capture | Ce qu'elle montre |
|---|---|
| `qualite-page-complete.png` | La page Qualité entière |
| `qualite-taux-global.png` | Taux de rejet global : 0,062 % |
| `qualite-par-source.png` | 1 073 rejets sur 1 550 922 lignes (olist), et les sources catalogue et rakuten |
| `qualite-par-regle.png` | Les avis concentrent l'essentiel des rejets |
| `qualite-par-gravite.png` | Répartition bloquante / non bloquante |

Les visuels par règle et par gravité portent sur la **dernière exécution** de
chaque source (vues `sql/012_vues_rejets_derniere_ingestion.sql`) : les barres
totalisent 1 073 rejets, comme le tableau par source.

`catalogue` et `rakuten` déposent le même fichier sous deux noms : le taux
global (0,062 %) les compte tous deux. Voir le dictionnaire des indicateurs.
