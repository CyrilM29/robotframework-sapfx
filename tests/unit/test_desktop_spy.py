"""Recorder bureau : arbre/collect, ids relatifs, main, capture/survol, chemins. Doublures dans _desktop_spy_fixtures (convention #13)."""
import datetime
import json
import os
import pytest

from _desktop_spy_fixtures import (  # noqa: F401
    FakeFocusSession,
    FakeGeoNode,
    FakeNode,
    FakeSessionFind,
    FakeVisualizable,
    _engine_with_session,
    _geo_engine,
    _sample_engine,
    rcap,
    rcom,
    spy,
)



def test_walk_yields_node_and_all_descendants_with_depth():
    _, session = _sample_engine()
    rows = list(spy.walk(session))
    assert rows[0] == (0, "ses[0]", "GuiSession", "")
    ids = {r[1]: r for r in rows}
    assert ids["wnd[0]"][0] == 1                       # profondeur de la fenêtre
    assert ids["wnd[0]/usr/txtRSYST-BNAME"][0] == 2    # champ sous /usr
    assert ids["wnd[0]/tbar[0]/btn[0]"][2] == "GuiButton"


def test_collect_flattens_every_connection_and_session():
    engine, _ = _sample_engine()
    elements = spy.collect(engine)
    assert len(elements) == 4
    assert elements[0] == {"depth": 0, "id": "ses[0]", "type": "GuiSession", "text": ""}
    assert {e["id"] for e in elements} >= {
        "wnd[0]/usr/txtRSYST-BNAME", "wnd[0]/tbar[0]/btn[0]"}


def test_relative_id_strips_session_prefix():
    # SAP GUI expose le .Id ABSOLU ; SapEccLibrary résout relativement à la session.
    assert spy.relative_id("/app/con[0]/ses[0]/wnd[0]/usr/txtI1-LOW") == \
        "wnd[0]/usr/txtI1-LOW"
    assert spy.relative_id("/app/con[2]/ses[3]/wnd[1]/tbar[0]/okcd") == \
        "wnd[1]/tbar[0]/okcd"
    # id déjà relatif ou vide -> inchangé (idempotent)
    assert spy.relative_id("wnd[0]/usr/txtA") == "wnd[0]/usr/txtA"
    assert spy.relative_id("") == ""
    assert spy.relative_id(None) == ""


def test_collect_emits_session_relative_ids():
    # Doublure avec les ids ABSOLUS que renvoie le vrai SAP GUI.
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtI1-LOW", "GuiTextField")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", [txt])
    session = FakeNode("/app/con[0]/ses[0]", "GuiSession", "", [win])
    conn = FakeNode("/app/con[0]", "GuiConnection", "", [session])
    engine = FakeNode("app", "GuiApplication", "", [conn])
    ids = {e["id"] for e in spy.collect(engine)}
    # les descendants de la session sont émis relatifs -> collables tels quels,
    # plus aucune forme absolue (la racine session elle-même n'est pas collable).
    assert "wnd[0]/usr/txtI1-LOW" in ids
    assert "wnd[0]" in ids
    assert "/app/con[0]/ses[0]/wnd[0]/usr/txtI1-LOW" not in ids
    assert "/app/con[0]/ses[0]/wnd[0]" not in ids


def test_walk_is_defensive_when_children_count_raises():
    class BadChildren:
        @property
        def Count(self):
            raise spy.com_error("boom")

    class NodeBadChildren(FakeNode):
        @property
        def Children(self):
            return BadChildren()

    bad = NodeBadChildren("wnd[0]", "GuiMainWindow")
    rows = list(spy.walk(bad))
    assert rows == [(0, "wnd[0]", "GuiMainWindow", "")]  # le nœud, sans planter


def test_safe_swallows_com_error_and_missing_attribute():
    class Bad:
        @property
        def Id(self):
            raise spy.com_error("boom")
    assert spy._safe(Bad(), "Id") == ""        # com_error -> ""
    assert spy._safe(Bad(), "Nope") == ""      # AttributeError -> ""
    assert spy._safe(FakeNode("x", "T"), "Id") == "x"


@pytest.mark.skipif(
    spy.pythoncom is None,
    reason="Chemin COM réel : le recorder pose pythoncom=None quand l'import "
           "global de pywin32 échoue (toute machine sans SAP GUI, dont la CI "
           "Linux), et monkeypatch ne peut rien poser sur None. Le stub COM du "
           "conftest ne suffit pas : c'est l'import de win32api/win32ui qui "
           "manque, pas celui de pythoncom.")
