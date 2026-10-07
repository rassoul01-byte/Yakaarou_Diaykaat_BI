"""La fabrique rend le retrouveur attendu selon l'environnement."""

from __future__ import annotations

import pytest

from assistant.fabrique import creer_retrouveur
from assistant.retrouveur import RetrouveurDepannage, RetrouveurExterne


def test_defaut_est_externe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASSISTANT_RETROUVEUR", raising=False)
    assert isinstance(creer_retrouveur(), RetrouveurExterne)


def test_bascule_depannage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSISTANT_RETROUVEUR", "depannage")
    assert isinstance(creer_retrouveur(), RetrouveurDepannage)


def test_choix_invalide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSISTANT_RETROUVEUR", "nimportequoi")
    with pytest.raises(ValueError, match="inconnu"):
        creer_retrouveur()


def test_espace_et_casse_ignores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSISTANT_RETROUVEUR", "  EXTERNE  ")
    assert isinstance(creer_retrouveur(), RetrouveurExterne)