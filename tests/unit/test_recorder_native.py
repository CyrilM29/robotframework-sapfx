"""Tests hors SAP du mode record/capture NATIF du recorder desktop.

Le mode natif s'appuie sur les événements COM de l'API SAP GUI Scripting
(``Session.Record`` + ``Change``, hit-test ``Hit``, ``FocusChanged``). Toute la
traduction événement -> keyword est pure (`normalize_command`,
`map_change_command`, `process_change`, `flush_native_state`) et la glue COM
est injectable (`_dispatch_with_events`/`_pump`) : testable avec des doublures,
convention #5 du CLAUDE.md.
"""
import importlib.util
import os

_SPY_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "sapgui_recorder.py"))


def _load_spy():
    spec = importlib.util.spec_from_file_location("sapgui_recorder_native", _SPY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spy = _load_spy()


# --- normalize_command --------------------------------------------------------

def test_normalize_command_flat_tuple():
    assert spy.normalize_command(("SP", "text", "SE16")) == ["SP", "text", "SE16"]


def test_normalize_command_unwraps_nested_variant():
    # Selon le marshaling COM, le CommandArray peut arriver enveloppé.
    assert spy.normalize_command((("M", "press"),)) == ["M", "press"]


def test_normalize_command_stringifies_and_handles_none():
    assert spy.normalize_command(None) == []
    assert spy.normalize_command(("M", "sendVKey", 8)) == ["M", "sendVKey", "8"]


# --- map_change_command -------------------------------------------------------

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


# --- process_change : la subtilité OK-code ------------------------------------

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


# --- glue COM : record_loop_native avec doublures ------------------------------
#
# La liaison réelle (`advise_session_events` : connexion manuelle au point de
# connexion ISapSessionEvents, hack _query_interface_ de la démo pywin32
# connect.py, DispatchWithEvents étant inutilisable sur la typelib sapfewse,
# issue pywin32 #2433) est validée LIVE contre l'A4H ; ici on injecte `_advise`
# pour tester la boucle (émission, teardown, replis) hors SAP.

class FakeInfo:
    def __init__(self, recording_disabled=False):
        self.ScriptingModeRecordingDisabled = recording_disabled


class FakeSession:
    def __init__(self, recording_disabled=False):
        self.Id = "/app/con[0]/ses[0]"
        self.Type = "GuiSession"
        self.Text = ""
        self.Children = None
        self.Info = FakeInfo(recording_disabled)
        self.Record = False


class FakeComponent:
    def __init__(self, eid, etype, text=""):
        self.Id = "/app/con[0]/ses[0]/" + eid
        self.Type = etype
        self.Text = text


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _engine_with(session):
    class _Children:
        def __init__(self, items):
            self._items = items

        @property
        def Count(self):
            return len(self._items)

        def ElementAt(self, index):
            return self._items[index]

    class _Node:
        def __init__(self, children):
            self.Children = _Children(children)

    return _Node([_Node([session])])


def _fake_advise(handlers, connection):
    """Fabrique un `_advise` factice : capture les handlers passés par la boucle
    (mêmes noms que `advise_session_events`) et retourne `connection`."""
    def advise(session, on_change=None, on_hit=None, on_focus_changed=None):
        handlers.update(change=on_change, hit=on_hit, focus=on_focus_changed)
        return connection
    return advise


def test_record_loop_native_writes_steps_from_change_events(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "native.robot")
    handlers = {}
    connection = FakeConnection()

    events = iter([
        lambda: handlers["change"](FakeComponent("wnd[0]/tbar[0]/okcd", "GuiOkCodeField"),
                                   (("SP", "text", "SE16"),)),   # variant imbriqué (comme live)
        lambda: handlers["change"](FakeComponent("wnd[0]", "GuiMainWindow"),
                                   (("M", "sendVKey", 0),)),
        lambda: handlers["change"](FakeComponent("wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
                                                 "GuiCTextField"),
                                   (("SP", "text", "SFLIGHT"),)),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    written = []
    count = spy.record_loop_native(
        engine, out, _writer=written.append, _max_iterations=5,
        _advise=_fake_advise(handlers, connection), _pump=fake_pump,
        _sleep=lambda s: None)

    assert count == 2
    assert session.Record is False                      # désarmé au teardown
    assert connection.closed is True                    # désabonné au teardown
    content = open(out, encoding="utf-8").read()
    assert "*** Test Cases ***" in content
    assert "Run Transaction    SE16" in content
    assert "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT" in content
    assert "Send Vkey    0" not in content              # absorbé par Run Transaction


def test_record_loop_native_returns_none_when_server_disables_recording(tmp_path):
    session = FakeSession(recording_disabled=True)
    out = str(tmp_path / "never.robot")
    result = spy.record_loop_native(
        _engine_with(session), out, _writer=lambda *_: None,
        _advise=lambda *a, **k: (_ for _ in ()).throw(AssertionError),
        _pump=lambda: None)
    assert result is None                               # -> repli polling côté CLI
    assert not os.path.exists(out)                      # aucun fichier fantôme


def test_record_loop_native_returns_none_when_event_binding_fails(tmp_path):
    session = FakeSession()
    out = str(tmp_path / "unbound.robot")

    def failing_advise(session, **handlers):
        raise OSError("connection point refused")

    result = spy.record_loop_native(
        _engine_with(session), out, _writer=lambda *_: None,
        _advise=failing_advise, _pump=lambda: None)
    assert result is None


def test_capture_loop_native_records_hits_and_focus_dedup(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "capture.txt")
    handlers = {}
    connection = FakeConnection()

    field = FakeComponent("wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", "DEVELOPER")
    events = iter([
        lambda: handlers["hit"](field),
        lambda: handlers["focus"](field),               # même id -> dédupliqué
        lambda: handlers["hit"](FakeComponent("wnd[0]/tbar[0]/btn[3]", "GuiButton")),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    count = spy.capture_loop_native(
        engine, out, _writer=lambda *_: None, _max_iterations=5,
        _advise=_fake_advise(handlers, connection), _pump=fake_pump,
        _sleep=lambda s: None)

    assert count == 2
    assert session.elementVisualizationMode is False    # hit-test désarmé au teardown
    assert connection.closed is True
    content = open(out, encoding="utf-8").read()
    assert "wnd[0]/usr/txtRSYST-BNAME" in content
    assert content.count("[GuiTextField]") == 1         # un seul BLOC malgré Hit+Focus
    assert "wnd[0]/tbar[0]/btn[3]" in content


def test_capture_loop_native_honours_filter(tmp_path):
    session = FakeSession()
    out = str(tmp_path / "filtered.txt")
    handlers = {}

    events = iter([
        lambda: handlers["hit"](FakeComponent("wnd[0]/usr/txtA", "GuiTextField")),
        lambda: handlers["hit"](FakeComponent("wnd[0]/tbar[0]/btn[3]", "GuiButton")),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    count = spy.capture_loop_native(
        engine=_engine_with(session), out_path=out, filter_text="txt",
        _writer=lambda *_: None, _max_iterations=4,
        _advise=_fake_advise(handlers, FakeConnection()), _pump=fake_pump,
        _sleep=lambda s: None)
    assert count == 1
    content = open(out, encoding="utf-8").read()
    assert "btn[3]" not in content


# --- mode sémantique (--semantic) : keywords humains, id en commentaire --------

from sapfx_common.object_tree import ScreenElement  # noqa: E402


def _sem(eid, etype, text="", tooltip="", changeable=False, box=None):
    left, top, width, height = box if box else (None, None, None, None)
    return ScreenElement(id=eid, type=etype, text=text, tooltip=tooltip,
                         changeable=changeable, left=left, top=top,
                         width=width, height=height)


_SE16_ELEMENTS = [
    _sem("wnd[0]/usr/lblTable", "GuiLabel", "Table Name", box=(10, 20, 90, 20)),
    _sem("wnd[0]/usr/ctxtDATABROWSE-TABLENAME", "GuiCTextField", "SFLIGHT",
         changeable=True, box=(110, 20, 120, 20)),
    _sem("wnd[0]/tbar[1]/btn[8]", "GuiButton", "", tooltip="Execute (F8)",
         box=(10, 0, 30, 18)),
    _sem("wnd[0]/usr/chkONLY", "GuiCheckBox", "", changeable=True,
         box=(110, 50, 20, 20)),
    _sem("wnd[0]/usr/lblOnly", "GuiLabel", "Selected entries only",
         box=(10, 50, 90, 20)),
]


def test_semanticize_input_text_devient_fill_field_by_label():
    line = "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT"
    assert spy.semanticize_step(line, _SE16_ELEMENTS) == (
        "Fill Field By Label    Table Name    SFLIGHT"
        "    # id: wnd[0]/usr/ctxtDATABROWSE-TABLENAME")


def test_semanticize_click_element_devient_click_button_by_label():
    line = "Click Element    wnd[0]/tbar[1]/btn[8]"
    assert spy.semanticize_step(line, _SE16_ELEMENTS) == (
        "Click Button By Label    Execute (F8)    # id: wnd[0]/tbar[1]/btn[8]")


def test_semanticize_checkbox_est_annotee_pas_reecrite():
    line = "Select Checkbox    wnd[0]/usr/chkONLY"
    assert spy.semanticize_step(line, _SE16_ELEMENTS) == (
        "Select Checkbox    wnd[0]/usr/chkONLY    # libellé : Selected entries only")


def test_semanticize_garde_la_ligne_sans_libelle_fiable_ou_sans_elements():
    inconnu = "Input Text    wnd[0]/usr/txtINCONNU    X"
    assert spy.semanticize_step(inconnu, _SE16_ELEMENTS) == inconnu
    assert spy.semanticize_step(inconnu, []) == inconnu
    okcd = "Input Text    wnd[0]/tbar[0]/okcd    SE16"
    assert spy.semanticize_step(okcd, _SE16_ELEMENTS) == okcd
    run = "Run Transaction    SE16"
    assert spy.semanticize_step(run, _SE16_ELEMENTS) == run


def test_record_loop_native_semantic_emet_des_keywords_humains(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "semantic.robot")
    handlers = {}

    events = iter([
        lambda: handlers["change"](FakeComponent("wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
                                                 "GuiCTextField"),
                                   (("SP", "text", "SFLIGHT"),)),
        lambda: handlers["change"](FakeComponent("wnd[0]/tbar[1]/btn[8]", "GuiButton"),
                                   (("M", "press"),)),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    count = spy.record_loop_native(
        engine, out, semantic=True, _writer=lambda *_: None, _max_iterations=4,
        _advise=_fake_advise(handlers, FakeConnection()), _pump=fake_pump,
        _sleep=lambda s: None, _elements_fn=lambda session: _SE16_ELEMENTS)

    assert count == 2
    content = open(out, encoding="utf-8").read()
    assert "Fill Field By Label    Table Name    SFLIGHT" in content
    assert "# id: wnd[0]/usr/ctxtDATABROWSE-TABLENAME" in content
    assert "Click Button By Label    Execute (F8)" in content


def test_record_loop_native_sans_semantic_reste_en_ids(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "technique.robot")
    handlers = {}
    events = iter([
        lambda: handlers["change"](FakeComponent("wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
                                                 "GuiCTextField"),
                                   (("SP", "text", "SFLIGHT"),)),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    spy.record_loop_native(
        engine, out, _writer=lambda *_: None, _max_iterations=3,
        _advise=_fake_advise(handlers, FakeConnection()), _pump=fake_pump,
        _sleep=lambda s: None,
        _elements_fn=lambda session: (_ for _ in ()).throw(AssertionError(
            "screen_elements ne doit pas être appelé sans --semantic")))
    content = open(out, encoding="utf-8").read()
    assert "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT" in content


# --- hardcopy_screenshot : capture API avec extension par magic bytes ----------

class _ShotWindow:
    def __init__(self, raw):
        self._raw = raw
        self.Id = "/app/con[0]/ses[0]/wnd[0]"

    def HardCopyToMemory(self, image_type):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


class _ShotSession:
    def __init__(self, window):
        self.ActiveWindow = window


def test_hardcopy_screenshot_ecrit_le_png_et_choisit_l_extension(tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    base = str(tmp_path / "step_001")
    path = spy.hardcopy_screenshot(_ShotSession(_ShotWindow(png)), base)
    assert path == base + ".png"
    assert open(path, "rb").read() == png


def test_hardcopy_screenshot_extension_suit_les_magic_bytes_pas_la_demande(tmp_path):
    bmp = b"BM" + b"bitmap-payload"                      # l'API a rendu du BMP
    base = str(tmp_path / "step_002")
    path = spy.hardcopy_screenshot(_ShotSession(_ShotWindow(tuple(bmp))), base)
    assert path == base + ".bmp"
    assert open(path, "rb").read() == bmp


def test_hardcopy_screenshot_none_si_api_absente_ou_buffer_vide(tmp_path):
    base = str(tmp_path / "step_003")
    sans_api = _ShotSession(_ShotWindow(AttributeError("HardCopyToMemory")))
    assert spy.hardcopy_screenshot(sans_api, base) is None
    vide = _ShotSession(_ShotWindow(b""))
    assert spy.hardcopy_screenshot(vide, base) is None