def test_get_scripting_engine_wraps_rot_com_error_as_runtime_error(monkeypatch):
    # Régression : une pythoncom.com_error en cours d'énumération de la Running
    # Object Table (COM non initialisé sur ce thread, RPC transitoire...)
    # remontait en traceback brut au lieu du chemin d'erreur convivial de main().
    class BoomROT:
        def EnumRunning(self):
            raise spy.com_error("RPC failure")
    monkeypatch.setattr(rcom, "win32com", object())
    # raising=False : le stub de test hors-Windows (conftest.py) n'a pas cet
    # attribut du tout (seul le vrai pywin32 l'expose) ; le monkeypatch doit
    # pouvoir le créer plutôt que d'exiger qu'il préexiste.
    monkeypatch.setattr(spy.pythoncom, "GetRunningObjectTable", lambda: BoomROT(), raising=False)
    with pytest.raises(RuntimeError, match="Running Object Table"):
        spy.get_scripting_engine()


def test_main_filter_keeps_matching_rows_only(monkeypatch, capsys):
    engine, _ = _sample_engine()
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: engine)
    rc = spy.main(["--filter", "txt"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "txtRSYST-BNAME" in out
    assert "GuiButton" not in out          # exclu par le filtre


def test_main_json_dump_writes_every_element(monkeypatch, tmp_path):
    engine, _ = _sample_engine()
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: engine)
    out_file = tmp_path / "dump.json"        # chemin absolu -> écrit tel quel
    rc = spy.main(["--json", str(out_file)])
    assert rc == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data) == 4
    assert data[0]["type"] == "GuiSession"
    assert set(data[0]) == {"depth", "id", "type", "text"}


def test_main_json_without_value_uses_default_dump_path(monkeypatch, tmp_path):
    engine, _ = _sample_engine()
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: engine)
    target = tmp_path / "dump_auto.json"
    monkeypatch.setattr(spy, "default_dump_path", lambda: str(target))
    rc = spy.main(["--json"])                 # --json sans valeur -> chemin par défaut
    assert rc == 0
    assert len(json.loads(target.read_text(encoding="utf-8"))) == 4


def test_main_json_relative_path_lands_under_captures_dir(monkeypatch, tmp_path):
    engine, _ = _sample_engine()
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: engine)
    monkeypatch.setattr(rcap, "CAPTURES_DIR", str(tmp_path))   # captures/ redirigé pour le test
    rc = spy.main(["--json", "arbre.json"])   # relatif -> sous captures/
    assert rc == 0
    assert (tmp_path / "arbre.json").exists()


def test_main_reports_missing_engine_cleanly(monkeypatch, capsys):
    def _no_engine():
        raise RuntimeError("No running SAPGUI engine found. Is SAP Logon Pad open?")
    monkeypatch.setattr(spy, "get_scripting_engine", _no_engine)
    rc = spy.main([])
    captured = capsys.readouterr()
    assert rc == 1                          # pas de traceback, sortie 1
    assert "Erreur" in captured.err
    assert "SAPGUI" in captured.err


def test_suggest_keyword_maps_field_types_to_keywords():
    eid = "wnd[0]/usr/txtFOO"
    assert spy.suggest_keyword("GuiTextField", eid, "bar") == "Input Text    %s    bar" % eid
    assert spy.suggest_keyword("GuiCTextField", eid) == "Input Text    %s    <valeur>" % eid
    assert spy.suggest_keyword("GuiPasswordField", eid) == "Input Password    %s    <valeur>" % eid
    assert spy.suggest_keyword("GuiButton", eid) == "Click Element    %s" % eid
    assert spy.suggest_keyword("GuiCheckBox", eid) == "Select Checkbox    %s" % eid
    assert spy.suggest_keyword("GuiRadioButton", eid) == "Select Radio Button    %s" % eid
    assert spy.suggest_keyword("GuiComboBox", eid, "X") == "Select From List By Label    %s    X" % eid


def test_suggest_keyword_special_and_unknown_types():
    assert spy.suggest_keyword("GuiOkCodeField", "wnd[0]/tbar[0]/okcd") == "Run Transaction    <CODE>"
    out = spy.suggest_keyword("GuiShell", "wnd[0]/usr/shell")
    assert out.startswith("#") and "GuiShell" in out and "wnd[0]/usr/shell" in out


