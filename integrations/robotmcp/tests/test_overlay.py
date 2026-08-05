"""Tests off-SAP de la surcouche sapfx-mcp (``sap_robotmcp._overlay`` +
montage ``sap_robotmcp.server``), convention #5 du CLAUDE.md.

La logique se teste avec des doublures injectées (moteur, manager, exécuteur
de keyword) ; le montage se vérifie contre la VRAIE instance FastMCP de
rf-mcp, sans lancer le serveur ni toucher SAP.
"""
import asyncio
import base64

import pytest

from sap_robotmcp import _overlay


# --- doublures ----------------------------------------------------------------

_PNG = b"\x89PNG\r\n\x1a\nfake-png-bytes"


class FakeSession:
    def __init__(self, session_id="s1", imported=("SapEccLibrary",)):
        self.session_id = session_id
        self.imported_libraries = list(imported)
        self.variables = {}


class FakeEngine:
    def __init__(self, sessions=None, boom=False):
        self._sessions = sessions or {}
        self._boom = boom

    def get_session(self, session_id):
        if self._boom:
            raise RuntimeError("session manager cassé")
        return self._sessions.get(session_id)


class FakeProvider:
    def __init__(self, page=None, app=None, page_exc=None):
        self._page, self._app, self._page_exc = page, app, page_exc

    async def get_page_source(self, session, **kwargs):
        if self._page_exc:
            raise self._page_exc
        return dict(self._page or {}, kwargs=kwargs)

    async def get_application_state(self, session):
        return self._app


class FakeManager:
    def __init__(self, providers=None):
        self._providers = providers or {}

    def get_state_provider(self, name):
        return self._providers.get(name)


# --- pick_library / resolve_session ------------------------------------------

def test_pick_library_returns_the_single_sapfx_library():
    assert _overlay.pick_library(FakeSession()) == "SapEccLibrary"


def test_pick_library_rejects_an_unknown_explicit_library():
    out = _overlay.pick_library(FakeSession(), library="Browser")
    assert out["success"] is False and "inconnue" in out["error"]


def test_pick_library_flags_a_session_without_sapfx_library():
    out = _overlay.pick_library(FakeSession(imported=("Browser", "BuiltIn")))
    assert out["success"] is False and "aucune bibliothèque SAPFX" in out["error"]


def test_pick_library_raises_ambiguity_when_both_are_imported():
    session = FakeSession(imported=("SapEccLibrary", "SapFioriLibrary"))
    out = _overlay.pick_library(session)
    assert out["success"] is False and "library=" in out["error"]
    # ... et l'explicite tranche l'ambiguïté
    assert _overlay.pick_library(session, "SapFioriLibrary") == "SapFioriLibrary"


def test_resolve_session_is_defensive():
    assert _overlay.resolve_session(FakeEngine(boom=True), "s1") is None
    session = FakeSession()
    assert _overlay.resolve_session(FakeEngine({"s1": session}), "s1") is session


# --- collect_state ------------------------------------------------------------

def _collect(**kwargs):
    return asyncio.run(_overlay.collect_state(**kwargs))


def test_collect_state_serves_both_sections_from_the_provider():
    session = FakeSession()
    provider = FakeProvider(page={"success": True, "page_source": "# screen"},
                            app={"connected": True, "modal_open": False})
    out = _collect(execution_engine=FakeEngine({"s1": session}),
                   plugin_manager=FakeManager({"SapEccLibrary": provider}),
                   session_id="s1")
    assert out["success"] is True
    assert out["library"] == "SapEccLibrary"
    assert out["sections"]["page_source"]["page_source"] == "# screen"
    # la sémantique full_source est transmise TELLE QUELLE (défaut False :
    # le mode diff du provider peut s'exercer, le point de la surcouche)
    assert out["sections"]["page_source"]["kwargs"]["full_source"] is False
    assert out["sections"]["application_state"]["modal_open"] is False
    assert "stale_code_warning" not in out


