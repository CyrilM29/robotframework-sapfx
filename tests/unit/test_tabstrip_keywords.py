"""Tests hors SAP des onglets : la logique pure (``sapfx_common.tab_strip``) et
le mixin ``TabStripKeywords`` (liste depuis la perception, onglet actif relu par
``SelectedTab`` à id ABSOLU, sélection par clé ou libellé VÉRIFIÉE)."""
import pytest

from SapEccLibrary import SapEccLibrary
from sapfx_common.object_tree import ScreenElement
from sapfx_common.tab_strip import (
    describe_tabs,
    find_tab_by_key,
    find_tabs_by_label,
    format_tabs,
    relative_id,
    tab_key,
)

STRIP = "wnd[0]/usr/tabsTABSTRIP1"
TABS = [("DOCU", "Documentation"), ("ADDR", "Address"), ("LOGO", "Logon Data"),
        ("DEFA", "Defaults"), ("USAT", "User Attributes")]


def _elements():
    elements = [ScreenElement(id=STRIP, type="GuiTabStrip")]
    for key, text in TABS:
        elements.append(ScreenElement(id="%s/tabp%s" % (STRIP, key), type="GuiTab", text=text))
    elements.append(ScreenElement(id="wnd[0]/usr/tabsOTHER/tabpXX", type="GuiTab", text="Autre"))
    return elements


def test_relative_id_tab_key_et_describe_tabs():
    assert relative_id("/app/con[0]/ses[0]/wnd[0]/usr/tabsT/tabpADDR") == "wnd[0]/usr/tabsT/tabpADDR"
    assert relative_id("wnd[0]/usr/tabsT/tabpADDR") == "wnd[0]/usr/tabsT/tabpADDR"
    assert tab_key("wnd[0]/usr/tabsT/tabpLOGO") == "LOGO" and tab_key("wnd[0]/usr/txtX") == ""
    tabs = describe_tabs(_elements(), STRIP, "/app/con[0]/ses[0]/" + STRIP + "/tabpADDR")
    assert [t["key"] for t in tabs] == ["DOCU", "ADDR", "LOGO", "DEFA", "USAT"]
    assert [t["selected"] for t in tabs] == [False, True, False, False, False]
    assert "ADDR=Address (actif)" in format_tabs(tabs)
    assert find_tab_by_key(tabs, "logo")["text"] == "Logon Data"
    assert find_tab_by_key(tabs, "NOPE") is None
    assert [t["key"] for t in find_tabs_by_label(tabs, "d")] == ["DOCU", "DEFA"]   # préfixe : ambigu
    assert [t["key"] for t in find_tabs_by_label(tabs, "Defaults", exact=True)] == ["DEFA"]


class _Tab:
    def __init__(self, strip, tab_id):
        self._strip, self._id = strip, tab_id

    def Select(self):  # noqa: N802 (API COM)
        self._strip.selected = self._id


class _Strip:
    def __init__(self):
        self.selected = "/app/con[0]/ses[0]/" + STRIP + "/tabpADDR"

    @property
    def SelectedTab(self):  # noqa: N802 (API COM)
        return type("T", (), {"Id": self.selected})()


class FakeSession:
    def __init__(self):
        self.Busy = False
        self.strip = _Strip()

    def findById(self, element_id, raise_on_missing=True):  # noqa: N802
        if element_id == STRIP:
            return self.strip
        if "/tabp" in element_id:
            return _Tab(self.strip, "/app/con[0]/ses[0]/" + element_id)
        raise KeyError(element_id)


def _lib():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession()
    lib._screen_elements = _elements
    lib.get_element_type = lambda eid: "GuiTabStrip" if eid == STRIP else "GuiTextField"
    lib.wait_until_busy_done = lambda *a, **k: None
    return lib


def test_list_tabs_get_selected_tab_et_select_tab_par_cle_verifiee():
    lib = _lib()
    assert [t["key"] for t in lib.list_tabs(STRIP)] == ["DOCU", "ADDR", "LOGO", "DEFA", "USAT"]
    assert lib.get_selected_tab(STRIP)["key"] == "ADDR"
    assert lib.select_tab(STRIP, "logo")["key"] == "LOGO"
    assert lib.get_selected_tab(STRIP)["key"] == "LOGO"
    with pytest.raises(ValueError, match="Aucun onglet de clé 'NOPE'.*LOGO=Logon Data \\(actif\\)"):
        lib.select_tab(STRIP, "NOPE")


def test_select_tab_by_label_prefixe_exact_et_ambiguite():
    lib = _lib()
    assert lib.select_tab_by_label(STRIP, "user attr")["key"] == "USAT"
    with pytest.raises(ValueError, match="ambigu"):
        lib.select_tab_by_label(STRIP, "d")
    with pytest.raises(ValueError, match="LOCALISÉ"):
        lib.select_tab_by_label(STRIP, "Nope")
    assert lib.select_tab_by_label(STRIP, "Defaults", exact=True)["key"] == "DEFA"


def test_un_element_qui_n_est_pas_un_tabstrip_est_refuse_et_une_selection_non_acquise_echoue():
    lib = _lib()
    with pytest.raises(ValueError, match="pas un GuiTabStrip"):
        lib.list_tabs("wnd[0]/usr/txtX")
    lib.session.strip.selected = ""        # SelectedTab illisible : aucun onglet actif
    with pytest.raises(AssertionError, match="ne désigne pas UN onglet actif"):
        lib.get_selected_tab(STRIP)
