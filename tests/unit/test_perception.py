"""Tests off-SAP des keywords de perception (convention #5 du CLAUDE.md).

* ECC : `Get Screen Signature` sur une session COM simulée.
* Fiori : `Get Ui5 Page Tree` avec une doublure de la bibliothèque Browser.

Ces keywords alimentent le plugin rf-mcp (``integrations/robotmcp``) : ils donnent
à un agent une vue de l'écran. On valide ici la logique Python (parcours, format,
sondage/erreur), la validation live restant du ressort des smokes.
"""
import pytest
from pythoncom import com_error

from SapEccLibrary import SapEccLibrary
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import DUMP_TREE_JS, RESOLVE_ROLE_JS


# --- ECC : Get Screen Signature ----------------------------------------------

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


def test_screen_signature_entete_porte_l_identite_d_ecran():
    sig = _ecc_lib().get_screen_signature()
    assert sig.splitlines()[0] == "# screen SAPLSMTR_NAVIGATION/SESSION_MANAGER/100"


def test_screen_signature_ids_relatifs_a_la_session():
    sig = _ecc_lib().get_screen_signature()
    # préfixe /app/con[0]/ses[0]/ retiré -> id collable dans un test
    assert "wnd[0]/usr/txtRSYST-BNAME" in sig
    assert "/app/con[0]" not in sig


def test_screen_signature_marque_les_champs_editables():
    lines = _ecc_lib().get_screen_signature().splitlines()
    field = next(line for line in lines if "txtRSYST-BNAME" in line)
    button = next(line for line in lines if "btn[0]" in line)
    assert field.startswith("* ")       # GuiTextField -> éditable
    assert button.startswith("  ")       # GuiButton -> non éditable


def test_screen_signature_defensif_si_pas_de_fenetre():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(None)
    sig = lib.get_screen_signature()
    assert sig.startswith("# screen")    # entête seule, pas d'exception


class StaleChildrenNode(FakeNode):
    """Nœud dont l'accès à .Children lève com_error (nœud COM périmé/disposé)."""

    @property
    def Children(self):
        raise com_error("nœud COM périmé")


def test_screen_signature_defensif_si_children_leve_com_error():
    # un enfant dont .Children est périmé ne doit pas faire planter tout le
    # parcours : on garde sa propre ligne et on arrête simplement sa descente.
    stale = StaleChildrenNode("/app/con[0]/ses[0]/wnd[0]/usr/subScreen", "GuiContainerShell")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP Easy Access", [stale])
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(win)
    sig = lib.get_screen_signature()
    assert "usr/subScreen" in sig
    assert sig.startswith("# screen")


# --- ECC : carte numérotée + action par référence (@N) -------------------------
# Boucle perception -> action façon « map / @e1 » (inspiration Vibium) : la
# carte numérote les cibles actionnables, l'agent agit par numéro, la
# résolution re-vérifie l'écran — jamais d'action sur une référence périmée.

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


def test_get_screen_map_numerote_les_cibles_actionnables():
    lib = _ecc_lib_actionable()
    lines = lib.get_screen_map().splitlines()
    assert lines[0].startswith("# screen ")
    assert lines[1].startswith("@1\t")
    assert "txtRSYST-BNAME" in lines[1]      # champ saisissable = 1re cible
    assert lines[2].startswith("@2\t")
    assert "btn[0]" in lines[2]              # bouton = 2e cible
    assert len(lines) == 3                    # la fenêtre elle-même n'est pas une cible


def test_resolve_screen_ref_retourne_l_id_et_accepte_le_prefixe_arobase():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    assert lib.resolve_screen_ref("1") == "wnd[0]/usr/txtRSYST-BNAME"
    assert lib.resolve_screen_ref("@2") == "wnd[0]/tbar[0]/btn[0]"


def test_resolve_screen_ref_sans_perception_erreur_actionnable():
    lib = _ecc_lib_actionable()
    with pytest.raises(AssertionError, match="Get Screen Map"):
        lib.resolve_screen_ref("1")


