"""Tests off-SAP du garde de compatibilité de la surcouche sapfx-mcp
(``sap_robotmcp._compat``), convention #5 du CLAUDE.md. Le test « vivant »
vérifie le vrai rf-mcp installé : si un upgrade casse un point d'ancrage, ce
fichier vire au rouge AVANT le premier lancement du serveur."""
import pytest

robotmcp = pytest.importorskip("robotmcp", reason="rf-mcp non installé")

from sap_robotmcp import _compat  # noqa: E402


def test_check_compat_passes_against_the_installed_rfmcp():
    # Garde vivant : la fenêtre validée et chaque point d'ancrage existent.
    assert _compat.check_compat() == []


def test_version_outside_the_tested_window_is_reported(monkeypatch):
    monkeypatch.setattr(_compat, "robotmcp_version", lambda: "0.99.0")
    problems = _compat.check_compat()
    assert any("hors de la fenêtre validée" in p for p in problems)


def test_missing_distribution_is_reported(monkeypatch):
    monkeypatch.setattr(_compat, "robotmcp_version", lambda: None)
    problems = _compat.check_compat()
    assert any("introuvable" in p for p in problems)


def test_unparsable_version_is_reported(monkeypatch):
    monkeypatch.setattr(_compat, "robotmcp_version", lambda: "dev")
    problems = _compat.check_compat()
    assert any("illisible" in p for p in problems)


def test_a_vanished_anchor_attribute_is_reported(monkeypatch):
    monkeypatch.setattr(_compat, "_ANCHORS", [
        ("robotmcp.plugins.manager", ["get_library_plugin_manager",
                                      "attr_qui_n_existe_pas"]),
    ])
    problems = _compat.check_compat()
    assert any("attr_qui_n_existe_pas" in p and "disparu" in p
               for p in problems)


def test_an_unimportable_anchor_module_is_reported(monkeypatch):
    monkeypatch.setattr(_compat, "_ANCHORS",
                        [("module_fantome_sapfx", ["x"])])
    problems = _compat.check_compat()
    assert any("inimportable" in p and "module_fantome_sapfx" in p
               for p in problems)


# --- sonde get_session (proxy lazy rf-mcp >= 0.34) ---------------------------

class _FakeModule:
    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)


def _patch_import(monkeypatch, mapping):
    real_import = _compat.importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name in mapping:
            value = mapping[name]
            if isinstance(value, Exception):
                raise value
            return value
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(_compat.importlib, "import_module", fake_import)


def test_get_session_anchor_probes_the_class_without_touching_the_proxy(
        monkeypatch):
    # Depuis rf-mcp 0.34, execution_engine est un proxy LAZY : la sonde doit
    # regarder la classe ExecutionCoordinator et ne JAMAIS matérialiser le
    # moteur via un attribut du proxy.
    class Coordinator:
        def get_session(self, session_id):
            return None

    class ExplodingProxy:
        def __getattr__(self, name):
            raise AssertionError(
                "la sonde a matérialisé le moteur lazy (accès %r)" % name)

    _patch_import(monkeypatch, {
        "robotmcp.components.execution.execution_coordinator":
            _FakeModule(ExecutionCoordinator=Coordinator),
        "robotmcp.server": _FakeModule(execution_engine=ExplodingProxy()),
    })
    assert _compat._has_get_session_anchor() is True


def test_a_vanished_get_session_is_reported_from_the_class_probe(monkeypatch):
    class CoordinatorSansGetSession:
        pass

    _patch_import(monkeypatch, {
        "robotmcp.components.execution.execution_coordinator":
            _FakeModule(ExecutionCoordinator=CoordinatorSansGetSession),
    })
    problems = _compat.check_compat()
    assert any("get_session" in p and "disparu" in p for p in problems)


def test_get_session_anchor_falls_back_to_the_engine_instance(monkeypatch):
    # rf-mcp sans le module coordinator à ce chemin : repli sur l'instance.
    class Engine:
        def get_session(self, session_id):
            return None

    _patch_import(monkeypatch, {
        "robotmcp.components.execution.execution_coordinator":
            ImportError("chemin déplacé"),
        "robotmcp.server": _FakeModule(execution_engine=Engine()),
    })
    assert _compat._has_get_session_anchor() is True
