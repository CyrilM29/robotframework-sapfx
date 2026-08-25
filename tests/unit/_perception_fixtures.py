"""Doublures et helpers partages des tests de la perception (ECC et Fiori, fake COM / fake Browser) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import pytest


from pythoncom import com_error


from SapEccLibrary import SapEccLibrary


from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary


from SapFioriLibrary._ui5_js import DUMP_TREE_JS, RESOLVE_ROLE_JS


class FakeChildren:
    def __init__(self, items):
        self._items = items

    @property
    def Count(self):
        return len(self._items)

    def ElementAt(self, index):
        return self._items[index]


class FakeNode:
    def __init__(self, node_id, node_type, text="", children=None):
        self.Id = node_id
        self.Type = node_type
        self.Text = text
        self._children = children

    @property
    def Children(self):
        return FakeChildren(self._children) if self._children is not None else None


class FakeInfo:
    def __init__(self):
        self.Program = "SAPLSMTR_NAVIGATION"
        self.Transaction = "SESSION_MANAGER"
        self.ScreenNumber = 100


class FakeSession:
    def __init__(self, window):
        self.ActiveWindow = window
        self.Info = FakeInfo()
        # None = tout id résolu ; un set = seuls ces ids existent (findById).
        self.found_ids = None

    def findById(self, element_id):
        if self.found_ids is not None and element_id not in self.found_ids:
            raise com_error("élément introuvable : %s" % element_id)
        return FakeNode(element_id, "GuiTextField")


def _ecc_lib():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", "DEVELOPER")
    btn = FakeNode("/app/con[0]/ses[0]/wnd[0]/tbar[0]/btn[0]", "GuiButton", "Enter")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP Easy Access", [txt, btn])
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(win)
    return lib


class StaleChildrenNode(FakeNode):
    """Nœud dont l'accès à .Children lève com_error (nœud COM périmé/disposé)."""

    @property
    def Children(self):
        raise com_error("nœud COM périmé")


def _ecc_lib_actionable():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtRSYST-BNAME",
                   "GuiTextField", "DEVELOPER")
    txt.Changeable = True          # le vrai SAP GUI marque les champs saisissables
    btn = FakeNode("/app/con[0]/ses[0]/wnd[0]/tbar[0]/btn[0]", "GuiButton", "Enter")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow",
                   "SAP Easy Access", [txt, btn])
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(win)
    return lib


def _lib_with_windows(children):
    main = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP Easy Access")
    lib = SapEccLibrary(screenshots_on_error=False)
    session = FakeSession(main)
    session.Children = children
    lib.session = session
    return lib


class ObjectTreeSession(FakeSession):
    """FakeSession exposant GetObjectTree : payload JSON, ou exception à lever."""

    def __init__(self, window, payload):
        super().__init__(window)
        self._payload = payload
        self.object_tree_calls = 0

    def GetObjectTree(self, root_id, properties):
        self.object_tree_calls += 1
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


_TREE_JSON = """
{"children": [{
  "properties": {"Id": "/app/con[0]/ses[0]/wnd[0]", "Type": "GuiMainWindow", "Text": "SAP"},
  "children": [{
    "properties": {"Id": "/app/con[0]/ses[0]/wnd[0]/usr/txtFAST-PATH",
                   "Type": "GuiTextField", "Text": "42", "Changeable": "true",
                   "ScreenLeft": "10", "ScreenTop": "20", "Width": "110", "Height": "22"},
    "children": []
  }]
}]}
"""


def _lib_with_session(session):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = session
    return lib


_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-payload"


class ScreenshotWindow(FakeNode):
    def __init__(self, raw):
        super().__init__("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP")
        self._raw = raw
        self.requested_types = []

    def HardCopyToMemory(self, image_type):
        self.requested_types.append(image_type)
        return self._raw


class FakeBrowser:
    def __init__(self, tree):
        self._tree = tree

    def evaluate_javascript(self, selector, js, arg=None):
        return self._tree if js == DUMP_TREE_JS else None


def _fiori_lib(tree, timeout="2s"):
    lib = SapFioriLibrary(ui5_timeout=timeout)
    browser = FakeBrowser(tree)
    lib._browser = lambda: browser
    return lib


class FlakyTreeBrowser(FakeBrowser):
    """FakeBrowser qui lève une fois avant de répondre (re-rendu Fiori transitoire)."""

    def __init__(self, tree, fail_first=1):
        super().__init__(tree)
        self._fail_remaining = fail_first

    def evaluate_javascript(self, selector, js, arg=None):
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise RuntimeError("Execution context was destroyed")
        return super().evaluate_javascript(selector, js, arg=arg)


_MAP_XML = (
    '<UI5Tree><Page id="page0" title="Home">'
    '<SearchField id="sf0" placeholder="Search" value="LH"/>'
    '<Button id="btn0" text="Go"/>'
    '<Text id="txt0" text="just a label"/>'
    '</Page></UI5Tree>')


class MapFakeBrowser(FakeBrowser):
    """FakeBrowser répondant aussi au résolveur role (contrôle de fraîcheur)
    et enregistrant les actions click/fill."""

    def __init__(self, tree, live_ids=None):
        super().__init__(tree)
        self.live_ids = live_ids          # None = tout contrôle encore rendu
        self.clicks = []
        self.fills = []

    def evaluate_javascript(self, selector, js, arg=None):
        if js == DUMP_TREE_JS:
            return self._tree
        if js == RESOLVE_ROLE_JS:
            import json
            wanted = json.loads(arg).get("id")
            live = self.live_ids is None or wanted in self.live_ids
            return [wanted] if live else []
        return None

    def click(self, selector):
        self.clicks.append(selector)

    def fill_text(self, selector, text):
        self.fills.append((selector, text))


def _fiori_map_lib(live_ids=None, timeout="1s"):
    lib = SapFioriLibrary(ui5_timeout=timeout)
    browser = MapFakeBrowser(_MAP_XML, live_ids)
    lib._browser = lambda: browser
    return lib, browser


def _semantic_lib():
    from sapfx_common.object_tree import ScreenElement
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(None)
    lib._screen_elements = lambda: [
        ScreenElement(id="wnd[0]/usr/lblTable", type="GuiLabel",
                      text="Table Name", left=10, top=20, width=80, height=16),
        ScreenElement(id="wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
                      type="GuiCTextField", text="T000", changeable=True,
                      left=100, top=20, width=120, height=16),
        # assez loin du libellé pour ne pas être aussi son voisin « dessous »
        # (l'ambiguïté serait détectée et la ligne resterait « ? », comme conçu)
        ScreenElement(id="wnd[0]/tbar[1]/btn[31]", type="GuiButton",
                      text="Number of Entries", left=10, top=90, width=30,
                      height=16),
    ]
    return lib


def _annotated_lib(captured):
    import base64
    lib = _semantic_lib()
    lib.get_screenshot_as_base64 = (
        lambda image_format="png": base64.b64encode(b"\x89PNG-raw").decode())
    lib._window_origin = lambda: (5, 10)

    def draw(png, boxes):
        captured["png"] = png
        captured["boxes"] = boxes
        return b"\x89PNG-annotated"

    lib._draw_annotations = draw
    return lib
