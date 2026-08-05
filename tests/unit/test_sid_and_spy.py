"""Tests unitaires hors navigateur pour le helper sid (WebGUI), l'ajout du bundle
XPath le plus court, et la synchronisation du snippet Spy généré avec le bundle.
"""
import os

import pytest

from SapFioriLibrary._ui5_js import (
    BEST_XPATH_JS,
    BUNDLE,
    sid_xpath,
    spy_snippet,
)

_RECORDER_WEB = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder_web"))
_SPY_FILES = [
    os.path.join(_RECORDER_WEB, "recorder_snippet.js"),
    os.path.join(_RECORDER_WEB, "extension", "recorder.js"),
]


def test_sid_xpath_builds_contains_predicate():
    sel = sid_xpath("wnd[0]/usr/ctxtVBAK-VBELN")
    assert sel == ("xpath=//*[contains(@lsdata, '\"SID\":\"wnd[0]/usr/ctxtVBAK-VBELN\"')"
                   " or contains(@lsdata, \"SID:'wnd[0]/usr/ctxtVBAK-VBELN'\")]")
    # Les identifiants SAP GUI contiennent [ ] / - mais jamais de guillemet simple, donc le littéral est sûr.
    assert "'" not in "wnd[0]/usr/ctxtVBAK-VBELN"


def test_sid_xpath_matches_both_lsdata_encodings():
    # Découvert live sur le WebGUI A4H (exploration agent 2026-07-18) : le vrai
    # SAP GUI for HTML émet `lsdata` en littéral JS (`SID:'…'`, clé non citée,
    # guillemets simples) et non le JSON `"SID":"…"` des fixtures : l'ancien
    # sélecteur JSON-seul ne matchait RIEN sur un vrai système (0 match live).
    sel = sid_xpath("wnd[0]/tbar[0]/okcd")
    assert "contains(@lsdata, '\"SID\":\"wnd[0]/tbar[0]/okcd\"')" in sel      # fixtures / anciens ITS
    assert "contains(@lsdata, \"SID:'wnd[0]/tbar[0]/okcd'\")" in sel          # WebGUI live S/4 1909
    assert " or " in sel


@pytest.mark.parametrize("malicious_sid", [
    "x'] | //input[@type='password",
    'x"] | //input[@type="password',
])
def test_sid_xpath_rejects_quotes_to_prevent_selector_injection(malicious_sid):
    # Un sid forgé contenant un guillemet casserait le littéral XPath et pourrait
    # rediriger Click Sid/Fill Sid Input vers un élément arbitraire de la page.
    with pytest.raises(ValueError):
        sid_xpath(malicious_sid)


def test_bundle_exposes_best_xpath_sid_and_highlight():
    assert "bestXpath" in BUNDLE
    assert "positionalPath" in BUNDLE and "snapshotLength === 1" in BUNDLE
    # La capture sid accepte les DEUX encodages de lsdata (JSON et littéral JS) :
    # regex tolérante sur les guillemets, jamais le seul motif JSON.
    assert "captureSid" in BUNDLE and "[\"']?SID[\"']?" in BUNDLE
    assert "highlightInfo" in BUNDLE and "getBoundingClientRect" in BUNDLE
    assert BEST_XPATH_JS.startswith("(first, second) =>") and "bestXpath" in BEST_XPATH_JS


def test_bundle_escapes_xpath_literals_instead_of_stripping_quotes():
    # Régression : la capture construisait `[@text='...']` en SUPPRIMANT les apostrophes
    # (replace(/'/g, '')), produisant un xpath faux pour un texte comme "L'utilisateur".
    # XPath 1.0 n'échappe pas les guillemets dans un littéral -> on bascule de quote ou concat().
    assert "function xpathLiteral" in BUNDLE
    assert "xpathLiteral(val)" in BUNDLE          # valeur de propriété capturée
    assert "xpathLiteral(c.getId())" in BUNDLE    # repli sur l'id
    assert "xpathLiteral(id)" in BUNDLE           # findNodeById
    assert "concat('" in BUNDLE                   # repli quand les deux guillemets sont présents
    # plus aucune suppression destructrice de guillemets
    assert "replace(/'/g, '')" not in BUNDLE


