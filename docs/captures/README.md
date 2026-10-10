# Captures du tableau de bord

Pour qui n'a pas Power BI Desktop — correcteur compris.
Le fichier source est `dashboards/ventes.pbix`.

| Fichier | Page | Description |
|---|---|---|
| `ventes-page.png` | Ventes | 3 cartes, courbe mensuelle, tableau détaillé |
| `produits-page.png` | Produits | Barres catégories, carte inconnu, tableau produits |
| `temps-reel-page.png` | Temps réel | 3 cartes, 2 histogrammes, tableau alerte |
| `qualite-page.png` | Qualité | Taux global, tableau sources, règles, note gravité |
| `segment-page.png` | Segment | 711 clients, tableau, règle vs modèle |
| `assistant-page.png` | Assistant | Taux de réponses ancrées |

Les visuels par règle et par gravité portent sur la **dernière exécution** de
chaque source (vues `sql/012_vues_rejets_derniere_ingestion.sql`) : les barres
totalisent 1 073 rejets, comme le tableau par source.

`catalogue` et `rakuten` déposent le même fichier sous deux noms : le taux
global (0,062 %) les compte tous deux. Voir le dictionnaire des indicateurs.
