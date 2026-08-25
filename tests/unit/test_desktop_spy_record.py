"""Recorder bureau, mode record par sondage : diff d'ecran, process_poll, record_loop, screenshots. Doublures dans _desktop_spy_fixtures."""
import os

from _desktop_spy_fixtures import (  # noqa: F401
    FakeGeoNode,
    FakeInfo,
    FakeNode,
    FakeRecSession,
    rcap,
    rcom,
    rpoll,
    spy,
)



def test_field_step_maps_each_editable_type():
    assert spy._field_step("wnd[0]/usr/txtA", "GuiTextField", "X") == "Input Text    wnd[0]/usr/txtA    X"
    # vidé -> ${EMPTY}, un step rejouable (le diff a déjà écarté les nouveaux
    # champs vides ; même contrat que le moteur natif depuis la passe 0.6.0)
    assert spy._field_step("wnd[0]/usr/txtA", "GuiTextField", "") == "Input Text    wnd[0]/usr/txtA    ${EMPTY}"
    assert spy._field_step("wnd[0]/usr/pwd", "GuiPasswordField", None) == "Input Password    wnd[0]/usr/pwd    <password>"
    assert spy._field_step("c", "GuiCheckBox", True) == "Select Checkbox    c"
    assert spy._field_step("c", "GuiCheckBox", False) == "Unselect Checkbox    c"
    assert spy._field_step("r", "GuiRadioButton", True) == "Select Radio Button    r"
    assert spy._field_step("r", "GuiRadioButton", False) is None    # induit par le frère coché
    assert spy._field_step("cb", "GuiComboBox", "Val") == "Select From List By Label    cb    Val"


def test_diff_to_steps_emits_changed_fields_in_order():
    prev = {"wnd[0]/usr/a": ("GuiTextField", "old"), "wnd[0]/usr/b": ("GuiTextField", "")}
    cur = {"wnd[0]/usr/a": ("GuiTextField", "new"),     # modifié
           "wnd[0]/usr/b": ("GuiTextField", "B"),       # vide -> rempli
           "wnd[0]/usr/c": ("GuiTextField", "")}        # nouveau mais vide -> ignoré
    assert spy.diff_to_steps(prev, cur) == [
        "Input Text    wnd[0]/usr/a    new", "Input Text    wnd[0]/usr/b    B"]


def test_diff_to_steps_skips_unchanged():
    same = {"x": ("GuiTextField", "v")}
    assert spy.diff_to_steps(same, dict(same)) == []


def test_diff_to_steps_records_uncheck_and_clear():
    # Décocher une case et vider un champ sont des actions délibérées : elles
    # s'enregistrent (parité avec le moteur natif). Le radio passé à False
    # (frère nouvellement coché) ne doit rien émettre, lui.
    prev = {"c": ("GuiCheckBox", True), "t": ("GuiTextField", "X"),
            "r": ("GuiRadioButton", True)}
    cur = {"c": ("GuiCheckBox", False), "t": ("GuiTextField", ""),
           "r": ("GuiRadioButton", False)}
    assert spy.diff_to_steps(prev, cur) == [
        "Unselect Checkbox    c", "Input Text    t    ${EMPTY}"]


def test_submit_step_uses_okcode_or_enter():
    assert spy.submit_step("/nSE16") == "Run Transaction    /nSE16"
    assert spy.submit_step("") == "Send Vkey    0"


def test_process_poll_first_call_starts_silently():
    state, steps = spy.process_poll({}, "sigA", {}, "")
    assert steps == [] and state["started"] is True


def test_process_poll_emits_diff_then_submit_on_signature_change():
    # le champ est présent dès l'entrée sur l'écran (vide), sa valeur change ensuite.
    base = {"wnd[0]/usr/txtT": ("GuiTextField", "")}
    s0, _ = spy.process_poll({}, "screenA", base, "")
    s1, e1 = spy.process_poll(s0, "screenA",
                              {"wnd[0]/usr/txtT": ("GuiTextField", "T000")}, "")
    assert e1 == []                                   # même signature : on accumule
    s2, e2 = spy.process_poll(s1, "screenB", {}, "")
    assert e2 == ["Input Text    wnd[0]/usr/txtT    T000", "Send Vkey    0"]


