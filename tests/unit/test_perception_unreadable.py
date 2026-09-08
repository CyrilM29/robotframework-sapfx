"""Tests hors SAP des défauts « vert et faux » de perception corrigés le
2026-09-07 : une session illisible ÉCHOUE en nommant la cause (jamais
``# screen ?`` ni ``[]`` en PASS), la latche GetObjectTree ne se ferme pas sur
une AttributeError de proxy cross-thread, la signature porte le sous-type des
shells, et `Get Value` refuse de rendre un ProgID."""
import pytest
from pythoncom import com_error

from SapEccLibrary import SapEccLibrary
from SapEccLibrary.keywords._perception import ScreenUnreadableError
from sapfx_common.com_safety import RPC_E_WRONG_THREAD

from _perception_fixtures import FakeNode, FakeSession, ObjectTreeSession


class WrongThreadSession:
    """Proxy COM utilisé depuis un thread étranger : chaque accès lève."""

    def __init__(self, error):
        self._error = error

    def __getattr__(self, name):
        raise self._error


def _lib(session):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = session
    return lib


@pytest.mark.parametrize("error", [
    com_error(RPC_E_WRONG_THREAD, "interface d'un autre thread", None, None),
    AttributeError("<unknown>.Info"),
])
def test_signature_echoue_en_nommant_la_cause_quand_la_session_est_illisible(error):
    with pytest.raises(ScreenUnreadableError, match="use_context=true") as exc:
        _lib(WrongThreadSession(error)).get_screen_signature()
    assert "illisible" in str(exc.value)


def test_get_open_windows_echoue_au_lieu_de_rendre_une_liste_vide():
    with pytest.raises(ScreenUnreadableError, match="Children"):
        _lib(WrongThreadSession(AttributeError("<unknown>.Children"))).get_open_windows()


def test_la_latche_getobjecttree_ne_se_ferme_pas_sur_une_attributeerror_de_proxy():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    session = ObjectTreeSession(win, AttributeError("<unknown>.GetObjectTree"))
    lib = _lib(session)
    with pytest.raises(ScreenUnreadableError, match="GetObjectTree"):
        lib.get_screen_signature()
    assert not lib._object_tree_unsupported   # la prochaine perception retentera


def test_une_vraie_absence_d_api_ferme_toujours_la_latche():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    lib = _lib(ObjectTreeSession(win, AttributeError("GetObjectTree absent")))
    assert "txtA" in lib.get_screen_signature()
    assert lib._object_tree_unsupported


_TREE_WITH_SUBTYPE = """
{"children": [{
  "properties": {"Id": "/app/con[0]/ses[0]/wnd[0]", "Type": "GuiMainWindow", "Text": "SAP"},
  "children": [
    {"properties": {"Id": "/app/con[0]/ses[0]/wnd[0]/usr/cntlX/shellcont/shell",
                    "Type": "GuiShell", "SubType": "Tree", "Text": "SAP.TableTreeControl.1"},
     "children": []},
    {"properties": {"Id": "/app/con[0]/ses[0]/wnd[0]/usr/txtA", "Type": "GuiTextField",
                    "SubType": "", "Text": "x"}, "children": []}
  ]}]}
"""


def test_la_signature_affiche_le_sous_type_des_shells_et_le_type_nu_ailleurs():
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [])
    sig = _lib(ObjectTreeSession(win, _TREE_WITH_SUBTYPE)).get_screen_signature()
    assert "wnd[0]/usr/cntlX/shellcont/shell\tGuiShell/Tree\tSAP.TableTreeControl.1" in sig
    assert "wnd[0]/usr/txtA\tGuiTextField\tx" in sig


def test_la_marche_com_de_repli_lit_aussi_le_sous_type():
    shell = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/shell", "GuiShell", "SAPGUI.GridViewCtrl.1")
    shell.SubType = "GridView"
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [shell])
    lib = _lib(FakeSession(win))
    elements = lib._screen_elements()
    assert elements[1].subtype == "GridView"
    assert "GuiShell/GridView" in lib.get_screen_signature()


class _Shell:
    """Doublure d'un GuiShell tel que le keyword hérité `Get Value` le lit :
    pywin32 est insensible à la casse (``type``/``text``), une doublure non."""

    def __init__(self, subtype, text):
        self.type = self.Type = "GuiShell"
        self.text = self.Text = text
        self.SubType = subtype

    def setFocus(self):
        pass


class ShellSession(FakeSession):
    def __init__(self, subtype, text):
        super().__init__(None)
        self._shell = _Shell(subtype, text)

    def findById(self, element_id, raise_on_missing=True):
        return self._shell


def test_get_value_refuse_le_progid_d_un_shell_en_nommant_le_lecteur():
    lib = _lib(ShellSession("AbapEditor", "SAPGUI.AbapEditor.1"))
    with pytest.raises(ValueError, match="GuiShell/AbapEditor") as exc:
        lib.get_value("wnd[0]/usr/shell")
    assert "ProgID" in str(exc.value) and "hors de l'API" in str(exc.value)
    lib = _lib(ShellSession("Tree", "SAP.TableTreeControl.1"))
    with pytest.raises(ValueError, match="Read Tree Nodes"):
        lib.get_value("wnd[0]/usr/shell")


def test_get_value_rend_le_texte_reel_d_un_shell_qui_en_a_un():
    lib = _lib(ShellSession("TextEdit", "Bonjour depuis un éditeur de texte"))
    assert lib.get_value("wnd[0]/usr/shell") == "Bonjour depuis un éditeur de texte"
