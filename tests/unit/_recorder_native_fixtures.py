"""Doublures et helpers partages des tests du moteur record natif (commandes Change factices) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import importlib.util


import os


_SPY_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "sapgui_recorder.py"))


def _load_spy():
    spec = importlib.util.spec_from_file_location("sapgui_recorder_native", _SPY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spy = _load_spy()


class FakeInfo:
    def __init__(self, recording_disabled=False):
        self.ScriptingModeRecordingDisabled = recording_disabled


class FakeSession:
    def __init__(self, recording_disabled=False):
        self.Id = "/app/con[0]/ses[0]"
        self.Type = "GuiSession"
        self.Text = ""
        self.Children = None
        self.Info = FakeInfo(recording_disabled)
        self.Record = False


class FakeComponent:
    def __init__(self, eid, etype, text=""):
        self.Id = "/app/con[0]/ses[0]/" + eid
        self.Type = etype
        self.Text = text


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _engine_with(session):
    class _Children:
        def __init__(self, items):
            self._items = items

        @property
        def Count(self):
            return len(self._items)

        def ElementAt(self, index):
            return self._items[index]

    class _Node:
        def __init__(self, children):
            self.Children = _Children(children)

    return _Node([_Node([session])])


def _fake_advise(handlers, connection):
    """Fabrique un `_advise` factice : capture les handlers passés par la boucle
    (mêmes noms que `advise_session_events`) et retourne `connection`."""
    def advise(session, on_change=None, on_hit=None, on_focus_changed=None):
        handlers.update(change=on_change, hit=on_hit, focus=on_focus_changed)
        return connection
    return advise


from sapfx_common.object_tree import ScreenElement  # noqa: E402


def _sem(eid, etype, text="", tooltip="", changeable=False, box=None):
    left, top, width, height = box if box else (None, None, None, None)
    return ScreenElement(id=eid, type=etype, text=text, tooltip=tooltip,
                         changeable=changeable, left=left, top=top,
                         width=width, height=height)


_SE16_ELEMENTS = [
    _sem("wnd[0]/usr/lblTable", "GuiLabel", "Table Name", box=(10, 20, 90, 20)),
    _sem("wnd[0]/usr/ctxtDATABROWSE-TABLENAME", "GuiCTextField", "SFLIGHT",
         changeable=True, box=(110, 20, 120, 20)),
    _sem("wnd[0]/tbar[1]/btn[8]", "GuiButton", "", tooltip="Execute (F8)",
         box=(10, 0, 30, 18)),
    _sem("wnd[0]/usr/chkONLY", "GuiCheckBox", "", changeable=True,
         box=(110, 50, 20, 20)),
    _sem("wnd[0]/usr/lblOnly", "GuiLabel", "Selected entries only",
         box=(10, 50, 90, 20)),
]


class _ShotWindow:
    def __init__(self, raw):
        self._raw = raw
        self.Id = "/app/con[0]/ses[0]/wnd[0]"

    def HardCopyToMemory(self, image_type):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


class _ShotSession:
    def __init__(self, window):
        self.ActiveWindow = window
