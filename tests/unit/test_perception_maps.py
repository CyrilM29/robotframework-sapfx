"""Perception Fiori (arbre, carte @N) + mode semantique et screenshot annote ECC. Doublures dans _perception_fixtures."""
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
import pytest

from _perception_fixtures import (  # noqa: F401
    FlakyTreeBrowser,
    _MAP_XML,
    _annotated_lib,
    _fiori_lib,
    _fiori_map_lib,
    _semantic_lib,
)



def test_get_ui5_page_tree_retourne_le_xml_du_bundle():
    xml = '<UI5Tree><Button id="__btn0" controlType="sap.m.Button" text="Go"/></UI5Tree>'
    assert _fiori_lib(xml).get_ui5_page_tree() == xml


def test_get_ui5_page_tree_leve_si_pas_d_ui5():
    # bundle renvoie None hors application UI5 -> sondage épuisé -> AssertionError,
    # qui nomme la voie de diagnostic (erreur auto-corrigible).
    with pytest.raises(AssertionError, match="No UI5 control tree") as err:
        _fiori_lib(None, timeout="0.1s").get_ui5_page_tree()
    assert "Get Page Composition" in str(err.value)


def test_get_ui5_page_tree_survit_a_une_exception_js_transitoire():
    xml = '<UI5Tree><Button id="__btn0"/></UI5Tree>'
    lib = SapFioriLibrary(ui5_timeout="2s")
    browser = FlakyTreeBrowser(xml, fail_first=1)   # UNE instance : l'état du retry compte
    lib._browser = lambda: browser
    assert lib.get_ui5_page_tree() == xml


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


def test_get_ui5_page_map_numerote_et_enregistre_les_references():
    lib, _browser = _fiori_map_lib()
    lines = lib.get_ui5_page_map().splitlines()
    assert lines[0] == "# ui5 page map : 2 actionable target(s)"
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
