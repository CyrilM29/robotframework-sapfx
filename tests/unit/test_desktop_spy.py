"""Tests unitaires hors SAP du recorder bureau (``tools/recorder/sapgui_recorder.py``).

Le spy ne peut être validé bout-en-bout que contre une session SAP GUI live, mais
sa logique pure (parcours de l'arbre d'objets (`walk`), aplatissement
connexions→sessions (`collect`), lecture défensive (`_safe`), filtre et export
JSON (`main`)) se teste sans serveur ni COM Windows avec des doublures qui
reproduisent le modèle objet SAP GUI Scripting (convention #5 du CLAUDE.md).

`sapgui_recorder.py` vit sous ``tools/`` (hors paquet `src/`) ; on le charge par chemin.
Le `conftest` voisin fournit déjà un `pythoncom.com_error` factice.
"""
import datetime
import importlib.util
import json
import os

import pytest

_SPY_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "sapgui_recorder.py"))


def _load_spy():
    spec = importlib.util.spec_from_file_location("sapgui_recorder", _SPY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spy = _load_spy()


# --- doublures du modèle objet SAP GUI Scripting -----------------------------

class FakeChildren:
    """Collection SAP GUI : expose `Count` et `ElementAt(i)`."""
    def __init__(self, items):
        self._items = items

    @property
    def Count(self):
        return len(self._items)

    def ElementAt(self, index):
        return self._items[index]


class FakeNode:
    """Nœud GUI : `Id`/`Type`/`Text` + `Children` (None pour une feuille)."""
    def __init__(self, node_id, node_type, text="", children=None):
        self.Id = node_id
        self.Type = node_type
        self.Text = text
        self._children = children

    @property
    def Children(self):
        return FakeChildren(self._children) if self._children is not None else None


def _sample_engine():
    """engine → connexion → session → fenêtre → (champ texte, bouton)."""
    btn = FakeNode("wnd[0]/tbar[0]/btn[0]", "GuiButton")
    txt = FakeNode("wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", "")
    win = FakeNode("wnd[0]", "GuiMainWindow", "SAP Easy Access", [txt, btn])
    session = FakeNode("ses[0]", "GuiSession", "", [win])
    connection = FakeNode("con[0]", "GuiConnection", "", [session])
    return FakeNode("app", "GuiApplication", "", [connection]), session


# --- walk / collect ----------------------------------------------------------

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


# --- relative_id : ids collables (préfixe de session retiré) -----------------

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


# --- _safe -------------------------------------------------------------------

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
    monkeypatch.setattr(spy, "win32com", object())
    # raising=False : le stub de test hors-Windows (conftest.py) n'a pas cet
    # attribut du tout (seul le vrai pywin32 l'expose) ; le monkeypatch doit
    # pouvoir le créer plutôt que d'exiger qu'il préexiste.
    monkeypatch.setattr(spy.pythoncom, "GetRunningObjectTable", lambda: BoomROT(), raising=False)
    with pytest.raises(RuntimeError, match="Running Object Table"):
        spy.get_scripting_engine()


# --- main : filtre, export JSON, erreur propre -------------------------------

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
    monkeypatch.setattr(spy, "CAPTURES_DIR", str(tmp_path))   # captures/ redirigé pour le test
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


# --- suggest_keyword : mapping type -> mot-clé SapEccLibrary ------------------

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


# --- find_element / highlight (Visualize) ------------------------------------

class FakeSessionFind:
    """Session exposant findById(id, flag) + Visualize sur les éléments trouvés."""
    def __init__(self, ids):
        self._ids = ids               # {id: FakeVisualizable}

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self._ids:
            return self._ids[element_id]
        if raise_on_missing:
            raise spy.com_error("not found")
        return None


class FakeVisualizable:
    def __init__(self, eid, etype="GuiTextField", text=""):
        self.Id, self.Type, self.Text = eid, etype, text
        self.visualized = []

    def Visualize(self, on_off):
        self.visualized.append(on_off)
        return True


def _engine_with_session(session):
    conn = FakeNode("con[0]", "GuiConnection", "", [session])
    return FakeNode("app", "GuiApplication", "", [conn])


def test_find_element_returns_match_or_none():
    el = FakeVisualizable("wnd[0]/usr/txtA")
    engine = _engine_with_session(FakeSessionFind({"wnd[0]/usr/txtA": el}))
    assert spy.find_element(engine, "wnd[0]/usr/txtA") is el
    assert spy.find_element(engine, "wnd[0]/usr/absent") is None


def test_highlight_visualizes_then_clears(monkeypatch):
    el = FakeVisualizable("wnd[0]/usr/txtA")
    engine = _engine_with_session(FakeSessionFind({"wnd[0]/usr/txtA": el}))
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)   # pas d'attente réelle
    assert spy.highlight(engine, "wnd[0]/usr/txtA") is True
    assert el.visualized == [True, False]                     # encadré puis effacé
    assert spy.highlight(engine, "absent") is False


