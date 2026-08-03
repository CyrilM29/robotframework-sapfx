"""Tests off-SAP des plugins rf-mcp (convention n°5 du CLAUDE.md).

Nécessite rf-mcp installé (``pip install rf-mcp``) pour les vrais contrats ; les
tests sont skippés proprement sinon. Aucune session SAP / Browser réelle requise :
on ne valide que la conformité du plugin au contrat et le contenu de la guidance.
"""
import asyncio

import pytest

robotmcp = pytest.importorskip("robotmcp", reason="rf-mcp non installé")

from sap_robotmcp import SapApiPlugin, SapEccPlugin, SapFioriPlugin  # noqa: E402
import sap_robotmcp.api_plugin as api_plugin  # noqa: E402
import sap_robotmcp.ecc_plugin as ecc_plugin  # noqa: E402
import sap_robotmcp.fiori_plugin as fiori_plugin  # noqa: E402

ALL_PLUGINS = [SapEccPlugin, SapFioriPlugin, SapApiPlugin]


class _FakeSession:
    session_id = "session-1"
    variables = {}


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_plugin_instancie_et_expose_metadata(cls):
    p = cls()
    md = p.get_metadata()
    assert md.name == md.import_path  # libs importables sous leur nom
    assert md.library_type == "external"
    assert "sap" in md.categories
    caps = p.get_capabilities()
    # le canal API n'a pas d'écran : page source honnêtement non supportée
    assert caps.supports_page_source is (cls is not SapApiPlugin)


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_state_provider_a_la_bonne_interface(cls):
    import inspect

    sp = cls().get_state_provider()
    # LibraryStateProvider est un Protocol non runtime_checkable : on valide
    # l'interface structurellement (méthode async get_page_source).
    assert inspect.iscoroutinefunction(sp.get_page_source)
    params = inspect.signature(sp.get_page_source).parameters
    assert "session" in params


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_keyword_map_minuscule_et_route_vers_la_lib(cls):
    p = cls()
    kmap = p.get_keyword_library_map()
    assert kmap, "le mapping de keywords ne doit pas être vide"
    for kw, lib in kmap.items():
        assert kw == kw.lower(), f"clé non normalisée: {kw!r}"
        assert lib == p.get_metadata().name


def test_guidance_fiori_interdit_les_ids_dom():
    hints = SapFioriPlugin().get_hints()
    blob = " ".join(hints.error_hints).lower()
    # phrase précise (pas juste "ui5" et "dom" isolés, présents ailleurs sans rapport)
    assert "jamais des ids dom" in blob


def test_guidance_ecc_impose_le_type_de_message():
    hints = SapEccPlugin().get_hints()
    blob = " ".join(hints.error_hints).lower()
    # assertion locale-indépendante : type de message, pas texte localisé
    assert "type du message de barre d'état (e/s/w/i)" in blob
    assert "jamais le texte localisé" in blob


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_prompt_bundle_present(cls):
    bundle = cls().get_prompt_bundle()
    assert bundle.recommendation and "SAP" in bundle.recommendation


# --- anti-dérive : chaque keyword routé doit EXISTER dans la bibliothèque réelle --

def _routed_keywords_exist_in(cls, plugin_cls, extra_sources=()):
    """Chaque entrée de la carte de routage correspond à une méthode publique de la
    classe de bibliothèque (nom RF -> snake_case). C'est le test qui aurait attrapé
    la coquille historique « Fill Sid » (le vrai keyword est « Fill Sid Input »)."""
    methods = {name for src in (cls, *extra_sources) for name in dir(src)}
    for kw in plugin_cls().get_keyword_library_map():
        assert kw.replace(" ", "_") in methods, f"keyword routé inexistant: {kw!r}"


def test_fiori_map_route_des_keywords_reels():
    SapFioriLibrary = pytest.importorskip(
        "SapFioriLibrary", reason="SapFioriLibrary non importable").SapFioriLibrary
    _routed_keywords_exist_in(SapFioriLibrary, SapFioriPlugin)


