"""`scripts/appliquer_sql.py` passe, de la base vide à l'entrepôt complet.

Pourquoi ce fichier existe. Le 2026-10-09, trois migrations écrites l'une
après l'autre ont échoué **sur la base du projet**, à l'exécution de
`scripts/appliquer_sql.py`, chacune pour la même raison :
`CREATE OR REPLACE VIEW` n'autorise que l'ajout de colonnes en fin de liste.
Une quatrième faute n'est apparue qu'ensuite : `sql/007` ne déclarait pas la
colonne `annee_iso` que le chargement s'était mis à écrire, donc tout entrepôt
bâti à neuf était cassé.

Aucune de ces quatre fautes n'était visible sans base de données. Le contrôle
statique `tests/quality/test_migrations_vues.py` en attrape la forme — une
colonne qui disparaît d'une vue — mais il ne sait pas si le fichier s'exécute.
Ce test-ci le sait : il lance la **vraie commande**, celle qui a échoué, sur
une base neuve et jetable, puis vérifie que l'entrepôt obtenu tient debout.

Il tourne dans le travail `integration-postgres` de la CI, qui dispose d'un
service PostgreSQL. En local :  pytest -m integration tests/integration
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest

from common.config import load_settings

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_SQL = RACINE / "sql"
SCRIPT = RACINE / "scripts" / "appliquer_sql.py"
INITIALISATION = RACINE / "docker" / "postgres" / "init" / "01-databases.sql"

# Une base à part, détruite et refaite à chaque test : appliquer une migration
# n'a de sens que depuis un état connu.
BASE_DES_MIGRATIONS = "dataflow360_migrations"


def _sql_executable(initialisation: str) -> str:
    """Le fichier d'initialisation, sans ce qui n'a de sens que dans `psql`.

    Deux instructions sortent du cadre d'une base : `CREATE DATABASE`, qui crée
    les bases voisines, et la méta-commande `\\connect`, que seul `psql`
    comprend. Tout le reste — les trois schémas et le journal d'exécution — est
    du SQL ordinaire, et c'est ce qui nous intéresse.

    On repart du vrai fichier au lieu d'en recopier le contenu : une base
    d'essai bâtie sur une copie ne prouve rien sur la vraie.
    """
    texte = re.sub(r"(?im)^\s*CREATE\s+DATABASE\s+\w+\s*;", "", initialisation)
    return "\n".join(ligne for ligne in texte.splitlines() if not ligne.lstrip().startswith("\\"))


def _appliquer_sql(dsn: str) -> subprocess.CompletedProcess[str]:
    """Lance `scripts/appliquer_sql.py` sur cette base, comme en production.

    Un sous-processus et non un import : c'est la commande entière qui est
    testée, y compris la lecture de `POSTGRES_DSN` dans l'environnement et ce
    qu'elle affiche. C'est exactement ce que lance l'équipe.
    """
    environnement = os.environ | {
        "POSTGRES_DSN": dsn,
        "PYTHONPATH": os.pathsep.join([str(RACINE / "src"), str(RACINE)]),
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=environnement,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


@pytest.fixture
def base_initialisee() -> str:
    """Une base vide avec les schémas du Sprint 0, avant toute migration."""
    dsn_projet = load_settings().postgres_dsn

    admin = psycopg2.connect(dsn_projet)
    try:
        admin.autocommit = True  # CREATE/DROP DATABASE refusent les transactions
        with admin.cursor() as curseur:
            curseur.execute(f'DROP DATABASE IF EXISTS "{BASE_DES_MIGRATIONS}" WITH (FORCE)')
            curseur.execute(f'CREATE DATABASE "{BASE_DES_MIGRATIONS}"')
    finally:
        admin.close()

    morceaux = urlsplit(dsn_projet)
    dsn = urlunsplit(morceaux._replace(path=f"/{BASE_DES_MIGRATIONS}"))

    connexion = psycopg2.connect(dsn)
    connexion.autocommit = True
    try:
        with connexion.cursor() as curseur:
            curseur.execute(_sql_executable(INITIALISATION.read_text(encoding="utf-8")))
    finally:
        connexion.close()
    return dsn


@pytest.fixture
def base_migree(base_initialisee: str) -> str:
    """La base initialisée, après un passage complet de `appliquer_sql.py`."""
    resultat = _appliquer_sql(base_initialisee)
    if resultat.returncode != 0:
        pytest.fail(
            "scripts/appliquer_sql.py a échoué sur une base neuve :\n"
            f"{resultat.stdout}\n{resultat.stderr}"
        )
    return base_initialisee


def _lignes(dsn: str, requete: str) -> list[tuple]:
    with psycopg2.connect(dsn) as connexion, connexion.cursor() as curseur:
        curseur.execute(requete)
        return curseur.fetchall()


def _un(dsn: str, requete: str):
    lignes = _lignes(dsn, requete)
    return lignes[0][0] if lignes else None


# --- La commande passe -------------------------------------------------------


@pytest.mark.integration
def test_l_initialisation_porte_bien_les_schemas_et_le_journal():
    """Le filtrage ne doit pas avoir vidé le fichier de sa substance.

    Si quelqu'un restructure `01-databases.sql`, ce test parle avant que les
    autres n'échouent pour une raison qui ressemblerait à un défaut de migration.
    """
    sql = _sql_executable(INITIALISATION.read_text(encoding="utf-8"))

    for schema in ("raw_quarantine", "staging", "dwh"):
        assert f"CREATE SCHEMA IF NOT EXISTS {schema}" in sql
    assert "staging.execution_log" in sql
    assert "CREATE DATABASE" not in sql.upper()


@pytest.mark.integration
def test_toutes_les_migrations_s_appliquent_sur_une_base_neuve(base_initialisee):
    """Le test central : la vraie commande, du schéma vide à l'entrepôt.

    Chaque fichier de `sql/` doit apparaître une fois en `[APPLY]`, et la
    commande doit rendre 0. C'est le contrôle qui manquait : les trois échecs
    du 2026-10-09 se sont produits ici, après une suite de tests toute verte.
    """
    resultat = _appliquer_sql(base_initialisee)

    assert resultat.returncode == 0, f"{resultat.stdout}\n{resultat.stderr}"

    appliquees = set(re.findall(r"\[APPLY\] (\S+)", resultat.stdout))
    attendues = {chemin.name for chemin in DOSSIER_SQL.glob("*.sql")}
    assert appliquees == attendues


@pytest.mark.integration
def test_relancer_la_commande_n_applique_plus_rien(base_migree):
    """La deuxième exécution ne doit rien rejouer, et ne rien casser.

    C'est la garantie réelle du projet, et elle ne vient pas des fichiers :
    `sql/001` commence par `ALTER SCHEMA raw_quarantine RENAME TO quarantaine`,
    qui ne peut pas repasser deux fois. C'est `public.schema_migrations` qui
    protège, en enregistrant ce qui est déjà passé. Ce test vérifie cette
    table, pas une idempotence que les fichiers n'ont jamais eue.
    """
    resultat = _appliquer_sql(base_migree)

    assert resultat.returncode == 0, f"{resultat.stdout}\n{resultat.stderr}"
    assert "[APPLY]" not in resultat.stdout

    enregistrees = {
        ligne[0] for ligne in _lignes(base_migree, "SELECT version FROM public.schema_migrations")
    }
    assert enregistrees == {chemin.name for chemin in DOSSIER_SQL.glob("*.sql")}


# --- Ce que l'entrepôt obtenu doit garantir ---------------------------------


@pytest.mark.integration
def test_toutes_les_vues_sont_interrogeables(base_migree):
    """Une vue peut se créer et pourtant ne pas s'exécuter.

    PostgreSQL vérifie les noms à la création, mais `SELECT` est le seul moyen
    de savoir qu'une vue bâtie sur une autre, elle-même remplacée depuis,
    rend encore un résultat.
    """
    vues = _lignes(
        base_migree,
        """
        SELECT n.nspname, c.relname
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE c.relkind = 'v'
          AND n.nspname IN ('dwh', 'staging', 'quarantaine')
        ORDER BY 1, 2
        """,
    )

    assert vues, "aucune vue créée : les migrations n'ont pas abouti"

    with psycopg2.connect(base_migree) as connexion, connexion.cursor() as curseur:
        for schema, nom in vues:
            try:
                curseur.execute(f'SELECT * FROM "{schema}"."{nom}" LIMIT 0')
            except psycopg2.Error as erreur:
                pytest.fail(f"{schema}.{nom} ne s'exécute pas :\n{erreur}")


@pytest.mark.integration
def test_annee_iso_est_obligatoire_et_en_derniere_position(base_migree):
    """`dim_date` doit avoir la même forme, base neuve ou base complétée.

    `sql/007` déclare la colonne ; `sql/025` l'ajoute par ALTER sur les bases
    déjà installées, donc en dernière position. Les deux chemins ne peuvent
    aboutir à la même table que si la déclaration est elle aussi en dernier.
    Obligatoire, car une `annee_iso` nulle créerait dans
    `v_ventes_par_semaine` un groupe sans nom, absent du total sans que rien
    ne le signale.
    """
    colonnes = _lignes(
        base_migree,
        """
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'dwh' AND table_name = 'dim_date'
        ORDER BY ordinal_position
        """,
    )

    assert colonnes[-1] == ("annee_iso", "NO")


@pytest.mark.integration
def test_la_ligne_date_inconnue_garde_ses_zeros(base_migree):
    """La date « inconnue » ne doit pas se mettre à prétendre être 1900.

    `sql/007` donne 0 à toutes les parties de cette ligne, précisément pour
    qu'elle ne se confonde pas avec une date réelle ; sa date de remplissage
    1900-01-01 n'est qu'un repère. Calculer `EXTRACT(ISOYEAR)` dessus lui
    donnerait 1900, et un regroupement par semaine afficherait « 1900-S0 ».
    """
    ligne = _lignes(
        base_migree,
        """
        SELECT annee, trimestre, mois, semaine_iso, jour, annee_iso
        FROM dwh.dim_date
        WHERE date_id = 0
        """,
    )

    assert ligne == [(0, 0, 0, 0, 0, 0)]


@pytest.mark.integration
def test_le_perimetre_des_ventes_exclut_toujours_les_commandes_annulees(base_migree):
    """Le filtre sur le statut EST la définition du chiffre d'affaires.

    Il a disparu une fois d'une réécriture de `v_ventes_retenues` ; PostgreSQL
    a refusé la migration pour une autre raison, et c'est le seul hasard qui a
    empêché les commandes annulées d'entrer dans le chiffre d'affaires.
    """
    definition = _un(base_migree, "SELECT pg_get_viewdef('dwh.v_ventes_retenues', true)")

    for statut in ("canceled", "unavailable"):
        assert statut in definition, f"{statut} n'est plus exclu de v_ventes_retenues"


@pytest.mark.integration
def test_le_segment_et_le_modele_comptent_les_commandes_au_meme_endroit(base_migree):
    """`sql/028` a sorti le segment du détour par les variables du modèle.

    Avant, `v_segment_a_retenir` lisait `v_historique_client`, qui calculait
    seize variables pour n'en rendre que cinq : deux secondes de PostgreSQL
    pour afficher un seul nombre sur le tableau de bord. Les deux vues lisent
    maintenant `v_socle_client`.

    Ce qu'on garde ici, c'est la propriété qui compte : le nombre de commandes
    d'une personne est calculé **une seule fois**. Une réécriture qui
    redonnerait au segment sa propre expression de `commandes >= 2` ferait
    échouer ce contrôle avant qu'un écart n'apparaisse entre le chiffre du
    tableau de bord et celui du dossier.
    """
    for vue in ("dwh.v_segment_a_retenir", "dwh.v_historique_client"):
        definition = _un(base_migree, f"SELECT pg_get_viewdef('{vue}', true)")
        assert "v_socle_client" in definition, (
            f"{vue} ne lit plus dwh.v_socle_client : le compte des commandes "
            f"a été redéfini quelque part, et les deux peuvent diverger"
        )

    # Et la règle du segment est bien celle du dictionnaire, à la date publiée.
    segment = _un(base_migree, "SELECT pg_get_viewdef('dwh.v_segment_a_retenir', true)")
    assert "commandes >= 2" in segment
    assert "v_date_segment" in segment