def test_resolve_screen_ref_inconnue_liste_la_plage_disponible():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    with pytest.raises(AssertionError, match=r"@1\.\.@2"):
        lib.resolve_screen_ref("7")


def test_resolve_screen_ref_refuse_un_ecran_qui_a_change():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    lib.session.Info.Transaction = "SE16"     # navigation depuis la perception
    with pytest.raises(AssertionError, match="re-percevoir"):
        lib.resolve_screen_ref("1")


def test_resolve_screen_ref_refuse_un_element_disparu():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    lib.session.found_ids = set()             # même écran, cible retirée
    with pytest.raises(AssertionError, match="n'existe plus"):
        lib.resolve_screen_ref("1")


def test_click_et_fill_screen_ref_deleguent_aux_keywords_deterministes():
    lib = _ecc_lib_actionable()
    lib.get_screen_map()
    calls = []
    lib.click_element = lambda eid: calls.append(("click", eid))
    lib.input_text = lambda eid, value: calls.append(("fill", eid, value))
    assert lib.click_screen_ref("@2") == "wnd[0]/tbar[0]/btn[0]"
    assert lib.fill_screen_ref("1", "T000") == "wnd[0]/usr/txtRSYST-BNAME"
    assert calls == [("click", "wnd[0]/tbar[0]/btn[0]"),
                     ("fill", "wnd[0]/usr/txtRSYST-BNAME", "T000")]


# --- ECC : Get Open Windows (pile de fenêtres / détection de modal) -----------
# Le piège SESSION_MANAGER constaté live : Run Transaction rapporte un succès
# alors qu'un modal d'erreur est resté affiché — ce keyword le rend visible.

def _lib_with_windows(children):
    main = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP Easy Access")
    lib = SapEccLibrary(screenshots_on_error=False)
    session = FakeSession(main)
    session.Children = children
    lib.session = session
    return lib


def test_get_open_windows_liste_la_pile_et_marque_le_modal():
    main = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP Easy Access")
    popup = FakeNode("/app/con[0]/ses[0]/wnd[1]", "GuiModalWindow",
                     "Cannot start transaction ")
    windows = _lib_with_windows(FakeChildren([main, popup])).get_open_windows()
    assert windows == [
        {"id": "wnd[0]", "type": "GuiMainWindow",
         "title": "SAP Easy Access", "modal": False},
        {"id": "wnd[1]", "type": "GuiModalWindow",
         "title": "Cannot start transaction", "modal": True},
    ]


def test_get_open_windows_defensif_sans_session_lisible():
    class BrokenSession:
        @property
        def Children(self):
            raise com_error("session fermée")

    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = BrokenSession()
    assert lib.get_open_windows() == []


def test_get_open_windows_ignore_une_fenetre_illisible():
    class BrokenChildren(FakeChildren):
        def ElementAt(self, index):
            if index == 1:
                raise com_error("fenêtre disposée")
            return super().ElementAt(index)

    main = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "OK")
    ghost = FakeNode("/app/con[0]/ses[0]/wnd[9]", "GuiModalWindow", "?")
    windows = _lib_with_windows(BrokenChildren([main, ghost])).get_open_windows()
    assert [w["id"] for w in windows] == ["wnd[0]"]


# --- ECC : chemin rapide GetObjectTree ----------------------------------------

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


def test_screen_signature_utilise_getobjecttree_quand_disponible():
    # la fenêtre COM n'a AUCUN enfant : si txtFAST-PATH apparaît, il vient
    # nécessairement du JSON GetObjectTree, pas de la marche COM.
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [])
    lib = _lib_with_session(ObjectTreeSession(win, _TREE_JSON))
    sig = lib.get_screen_signature()
    assert "wnd[0]/usr/txtFAST-PATH" in sig
    assert "/app/con[0]" not in sig          # ids relativisés aussi sur ce chemin
    field = next(line for line in sig.splitlines() if "txtFAST-PATH" in line)
    assert field.startswith("* ")            # GuiTextField -> éditable, comme avant


