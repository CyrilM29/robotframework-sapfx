"""Exports du recorder : mappings natifs, transpile VBS et replay. Doublures dans _recorder_exports_fixtures."""
import codecs

from _recorder_exports_fixtures import (  # noqa: F401
    _FakeReplayLib,
    _VBS_ACCENTED,
    _VBS_SAMPLE,
    spy,
)



def test_vkey_comment_uses_session_resolver_beyond_static_table():
    assert spy._vkey_comment(8) == "    # F8"        # table statique prioritaire
    calls = []

    def resolver(code):
        calls.append(code)
        return "  Shift+F5\n"

    previous = spy.set_vkey_resolver(resolver)
    try:
        assert spy._vkey_comment(17) == "    # Shift+F5"   # blancs normalisés
        assert spy._vkey_comment(8) == "    # F8" and calls == [17]
    finally:
        spy.set_vkey_resolver(previous)
    assert spy._vkey_comment(17) == ""               # résolveur débranché


def test_vkey_resolver_failure_never_crashes():
    def boom(code):
        raise RuntimeError("COM en échec")

    previous = spy.set_vkey_resolver(boom)
    try:
        assert spy._vkey_comment(17) == ""
    finally:
        spy.set_vkey_resolver(previous)


def test_hotkey_poller_fires_on_rising_edge_only():
    pressed = {"keys": set()}

    def key_state(code):
        return 0x8000 if code in pressed["keys"] else 0

    poll = spy.make_hotkey_poller(key_state)
    assert poll() is None
    pressed["keys"] = {0x11, 0x12, 0x41}             # Ctrl+Alt+A enfoncé
    assert poll() == "value"
    assert poll() is None                            # tenu : ne re-déclenche pas
    pressed["keys"] = set()
    assert poll() is None
    pressed["keys"] = {0x11, 0x12, 0x56}             # Ctrl+Alt+V
    assert poll() == "visual"


def test_assertion_step_prefers_value_but_never_for_passwords():
    assert spy.assertion_step_for_element("wnd[0]/usr/txtA", "GuiTextField", "T000") \
        == "Element Value Should Be    wnd[0]/usr/txtA    T000"
    assert spy.assertion_step_for_element("wnd[0]/usr/pwdA", "GuiPasswordField", "secret") \
        == "Element Should Be Present    wnd[0]/usr/pwdA"
    assert spy.assertion_step_for_element("wnd[0]/usr/btnB", "GuiButton", "") \
        == "Element Should Be Present    wnd[0]/usr/btnB"
    assert spy.assertion_step_for_element("", "GuiTextField", "x") is None


def test_visual_assertion_step_sanitizes_baseline_name():
    assert spy.visual_assertion_step("record 2026!", 3) \
        == "Screen Should Match Baseline    record_2026_etape_03"


def test_offset_suggestion_only_for_opaque_types_with_cursor_inside():
    rect = (100, 200, 200, 100)
    line = spy.offset_suggestion("GuiShell", "wnd[0]/usr/shell", rect, 150, 250)
    assert line.startswith("Click Element At Offset    wnd[0]/usr/shell    0.25    0.50")
    # type scriptable -> pas de suggestion ; curseur hors rect -> pas de suggestion
    assert spy.offset_suggestion("GuiButton", "wnd[0]/tbar[0]/btn[0]", rect, 150, 250) is None
    assert spy.offset_suggestion("GuiShell", "wnd[0]/usr/shell", rect, 10, 10) is None
    assert spy.offset_suggestion("GuiShell", "wnd[0]/usr/shell", None, 150, 250) is None


def test_map_change_selected_rows_single_row_maps_to_keyword():
    line = spy.map_change_command("wnd[0]/usr/cntlGRID1/shellcont/shell", "GuiShell",
                                  ["SP", "selectedRows", "3"])
    assert line == "Select Table Row    wnd[0]/usr/cntlGRID1/shellcont/shell    3"
    ranged = spy.map_change_command("g", "GuiShell", ["SP", "selectedRows", "1-4"])
    assert ranged.startswith("# grille g : sélection de lignes '1-4'")


def test_map_change_tree_nodes_map_to_select_node():
    assert spy.map_change_command("tree", "GuiShell", ["M", "selectNode", "N42"]) \
        == "Select Node    tree    N42"
    assert spy.map_change_command("tree", "GuiShell", ["M", "expandNode", "N42"]) \
        == "Select Node    tree    N42    True"