def test_collect_state_unknown_session_is_an_actionable_error():
    out = _collect(execution_engine=FakeEngine(), plugin_manager=FakeManager(),
                   session_id="nope")
    assert out["success"] is False and "introuvable" in out["error"]


def test_collect_state_missing_provider_names_the_fix():
    out = _collect(execution_engine=FakeEngine({"s1": FakeSession()}),
                   plugin_manager=FakeManager({}), session_id="s1")
    assert out["success"] is False and "sapfx_reload" in out["error"]


def test_collect_state_a_failing_section_degrades_best_effort():
    provider = FakeProvider(page_exc=RuntimeError("COM parti"),
                            app={"connected": True})
    out = _collect(execution_engine=FakeEngine({"s1": FakeSession()}),
                   plugin_manager=FakeManager({"SapEccLibrary": provider}),
                   session_id="s1")
    assert out["success"] is True
    assert out["sections"]["page_source"]["success"] is False
    assert "COM parti" in out["sections"]["page_source"]["error"]
    assert out["sections"]["application_state"]["connected"] is True


def test_collect_state_reports_unknown_sections_and_serves_the_known_one():
    provider = FakeProvider(page={"success": True})
    out = _collect(execution_engine=FakeEngine({"s1": FakeSession()}),
                   plugin_manager=FakeManager({"SapEccLibrary": provider}),
                   session_id="s1", sections=["page_source", "dom"])
    assert out["unknown_sections"] == ["dom"]
    assert "page_source" in out["sections"]
    assert "application_state" not in out["sections"]


# --- take_screenshot_payload --------------------------------------------------

def test_screenshot_plain_decodes_the_base64_png():
    def runner(session, keyword, **kwargs):
        assert keyword == "Get Screenshot As Base64"
        return base64.b64encode(_PNG).decode("ascii")
    out = _overlay.take_screenshot_payload(FakeSession(), runner=runner)
    assert out["success"] is True
    assert out["data"] == _PNG
    assert out["format"] == "png"
    assert out["legend"] is None


def test_screenshot_annotated_carries_the_legend_and_the_real_mime():
    def runner(session, keyword, **kwargs):
        assert keyword == "Get Annotated Screenshot"
        assert kwargs.get("allow_structured") is True
        return {"image": base64.b64encode(_PNG).decode("ascii"),
                "mime": "image/jpeg", "legend": {"1": "wnd[0]/tbar[1]/btn[31]"}}
    out = _overlay.take_screenshot_payload(FakeSession(), annotated=True,
                                           runner=runner)
    assert out["format"] == "jpeg"
    assert out["legend"] == {"1": "wnd[0]/tbar[1]/btn[31]"}


def test_screenshot_annotated_passes_include_types_as_keyword_argument():
    seen = {}

    def runner(session, keyword, **kwargs):
        seen["arguments"] = kwargs.get("arguments")
        return {"image": base64.b64encode(_PNG).decode("ascii"),
                "mime": "image/png", "legend": {}}
    _overlay.take_screenshot_payload(FakeSession(), annotated=True,
                                     include_types="GuiShell,GuiCustomControl",
                                     runner=runner)
    assert seen["arguments"] == ["GuiShell,GuiCustomControl"]


def test_screenshot_plain_falls_back_to_the_browser_keyword_on_fiori():
    # Session Fiori : pas de keyword ECC -> repli Browser Take Screenshot
    # (return_as=base64 passé en argument NOMMÉ, converti par le contexte RF).
    calls = []

    def runner(session, keyword, **kwargs):
        calls.append((keyword, kwargs.get("arguments")))
        if keyword == "Get Screenshot As Base64":
            raise RuntimeError("No keyword with name ... found.")
        return base64.b64encode(_PNG).decode("ascii")
    out = _overlay.take_screenshot_payload(FakeSession(), runner=runner)
    assert out["success"] is True and out["data"] == _PNG
    assert calls == [("Get Screenshot As Base64", None),
                     ("Take Screenshot", ["EMBED", "return_as=base64"])]


