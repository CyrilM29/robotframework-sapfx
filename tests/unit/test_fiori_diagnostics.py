"""Tests hors navigateur de la couche **diagnostic Fiori agrégé** :
le module pur ``sapfx_common.fiori_diagnostics`` (normalisation console/erreurs,
troncature annoncée, synthèse actionnable, rapport Markdown) et les keywords
`Get/Log Fiori Diagnostics` de SapFioriLibrary. Fake Browser, convention #5."""
import json

import pytest

from sapfx_common.fiori_diagnostics import (
    VALID_SECTIONS,
    normalize_console_entries,
    normalize_page_errors,
    parse_sections,
    render_diagnostics_report,
    summarize_issues,
    tail_entries,
)
from SapFioriLibrary._ui5_js import DUMP_TREE_JS, PAGE_COMPOSITION_JS
from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary


# --- parse_sections -----------------------------------------------------------------

def test_parse_sections_accepts_string_and_list_and_orders_canonically():
    assert parse_sections("console, tree") == ["tree", "console"]
    assert parse_sections(["aria", "composition"]) == ["composition", "aria"]
    assert parse_sections("tree,tree") == ["tree"]


def test_parse_sections_rejects_unknown_listing_valid_ones():
    with pytest.raises(ValueError) as err:
        parse_sections("console,typo")
    assert "'typo'" in str(err.value)
    assert ", ".join(VALID_SECTIONS) in str(err.value)


def test_parse_sections_rejects_empty():
    with pytest.raises(ValueError, match="none given"):
        parse_sections("")


# --- normalisation console / erreurs de page ----------------------------------------

def test_normalize_console_entries_stable_shape_and_location_compaction():
    entries = normalize_console_entries([
        {"type": "Error", "text": "boom",
         "location": {"url": "https://x/app.js", "lineNumber": 12, "columnNumber": 3},
         "time": "2026-07-18T10:00:00Z"},
        "plain string",
    ])
    assert entries[0] == {"type": "error", "text": "boom",
                          "location": "https://x/app.js:12:3",
                          "time": "2026-07-18T10:00:00Z"}
    assert entries[1] == {"type": "log", "text": "plain string",
                          "location": "", "time": ""}


def test_normalize_functions_tolerate_non_list_input():
    assert normalize_console_entries(None) == []
    assert normalize_console_entries("oops") == []
    assert normalize_page_errors({"not": "a list"}) == []


def test_normalize_page_errors_stable_shape():
    errors = normalize_page_errors([
        {"name": "ReferenceError", "message": "YT is not defined",
         "stack": "at x", "time": "t"},
        42,
    ])
    assert errors[0]["name"] == "ReferenceError"
    assert errors[1] == {"name": "Error", "message": "42", "stack": "", "time": ""}


def test_tail_entries_keeps_the_most_recent_and_counts_dropped():
    entries = [{"text": str(i)} for i in range(5)]
    kept, dropped = tail_entries(entries, 2)
    assert [e["text"] for e in kept] == ["3", "4"]
    assert dropped == 3
    assert tail_entries(entries, 0) == (entries, 0)
    assert tail_entries(entries, 9) == (entries, 0)


# --- synthèse actionnable ------------------------------------------------------------

def test_summarize_issues_counts_errors_and_names_the_first():
    issues = summarize_issues({
        "sections": ["console", "errors"],
        "console": [{"type": "error", "text": "boom"},
                    {"type": "warning", "text": "meh"},
                    {"type": "log", "text": "ok"}],
        "page_errors": [{"name": "TypeError", "message": "x is null"}],
    })
    assert any("TypeError: x is null" in i for i in issues)
    assert any("1 erreur(s) console" in i and "boom" in i for i in issues)
    assert any("1 avertissement(s)" in i for i in issues)


def test_summarize_issues_missing_tree_names_fallback_engines_and_frames():
    issues = summarize_issues({
        "sections": ["composition", "tree"],
        "ui5_tree": None,
        "composition": {"engines": ["role", "xpath", "sid", "dom"],
                        "frames": [{"selector": "iframe#app"}]},
    })
    assert len(issues) == 1
    assert "sid, dom" in issues[0]
    assert "Set Ui5 Frame" in issues[0]


def test_summarize_issues_reports_unprobeable_sections():
    issues = summarize_issues({
        "sections": ["aria"],
        "collection_errors": {"aria": "no page open"},
    })
    assert issues == ["section 'aria' insondable : no page open"]


def test_summarize_issues_empty_when_all_clean():
    assert summarize_issues({"sections": ["tree", "console"],
                             "ui5_tree": "<Page/>", "console": []}) == []


# --- rapport Markdown ----------------------------------------------------------------

def test_render_report_leads_with_issues_and_announces_truncation():
    report = render_diagnostics_report({
        "url": "https://flp/", "title": "FLP", "frame_scope": None,
        "issues": ["2 erreur(s) console, première : boom"],
        "console": [{"type": "error", "text": "boom"}],
        "console_dropped": 7,
        "page_errors": [],
        "aria": "banner:\n  - heading",
    })
    assert report.startswith("# Diagnostic Fiori")
    assert "## Anomalies (1)" in report
    assert "Console : 1 entrée(s) (+7 plus ancienne(s) écartée(s))" in report
    assert "```yaml" in report


def test_render_report_without_issues_says_none():
    report = render_diagnostics_report({"frame_scope": "iframe#app",
                                        "issues": [], "ui5_tree": "<Page/>"})
    assert "aucune détectée" in report
    assert "- portée : iframe#app" in report
    assert "```xml" in report


# --- keywords Get/Log Fiori Diagnostics ----------------------------------------------

