"""Doublures et helpers partages des tests des exports du recorder bureau (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import codecs


import importlib.util


import os


import pytest


_SPY_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "sapgui_recorder.py"))


_GUI_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "recorder_gui.py"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spy = _load(_SPY_PATH, "sapgui_recorder")


gui = _load(_GUI_PATH, "recorder_gui")


_VBS_SAMPLE = """\
If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
' commentaire VBS
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nse16"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").text = "T000"
session.findById("wnd[0]/tbar[1]/btn[8]").press
session.findById("wnd[0]/usr/chkFLAG").selected = true
"""


_VBS_ACCENTED = 'session.findById("wnd[0]/usr/txtNAME").text = "Société Générale"'


class _FakeReplayLib:
    def __init__(self):
        self.calls = []

    def run_transaction(self, code):
        self.calls.append(("run_transaction", code))

    def input_text(self, eid, value):
        self.calls.append(("input_text", eid, value))

    def send_vkey(self, *args):
        self.calls.append(("send_vkey",) + args)

    def element_value_should_be(self, eid, value):
        self.calls.append(("check", eid, value))
        if value == "BOOM":
            raise AssertionError("valeur inattendue")


class _LibSansKeywords:
    """Bibliothèque qui ne porte AUCUN des keywords du déroulé (le cas de la
    suite resource-first, dont les steps sont des keywords métier)."""