# --- active_focus / current_focus / capture_loop -----------------------------

class FakeFocusSession:
    """Session dont ActiveWindow.GuiFocus retourne l'élément focalisé courant."""
    def __init__(self, focus):
        self._focus = focus

    @property
    def ActiveWindow(self):
        parent = self

        class _Win:
            GuiFocus = parent._focus
        return _Win()


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
    monkeypatch.setattr(spy, "current_focus", lambda _eng: next(seq, None))
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)
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
    monkeypatch.setattr(spy, "current_focus", lambda _eng: next(seq, None))
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)
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
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)
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
    monkeypatch.setattr(spy, "CAPTURES_DIR", os.path.join("ROOT", "captures"))
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
    monkeypatch.setattr(spy, "CAPTURES_DIR", os.path.join("ROOT", "captures"))
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
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)
    assert spy.main(["--highlight", "wnd[0]/usr/txtA"]) == 0
    assert "Surligné" in capsys.readouterr().out
    assert spy.main(["--highlight", "absent"]) == 1
    assert "introuvable" in capsys.readouterr().err


def test_main_capture_resolves_out_path(monkeypatch):
    calls = {}
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    monkeypatch.setattr(spy, "default_capture_path", lambda: "DEFAULT.txt")
    monkeypatch.setattr(spy, "CAPTURES_DIR", os.path.join("ROOT", "captures"))

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
    monkeypatch.setattr(spy, "CAPTURES_DIR", os.path.join("ROOT", "captures"))
    called = {"loop": False}
    monkeypatch.setattr(spy, "capture_loop", lambda *a, **k: called.__setitem__("loop", True))
    rc = spy.main(["--capture", "--out", os.path.join("..", "..", "evil.txt")])
    assert rc == 1
    assert "sort de" in capsys.readouterr().err
    assert called["loop"] is False    # ne doit jamais lancer la capture sur un chemin rejeté


# --- Survol : géométrie, élément sous le curseur, boucle ----------------------

class FakeGeoNode:
    """Nœud avec géométrie écran (ScreenLeft/Top/Width/Height) + Visualize + Children.

    ``rect=None`` simule un contrôle sans géométrie (menu…) : l'accès aux propriétés
    lève ``AttributeError``, exactement ce que ``element_rect`` doit absorber."""
    def __init__(self, node_id, node_type, rect=None, text="", children=None):
        self.Id, self.Type, self.Text = node_id, node_type, text
        self._children = children
        self.visualized = []
        if rect is not None:
            self.ScreenLeft, self.ScreenTop, self.Width, self.Height = rect

    @property
    def Children(self):
        return FakeChildren(self._children) if self._children is not None else None

    def Visualize(self, on_off):
        self.visualized.append(on_off)
        return True


def _geo_engine():
    """Fenêtre 100×100 contenant un champ (10,10,40,20) et un bouton (60,10,30,20)."""
    field = FakeGeoNode("wnd[0]/usr/txtF", "GuiTextField", (10, 10, 40, 20))
    button = FakeGeoNode("wnd[0]/tbar[0]/btn[0]", "GuiButton", (60, 10, 30, 20))
    win = FakeGeoNode("wnd[0]", "GuiMainWindow", (0, 0, 100, 100), children=[field, button])
    session = FakeGeoNode("ses[0]", "GuiSession", None, children=[win])
    session.ActiveWindow = win   # iter_active_window_elements ne regarde que celle-ci
    conn = FakeGeoNode("con[0]", "GuiConnection", None, children=[session])
    engine = FakeGeoNode("app", "GuiApplication", None, children=[conn])
    return engine, field, button, win


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
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)
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
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)
    lines = []
    count = spy.hover_loop(engine, cursor_fn=lambda: (15, 15),
                           out_path=None, _max_iterations=2, _writer=lines.append)
    assert count == 0                                   # mode inspecteur : rien sur disque
    assert any("Input Text    wnd[0]/usr/txtF" in line for line in lines)   # mais affiché live


# --- Mode record : diff par aller-retour -------------------------------------

class FakeInfo:
    def __init__(self, program="SAPMSSY0", transaction="SE16", screen="0500"):
        self.Program, self.Transaction, self.ScreenNumber = program, transaction, screen