def test_process_change_pairs_context_menu_button_and_item():
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("M", "pressToolbarContextButton", "&MB_EXPORT"))
    assert lines == []                               # bouton retenu, rien d'émis
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("M", "selectContextMenuItem", "&PC"))
    assert lines == ["Select Context Menu Item    grid    &MB_EXPORT    &PC"]
    assert state.get("ctx_button") is None           # consommé


def test_process_change_tracks_current_cell_for_grid_clicks():
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("SP", "currentCellRow", "5"))
    assert lines == []
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("SP", "currentCellColumn", "CARRID"))
    assert lines == []
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("M", "doubleClickCurrentCell"))
    assert lines == ["# grille grid : double-clic cellule ligne 5, colonne CARRID"
                     ", lecture : Get Cell Value    grid    5    CARRID"]


def test_process_change_okcode_flow_still_merges_into_run_transaction():
    # non-régression : le flux OK-code + Entrée -> Run Transaction est inchangé
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "wnd[0]/tbar[0]/okcd", "GuiOkCodeField",
                                      ("SP", "text", "SE16"))
    assert lines == []
    state, lines = spy.process_change(state, "wnd[0]", "GuiMainWindow",
                                      ("M", "sendVKey", "0"))
    assert lines == ["Run Transaction    SE16"]


def test_resource_first_semantic_lines_become_healing_keywords():
    steps = ["Fill Field By Label    Table Name    T000"
             "    # id: wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
             "Click Button By Label    Execute    # id: wnd[0]/tbar[1]/btn[8]"]
    resource, suite = spy.steps_to_resource_first(steps)
    assert ("Resolve Element With Healing    ${LOC_DATABROWSE_TABLENAME}"
            "    label=Table Name") in resource
    assert "Input Text    ${cible}    ${valeur}" in resource
    assert "Resolve Element With Healing    ${LOC_8}    label=Execute" in resource
    assert "Click Element    ${cible}" in resource
    assert "Saisir DATABROWSE_TABLENAME    T000" in suite
    assert "Cliquer 8" in suite
    assert "wnd[" not in suite                       # convention n°1 intacte


def test_transpile_vbs_merges_okcode_and_maps_actions():
    steps = spy.transpile_vbs(_VBS_SAMPLE)
    joined = "\n".join(steps)
    assert "Run Transaction    /nse16" in joined     # fusion OK-code + Entrée
    assert "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000" in joined
    assert "Click Element    wnd[0]/tbar[1]/btn[8]" in joined
    assert "Select Checkbox    wnd[0]/usr/chkFLAG" in joined
    # commande sans keyword -> commentaire, jamais perdue en silence
    assert any(s.startswith("# non mappé") and "maximize" in s for s in steps)


def test_transpile_vbs_keeps_quoted_commas_together():
    steps = spy.transpile_vbs('session.findById("g").selectContextMenuItem "A,B"')
    assert any("A,B" in s for s in steps)


def test_transpile_vbs_flushes_trailing_okcode():
    steps = spy.transpile_vbs('session.findById("wnd[0]/tbar[0]/okcd").text = "/nex"')
    assert steps == ["Run Transaction    /nex"]


def test_default_replay_lib_disables_screenshot_handler(monkeypatch):
    # Hors contexte Robot, le handler screenshot d'échec remplacerait l'erreur
    # réelle du step par « Cannot access execution context » (constaté live
    # 2026-07-21, l'échec du replay devenait indiagnosticable) : la fabrique
    # CLI du replay doit désarmer screenshots_on_error.
    import sys
    import types
    calls = {}

    class StubLib:
        def __init__(self, screenshots_on_error=True):
            calls["screenshots_on_error"] = screenshots_on_error

        def attach_to_open_session(self):
            calls["attached"] = True

    stub = types.ModuleType("SapEccLibrary")
    stub.SapEccLibrary = StubLib
    monkeypatch.setitem(sys.modules, "SapEccLibrary", stub)
    lib = spy._default_replay_lib()
    assert isinstance(lib, StubLib)
    assert calls == {"screenshots_on_error": False, "attached": True}


def test_decode_vbs_source_utf8_sans_bom():
    assert spy.decode_vbs_source(_VBS_ACCENTED.encode("utf-8")) == _VBS_ACCENTED


