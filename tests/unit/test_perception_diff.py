"""Tests du mode diff de perception : primitives pures (``sapfx_common.
perception_diff``) et keywords ``Get Screen Signature``/``Get Ui5 Page Tree``
avec ``mode=diff``. Hors SAP/navigateur — convention #5."""
from sapfx_common.perception_diff import diff_lines, diff_perception, split_xml_lines
from SapEccLibrary.SapEccLibrary import SapEccLibrary
from SapFioriLibrary._ui5_js import DUMP_TREE_JS
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary


# --- primitives pures -----------------------------------------------------------

def test_diff_lines_identical_is_compact_marker():
    lines = ["a", "b"]
    assert diff_lines(lines, lines) == "(no change since the previous perception)"


def test_diff_lines_shows_added_removed_and_summarizes_common():
    previous = ["# screen SE16/0100", "field A", "field B"]
    current = ["# screen SE16/0100", "field A", "field C", "grid"]
    diff = diff_lines(previous, current)
    assert "= 2 unchanged line(s)" in diff
    assert "- field B" in diff
    assert "+ field C" in diff
    assert "+ grid" in diff
    assert "field A" not in diff.replace("unchanged", "")  # jamais répété en clair


def test_diff_perception_first_call_returns_full():
    assert diff_perception(None, "full text") == "full text"


def test_split_xml_lines_one_tag_per_line():
    xml = '<UI5Tree><Page id="p"><Button id="b"/></Page></UI5Tree>'
    lines = split_xml_lines(xml)
    assert lines[0] == "<UI5Tree>"
    assert any(line.startswith("<Button") for line in lines)


def test_diff_perception_xml_mode_diffs_tags():
    old = '<UI5Tree><Button id="a" text="Go"/></UI5Tree>'
    new = '<UI5Tree><Button id="a" text="Stop"/></UI5Tree>'
    diff = diff_perception(old, new, xml=True)
    assert '- <Button id="a" text="Go"/>' in diff
    assert '+ <Button id="a" text="Stop"/>' in diff


# --- Get Screen Signature mode=diff ----------------------------------------------

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
    Program = "SAPLSE16"
    Transaction = "SE16"
    ScreenNumber = 100


class FakeSession:
    def __init__(self, window):
        self.ActiveWindow = window
        self.Info = FakeInfo()


def _ecc_with_fields(*fields):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(
        FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", list(fields)))
    return lib


def test_screen_signature_diff_first_call_full_then_differential():
    lib = _ecc_with_fields(FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA",
                                    "GuiTextField", ""))
    first = lib.get_screen_signature(mode="diff")
    assert first.startswith("# screen")                # premier appel : vue complète
    # l'écran gagne un champ -> le diff ne montre QUE le champ apparu
    lib.session = FakeSession(FakeNode(
        "/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "",
        [FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA", "GuiTextField", ""),
         FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtB", "GuiTextField", "")]))
    diff = lib.get_screen_signature(mode="diff")
    assert "+ * wnd[0]/usr/txtB" in diff
    assert "unchanged line(s)" in diff
    assert "txtA" not in diff                          # inchangé -> résumé, pas répété


def test_screen_signature_full_mode_still_updates_the_baseline():
    lib = _ecc_with_fields(FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtA",
                                    "GuiTextField", ""))
    lib.get_screen_signature()                          # full : pose la baseline
    assert lib.get_screen_signature(mode="diff") == \
        "(no change since the previous perception)"


# --- Get Ui5 Page Tree mode=diff --------------------------------------------------

class FakeBrowser:
    def __init__(self, trees):
        self._trees = list(trees)

    def evaluate_javascript(self, selector, js, arg=None):
        if js == DUMP_TREE_JS:
            return self._trees.pop(0) if len(self._trees) > 1 else self._trees[0]
        return None


def test_page_tree_diff_first_full_then_differential():
    old = '<UI5Tree><Button id="a" text="Go"/></UI5Tree>'
    new = '<UI5Tree><Button id="a" text="Go"/><Dialog id="d"/></UI5Tree>'
    lib = SapFioriLibrary(ui5_timeout="1s")
    browser = FakeBrowser([old, new])
    lib._browser = lambda: browser
    assert lib.get_ui5_page_tree(mode="diff") == old    # premier appel : complet
    diff = lib.get_ui5_page_tree(mode="diff")
    assert '+ <Dialog id="d"/>' in diff
    assert "unchanged" in diff


# --- diff intelligent : appariement des renommages (pair_renames) -----------------

SIG_OLD = [
    "# screen SAPLMEGUI/ME21N/0013",
    "* wnd[0]/usr/subSUB0:SAPLMEGUI:0013/ctxtMEPO_TOPLINE-BSART\tGuiCTextField\tNB",
    "  wnd[0]/usr/lblHeader\tGuiLabel\tEn-tête",
]
# le sous-écran est renuméroté 0013 -> 0015 : l'id casse, le terminal survit
SIG_NEW = [
    "# screen SAPLMEGUI/ME21N/0015",
    "* wnd[0]/usr/subSUB0:SAPLMEGUI:0015/ctxtMEPO_TOPLINE-BSART\tGuiCTextField\tNB",
    "  wnd[0]/usr/lblHeader\tGuiLabel\tEn-tête",
]


def test_pair_renames_apparie_un_sous_ecran_renumerote():
    diff = diff_lines(SIG_OLD, SIG_NEW, pair_renames=True)
    assert "~ wnd[0]/usr/subSUB0:SAPLMEGUI:0013/ctxtMEPO_TOPLINE-BSART -> " \
           "wnd[0]/usr/subSUB0:SAPLMEGUI:0015/ctxtMEPO_TOPLINE-BSART" in diff
    assert "similarité" in diff
    # les lignes appariées ne réapparaissent PAS en -/+
    assert "- * wnd[0]/usr/subSUB0" not in diff


def test_pair_renames_meme_id_texte_change_est_un_changement_de_valeur():
    old = ["* wnd[0]/usr/txtA\tGuiTextField\tT000"]
    new = ["* wnd[0]/usr/txtA\tGuiTextField\tT001"]
    diff = diff_lines(old, new, pair_renames=True)
    assert "~ wnd[0]/usr/txtA" in diff
    assert "texte : 'T000' -> 'T001'" in diff


def test_pair_renames_ids_sans_rapport_restent_en_moins_plus():
    old = ["  wnd[0]/tbar[1]/btn[31]\tGuiButton\tNumber of Entries"]
    new = ["* wnd[0]/usr/ctxtDATABROWSE-TABLENAME\tGuiCTextField\t"]
    diff = diff_lines(old, new, pair_renames=True)
    assert "- " in diff and "+ " in diff and "~ " not in diff


def test_pair_renames_ignore_les_lignes_hors_format():
    # l'entête (# screen ...) n'a pas 3 colonnes : jamais appariée
    diff = diff_lines(["# screen A/B/1"], ["# screen A/B/2"], pair_renames=True)
    assert "- # screen A/B/1" in diff
    assert "+ # screen A/B/2" in diff


def test_keyword_diff_pair_renames_active_l_appariement():
    lib = _ecc_with_fields(FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtCHAMP-A",
                                    "GuiTextField", ""))
    lib.get_screen_signature(mode="diff")
    lib.session = FakeSession(FakeNode(
        "/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "",
        [FakeNode("/app/con[0]/ses[0]/wnd[0]/usr/txtCHAMP-B",
                  "GuiTextField", "")]))
    diff = lib.get_screen_signature(mode="diff", pair_renames=True)
    assert "~ wnd[0]/usr/txtCHAMP-A -> wnd[0]/usr/txtCHAMP-B" in diff
