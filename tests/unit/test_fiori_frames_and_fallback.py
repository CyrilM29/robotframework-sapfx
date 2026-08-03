"""Tests hors navigateur du support iframe (Work Zone/cFLP), des erreurs
auto-corrigibles, de la chaîne de fallback et du support Fiori Elements
(``idSuffix``) de SapFioriLibrary. Fake Browser — convention #5."""
import pytest

from SapFioriLibrary._ui5_js import (
    BUNDLE,
    RESOLVE_ROLE_JS,
    RESOLVE_XPATH_JS,
    spy_snippet,
)
from SapFioriLibrary._ui5_runtime import build_control_selector
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary


class FakeBrowser:
    """Browser factice : réponses programmées par (js, arg->) + journal d'appels."""

    def __init__(self, role_ids=None, xpath_ids=None):
        self.role_ids = role_ids if role_ids is not None else []
        self.xpath_ids = xpath_ids if xpath_ids is not None else []
        self.calls = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.calls.append(("evaluate", selector, arg))
        if js == RESOLVE_ROLE_JS:
            # les ids peuvent être programmés par arg JSON (dict) ou liste plate
            if isinstance(self.role_ids, dict):
                return self.role_ids.get(arg, [])
            return self.role_ids
        if js == RESOLVE_XPATH_JS:
            return self.xpath_ids
        return None

    def fill_text(self, selector, text):
        self.calls.append(("fill", selector, text))

    def get_text(self, selector):
        self.calls.append(("get_text", selector, None))
        return "42,00 EUR"

    def wait_for_elements_state(self, selector, state, timeout=None):
        self.calls.append(("wait_state", selector, state))


def _lib(browser, timeout="0.2s"):
    lib = SapFioriLibrary(ui5_timeout=timeout, poll_interval="0.01s")
    lib._browser = lambda: browser
    return lib


# --- Set Ui5 Frame : résolution et sélecteurs scoping ---------------------------

def test_without_frame_scope_is_page_and_selector_bare():
    browser = FakeBrowser(role_ids=["__button0"])
    lib = _lib(browser)
    sel = lib.resolve_ui5_control(controlType="Button")
    assert sel == 'css=[id="__button0"]'
    assert browser.calls[0] == ("evaluate", None, mock_arg(browser))     # scope page


def mock_arg(browser):
    return browser.calls[0][2]


def test_frame_scopes_evaluation_and_prefixes_selectors():
    browser = FakeBrowser(role_ids=["__button0"])
    lib = _lib(browser)
    lib.set_ui5_frame('iframe[id*="application"]')
    sel = lib.resolve_ui5_control(controlType="Button")
    assert sel == 'iframe[id*="application"] >>> css=[id="__button0"]'
    scope = browser.calls[0][1]
    assert scope == 'iframe[id*="application"] >>> css=body'   # évalué DANS la frame
    # reset -> retour page principale
    lib.set_ui5_frame(None)
    assert lib.resolve_ui5_control(controlType="Button") == 'css=[id="__button0"]'


def test_frame_prefixes_sid_and_fill_selectors():
    browser = FakeBrowser(role_ids=["__input0-inner"])
    lib = _lib(browser)
    lib.set_ui5_frame("#appframe")
    assert lib.resolve_sid("wnd[0]/usr/txtX").startswith("#appframe >>> xpath=")
    lib.fill_ui5_input("hello", controlType="Input")
    fill_calls = [c for c in browser.calls if c[0] == "fill"]
    assert fill_calls[0][1].startswith("#appframe >>> css=")
    assert 'id="__input0-inner"' in fill_calls[0][1]


# --- erreurs auto-corrigibles ----------------------------------------------------

def test_no_match_error_reports_type_only_count():
    # properties ne matchent pas, mais 3 contrôles du type existent
    def role_resolver(arg):
        return [] if "properties" in arg else ["a", "b", "c"]

    class HintBrowser(FakeBrowser):
        def evaluate_javascript(self, selector, js, arg=None):
            self.calls.append(("evaluate", selector, arg))
            if js == RESOLVE_ROLE_JS:
                return role_resolver(arg)
            return None

    lib = _lib(HintBrowser())
    with pytest.raises(AssertionError) as err:
        lib.resolve_ui5_control(controlType="Button", properties={"text": "Gone"})
    message = str(err.value)
    assert "3 control(s) of type Button ARE rendered" in message
    assert "Get Ui5 Page Tree" in message


