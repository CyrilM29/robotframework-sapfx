"""Tests hors SAP du mixin ``ToolbarKeywords`` : inventaire de la barre
d'application depuis la perception (icône lue best-effort), clic par id, par
segment ou par icône, bouton absent = échec listant l'inventaire."""
import pytest

from SapEccLibrary import SapEccLibrary
from sapfx_common.object_tree import ScreenElement

TBAR = "wnd[0]/tbar[1]"


class _Button:
    def __init__(self, icon):
        self.IconName = icon


class FakeSession:
    Busy = False
    icons = {"btn[8]": "ICON_EXECUTE", "btn[31]": "ICON_COUNT"}

    def findById(self, element_id, raise_on_missing=True):  # noqa: N802
        segment = element_id.rsplit("/", 1)[-1]
        if segment in self.icons:
            return _Button(self.icons[segment])
        raise AttributeError("no icon")


def _lib():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession()
    lib._screen_elements = lambda: [
        ScreenElement(id=TBAR, type="GuiToolbar"),
        ScreenElement(id=TBAR + "/btn[8]", type="GuiButton", tooltip="Execute   (F8)"),
        ScreenElement(id=TBAR + "/btn[31]", type="GuiButton", text="Number of Entries"),
        ScreenElement(id="wnd[0]/tbar[0]/btn[0]", type="GuiButton", tooltip="Enter"),
        ScreenElement(id="wnd[0]/usr/btnX", type="GuiButton", text="Autre"),
    ]
    lib.clicked = []
    lib.click_element = lambda eid: lib.clicked.append(eid)
    lib.wait_until_busy_done = lambda *a, **k: None
    return lib


def test_list_toolbar_buttons_inventorie_la_barre_visee_avec_l_icone():
    lib = _lib()
    buttons = lib.list_toolbar_buttons()
    assert [(b["id"].rsplit("/", 1)[-1], b["icon"]) for b in buttons] == [
        ("btn[8]", "ICON_EXECUTE"), ("btn[31]", "ICON_COUNT")]
    assert buttons[0]["tooltip"] == "Execute   (F8)" and buttons[1]["text"] == "Number of Entries"
    assert [b["id"] for b in lib.list_toolbar_buttons("wnd[0]/tbar[0]")] == ["wnd[0]/tbar[0]/btn[0]"]
    assert lib.list_toolbar_buttons("wnd[0]/tbar[7]") == []


def test_click_application_toolbar_button_par_id_segment_ou_icone_et_echec_avec_inventaire():
    lib = _lib()
    assert lib.click_application_toolbar_button("btn[31]") == TBAR + "/btn[31]"
    assert lib.click_application_toolbar_button("icon_execute") == TBAR + "/btn[8]"
    assert lib.click_application_toolbar_button(TBAR + "/btn[8]") == TBAR + "/btn[8]"
    assert lib.clicked == [TBAR + "/btn[31]", TBAR + "/btn[8]", TBAR + "/btn[8]"]
    with pytest.raises(ValueError, match="Aucun bouton 'btn\\[99\\]'.*btn\\[31\\] \\(ICON_COUNT"):
        lib.click_application_toolbar_button("btn[99]")
