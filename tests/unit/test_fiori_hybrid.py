"""Tests hors navigateur du support **pages hybrides** de SapFioriLibrary :
sonde de composition (`Get Page Composition`), pile de frames imbriquées
(`Push/Pop Ui5 Frame`), moteur DOM générique (`Resolve/Click/Fill Dom …`) et
son repli ``dom=`` dans la chaîne de fallback. Fake Browser, convention #5."""
import pytest

from SapFioriLibrary import SapFioriLibrary as _pkg  # noqa: F401  (import path sanity)
from SapFioriLibrary._ui5_js import (
    BUNDLE,
    PAGE_COMPOSITION_JS,
    RESOLVE_DOM_JS,
    RESOLVE_ROLE_JS,
)
from SapFioriLibrary._ui5_runtime import build_dom_selector, recommended_engines
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary


class FakeBrowser:
    """Browser factice : réponses programmées par bundle JS + journal d'appels."""

    def __init__(self, dom_paths=None, role_ids=None, composition=None,
                 frame_compositions=None):
        self.dom_paths = dom_paths if dom_paths is not None else []
        self.role_ids = role_ids if role_ids is not None else []
        self.composition = composition
        self.frame_compositions = frame_compositions or {}
        self.calls = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.calls.append(("evaluate", selector, arg))
        if js == RESOLVE_DOM_JS:
            return self.dom_paths
        if js == RESOLVE_ROLE_JS:
            return self.role_ids
        if js == PAGE_COMPOSITION_JS:
            if selector is None:
                return self.composition
            value = self.frame_compositions.get(selector)
            if isinstance(value, Exception):
                raise value
            return value
        return None

    def click(self, selector):
        self.calls.append(("click", selector, None))

    def fill_text(self, selector, text):
        self.calls.append(("fill", selector, text))

    def get_text(self, selector):
        self.calls.append(("get_text", selector, None))
        return "Valider"


def _lib(browser, timeout="0.2s"):
    lib = SapFioriLibrary(ui5_timeout=timeout, poll_interval="0.01s")
    lib._browser = lambda: browser
    return lib


# --- build_dom_selector (modèle pur) ----------------------------------------------

def test_build_dom_selector_rejects_unknown_keys():
    with pytest.raises(ValueError, match="Unknown DOM selector"):
        build_dom_selector(cssz="button")


def test_build_dom_selector_rejects_empty():
    with pytest.raises(ValueError, match="Empty DOM selector"):
        build_dom_selector()


def test_build_dom_selector_coerces_properties_literal():
    sel = build_dom_selector(role="button", properties="{'data-testid': 'go'}")
    assert sel == {"role": "button", "properties": {"data-testid": "go"}}


def test_build_dom_selector_accepts_accessibility_keys():
    # role (explicite OU implicite) + name (nom accessible) : la grammaire
    # « intention utilisateur » du moteur dom, façon getByRole(name=…).
    sel = build_dom_selector(role="button", name="Valider")
    assert sel == {"role": "button", "name": "Valider"}


# --- recommended_engines (modèle pur) ----------------------------------------------

def test_recommended_engines_always_ends_with_dom():
    assert recommended_engines({}) == ["dom"]


def test_recommended_engines_maps_each_technology():
    assert recommended_engines({"ui5_runtime": True}) == ["role", "xpath", "dom"]
    assert recommended_engines({"webgui_elements": 3}) == ["sid", "dom"]
    assert recommended_engines({"wc_hosts": 2}) == ["wc", "dom"]
    assert recommended_engines({"ui5_runtime": True, "webgui_elements": 1,
                                "wc_hosts": 1}) == ["role", "xpath", "sid", "wc", "dom"]


# --- moteur DOM générique ----------------------------------------------------------

def test_resolve_dom_element_returns_scoped_css_path():
    browser = FakeBrowser(dom_paths=['[id="widget"] > button:nth-of-type(1)'])
    sel = _lib(browser).resolve_dom_element(role="button", text="Valider")
    assert sel == 'css=[id="widget"] > button:nth-of-type(1)'


def test_resolve_dom_element_failure_points_to_composition_probe():
    lib = _lib(FakeBrowser(dom_paths=[]))
    with pytest.raises(AssertionError) as err:
        lib.resolve_dom_element(role="button")
    assert "Get Page Composition" in str(err.value)


