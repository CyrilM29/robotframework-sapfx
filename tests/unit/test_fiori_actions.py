"""Tests unitaires hors navigateur des raccourcis d'action de SapFioriLibrary.

La résolution en page (le JS injecté) est exercée par la suite de fumée contre
l'OpenUI5 Demo Kit ; ici on valide la logique Python *autour* du navigateur (la
lecture de table, le retry anti *stale element* du clic/saisie, et le clic par
XPath) avec une doublure de la bibliothèque Browser (convention #5 du CLAUDE.md).
"""
import pytest

from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import (
    READ_TABLE_JS,
    RESOLVE_ROLE_JS,
    RESOLVE_XPATH_JS,
)


class FakeBrowser:
    """Doublure de la bibliothèque Browser : sert des ids de résolution cannés,
    enregistre clics/saisies, et peut faire échouer N clics (simulation stale)."""

    def __init__(self, role_ids=None, table_rows=None, texts=None):
        self.role_ids = list(role_ids) if role_ids is not None else []
        self.table_rows = table_rows
        self.texts = texts or {}     # selector -> texte, pour get_text
        self.clicks = []
        self.fills = []
        self.click_fail = 0          # nombre de clics à faire échouer avant succès

    def evaluate_javascript(self, selector, js, arg=None):
        if js in (RESOLVE_ROLE_JS, RESOLVE_XPATH_JS):
            return list(self.role_ids)
        if js == READ_TABLE_JS:
            return self.table_rows
        return None

    def click(self, selector):
        if self.click_fail > 0:
            self.click_fail -= 1
            raise RuntimeError("stale element reference")
        self.clicks.append(selector)

    def fill_text(self, selector, text):
        self.fills.append((selector, text))

    def get_text(self, selector):
        return self.texts.get(selector, "")


def _lib(browser, timeout="2s"):
    lib = SapFioriLibrary(ui5_timeout=timeout)
    lib._browser = lambda: browser
    return lib


# --- poll_interval configurable -----------------------------------------------

def test_poll_interval_defaults_to_quarter_second():
    assert SapFioriLibrary().poll_interval == 0.25


def test_poll_interval_accepts_a_custom_robot_time_string():
    assert SapFioriLibrary(poll_interval="0.5s").poll_interval == 0.5


def test_poll_interval_is_the_actual_sleep_step_used_by_resolve(monkeypatch):
    import sapfx_common.polling as polling_mod
    sleeps = []
    monkeypatch.setattr(polling_mod.time, "sleep", lambda s: sleeps.append(s))
    lib = SapFioriLibrary(ui5_timeout="0.3s", poll_interval="0.05s")
    lib._browser = lambda: FakeBrowser(role_ids=[])   # ne matche jamais -> sonde jusqu'au timeout
    with pytest.raises(AssertionError, match="No UI5 control matched"):
        lib.resolve_ui5_control(controlType="sap.m.Button")
    assert sleeps                             # au moins un sondage a eu lieu
    assert all(s == 0.05 for s in sleeps)     # toujours au pas configuré, jamais 0.25 en dur


# --- réglage dynamique des timeouts (miroir de Set Default Timeout côté ECC) ---

def test_set_ui5_timeout_change_la_valeur_et_retourne_l_ancienne():
    lib = SapFioriLibrary(ui5_timeout="15s")
    old = lib.set_ui5_timeout("45s")
    assert old == "15 seconds"      # format Robot, redonnable tel quel au keyword
    # le stockage reste une chaîne de temps Robot, comme depuis __init__ :
    # chaque site d'usage la convertit via timestr_to_secs.
    from robot.utils import timestr_to_secs
    assert timestr_to_secs(lib.ui5_timeout) == 45.0


def test_set_ui5_timeout_l_ancienne_valeur_restaure_en_teardown():
    from robot.utils import timestr_to_secs
    lib = SapFioriLibrary(ui5_timeout="2 min")
    old = lib.set_ui5_timeout("5s")
    lib.set_ui5_timeout(old)
    assert timestr_to_secs(lib.ui5_timeout) == 120.0


