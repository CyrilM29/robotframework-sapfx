"""Moteur record natif : normalisation et mapping des commandes, machine a etats. Doublures dans _recorder_native_fixtures (convention #13)."""

from _recorder_native_fixtures import (  # noqa: F401
    spy,
)



def test_normalize_command_flat_tuple():
    assert spy.normalize_command(("SP", "text", "SE16")) == ["SP", "text", "SE16"]


def test_normalize_command_unwraps_nested_variant():
    # Selon le marshaling COM, le CommandArray peut arriver enveloppé.
    assert spy.normalize_command((("M", "press"),)) == ["M", "press"]


def test_normalize_command_stringifies_and_handles_none():
    assert spy.normalize_command(None) == []
    assert spy.normalize_command(("M", "sendVKey", 8)) == ["M", "sendVKey", "8"]


def test_map_text_set_property_becomes_input_text():
    line = spy.map_change_command(
        "wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", ["SP", "text", "DEVELOPER"])
    assert line == "Input Text    wnd[0]/usr/txtRSYST-BNAME    DEVELOPER"


def test_map_password_is_redacted():
    line = spy.map_change_command(
        "wnd[0]/usr/pwdRSYST-BCODE", "GuiPasswordField", ["SP", "text", "secret!"])
    assert "secret" not in line
    assert line == "Input Password    wnd[0]/usr/pwdRSYST-BCODE    <password>"


def test_map_press_becomes_click_element():
    line = spy.map_change_command("wnd[0]/tbar[1]/btn[8]", "GuiButton", ["M", "press"])
    assert line == "Click Element    wnd[0]/tbar[1]/btn[8]"


def test_map_sendvkey_with_window_index():
    # vkey connu -> commentaire lisible en fin de ligne (cellule # ignorée au replay)
    assert spy.map_change_command("wnd[0]", "GuiMainWindow",
                                  ["M", "sendVKey", "8"]) == "Send Vkey    8    # F8"
    assert spy.map_change_command("wnd[1]", "GuiModalWindow",
                                  ["M", "sendVKey", "0"]) == "Send Vkey    0    1    # Enter"
    # vkey hors table -> pas de commentaire inventé
    assert spy.map_change_command("wnd[0]", "GuiMainWindow",
                                  ["M", "sendVKey", "71"]) == "Send Vkey    71"


def test_map_checkbox_and_radio_selected():
    assert spy.map_change_command("wnd[0]/usr/chkX", "GuiCheckBox",
                                  ["SP", "selected", "true"]) == \
        "Select Checkbox    wnd[0]/usr/chkX"
    assert spy.map_change_command("wnd[0]/usr/chkX", "GuiCheckBox",
                                  ["SP", "selected", "false"]) == \
        "Unselect Checkbox    wnd[0]/usr/chkX"
    assert spy.map_change_command("wnd[0]/usr/radY", "GuiRadioButton",
                                  ["SP", "selected", "True"]) == \
        "Select Radio Button    wnd[0]/usr/radY"


def test_map_tab_and_menu_select_use_click_element():
    # click_element de la base fait .select() sur GuiTab/GuiMenu.
    assert spy.map_change_command("wnd[0]/usr/tabsTS/tabpT1", "GuiTab",
                                  ["M", "select"]) == \
        "Click Element    wnd[0]/usr/tabsTS/tabpT1"


def test_map_toolbar_button_of_grid():
    line = spy.map_change_command("wnd[0]/usr/cntlGRID1/shellcont/shell", "GuiShell",
                                  ["M", "pressToolbarButton", "&MB_EXPORT"])
    assert line == "Click Toolbar Button    wnd[0]/usr/cntlGRID1/shellcont/shell    &MB_EXPORT"


def test_map_noise_properties_are_dropped():
    for prop in ("caretPosition", "currentCellRow", "verticalScrollPosition"):
        assert spy.map_change_command("wnd[0]/usr/x", "GuiTextField",
                                      ["SP", prop, "3"]) is None
    assert spy.map_change_command("wnd[0]/usr/x", "GuiTextField",
                                  ["M", "setFocus"]) is None


def test_map_unknown_method_becomes_comment_with_full_call():
    # NB : doubleClickCurrentCell (l'ancien exemple) est mappé depuis 2026-07
    # en commentaire de grille enrichi (ligne/colonne suivies) : voir
    # test_recorder_exports.py ; doubleClickNode reste un vrai non-mappé.
    line = spy.map_change_command("wnd[0]/shellcont/tree", "GuiShell",
                                  ["M", "doubleClickNode", "N1"])
    assert line.startswith("# non mappé :")
    assert "doubleClickNode" in line


def test_map_combo_key_keeps_exact_key_in_comment():
    line = spy.map_change_command("wnd[0]/usr/cmbX", "GuiComboBox",
                                  ["SP", "key", "004"])
    assert line.startswith("#")
    assert "'004'" in line


def test_okcode_then_enter_becomes_single_run_transaction():
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "wnd[0]/tbar[0]/okcd", "GuiOkCodeField",
                                      ["SP", "text", "/nse16"])
    assert lines == []                                  # en attente de la soumission
    state, lines = spy.process_change(state, "wnd[0]", "GuiMainWindow",
                                      ["M", "sendVKey", "0"])
    assert lines == ["Run Transaction    /nse16"]       # PAS de Send Vkey 0 en plus
    assert spy.flush_native_state(state) == []


def test_okcode_followed_by_button_press_is_kept_as_input_text():
    state = spy.initial_native_state()
    state, _ = spy.process_change(state, "wnd[0]/tbar[0]/okcd", "GuiOkCodeField",
                                  ["SP", "text", "SE38"])
    state, lines = spy.process_change(state, "wnd[0]/tbar[1]/btn[8]", "GuiButton",
                                      ["M", "press"])
    assert lines == ["Input Text    wnd[0]/tbar[0]/okcd    SE38",
                     "Click Element    wnd[0]/tbar[1]/btn[8]"]


def test_pending_okcode_is_flushed_as_run_transaction_on_stop():
    state = spy.initial_native_state()
    state, _ = spy.process_change(state, "wnd[0]/tbar[0]/okcd", "GuiOkCodeField",
                                  ["SP", "text", "SM04"])
    assert spy.flush_native_state(state) == ["Run Transaction    SM04"]


def test_regular_events_flow_through_one_to_one():
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "wnd[0]/usr/txtMAX_SEL", "GuiTextField",
                                      ["SP", "text", "500"])
    assert lines == ["Input Text    wnd[0]/usr/txtMAX_SEL    500"]