def test_process_poll_boundary_when_signature_changes_with_field_unchanged():
    # SE16 : la valeur du champ est identique, mais la grille ALV apparaît -> la
    # signature structurelle change -> frontière détectée (cas réel validé en live).
    sel = {"wnd[0]/usr/ctxtTAB": ("GuiCTextField", "T000")}
    s0, _ = spy.process_poll({}, "se16-sel",
                             {"wnd[0]/usr/ctxtTAB": ("GuiCTextField", "")}, "")
    s1, e1 = spy.process_poll(s0, "se16-sel", sel, "")
    assert e1 == []
    s2, e2 = spy.process_poll(s1, "se16-result", sel, "")   # grille ALV ajoutée
    assert e2 == ["Input Text    wnd[0]/usr/ctxtTAB    T000", "Send Vkey    0"]


def test_process_poll_uses_typed_okcode_for_run_transaction():
    s0, _ = spy.process_poll({}, "easyaccess", {}, "")
    s1, e1 = spy.process_poll(s0, "easyaccess", {}, "/nSE16")
    assert e1 == []
    s2, e2 = spy.process_poll(s1, "se16", {}, "")
    assert e2 == ["Run Transaction    /nSE16"]


def test_screen_signature_changes_when_a_control_appears():
    field = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/ctxtTAB", "GuiCTextField", "T000")
    win1 = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", [field])
    sig1 = spy.screen_signature(FakeRecSession(window=win1))
    grid = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/shell", "GuiShell")
    win2 = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", [field, grid])
    sig2 = spy.screen_signature(FakeRecSession(window=win2))
    assert sig1 != sig2                                # l'apparition de la grille -> frontière


def test_snapshot_fields_collects_editable_relative_ids_in_order():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "hello")
    btn = FakeNode("/app/con[0]/ses[0]/wnd[0]/tbar[0]/btn[0]", "GuiButton")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", [txt, btn])
    snap = spy.snapshot_fields(FakeRecSession(window=win))
    assert snap == {"wnd[0]/usr/txtA": ("GuiTextField", "hello")}   # bouton exclu, id relatif


def test_screen_key_and_okcode_value_read_session():
    session = FakeRecSession(info=FakeInfo("PROG", "SE16", "0500"), okcd="/nSM50")
    assert spy.screen_key(session) == ("PROG", "SE16", "0500")
    assert spy.okcode_value(session) == "/nSM50"


def test_scan_active_window_matches_separate_signature_and_snapshot_calls():
    # scan_active_window fusionne les deux parcours COM de screen_signature et
    # snapshot_fields en un seul ; le résultat doit rester identique.
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "hello")
    btn = FakeNode("/app/con[0]/ses[0]/wnd[0]/tbar[0]/btn[0]", "GuiButton")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", [txt, btn])
    session = FakeRecSession(window=win)

    expected_sig = spy.screen_signature(session)
    expected_fields = spy.snapshot_fields(session)
    sig, fields = spy.scan_active_window(session)

    assert sig == expected_sig
    assert fields == expected_fields
    assert fields == {"wnd[0]/usr/txtA": ("GuiTextField", "hello")}


def test_scan_active_window_defensive_when_no_active_window():
    session = FakeRecSession(window=None)
    sig, fields = spy.scan_active_window(session)
    assert sig == spy.screen_signature(session)
    assert fields == {} == spy.snapshot_fields(session)