class FakeRecSession:
    """Session minimale pour le record : ActiveWindow, Info, okcode via findById."""
    def __init__(self, window=None, info=None, okcd=""):
        self._window = window
        self.Info = info or FakeInfo()
        self._okcd = FakeNode("wnd[0]/tbar[0]/okcd", "GuiOkCodeField", okcd)

    @property
    def ActiveWindow(self):
        return self._window

    def findById(self, element_id, raise_on_missing=True):
        if element_id == "wnd[0]/tbar[0]/okcd":
            return self._okcd
        if raise_on_missing:
            raise spy.com_error("not found")
        return None


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
    monkeypatch.setattr(spy, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(spy, "okcode_value", lambda _s: "")
    monkeypatch.setattr(spy, "first_session", lambda _e: object())
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)
    out = tmp_path / "rec.robot"
    count = spy.record_loop(object(), str(out), _max_iterations=3, _writer=lambda *_: None)
    assert count == 2                                   # Input Text + Send Vkey
    content = out.read_text(encoding="utf-8")
    assert "*** Test Cases ***" in content
    assert "    Input Text    wnd[0]/usr/txtT    T000" in content
    assert "    Send Vkey    0" in content


# --- Mode record : capture d'écran (--screenshots) ----------------------------

def test_capture_rect_to_bmp_returns_false_without_pywin32(monkeypatch):
    monkeypatch.setattr(spy, "win32gui", None)
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
    monkeypatch.setattr(spy, "win32ui", fake_win32ui)
    monkeypatch.setattr(spy, "win32gui", fake_win32gui)
    monkeypatch.setattr(spy, "win32con", fake_win32con)

    out = str(tmp_path / "shot.bmp")
    assert spy.capture_rect_to_bmp((10, 20, 100, 50), out) is True
    assert calls["saved"] == out
    assert calls["released"] is True
    assert calls["deleted_dc"] == 2   # srcdc + memdc


def test_capture_rect_to_bmp_never_raises_on_gdi_failure(monkeypatch):
    fake_win32gui = type("M", (), {
        "GetDesktopWindow": staticmethod(lambda: (_ for _ in ()).throw(OSError("no display"))),
    })()
    monkeypatch.setattr(spy, "win32gui", fake_win32gui)
    monkeypatch.setattr(spy, "win32ui", object())
    monkeypatch.setattr(spy, "win32con", object())
    assert spy.capture_rect_to_bmp((0, 0, 10, 10), "x.bmp") is False   # jamais levé


def test_record_loop_captures_a_screenshot_on_each_boundary_when_enabled(monkeypatch, tmp_path):
    scans = iter([("sm", {}), ("se16", {})])
    monkeypatch.setattr(spy, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(spy, "okcode_value", lambda _s: "")
    win = FakeGeoNode("wnd[0]", "GuiMainWindow", (0, 0, 100, 100))
    monkeypatch.setattr(spy, "first_session", lambda _e: FakeRecSession(window=win))
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)

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
    monkeypatch.setattr(spy, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(spy, "okcode_value", lambda _s: "")
    win = FakeGeoNode("wnd[0]", "GuiMainWindow", (0, 0, 100, 100))
    monkeypatch.setattr(spy, "first_session", lambda _e: FakeRecSession(window=win))
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)

    out = tmp_path / "rec.robot"
    lines = []
    spy.record_loop(object(), str(out), screenshot_dir=str(tmp_path / "shots"),
                    _max_iterations=2, _writer=lines.append, _screenshot_fn=lambda *a: False)
    assert not any("# screenshot:" in line for line in lines)


def test_record_loop_never_attempts_a_screenshot_without_screenshot_dir(monkeypatch, tmp_path):
    scans = iter([("sm", {}), ("se16", {})])
    monkeypatch.setattr(spy, "scan_active_window", lambda _s: next(scans))
    monkeypatch.setattr(spy, "okcode_value", lambda _s: "")
    monkeypatch.setattr(spy, "first_session", lambda _e: FakeRecSession())
    monkeypatch.setattr(spy.time, "sleep", lambda *_: None)

    called = []
    out = tmp_path / "rec.robot"
    spy.record_loop(object(), str(out), _max_iterations=2, _writer=lambda *_: None,
                    _screenshot_fn=lambda *a: called.append(a) or True)
    assert called == []   # comportement par défaut inchangé : jamais de capture


def test_main_record_with_screenshots_derives_dir_from_out_path(monkeypatch, tmp_path):
    monkeypatch.setattr(spy, "get_scripting_engine", lambda: object())
    monkeypatch.setattr(spy, "CAPTURES_DIR", str(tmp_path))
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
    monkeypatch.setattr(spy, "CAPTURES_DIR", str(tmp_path))
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
    monkeypatch.setattr(spy, "CAPTURES_DIR", os.path.join("ROOT", "captures"))

    def _fake_hover(engine, out_path=None, **_):
        calls["out_path"] = out_path
        return 0
    monkeypatch.setattr(spy, "hover_loop", _fake_hover)
    assert spy.main(["--hover"]) == 0
    assert calls == {"out_path": None}                  # sans --out : inspecteur, pas de fichier
    assert spy.main(["--hover", "--out", "h.txt"]) == 0
    assert calls == {"out_path": os.path.join("ROOT", "captures", "h.txt")}
