"""Tests de l'historisation de type 2 des dimensions (F1.10, étape 2).

Chaque test change la zone intermédiaire entre deux chargements, comme le ferait
une source qui évolue, puis regarde ce que l'entrepôt a gardé : la version
d'avant, fermée, et la version d'après, courante.
"""

from datetime import date

import pytest

from integration.chargement import charger
from integration.verifier import code_sortie, verifier
from tests.integration.aides import lire

pytestmark = pytest.mark.integration

JOUR_1 = date(2026, 10, 1)
JOUR_2 = date(2026, 10, 8)
JOUR_3 = date(2026, 10, 15)


def _modifier(cnx, sql: str, parametres=None) -> None:
    with cnx.cursor() as curseur:
        curseur.execute(sql, parametres)
    cnx.commit()


def _versions_client(cnx, personne: str) -> list[tuple]:
    return lire(
        cnx,
        """
        SELECT ville, valide_du, valide_au, est_courante
        FROM dwh.dim_client WHERE customer_unique_id = %s ORDER BY valide_du, client_id
        """,
        (personne,),
    )


def test_le_premier_chargement_ouvre_une_version_par_identifiant(cnx):
    resultat = charger(cnx, JOUR_1)

    assert resultat.versions_ouvertes == {"dim_client": 3, "dim_produit": 3, "dim_vendeur": 2}
    assert resultat.versions_fermees == {"dim_client": 0, "dim_produit": 0, "dim_vendeur": 0}
    assert _versions_client(cnx, "u-B") == [("Sao Paulo", JOUR_1, None, True)]


def test_un_second_chargement_sans_changement_ne_touche_a_rien(cnx):
    charger(cnx, JOUR_1)
    avant = lire(cnx, "SELECT * FROM dwh.dim_client ORDER BY client_id")

    second = charger(cnx, JOUR_2)  # une autre date : si une version s'ouvrait, on le verrait

    assert second.versions_ouvertes == {"dim_client": 0, "dim_produit": 0, "dim_vendeur": 0}
    assert second.versions_fermees == {"dim_client": 0, "dim_produit": 0, "dim_vendeur": 0}
    assert lire(cnx, "SELECT * FROM dwh.dim_client ORDER BY client_id") == avant
    assert lire(cnx, "SELECT count(*) FROM dwh.dim_produit") == [(4,)]  # 3 + la ligne 0
    assert lire(cnx, "SELECT count(*) FROM dwh.dim_vendeur") == [(3,)]  # 2 + la ligne 0


def test_un_attribut_suivi_modifie_ferme_l_ancienne_version_et_en_ouvre_une_nouvelle(cnx):
    charger(cnx, JOUR_1)
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'",
    )

    resultat = charger(cnx, JOUR_2)

    assert resultat.versions_ouvertes["dim_client"] == 1
    assert resultat.versions_fermees["dim_client"] == 1
    assert _versions_client(cnx, "u-B") == [
        ("Sao Paulo", JOUR_1, JOUR_2, False),  # l'ancienne reste consultable
        ("Brasilia", JOUR_2, None, True),
    ]
    # Les personnes inchangées gardent leur unique version, et leur clé.
    assert _versions_client(cnx, "u-A") == [("Rio", JOUR_1, None, True)]
    # Le comptage « courant » ne bouge pas : une personne reste une personne.
    assert resultat.comptages["dim_client"] == 3


def test_les_faits_pointent_vers_la_version_courante(cnx):
    charger(cnx, JOUR_1)
    ancienne = lire(cnx, "SELECT client_id FROM dwh.dim_client WHERE customer_unique_id = 'u-B'")[
        0
    ][0]
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'",
    )

    charger(cnx, JOUR_2)

    nouvelle = lire(
        cnx,
        "SELECT client_id FROM dwh.dim_client WHERE customer_unique_id = 'u-B' AND est_courante",
    )[0][0]
    assert nouvelle != ancienne
    assert lire(
        cnx, "SELECT DISTINCT client_id FROM dwh.fait_commande WHERE order_id IN ('o2', 'o4')"
    ) == [(nouvelle,)]
    # Aucune commande ne pointe vers la version fermée.
    assert lire(
        cnx, "SELECT count(*) FROM dwh.fait_commande WHERE client_id = %s", (ancienne,)
    ) == [(0,)]


def test_un_changement_de_correspondance_historise_le_produit(cnx):
    charger(cnx, JOUR_1)
    _modifier(
        cnx,
        "UPDATE staging.correspondance_produits"
        " SET id_fiche = 'f2', categorie_catalogue = '2060', rattache = TRUE WHERE id_produit = 'p3'",
    )

    resultat = charger(cnx, JOUR_2)

    assert resultat.versions_fermees["dim_produit"] == 1
    assert lire(
        cnx,
        "SELECT rattache, categorie_catalogue, valide_au, est_courante FROM dwh.dim_produit"
        " WHERE id_produit_olist = 'p3' ORDER BY valide_du, produit_id",
    ) == [(False, "inconnu", JOUR_2, False), (True, "2060", None, True)]
    # La ligne d'article de o2 suit la version courante du produit.
    assert lire(
        cnx,
        "SELECT p.rattache FROM dwh.fait_ligne_commande AS l"
        " JOIN dwh.dim_produit AS p USING (produit_id) WHERE l.order_id = 'o2'",
    ) == [(True,)]


