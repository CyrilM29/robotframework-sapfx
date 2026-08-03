"""Tests hors SAP du pont contrôle-navigateur-embarqué (WebView2/CDP).

Aucune fenêtre SAP GUI ni navigateur réel : seule la logique Python autour de
la bibliothèque Browser est exercée, avec une doublure de celle-ci (convention
#5 du CLAUDE.md — même pattern que ``test_fiori_actions.py``)."""
import os

import pytest

from SapEccLibrary.SapEccLibrary import SapEccLibrary
from SapEccLibrary.keywords._embedded_browser import _WEBVIEW2_ENV_VAR


class FakeBrowser:
    """Doublure de la bibliothèque Browser : catalogue de pages piloté par le
    test ; ``renders_after`` simule le rendu asynchrone du contrôle embarqué en
    ne révélant le catalogue qu'après ce nombre d'appels."""

    def __init__(self, catalog=None, renders_after=0):
        self._catalog = catalog if catalog is not None else []
        self._calls = 0
        self._renders_after = renders_after
        self.connect_calls = []
        self.switch_calls = []
        self.connect_should_raise = None

    def get_browser_catalog(self):
        self._calls += 1
        return self._catalog if self._calls > self._renders_after else []

    def connect_to_browser(self, ws_endpoint, use_cdp=False, **kwargs):
        self.connect_calls.append((ws_endpoint, use_cdp))
        if self.connect_should_raise:
            raise self.connect_should_raise

    def switch_page(self, page_id):
        self.switch_calls.append(page_id)
        return "previous-page-id"


def _catalog(pages):
    return [{"type": "chromium", "id": "b0", "contexts": [
        {"type": "default", "id": "c0", "activePage": "", "pages": list(pages)}
    ]}]


def _lib(browser=None, default_timeout="1s", poll_interval="0.05s"):
    lib = SapEccLibrary(screenshots_on_error=False, default_timeout=default_timeout,
                        poll_interval=poll_interval)
    if browser is not None:
        lib._browser = lambda: browser
    return lib


# --- Enable Embedded Browser Debugging ----------------------------------------

def test_enable_embedded_browser_debugging_sets_env_var_with_default_port(monkeypatch):
    monkeypatch.delenv(_WEBVIEW2_ENV_VAR, raising=False)
    port = _lib().enable_embedded_browser_debugging()
    assert port == 4711
    assert "--remote-debugging-port=4711" in os.environ[_WEBVIEW2_ENV_VAR]


def test_enable_embedded_browser_debugging_accepts_a_custom_port(monkeypatch):
    monkeypatch.delenv(_WEBVIEW2_ENV_VAR, raising=False)
    port = _lib().enable_embedded_browser_debugging(port=9333)
    assert port == 9333
    assert "--remote-debugging-port=9333" in os.environ[_WEBVIEW2_ENV_VAR]


def test_enable_embedded_browser_debugging_appends_to_existing_flags(monkeypatch):
    monkeypatch.setenv(_WEBVIEW2_ENV_VAR, "--some-other-flag")
    _lib().enable_embedded_browser_debugging()
    value = os.environ[_WEBVIEW2_ENV_VAR]
    assert "--some-other-flag" in value
    assert "--remote-debugging-port=4711" in value


# --- _browser() : message d'erreur explicite hors suite Robot ----------------

def test_browser_raises_helpful_runtime_error_outside_a_robot_run():
    lib = SapEccLibrary(screenshots_on_error=False)
    with pytest.raises(RuntimeError, match="Browser library imported"):
        lib._browser()


# --- Get Embedded Browser Page Id ---------------------------------------------

def test_finds_an_already_open_page_without_reconnecting():
    browser = FakeBrowser(_catalog([{"id": "p1", "title": "SAP Help - Article"}]))
    lib = _lib(browser)
    assert lib.get_embedded_browser_page_id("Help") == "p1"
    assert browser.connect_calls == []   # déjà là -> pas de reconnexion


def test_connects_then_polls_until_the_page_renders():
    browser = FakeBrowser(_catalog([{"id": "p1", "title": "Embedded Help"}]),
                          renders_after=2)
    lib = _lib(browser)
    assert lib.get_embedded_browser_page_id("Help") == "p1"
    assert browser.connect_calls == [("http://localhost:4711", True)]


def test_title_match_is_case_insensitive_substring_by_default():
    browser = FakeBrowser(_catalog([{"id": "p1", "title": "SAP Business Client - Inbox"}]))
    assert _lib(browser).get_embedded_browser_page_id("business client") == "p1"


def test_exact_requires_an_exact_title():
    browser = FakeBrowser(_catalog([{"id": "p1", "title": "SAP Help - Article"}]))
    lib = _lib(browser, default_timeout="0.2s")
    with pytest.raises(AssertionError):
        lib.get_embedded_browser_page_id("SAP Help", exact=True, timeout="0.2s")
    assert _lib(browser).get_embedded_browser_page_id(
        "SAP Help - Article", exact=True) == "p1"


def test_custom_port_is_used_to_connect():
    browser = FakeBrowser(_catalog([]), renders_after=99)
    lib = _lib(browser, default_timeout="0.2s")
    with pytest.raises(AssertionError):
        lib.get_embedded_browser_page_id("Help", port=9333, timeout="0.2s")
    assert browser.connect_calls == [("http://localhost:9333", True)]


def test_fails_with_open_titles_hint_when_nothing_matches():
    browser = FakeBrowser(_catalog([{"id": "p1", "title": "Unrelated page"}]))
    lib = _lib(browser, default_timeout="0.2s")
    with pytest.raises(AssertionError) as err:
        lib.get_embedded_browser_page_id("Help", timeout="0.2s")
    assert "Unrelated page" in str(err.value)
    assert "Enable Embedded Browser Debugging" in str(err.value)


def test_wraps_connect_errors_with_a_checklist():
    browser = FakeBrowser(_catalog([]))
    browser.connect_should_raise = RuntimeError("ECONNREFUSED")
    lib = _lib(browser, default_timeout="0.2s")
    with pytest.raises(RuntimeError) as err:
        lib.get_embedded_browser_page_id("Help", timeout="0.2s")
    assert "Control Settings -> Browser Control = Edge" in str(err.value)
    assert "ECONNREFUSED" in str(err.value)


# --- Switch To Embedded Browser Page ------------------------------------------

def test_switch_to_embedded_browser_page_switches_the_resolved_page():
    browser = FakeBrowser(_catalog([{"id": "p1", "title": "SAP Help - Article"}]))
    lib = _lib(browser)
    assert lib.switch_to_embedded_browser_page("Help") == "p1"
    assert browser.switch_calls == ["p1"]