def test_bundle_warns_on_dynamic_id_capture_fallback():
    # Régression : capture() retombait silencieusement sur un id dynamique quand
    # aucune propriété stable ne matchait, sans jamais avertir l'utilisateur.
    assert "falling back to a dynamic control id" in BUNDLE


def test_spy_snippet_has_hover_and_stop_controls():
    snippet = spy_snippet()
    assert "mousemove" in snippet and "requestAnimationFrame" in snippet  # superposition au survol
    assert "__ui5SpyStop" in snippet and "Escape" in snippet             # contrôles d'arrêt


def test_recorder_snippet_has_record_mode():
    snippet = spy_snippet()
    # mode record : actions ordonnées + export d'un corps de test rejouable
    assert "function clickLine" in snippet and "Click Ui5 Control" in snippet
    assert "function fillLine" in snippet and "Fill Ui5 Input" in snippet
    assert "change" in snippet                       # écoute des saisies validées
    assert "recording" in snippet and "exportScript" in snippet
    assert "*** Test Cases ***" in snippet           # l'export produit un corps de test
    # export = téléchargement d'un .robot (via Blob) + copie presse-papiers
    assert "function download" in snippet and "createObjectURL" in snippet
    assert "recorded.robot" in snippet


def test_recorder_snippet_high_impact_features():
    snippet = spy_snippet()
    # 1) persistance du déroulé entre rechargements (sessionStorage)
    assert "sessionStorage" in snippet and "__ui5RecorderSteps" in snippet
    assert "function loadSteps" in snippet and "function saveSteps" in snippet
    # 2) export .robot COMPLET et rejouable (Settings + ouverture navigateur)
    assert "*** Settings ***" in snippet and "Library    Browser" in snippet
    assert "Library    SapFioriLibrary" in snippet and "New Browser" in snippet
    # 2) liste de steps éditable (déplacer / supprimer)
    assert "function moveStep" in snippet and "function removeStep" in snippet
    # 3) déduplication des steps consécutifs identiques, TEMPORISÉE depuis
    # 2026-07 : un double dispatch (<500 ms) est dédupliqué, une répétition
    # volontaire (second clic sur le même bouton au-delà de la fenêtre) est gardée
    assert "CLICK_DEDUP_WINDOW_MS" in snippet and "if (last === line &&" in snippet
    # 3) assertion via Alt+clic, et attente sur navigation Fiori
    assert "Ui5 Control Should Be Visible" in snippet and "altKey" in snippet
    assert "Wait For Load State" in snippet and "hashchange" in snippet
    # 4) échappement Robot Framework des valeurs enregistrées (variables ${...},
    # runs d'espaces, '#', 'mot=') + inverse exact appliqué par le replay
    assert "function rfEscape" in snippet and "function rfUnescape" in snippet
    # 5) l'état d'enregistrement survit à la navigation (reprise à la ré-injection)
    assert "__ui5RecorderRecording" in snippet and "loadRecording" in snippet
    # 6) l'Entrée différée est flushée si la page se décharge (soumission pleine page)
    assert "onBeforeUnload" in snippet and "pendingEnter" in snippet
    # 7) état explicite pour l'extension (anti-phase entre frames)
    assert "setRec:" in snippet


def test_recorder_snippet_panel_and_extension_api():
    snippet = spy_snippet()
    # panneau : déplaçable, repliable, indicateur d'enregistrement
    assert "function onDragMove" in snippet and "function setCollapsed" in snippet
    assert "__ui5RecBlink" in snippet                # animation du point d'enregistrement
    # API pilotable depuis le popup / le raccourci de l'extension + diffusion d'état (badge)
    assert "window.__ui5RecorderApi" in snippet and "toggleRec" in snippet
    assert "__ui5RecorderState" in snippet           # événement relayé par bridge.js


def test_generated_spy_files_are_in_sync_with_bundle():
    # Les deux fichiers Spy commités sont générés depuis spy_snippet() ; protection contre la dérive.
    # Régénérer avec : python -m SapFioriLibrary.regen_recorder
    expected = spy_snippet().replace("\r\n", "\n")
    for path in _SPY_FILES:
        with open(path, "r", encoding="utf-8") as fh:
            on_disk = fh.read().replace("\r\n", "\n")
        assert on_disk == expected, (
            "%s is out of sync with _ui5_js.py: run "
            "`python -m SapFioriLibrary.regen_recorder`." % path
        )
