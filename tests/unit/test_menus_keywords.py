"""Tests hors SAP du mixin ``MenuKeywords`` : la barre perçue résolue par
chemin de textes ou de positions, puis sélectionnée par `Click Element`."""
import pytest

from SapEccLibrary import SapEccLibrary
from sapfx_common.object_tree import ScreenElement


def _lib():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: [
        ScreenElement(id="wnd[0]/mbar/menu[4]", type="GuiMenu", text="System"),
        ScreenElement(id="wnd[0]/mbar/menu[4]/menu[11]", type="GuiMenu", text="Status..."),
        ScreenElement(id="wnd[0]/mbar/menu[5]", type="GuiMenu", text="Help"),
    ]
    lib.clicked = []
    lib.click_element = lambda eid: lib.clicked.append(eid)
    lib.wait_until_busy_done = lambda *a, **k: None
    return lib


def test_list_menu_items_et_resolve_par_texte_ou_position():
    lib = _lib()
    items = lib.list_menu_items()
    assert [i["path"] for i in items] == ["4", "4 > 11", "5"]
    assert lib.resolve_menu_item("System > Status") == "wnd[0]/mbar/menu[4]/menu[11]"
    assert lib.resolve_menu_item("4 > 11") == "wnd[0]/mbar/menu[4]/menu[11]"


def test_select_menu_item_clique_l_id_resolu_et_refuse_un_chemin_absent():
    lib = _lib()
    assert lib.select_menu_item("System > Status") == "wnd[0]/mbar/menu[4]/menu[11]"
    assert lib.clicked == ["wnd[0]/mbar/menu[4]/menu[11]"]
    with pytest.raises(ValueError, match="aucune entrée 'Edit'"):
        lib.select_menu_item("Edit > Cancel")


def test_sans_barre_percue_l_echec_nomme_la_fenetre():
    lib = _lib()
    lib._screen_elements = lambda: []
    with pytest.raises(ValueError, match="wnd\\[1\\]/mbar"):
        lib.resolve_menu_item("System > Status", window="wnd[1]")
