"""Doublures et helpers partages des tests du recorder bureau (modele objet SAP GUI Scripting factice) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import datetime


import importlib.util


import json


import os


import pytest


_SPY_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "sapgui_recorder.py"))


def _load_spy():
    spec = importlib.util.spec_from_file_location("sapgui_recorder", _SPY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spy = _load_spy()


import recorder_capture as rcap   # noqa: E402


import recorder_com as rcom       # noqa: E402


import recorder_poll as rpoll     # noqa: E402


class FakeChildren:
    """Collection SAP GUI : expose `Count` et `ElementAt(i)`."""
    def __init__(self, items):
        self._items = items

    @property
    def Count(self):
        return len(self._items)

    def ElementAt(self, index):
        return self._items[index]


class FakeNode:
    """Nœud GUI : `Id`/`Type`/`Text` + `Children` (None pour une feuille)."""
    def __init__(self, node_id, node_type, text="", children=None):
        self.Id = node_id
        self.Type = node_type
        self.Text = text
        self._children = children

    @property
    def Children(self):
        return FakeChildren(self._children) if self._children is not None else None


def _sample_engine():
    """engine → connexion → session → fenêtre → (champ texte, bouton)."""
    btn = FakeNode("wnd[0]/tbar[0]/btn[0]", "GuiButton")
    txt = FakeNode("wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", "")
    win = FakeNode("wnd[0]", "GuiMainWindow", "SAP Easy Access", [txt, btn])
    session = FakeNode("ses[0]", "GuiSession", "", [win])
    connection = FakeNode("con[0]", "GuiConnection", "", [session])
    return FakeNode("app", "GuiApplication", "", [connection]), session


class FakeSessionFind:
    """Session exposant findById(id, flag) + Visualize sur les éléments trouvés."""
    def __init__(self, ids):
        self._ids = ids               # {id: FakeVisualizable}

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self._ids:
            return self._ids[element_id]
        if raise_on_missing:
            raise spy.com_error("not found")
        return None


class FakeVisualizable:
    def __init__(self, eid, etype="GuiTextField", text=""):
        self.Id, self.Type, self.Text = eid, etype, text
        self.visualized = []

    def Visualize(self, on_off):
        self.visualized.append(on_off)
        return True


def _engine_with_session(session):
    conn = FakeNode("con[0]", "GuiConnection", "", [session])
    return FakeNode("app", "GuiApplication", "", [conn])


class FakeFocusSession:
    """Session dont ActiveWindow.GuiFocus retourne l'élément focalisé courant."""
    def __init__(self, focus):
        self._focus = focus

    @property
    def ActiveWindow(self):
        parent = self

        class _Win:
            GuiFocus = parent._focus
        return _Win()


class FakeGeoNode:
    """Nœud avec géométrie écran (ScreenLeft/Top/Width/Height) + Visualize + Children.

    ``rect=None`` simule un contrôle sans géométrie (menu…) : l'accès aux propriétés
    lève ``AttributeError``, exactement ce que ``element_rect`` doit absorber."""
    def __init__(self, node_id, node_type, rect=None, text="", children=None):
        self.Id, self.Type, self.Text = node_id, node_type, text
        self._children = children
        self.visualized = []
        if rect is not None:
            self.ScreenLeft, self.ScreenTop, self.Width, self.Height = rect

    @property
    def Children(self):
        return FakeChildren(self._children) if self._children is not None else None

    def Visualize(self, on_off):
        self.visualized.append(on_off)
        return True


def _geo_engine():
    """Fenêtre 100×100 contenant un champ (10,10,40,20) et un bouton (60,10,30,20)."""
    field = FakeGeoNode("wnd[0]/usr/txtF", "GuiTextField", (10, 10, 40, 20))
    button = FakeGeoNode("wnd[0]/tbar[0]/btn[0]", "GuiButton", (60, 10, 30, 20))
    win = FakeGeoNode("wnd[0]", "GuiMainWindow", (0, 0, 100, 100), children=[field, button])
    session = FakeGeoNode("ses[0]", "GuiSession", None, children=[win])
    session.ActiveWindow = win   # iter_active_window_elements ne regarde que celle-ci
    conn = FakeGeoNode("con[0]", "GuiConnection", None, children=[session])
    engine = FakeGeoNode("app", "GuiApplication", None, children=[conn])
    return engine, field, button, win


class FakeInfo:
    def __init__(self, program="SAPMSSY0", transaction="SE16", screen="0500"):
        self.Program, self.Transaction, self.ScreenNumber = program, transaction, screen


class FakeRecSession:
    """Session minimale pour le record : ActiveWindow, Info, okcode via findById."""
    def __init__(self, window=None, info=None, okcd=""):
        self._window = window
        self.Info = info or FakeInfo()
        self._okcd = FakeNode("wnd[0]/tbar[0]/okcd", "GuiOkCodeField", okcd)

    @property
    def ActiveWindow(self):
        return self._window

    def findById(self, element_id, raise_on_missing=True):
        if element_id == "wnd[0]/tbar[0]/okcd":
            return self._okcd
        if raise_on_missing:
            raise spy.com_error("not found")
        return None