def test_set_ui5_timeout_rejette_sans_corrompre_le_reglage_courant():
    # une chaîne invalide doit échouer AVANT adoption : le budget de sondage
    # de toute la bibliothèque ne doit jamais devenir inutilisable.
    from robot.utils import timestr_to_secs
    lib = SapFioriLibrary(ui5_timeout="15s")
    with pytest.raises(ValueError):
        lib.set_ui5_timeout("pas un temps")
    assert timestr_to_secs(lib.ui5_timeout) == 15.0


def test_set_poll_interval_change_le_pas_reellement_utilise(monkeypatch):
    import sapfx_common.polling as polling_mod
    sleeps = []
    monkeypatch.setattr(polling_mod.time, "sleep", lambda s: sleeps.append(s))
    lib = SapFioriLibrary(ui5_timeout="0.3s", poll_interval="0.25s")
    lib._browser = lambda: FakeBrowser(role_ids=[])
    old = lib.set_poll_interval("0.05s")
    assert old == "250 milliseconds"
    with pytest.raises(AssertionError, match="No UI5 control matched"):
        lib.resolve_ui5_control(controlType="sap.m.Button")
    assert sleeps
    assert all(s == 0.05 for s in sleeps)     # le nouveau pas, pas celui de l'import


# --- Read Ui5 Table ----------------------------------------------------------

def test_read_ui5_table_returns_rows_from_bundle():
    rows = [{"Name": "Acme", "City": "NY"}, {"Name": "Globex", "City": "LA"}]
    lib = _lib(FakeBrowser(role_ids=["__table0"], table_rows=rows))
    assert lib.read_ui5_table(controlType="sap.m.Table") == rows


def test_read_ui5_table_empty_when_bundle_returns_none():
    lib = _lib(FakeBrowser(role_ids=["__table0"], table_rows=None))
    assert lib.read_ui5_table(controlType="sap.m.Table") == []


def test_read_ui5_table_raises_when_no_table_matches():
    lib = _lib(FakeBrowser(role_ids=[]), timeout="0.1s")
    with pytest.raises(AssertionError, match="No UI5 table matched"):
        lib.read_ui5_table(controlType="sap.m.Table")


def test_read_ui5_table_raises_on_out_of_range_index():
    lib = _lib(FakeBrowser(role_ids=["__t0"], table_rows=[]))
    with pytest.raises(AssertionError, match="out of range"):
        lib.read_ui5_table(index=3, controlType="sap.m.Table")


def test_get_ui5_xpath_raises_on_out_of_range_index():
    # Cohérence avec _pick : index hors-borne lève au lieu de retomber sur ids[0].
    lib = _lib(FakeBrowser(role_ids=["__a0"]))
    with pytest.raises(AssertionError, match="out of range"):
        lib.get_ui5_xpath(index=5, controlType="sap.m.Button")


# --- retry anti stale-element sur le clic ------------------------------------

def test_click_ui5_control_retries_after_stale_then_succeeds():
    browser = FakeBrowser(role_ids=["__btn0"])
    browser.click_fail = 1                       # 1er clic stale, 2e ok
    lib = _lib(browser)
    lib.click_ui5_control(controlType="sap.m.Button", properties={"text": "Go"})
    assert browser.clicks == ['css=[id="__btn0"]']


def test_click_ui5_control_gives_up_after_retries():
    browser = FakeBrowser(role_ids=["__btn0"])
    browser.click_fail = 99
    lib = _lib(browser, timeout="0.3s")
    with pytest.raises(AssertionError, match="Could not click"):
        lib.click_ui5_control(controlType="sap.m.Button")


def test_fill_ui5_input_targets_inner_input_or_textarea():
    browser = FakeBrowser(role_ids=["__in0"])
    lib = _lib(browser)
    lib.fill_ui5_input("hello", controlType="sap.m.Input")
    assert browser.fills == [
        ('css=[id="__in0"] input, [id="__in0"] textarea', "hello")]


