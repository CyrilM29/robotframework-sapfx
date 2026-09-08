"""Tests hors SAP du mixin ``GridActionKeywords`` : double-clic de cellule, menu
contextuel par code fonction, inventaire de la barre, tri, et les surcharges
des keywords hérités (`Doubleclick Element`, `Select Context Menu Item`,
`Click Toolbar Button`) sur une doublure de GuiGridView."""
import pytest
from pythoncom import com_error

from SapEccLibrary import SapEccLibrary


class _MenuNode:
    def __init__(self, name="", text="", children=()):
        self.Name = name
        self.Text = text
        self.Children = _Col(children)


class _Col:
    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def Item(self, index):
        return self._items[index]


class FakeGrid:
    def __init__(self, toolbar=(), menu=()):
        self.ColumnOrder = ["MANDT", "MTEXT"]
        self.current = None
        self.double_clicked = 0
        self.selected_column = None
        self.pressed = []
        self.context_selected = []
        self._toolbar = list(toolbar)
        self._menu = _MenuNode(children=menu)
        self.menu_opened = 0

    def SetCurrentCell(self, row, column):
        if column not in self.ColumnOrder:
            raise com_error("invalid column")
        self.current = (row, column)

    def DoubleClickCurrentCell(self):
        self.double_clicked += 1

    def ContextMenu(self):
        self.menu_opened += 1

    @property
    def CurrentContextMenu(self):
        return self._menu

    def SelectContextMenuItem(self, code):
        self.context_selected.append(code)

    @property
    def ToolbarButtonCount(self):
        return len(self._toolbar)

    def GetToolbarButtonId(self, index):
        return self._toolbar[index][0]

    def GetToolbarButtonTooltip(self, index):
        return self._toolbar[index][1]

    def GetToolbarButtonType(self, index):
        return "Button"

    def PressToolbarButton(self, code):
        if code not in [b[0] for b in self._toolbar]:
            raise com_error("no such button")
        self.pressed.append(code)

    def pressToolbarButton(self, code):
        self.PressToolbarButton(code)

    def SelectColumn(self, column):
        self.selected_column = column


class FakeSession:
    def __init__(self, grid):
        self._grid = grid

    def findById(self, element_id, raise_on_missing=True):
        if element_id == "grid":
            return self._grid
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def _lib(grid):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(grid)
    lib.element_should_be_present = lambda *a, **k: None
    lib.wait_until_busy_done = lambda *a, **k: None
    lib.get_element_type = lambda eid: "GuiShell"
    return lib


MENU = (_MenuNode("&FIND", "Find"), _MenuNode("&FILTER", "Set Filter..."),
        _MenuNode("", "", children=(_MenuNode("&XXL", "Spreadsheet..."),)))


def test_double_click_grid_cell_et_la_surcharge_de_doubleclick_element():
    grid = FakeGrid()
    lib = _lib(grid)
    lib.double_click_grid_cell("grid", 0, "MANDT")
    lib.doubleclick_element("grid", "1", "MTEXT")
    assert grid.double_clicked == 2 and grid.current == (1, "MTEXT")
    with pytest.raises(ValueError, match="colonnes disponibles"):
        lib.double_click_grid_cell("grid", 0, "NOPE")


def test_list_et_select_grid_context_menu_item_par_code():
    grid = FakeGrid(menu=MENU)
    lib = _lib(grid)
    items = lib.list_grid_context_menu("grid")
    assert [i["code"] for i in items] == ["&FIND", "&FILTER", "&XXL"]
    assert items[2]["level"] == 1
    lib.select_grid_context_menu_item("grid", "&FILTER")
    lib.select_context_menu_item("grid", "ignored", "&FIND")     # surcharge hérité
    assert grid.context_selected == ["&FILTER", "&FIND"]
    with pytest.raises(ValueError, match="Codes disponibles : &FIND"):
        lib.select_grid_context_menu_item("grid", "&SORT_DSC")


def test_click_toolbar_button_absent_liste_la_barre_ou_nomme_son_absence():
    lib = _lib(FakeGrid(toolbar=[("&SORT_UP", "Sort ascending")]))
    with pytest.raises(ValueError, match="&SORT_UP \\(Sort ascending\\)"):
        lib.click_toolbar_button("grid", "&NOPE")
    lib = _lib(FakeGrid())
    with pytest.raises(ValueError, match="pas de barre d'outils propre"):
        lib.click_toolbar_button("grid", "&NOPE")
    assert lib.list_grid_toolbar_buttons("grid") == []


def test_sort_grid_by_column_par_barre_puis_menu_puis_echec_nomme():
    grid = FakeGrid(toolbar=[("&SORT_UP", "asc"), ("&SORT_DOWN", "desc")])
    lib = _lib(grid)
    assert lib.sort_grid_by_column("grid", "MANDT", descending=True) == "&SORT_DOWN"
    assert grid.selected_column == "MANDT" and grid.pressed == ["&SORT_DOWN"]
    grid = FakeGrid(menu=(_MenuNode("&SORT_ASC", "Sort"),))
    assert _lib(grid).sort_grid_by_column("grid", "MANDT") == "&SORT_ASC"
    with pytest.raises(ValueError, match="barre d'application"):
        _lib(FakeGrid(menu=MENU)).sort_grid_by_column("grid", "MANDT")
