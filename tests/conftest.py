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


@pytest.fixture(autouse=True)
def _retrouveur_depannage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les tests unitaires ne dépendent pas d'Elasticsearch.

    Le retrouveur par défaut de l'assistant (RetrouveurExterne) exige un index
    ES joignable, ce qui n'a pas de sens en test. On force le dépannage (TF-IDF
    en mémoire). La couverture du retrouveur externe vit dans tests/integration/.
    """
    monkeypatch.setenv("ASSISTANT_RETROUVEUR", "depannage")


@pytest.fixture(autouse=True)
def _journal_isole(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Aucun test n'écrit dans le journal du dépôt.

    L'API journalise chaque échange ; sans ce redirigement, lancer la suite
    salirait `data/assistant/journal.jsonl` avec des questions de test, qui
    seraient ensuite chargées en base comme de l'usage réel.
    """
    monkeypatch.setenv("ASSISTANT_JOURNAL", str(tmp_path / "journal_de_test.jsonl"))
