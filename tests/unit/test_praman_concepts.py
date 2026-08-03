"""Tests hors SAP / hors navigateur des concepts portés de playwright-praman
(Apache-2.0 — NOTICE) : vocabulaire métier (``sapfx_common.vocabulary``),
presets IDP (``sapfx_common.auth_flows``), hash d'intent FLP
(``_ui5_runtime.build_intent_hash``) et les keywords qui les exposent.
Doublures Browser — convention #5."""
import pytest
from robot.api.types import Secret

from sapfx_common.auth_flows import IDP_PRESETS, resolve_preset
from sapfx_common.vocabulary import (
    BusinessTerm,
    format_candidates,
    lookup_as_dict,
    lookup_term,
    resolve_term,
)
from SapEccLibrary.SapEccLibrary import SapEccLibrary
from SapFioriLibrary._ui5_runtime import build_intent_hash
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary


# --- vocabulaire métier -----------------------------------------------------------

def test_canonical_exact_scores_one():
    match = lookup_term("vendor")
    assert match.score == 1.0
    assert match.matched_via == "canonical"
    assert match.term.abap_field == "LIFNR"


def test_french_synonym_resolves():
    match = lookup_term("fournisseur")
    assert match.term.canonical == "vendor"
    assert match.score == pytest.approx(0.9)
    assert match.matched_via.startswith("synonym:")


def test_abap_field_is_a_valid_query():
    match = lookup_term("LIFNR")
    assert match.term.canonical == "vendor"
    assert match.matched_via == "abap_field"


def test_prefix_matches_below_default_threshold():
    matches = resolve_term("storage loc")
    assert matches and matches[0].term.canonical == "storage location"
    assert matches[0].score == pytest.approx(0.7)
    # sous le seuil par défaut (0.8) : lookup refuse, en listant le candidat
    with pytest.raises(ValueError, match="storage location"):
        lookup_term("storage loc")
    # seuil abaissé en connaissance de cause : accepté
    assert lookup_term("storage loc",
                       threshold=0.7).term.canonical == "storage location"


def test_ambiguous_prefix_is_refused_even_with_lowered_threshold():
    # « purcha » préfixe purchase order ET purchasing organization : à seuil
    # abaissé, l'ambiguïté est remontée — jamais de premier-match silencieux.
    with pytest.raises(ValueError, match="ambigu"):
        lookup_term("purcha", threshold=0.7)


def test_shared_abap_field_is_reported_ambiguous():
    # VBELN = sales order (VBAK) ET delivery (LIKP) : jamais tranché en silence
    matches = resolve_term("VBELN")
    assert {m.term.table for m in matches[:2]} == {"VBAK", "LIKP"}
    with pytest.raises(ValueError, match="ambigu"):
        lookup_term("VBELN")


def test_domain_filter_restricts_candidates():
    assert lookup_term("connection", domain="FLIGHT").term.table == "SPFLI"
    with pytest.raises(ValueError, match="non résolu"):
        lookup_term("connection", domain="FI")


def test_extra_vocabulary_extends_without_replacing():
    site = [BusinessTerm("z-priorité transport", "ZZTPRIO", "ZSITE", "ZTRANSP",
                         ("priorité transport",))]
    match = lookup_term("priorité transport", extra=site)
    assert match.term.abap_field == "ZZTPRIO"
    assert lookup_term("vendor", extra=site).term.abap_field == "LIFNR"


def test_empty_or_unknown_term_fails_actionably():
    assert resolve_term("") == []
    with pytest.raises(ValueError, match="aucun"):
        lookup_term("")
    with pytest.raises(ValueError, match="Candidats"):
        lookup_term("xyzzy-inconnu")


def test_lookup_as_dict_is_json_safe():
    info = lookup_as_dict("compagnie aérienne")
    assert info["abap_field"] == "CARRID"
    assert info["table"] == "SCARR"
    assert isinstance(info["synonyms"], list)
    assert set(info) == {"canonical", "abap_field", "table", "domain",
                         "synonyms", "description", "score", "matched_via"}


def test_format_candidates_readable_and_bounded():
    text = format_candidates(resolve_term("vendor"), limit=2)
    assert "LFA1.LIFNR" in text and "100%" in text
    assert format_candidates([]) == ""


# --- presets IDP ------------------------------------------------------------------

def test_presets_resolve_case_insensitively_with_overrides():
    idp = resolve_preset("SAP-IAS", submit_selector="#custom")
    assert idp.username_selector == "#j_username"
    assert idp.submit_selector == "#custom"


