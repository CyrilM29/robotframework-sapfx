"""Doublures et helpers partages des tests des localisateurs humains (grammaire + keywords) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import pytest


from SapEccLibrary import SapEccLibrary


from sapfx_common.object_tree import ScreenElement


from sapfx_common.semantic import (
    is_label,
    nearby_labels,
    resolve_semantic,
    text_matches,
)


def _el(eid, etype, text="", tooltip="", changeable=False, box=None):
    left, top, width, height = box if box else (None, None, None, None)
    return ScreenElement(id=eid, type=etype, text=text, tooltip=tooltip,
                         changeable=changeable, left=left, top=top,
                         width=width, height=height)


LOGIN = [
    _el("wnd[0]", "GuiMainWindow", "SAP", box=(0, 0, 800, 600)),
    _el("wnd[0]/usr/lblClient", "GuiLabel", "Client", box=(10, 20, 80, 20)),
    _el("wnd[0]/usr/txtRSYST-MANDT", "GuiTextField", "001", changeable=True,
        box=(100, 20, 60, 20)),
    _el("wnd[0]/usr/lblUser", "GuiLabel", "User", box=(10, 50, 80, 20)),
    _el("wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", "", changeable=True,
        box=(100, 50, 120, 20)),
    # 2e champ de la même ligne, plus loin mais encore dans la tolérance :
    # seul le PLUS PROCHE doit être désigné par le libellé.
    _el("wnd[0]/usr/txtRSYST-LANGU", "GuiTextField", "", changeable=True,
        box=(115, 50, 40, 20)),
    _el("wnd[0]/usr/lblAmount", "GuiLabel", "Amount", box=(300, 20, 60, 20)),
    _el("wnd[0]/usr/txtAMOUNT", "GuiTextField", "42,00", changeable=True,
        box=(300, 45, 60, 20)),
    _el("wnd[0]/tbar[0]/btn[0]", "GuiButton", "Enter", box=(10, 0, 30, 18)),
    _el("wnd[0]/tbar[1]/btn[8]", "GuiButton", "", tooltip="Exécuter (F8)",
        box=(50, 0, 30, 18)),
    # intersection ligne/colonne (grille de champs)
    _el("wnd[0]/usr/lblLigne1", "GuiLabel", "Ligne1", box=(40, 300, 50, 20)),
    _el("wnd[0]/usr/lblQte", "GuiLabel", "Qté", box=(100, 270, 40, 20)),
    _el("wnd[0]/usr/txtQTY-1", "GuiTextField", "", changeable=True,
        box=(100, 300, 40, 20)),
]


def _ids(matches):
    return [m.element.id for m in matches]


GRID = [
    _el("wnd[0]/usr/lblAddress", "GuiLabel", "Address", box=(10, 100, 80, 20)),
    _el("wnd[0]/usr/txtLINE1", "GuiTextField", "", changeable=True, box=(10, 130, 100, 20)),
    _el("wnd[0]/usr/txtLINE2", "GuiTextField", "", changeable=True, box=(10, 160, 100, 20)),
    _el("wnd[0]/usr/txtLINE3", "GuiTextField", "", changeable=True, box=(10, 190, 100, 20)),
    _el("wnd[0]/usr/lblPeriod", "GuiLabel", "Period", box=(10, 400, 60, 20)),
    _el("wnd[0]/usr/txtFROM", "GuiTextField", "", changeable=True, box=(80, 400, 50, 20)),
    _el("wnd[0]/usr/txtTO", "GuiTextField", "", changeable=True, box=(140, 400, 50, 20)),
]


SELECTION_ROW = [
    _el("wnd[0]/usr/txt%_I1_%_APP_%-TEXT", "GuiTextField", "MTEXT",
        box=(27, 197, 231, 24)),
    _el("wnd[0]/usr/txtI1-LOW", "GuiTextField", "", changeable=True,
        box=(283, 197, 151, 24)),
    _el("wnd[0]/usr/txt%_I1_%_APP_%-TO_TEXT", "GuiTextField", "to",
        box=(435, 197, 47, 24)),
    _el("wnd[0]/usr/txtI1-HIGH", "GuiTextField", "", changeable=True,
        box=(483, 197, 151, 24)),
    _el("wnd[0]/usr/btn%_I1_%_APP_%-VALU_PUSH", "GuiButton", "",
        box=(635, 196, 32, 26)),
]


_SELECTION_INPUT_TYPES = ("GuiTextField", "GuiCTextField")


SCOPED = [
    # deux groupes avec le MÊME libellé non-unique ("Amount"), chacun ancré
    # sous un libellé unique différent ("Header" / "Item").
    _el("wnd[0]/usr/lblHeader", "GuiLabel", "Header", box=(10, 500, 60, 20)),
    _el("wnd[0]/usr/lblAmountH", "GuiLabel", "Amount", box=(10, 530, 60, 20)),
    _el("wnd[0]/usr/txtAMOUNTH", "GuiTextField", "", changeable=True, box=(80, 530, 60, 20)),
    _el("wnd[0]/usr/lblItem", "GuiLabel", "Item", box=(300, 500, 60, 20)),
    _el("wnd[0]/usr/lblAmountI", "GuiLabel", "Amount", box=(300, 530, 60, 20)),
    _el("wnd[0]/usr/txtAMOUNTI", "GuiTextField", "", changeable=True, box=(370, 530, 60, 20)),
    # deux champs SANS libellé propre, identifiés par tooltip (l'équivalent F1),
    # chacun proche d'une ancre unique différente.
    _el("wnd[0]/usr/lblSearch", "GuiLabel", "Search", box=(10, 700, 60, 20)),
    _el("wnd[0]/usr/txtNOLABEL", "GuiTextField", "", changeable=True,
        tooltip="Reference number", box=(80, 700, 100, 20)),
    _el("wnd[0]/usr/lblOther", "GuiLabel", "Other", box=(300, 700, 60, 20)),
    _el("wnd[0]/usr/txtNOLABEL2", "GuiTextField", "", changeable=True,
        tooltip="Reference number", box=(370, 700, 100, 20)),
]


SCOPE_FAR = [
    _el("wnd[0]/usr/lblZone", "GuiLabel", "Zone", box=(0, 0, 50, 20)),
    _el("wnd[0]/usr/txtFAR", "GuiTextField", "", changeable=True,
        tooltip="Currency Key", box=(300, 0, 60, 20)),
]


def _lib(elements=LOGIN):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: elements
    return lib


class _NoFindSession:
    """Session sans findById exploitable : _find retourne toujours None."""
