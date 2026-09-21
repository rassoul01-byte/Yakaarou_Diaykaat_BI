"""Configuration partagée des tests.

Les tests marqués « integration » exigent les services démarrés. Ils sont
ignorés par défaut, et exécutés avec :  pytest -m integration
"""

import pytest


def pytest_collection_modifyitems(config, items):
    if config.getoption("-m"):
        return
    passer = pytest.mark.skip(reason="test d'intégration : lancer avec -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(passer)
