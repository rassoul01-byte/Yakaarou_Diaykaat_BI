"""Copie d'audit en CSV du contrôle qualité DataFlow360.

Ces fichiers ne sont PAS la zone intermédiaire : la seule vérité est
PostgreSQL (staging.<tables>, quarantaine.rejets, staging.execution_log),
alimentée par quality.chargement. Cette copie sert à relire un contrôle
sans base de données (débogage, revue de règle). Elle n'est écrite qu'à la
demande (--export-csv) et n'est lue par aucun traitement.

Arborescence, une par ingestion contrôlée :

    data/audit_qualite/<source>/ingestion=<id>/
    ├── valides/<table>.csv
    ├── rejets/<table>_<regle>.csv
    └── execution_log.csv
"""

from pathlib import Path

import pandas as pd

from common.config import load_settings


def dossier_audit(source, ingestion, racine=None):
    """Dossier d'audit d'une ingestion contrôlée."""
    racine = Path(racine) if racine else load_settings().data_dir / "audit_qualite"
    return racine / source / f"ingestion={ingestion}"


def exporter_audit(resultat, racine=None):
    """Écrit la copie d'audit d'un ResultatControle et renvoie son dossier."""
    dossier = dossier_audit(resultat.source, resultat.ingestion, racine)
    (dossier / "valides").mkdir(parents=True, exist_ok=True)
    (dossier / "rejets").mkdir(parents=True, exist_ok=True)

    for table, df in resultat.valides.items():
        df.to_csv(dossier / "valides" / f"{table}.csv", index=False)

    for lot in resultat.rejets:
        fichier = dossier / "rejets" / f"{lot.table}_{lot.regle['identifiant']}.csv"
        lot.lignes.to_csv(fichier, index=False)

    df_log = pd.DataFrame(resultat.controles)
    df_log.insert(0, "source", resultat.source)
    df_log.to_csv(dossier / "execution_log.csv", index=False)

    print("\nCOPIE D'AUDIT CSV")
    print("Dossier :", dossier)

    return dossier
