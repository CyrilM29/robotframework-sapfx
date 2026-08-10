"""Tests hors SAP des **GuiTableControl** : logique pure
(``sapfx_common.table_control`` : titres, fenêtres de défilement, ligne
absolue) et mixin ``GridKeywords`` contre de faux objets COM (défilement +
ré-acquisition de l'objet après scroll, lecture par titre, écriture refusée
sur cellule non modifiable)."""
import importlib

import pytest
from pythoncom import com_error

from SapEccLibrary.keywords._grid import GridKeywords
from sapfx_common.table_control import (
    column_index_by_title,
    unique_titles,
    window_for_row,
    window_plan,
)


# --- logique pure ------------------------------------------------------------

def test_unique_titles_col_vides_et_doublons():
    assert unique_titles(["Qty", "", "Qty", "Item"]) == [
        "Qty", "COL2", "Qty (2)", "Item"]


def test_column_index_by_title_exact_insensible_a_la_casse():
    assert column_index_by_title(["Item", "Quantity"], " quantity ") == 1


def test_column_index_by_title_doublon_invite_a_la_forme_dedoublonnee():
    with pytest.raises(ValueError, match=r"Qty \(2\)"):
        column_index_by_title(["Qty", "Qty"], "Qty")
    # la forme dédoublonnée, elle, résout
    assert column_index_by_title(["Qty", "Qty"], "Qty (2)") == 1


def test_column_index_by_title_absent_liste_les_titres():
    with pytest.raises(ValueError, match="Titres disponibles"):
        column_index_by_title(["Item"], "Prix", context="tbl")


def test_window_plan_couvre_chaque_ligne_une_fois():
    # (position, index local de départ, nombre de lignes)
    assert window_plan(5, 2) == [(0, 0, 2), (2, 0, 2), (3, 1, 1)]
    assert window_plan(4, 2) == [(0, 0, 2), (2, 0, 2)]
    assert window_plan(2, 5) == [(0, 0, 2)]
    assert window_plan(0, 2) == []
    assert window_plan(5, 0) == [(0, 0, 5)]


def test_window_plan_borne_la_scrollbar_cas_live_se11():
    # Cas RÉEL constaté live (SE11/SNWD_PD) : 47 lignes, 22 visibles, la
    # scrollbar plafonne à 25. Demander la position 44 lève un com_error :
    # la dernière fenêtre est bornée et lue depuis un index local décalé.
    plan = window_plan(47, 22)
    assert plan == [(0, 0, 22), (22, 0, 22), (25, 19, 3)]
    assert max(position for position, _, _ in plan) <= 47 - 22
    # chaque ligne absolue exactement une fois, dans l'ordre
    seen = [position + local
            for position, first, count in plan
            for local in range(first, first + count)]
    assert seen == list(range(47))


def test_window_for_row_alignee_et_bornee_en_fin_de_table():
    assert window_for_row(3, 5, 2) == (2, 1)
    # dernière fenêtre bornée à total - visible : la ligne reste visible
    assert window_for_row(4, 5, 2) == (3, 1)
    assert window_for_row(1, 5, 0) == (0, 1)
    with pytest.raises(ValueError, match="hors bornes"):
        window_for_row(5, 5, 2)


# --- faux objets COM ---------------------------------------------------------

class FakeCell:
    def __init__(self, text, changeable=True):
        self.Text = text
        self.Changeable = changeable


class FakeColumn:
    def __init__(self, title):
        self.Title = title
        self.Tooltip = ""
        self.Name = ""


class FakeColumns:
    def __init__(self, titles):
        self._columns = [FakeColumn(t) for t in titles]
        self.Count = len(self._columns)

    def ElementAt(self, index):
        return self._columns[index]


class FakeScrollbar:
    """Scrollbar de table control : comme le vrai objet COM, elle REFUSE une
    position au-delà de ``Maximum`` (= total - visible), le com_error attrapé
    live sur SE11."""

    def __init__(self, maximum=0):
        self._position = 0
        self.Maximum = maximum
        self.Minimum = 0

    @property
    def Position(self):
        return self._position

    @Position.setter
    def Position(self, value):
        if int(value) > int(self.Maximum):
            raise FakeComError(
                "The method got an invalid argument (position %s > max %s)"
                % (value, self.Maximum))
        self._position = int(value)


