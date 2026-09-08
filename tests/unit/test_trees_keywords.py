"""Tests hors SAP du mixin ``TreeKeywords`` (arbres SAP GUI) sur une doublure de
``GuiShell/Tree`` reproduisant l'API relevée live : clés opaques, arbre simple
(texte par ``GetNodeTextByKey``) et arbre à colonnes (texte dans ``TEXT``)."""
import pytest

from SapEccLibrary import SapEccLibrary


class FakeCol:
    def __init__(self, items):
        self._items = list(items)

    @property
    def Count(self):
        return len(self._items)

    def Item(self, index):
        return self._items[index]


class FakeTree:
    def __init__(self, nodes, children, columns=None, texts_by_column=None):
        self.SubType = "Tree"
        self._nodes = nodes                 # key -> text
        self._children = children           # key -> [keys]
        self._columns = columns or []
        self._cells = texts_by_column or {}
        self.SelectedNode = ""
        self.expanded = []
        self.double_clicked = []

    def GetAllNodeKeys(self):
        return FakeCol(self._nodes.keys())

    def GetNodeTextByKey(self, key):
        return self._nodes[key]

    def GetColumnNames(self):
        return FakeCol(self._columns)

    def GetItemText(self, key, column):
        return self._cells.get((key, column), "")

    def IsFolder(self, key):
        return bool(self._children.get(key))

    def GetNodeChildrenCount(self, key):
        return len(self._children.get(key, []))

    def GetSubNodesCol(self, key):
        return FakeCol(self._children.get(key, []))

    def SelectNode(self, key):
        if key not in self._nodes:
            from pythoncom import com_error
            raise com_error("invalid node key")
        self.SelectedNode = key

    def ExpandNode(self, key):
        self.expanded.append(key)

    def DoubleClickNode(self, key):
        self.double_clicked.append(key)


class FakeSession:
    def __init__(self, tree):
        self._tree = tree

    def findById(self, element_id, raise_on_missing=True):
        if element_id == "tree":
            return self._tree
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def _lib(tree):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(tree)
    lib.element_should_be_present = lambda *a, **k: None
    lib.wait_until_busy_done = lambda *a, **k: None
    return lib


def _menu_tree():
    return FakeTree(
        {"Favo": "Favorites", "Root": "User Menu", "0000000003": "Plain ABAP",
         "0000000029": "URL - ABAP Samples"},
        {"Favo": [], "Root": ["0000000003"], "0000000003": ["0000000029"]})


def test_read_tree_nodes_rend_cles_intactes_textes_et_dossiers():
    nodes = _lib(_menu_tree()).read_tree_nodes("tree")
    assert [n["key"] for n in nodes] == ["Favo", "Root", "0000000003", "0000000029"]
    root = next(n for n in nodes if n["key"] == "Root")
    assert root["text"] == "User Menu" and root["folder"] and root["children"] == 1


def test_read_tree_nodes_echoue_quand_le_plafond_est_atteint():
    with pytest.raises(AssertionError, match="plafond max_nodes=2"):
        _lib(_menu_tree()).read_tree_nodes("tree", max_nodes=2)


def test_select_tree_node_verifie_la_selection_et_developpe():
    tree = _menu_tree()
    lib = _lib(tree)
    assert lib.select_tree_node("tree", "0000000003", expand=True) == "0000000003"
    assert tree.expanded == ["0000000003"]
    assert lib.get_selected_tree_node("tree") == "0000000003"
    lib.select_node("tree", "Favo")            # l'hérité surchargé passe par SelectNode
    assert tree.SelectedNode == "Favo"


def test_select_tree_node_echoue_en_listant_les_noeuds():
    with pytest.raises(ValueError, match="'ZZ'.*Nœuds rendus") as exc:
        _lib(_menu_tree()).select_tree_node("tree", "ZZ")
    assert "'Favo' -> Favorites" in str(exc.value)


def test_select_by_text_et_par_chemin():
    tree = _menu_tree()
    lib = _lib(tree)
    assert lib.select_tree_node_by_text("tree", "plain") == "0000000003"
    assert lib.select_tree_node_by_path("tree", "User Menu > Plain ABAP > URL") == "0000000029"
    assert tree.expanded[-2:] == ["Root", "0000000003"]
    with pytest.raises(ValueError, match="niveau 2"):
        lib.select_tree_node_by_path("tree", "User Menu > Nope")


def test_expand_tree_node_rend_les_enfants_et_double_click():
    tree = _menu_tree()
    lib = _lib(tree)
    children = lib.expand_tree_node("tree", "Root")
    assert [c["key"] for c in children] == ["0000000003"]
    lib.double_click_tree_node("tree", "0000000029")
    assert tree.double_clicked == ["0000000029"]


def test_arbre_a_colonnes_lit_le_texte_dans_la_colonne_text():
    tree = FakeTree({"01  1      1": "", "02  1      2": ""},
                    {"01  1      1": ["02  1      2"]},
                    columns=["1", "TEXT"],
                    texts_by_column={("01  1      1", "TEXT"): "SAP Customizing IMG",
                                     ("02  1      2", "TEXT"): "Enterprise Structure"})
    nodes = _lib(tree).read_tree_nodes("tree")
    assert nodes[0]["key"] == "01  1      1" and nodes[0]["text"] == "SAP Customizing IMG"
    assert nodes[1]["columns"]["TEXT"] == "Enterprise Structure"
    assert _lib(tree).get_tree_node_key_by_text("tree", "Enterprise") == "02  1      2"


def test_un_shell_qui_n_est_pas_un_arbre_est_refuse_en_nommant_le_sous_type():
    grid = FakeTree({}, {})
    grid.SubType = "GridView"
    with pytest.raises(ValueError, match="GuiShell/GridView"):
        _lib(grid).read_tree_nodes("tree")
