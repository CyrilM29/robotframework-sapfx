"""Doublures et helpers partages des tests du recorder web (bundle __SAPFX + listener) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import json


import os


from SapFioriLibrary._ui5_js import BUNDLE, spy_snippet


_RECORDER_WEB = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder_web"))


SNIPPET = spy_snippet()