class FakeComError(com_error):
    """Un vrai ``com_error`` (celui que le mixin attrape), levé par les fakes."""


class FakeTableControl:
    """GuiTableControl minimal : cellules absolues, fenêtre visible pilotée
    par la scrollbar (GetCell est LOCAL à la fenêtre, comme le vrai, et lève
    hors de la fenêtre visible)."""

    def __init__(self, titles, rows, visible=2):
        self.Columns = FakeColumns(titles)
        self._cells = [[FakeCell(text) for text in row] for row in rows]
        self.RowCount = len(rows)
        self.VisibleRowCount = visible
        self.VerticalScrollbar = FakeScrollbar(max(0, len(rows) - visible))

    def GetCell(self, local_row, column):
        if local_row >= self.VisibleRowCount:
            raise FakeComError("The method got an invalid argument")
        absolute = self.VerticalScrollbar.Position + local_row
        if absolute >= len(self._cells):
            raise FakeComError("The method got an invalid argument")
        return self._cells[absolute][column]


class FakeSession:
    def __init__(self, objects):
        self._objects = objects

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self._objects:
            return self._objects[element_id]
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def _lib(table):
    cls = type("TestLib", (GridKeywords,), {})
    lib = cls()
    lib.session = FakeSession({"tbl": table})
    lib.element_should_be_present = lambda element_id, message=None: None
    lib.take_screenshot = lambda *a, **k: None
    lib.busy_waits = []
    lib.wait_until_busy_done = lambda *a, **k: lib.busy_waits.append(True)
    return lib


def _table():
    return FakeTableControl(
        ["Item", "Qty"],
        [["A", "1"], ["B", "2"], ["C", "3"], ["D", "4"], ["E", "5"]],
        visible=2)


# --- lecture complète avec défilement ---------------------------------------

def test_read_table_control_defile_et_lit_tout():
    table = _table()
    lib = _lib(table)
    rows = lib.read_table_control("tbl")
    assert rows == [{"Item": "A", "Qty": "1"}, {"Item": "B", "Qty": "2"},
                    {"Item": "C", "Qty": "3"}, {"Item": "D", "Qty": "4"},
                    {"Item": "E", "Qty": "5"}]
    # chaque défilement est un aller-retour serveur attendu
    assert len(lib.busy_waits) >= 2
    # position de départ restaurée
    assert table.VerticalScrollbar.Position == 0


def test_read_table_control_titres_normalises():
    table = FakeTableControl(["Qty", "", "Qty"],
                             [["1", "x", "9"]], visible=3)
    lib = _lib(table)
    assert lib.read_table_control("tbl") == [
        {"Qty": "1", "COL2": "x", "Qty (2)": "9"}]


def test_read_table_control_max_rows_annonce(monkeypatch):
    warnings = []
    grid_module = importlib.import_module("SapEccLibrary.keywords._grid")
    monkeypatch.setattr(grid_module.logger, "warn",
                        lambda msg: warnings.append(msg))
    lib = _lib(_table())
    assert len(lib.read_table_control("tbl", max_rows=3)) == 3
    assert any("max_rows" in w for w in warnings)


def test_table_control_redirige_l_alv_vers_read_grid():
    class FakeAlv:
        ColumnOrder = ["A"]

    lib = _lib(FakeAlv())
    with pytest.raises(ValueError, match="Read Grid"):
        lib.read_table_control("tbl")


def test_table_control_refuse_un_objet_quelconque():
    lib = _lib(object())
    with pytest.raises(ValueError, match="GuiTableControl"):
        lib.read_table_control("tbl")


# --- cellule absolue : lecture, écriture, recherche --------------------------

def test_get_table_control_cell_defile_jusqu_a_la_ligne():
    table = _table()
    lib = _lib(table)
    assert lib.get_table_control_cell("tbl", 3, "Qty") == "4"
    assert table.VerticalScrollbar.Position == 2   # fenêtre [2..3]


def test_get_table_control_cell_hors_bornes_actionnable():
    lib = _lib(_table())
    with pytest.raises(ValueError, match="hors bornes"):
        lib.get_table_control_cell("tbl", 9, "Qty")


