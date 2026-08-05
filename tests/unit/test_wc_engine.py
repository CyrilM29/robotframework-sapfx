"""Tests hors navigateur du moteur **Web Components** (custom elements ``ui5-*``,
pages sans runtime UI5 : home SuccessFactors, apps ui5-webcomponents) :
sélecteur pur, contenu du bundle et du recorder générés, keywords
``SapFioriLibrary`` (fake Browser, convention #5) et repli ``wc=`` de la
chaîne de fallback."""
import pytest

from SapFioriLibrary._ui5_js import (
    BUNDLE,
    RESOLVE_WC_JS,
    spy_snippet,
)
from SapFioriLibrary._ui5_runtime import build_wc_selector
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary


class FakeBrowser:
    """Browser factice pour une page « pur WC » : seul le résolveur wc voit des
    correspondances ; role/xpath retournent vide (pas de registre UI5)."""

    def __init__(self, wc_paths=None):
        self.wc_paths = wc_paths if wc_paths is not None else []
        self.calls = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.calls.append(("evaluate", selector, arg))
        if js == RESOLVE_WC_JS:
            return self.wc_paths
        return []

    def click(self, selector):
        self.calls.append(("click", selector, None))

    def fill_text(self, selector, text):
        self.calls.append(("fill", selector, text))

    def get_text(self, selector):
        self.calls.append(("get_text", selector, None))
        return "Save"


def _lib(browser, timeout="0.2s"):
    lib = SapFioriLibrary(ui5_timeout=timeout, poll_interval="0.01s")
    lib._browser = lambda: browser
    return lib


# --- build_wc_selector : validation pure ------------------------------------------

def test_wc_selector_rejects_unknown_keys_fast():
    with pytest.raises(ValueError) as err:
        build_wc_selector(tag="Button", controlType="sap.m.Button")
    assert "controlType" in str(err.value)
    assert "tag" in str(err.value)          # la liste des clés valides est affichée


def test_wc_selector_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        build_wc_selector()


def test_wc_selector_coerces_properties_literal_string():
    # Robot passe properties={'design': 'Emphasized'} comme une CHAÎNE
    sel = build_wc_selector(tag="Button", properties="{'design': 'Emphasized'}")
    assert sel == {"tag": "Button", "properties": {"design": "Emphasized"}}


def test_wc_selector_accepts_accessible_name():
    # name = nom accessible de l'hôte (aria-label/labelledby, accessible-name,
    # la convention UI5 Web Components, label, texte) : l'intention utilisateur.
    sel = build_wc_selector(tag="Button", name="Créer une commande")
    assert sel == {"tag": "Button", "name": "Créer une commande"}


# --- bundle : moteur wc présent et partagé avec le recorder ------------------------

def test_bundle_has_wc_engine_and_exports_it():
    assert "function resolveByWc" in BUNDLE
    assert "WC_PREFIXES" in BUNDLE and "'ui5-'" in BUNDLE
    assert "resolveByWc: resolveByWc" in BUNDLE       # exporté sur window.__SAPFX
    assert "captureWc: captureWc" in BUNDLE
    assert RESOLVE_WC_JS.startswith("(first, second) =>")
    assert "resolveByWc" in RESOLVE_WC_JS


def test_bundle_wc_engine_matches_the_accessible_name():
    # wcMatches câble sel.name sur accName (normalisé wsCollapse : le nom
    # enregistré est à espaces simples), qui honore la convention
    # accessible-name/accessibleName des UI5 Web Components.
    assert ("if (sel.name && !valueMatches(wsCollapse(accName(el)), sel.name)) "
            "return false;") in BUNDLE
    assert "accessible-name" in BUNDLE
    assert "accessibleName" in BUNDLE


def test_bundle_wc_matches_scoped_tags_and_builds_css_paths():
    # scoping UI5 WC : un type court doit matcher ui5-button ET ui5-button-<suffixe>
    assert "wcTagMatches" in BUNDLE and "wcKebab" in BUNDLE
    # les hôtes WC n'ont souvent pas d'id : chemin CSS light-DOM ancré à un id
    assert "function wcCssPath" in BUNDLE and "nth-of-type" in BUNDLE


def test_bundle_shares_value_matcher_between_role_and_wc_engines():
    # le comparateur (sous-chaîne insensible à la casse + /regex/ borné anti-ReDoS)
    # est factorisé : une évolution du matching role profite au moteur wc, et
    # réciproquement : jamais deux implémentations qui divergent.
    assert "function valueMatches" in BUNDLE
    assert "valueMatches(have[k], want[k])" in BUNDLE          # moteur role
    # moteur wc : même comparateur, haystack DOM normalisé (wsCollapse)
    assert "valueMatches(wsCollapse(el.textContent), sel.text)" in BUNDLE


