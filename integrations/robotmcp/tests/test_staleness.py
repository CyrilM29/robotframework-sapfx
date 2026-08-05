"""Tests off-SAP de la détection de code modifié après le démarrage du serveur
rf-mcp (``sap_robotmcp._staleness``), convention #5 du CLAUDE.md.

Le piège couvert : rf-mcp fige classes et instances de bibliothèques pour tout
le process : un fichier de ``src/`` modifié après le démarrage n'est PAS pris
en compte par ``manage_session init``, et l'agent debugge un comportement qui
n'existe plus dans les sources.
"""
import sys
import time
import types

from sap_robotmcp import _staleness

_FAKE_NAME = "SapEccLibrary._fake_for_staleness_tests"


def _install_fake_module(tmp_path, monkeypatch, name=_FAKE_NAME):
    src = tmp_path / "fake_mod.py"
    src.write_text("x = 1", encoding="utf-8")
    module = types.ModuleType(name)
    module.__file__ = str(src)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def test_stale_modules_detects_a_source_file_newer_than_the_baseline(tmp_path, monkeypatch):
    _install_fake_module(tmp_path, monkeypatch)
    # référence dans le passé -> le fichier (créé maintenant) est plus récent
    assert _FAKE_NAME in _staleness.stale_modules(since=time.time() - 3600)


def test_stale_modules_empty_when_nothing_changed_since_the_baseline(tmp_path, monkeypatch):
    _install_fake_module(tmp_path, monkeypatch)
    # référence dans le futur -> rien ne peut être plus récent
    assert _staleness.stale_modules(since=time.time() + 3600) == []


def test_stale_modules_ignores_modules_without_a_file_or_unreadable(tmp_path, monkeypatch):
    no_file = types.ModuleType("sapfx_common._fake_no_file")
    monkeypatch.setitem(sys.modules, "sapfx_common._fake_no_file", no_file)
    ghost = types.ModuleType("sapfx_common._fake_ghost_file")
    ghost.__file__ = str(tmp_path / "does_not_exist.py")
    monkeypatch.setitem(sys.modules, "sapfx_common._fake_ghost_file", ghost)
    names = _staleness.stale_modules(since=time.time() - 3600)
    assert "sapfx_common._fake_no_file" not in names
    assert "sapfx_common._fake_ghost_file" not in names


def test_stale_modules_only_watches_the_sapfx_prefixes(tmp_path, monkeypatch):
    _install_fake_module(tmp_path, monkeypatch, name="некое_autre.module")
    assert "некое_autre.module" not in _staleness.stale_modules(
        since=time.time() - 3600)


def test_staleness_warning_names_the_modules_and_the_fix(tmp_path, monkeypatch):
    _install_fake_module(tmp_path, monkeypatch)
    warning = _staleness.staleness_warning(since=time.time() - 3600)
    assert warning is not None
    assert _FAKE_NAME in warning
    assert "Redémarrer le serveur rf-mcp" in warning


def test_staleness_warning_is_none_when_nothing_changed():
    assert _staleness.staleness_warning(since=time.time() + 3600) is None