def test_format_capture_block_has_info_line_and_keyword():
    block = spy.format_capture_block(
        {"id": "wnd[0]/usr/txtX", "type": "GuiTextField", "text": "hi"})
    lines = block.splitlines()
    assert lines[0] == "[GuiTextField] wnd[0]/usr/txtX = 'hi'"
    assert lines[1].strip() == "Input Text    wnd[0]/usr/txtX    hi"


def test_find_element_returns_match_or_none():
    el = FakeVisualizable("wnd[0]/usr/txtA")
    engine = _engine_with_session(FakeSessionFind({"wnd[0]/usr/txtA": el}))
    assert spy.find_element(engine, "wnd[0]/usr/txtA") is el
    assert spy.find_element(engine, "wnd[0]/usr/absent") is None


def test_highlight_visualizes_then_clears(monkeypatch):
    el = FakeVisualizable("wnd[0]/usr/txtA")
    engine = _engine_with_session(FakeSessionFind({"wnd[0]/usr/txtA": el}))
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)   # pas d'attente réelle
    assert spy.highlight(engine, "wnd[0]/usr/txtA") is True
    assert el.visualized == [True, False]                     # encadré puis effacé
    assert spy.highlight(engine, "absent") is False


def test_active_and_current_focus_read_gui_focus():
    el = FakeVisualizable("wnd[0]/usr/txtA")
    session = FakeFocusSession(el)
    assert spy.active_focus(session) is el
    engine = _engine_with_session(session)
    assert spy.current_focus(engine) is el


def test_active_focus_is_defensive_on_com_error():
    class Boom:
        @property
        def ActiveWindow(self):
            raise spy.com_error("boom")
    assert spy.active_focus(Boom()) is None


def test_capture_loop_records_distinct_focused_elements(monkeypatch, tmp_path):
    # Le focus change a chaque tour : A, A (ignoré, doublon), B.
    elements = [
        FakeVisualizable("wnd[0]/usr/txtA", "GuiTextField"),
        FakeVisualizable("wnd[0]/usr/txtA", "GuiTextField"),   # même id -> dédupliqué
        FakeVisualizable("wnd[0]/tbar[0]/btn[0]", "GuiButton"),
    ]
    seq = iter(elements)
    monkeypatch.setattr(rcap, "current_focus", lambda _eng: next(seq, None))
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)
    out_file = tmp_path / "cap.txt"
    lines = []
    count = spy.capture_loop(object(), str(out_file), do_highlight=True,
                             _max_iterations=3, _writer=lines.append)
    assert count == 2                                  # A et B, pas le doublon
    content = out_file.read_text(encoding="utf-8")
    assert "Input Text    wnd[0]/usr/txtA" in content
    assert "Click Element    wnd[0]/tbar[0]/btn[0]" in content
    assert elements[0].visualized == [True]            # le 1er A surligné
    assert elements[1].visualized == []                # doublon non surligné


def test_capture_loop_filter_keeps_only_matching_elements(monkeypatch, tmp_path):
    elements = [
        FakeVisualizable("wnd[0]/usr/txtA", "GuiTextField"),
        FakeVisualizable("wnd[0]/tbar[0]/btn[0]", "GuiButton"),
    ]
    seq = iter(elements)
    monkeypatch.setattr(rcap, "current_focus", lambda _eng: next(seq, None))
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)
    out_file = tmp_path / "cap.txt"
    count = spy.capture_loop(object(), str(out_file), do_highlight=True,
                             filter_text="txt", _max_iterations=2, _writer=lambda *_: None)
    assert count == 1                                  # seul le champ txt retenu
    content = out_file.read_text(encoding="utf-8")
    assert "wnd[0]/usr/txtA" in content
    assert "GuiButton" not in content                  # bouton filtré
    assert elements[1].visualized == []                # ni surligné


def test_hover_loop_filter_skips_non_matching(monkeypatch, tmp_path):
    engine, field, button, _ = _geo_engine()
    positions = iter([(15, 15), (65, 15)])             # champ (match), bouton (filtré)
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)
    out_file = tmp_path / "hov.txt"
    count = spy.hover_loop(engine, cursor_fn=lambda: next(positions, (65, 15)),
                           out_path=str(out_file), filter_text="txt",
                           _max_iterations=2, _writer=lambda *_: None)
    assert count == 1                                  # seul le champ txt enregistré
    assert field.visualized == [True, False]           # champ encadré puis effacé
    assert button.visualized == []                     # bouton jamais encadré (hors filtre)