def test_recorder_snippet_emits_wc_keyword_lines():
    snippet = spy_snippet()
    assert "function wcArgs" in snippet
    assert "Resolve Wc Control" in snippet             # mode capture
    assert "Click Wc Control" in snippet               # mode record : clic
    assert "Fill Wc Input" in snippet                  # mode record : saisie
    assert "Wc Control Should Be Visible" in snippet   # Alt+clic : assertion


# --- keywords : résolution ----------------------------------------------------------

def test_resolve_wc_control_returns_css_path_selector():
    browser = FakeBrowser(wc_paths=['[id="saveBtn"]'])
    assert _lib(browser).resolve_wc_control(tag="Button", text="Save") \
        == 'css=[id="saveBtn"]'


def test_resolve_wc_control_respects_frame_scope():
    browser = FakeBrowser(wc_paths=['[id="app"] > ui5-button:nth-of-type(1)'])
    lib = _lib(browser)
    lib.set_ui5_frame('iframe[id*="application"]')
    sel = lib.resolve_wc_control(tag="Button")
    assert sel == 'iframe[id*="application"] >>> css=[id="app"] > ui5-button:nth-of-type(1)'
    assert browser.calls[0][1] == 'iframe[id*="application"] >>> css=body'  # évalué DANS la frame


def test_resolve_wc_control_error_points_back_to_role_engine():
    with pytest.raises(AssertionError) as err:
        _lib(FakeBrowser()).resolve_wc_control(tag="Button")
    message = str(err.value)
    assert "ui5-*" in message
    assert "Resolve Ui5 Control" in message   # page UI5 classique -> mauvais moteur


def test_resolve_wc_control_index_out_of_range_is_explicit():
    browser = FakeBrowser(wc_paths=['[id="a"]', '[id="b"]'])
    with pytest.raises(AssertionError, match="out of range"):
        _lib(browser).resolve_wc_control(index=5, tag="Button")


def test_get_wc_match_count_does_not_wait():
    browser = FakeBrowser(wc_paths=['[id="a"]', '[id="b"]', '[id="c"]'])
    assert _lib(browser).get_wc_match_count(tag="Button") == 3
    assert _lib(FakeBrowser()).get_wc_match_count(tag="Button") == 0


def test_wc_control_should_be_visible_passes_and_fails():
    _lib(FakeBrowser(wc_paths=['[id="a"]'])).wc_control_should_be_visible(tag="Button")
    with pytest.raises(AssertionError, match="found none"):
        _lib(FakeBrowser()).wc_control_should_be_visible(tag="Button")


# --- keywords : interaction ---------------------------------------------------------

def test_click_wc_control_clicks_the_resolved_host():
    browser = FakeBrowser(wc_paths=['[id="saveBtn"]'])
    _lib(browser).click_wc_control(tag="Button", text="Save")
    assert ("click", 'css=[id="saveBtn"]', None) in browser.calls


def test_fill_wc_input_targets_the_shadow_input():
    path = '[id="app"] > div:nth-of-type(1) > ui5-input:nth-of-type(1)'
    browser = FakeBrowser(wc_paths=[path])
    _lib(browser).fill_wc_input("Jean", tag="Input")
    fill_calls = [c for c in browser.calls if c[0] == "fill"]
    # l'<input> réel vit dans le shadow root ouvert : le sélecteur descend dedans
    assert fill_calls[0][1] == "css=%s input, %s textarea" % (path, path)
    assert fill_calls[0][2] == "Jean"


def test_get_wc_text_reads_via_browser():
    browser = FakeBrowser(wc_paths=['[id="saveBtn"]'])
    assert _lib(browser).get_wc_text(tag="Button") == "Save"


# --- chaîne de fallback : repli wc= --------------------------------------------------

def test_fallback_heals_role_to_wc_on_registry_less_page():
    browser = FakeBrowser(wc_paths=['[id="saveBtn"]'])
    sel = _lib(browser).resolve_ui5_with_fallback(
        controlType="Button", properties={"text": "Save"},
        wc={"tag": "Button", "text": "Save"}, attempt_timeout="0.05s")
    assert sel == 'css=[id="saveBtn"]'


def test_fallback_accepts_wc_as_dict_literal_string():
    # forme Robot Framework : wc={'tag': 'Button'} arrive comme une chaîne
    browser = FakeBrowser(wc_paths=['[id="saveBtn"]'])
    sel = _lib(browser).resolve_ui5_with_fallback(
        wc="{'tag': 'Button'}", attempt_timeout="0.05s")
    assert sel == 'css=[id="saveBtn"]'


def test_fallback_failure_detail_includes_the_wc_attempt():
    with pytest.raises(AssertionError) as err:
        _lib(FakeBrowser()).resolve_ui5_with_fallback(
            controlType="Button", wc={"tag": "Button"}, attempt_timeout="0.05s")
    message = str(err.value)
    assert "role" in message and "wc" in message