# --- clic par UI5 XPath ------------------------------------------------------

def test_click_ui5_by_xpath_resolves_then_clicks():
    browser = FakeBrowser(role_ids=["__d0"])
    lib = _lib(browser)
    lib.click_ui5_by_xpath("//Dialog//Button[@text='OK']")
    assert browser.clicks == ['css=[id="__d0"]']


# --- résilience du sondage face à une exception JS transitoire ---------------

class FlakyBrowser(FakeBrowser):
    """Comme FakeBrowser, mais lève une exception sur le N premier appels
    d'evaluate_javascript (simulation d'un re-rendu qui détruit le contexte
    d'exécution JS en cours de sondage)."""

    def __init__(self, role_ids=None, table_rows=None, fail_first=1):
        super().__init__(role_ids=role_ids, table_rows=table_rows)
        self._fail_remaining = fail_first

    def evaluate_javascript(self, selector, js, arg=None):
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise RuntimeError("Execution context was destroyed")
        return super().evaluate_javascript(selector, js, arg=arg)


def test_resolve_ui5_control_survives_a_transient_js_exception():
    # poll_until interdit à `check` de lever ; _resolve doit absorber l'échec et
    # continuer à sonder plutôt que de laisser l'exception interrompre l'attente.
    browser = FlakyBrowser(role_ids=["__btn0"], fail_first=1)
    lib = _lib(browser)
    assert lib.resolve_ui5_control(controlType="sap.m.Button") == 'css=[id="__btn0"]'


def test_resolve_ui5_control_raises_if_js_keeps_failing_until_timeout():
    browser = FlakyBrowser(role_ids=["__btn0"], fail_first=999)
    lib = _lib(browser, timeout="0.1s")
    with pytest.raises(AssertionError, match="No UI5 control matched"):
        lib.resolve_ui5_control(controlType="sap.m.Button")


# --- Ui5 Control Should Be Visible / Get Ui5 Match Count / Get Ui5 Text -------

def test_ui5_control_should_be_visible_passes_when_a_control_matches():
    lib = _lib(FakeBrowser(role_ids=["__btn0"]))
    lib.ui5_control_should_be_visible(controlType="sap.m.Button")   # ne doit pas lever


def test_ui5_control_should_be_visible_raises_when_none_match():
    lib = _lib(FakeBrowser(role_ids=[]), timeout="0.1s")
    with pytest.raises(AssertionError, match="found none"):
        lib.ui5_control_should_be_visible(controlType="sap.m.Button")


def test_get_ui5_match_count_returns_cardinality_without_waiting():
    lib = _lib(FakeBrowser(role_ids=["__a", "__b", "__c"]))
    assert lib.get_ui5_match_count(controlType="sap.m.Button") == 3


def test_get_ui5_match_count_is_zero_when_nothing_matches():
    lib = _lib(FakeBrowser(role_ids=[]))
    assert lib.get_ui5_match_count(controlType="sap.m.Button") == 0


def test_get_ui5_text_resolves_then_reads_via_browser_get_text():
    browser = FakeBrowser(role_ids=["__lbl0"], texts={'css=[id="__lbl0"]': "Hello"})
    lib = _lib(browser)
    assert lib.get_ui5_text(controlType="sap.m.Text") == "Hello"


# --- _browser() : message d'erreur explicite hors suite Robot ----------------

def test_browser_raises_helpful_runtime_error_outside_a_robot_run():
    # Sans contexte d'exécution Robot actif, BuiltIn().get_library_instance lève
    # RobotNotRunningError -- _browser() doit le convertir en RuntimeError clair
    # plutôt que de laisser fuiter l'exception interne de BuiltIn.
    lib = SapFioriLibrary()
    with pytest.raises(RuntimeError, match="Browser library imported"):
        lib._browser()
