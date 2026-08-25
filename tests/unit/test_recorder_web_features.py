"""Recorder web : capture dom, compaction, menu d'assertions, panneau. Doublures dans _recorder_web_features_fixtures (convention #13)."""
from SapFioriLibrary._ui5_js import BUNDLE

from _recorder_web_features_fixtures import (  # noqa: F401
    SNIPPET,
)



def test_bundle_exposes_capture_dom_with_interactive_target_filter():
    assert "captureDom" in BUNDLE
    assert "interactiveDomTarget" in BUNDLE
    # cibles interactives seulement : un clic sur un div nu ne produit AUCUN step
    assert "INTERACTIVE_ROLES" in BUNDLE
    assert "captureDom: captureDom" in BUNDLE


def test_bundle_highlight_info_falls_back_to_dom_targets():
    # le survol montre aussi les zones non-SAP (label 'DOM <role>')
    assert "'DOM ' + (role || domEl.tagName.toLowerCase())" in BUNDLE


def test_listener_records_dom_clicks_fills_and_assertions():
    assert "Click Dom Element    ' + domArgs(dom)" in SNIPPET
    assert "Fill Dom Input    ' + value + '    ' + domArgs(dom)" in SNIPPET
    assert "Dom Element Should Be Visible    ' + domArgs(dom)" in SNIPPET
    assert "Resolve Dom Element    ' + domArgs(rec.dom)" in SNIPPET


def test_dom_args_prefer_role_and_accessible_name():
    # le localisateur « intention utilisateur » d'abord, le chemin CSS en repli
    # (nom accessible assaini : voir test_selector_texts_are_sanitized...)
    assert "return 'role=' + d.role + '    name=' + n;" in SNIPPET
    assert "return 'css=' + d.css;" in SNIPPET


def test_listener_compacts_refills_and_consecutive_waits():
    assert "function fillKey(line)" in SNIPPET
    # re-saisie du même champ = remplacement du dernier step, pas un empilement
    assert "fillKey(last) === fillKey(line)" in SNIPPET
    assert "WAIT_STEPS" in SNIPPET


def test_listener_opens_assertion_menu_on_right_click_while_recording():
    assert "function onContextMenu(event)" in SNIPPET
    assert "addEventListener('contextmenu', onContextMenu, true)" in SNIPPET
    assert "removeEventListener('contextmenu', onContextMenu, true)" in SNIPPET
    # assertions texte des moteurs sans keyword direct : paire Get + Should Be Equal
    assert "${texte} =    Get Wc Text" in SNIPPET
    assert "${texte} =    Get Dom Text" in SNIPPET
    # les raccourcis historiques restent (Alt+clic / Shift+Alt+clic)
    assert "event.altKey && cap" in SNIPPET


def test_listener_captures_enter_deferred_and_skips_textarea():
    assert "Keyboard Key    press    Enter" in SNIPPET
    assert "setTimeout" in SNIPPET
    assert "tag !== 'textarea'" in SNIPPET


def test_nav_emits_ui5_ready_or_load_state():
    assert "window.__SAPFX.isUI5() ? 'Wait For UI5 Ready' : 'Wait For Load State    load'" \
        in SNIPPET


def test_exports_embed_the_ui5_ready_keyword_definition():
    # le .robot exporté reste AUTONOME : le keyword est copié dans le fichier
    assert "UI5_READY_KEYWORD" in SNIPPET
    assert "Wait For Function    () => { const s = window.sap;" in SNIPPET
    assert "message=UI5 runtime did not become idle" in SNIPPET


def test_panel_warns_about_cross_origin_frames():
    assert "crossOriginFrameCount" in SNIPPET
    assert "cross-origin" in SNIPPET
    assert "allFrames" in SNIPPET