def test_record_loop_writes_replayable_test_body(monkeypatch, tmp_path):
    scans = iter([
        ("sm", {"wnd[0]/usr/txtT": ("GuiTextField", "")}),         # baseline (champ vide)
        ("sm", {"wnd[0]/usr/txtT": ("GuiTextField", "T000")}),     # saisie
        ("se16", {}),                                              # écran suivant
    ])
    monkeypatch.setattr(rpoll, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(rpoll, "okcode_value", lambda _s: "")
    monkeypatch.setattr(rpoll, "first_session", lambda _e: object())
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)
    out = tmp_path / "rec.robot"
    count = spy.record_loop(object(), str(out), _max_iterations=3, _writer=lambda *_: None)
    assert count == 2                                   # Input Text + Send Vkey
    content = out.read_text(encoding="utf-8")
    assert "*** Test Cases ***" in content
    assert "    Input Text    wnd[0]/usr/txtT    T000" in content
    assert "    Send Vkey    0" in content


def test_capture_rect_to_bmp_returns_false_without_pywin32(monkeypatch):
    monkeypatch.setattr(rcom, "win32gui", None)
    assert spy.capture_rect_to_bmp((0, 0, 10, 10), "x.bmp") is False


def test_capture_rect_to_bmp_saves_via_gdi_and_releases_resources(monkeypatch, tmp_path):
    calls = {"saved": None, "released": False, "deleted_dc": 0}

    class FakeBitmap:
        def CreateCompatibleBitmap(self, srcdc, w, h):
            pass

        def SaveBitmapFile(self, memdc, path):
            calls["saved"] = path

        def GetHandle(self):
            return 123

    class FakeDC:
        def CreateCompatibleDC(self):
            return FakeMemDC()

        def DeleteDC(self):
            calls["deleted_dc"] += 1

    class FakeMemDC:
        def SelectObject(self, bmp):
            pass

        def BitBlt(self, dst_pos, size, srcdc, src_pos, rop):
            pass

        def DeleteDC(self):
            calls["deleted_dc"] += 1

    fake_win32ui = type("M", (), {
        "CreateDCFromHandle": staticmethod(lambda hdc: FakeDC()),
        "CreateBitmap": staticmethod(lambda: FakeBitmap()),
    })()
    fake_win32gui = type("M", (), {
        "GetDesktopWindow": staticmethod(lambda: 1),
        "GetWindowDC": staticmethod(lambda hwin: 2),
        "DeleteObject": staticmethod(lambda h: None),
        "ReleaseDC": staticmethod(lambda hwin, hdc: calls.__setitem__("released", True)),
    })()
    fake_win32con = type("M", (), {"SRCCOPY": 0xCC0020})()
    monkeypatch.setattr(rcom, "win32ui", fake_win32ui)
    monkeypatch.setattr(rcom, "win32gui", fake_win32gui)
    monkeypatch.setattr(rcom, "win32con", fake_win32con)

    out = str(tmp_path / "shot.bmp")
    assert spy.capture_rect_to_bmp((10, 20, 100, 50), out) is True
    assert calls["saved"] == out
    assert calls["released"] is True
    assert calls["deleted_dc"] == 2   # srcdc + memdc


def test_capture_rect_to_bmp_never_raises_on_gdi_failure(monkeypatch):
    fake_win32gui = type("M", (), {
        "GetDesktopWindow": staticmethod(lambda: (_ for _ in ()).throw(OSError("no display"))),
    })()
    monkeypatch.setattr(rcom, "win32gui", fake_win32gui)
    monkeypatch.setattr(rcom, "win32ui", object())
    monkeypatch.setattr(rcom, "win32con", object())
    assert spy.capture_rect_to_bmp((0, 0, 10, 10), "x.bmp") is False   # jamais levé