def test_ecc_map_route_des_keywords_reels():
    mod = pytest.importorskip(
        "SapEccLibrary", reason="SapEccLibrary non importable (pywin32 requis)")
    _routed_keywords_exist_in(mod.SapEccLibrary, SapEccPlugin)


def test_api_map_route_des_keywords_reels():
    SapApiLibrary = pytest.importorskip(
        "SapApiLibrary", reason="SapApiLibrary non importable").SapApiLibrary
    _routed_keywords_exist_in(SapApiLibrary, SapApiPlugin)


# --- canal API : pas d'écran, un état applicatif réel -------------------------

def test_api_page_source_explains_that_the_channel_has_no_screen():
    provider = SapApiPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result["success"] is False
    assert "n'a pas d'écran" in result["error"]
    assert "List Api Sessions" in result["error"]


def test_api_application_state_serves_the_live_channel_state(monkeypatch):
    monkeypatch.setattr(api_plugin, "run_keyword_in_context",
                        lambda session, keyword_name, **kwargs: {
                            "api_sessions": [
                                {"alias": "default",
                                 "base_url": "http://vhcala4hci:50000",
                                 "sap_client": "001", "authenticated": True,
                                 "csrf_token_cached": False}],
                            "rfc_connections": []})
    provider = SapApiPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["active_library"] == "SapApiLibrary"
    assert state["api_sessions"][0]["alias"] == "default"
    assert state["api_sessions"][0]["authenticated"] is True
    assert state["rfc_connections"] == []


def test_api_application_state_degrades_with_the_reason(monkeypatch):
    def boom(session, keyword_name, **kwargs):
        raise RuntimeError("List Api Sessions indisponible")
    monkeypatch.setattr(api_plugin, "run_keyword_in_context", boom)
    provider = SapApiPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["active_library"] == "SapApiLibrary"
    assert "indisponible" in state["state_error"]


# --- state providers : la cause réelle d'un échec doit remonter à l'agent -----
# (régression : get_page_source renvoyait un "keyword absent ?" générique quel
# que soit le problème réel — cf. _rf_context.run_keyword_in_context)

def test_ecc_state_provider_surfaces_the_real_failure_reason(monkeypatch):
    def boom(session, keyword_name):
        raise RuntimeError("Get Screen Signature a échoué côté RF : boom")
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context", boom)

    provider = SapEccPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result == {"success": False,
                      "error": "Get Screen Signature a échoué côté RF : boom"}


def test_fiori_state_provider_surfaces_the_real_failure_reason(monkeypatch):
    def boom(session, keyword_name):
        raise RuntimeError("Get Ui5 Page Tree a échoué côté RF : boom")
    monkeypatch.setattr(fiori_plugin, "run_keyword_in_context", boom)

    provider = SapFioriPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result == {"success": False,
                      "error": "Get Ui5 Page Tree a échoué côté RF : boom"}


def test_ecc_state_provider_succeeds_when_signature_is_returned(monkeypatch):
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "# screen X\n")
    provider = SapEccPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result["success"] is True
    assert result["page_source"] == "# screen X\n"
    assert result["format"] == "ecc-screen-signature"
    assert result["unchanged_since_last_call"] is False
    assert result["diff_since_last_call"] is False
    assert result["filtered"] is False
    assert "stale_code_warning" not in result   # rien modifié pendant le run


def test_ecc_state_provider_applies_filtering_when_requested(monkeypatch):
    sig = ("# screen X\n"
          "* wnd[0]/usr/txtA\tGuiTextField\tval\n"
          "  wnd[0]/usr/lblEmpty\tGuiLabel\t\n")
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: sig)
    provider = SapEccPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession(), filtered=True,
                                                  filtering_level="aggressive"))
    assert result["filtered"] is True
    assert "txtA" in result["page_source"]
    assert "lblEmpty" not in result["page_source"]
    assert result["page_source_length"] < len(sig)


