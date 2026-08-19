"""Amorçage des tests pour que la logique Python pure soit testable sans installation SAP.

SapEccLibrary dépend de `robot.*` et des modules COM pywin32. Pour les tests
unitaires, il n'est pas nécessaire d'avoir un vrai serveur SAP ni même Robot
Framework : seulement la logique Python déterministe (analyse des délais,
boucles de relance, résolution des titres de grille). Ce conftest installe des
substituts légers pour tous les modules manquants, afin que `pytest` tourne sur
un interpréteur nu. Lorsque les vrais paquets sont installés
(``pip install -r requirements.txt``), les stubs sont ignorés et les modules
authentiques sont utilisés.
"""
import os
import sys
import types

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Les scripts d'outillage partagent ``scripts/_common.py`` (sortie console,
# lecture de version). Lancés en ligne de commande, ils le trouvent seuls
# (``sys.path[0]`` = leur répertoire) ; chargés par chemin dans les tests, non.
_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


def _ensure(name, factory):
    if name not in sys.modules:
        try:
            __import__(name)
        except ImportError:
            sys.modules[name] = factory()


def _make_pythoncom():
    mod = types.ModuleType("pythoncom")
    mod.com_error = type("com_error", (Exception,), {})
    return mod


def _make_win32com():
    pkg = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")
    client.Dispatch = lambda *a, **k: None
    pkg.client = client
    sys.modules["win32com.client"] = client
    return pkg


def _make_robot():
    robot = types.ModuleType("robot")
    robot.__path__ = []  # marquer comme paquet afin que les imports de sous-modules se résolvent

    libraries = types.ModuleType("robot.libraries")
    libraries.__path__ = []  # marquer comme paquet
    screenshot_mod = types.ModuleType("robot.libraries.Screenshot")

    class _Screenshot:
        def take_screenshot(self, *a, **k):
            return None

        def set_screenshot_directory(self, *a, **k):
            return None

    screenshot_mod.Screenshot = _Screenshot
    libraries.Screenshot = screenshot_mod

    builtin_mod = types.ModuleType("robot.libraries.BuiltIn")

    class _BuiltIn:
        def get_library_instance(self, *a, **k):
            return None

    builtin_mod.BuiltIn = _BuiltIn
    libraries.BuiltIn = builtin_mod

    sys.modules["robot.libraries"] = libraries
    sys.modules["robot.libraries.Screenshot"] = screenshot_mod
    sys.modules["robot.libraries.BuiltIn"] = builtin_mod
    robot.libraries = libraries

    api = types.ModuleType("robot.api")
    api.__path__ = []
    logger = types.ModuleType("robot.api.logger")
    logger.info = lambda *a, **k: None
    logger.warn = lambda *a, **k: None
    api.logger = logger

    types_mod = types.ModuleType("robot.api.types")

    class _Secret:
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return "<secret>"

    types_mod.Secret = _Secret
    api.types = types_mod

    utils = types.ModuleType("robot.utils")

    def timestr_to_secs(value):
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().lower()
        for suffix, factor in (("ms", 0.001), ("s", 1.0), ("min", 60.0), ("m", 60.0)):
            if text.endswith(suffix):
                return float(text[: -len(suffix)].strip()) * factor
        return float(text)

    utils.timestr_to_secs = timestr_to_secs

    sys.modules["robot.api"] = api
    sys.modules["robot.api.logger"] = logger
    sys.modules["robot.api.types"] = types_mod
    sys.modules["robot.utils"] = utils
    robot.api = api
    robot.utils = utils
    return robot


_ensure("pythoncom", _make_pythoncom)
_ensure("win32com", _make_win32com)
_ensure("robot", _make_robot)
