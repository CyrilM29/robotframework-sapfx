"""Tests hors SAP de `Pick Calendar Date`, de la détection du calendrier par
`Pick F4 Value`, et des cases/radios par libellé (mixin ``SemanticKeywords``)."""
import pytest

from SapEccLibrary import SapEccLibrary
from sapfx_common.object_tree import ScreenElement


class FakeField:
    def __init__(self):
        self.text = ""
        self.Type = "GuiCTextField"

    def SetFocus(self):
        pass


class FakeCalendar:
    def __init__(self, session):
        self.SelectionInterval = ""
        self._session = session

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if name == "SelectionInterval" and value:
            # sélectionner referme le popup et pose la date (comme le vrai)
            self._session._objects.pop("wnd[1]", None)
            self._session._objects["fld"].text = "01.09.2026"


class FakeSession:
    def __init__(self, objects):
        self._objects = objects

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self._objects:
            return self._objects[element_id]
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def _calendar_lib():
    field = FakeField()
    session = FakeSession({"fld": field, "wnd[1]": object()})
    session._objects["wnd[1]/usr/cntlCONTAINER/shellcont/shell"] = FakeCalendar(session)
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = session
    lib._screen_elements = lambda: [
        ScreenElement(id="wnd[1]/usr/cntlCONTAINER/shellcont/shell", type="GuiShell",
                      subtype="Calendar", text="SAPGUI.CalendarCtrl.1")]
    lib.send_vkey = lambda vkey, window=0: None
    lib.wait_until_busy_done = lambda *a, **k: None
    lib.wait_until_element_present = lambda *a, **k: None
    lib.get_value = lambda eid: session._objects[eid].text
    return lib


def test_pick_calendar_date_selectionne_et_relit_le_champ():
    assert _calendar_lib().pick_calendar_date("fld", "2026-09-01") == "01.09.2026"


def test_pick_calendar_date_refuse_une_date_non_iso():
    with pytest.raises(ValueError, match="ISO 8601"):
        _calendar_lib().pick_calendar_date("fld", "01.09.2026")


def test_pick_f4_value_nomme_le_calendrier_au_lieu_d_un_com_error():
    lib = _calendar_lib()
    with pytest.raises(AssertionError, match="CALENDRIER.*Pick Calendar Date"):
        lib.pick_f4_value("fld", "01.09.2026")


def test_pick_calendar_date_echoue_quand_l_aide_n_est_pas_un_calendrier():
    lib = _calendar_lib()
    lib._screen_elements = lambda: [ScreenElement(id="wnd[1]/usr/grid", type="GuiGridView")]
    with pytest.raises(AssertionError, match="Pick F4 Value"):
        lib.pick_calendar_date("fld", "2026-09-01")


def _labels_lib():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: [
        ScreenElement(id="wnd[0]/usr/chkA", type="GuiCheckBox", text="Sched.",
                      changeable=True, left=10, top=10, width=20, height=10),
        ScreenElement(id="wnd[0]/usr/chkB", type="GuiCheckBox", text="Released",
                      changeable=True, left=10, top=30, width=20, height=10),
        ScreenElement(id="wnd[0]/usr/radA", type="GuiRadioButton",
                      text="Professional User Transaction", changeable=True,
                      left=10, top=50, width=20, height=10),
        ScreenElement(id="wnd[0]/usr/lblX", type="GuiLabel", text="Job Name",
                      left=10, top=70, width=40, height=10),
    ]
    lib.actions = []
    lib.select_checkbox = lambda eid: lib.actions.append(("check", eid))
    lib.unselect_checkbox = lambda eid: lib.actions.append(("uncheck", eid))
    lib.select_radio_button = lambda eid: lib.actions.append(("radio", eid))
    lib.get_value = lambda eid: "checked" if eid == "wnd[0]/usr/chkA" else "unchecked"
    return lib


def test_cases_et_radios_par_leur_texte_propre():
    lib = _labels_lib()
    assert lib.select_checkbox_by_label("Sched") == "wnd[0]/usr/chkA"
    assert lib.unselect_checkbox_by_label("Released") == "wnd[0]/usr/chkB"
    assert lib.select_radio_button_by_label("Professional") == "wnd[0]/usr/radA"
    assert lib.actions == [("check", "wnd[0]/usr/chkA"), ("uncheck", "wnd[0]/usr/chkB"),
                           ("radio", "wnd[0]/usr/radA")]


def test_checkbox_by_label_should_be_et_echec_qui_liste_les_textes_propres():
    lib = _labels_lib()
    lib.checkbox_by_label_should_be("Sched", "checked")
    lib.checkbox_by_label_should_be("Released", False)
    with pytest.raises(AssertionError, match="est unchecked, attendu checked"):
        lib.checkbox_by_label_should_be("Released", True)
    with pytest.raises(AssertionError, match="Textes propres des cases") as exc:
        lib.select_checkbox_by_label("Scheduled")
    assert "Sched." in str(exc.value)
