"""Tests hors SAP des mixins diagnostic (préflight scripting, TestToolMode,
télémétrie) et healing (réparation de localisateurs, closest matches), plus les
primitives pures de ``sapfx_common.healing``. Fake COM — convention #5."""
import pytest

from sapfx_common.healing import (
    closest_gui_ids,
    format_suggestions,
    gui_id_similarity,
    split_segments,
)
from SapEccLibrary.SapEccLibrary import SapEccLibrary


# --- doublures COM ------------------------------------------------------------

class FakeChildren:
    def __init__(self, items):
        self._items = items

    @property
    def Count(self):
        return len(self._items)

    def ElementAt(self, index):
        return self._items[index]


class FakeNode:
    def __init__(self, node_id, node_type, text="", children=None):
        self.Id = node_id
        self.Type = node_type
        self.Text = text
        self._children = children

    @property
    def Children(self):
        return FakeChildren(self._children) if self._children is not None else None


class FakeInfo:
    def __init__(self, **props):
        for key, value in props.items():
            setattr(self, key, value)


class FakeSession:
    def __init__(self, window=None, info=None, present_ids=()):
        self.ActiveWindow = window
        self.Info = info
        self._present = set(present_ids)

    def findById(self, element_id, raise_on_error=True):
        if element_id in self._present:
            return FakeNode(element_id, "GuiTextField")
        return None


def _lib(session=None, sapapp=None, connection=None):
    lib = SapEccLibrary(screenshots_on_error=False)
    if session is not None:
        lib.session = session
    if sapapp is not None:
        lib.sapapp = sapapp
    if connection is not None:
        lib.connection = connection
    return lib


# --- sapfx_common.healing : scoring pur ----------------------------------------

def test_split_segments_drops_empties():
    assert split_segments("wnd[0]/usr/txtA") == ["wnd[0]", "usr", "txtA"]
    assert split_segments("") == []


def test_identical_id_scores_one():
    fid = "wnd[0]/usr/ctxtMEPO_TOPLINE-BSART"
    assert gui_id_similarity(fid, fid) == pytest.approx(1.0)


def test_renumbered_subscreen_scores_high_unrelated_scores_low():
    old = "wnd[0]/usr/subSUB0:SAPLMEGUI:0013/ssubSUB2:SAPLMEGUI:0020/ctxtMEPO_TOPLINE-BSART"
    renum = "wnd[0]/usr/subSUB0:SAPLMEGUI:0015/ssubSUB2:SAPLMEGUI:0021/ctxtMEPO_TOPLINE-BSART"
    other = "wnd[0]/tbar[1]/btn[8]"
    assert gui_id_similarity(old, renum) > 0.8           # même champ, sous-écrans renumérotés
    assert gui_id_similarity(old, other) < 0.4
    assert gui_id_similarity(old, renum) > gui_id_similarity(old, other)


def test_type_prefix_is_stripped_for_terminal_comparison():
    # même champ exposé en txt vs ctxt : le nom terminal doit dominer
    assert gui_id_similarity("wnd[0]/usr/txtVBAK-VBELN",
                             "wnd[0]/usr/ctxtVBAK-VBELN") > 0.9


def test_matching_type_beats_mismatching_type():
    target = "wnd[0]/usr/ctxtX-FIELD"
    same = gui_id_similarity(target, "wnd[0]/usr/ctxtY-FIELD",
                             target_type="GuiCTextField", candidate_type="GuiCTextField")
    diff = gui_id_similarity(target, "wnd[0]/usr/ctxtY-FIELD",
                             target_type="GuiCTextField", candidate_type="GuiButton")
    assert same > diff


def test_closest_gui_ids_orders_and_limits_deterministically():
    candidates = [("wnd[0]/usr/txtAAA", "GuiTextField"),
                  ("wnd[0]/usr/txtAAB", "GuiTextField"),
                  ("wnd[0]/tbar[0]/btn[0]", "GuiButton")]
    top = closest_gui_ids("wnd[0]/usr/txtAAA", candidates, limit=2)
    assert [sc.candidate for sc in top] == ["wnd[0]/usr/txtAAA", "wnd[0]/usr/txtAAB"]
    assert top[0].score == pytest.approx(1.0)


def test_format_suggestions_filters_noise():
    scored = closest_gui_ids("wnd[0]/usr/txtA",
                             [("wnd[0]/usr/txtA", "GuiTextField")], limit=5)
    text = format_suggestions(scored)
    assert "wnd[0]/usr/txtA" in text and "100%" in text
    assert format_suggestions([]) == ""


# --- préflight scripting --------------------------------------------------------

def test_get_scripting_status_reads_all_surfaces():
    session = FakeSession(info=FakeInfo(
        ScriptingModeReadOnly=False, ScriptingModeRecordingDisabled=True,
        UI_GUIDELINE="3", SystemName="A4H", Client="001", User="DEVELOPER"))
    sapapp = FakeInfo(MajorVersion=8, MinorVersion=0, Patchlevel=6)
    connection = FakeInfo(DisabledByServer=False)
    status = _lib(session, sapapp, connection).get_scripting_status()
    assert status == {
        "gui_version": "8.0 PL6", "disabled_by_server": False, "read_only": False,
        "recording_disabled": True, "ui_guideline": "3",
        "system": "A4H", "client": "001", "user": "DEVELOPER",
    }