def test_default_capture_and_dump_paths_are_timestamped_under_captures_dir():
    fixed = datetime.datetime(2026, 6, 25, 14, 30, 5)
    cap = spy.default_capture_path(now=fixed)
    dump = spy.default_dump_path(now=fixed)
    assert cap.endswith(os.path.join("captures", "capture_20260625_143005.txt"))
    assert dump.endswith(os.path.join("captures", "dump_20260625_143005.json"))
    assert os.path.normpath(spy.CAPTURES_DIR) in os.path.normpath(cap)


def test_resolve_save_path_policy(monkeypatch):
    monkeypatch.setattr(rcap, "CAPTURES_DIR", os.path.join("ROOT", "captures"))
    sentinel = "DEFAULT"
    # None / vide -> fabrique par défaut
    assert spy.resolve_save_path(None, lambda: sentinel) is sentinel
    assert spy.resolve_save_path("", lambda: sentinel) is sentinel
    # relatif -> sous captures/
    assert spy.resolve_save_path("a.json", lambda: sentinel) == \
        os.path.join("ROOT", "captures", "a.json")
    # absolu -> tel quel
    abs_path = os.path.abspath(os.path.join("X", "y.json"))
    assert spy.resolve_save_path(abs_path, lambda: sentinel) == abs_path
    # relatif imbriqué mais qui reste sous captures/ -> autorisé
    assert spy.resolve_save_path(os.path.join("sub", "a.json"), lambda: sentinel) == \
        os.path.join("ROOT", "captures", "sub", "a.json")


def test_resolve_save_path_rejects_traversal_outside_captures_dir(monkeypatch):
    monkeypatch.setattr(rcap, "CAPTURES_DIR", os.path.join("ROOT", "captures"))
    # régression : --out ../../evil.txt sortait silencieusement de captures/
    with pytest.raises(ValueError, match="sort de"):
        spy.resolve_save_path(os.path.join("..", "..", "evil.txt"), lambda: "DEFAULT")


def test_main_rejects_combining_mode_flags(monkeypatch, capsys):
    # Régression : --capture --hover (ou toute autre combinaison de modes) était
    # honoré silencieusement selon un ordre de priorité fixe dans main(), sans
    # jamais avertir l'utilisateur d'une invocation ambiguë.
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    with pytest.raises(SystemExit):
        spy.main(["--capture", "--hover"])
    assert "not allowed with argument" in capsys.readouterr().err


def test_main_highlight_subcommand(monkeypatch, capsys):
    el = FakeVisualizable("wnd[0]/usr/txtA")
    engine = _engine_with_session(FakeSessionFind({"wnd[0]/usr/txtA": el}))
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: engine)
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)
    assert spy.main(["--highlight", "wnd[0]/usr/txtA"]) == 0
    assert "Surligné" in capsys.readouterr().out
    assert spy.main(["--highlight", "absent"]) == 1
    assert "introuvable" in capsys.readouterr().err


def test_main_capture_resolves_out_path(monkeypatch):
    calls = {}
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    monkeypatch.setattr(spy, "default_capture_path", lambda: "DEFAULT.txt")
    monkeypatch.setattr(rcap, "CAPTURES_DIR", os.path.join("ROOT", "captures"))

    def _fake_loop(engine, out_path, do_highlight=True, **_):
        calls["out_path"] = out_path
        calls["do_highlight"] = do_highlight
        return 0
    monkeypatch.setattr(spy, "capture_loop", _fake_loop)
    # sans --out -> chemin par défaut
    assert spy.main(["--capture"]) == 0
    assert calls == {"out_path": "DEFAULT.txt", "do_highlight": True}
    # --out relatif -> sous captures/ ; --no-highlight pris en compte
    assert spy.main(["--capture", "--out", "X.txt", "--no-highlight"]) == 0
    assert calls == {"out_path": os.path.join("ROOT", "captures", "X.txt"),
                     "do_highlight": False}


def test_main_capture_rejects_out_path_traversal(monkeypatch, capsys):
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    monkeypatch.setattr(rcap, "CAPTURES_DIR", os.path.join("ROOT", "captures"))
    called = {"loop": False}
    monkeypatch.setattr(spy, "capture_loop", lambda *a, **k: called.__setitem__("loop", True))
    rc = spy.main(["--capture", "--out", os.path.join("..", "..", "evil.txt")])
    assert rc == 1
    assert "sort de" in capsys.readouterr().err
    assert called["loop"] is False    # ne doit jamais lancer la capture sur un chemin rejeté