def test_decode_vbs_source_utf8_avec_bom():
    data = codecs.BOM_UTF8 + _VBS_ACCENTED.encode("utf-8")
    assert spy.decode_vbs_source(data) == _VBS_ACCENTED


def test_decode_vbs_source_utf16_le_avec_bom():
    # encode("utf-16") écrit le BOM LE : la forme « Unicode » du Bloc-notes
    # et d'``Out-File`` PowerShell 5.1.
    assert spy.decode_vbs_source(_VBS_ACCENTED.encode("utf-16")) == _VBS_ACCENTED


def test_decode_vbs_source_utf16_be_avec_bom():
    data = codecs.BOM_UTF16_BE + _VBS_ACCENTED.encode("utf-16-be")
    assert spy.decode_vbs_source(data) == _VBS_ACCENTED


def test_decode_vbs_source_utf16_le_sans_bom():
    # Le cas perfide : les octets NUL de l'UTF-16 sont du UTF-8 VALIDE,
    # l'ancien décodage UTF-8 forcé « réussissait » et la transpilation
    # sortait 0 step, sans la moindre exception.
    data = _VBS_ACCENTED.encode("utf-16-le")
    assert spy.decode_vbs_source(data) == _VBS_ACCENTED


def test_decode_vbs_source_ansi_cp1252():
    # 'é' en cp1252 = 0xE9 seul, séquence UTF-8 invalide -> repli ANSI.
    # (encodage de repli passé explicitement : déterministe sur toute CI.)
    data = _VBS_ACCENTED.encode("cp1252")
    assert spy.decode_vbs_source(data, ansi_encoding="cp1252") == _VBS_ACCENTED


def test_decode_vbs_source_transpile_utf16_bout_en_bout():
    # Un enregistrement complet en UTF-16 traverse décodage + transpilation.
    steps = spy.transpile_vbs(spy.decode_vbs_source(_VBS_SAMPLE.encode("utf-16")))
    assert "Run Transaction    /nse16" in "\n".join(steps)


def test_replay_runs_methods_in_order_and_skips_comments_and_unknown():
    lib = _FakeReplayLib()
    steps = ["Run Transaction    SE16",
             "# screenshot: x.png",
             "Input Text    wnd[0]/usr/txtA    T000",
             "Send Vkey    0    # Enter",
             "Mon Keyword Site    x"]                # keyword hors bibliothèque
    executed, skipped, failed, _msg = spy.replay_recorded_steps(
        steps, lib, writer=lambda *_a: None)
    assert failed is None
    assert executed == 3 and skipped == 1
    assert lib.calls == [("run_transaction", "SE16"),
                         ("input_text", "wnd[0]/usr/txtA", "T000"),
                         ("send_vkey", "0")]


def test_replay_stops_on_first_failure_with_index_and_message():
    lib = _FakeReplayLib()
    steps = ["Element Value Should Be    wnd[0]/usr/txtA    BOOM",
             "Run Transaction    SE16"]
    executed, _skipped, failed, msg = spy.replay_recorded_steps(
        steps, lib, writer=lambda *_a: None)
    assert failed == 0 and "valeur inattendue" in msg
    assert executed == 0
    assert ("run_transaction", "SE16") not in lib.calls


def test_run_replay_reads_file_attaches_and_reports(tmp_path):
    out = tmp_path / "r.robot"
    out.write_text(spy.build_record_header(str(out), suite=True)
                   + "    Run Transaction    SE16\n", encoding="utf-8")
    lib = _FakeReplayLib()
    messages = []
    rc = spy.run_replay(str(out), _lib_factory=lambda: lib, _writer=messages.append)
    assert rc == 0
    assert ("run_transaction", "SE16") in lib.calls
    assert any("Replay OK" in m for m in messages)


def test_run_replay_fails_cleanly_on_missing_file_or_empty(tmp_path):
    messages = []
    assert spy.run_replay(str(tmp_path / "absent.robot"),
                          _lib_factory=lambda: _FakeReplayLib(),
                          _writer=messages.append) == 1
    empty = tmp_path / "vide.robot"
    empty.write_text(spy.build_record_header(str(empty)), encoding="utf-8")
    assert spy.run_replay(str(empty), _lib_factory=lambda: _FakeReplayLib(),
                          _writer=messages.append) == 1
