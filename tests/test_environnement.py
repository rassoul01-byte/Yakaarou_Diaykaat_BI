"""Premier test du projet.

Il est volontairement simple : son rôle n'est pas de vérifier une logique
métier, mais de prouver que la chaîne de test fonctionne — que les
dépendances s'installent, que le code du projet s'importe et que pytest
les trouve. Le Sprint 2 n'aura plus qu'à écrire de vrais tests.
"""

import importlib
import sys

import pytest

BIBLIOTHEQUES_DU_SOCLE = [
    "pandas",
    "dotenv",
    "yaml",
    "sqlalchemy",
    "psycopg2",
    "pymongo",
    "elasticsearch",
    "confluent_kafka",
    "faker",
]


def test_version_de_python():
    assert sys.version_info >= (3, 11), "le projet exige Python 3.11 ou plus"


@pytest.mark.parametrize("module", BIBLIOTHEQUES_DU_SOCLE)
def test_bibliotheque_installee(module):
    importlib.import_module(module)


def test_le_code_du_projet_est_importable():
    importlib.import_module("common.config")
