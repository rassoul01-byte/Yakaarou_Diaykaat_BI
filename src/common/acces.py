"""Compte de lecture seule pour les outils de restitution.

Power BI se connecte à l'entrepôt avec ce compte. Il peut tout lire et rien
écrire : un tableau de bord n'a aucune raison de modifier une donnée, et un
outil branché en écriture sur un entrepôt finit toujours par y écrire.

Le mot de passe vient de l'environnement et n'est jamais versionné.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import psycopg2
from psycopg2 import sql

from .config import load_settings

# Les schémas auxquels le compte a accès, dans l'ordre où on les traite.
SCHEMAS_LISIBLES = ("dwh", "quarantaine", "staging")

UTILISATEUR_PAR_DEFAUT = "powerbi_lecture"

# Un nom de rôle ne peut pas être passé en paramètre à PostgreSQL : il est
# donc validé ici, puis cité par psycopg2. Sans cette validation, un nom de
# compte venu de l'environnement pourrait porter n'importe quoi.
_NOM_VALIDE = re.compile(r"[a-z_][a-z0-9_]{2,62}")


@dataclass(frozen=True)
class Resultat:
    utilisateur: str
    cree: bool
    schemas_accordes: tuple
    schemas_absents: tuple


def identifiants() -> tuple[str, str]:
    """Nom et mot de passe du compte, lus dans l'environnement."""
    utilisateur = os.getenv("POWERBI_UTILISATEUR", UTILISATEUR_PAR_DEFAUT)
    motdepasse = os.getenv("POWERBI_MOTDEPASSE", "")
    valider_nom(utilisateur)
    if not motdepasse:
        raise ValueError(
            "POWERBI_MOTDEPASSE n'est pas défini — l'ajouter à votre .env, jamais à .env.example"
        )
    return utilisateur, motdepasse


def valider_nom(utilisateur: str) -> None:
    if not _NOM_VALIDE.fullmatch(utilisateur):
        raise ValueError(
            f"nom de compte invalide : {utilisateur!r} — minuscules, chiffres "
            "et tirets bas uniquement, au moins trois caractères"
        )


def nom_de_base(dsn: str) -> str:
    """Nom de la base, extrait de la chaîne de connexion."""
    from urllib.parse import urlsplit

    return urlsplit(dsn).path.lstrip("/") or "postgres"


def creer_compte_lecture(
    utilisateur: str, motdepasse: str, dsn: str | None = None, schemas=SCHEMAS_LISIBLES
) -> Resultat:
    """Crée ou met à jour le compte, et lui accorde la lecture.

    Relançable sans risque : un compte existant voit son mot de passe mis à
    jour et ses droits réaffirmés. Un schéma absent est signalé, pas fatal :
    l'entrepôt peut ne pas encore exister au moment où l'on prépare l'accès.
    """
    valider_nom(utilisateur)
    dsn = dsn or load_settings().postgres_dsn
    base = nom_de_base(dsn)
    role = sql.Identifier(utilisateur)
    accordes, absents = [], []

    connexion = psycopg2.connect(dsn)
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            curseur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (utilisateur,))
            existe = bool(curseur.fetchone())
            ordre = (
                "ALTER ROLE {} WITH LOGIN PASSWORD %s"
                if existe
                else ("CREATE ROLE {} WITH LOGIN PASSWORD %s")
            )
            curseur.execute(sql.SQL(ordre).format(role), (motdepasse,))

            curseur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(base), role)
            )
            # Aucun droit de création, nulle part : ce compte lit, un point.
            curseur.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(role))

            for schema in schemas:
                curseur.execute(
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                    (schema,),
                )
                if not curseur.fetchone():
                    absents.append(schema)
                    continue
                identifiant = sql.Identifier(schema)
                curseur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(identifiant, role))
                curseur.execute(
                    sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
                        identifiant, role
                    )
                )
                # Les tables et vues créées plus tard seront lisibles aussi :
                # sans cela, chaque migration demanderait de rejouer ce script.
                curseur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {}"
                    ).format(identifiant, role)
                )
                accordes.append(schema)
    finally:
        connexion.close()

    return Resultat(utilisateur, not existe, tuple(accordes), tuple(absents))


def dsn_du_compte(utilisateur: str, motdepasse: str, dsn: str | None = None) -> str:
    """Chaîne de connexion du compte de lecture, pour le vérifier."""
    from urllib.parse import quote, urlsplit, urlunsplit

    morceaux = urlsplit(dsn or load_settings().postgres_dsn)
    hote = morceaux.hostname or ""
    port = f":{morceaux.port}" if morceaux.port else ""
    autorite = f"{quote(utilisateur)}:{quote(motdepasse)}@{hote}{port}"
    return urlunsplit(morceaux._replace(netloc=autorite))


def verifier_lecture_seule(utilisateur: str, motdepasse: str, dsn: str | None = None) -> list[str]:
    """Se connecte avec le compte et vérifie qu'il lit mais n'écrit pas.

    Renvoie la liste des anomalies — une liste vide signifie que le compte est
    bien en lecture seule. Ce contrôle est le critère de réussite du livrable :
    il ne suffit pas d'avoir voulu un compte en lecture, il faut le prouver.
    """
    anomalies = []
    connexion = psycopg2.connect(dsn_du_compte(utilisateur, motdepasse, dsn))
    try:
        connexion.autocommit = True
        with connexion.cursor() as curseur:
            try:
                curseur.execute("SELECT 1")
            except psycopg2.Error as erreur:
                anomalies.append(f"lecture impossible : {erreur.__class__.__name__}")

            for ordre, description in (
                ("CREATE TABLE public.essai_lecture_seule (x int)", "créer une table"),
                ("CREATE SCHEMA essai_lecture_seule", "créer un schéma"),
            ):
                try:
                    curseur.execute(ordre)
                    anomalies.append(f"le compte peut {description}")
                except psycopg2.Error:
                    pass  # refus attendu
    finally:
        connexion.close()
    return anomalies
