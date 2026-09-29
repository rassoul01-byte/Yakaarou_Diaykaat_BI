"""
Gestion des sorties du contrôle qualité DataFlow360.

F1.5 :
- lignes valides -> staging
- lignes rejetées -> quarantine
"""

from pathlib import Path

import pandas as pd


STAGING_DIR = Path("data/staging")
QUARANTINE_DIR = Path("data/quarantine")


def ecrire_staging(df, source, table):
    """
    Écrit les lignes validées dans la zone staging.
    """
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    chemin = STAGING_DIR / source
    chemin.mkdir(parents=True, exist_ok=True)

    fichier = chemin / f"{table}.csv"

    df.to_csv(fichier, index=False)

    print(f"\nSTAGING")
    print("Fichier :", fichier)
    print("Lignes écrites :", len(df))

    return fichier


def ecrire_quarantaine(df, source, table, rule_id):
    """
    Écrit les lignes rejetées dans la zone quarantine.
    """
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    chemin = QUARANTINE_DIR / source
    chemin.mkdir(parents=True, exist_ok=True)

    fichier = chemin / f"{table}_{rule_id}.csv"

    df.to_csv(fichier, index=False)

    print(f"\nQUARANTAINE")
    print("Règle :", rule_id)
    print("Fichier :", fichier)
    print("Lignes rejetées :", len(df))

    return fichier


def ecrire_execution_log(resultats, source):
    """
    Enregistre le résultat de chaque règle dans un journal CSV.
    F1.5 - traçabilité des contrôles qualité.
    """
    log_dir = STAGING_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    fichier = log_dir / "execution_log.csv"

    df_log = pd.DataFrame(resultats)
    df_log.insert(0, "source", source)

    df_log.to_csv(fichier, index=False)

    print("\nEXECUTION LOG")
    print("Fichier :", fichier)
    print("Contrôles enregistrés :", len(df_log))

    return fichier
