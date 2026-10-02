"""Petits outils partagés par les tests de l'entrepôt."""

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def lire(cnx, sql: str, parametres=None) -> list[tuple]:
    """Exécute une requête et retourne toutes ses lignes, sans rien laisser d'ouvert."""
    with cnx.cursor() as curseur:
        curseur.execute(sql, parametres)
        lignes = curseur.fetchall()
    cnx.rollback()
    return lignes