def test_ecc_state_provider_filtering_does_not_affect_unchanged_detection(monkeypatch):
    # Un appel filtré puis un appel non filtré du MÊME écran doivent quand même
    # se reconnaître comme "unchanged" (comparaison sur le texte complet).
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "# screen X\n* wnd[0]/usr/a\tGuiTextField\tv\n")
    provider = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    asyncio.run(provider.get_page_source(session, filtered=True, filtering_level="aggressive"))
    second = asyncio.run(provider.get_page_source(session, filtered=False))
    assert second["unchanged_since_last_call"] is True


def test_ecc_state_provider_compacts_two_identical_perceptions_in_a_row(monkeypatch):
    # L'agent revérifie l'écran sans avoir agi entre-temps -> 2e appel compacté.
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "# screen X\n")
    provider = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    first = asyncio.run(provider.get_page_source(session))
    second = asyncio.run(provider.get_page_source(session))
    assert first["unchanged_since_last_call"] is False
    assert first["page_source"] == "# screen X\n"
    assert second["unchanged_since_last_call"] is True
    assert second["page_source"] != "# screen X\n"   # marqueur compact, pas le texte


def test_ecc_state_provider_never_compacts_a_real_change(monkeypatch):
    # Toujours interroger l'écran réel : si le contenu a changé (une action a eu
    # lieu entre les deux appels), le second appel doit renvoyer le vrai écran —
    # ici l'écran est ENTIÈREMENT remplacé, donc le diff ne fait rien gagner et
    # l'arbitrage doit servir la vue complète, pas un diff plus long.
    outputs = iter(["# screen X\n", "# screen Y\n"])
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: next(outputs))
    provider = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    first = asyncio.run(provider.get_page_source(session))
    second = asyncio.run(provider.get_page_source(session))
    assert first["page_source"] == "# screen X\n"
    assert second["page_source"] == "# screen Y\n"
    assert second["unchanged_since_last_call"] is False
    assert second["diff_since_last_call"] is False
    assert second["format"] == "ecc-screen-signature"


# --- mode différentiel : un écran déjà vu qui a changé est servi en diff -------

_BASE_SIG_LINES = ["# screen SAPLMEGUI/ME21N/0015"] + [
    "  wnd[0]/usr/lbl%02d\tGuiLabel\ttexte stable" % i for i in range(12)]
_RENAMED_OLD = ("* wnd[0]/usr/subSUB:SAPLMEGUI:0013/ctxtMEPO-EBELN"
                "\tGuiCTextField\t4500000001")
_RENAMED_NEW = ("* wnd[0]/usr/subSUB:SAPLMEGUI:0015/ctxtMEPO-EBELN"
                "\tGuiCTextField\t4500000001")


def test_ecc_state_provider_serves_a_smart_diff_when_the_screen_drifted(monkeypatch):
    before = "\n".join(_BASE_SIG_LINES + [_RENAMED_OLD])
    after = "\n".join(_BASE_SIG_LINES + [_RENAMED_NEW])
    outputs = iter([before, after])
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: next(outputs))
    provider = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    first = asyncio.run(provider.get_page_source(session))
    second = asyncio.run(provider.get_page_source(session))
    assert first["page_source"] == before
    assert second["diff_since_last_call"] is True
    assert second["unchanged_since_last_call"] is False
    assert second["format"] == "ecc-screen-signature-diff"
    # en-tête auto-descriptif + diff intelligent (renommage apparié, pas -/+)
    assert second["page_source"].startswith("(diff since the previous perception")
    assert "= 13 unchanged line(s)" in second["page_source"]
    assert ("~ wnd[0]/usr/subSUB:SAPLMEGUI:0013/ctxtMEPO-EBELN -> "
            "wnd[0]/usr/subSUB:SAPLMEGUI:0015/ctxtMEPO-EBELN"
            ) in second["page_source"]
    assert second["page_source_length"] < len(after)
    # un diff n'est jamais présenté comme une vue filtrée
    assert second["filtered"] is False