def test_screen_signature_format_identique_sur_les_deux_chemins():
    # même écran perçu via GetObjectTree et via la marche COM -> même signature
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtFAST-PATH", "GuiTextField", "42")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    par_marche = _lib_with_session(FakeSession(win)).get_screen_signature()
    par_arbre = _lib_with_session(ObjectTreeSession(
        FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", []),
        _TREE_JSON)).get_screen_signature()
    assert par_arbre == par_marche


def test_attributeerror_marque_l_api_absente_et_ne_retente_pas():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    session = ObjectTreeSession(win, AttributeError("GetObjectTree absent"))
    lib = _lib_with_session(session)
    assert "txtA" in lib.get_screen_signature()   # repli marche COM
    lib.get_screen_signature()
    assert session.object_tree_calls == 1          # pas de nouvel essai


def test_com_error_replie_ponctuellement_mais_retente_au_prochain_appel():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    session = ObjectTreeSession(win, com_error("transitoire"))
    lib = _lib_with_session(session)
    assert "txtA" in lib.get_screen_signature()
    lib.get_screen_signature()
    assert session.object_tree_calls == 2          # retenté : l'erreur était transitoire


def test_json_invalide_ou_vide_replie_sur_la_marche():
    txt = FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", "x")
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [txt])
    assert "txtA" in _lib_with_session(
        ObjectTreeSession(win, "pas du json {")).get_screen_signature()
    assert "txtA" in _lib_with_session(
        ObjectTreeSession(win, '{"children": []}')).get_screen_signature()


def test_include_geometry_ajoute_une_4e_colonne_optionnelle():
    win = FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP", [])
    lib = _lib_with_session(ObjectTreeSession(win, _TREE_JSON))
    avec = lib.get_screen_signature(include_geometry=True)
    field = next(line for line in avec.splitlines() if "txtFAST-PATH" in line)
    assert field.endswith("\t@10,20 110x22")
    # par défaut : format 3 colonnes inchangé (contrat du filtrage rf-mcp)
    sans = lib.get_screen_signature()
    assert "@10,20" not in sans


# --- ECC : screenshot en mémoire (HardCopyToMemory) ---------------------------

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-payload"


