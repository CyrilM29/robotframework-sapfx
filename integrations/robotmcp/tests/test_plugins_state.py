"""Plugins rf-mcp : state providers ECC/Fiori (diff, compaction, filtrage, staleness, isolation). Doublures dans _plugins_fixtures."""
import asyncio
import pytest

from _plugins_fixtures import (  # noqa: F401
    ALL_PLUGINS,
    SapEccPlugin,
    SapFioriPlugin,
    _BASE_SIG_LINES,
    _FakeSession,
    _RENAMED_NEW,
    _RENAMED_OLD,
    _patch_rf_context,
    _patch_staleness,
    _state_dispatch,
)



def test_ecc_state_provider_surfaces_the_real_failure_reason(monkeypatch):
    def boom(session, keyword_name, **kwargs):
        raise RuntimeError("Get Screen Signature a échoué côté RF : boom")
    _patch_rf_context(monkeypatch, boom)

    provider = SapEccPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result == {"success": False,
                      "error": "Get Screen Signature a échoué côté RF : boom"}


def test_fiori_state_provider_surfaces_the_real_failure_reason(monkeypatch):
    def boom(session, keyword_name, **kwargs):
        raise RuntimeError("Get Ui5 Page Tree a échoué côté RF : boom")
    _patch_rf_context(monkeypatch, boom)

    provider = SapFioriPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result == {"success": False,
                      "error": "Get Ui5 Page Tree a échoué côté RF : boom"}


def test_ecc_state_provider_succeeds_when_signature_is_returned(monkeypatch):
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "# screen X\n")
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
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: sig)
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
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "# screen X\n* wnd[0]/usr/a\tGuiTextField\tv\n")
    provider = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    asyncio.run(provider.get_page_source(session, filtered=True, filtering_level="aggressive"))
    second = asyncio.run(provider.get_page_source(session, filtered=False))
    assert second["unchanged_since_last_call"] is True


def test_ecc_state_provider_compacts_two_identical_perceptions_in_a_row(monkeypatch):
    # L'agent revérifie l'écran sans avoir agi entre-temps -> 2e appel compacté.
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "# screen X\n")
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
    # lieu entre les deux appels), le second appel doit renvoyer le vrai écran :
    # ici l'écran est ENTIÈREMENT remplacé, donc le diff ne fait rien gagner et
    # l'arbitrage doit servir la vue complète, pas un diff plus long.
    outputs = iter(["# screen X\n", "# screen Y\n"])
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: next(outputs))
    provider = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    first = asyncio.run(provider.get_page_source(session))
    second = asyncio.run(provider.get_page_source(session))
    assert first["page_source"] == "# screen X\n"
    assert second["page_source"] == "# screen Y\n"
    assert second["unchanged_since_last_call"] is False
    assert second["diff_since_last_call"] is False
    assert second["format"] == "ecc-screen-signature"


def test_ecc_state_provider_serves_a_smart_diff_when_the_screen_drifted(monkeypatch):
    before = "\n".join(_BASE_SIG_LINES + [_RENAMED_OLD])
    after = "\n".join(_BASE_SIG_LINES + [_RENAMED_NEW])
    outputs = iter([before, after])
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: next(outputs))
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
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: next(outputs))
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
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: next(outputs))
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


def test_ecc_state_provider_flags_stale_library_code(monkeypatch):
    message = _patch_staleness(monkeypatch)
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "# screen X\n")
    provider = SapEccPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result["stale_code_warning"] == message


def test_fiori_state_provider_flags_stale_library_code(monkeypatch):
    message = _patch_staleness(monkeypatch)
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "<UI5Tree/>")
    provider = SapFioriPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result["stale_code_warning"] == message


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_chaque_sortie_d_etat_porte_l_avertissement_de_code_perime(cls, monkeypatch):
    """L'épilogue est factorisé (`finalize_state`) : plus aucune sortie ne peut
    l'oublier, y compris le retour anticipé « non connecté », qui exigeait
    jusqu'ici sa propre copie dans chaque provider."""
    message = _patch_staleness(monkeypatch)

    def boom(session, keyword_name, **kwargs):
        raise RuntimeError("%s indisponible" % keyword_name)
    _patch_rf_context(monkeypatch, boom)
    state = asyncio.run(cls().get_state_provider()
                        .get_application_state(_FakeSession()))
    assert state["connected"] is False
    assert state["stale_code_warning"] == message


def test_fiori_state_provider_compacts_two_identical_perceptions_in_a_row(monkeypatch):
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "<UI5Tree/>")
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
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: xml)
    provider = SapFioriPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession(), filtered=True,
                                                  filtering_level="standard"))
    assert result["filtered"] is True
    assert 'id="b1"' in result["page_source"]
    assert 'id="l1"' not in result["page_source"]


def test_ecc_state_provider_tracks_isolated_sessions_independently(monkeypatch):
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "# screen X\n")
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


def test_ecc_application_state_reports_the_live_screen_state(monkeypatch):
    _patch_rf_context(monkeypatch, _state_dispatch({
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
    # modal d'erreur est resté affiché : l'état applicatif doit le crier.
    _patch_rf_context(monkeypatch, _state_dispatch({
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
    _patch_rf_context(monkeypatch, fake)
    provider = SapEccPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["connected"] is True
    assert state["transaction"] == "SE16"
    assert "windows" not in state and "modal_open" not in state
    assert set(state["collection_errors"]) == {
        "Get Open Windows", "Get Status Message", "Get Session Telemetry"}


def test_ecc_application_state_degrades_to_disconnected_with_the_reason(monkeypatch):
    def boom(session, keyword_name, **kwargs):
        raise RuntimeError("pas de session SAP")
    _patch_rf_context(monkeypatch, boom)
    provider = SapEccPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["connected"] is False
    assert "pas de session SAP" in state["state_error"]
    assert "transaction" not in state


def test_two_provider_instances_do_not_share_compaction_state(monkeypatch):
    # Régression : un LastSeenCompactor partagé par erreur entre deux instances
    # de provider ferait "fuiter" l'état d'une session vers une autre plugin
    # instance (ex. deux sessions ouvertes par le même process rf-mcp).
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: "# screen X\n")
    provider_a = SapEccPlugin().get_state_provider()
    provider_b = SapEccPlugin().get_state_provider()
    session = _FakeSession()
    asyncio.run(provider_a.get_page_source(session))
    result = asyncio.run(provider_b.get_page_source(session))
    assert result["unchanged_since_last_call"] is False
