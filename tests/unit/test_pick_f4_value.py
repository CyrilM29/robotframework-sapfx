"""Tests hors SAP de `Pick F4 Value` (mixin ``SemanticKeywords``) : les deux
formes de popup (grille de résultats double-cliquée, liste à labels choisie
par F2), l'échec actionnable listant les valeurs, et le cas « aide à étapes »
où le popup survit à la sélection."""
import pytest

from SapEccLibrary.keywords._grid import GridKeywords
from SapEccLibrary.keywords._semantic import SemanticKeywords
from sapfx_common.object_tree import ScreenElement


class FakeField:
    def __init__(self):
        self.text = ""
        self.focused = False

    def SetFocus(self):
        self.focused = True


class FakeF4Grid:
    """GuiGridView de popup F4 : le double-clic sur la cellule courante
    reporte la valeur dans le champ et referme le popup (comme le vrai)."""

    def __init__(self, session, field):
        self.ColumnOrder = ["CARRID", "CARRNAME"]
        self._titles = {"CARRID": "Airline", "CARRNAME": "Name"}
        self._cells = {(0, "CARRID"): "AA", (0, "CARRNAME"): "American",
                       (1, "CARRID"): "LH", (1, "CARRNAME"): "Lufthansa"}
        self.RowCount = 2
        self.current = None
        self._session = session
        self._field = field
        self.close_on_pick = True

    def GetDisplayedColumnTitle(self, col_id):
        return self._titles[col_id]

    def GetCellValue(self, row, col_id):
        return self._cells[(row, col_id)]

    def SetCurrentCell(self, row, col_id):
        self.current = (row, col_id)

    def DoubleClickCurrentCell(self):
        row, _ = self.current
        self._field.text = self._cells[(row, "CARRID")]
        if self.close_on_pick:
            self._session._objects.pop("wnd[1]", None)


class FakeSession:
    def __init__(self, objects):
        self._objects = objects

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self._objects:
            return self._objects[element_id]
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def _lib(with_grid=True, labels=(), close_on_pick=True):
    field = FakeField()
    session = FakeSession({"fld": field, "wnd[1]": object()})
    elements = []
    if with_grid:
        grid = FakeF4Grid(session, field)
        grid.close_on_pick = close_on_pick
        session._objects["wnd[1]/usr/grid"] = grid
        elements.append(ScreenElement(id="wnd[1]/usr/grid", type="GuiGridView"))
    for index, text in enumerate(labels):
        label_id = "wnd[1]/usr/lbl[%d]" % index
        label = FakeField()
        session._objects[label_id] = label
        elements.append(ScreenElement(id=label_id, type="GuiLabel", text=text))

    cls = type("TestLib", (SemanticKeywords, GridKeywords), {})
    lib = cls()
    lib.session = session
    lib.field = field
    lib.vkeys = []
    lib.element_should_be_present = lambda element_id, message=None: None
    lib.take_screenshot = lambda *a, **k: None
    lib.wait_until_busy_done = lambda *a, **k: None
    lib.wait_until_element_present = lambda element_id, timeout=None: object()
    lib.get_value = lambda element_id: field.text
    lib._screen_elements = lambda: list(elements)

    def send_vkey(vkey_id, window=0):
        lib.vkeys.append((vkey_id, window))
        if vkey_id == 2 and window == 1:      # F2 : choisir le label focalisé
            focused = [obj for key, obj in session._objects.items()
                       if key.startswith("wnd[1]/usr/lbl")
                       and getattr(obj, "focused", False)]
            picked = elements[[session._objects[e.id] for e in elements
                               if e.type == "GuiLabel"].index(focused[0])]
            field.text = picked.text
            session._objects.pop("wnd[1]", None)
        if vkey_id == 12 and window == 1:     # F12 : refermer le popup
            session._objects.pop("wnd[1]", None)

    lib.send_vkey = send_vkey
    return lib


def test_pick_f4_grille_double_clic_et_retour_de_valeur():
    lib = _lib()
    assert lib.pick_f4_value("fld", "LH") == "LH"
    assert lib.field.focused is True
    assert (4, 0) in lib.vkeys                       # F4 sur la fenêtre principale
    assert lib.session.findById("wnd[1]", False) is None


def test_pick_f4_grille_colonne_restreinte_par_titre():
    lib = _lib()
    # 'Lufthansa' n'existe que dans la colonne Name ; la restriction le prouve
    assert lib.pick_f4_value("fld", "Lufthansa", column="Name") == "LH"


def test_pick_f4_liste_de_labels_via_f2():
    lib = _lib(with_grid=False, labels=["AA", "LH"])
    assert lib.pick_f4_value("fld", "LH") == "LH"
    assert (2, 1) in lib.vkeys                       # F2 sur le popup


def test_pick_f4_introuvable_referme_et_liste_les_valeurs():
    lib = _lib()
    with pytest.raises(AssertionError) as err:
        lib.pick_f4_value("fld", "XX")
    message = str(err.value)
    assert "AA" in message and "LH" in message
    assert (12, 1) in lib.vkeys                      # popup refermé par F12
    assert lib.session.findById("wnd[1]", False) is None


def test_pick_f4_popup_persistant_nomme_la_perception():
    lib = _lib(close_on_pick=False)                  # aide « à étapes »
    with pytest.raises(AssertionError, match="Get Screen Signature"):
        lib.pick_f4_value("fld", "LH")
