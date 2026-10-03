"""Service référentiel — la source API du projet.

Deux données extérieures que la plateforme ne produit pas : les jours fériés
brésiliens, qui expliquent les creux de ventes, et les taux de change
historiques, qui permettent d'afficher le chiffre d'affaires en euros.

Ces données sont récupérées une fois auprès de services publics gratuits, puis
conservées dans la zone brute. La plateforme, elle, n'interroge que ce service
local : elle ne dépend donc d'aucune connexion au moment où elle calcule.

Contrat : docs/contrats/referentiel.md
"""