def test_ecc_state_provider_full_source_forces_the_complete_screen(monkeypatch):
    before = "\n".join(_BASE_SIG_LINES + [_RENAMED_OLD])
    after = "\n".join(_BASE_SIG_LINES + [_RENAMED_NEW])
    outputs = iter([before, after])
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: next(outputs))
    provider = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    asyncio.run(provider.get_page_source(session))
    second = asyncio.run(provider.get_page_source(session, full_source=True))
    assert second["page_source"] == after
    assert second["diff_since_last_call"] is False
    assert second["format"] == "ecc-screen-signature"


def test_fiori_state_provider_serves_a_diff_on_tree_change(monkeypatch):
    before = ("<UI5Tree>"
              + "".join('<Label id="l%02d"/>' % i for i in range(20))
              + '<Button id="b1" text="Go"/></UI5Tree>')
    after = before.replace('text="Go"', 'text="Stop"')
    outputs = iter([before, after])
    monkeypatch.setattr(fiori_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: next(outputs))
    provider = SapFioriPlugin().get_state_provider()
    session = _FakeSession()
    first = asyncio.run(provider.get_page_source(session))
    second = asyncio.run(provider.get_page_source(session))
    assert first["page_source"] == before
    assert second["diff_since_last_call"] is True
    assert second["format"] == "ui5-control-tree-diff"
    assert "one XML tag per" in second["page_source"]
    assert '- <Button id="b1" text="Go"/>' in second["page_source"]
    assert '+ <Button id="b1" text="Stop"/>' in second["page_source"]
    assert second["page_source_length"] < len(after)


# --- code de bibliothèque modifié après le démarrage du serveur rf-mcp ---------

def test_ecc_state_provider_flags_stale_library_code(monkeypatch):
    monkeypatch.setattr(ecc_plugin, "staleness_warning",
                        lambda: "code modifié — redémarrer rf-mcp")
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "# screen X\n")
    provider = SapEccPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result["stale_code_warning"] == "code modifié — redémarrer rf-mcp"


def test_fiori_state_provider_flags_stale_library_code(monkeypatch):
    monkeypatch.setattr(fiori_plugin, "staleness_warning",
                        lambda: "code modifié — redémarrer rf-mcp")
    monkeypatch.setattr(fiori_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "<UI5Tree/>")
    provider = SapFioriPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result["stale_code_warning"] == "code modifié — redémarrer rf-mcp"


def test_fiori_state_provider_compacts_two_identical_perceptions_in_a_row(monkeypatch):
    monkeypatch.setattr(fiori_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "<UI5Tree/>")
    provider = SapFioriPlugin().get_state_provider()
    session = _FakeSession()
    first = asyncio.run(provider.get_page_source(session))
    second = asyncio.run(provider.get_page_source(session))
    assert first["unchanged_since_last_call"] is False
    assert second["unchanged_since_last_call"] is True
    assert second["page_source"] != "<UI5Tree/>"


def test_fiori_state_provider_applies_filtering_when_requested(monkeypatch):
    xml = ('<UI5Tree><Button id="b1" text="Go"/>'
          '<Label id="l1"/></UI5Tree>')
    monkeypatch.setattr(fiori_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: xml)
    provider = SapFioriPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession(), filtered=True,
                                                  filtering_level="standard"))
    assert result["filtered"] is True
    assert 'id="b1"' in result["page_source"]
    assert 'id="l1"' not in result["page_source"]


def test_ecc_state_provider_tracks_isolated_sessions_independently(monkeypatch):
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "# screen X\n")
    provider = SapEccPlugin().get_state_provider()

    class _SessionA(_FakeSession):
        session_id = "session-a"

    class _SessionB(_FakeSession):
        session_id = "session-b"

    first = asyncio.run(provider.get_page_source(_SessionA()))
    assert first["success"] is True
    assert first["cross_session_sharing_detected"] is False
    second = asyncio.run(provider.get_page_source(_SessionB()))
    assert second["success"] is True
    assert second["cross_session_sharing_detected"] is False
    assert second["unchanged_since_last_call"] is False
    third = asyncio.run(provider.get_page_source(_SessionA()))
    assert third["unchanged_since_last_call"] is True
    assert third["session_isolation"] == "suite"


