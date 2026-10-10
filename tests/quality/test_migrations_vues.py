"""Une migration ne retire jamais une colonne d'une vue existante.

Pourquoi ce fichier existe. PostgreSQL n'autorise `CREATE OR REPLACE VIEW` que
pour **ajouter des colonnes en fin de liste** : en insérer une au milieu, en
renommer ou en retirer une fait échouer la migration avec
`cannot drop columns from view` ou `cannot change name of view column`.

Trois migrations écrites le 2026-10-09 sont tombées dans ce piège, l'une après
l'autre, parce qu'elles redéfinissaient une vue de mémoire au lieu de repartir
de sa définition. L'une d'elles avait aussi perdu le filtre
`statut NOT IN ('canceled', 'unavailable')` : si PostgreSQL l'avait acceptée,
les commandes annulées seraient entrées dans le chiffre d'affaires, partout,
sans message d'erreur.

Ce contrôle rejoue l'historique des migrations dans l'ordre et vérifie, pour
chaque vue remplacée, que la nouvelle liste de colonnes commence par
l'ancienne. Il tourne sans base de données, donc en intégration continue.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SQL = Path(__file__).resolve().parents[2] / "sql"


def _sans_commentaires(texte: str) -> str:
    return re.sub(r"--[^\n]*", "", texte)


def _vider_parentheses(texte: str) -> str:
    """Remplace le CONTENU de chaque parenthèse par un espace, parenthèses gardées.

    Sans cela, deux pièges font dérailler l'analyse :
    `COUNT(*) FILTER (WHERE statut IS DISTINCT FROM 'succes')` contient un
    `FROM` qui coupe la liste des colonnes trop tôt, et une sous-requête
    `(SELECT MAX(x) FROM ...)` se fait prendre pour le SELECT publié. Seuls
    les NOMS nous intéressent : le contenu des parenthèses n'en porte aucun.
    """
    sortie, profondeur = [], 0
    for caractere in texte:
        if caractere == "(":
            profondeur += 1
            sortie.append("(")
        elif caractere == ")":
            profondeur -= 1
            sortie.append(")")
        elif profondeur == 0:
            sortie.append(caractere)
        elif caractere == "\n":
            sortie.append("\n")  # on garde les retours à la ligne pour la lisibilité
        else:
            sortie.append(" ")
    return "".join(sortie)


def _nom_de_colonne(expression: str) -> str:
    """Le nom que la vue publie : l'alias s'il existe, sinon la colonne lue."""
    sans_alias = re.split(r"\s+AS\s+", expression, flags=re.IGNORECASE)
    if len(sans_alias) > 1:
        return sans_alias[-1].strip()
    return expression.strip().split(".")[-1].strip()


def _vues_definies(chemin: Path) -> list[tuple[str, bool, list[str]]]:
    """(nom, remplacement, colonnes publiées) pour chaque vue du fichier."""
    texte = _vider_parentheses(_sans_commentaires(chemin.read_text(encoding="utf-8")))
    trouvees = []
    for bloc in re.finditer(
        r"CREATE\s+(OR\s+REPLACE\s+)?VIEW\s+([\w.]+)\s+AS\s*(.*?);", texte, re.S | re.I
    ):
        remplacement, nom, corps = bool(bloc.group(1)), bloc.group(2), bloc.group(3)
        # Les CTE sont vidées par `_vider_parentheses` : le premier SELECT
        # restant est celui que la vue publie.
        select = re.search(r"\bSELECT\b(.*?)\bFROM\b", corps, re.S | re.I)
        if not select:
            continue
        # `SELECT DISTINCT ON (...) a, b` : le modificateur n'est pas une colonne.
        liste = re.sub(r"^\s*DISTINCT(\s+ON\s*\([^)]*\))?", "", select.group(1), flags=re.I)
        colonnes = [_nom_de_colonne(morceau) for morceau in liste.split(",") if morceau.strip()]
        trouvees.append((nom, remplacement, colonnes))
    return trouvees


def test_aucune_migration_ne_retire_une_colonne_d_une_vue():
    """Rejoue toutes les migrations dans l'ordre et vérifie chaque remplacement."""
    publiees: dict[str, list[str]] = {}
    fautes: list[str] = []

    for migration in sorted(SQL.glob("*.sql")):
        for nom, remplacement, colonnes in _vues_definies(migration):
            precedentes = publiees.get(nom)
            if remplacement and precedentes and colonnes[: len(precedentes)] != precedentes:
                fautes.append(
                    f"{migration.name} : {nom} ne commence plus par ses colonnes "
                    f"d'origine.\n      avant : {precedentes}\n      apres : {colonnes}"
                )
            publiees[nom] = colonnes

    assert not fautes, "\n".join(
        ["Un remplacement de vue ne peut qu'ajouter des colonnes en fin de liste :", *fautes]
    )


# --- Le périmètre des ventes ------------------------------------------------


@pytest.mark.parametrize("migration", ["010_vues_indicateurs.sql", "025_annee_iso.sql"])
def test_le_perimetre_des_ventes_est_le_meme_partout(migration):
    """Le filtre sur le statut EST la définition du chiffre d'affaires.

    Toute migration qui redéfinit `v_ventes_retenues` doit le reprendre : sans
    lui, les commandes annulées entrent dans le chiffre d'affaires.
    """
    texte = (SQL / migration).read_text(encoding="utf-8")
    if "v_ventes_retenues AS" not in texte:
        pytest.skip(f"{migration} ne redéfinit pas v_ventes_retenues")

    assert re.search(r"WHERE\s+c\.statut\s+NOT\s+IN\s*\(\s*'canceled',\s*'unavailable'\s*\)", texte)