def test_record_loop_captures_a_screenshot_on_each_boundary_when_enabled(monkeypatch, tmp_path):
    scans = iter([("sm", {}), ("se16", {})])
    monkeypatch.setattr(rpoll, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(rpoll, "okcode_value", lambda _s: "")
    win = FakeGeoNode("wnd[0]", "GuiMainWindow", (0, 0, 100, 100))
    monkeypatch.setattr(rpoll, "first_session", lambda _e: FakeRecSession(window=win))
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)

    shots = []

    def fake_shot(rect, out_path):
        shots.append((rect, out_path))
        return True

    out = tmp_path / "rec.robot"
    shots_dir = tmp_path / "rec_shots"
    lines = []
    spy.record_loop(object(), str(out), screenshot_dir=str(shots_dir), _max_iterations=2,
                    _writer=lines.append, _screenshot_fn=fake_shot)

    assert shots == [((0, 0, 100, 100), str(shots_dir / "step_001.bmp"))]
    assert any("# screenshot:" in line for line in lines)
    assert "# screenshot:" in out.read_text(encoding="utf-8")


def test_record_loop_skips_screenshot_when_capture_fails(monkeypatch, tmp_path):
    scans = iter([("sm", {}), ("se16", {})])
    monkeypatch.setattr(rpoll, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(rpoll, "okcode_value", lambda _s: "")
    win = FakeGeoNode("wnd[0]", "GuiMainWindow", (0, 0, 100, 100))
    monkeypatch.setattr(rpoll, "first_session", lambda _e: FakeRecSession(window=win))
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)

    out = tmp_path / "rec.robot"
    lines = []
    spy.record_loop(object(), str(out), screenshot_dir=str(tmp_path / "shots"),
                    _max_iterations=2, _writer=lines.append, _screenshot_fn=lambda *a: False)
    assert not any("# screenshot:" in line for line in lines)


def test_record_loop_never_attempts_a_screenshot_without_screenshot_dir(monkeypatch, tmp_path):
    scans = iter([("sm", {}), ("se16", {})])
    monkeypatch.setattr(rpoll, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(rpoll, "okcode_value", lambda _s: "")
    monkeypatch.setattr(rpoll, "first_session", lambda _e: FakeRecSession())
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)

    called = []
    out = tmp_path / "rec.robot"
    spy.record_loop(object(), str(out), _max_iterations=2, _writer=lambda *_: None,
                    _screenshot_fn=lambda *a: called.append(a) or True)
    assert called == []   # comportement par défaut inchangé : jamais de capture


def test_main_record_with_screenshots_derives_dir_from_out_path(monkeypatch, tmp_path):
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    monkeypatch.setattr(rcap, "CAPTURES_DIR", str(tmp_path))
    calls = {}

    def fake_record_loop(engine, out_path, screenshot_dir=None, **kw):
        calls["out_path"] = out_path
        calls["screenshot_dir"] = screenshot_dir
        return 0
    monkeypatch.setattr(spy, "record_loop", fake_record_loop)

    assert spy.main(["--record", "--out", "scenario.robot", "--screenshots"]) == 0
    assert calls["out_path"] == os.path.join(str(tmp_path), "scenario.robot")
    assert calls["screenshot_dir"] == os.path.join(str(tmp_path), "scenario_shots")


def test_main_record_without_screenshots_flag_passes_no_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    monkeypatch.setattr(rcap, "CAPTURES_DIR", str(tmp_path))
    calls = {}

    def fake_record_loop(engine, out_path, screenshot_dir=None, **kw):
        calls["screenshot_dir"] = screenshot_dir
        return 0
    monkeypatch.setattr(spy, "record_loop", fake_record_loop)

    assert spy.main(["--record", "--out", "scenario.robot"]) == 0
    assert calls["screenshot_dir"] is None


def test_main_hover_resolves_out_path(monkeypatch):
    calls = {}
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    monkeypatch.setattr(rcap, "CAPTURES_DIR", os.path.join("ROOT", "captures"))

    def _fake_hover(engine, out_path=None, **_):
        calls["out_path"] = out_path
        return 0
    monkeypatch.setattr(spy, "hover_loop", _fake_hover)
    assert spy.main(["--hover"]) == 0
    assert calls == {"out_path": None}                  # sans --out : inspecteur, pas de fichier
    assert spy.main(["--hover", "--out", "h.txt"]) == 0
    assert calls == {"out_path": os.path.join("ROOT", "captures", "h.txt")}