class FakeBrowser:
    """Browser 20 factice : arbre + composition par bundle, briques diagnostic."""

    def __init__(self, tree="<Page/>", composition=None, console=None,
                 page_errors=None, aria="banner:\n  - heading", broken=()):
        self.tree = tree
        self.composition = composition if composition is not None else {
            "ui5_runtime": True, "ui5_version": "1.136.0", "ui5_controls": 3,
            "wc_hosts": 0, "webgui_elements": 0, "frameworks": [], "frames": []}
        self.console = console or []
        self.page_errors = page_errors or []
        self.aria = aria
        self.broken = broken
        self.calls = []

    def _maybe_break(self, name):
        if name in self.broken:
            raise RuntimeError("%s unavailable" % name)

    def evaluate_javascript(self, selector, js, arg=None):
        self.calls.append(("evaluate", selector))
        if js == DUMP_TREE_JS:
            return self.tree
        if js == PAGE_COMPOSITION_JS:
            return self.composition
        return None

    def get_url(self):
        self._maybe_break("get_url")
        return "https://flp/"

    def get_title(self):
        self._maybe_break("get_title")
        return "FLP"

    def get_console_log(self, full=False):
        self.calls.append(("console", full))
        self._maybe_break("get_console_log")
        return self.console

    def get_page_errors(self, full=False):
        self.calls.append(("errors", full))
        self._maybe_break("get_page_errors")
        return self.page_errors

    def get_aria_snapshot(self, selector):
        self.calls.append(("aria", selector))
        self._maybe_break("get_aria_snapshot")
        return self.aria


def _lib(browser, timeout="0.2s"):
    lib = SapFioriLibrary(ui5_timeout=timeout, poll_interval="0.01s")
    lib._browser = lambda: browser
    return lib


def test_get_fiori_diagnostics_aggregates_all_sections_json_safe():
    browser = FakeBrowser(console=[{"type": "error", "text": "boom",
                                    "location": {}, "time": "t"}])
    diag = _lib(browser).get_fiori_diagnostics(tree_timeout="0.05s")
    assert diag["sections"] == list(VALID_SECTIONS)
    assert diag["url"] == "https://flp/"
    assert diag["composition"]["engines"] == ["role", "xpath", "dom"]
    assert diag["ui5_tree"] == "<Page/>"
    assert diag["console"][0]["text"] == "boom"
    assert diag["page_errors"] == []
    assert diag["aria"].startswith("banner:")
    assert any("boom" in issue for issue in diag["issues"])
    json.dumps(diag)    # MCP-safe : sérialisable tel quel


def test_diagnostics_sections_restrict_collection_and_reject_unknown():
    browser = FakeBrowser()
    diag = _lib(browser).get_fiori_diagnostics(sections="console")
    assert "composition" not in diag and "aria" not in diag and "ui5_tree" not in diag
    assert diag["console"] == []
    with pytest.raises(ValueError, match="Valid sections"):
        _lib(browser).get_fiori_diagnostics(sections="typo")


def test_diagnostics_is_best_effort_per_section():
    browser = FakeBrowser(broken=("get_console_log", "get_aria_snapshot", "get_url"))
    diag = _lib(browser).get_fiori_diagnostics(tree_timeout="0.05s")
    assert "url" not in diag                       # contexte facultatif, pas d'échec
    assert diag["collection_errors"]["console"] == "get_console_log unavailable"
    assert diag["collection_errors"]["aria"] == "get_aria_snapshot unavailable"
    assert any("section 'console' insondable" in issue for issue in diag["issues"])
    assert diag["ui5_tree"] == "<Page/>"           # les sections saines survivent


def test_diagnostics_missing_tree_becomes_an_actionable_issue():
    browser = FakeBrowser(
        tree=None,
        composition={"ui5_runtime": False, "ui5_controls": 0, "wc_hosts": 0,
                     "webgui_elements": 4, "frameworks": [], "frames": []})
    diag = _lib(browser).get_fiori_diagnostics(tree_timeout="0.05s")
    assert diag["ui5_tree"] is None
    assert any("pas d'arbre UI5" in issue and "sid" in issue
               for issue in diag["issues"])


def test_diagnostics_does_not_touch_page_tree_diff_state():
    lib = _lib(FakeBrowser())
    lib.get_fiori_diagnostics(tree_timeout="0.05s")
    assert lib._last_page_tree is None             # l'état mode=diff reste vierge


def test_diagnostics_truncates_logs_with_announced_drop():
    console = [{"type": "log", "text": str(i)} for i in range(10)]
    diag = _lib(FakeBrowser(console=console)).get_fiori_diagnostics(
        sections="console", max_log_entries=3)
    assert [e["text"] for e in diag["console"]] == ["7", "8", "9"]
    assert diag["console_dropped"] == 7


def test_diagnostics_full_logs_and_frame_scope_are_passed_through():
    browser = FakeBrowser()
    lib = _lib(browser)
    lib.set_ui5_frame("iframe#app")
    diag = lib.get_fiori_diagnostics(sections="console,errors,aria", full_logs=True)
    assert ("console", True) in browser.calls
    assert ("errors", True) in browser.calls
    assert ("aria", "iframe#app >>> css=body") in browser.calls
    assert diag["frame_scope"] == "iframe#app"


def test_log_fiori_diagnostics_logs_the_report_and_returns_the_dict(monkeypatch):
    import importlib
    fiori_module = importlib.import_module("SapFioriLibrary.SapFioriLibrary")
    logged = []
    monkeypatch.setattr(fiori_module.logger, "info",
                        lambda msg, *a, **k: logged.append(msg))
    diag = _lib(FakeBrowser()).log_fiori_diagnostics(tree_timeout="0.05s")
    report = next(msg for msg in logged if str(msg).startswith("# Diagnostic Fiori"))
    assert "## Composition" in report
    assert diag["ui5_tree"] == "<Page/>"