def test_no_match_error_reports_type_absent():
    lib = _lib(FakeBrowser(role_ids=[]))
    with pytest.raises(AssertionError) as err:
        lib.resolve_ui5_control(controlType="Dialog", properties={"title": "X"})
    assert "No control of type Dialog is rendered at all" in str(err.value)


# --- Resolve Ui5 With Fallback ----------------------------------------------------

def test_fallback_returns_primary_without_warning_when_role_matches():
    browser = FakeBrowser(role_ids=["__btn1"])
    sel = _lib(browser).resolve_ui5_with_fallback(
        controlType="Button", xpath="//Button", attempt_timeout="0.1s")
    assert sel == 'css=[id="__btn1"]'


def test_fallback_heals_to_xpath_when_role_fails():
    browser = FakeBrowser(role_ids=[], xpath_ids=["__btn2"])
    sel = _lib(browser).resolve_ui5_with_fallback(
        controlType="Button", properties={"text": "Gone"},
        xpath="//Dialog//Button", attempt_timeout="0.05s")
    assert sel == 'css=[id="__btn2"]'


def test_fallback_heals_to_sid_last():
    browser = FakeBrowser(role_ids=[], xpath_ids=[])
    sel = _lib(browser).resolve_ui5_with_fallback(
        controlType="Button", xpath="//Button", sid="wnd[0]/tbar[1]/btn[8]",
        attempt_timeout="0.05s")
    assert sel.startswith("xpath=")
    assert '"SID":"wnd[0]/tbar[1]/btn[8]"' in sel


def test_fallback_fails_with_per_engine_detail():
    browser = FakeBrowser(role_ids=[], xpath_ids=[])

    def failing_wait(selector, state, timeout=None):
        raise RuntimeError("not visible")
    browser.wait_for_elements_state = failing_wait
    with pytest.raises(AssertionError) as err:
        _lib(browser).resolve_ui5_with_fallback(
            controlType="Button", xpath="//Button", sid="wnd[0]/usr/txtX",
            attempt_timeout="0.05s")
    message = str(err.value)
    assert "role" in message and "xpath" in message and "sid" in message
    # échec le plus générique de la bibliothèque : il nomme la couche diagnostic
    assert "Log Fiori Diagnostics" in message


def test_fallback_requires_at_least_one_form():
    with pytest.raises(ValueError, match="at least one"):
        _lib(FakeBrowser()).resolve_ui5_with_fallback()


# --- Fiori Elements : idSuffix -----------------------------------------------------

def test_id_suffix_is_a_valid_selector_key():
    sel = build_control_selector(idSuffix="fe::table::Travel::LineItem::Table")
    assert sel == {"idSuffix": "fe::table::Travel::LineItem::Table"}


def test_bundle_matches_id_suffix_and_captures_fe_ids():
    assert "sel.idSuffix" in BUNDLE                    # moteur role : filtre par suffixe
    assert "feIdSuffix" in BUNDLE                      # capture Spy : id FE -> idSuffix
    snippet = spy_snippet()
    assert "idSuffix=" in snippet                      # ligne de keyword émise


def test_bundle_capture_exposes_text_for_value_assertions():
    assert "text: txt" in BUNDLE
    assert "Ui5 Text Should Be" in spy_snippet()       # Shift+Alt+clic du recorder


# --- Ui5 Text Should Be -------------------------------------------------------------

def test_ui5_text_should_be_passes_and_fails():
    browser = FakeBrowser(role_ids=["__text0"])
    lib = _lib(browser)
    lib.ui5_text_should_be("42,00 EUR", controlType="ObjectNumber")   # trim égal
    with pytest.raises(AssertionError, match="expected"):
        lib.ui5_text_should_be("43,00 EUR", controlType="ObjectNumber")
