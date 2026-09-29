"""
Catalogue des règles de qualité — DataFlow360
Livrable F1.5 — Responsable : Seydina WADE

Le catalogue constitue la source de vérité des règles de validation.
Les règles sont indépendantes du moteur qui les exécute.
"""

RULES = [
    {
        "identifiant": "OLIST_GEOLOCALISATION_01",
        "source": "olist",
        "colonne": "ligne_complete",
        "condition": "La ligne complète doit être unique.",
        "gravite": "silencieuse",
        "commentaire": (
            "Supprimer les doublons stricts avant chargement afin d'éviter "
            "de compter plusieurs fois la même ligne de géolocalisation."
        ),
    },
    {
        "identifiant": "OLIST_AVIS_01",
        "source": "olist",
        "colonne": "review_id",
        "condition": "review_id doit être unique.",
        "gravite": "bloquante",
        "commentaire": (
            "Un identifiant d'avis dupliqué peut entraîner plusieurs "
            "représentations du même avis dans les analyses."
        ),
    },
    {
        "identifiant": "OLIST_AVIS_02",
        "source": "olist",
        "colonne": "order_id",
        "condition": "Une commande ne doit conserver qu'un seul avis.",
        "gravite": "bloquante",
        "commentaire": (
            "Garantir la granularité attendue des avis et éviter qu'une "
            "commande soit représentée plusieurs fois dans les analyses."
        ),
    },
    {
        "identifiant": "OLIST_COMMANDES_01",
        "source": "olist",
        "colonne": "order_id",
        "condition": "Une commande doit posséder au moins une ligne d'article.",
        "gravite": "non bloquante",
        "commentaire": (
            "Une commande sans article est conservée mais exclue du calcul "
            "du chiffre d'affaires afin de ne pas produire un montant artificiel."
        ),
    },
    {
        "identifiant": "OLIST_PAIEMENTS_01",
        "source": "olist",
        "colonne": "order_id",
        "condition": (
            "Les paiements d'une même commande doivent être agrégés "
            "avant toute jointure."
        ),
        "gravite": "non bloquante",
        "commentaire": (
            "Une commande peut avoir plusieurs paiements. L'agrégation "
            "préalable évite de dupliquer les montants lors des jointures."
        ),
    },
    {
        "identifiant": "OLIST_ARTICLES_01",
        "source": "olist",
        "colonne": "product_category_name",
        "condition": (
            "Une catégorie produit doit être renseignée ou le produit "
            "doit être rattaché à la catégorie « inconnu »."
        ),
        "gravite": "non bloquante",
        "commentaire": (
            "Les produits sans catégorie ne doivent pas être supprimés, "
            "afin de préserver les totaux. Ils sont rattachés à une catégorie "
            "« inconnu »."
        ),
    },
    {
        "identifiant": "OLIST_COMMANDES_02",
        "source": "olist",
        "colonne": "order_delivered_customer_date",
        "condition": (
            "La date de livraison est obligatoire lorsque le statut "
            "de la commande est « delivered »."
        ),
        "gravite": "bloquante",
        "commentaire": (
            "La complétude de la date de livraison est conditionnelle : "
            "une commande livrée doit avoir une date de livraison."
        ),
    },
    {
        "identifiant": "OLIST_AVIS_03",
        "source": "olist",
        "colonne": "review_comment_message",
        "condition": (
            "L'absence de commentaire textuel ne doit pas entraîner "
            "le rejet de l'avis."
        ),
        "gravite": "non bloquante",
        "commentaire": (
            "Un avis peut ne contenir aucun commentaire. La note reste "
            "exploitable et l'absence de texte constitue une information."
        ),
    },
    {
        "identifiant": "OLIST_CLIENTS_01",
        "source": "olist",
        "colonne": "customer_id/customer_unique_id",
        "condition": (
            "Les agrégations par client doivent utiliser l'identifiant "
            "de personne customer_unique_id et non customer_id."
        ),
        "gravite": "bloquante",
        "commentaire": (
            "customer_id identifie un enregistrement de commande, tandis "
            "que customer_unique_id représente la personne. Utiliser le "
            "mauvais identifiant fausserait les agrégations client."
        ),
    },
    {
        "identifiant": "RAKUTEN_PRODUITS_01",
        "source": "rakuten",
        "colonne": "designation/description",
        "condition": (
            "Les entités HTML doivent être décodées et les balises HTML "
            "supprimées avant indexation."
        ),
        "gravite": "non bloquante",
        "commentaire": (
            "Le nettoyage du texte améliore sa lisibilité et sa qualité "
            "pour la recherche et l'indexation."
        ),
    },
    {
        "identifiant": "RAKUTEN_PRODUITS_02",
        "source": "rakuten",
        "colonne": "description",
        "condition": (
            "Une description absente ne doit pas entraîner le rejet "
            "de la fiche produit."
        ),
        "gravite": "non bloquante",
        "commentaire": (
            "La désignation du produit est suffisante pour l'indexation. "
            "La description constitue un enrichissement et non une donnée obligatoire."
        ),
    },
    {
        "identifiant": "RAKUTEN_PRODUITS_03",
        "source": "rakuten",
        "colonne": "designation",
        "condition": (
            "Une désignation identique sur plusieurs produits ne doit "
            "pas entraîner leur déduplication."
        ),
        "gravite": "silencieuse",
        "commentaire": (
            "Deux produits différents peuvent avoir le même libellé. "
            "Les identifiants produits restent la référence d'unicité."
        ),
    },
    {
        "identifiant": "RAKUTEN_PRODUITS_04",
        "source": "rakuten",
        "colonne": "designation/description",
        "condition": (
            "La langue du texte doit être détectée et stockée comme "
            "attribut sans filtrer les produits non francophones."
        ),
        "gravite": "non bloquante",
        "commentaire": (
            "Le catalogue peut contenir plusieurs langues. La détection "
            "permet de connaître la langue sans supprimer les produits."
        ),
    },
]


def get_rules(source=None):
    """
    Retourne les règles du catalogue.

    Parameters
    ----------
    source : str, optional
        Source à filtrer : 'olist' ou 'rakuten'.

    Returns
    -------
    list
        Liste des règles correspondant à la source demandée.
    """
    if source is None:
        return RULES

    return [
        rule
        for rule in RULES
        if rule["source"].lower() == source.lower()
    ]


def get_rule(rule_id):
    """
    Recherche une règle à partir de son identifiant.
    """
    for rule in RULES:
        if rule["identifiant"] == rule_id:
            return rule

    return None