def test_set_table_control_cell_ecrit_dans_la_bonne_cellule():
    table = _table()
    lib = _lib(table)
    lib.set_table_control_cell("tbl", 4, "Item", "Z")
    assert table._cells[4][0].Text == "Z"


def test_set_table_control_cell_refuse_une_cellule_en_lecture_seule():
    table = _table()
    table._cells[0][1].Changeable = False
    lib = _lib(table)
    with pytest.raises(AssertionError, match="pas\\s+modifiable"):
        lib.set_table_control_cell("tbl", 0, "Qty", "9")


def test_find_table_control_row_au_dela_de_la_premiere_fenetre():
    lib = _lib(_table())
    assert lib.find_table_control_row("tbl", "Item", "D") == 3
    assert lib.find_table_control_row("tbl", "Item", "d", ignore_case=True) == 3
    assert lib.find_table_control_row("tbl", "Item", "ZZ") == -1


# --- régressions attrapées LIVE (SE11/SNWD_PD, 2026-08-10) -------------------

def test_lecture_d_une_table_dont_la_scrollbar_plafonne():
    """47 lignes pour 22 visibles : la scrollbar refuse toute position > 25.
    L'ancien plan (0, 22, 44) levait un com_error ; le plan borné lit les 47
    lignes, chacune UNE fois et dans l'ordre."""
    rows = [["L%02d" % index] for index in range(47)]
    table = FakeTableControl(["Field"], rows, visible=22)
    lib = _lib(table)
    read = lib.read_table_control("tbl")
    assert [r["Field"] for r in read] == ["L%02d" % i for i in range(47)]
    assert table.VerticalScrollbar.Position == 0   # position restaurée
    # la dernière ligne est atteignable directement (scroll borné)
    assert lib.get_table_control_cell("tbl", 46, "Field") == "L46"
    assert lib.find_table_control_row("tbl", "Field", "L45") == 45


def test_cellule_absente_lue_comme_vide_mais_ecriture_toujours_explicite():
    """Une cellule isolée non matérialisée (colonne absente sur cette ligne)
    est lue comme vide : une lecture ne doit pas échouer pour ça. L'écriture,
    elle, ne masque jamais l'erreur COM."""
    table = _table()
    original = table.GetCell

    def flaky(local_row, column):
        if column == 1 and table.VerticalScrollbar.Position + local_row == 1:
            raise FakeComError("The method got an invalid argument")
        return original(local_row, column)

    table.GetCell = flaky
    lib = _lib(table)
    rows = lib.read_table_control("tbl")
    assert rows[1] == {"Item": "B", "Qty": ""}      # lecture tolérante
    with pytest.raises(FakeComError):               # écriture jamais masquée
        lib.set_table_control_cell("tbl", 1, "Qty", "9")


def test_rowcount_annonce_des_lignes_reservees_pas_remplies():
    """LE piège des table controls, mesuré live (SE11/SNWD_PD) : RowCount=47
    alors que seules 26 lignes sont remplies ; les lignes réservées n'ont
    aucune cellule. La lecture s'arrête aux lignes réelles (jamais de lignes
    fantômes), la recherche aussi, et l'accès direct à une ligne réservée
    échoue en NOMMANT le piège."""
    filled = [["F%02d" % index] for index in range(26)]
    table = FakeTableControl(["Field"], filled, visible=22)
    table.RowCount = 47                      # l'écran RÉSERVE 47 lignes
    table.VerticalScrollbar.Maximum = 25     # la scrollbar, elle, dit vrai
    lib = _lib(table)

    rows = lib.read_table_control("tbl")
    assert len(rows) == 26
    assert rows[0]["Field"] == "F00" and rows[25]["Field"] == "F25"

    assert lib.get_table_control_cell("tbl", 25, "Field") == "F25"
    assert lib.find_table_control_row("tbl", "Field", "F25") == 25
    assert lib.find_table_control_row("tbl", "Field", "ABSENT") == -1

    with pytest.raises(AssertionError) as err:
        lib.get_table_control_cell("tbl", 46, "Field")
    assert "RÉSERVÉES" in str(err.value)
    assert "Read Table Control" in str(err.value)