def test_get_scripting_status_defensive_when_properties_missing():
    status = _lib(FakeSession(info=FakeInfo())).get_scripting_status()
    assert status["gui_version"] is None
    assert status["disabled_by_server"] is None
    assert status["read_only"] is None


def test_preflight_passes_on_healthy_system():
    session = FakeSession(info=FakeInfo(
        ScriptingModeReadOnly=False, ScriptingModeRecordingDisabled=False))
    _lib(session, connection=FakeInfo(DisabledByServer=False)) \
        .scripting_should_be_fully_enabled()          # ne lève pas


def test_preflight_names_the_rz11_parameter_on_failure():
    session = FakeSession(info=FakeInfo(
        ScriptingModeReadOnly=True, ScriptingModeRecordingDisabled=False,
        SystemName="A4H"))
    with pytest.raises(AssertionError) as err:
        _lib(session, connection=FakeInfo(DisabledByServer=True)) \
            .scripting_should_be_fully_enabled()
    message = str(err.value)
    assert "sapgui/user_scripting" in message
    assert "sapgui/user_scripting_set_readonly" in message
    assert "A4H" in message


def test_preflight_can_tolerate_recording_disabled():
    session = FakeSession(info=FakeInfo(
        ScriptingModeReadOnly=False, ScriptingModeRecordingDisabled=True))
    lib = _lib(session, connection=FakeInfo(DisabledByServer=False))
    with pytest.raises(AssertionError, match="disable_recording"):
        lib.scripting_should_be_fully_enabled()
    lib.scripting_should_be_fully_enabled(allow_recording_disabled=True)   # toléré


# --- TestToolMode / télémétrie --------------------------------------------------

def test_enable_test_tool_mode_sets_and_clears():
    session = FakeSession()
    lib = _lib(session)
    lib.enable_test_tool_mode()
    assert session.TestToolMode == 1
    lib.enable_test_tool_mode(enabled=False)
    assert session.TestToolMode == 0
    lib.enable_test_tool_mode(enabled="False")        # chaîne Robot -> désactivé
    assert session.TestToolMode == 0


def test_get_session_telemetry_reads_info_counters():
    session = FakeSession(info=FakeInfo(
        ResponseTime=120, InterpretationTime=15, RoundTrips=3, Flushes=42,
        IsLowSpeedConnection=False))
    telemetry = _lib(session).get_session_telemetry()
    assert telemetry == {"response_time": 120, "interpretation_time": 15,
                         "roundtrips": 3, "flushes": 42,
                         "low_speed_connection": False}


# --- healing ECC ---------------------------------------------------------------

def _window_with(*fields):
    return FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", list(fields))


def test_resolve_with_healing_returns_id_untouched_when_present():
    session = FakeSession(present_ids=["wnd[0]/usr/txtA"])
    assert _lib(session).resolve_element_with_healing("wnd[0]/usr/txtA") \
        == "wnd[0]/usr/txtA"


def test_resolve_with_healing_heals_renumbered_subscreen():
    present = ("/app/con[0]/ses[0]/wnd[0]/usr/subSUB0:SAPLMEGUI:0015/"
               "ctxtMEPO_TOPLINE-BSART")
    session = FakeSession(window=_window_with(FakeNode(present, "GuiCTextField")))
    healed = _lib(session).resolve_element_with_healing(
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0013/ctxtMEPO_TOPLINE-BSART")
    assert healed == ("wnd[0]/usr/subSUB0:SAPLMEGUI:0015/ctxtMEPO_TOPLINE-BSART")


def test_resolve_with_healing_fails_below_threshold_with_suggestions():
    session = FakeSession(window=_window_with(
        FakeNode("/app/con[0]/ses[0]/wnd[0]/tbar[0]/btn[0]", "GuiButton")))
    with pytest.raises(AssertionError) as err:
        _lib(session).resolve_element_with_healing("wnd[0]/usr/ctxtZZ-UNKNOWN")
    assert "Candidats les plus proches" in str(err.value)
    assert "btn[0]" in str(err.value)


def test_get_closest_element_ids_returns_pairs():
    session = FakeSession(window=_window_with(
        FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField"),
        FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtB", "GuiTextField")))
    pairs = _lib(session).get_closest_element_ids("wnd[0]/usr/txtA", limit=1)
    assert pairs == [["wnd[0]/usr/txtA", 1.0]]


def test_wait_until_element_present_error_includes_closest_ids():
    session = FakeSession(window=_window_with(
        FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtRSYST-BNAME", "GuiTextField")))
    lib = _lib(session)
    lib.default_timeout = 0.05
    with pytest.raises(AssertionError) as err:
        lib.wait_until_element_present("wnd[0]/usr/txtRSYST-BNAMX", interval="0.01s")
    message = str(err.value)
    assert "Closest ids on the current screen" in message
    assert "wnd[0]/usr/txtRSYST-BNAME" in message