# --- état applicatif structuré : déduit d'une lecture réelle, jamais optimiste --

def _state_dispatch(values):
    """Doublure de run_keyword_in_context par keyword (Exception -> levée)."""
    def fake(session, keyword_name, **kwargs):
        result = values[keyword_name]
        if isinstance(result, Exception):
            raise result
        return result
    return fake


def test_ecc_application_state_reports_the_live_screen_state(monkeypatch):
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context", _state_dispatch({
        "Get Current Transaction": "SE16",
        "Get Open Windows": [
            {"id": "wnd[0]", "type": "GuiMainWindow",
             "title": "Data Browser", "modal": False},
        ],
        "Get Status Message": ("S", "42 entries found"),
        "Get Session Telemetry": {"response_time": 12, "roundtrips": 3},
    }))
    provider = SapEccPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["connected"] is True
    assert state["transaction"] == "SE16"
    assert state["modal_open"] is False
    assert "modal_titles" not in state
    assert state["status_message"] == {"type": "S", "text": "42 entries found"}
    assert state["telemetry"] == {"response_time": 12, "roundtrips": 3}
    assert "collection_errors" not in state


def test_ecc_application_state_flags_a_leftover_modal(monkeypatch):
    # Le piège SESSION_MANAGER vu live : Run Transaction "réussit" alors qu'un
    # modal d'erreur est resté affiché — l'état applicatif doit le crier.
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context", _state_dispatch({
        "Get Current Transaction": "SESSION_MANAGER",
        "Get Open Windows": [
            {"id": "wnd[0]", "type": "GuiMainWindow",
             "title": "SAP Easy Access", "modal": False},
            {"id": "wnd[1]", "type": "GuiModalWindow",
             "title": "Cannot start transaction SESSION_MANAGER", "modal": True},
        ],
        "Get Status Message": ("", ""),
        "Get Session Telemetry": {},
    }))
    provider = SapEccPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["modal_open"] is True
    assert state["modal_titles"] == ["Cannot start transaction SESSION_MANAGER"]


def test_ecc_application_state_sections_degrade_best_effort(monkeypatch):
    # Une section d'état qui échoue ne fait pas tomber l'état : elle est
    # consignée dans collection_errors, le reste est servi.
    def fake(session, keyword_name, **kwargs):
        if keyword_name == "Get Current Transaction":
            return "SE16"
        raise RuntimeError("%s indisponible" % keyword_name)
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context", fake)
    provider = SapEccPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["connected"] is True
    assert state["transaction"] == "SE16"
    assert "windows" not in state and "modal_open" not in state
    assert set(state["collection_errors"]) == {
        "Get Open Windows", "Get Status Message", "Get Session Telemetry"}


def test_ecc_application_state_degrades_to_disconnected_with_the_reason(monkeypatch):
    def boom(session, keyword_name):
        raise RuntimeError("pas de session SAP")
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context", boom)
    provider = SapEccPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["connected"] is False
    assert "pas de session SAP" in state["state_error"]
    assert "transaction" not in state


def test_two_provider_instances_do_not_share_compaction_state(monkeypatch):
    # Régression : un LastSeenCompactor partagé par erreur entre deux instances
    # de provider ferait "fuiter" l'état d'une session vers une autre plugin
    # instance (ex. deux sessions ouvertes par le même process rf-mcp).
    monkeypatch.setattr(ecc_plugin, "run_keyword_in_context",
                        lambda session, keyword_name: "# screen X\n")
    provider_a = SapEccPlugin().get_state_provider()
    provider_b = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    asyncio.run(provider_a.get_page_source(session))
    result = asyncio.run(provider_b.get_page_source(session))
    assert result["unchanged_since_last_call"] is False