def test_element_rect_reads_or_rejects_geometry():
    assert spy.element_rect(FakeGeoNode("x", "T", (5, 6, 7, 8))) == (5, 6, 7, 8)
    assert spy.element_rect(FakeGeoNode("x", "T", (5, 6, 0, 8))) is None   # largeur nulle
    assert spy.element_rect(FakeGeoNode("x", "T", None)) is None          # pas de géométrie


def test_rect_contains_boundaries():
    rect = (10, 10, 40, 20)                 # x∈[10,50[ , y∈[10,30[
    assert spy.rect_contains(rect, 10, 10)  # coin inclus
    assert spy.rect_contains(rect, 49, 29)
    assert not spy.rect_contains(rect, 50, 20)   # bord droit exclu
    assert not spy.rect_contains(rect, 30, 30)   # bord bas exclu


def test_element_at_picks_smallest_containing_control():
    engine, field, button, win = _geo_engine()
    assert spy.element_at(engine, 15, 15) is field    # champ, pas la fenêtre
    assert spy.element_at(engine, 65, 15) is button
    assert spy.element_at(engine, 5, 5) is win         # seule la fenêtre couvre ce point
    assert spy.element_at(engine, 200, 200) is None    # hors de tout


def test_element_at_ignores_residual_window_outside_active_window():
    # Régression : une fenêtre résiduelle (modale non fermée proprement, autre
    # onglet) qui n'est plus la fenêtre active de la session ne doit jamais
    # l'emporter sur le contrôle réellement sous le curseur dans la fenêtre active.
    field = FakeGeoNode("wnd[0]/usr/txtF", "GuiTextField", (10, 10, 40, 20))
    active_win = FakeGeoNode("wnd[0]", "GuiMainWindow", (0, 0, 100, 100), children=[field])
    # Fenêtre résiduelle : un tout petit contrôle qui chevauche le MÊME point que
    # `field` -- si elle était prise en compte, sa plus petite aire l'emporterait.
    ghost = FakeGeoNode("wnd[1]/usr/txtGhost", "GuiTextField", (10, 10, 2, 2))
    residual_win = FakeGeoNode("wnd[1]", "GuiMainWindow", (0, 0, 100, 100), children=[ghost])
    session = FakeGeoNode("ses[0]", "GuiSession", None, children=[active_win, residual_win])
    session.ActiveWindow = active_win   # wnd[1] existe encore mais n'est plus active
    conn = FakeGeoNode("con[0]", "GuiConnection", None, children=[session])
    engine = FakeGeoNode("app", "GuiApplication", None, children=[conn])

    assert spy.element_at(engine, 15, 15) is field   # jamais `ghost`


def test_hover_loop_frames_element_under_cursor_and_reframes(monkeypatch, tmp_path):
    engine, field, button, _ = _geo_engine()
    positions = iter([(15, 15), (15, 15), (65, 15)])   # champ, champ (doublon), bouton
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)
    out_file = tmp_path / "hover.txt"
    lines = []
    count = spy.hover_loop(engine, cursor_fn=lambda: next(positions, (65, 15)),
                           out_path=str(out_file), _max_iterations=3, _writer=lines.append)
    assert count == 2                                   # champ puis bouton, pas le doublon
    assert field.visualized == [True, False]            # encadré puis effacé au changement
    assert button.visualized == [True, False]           # encadré puis effacé en sortie (finally)
    content = out_file.read_text(encoding="utf-8")
    assert "Input Text    wnd[0]/usr/txtF" in content
    assert "Click Element    wnd[0]/tbar[0]/btn[0]" in content


def test_hover_loop_without_out_does_not_write(monkeypatch):
    engine, _, _, _ = _geo_engine()
    monkeypatch.setattr(rcom.time, "sleep", lambda *_: None)
    lines = []
    count = spy.hover_loop(engine, cursor_fn=lambda: (15, 15),
                           out_path=None, _max_iterations=2, _writer=lines.append)
    assert count == 0                                   # mode inspecteur : rien sur disque
    assert any("Input Text    wnd[0]/usr/txtF" in line for line in lines)   # mais affiché live
