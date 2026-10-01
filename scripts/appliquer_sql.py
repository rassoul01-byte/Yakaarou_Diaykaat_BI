"""Application ordonnée des migrations SQL.

Les migrations sont stockées dans sql/ et portent un numéro dans leur nom.
Une migration déjà enregistrée dans public.schema_migrations n'est pas rejouée.
"""

from pathlib import Path

import psycopg2

from common.config import load_settings

RACINE_PROJET = Path(__file__).resolve().parents[1]
DOSSIER_SQL = RACINE_PROJET / "sql"


def trouver_migrations() -> list[Path]:
    """Retourne les fichiers SQL de migration dans l'ordre."""
    return sorted(DOSSIER_SQL.glob("*.sql"))


def main() -> None:
    """Applique les migrations qui ne sont pas encore enregistrées."""
    settings = load_settings()

    migrations = trouver_migrations()

    with psycopg2.connect(settings.postgres_dsn) as connexion:
        with connexion.cursor() as curseur:
            curseur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    version TEXT PRIMARY KEY,
                    appliquee_a TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )

            for migration in migrations:
                version = migration.name

                curseur.execute(
                    """
                    SELECT 1
                    FROM public.schema_migrations
                    WHERE version = %s
                    """,
                    (version,),
                )

                if curseur.fetchone():
                    print(f"[SKIP] {version}")
                    continue

                print(f"[APPLY] {version}")

                sql = migration.read_text(encoding="utf-8")
                curseur.execute(sql)

                curseur.execute(
                    """
                    INSERT INTO public.schema_migrations (version)
                    VALUES (%s)
                    """,
                    (version,),
                )

    print("Migrations terminées.")


if __name__ == "__main__":
    main()