class ScreenshotWindow(FakeNode):
    def __init__(self, raw):
        super().__init__("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "SAP")
        self._raw = raw
        self.requested_types = []

    def HardCopyToMemory(self, image_type):
        self.requested_types.append(image_type)
        return self._raw


def test_get_screenshot_as_base64_retourne_les_octets_du_buffer():
    import base64
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(ScreenshotWindow(_PNG_BYTES))
    b64 = lib.get_screenshot_as_base64()
    assert base64.b64decode(b64) == _PNG_BYTES


def test_get_screenshot_accepte_un_safearray_de_tuples_d_entiers():
    import base64
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(ScreenshotWindow(tuple(_PNG_BYTES)))
    assert base64.b64decode(lib.get_screenshot_as_base64()) == _PNG_BYTES


def test_get_screenshot_echoue_clairement_si_l_api_est_absente():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow"))
    with pytest.raises(AssertionError, match="HardCopyToMemory"):
        lib.get_screenshot_as_base64()


def test_log_screenshot_incruste_un_data_uri_du_mime_reel(monkeypatch):
    from SapEccLibrary.keywords import _perception
    logged = []
    monkeypatch.setattr(_perception.logger, "info",
                        lambda msg, **kw: logged.append((msg, kw)), raising=False)
    lib = SapEccLibrary(screenshots_on_error=False)
    # buffer JPEG alors que png était demandé : le MIME incrusté suit les magic bytes
    lib.session = FakeSession(ScreenshotWindow(b"\xff\xd8\xff" + b"jpeg-payload"))
    assert lib.log_screenshot("après validation") == "image/jpeg"
    message, kwargs = logged[0]
    assert "data:image/jpeg;base64," in message
    assert "après validation" in message
    assert kwargs.get("html") is True


# --- Fiori : Get Ui5 Page Tree -----------------------------------------------

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


def test_get_ui5_page_tree_retourne_le_xml_du_bundle():
    xml = '<UI5Tree><Button id="__btn0" controlType="sap.m.Button" text="Go"/></UI5Tree>'
    assert _fiori_lib(xml).get_ui5_page_tree() == xml


def test_get_ui5_page_tree_leve_si_pas_d_ui5():
    # bundle renvoie None hors application UI5 -> sondage épuisé -> AssertionError,
    # qui nomme la voie de diagnostic (erreur auto-corrigible).
    with pytest.raises(AssertionError, match="No UI5 control tree") as err:
        _fiori_lib(None, timeout="0.1s").get_ui5_page_tree()
    assert "Get Page Composition" in str(err.value)


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


def test_get_ui5_page_tree_survit_a_une_exception_js_transitoire():
    xml = '<UI5Tree><Button id="__btn0"/></UI5Tree>'
    lib = SapFioriLibrary(ui5_timeout="2s")
    browser = FlakyTreeBrowser(xml, fail_first=1)   # UNE instance : l'état du retry compte
    lib._browser = lambda: browser
    assert lib.get_ui5_page_tree() == xml


# --- Fiori : carte numérotée + action par référence (@N) -----------------------
# Miroir du canal ECC : la carte numérote les cibles actionnables de l'arbre
# UI5, l'action passe par le numéro, la fraîcheur est re-vérifiée au registre.

_MAP_XML = (
    '<UI5Tree><Page id="page0" title="Home">'
    '<SearchField id="sf0" placeholder="Search" value="LH"/>'
    '<Button id="btn0" text="Go"/>'
    '<Text id="txt0" text="just a label"/>'
    '</Page></UI5Tree>')


def test_ui5_page_map_pure_numerote_et_marque_les_saisissables():
    from SapFioriLibrary._ui5_runtime import ui5_page_map
    lines, refs = ui5_page_map(_MAP_XML)
    assert refs == {"1": "sf0", "2": "btn0"}          # Page/Text hors carte
    assert lines[0] == "@1\t* Search\tsf0\tSearchField\t= LH"
    assert lines[1] == "@2\t  Go\tbtn0\tButton"


def test_ui5_page_map_pure_include_types_et_xml_invalide():
    from SapFioriLibrary._ui5_runtime import ui5_page_map
    lines, refs = ui5_page_map(_MAP_XML, include_types="Text")
    assert refs == {"1": "txt0"}
    assert lines[0].startswith("@1\t  just a label\t")
    with pytest.raises(ValueError, match="XML invalide"):
        ui5_page_map("<pas fermé")


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


def test_get_ui5_page_map_numerote_et_enregistre_les_references():
    lib, _browser = _fiori_map_lib()
    lines = lib.get_ui5_page_map().splitlines()
    assert lines[0] == "# ui5 page map — 2 actionable target(s)"
    assert lines[1].startswith("@1\t* Search\tsf0")
    assert lib._ui5_refs == {"1": "sf0", "2": "btn0"}
    assert lib._last_page_tree is None    # la mémoire du mode=diff est intacte


def test_resolve_ui5_ref_selecteur_scope_frame_et_prefixe_arobase():
    lib, _browser = _fiori_map_lib()
    lib.get_ui5_page_map()
    assert lib.resolve_ui5_ref("@2") == 'css=[id="btn0"]'
    lib._ui5_frame = "iframe#app"
    assert lib.resolve_ui5_ref("1") == 'iframe#app >>> css=[id="sf0"]'


def test_resolve_ui5_ref_erreurs_actionnables():
    lib, _browser = _fiori_map_lib()
    with pytest.raises(AssertionError, match="Get Ui5 Page Map"):
        lib.resolve_ui5_ref("1")                      # aucune carte relevée
    lib.get_ui5_page_map()
    with pytest.raises(AssertionError, match=r"@1\.\.@2"):
        lib.resolve_ui5_ref("9")                      # numéro hors carte


def test_resolve_ui5_ref_refuse_un_controle_plus_rendu():
    lib, browser = _fiori_map_lib()
    lib.get_ui5_page_map()
    browser.live_ids = set()                          # page naviguée/redessinée
    with pytest.raises(AssertionError, match="re-percevoir"):
        lib.resolve_ui5_ref("1")


def test_click_et_fill_ui5_ref_deleguent_a_browser():
    lib, browser = _fiori_map_lib()
    lib.get_ui5_page_map()
    assert lib.click_ui5_ref("@2") == 'css=[id="btn0"]'
    assert browser.clicks == ['css=[id="btn0"]']
    assert lib.fill_ui5_ref("1", "T000") == 'css=[id="sf0"]'
    # le remplissage vise l'élément interne du contrôle composite, jamais sa racine
    assert browser.fills == [('css=[id="sf0"] input, [id="sf0"] textarea', "T000")]


# --- ECC : Get Screen Signature mode=semantic ----------------------------------

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


def test_mode_semantic_vue_formulaire_libelle_vers_id():
    sig = _semantic_lib().get_screen_signature(mode="semantic")
    assert sig.splitlines()[0].startswith("# screen")
    champ = next(line for line in sig.splitlines() if "DATABROWSE" in line)
    assert champ.startswith("* Table Name\t")
    assert champ.endswith("= T000")
    bouton = next(line for line in sig.splitlines() if "btn[31]" in line)
    assert bouton.startswith("  Number of Entries\t")


def test_mode_semantic_ne_touche_pas_la_memoire_du_diff():
    lib = _semantic_lib()
    lib.get_screen_signature()                    # pose la baseline du diff
    lib.get_screen_signature(mode="semantic")     # autre lentille, pas un état
    assert lib.get_screen_signature(mode="diff") == \
        "(no change since the previous perception)"


# --- ECC : screenshot annoté (Set-of-Mark) ---------------------------------------

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


def test_annotated_screenshot_legende_et_boites_relatives_fenetre():
    import base64
    captured = {}
    shot = _annotated_lib(captured).get_annotated_screenshot()
    # cibles actionnables seulement : le champ + le bouton, pas le libellé
    assert shot["legend"] == {
        "1": "wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
        "2": "wnd[0]/tbar[1]/btn[31]"}
    # géométrie translatée de l'origine fenêtre (5, 10)
    assert captured["boxes"][0] == ("1", 95, 10, 120, 16)
    assert captured["boxes"][1] == ("2", 5, 80, 30, 16)
    assert base64.b64decode(shot["image"]) == b"\x89PNG-annotated"
    assert shot["mime"] == "image/png"


def test_annotated_screenshot_filtre_de_types_explicite():
    captured = {}
    shot = _annotated_lib(captured).get_annotated_screenshot(
        include_types="GuiLabel")
    assert list(shot["legend"].values()) == ["wnd[0]/usr/lblTable"]


def test_log_annotated_screenshot_retourne_la_legende():
    captured = {}
    legend = _annotated_lib(captured).log_annotated_screenshot("demo")
    assert legend["1"] == "wnd[0]/usr/ctxtDATABROWSE-TABLENAME"


def test_annotated_screenshot_enregistre_les_references_actionnables():
    # Le numéro lu sur l'image Set-of-Mark est directement actionnable : la
    # légende alimente la même table @N que Get Screen Map.
    captured = {}
    lib = _annotated_lib(captured)
    lib.get_annotated_screenshot()
    assert lib.resolve_screen_ref("@2") == "wnd[0]/tbar[1]/btn[31]"


def test_annotated_screenshot_ignore_les_geometries_negatives():
    # largeur négative remontée par le vrai SAP GUI (constaté live A4H) : la
    # boîte est écartée au lieu de casser le dessin Pillow.
    from sapfx_common.object_tree import ScreenElement
    captured = {}
    lib = _annotated_lib(captured)
    lib._screen_elements = lambda: [
        ScreenElement(id="wnd[0]/usr/txtOK", type="GuiTextField",
                      changeable=True, left=100, top=20, width=120, height=16),
        ScreenElement(id="wnd[0]/usr/txtKO", type="GuiTextField",
                      changeable=True, left=100, top=40, width=-1, height=16),
    ]
    shot = lib.get_annotated_screenshot()
    assert list(shot["legend"].values()) == ["wnd[0]/usr/txtOK"]
