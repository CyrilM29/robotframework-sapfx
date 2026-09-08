"""Tests hors SAP des deux résolveurs de contrôle, grille et arbre, alignés le
2026-09-08 après le registre de la seconde release : un ``GuiShell`` d'un autre
sous-type est REFUSÉ en nommant son lecteur (un arbre à colonnes porte
``ColumnOrder``, le résolveur de grille le prenait pour une ALV), un conteneur
est descendu jusqu'au bon contrôle en WARNING, et rien en dessous = échec
actionnable des DEUX côtés (le lecteur d'arbre laissait fuir une
``AttributeError`` COM brute)."""
import pytest

from SapEccLibrary import SapEccLibrary


class _Children:
    def __init__(self, items):
        self._items = list(items)
        self.Count = len(self._items)

    def ElementAt(self, index):  # noqa: N802 (API COM)
        return self._items[index]


class _Ctl:
    def __init__(self, Id, SubType=None, children=(), **attrs):  # noqa: N803
        self.Id = Id
        if SubType is not None:
            self.SubType = SubType
        self.Children = _Children(children)
        for name, value in attrs.items():
            setattr(self, name, value)


def _grid(Id="wnd[0]/usr/grid"):  # noqa: N803
    return _Ctl(Id, "GridView", ColumnOrder=["MANDT"], RowCount=0)


def _tree(Id="wnd[0]/usr/tree"):  # noqa: N803
    return _Ctl(Id, "Tree", ColumnOrder=["HierarchyHeader"], GetAllNodeKeys=lambda: [])


def _lib(objects):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = type("S", (), {"Busy": False,
                                 "findById": lambda self, eid, raise_on_missing=True: objects[eid]})()
    lib.element_should_be_present = lambda eid, **k: None
    return lib


def test_le_resolveur_de_grille_refuse_un_arbre_a_colonnes_en_nommant_son_lecteur():
    lib = _lib({"t": _tree("t")})
    with pytest.raises(ValueError, match="GuiShell/Tree.*Read Tree Nodes"):
        lib._grid("t")
    with pytest.raises(ValueError, match="GuiShell/Tree"):
        lib.get_grid_column_ids("t")           # ne PASSE plus en rendant HierarchyHeader


def test_le_resolveur_de_grille_descend_un_conteneur_et_saute_un_arbre():
    grid = _grid("wnd[0]/usr/c/shellcont[1]/shell")
    container = _Ctl("wnd[0]/usr/c", children=[_tree("wnd[0]/usr/c/shellcont[0]/shell"), grid])
    lib = _lib({"wnd[0]/usr/c": container})
    assert lib._grid("wnd[0]/usr/c") is grid
    assert lib._resolved_grid_id("wnd[0]/usr/c") == grid.Id
    only_tree = _Ctl("wnd[0]/usr/d", children=[_tree("wnd[0]/usr/d/shell")])
    with pytest.raises(ValueError, match="aucune grille n'a été trouvée en dessous"):
        _lib({"wnd[0]/usr/d": only_tree})._grid("wnd[0]/usr/d")


def test_un_splitter_est_un_conteneur_que_les_deux_resolveurs_traversent():
    """Le registre 758 a rougi sur ce cas le 2026-09-08 : refuser tout sous-type
    autre que GridView cassait la grille SE16 enveloppée dans un Splitter."""
    grid = _grid("wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")
    splitter = _Ctl("wnd[0]/usr/cntlGRID1/shellcont/shell", "Splitter",
                    children=[_Ctl("wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]", children=[grid])])
    lib = _lib({"wnd[0]/usr/cntlGRID1/shellcont/shell": splitter})
    assert lib._grid("wnd[0]/usr/cntlGRID1/shellcont/shell") is grid
    assert lib._resolved_grid_id("wnd[0]/usr/cntlGRID1/shellcont/shell") == grid.Id
    tree = _tree("wnd[0]/usr/s/shellcont[0]/shell")
    tree_splitter = _Ctl("wnd[0]/usr/s", "Splitter", children=[_Ctl("wnd[0]/usr/s/shellcont[0]", children=[tree])])
    assert _lib({"wnd[0]/usr/s": tree_splitter})._tree("wnd[0]/usr/s") is tree


def test_sans_sous_type_expose_column_order_decide_encore():
    """Compatibilité : les doublures et les clients qui n'exposent pas SubType."""
    legacy = _Ctl("g", ColumnOrder=["CARRID"])
    assert _lib({"g": legacy})._grid("g") is legacy


def test_le_resolveur_d_arbre_refuse_une_grille_en_nommant_read_grid():
    lib = _lib({"g": _grid("g")})
    with pytest.raises(ValueError, match="GuiShell/GridView.*Read Grid"):
        lib._tree("g")


def test_le_resolveur_d_arbre_descend_un_conteneur_et_echoue_en_nommant_la_profondeur():
    tree = _tree("wnd[0]/usr/c/shellcont/shell")
    container = _Ctl("wnd[0]/usr/c", children=[_Ctl("wnd[0]/usr/c/shellcont", children=[tree])])
    lib = _lib({"wnd[0]/usr/c": container})
    assert lib._tree("wnd[0]/usr/c") is tree
    empty = _Ctl("wnd[0]/usr/e", children=[_Ctl("wnd[0]/usr/e/x")])
    with pytest.raises(ValueError, match="aucun arbre n'a été trouvé en dessous \\(6 niveaux"):
        _lib({"wnd[0]/usr/e": empty})._tree("wnd[0]/usr/e")   # plus d'AttributeError brute
