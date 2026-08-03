"""Tests hors-SAP de ``sapfx_common.com_safety`` (convention #5 du CLAUDE.md).

Cette aide était dupliquée à l'identique dans ``_connection.py`` (ECC) et
``_rf_context.py`` (rf-mcp) ; centralisée ici, elle n'a plus qu'un seul jeu de
tests à maintenir. Les deux modules appelants ont leurs propres tests qui
vérifient qu'ils délèguent bien à cette fonction (test_logic.py,
tests/unit — pas de duplication de couverture, juste de délégation).
"""
import pytest

from sapfx_common.com_safety import ensure_com_initialized


def test_ensure_com_initialized_calls_pythoncom_coinitialize(monkeypatch):
    import pythoncom
    calls = []
    monkeypatch.setattr(pythoncom, "CoInitialize", lambda: calls.append(1), raising=False)
    ensure_com_initialized()
    assert calls == [1]


def test_ensure_com_initialized_tolerates_missing_coinitialize(monkeypatch):
    import pythoncom
    monkeypatch.delattr(pythoncom, "CoInitialize", raising=False)
    ensure_com_initialized()  # ne doit pas lever (AttributeError avalée)


def test_ensure_com_initialized_tolerates_already_initialized(monkeypatch):
    import pythoncom

    def already_done():
        raise pythoncom.com_error("already initialized")
    monkeypatch.setattr(pythoncom, "CoInitialize", already_done, raising=False)
    ensure_com_initialized()  # ne doit pas lever (com_error avalée)


def test_ensure_com_initialized_propagates_unexpected_com_errors(monkeypatch):
    import pythoncom

    def real_failure():
        raise OSError("mauvais modèle d'appartement")
    monkeypatch.setattr(pythoncom, "CoInitialize", real_failure, raising=False)
    with pytest.raises(OSError):
        ensure_com_initialized()  # une vraie panne COM doit remonter, pas être masquée