def test_screenshot_unexpected_shape_and_failure_are_actionable():
    bad = _overlay.take_screenshot_payload(
        FakeSession(), annotated=True, runner=lambda s, k, **kw: "pas un dict")
    assert bad["success"] is False and "forme inattendue" in bad["error"]

    def boom(session, keyword, **kwargs):
        raise RuntimeError("pas de session SAP")
    down = _overlay.take_screenshot_payload(FakeSession(), runner=boom)
    assert down["success"] is False and "pas de session SAP" in down["error"]


# --- reload_plugin_layer ------------------------------------------------------

class FakePluginMeta:
    def __init__(self, name):
        self._name = name

    def get_metadata(self):
        class _Md:
            pass
        md = _Md()
        md.name = self._name
        return md


class FakeManagerModule:
    def __init__(self):
        self.reset_calls = 0
        self.registered = []

    def reset_library_plugin_manager_for_tests(self):
        self.reset_calls += 1

    def get_library_plugin_manager(self):
        return self

    def register_plugin(self, plugin):
        self.registered.append(plugin)

    def iter_entry_point_plugins(self):
        return [FakePluginMeta("SapEccLibrary"), FakePluginMeta("SapFioriLibrary")]


def test_reload_protocol_resets_then_reregisters(monkeypatch):
    fake = FakeManagerModule()
    # paquet inexistant -> aucun reload réel de modules, protocole manager seul
    out = _overlay.reload_plugin_layer(manager_module=fake,
                                       package="sapfx_paquet_fantome")
    assert out["success"] is True
    assert out["reloaded_modules"] == []
    assert fake.reset_calls == 1
    assert out["registered_plugins"] == ["SapEccLibrary", "SapFioriLibrary"]
    assert "stale_code_warning" not in out
    assert "Reload Library" in out["library_layer_note"]


def test_reload_failure_is_an_actionable_error():
    class Broken(FakeManagerModule):
        def reset_library_plugin_manager_for_tests(self):
            raise RuntimeError("hook disparu")
    out = _overlay.reload_plugin_layer(manager_module=Broken(),
                                       package="sapfx_paquet_fantome")
    assert out["success"] is False and "hook disparu" in out["error"]


def test_reload_against_the_real_rfmcp_manager_reregisters_fresh_plugins():
    # Le protocole validé live du 2026-07-23, rejoué comme test vivant : les
    # modules sap_robotmcp sont réellement rechargés et le manager rf-mcp sert
    # des instances FRAÎCHES portant les hints du code sur disque.
    manager_module = pytest.importorskip(
        "robotmcp.plugins.manager", reason="rf-mcp non installé")
    out = _overlay.reload_plugin_layer(manager_module=manager_module)
    assert out["success"] is True
    assert "sap_robotmcp._guidance" in out["reloaded_modules"]
    assert set(out["registered_plugins"]) >= {"SapEccLibrary", "SapFioriLibrary"}
    manager = manager_module.get_library_plugin_manager()
    hints = manager.get_plugin("SapEccLibrary").get_hints().error_hints
    assert any("Get Open Windows" in h for h in hints)


# --- montage sur la vraie instance FastMCP de rf-mcp --------------------------

def test_build_overlay_mounts_the_three_tools_on_the_real_rfmcp_instance():
    robot_server = pytest.importorskip(
        "robotmcp.server", reason="rf-mcp non installé")
    from sap_robotmcp.server import OVERLAY_TOOL_NAMES, build_overlay

    registered = build_overlay(robot_server.mcp, robot_server.execution_engine)
    assert registered == list(OVERLAY_TOOL_NAMES)
    for name in OVERLAY_TOOL_NAMES:
        tool = asyncio.run(robot_server.mcp.get_tool(name))
        assert tool is not None, name


def test_main_refuses_to_start_on_compat_problems(monkeypatch, capsys):
    import sap_robotmcp.server as server_module

    monkeypatch.setattr(server_module, "check_compat",
                        lambda: ["point d'ancrage disparu : x.y"])
    monkeypatch.delenv("SAPFX_MCP_FORCE", raising=False)
    rc = server_module.main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert "refus de démarrer" in err and "SAPFX_MCP_FORCE" in err