def test_unknown_preset_lists_the_valid_ones():
    with pytest.raises(ValueError) as err:
        resolve_preset("okta")
    for name in IDP_PRESETS:
        assert name in str(err.value)


# --- hash d'intent FLP --------------------------------------------------------------

def test_intent_hash_builds_with_sorted_encoded_params():
    assert build_intent_hash("Shell-home") == "#Shell-home"
    assert build_intent_hash("#Shell-home") == "#Shell-home"
    assert build_intent_hash("SalesOrder-manage",
                             {"b": "x/y", "a": "1"}) == \
        "#SalesOrder-manage?a=1&b=x%2Fy"


@pytest.mark.parametrize("bad", ["notanintent", "a-b-c", "-action", "So-", ""])
def test_invalid_intent_fails_immediately(bad):
    with pytest.raises(ValueError, match="SemanticObject-action"):
        build_intent_hash(bad)


# --- keywords : doublures Browser ---------------------------------------------------

class FakeNavBrowser:
    def __init__(self, url="https://host/flp.html#Old-app?x=1"):
        self._url = url
        self.gone_to = []

    def get_url(self):
        return self._url

    def go_to(self, url):
        self.gone_to.append(url)


class FakeIdpBrowser:
    """Simule un formulaire IDP : visibilité par étape, comme la vraie fixture."""

    def __init__(self, two_step=True, accept=True):
        self.user_visible = True
        self.pass_visible = not two_step
        self.two_step = two_step
        self.accept = accept
        self.fills = []
        self.clicks = 0

    def get_element_count(self, selector):
        # le keyword DOIT compter en visibilité, pas en présence DOM
        assert selector.endswith(" >> visible=true")
        sel = selector[: -len(" >> visible=true")]
        if "j_username" in sel:
            return 1 if self.user_visible else 0
        if "j_password" in sel:
            return 1 if self.pass_visible else 0
        return 1

    def fill_text(self, selector, text):
        self.fills.append((selector, text))

    def click(self, selector):
        self.clicks += 1
        if self.two_step and self.clicks == 1:
            self.pass_visible = True      # « Suivant » révèle le mot de passe
            return
        if self.accept:
            self.user_visible = False
            self.pass_visible = False


def _fiori(browser, timeout="2s"):
    lib = SapFioriLibrary(ui5_timeout=timeout, poll_interval="0.05s")
    lib._browser = lambda: browser
    return lib


def test_open_fiori_app_navigates_the_intent_hash():
    browser = FakeNavBrowser()
    _fiori(browser).open_fiori_app("SalesOrder-manage", SalesOrder="1234")
    assert browser.gone_to == [
        "https://host/flp.html#SalesOrder-manage?SalesOrder=1234"]


def test_open_fiori_app_refuses_invalid_intent_without_navigating():
    browser = FakeNavBrowser()
    with pytest.raises(ValueError):
        _fiori(browser).open_fiori_app("pas un intent")
    assert browser.gone_to == []


def test_idp_login_two_step_flow():
    browser = FakeIdpBrowser(two_step=True)
    _fiori(browser).log_in_via_identity_provider("USER", Secret("PASS"))
    assert browser.clicks == 2
    assert browser.fills == [("#j_username", "USER"), ("#j_password", "PASS")]


def test_idp_login_single_page_flow():
    browser = FakeIdpBrowser(two_step=False)
    _fiori(browser).log_in_via_identity_provider("USER", "PASS")
    assert browser.clicks == 1


def test_idp_login_fails_when_credentials_refused():
    browser = FakeIdpBrowser(two_step=False, accept=False)
    with pytest.raises(AssertionError, match="Toujours sur le formulaire"):
        _fiori(browser, timeout="0.3s").log_in_via_identity_provider("USER", "BAD")


def test_idp_login_fails_when_form_never_appears():
    browser = FakeIdpBrowser(two_step=False)
    browser.user_visible = False
    with pytest.raises(AssertionError, match="Formulaire IDP introuvable"):
        _fiori(browser, timeout="0.3s").log_in_via_identity_provider("USER", "PASS")


def test_lookup_business_term_keyword_on_both_channels():
    fiori = _fiori(FakeNavBrowser())
    assert fiori.lookup_business_term("fournisseur")["abap_field"] == "LIFNR"
    ecc = SapEccLibrary(screenshots_on_error=False)
    info = ecc.lookup_business_term("compagnie aérienne", domain="FLIGHT")
    assert info["abap_field"] == "CARRID"