def test_un_nouvel_identifiant_ouvre_une_version_sans_toucher_les_autres(cnx):
    charger(cnx, JOUR_1)
    avant = lire(cnx, "SELECT client_id, customer_unique_id FROM dwh.dim_client ORDER BY client_id")
    _modifier(
        cnx,
        "INSERT INTO staging.olist_customers VALUES ('cust-d1', 'u-D', '05000', 'Manaus', 'AM')",
    )

    resultat = charger(cnx, JOUR_2)

    assert resultat.versions_ouvertes["dim_client"] == 1
    assert resultat.versions_fermees["dim_client"] == 0
    assert resultat.comptages["dim_client"] == 4
    apres = lire(cnx, "SELECT client_id, customer_unique_id FROM dwh.dim_client ORDER BY client_id")
    assert apres[: len(avant)] == avant  # les clés existantes n'ont pas bougé
    assert apres[-1][1] == "u-D"


def test_l_historique_s_accumule_sur_plusieurs_chargements(cnx):
    charger(cnx, JOUR_1)
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'",
    )
    charger(cnx, JOUR_2)
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Goiania' WHERE customer_id = 'cust-b1'",
    )
    charger(cnx, JOUR_3)

    # Trois versions, bout à bout : chacune ferme le jour où la suivante s'ouvre.
    assert _versions_client(cnx, "u-B") == [
        ("Sao Paulo", JOUR_1, JOUR_2, False),
        ("Brasilia", JOUR_2, JOUR_3, False),
        ("Goiania", JOUR_3, None, True),
    ]


def test_relancer_apres_un_changement_ne_rouvre_pas_de_version(cnx):
    charger(cnx, JOUR_1)
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'",
    )
    charger(cnx, JOUR_2)
    apres_changement = lire(cnx, "SELECT * FROM dwh.dim_client ORDER BY client_id")

    rejeu = charger(cnx, JOUR_2)

    assert rejeu.versions_ouvertes["dim_client"] == 0
    assert rejeu.versions_fermees["dim_client"] == 0
    assert lire(cnx, "SELECT * FROM dwh.dim_client ORDER BY client_id") == apres_changement


def test_la_ligne_inconnu_ne_se_ferme_jamais(cnx):
    charger(cnx, JOUR_1)
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'",
    )
    charger(cnx, JOUR_2)

    for table, cle in (
        ("dim_client", "client_id"),
        ("dim_produit", "produit_id"),
        ("dim_vendeur", "vendeur_id"),
    ):
        assert lire(
            cnx, f"SELECT valide_du, valide_au, est_courante FROM dwh.{table} WHERE {cle} = 0"
        ) == [(date(1900, 1, 1), None, True)]


def test_deux_versions_courantes_sont_refusees_par_la_base(cnx):
    charger(cnx, JOUR_1)

    with pytest.raises(Exception, match="ux_dim_client_courante"):
        with cnx.cursor() as curseur:
            curseur.execute(
                "INSERT INTO dwh.dim_client (customer_unique_id, valide_du, est_courante)"
                " VALUES ('u-A', '2026-10-02', TRUE)"
            )
    cnx.rollback()


def test_la_contrainte_de_validite_refuse_une_version_incoherente(cnx):
    charger(cnx, JOUR_1)

    with pytest.raises(Exception, match="ck_dim_client_validite"):
        with cnx.cursor() as curseur:
            curseur.execute(
                "UPDATE dwh.dim_client SET est_courante = FALSE WHERE customer_unique_id = 'u-A'"
            )
    cnx.rollback()


def test_la_verification_reste_vraie_apres_un_changement_d_historique(cnx):
    charger(cnx, JOUR_1)
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'",
    )
    charger(cnx, JOUR_2)

    # Les versions fermées existent dans dim_client, mais seules les courantes se comptent.
    assert lire(cnx, "SELECT count(*) FROM dwh.dim_client") == [(5,)]
    assert code_sortie(verifier(cnx)) == 0


def test_un_echec_en_cours_de_chargement_n_ecrit_aucune_version(cnx, monkeypatch):
    from integration import chargement

    charger(cnx, JOUR_1)
    _modifier(
        cnx,
        "UPDATE staging.olist_customers SET customer_city = 'Brasilia' WHERE customer_id = 'cust-b1'",
    )

    def panne(curseur):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(chargement, "charger_fait_ligne_commande", panne)
    with pytest.raises(RuntimeError):
        charger(cnx, JOUR_2)

    # La fermeture de l'ancienne version a été annulée avec le reste.
    assert _versions_client(cnx, "u-B") == [("Sao Paulo", JOUR_1, None, True)]