def test_click_and_get_text_and_count_dom():
    browser = FakeBrowser(dom_paths=['[id="w"] > button:nth-of-type(2)'])
    lib = _lib(browser)
    lib.click_dom_element(role="button")
    assert ("click", 'css=[id="w"] > button:nth-of-type(2)', None) in browser.calls
    assert lib.get_dom_text(role="button") == "Valider"
    assert lib.get_dom_match_count(role="button") == 1


def test_fill_dom_input_targets_the_element_or_its_inner_field():
    browser = FakeBrowser(dom_paths=['[id="name-input"]'])
    _lib(browser).fill_dom_input("Jean", css="#name-input")
    fill = next(c for c in browser.calls if c[0] == "fill")
    assert fill[1] == ('css=[id="name-input"]:is(input, textarea), '
                       '[id="name-input"] input, [id="name-input"] textarea')
    assert fill[2] == "Jean"


def test_dom_selectors_respect_the_frame_scope():
    browser = FakeBrowser(dom_paths=['[id="w"]'])
    lib = _lib(browser)
    lib.set_ui5_frame("#appframe")
    assert lib.resolve_dom_element(role="button") == '#appframe >>> css=[id="w"]'


# --- pile de frames (Push/Pop Ui5 Frame) -------------------------------------------

def test_push_builds_a_chained_scope_and_pop_unwinds_it():
    browser = FakeBrowser(role_ids=["__btn0"])
    lib = _lib(browser)
    lib.push_ui5_frame('iframe[id="level1"]')
    lib.push_ui5_frame('iframe[id="level2"]')
    sel = lib.resolve_ui5_control(controlType="Button")
    assert sel == 'iframe[id="level1"] >>> iframe[id="level2"] >>> css=[id="__btn0"]'
    scope = browser.calls[0][1]
    assert scope == 'iframe[id="level1"] >>> iframe[id="level2"] >>> css=body'
    assert lib.pop_ui5_frame() == 'iframe[id="level2"]'
    assert lib.get_ui5_frame_stack() == ['iframe[id="level1"]']
    lib.pop_ui5_frame()
    assert lib.get_ui5_frame_stack() == []
    assert lib.resolve_ui5_control(controlType="Button") == 'css=[id="__btn0"]'


def test_pop_on_empty_stack_fails_clearly():
    lib = _lib(FakeBrowser())
    with pytest.raises(AssertionError, match="frame stack is empty"):
        lib.pop_ui5_frame()


def test_push_requires_a_selector():
    lib = _lib(FakeBrowser())
    with pytest.raises(ValueError, match="non-empty frame selector"):
        lib.push_ui5_frame("")


def test_set_ui5_frame_replaces_the_whole_stack():
    lib = _lib(FakeBrowser(role_ids=["x"]))
    lib.push_ui5_frame("a")
    lib.push_ui5_frame("b")
    lib.set_ui5_frame("c")
    assert lib.get_ui5_frame_stack() == ["c"]
    lib.set_ui5_frame(None)
    assert lib.get_ui5_frame_stack() == []


# --- Get Page Composition -----------------------------------------------------------

def _main_composition():
    return {"url": "https://shell/", "title": "Shell",
            "ui5_runtime": True, "ui5_version": "1.136.0", "ui5_controls": 12,
            "wc_hosts": 0, "webgui_elements": 0, "frameworks": [],
            "frames": [
                {"selector": 'iframe[id="app"]', "src": "app.html", "visible": True},
                {"selector": 'iframe[id="dead"]', "src": "", "visible": False},
            ]}


def test_composition_recommends_engines_and_probes_frames():
    sub = {"ui5_runtime": False, "ui5_controls": 0, "wc_hosts": 0,
           "webgui_elements": 4, "frameworks": ["react"], "frames": []}
    browser = FakeBrowser(
        composition=_main_composition(),
        frame_compositions={
            'iframe[id="app"] >>> css=body': sub,
            'iframe[id="dead"] >>> css=body': RuntimeError("frame detached"),
        })
    comp = _lib(browser).get_page_composition()
    assert comp["engines"] == ["role", "xpath", "dom"]
    app = comp["frames"][0]
    assert app["composition"]["engines"] == ["sid", "dom"]
    dead = comp["frames"][1]
    assert "composition" not in dead
    assert "frame detached" in dead["error"]              # best-effort, jamais fatal


