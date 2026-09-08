"""Tests hors SAP de ``sapfx_common.menu_path`` (barre de menus, logique pure)."""
import pytest

from sapfx_common.menu_path import (
    describe_menu,
    menu_items_from_elements,
    resolve_menu_path,
)
from sapfx_common.object_tree import ScreenElement


def _el(eid, text, etype="GuiMenu"):
    return ScreenElement(id=eid, type=etype, text=text)


ELEMENTS = [
    _el("wnd[0]/mbar", "", "GuiMenubar"),
    _el("wnd[0]/mbar/menu[0]", "Menu"),
    _el("wnd[0]/mbar/menu[0]/menu[0]", "User Menu"),
    _el("wnd[0]/mbar/menu[4]", "System"),
    _el("wnd[0]/mbar/menu[4]/menu[10]", "Short Message"),
    _el("wnd[0]/mbar/menu[4]/menu[11]", "Status..."),
    _el("wnd[0]/mbar/menu[4]/menu[12]", "Log Off"),
    _el("wnd[0]/mbar/menu[4]/menu[3]", "Services"),
    _el("wnd[0]/mbar/menu[4]/menu[3]/menu[0]", "Reporting"),
    _el("wnd[0]/tbar[0]/btn[0]", "Enter", "GuiButton"),
    _el("wnd[1]/mbar/menu[0]", "Popup menu"),
]


def test_menu_items_from_elements_ne_garde_que_les_menus_de_la_fenetre():
    items = menu_items_from_elements(ELEMENTS)
    assert [i.positions for i in items][:3] == [(0,), (0, 0), (4,)]
    assert all(i.id.startswith("wnd[0]/mbar/") for i in items)
    assert len(menu_items_from_elements(ELEMENTS, "wnd[1]")) == 1


def test_resolve_menu_path_par_textes_positions_et_mixte():
    items = menu_items_from_elements(ELEMENTS)
    assert resolve_menu_path(items, "System > Status").id == "wnd[0]/mbar/menu[4]/menu[11]"
    assert resolve_menu_path(items, "4 > 11").id == "wnd[0]/mbar/menu[4]/menu[11]"
    assert resolve_menu_path(items, "system > 3 > report").id == \
        "wnd[0]/mbar/menu[4]/menu[3]/menu[0]"


def test_resolve_menu_path_refuse_vide_absent_et_ambigu():
    items = menu_items_from_elements(ELEMENTS)
    with pytest.raises(ValueError, match="vide"):
        resolve_menu_path(items, "  ")
    with pytest.raises(ValueError, match="aucune entrée 'Help' au niveau 1") as exc:
        resolve_menu_path(items, "Help > About")
    assert "4=System" in str(exc.value)
    with pytest.raises(ValueError, match="ambigu au niveau 2"):
        resolve_menu_path(items, "System > S")


def test_describe_menu_rend_un_chemin_de_positions_rejouable():
    described = describe_menu(menu_items_from_elements(ELEMENTS))
    status = next(d for d in described if d["text"] == "Status...")
    assert status["path"] == "4 > 11" and status["positions"] == [4, 11]