def test_composition_frame_probe_respects_current_scope():
    browser = FakeBrowser(
        composition=None,   # non utilisé : la portée n'est plus None
        frame_compositions={})

    class ScopedBrowser(FakeBrowser):
        def evaluate_javascript(self, selector, js, arg=None):
            self.calls.append(("evaluate", selector, arg))
            if js == PAGE_COMPOSITION_JS and selector == "outer >>> css=body":
                return {"ui5_runtime": False, "wc_hosts": 0, "webgui_elements": 0,
                        "frameworks": [],
                        "frames": [{"selector": "iframe#inner", "src": "", "visible": True}]}
            if js == PAGE_COMPOSITION_JS:
                return {"ui5_runtime": False, "wc_hosts": 1, "webgui_elements": 0,
                        "frameworks": [], "frames": []}
            return None

    browser = ScopedBrowser()
    lib = _lib(browser)
    lib.set_ui5_frame("outer")
    comp = lib.get_page_composition()
    # la sonde de la sous-frame est préfixée par la portée courante
    probed = [c[1] for c in browser.calls if c[1] and "inner" in str(c[1])]
    assert probed == ["outer >>> iframe#inner >>> css=body"]
    assert comp["frames"][0]["composition"]["engines"] == ["wc", "dom"]


def test_composition_without_page_fails_clearly():
    lib = _lib(FakeBrowser(composition=None))
    with pytest.raises(AssertionError, match="composition"):
        lib.get_page_composition()


def test_composition_can_skip_frame_probing():
    browser = FakeBrowser(composition=_main_composition())
    comp = _lib(browser).get_page_composition(include_frames=False)
    assert all("composition" not in f for f in comp["frames"])


# --- chaîne de fallback : dom= en dernier repli --------------------------------------

def test_fallback_heals_to_dom_last_and_records_telemetry(monkeypatch):
    import importlib
    fiori_module = importlib.import_module("SapFioriLibrary.SapFioriLibrary")
    healed = []
    monkeypatch.setattr(fiori_module, "record_healing",
                        lambda channel, **kw: healed.append((channel, kw)))
    browser = FakeBrowser(role_ids=[], dom_paths=['[id="w"] > button:nth-of-type(1)'])
    sel = _lib(browser).resolve_ui5_with_fallback(
        controlType="Button", properties={"text": "Valider"},
        dom={"role": "button", "text": "Valider"}, attempt_timeout="0.05s")
    assert sel == 'css=[id="w"] > button:nth-of-type(1)'
    assert healed and healed[0][0] == "fiori"
    assert healed[0][1]["engine"] == "dom"


def test_fallback_error_message_lists_dom_form():
    lib = _lib(FakeBrowser())
    with pytest.raises(ValueError, match="dom="):
        lib.resolve_ui5_with_fallback()


# --- bundle JS ------------------------------------------------------------------------

def test_bundle_exposes_dom_engine_and_composition_probe():
    assert "resolveByDom" in BUNDLE
    assert "pageComposition" in BUNDLE
    assert "frameworkHints" in BUNDLE


def test_bundle_dom_engine_uses_the_accessibility_helpers():
    # Le rôle est CALCULÉ (explicite ou implicite) et le nom accessible est un
    # accname simplifié, tous deux câblés dans resolveByDom. La regex \s+ doit
    # survivre à l'échappement Python de la chaîne du bundle (leçon du \D
    # défangé par Robot, test_se16_exploration_logic).
    assert "function ariaRole" in BUNDLE
    assert "function accName" in BUNDLE
    assert "ariaRole(el) !== String(sel.role).toLowerCase()" in BUNDLE
    # haystack NORMALISÉ (wsCollapse) : le nom enregistré est à espaces simples,
    # un accname multi-nœuds (textContent indenté) doit quand même matcher
    assert "valueMatches(wsCollapse(accName(el)), sel.name)" in BUNDLE
    assert "split(/\\s+/)" in BUNDLE and "split(/\\\\s+/)" not in BUNDLE
    # Précédence accname (spec W3C) : aria-labelledby avant aria-label.
    assert BUNDLE.index("aria-labelledby") < BUNDLE.index("'aria-label'")
