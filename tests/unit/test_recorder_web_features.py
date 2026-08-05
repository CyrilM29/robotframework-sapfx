"""Tests unitaires hors navigateur des NOUVEAUTÉS du recorder web (2026-07) :
capture du moteur dom générique, compaction des steps, menu contextuel
d'assertions, capture d'Entrée, attente UI5 intelligente, alerte frames
cross-origin et exports resource-first / spec.

La logique vit dans le JS généré (``_ui5_js.py``, source unique de vérité,
cf. ``regen_recorder``) : comme ``test_sid_and_spy.py``, on verrouille les
contrats par assertion sur le contenu du bundle et du listener générés, plus
la synchronisation des artefacts écrits sous ``tools/recorder_web/``.
"""
import json
import os

from SapFioriLibrary._ui5_js import BUNDLE, spy_snippet

_RECORDER_WEB = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder_web"))

SNIPPET = spy_snippet()


# --- capture du moteur dom générique (5e moteur, zones non-SAP) ---------------

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
    assert "return 'role=' + d.role + '    name=' + cleanCell(d.name);" in SNIPPET
    assert "return 'css=' + d.css;" in SNIPPET


# --- compaction du déroulé ----------------------------------------------------

def test_listener_compacts_refills_and_consecutive_waits():
    assert "function fillKey(line)" in SNIPPET
    # re-saisie du même champ = remplacement du dernier step, pas un empilement
    assert "fillKey(last) === fillKey(line)" in SNIPPET
    assert "WAIT_STEPS" in SNIPPET


# --- assertions : menu contextuel + raccourcis conservés ----------------------

def test_listener_opens_assertion_menu_on_right_click_while_recording():
    assert "function onContextMenu(event)" in SNIPPET
    assert "addEventListener('contextmenu', onContextMenu, true)" in SNIPPET
    assert "removeEventListener('contextmenu', onContextMenu, true)" in SNIPPET
    # assertions texte des moteurs sans keyword direct : paire Get + Should Be Equal
    assert "${texte} =    Get Wc Text" in SNIPPET
    assert "${texte} =    Get Dom Text" in SNIPPET
    # les raccourcis historiques restent (Alt+clic / Shift+Alt+clic)
    assert "event.altKey && cap" in SNIPPET


# --- clavier : Entrée capturée (différée après le change) ---------------------

def test_listener_captures_enter_deferred_and_skips_textarea():
    assert "Keyboard Key    press    Enter" in SNIPPET
    assert "setTimeout" in SNIPPET
    assert "tag !== 'textarea'" in SNIPPET


# --- navigation : attente UI5 quand le runtime est là -------------------------

def test_nav_emits_ui5_ready_or_load_state():
    assert "window.__SAPFX.isUI5() ? 'Wait For UI5 Ready' : 'Wait For Load State    load'" \
        in SNIPPET


def test_exports_embed_the_ui5_ready_keyword_definition():
    # le .robot exporté reste AUTONOME : le keyword est copié dans le fichier
    assert "UI5_READY_KEYWORD" in SNIPPET
    assert "Wait For Function    () => { const s = window.sap;" in SNIPPET
    assert "message=UI5 runtime did not become idle" in SNIPPET


# --- alerte frames cross-origin -----------------------------------------------

def test_panel_warns_about_cross_origin_frames():
    assert "crossOriginFrameCount" in SNIPPET
    assert "cross-origin" in SNIPPET
    assert "allFrames" in SNIPPET


# --- exports : menu à 3 formats, resource-first, spec -------------------------

def test_export_menu_offers_four_formats():
    assert "'.robot complet'" in SNIPPET
    assert "resource-first (.resource + .robot)" in SNIPPET
    assert "plan specs/ (.spec.md)" in SNIPPET
    assert "rapport HTML (.html)" in SNIPPET


def test_resource_first_export_wraps_all_engines():
    assert "function buildResourceFirst()" in SNIPPET
    for kw in ("'Click Ui5 Control'", "'Click Sid'", "'Click Wc Control'",
               "'Click Dom Element'", "'Fill Ui5 Input'", "'Fill Sid Input'",
               "'Fill Wc Input'", "'Fill Dom Input'", "'Ui5 Text Should Be'"):
        assert kw in SNIPPET, kw
    assert "Resource    recorded_keywords.resource" in SNIPPET
    assert "recorded_keywords.resource" in SNIPPET


def test_spec_export_follows_specs_contract():
    assert "function buildSpec()" in SNIPPET
    # étapes humanisées, localisateurs relégués en vigilance
    assert "function humanizeWebStep(line, fmt)" in SNIPPET
    assert "Points de vigilance" in SNIPPET
    assert "sap-generator" in SNIPPET


def test_report_export_is_a_self_contained_html_documentation():
    # Concept observé chez RoboSAPiens (saveHtmlReport, NOTICE) : rapport HTML
    # auto-contenu, phrase métier + ligne RF exacte par step, contenu échappé.
    assert "function buildReport()" in SNIPPET
    assert "function escapeHtml(t)" in SNIPPET
    assert "recorded_report.html" in SNIPPET
    # les phrases métier du rapport réutilisent humanizeWebStep avec un
    # formateur guillemets (jamais les backticks Markdown de l'export spec)
    assert "humanizeWebStep(line, quote)" in SNIPPET
    # la ligne RF exacte reste en regard : le rapport n'invente rien
    assert "<p class=\"raw\"><code>' + escapeHtml(line)" in SNIPPET


# --- replay in-page (« play ») ------------------------------------------------

def test_listener_replays_steps_in_page():
    assert "function playSteps()" in SNIPPET
    assert "function executeStep(line, vars, done)" in SNIPPET
    # les clics/saisies synthétiques du replay ne se ré-enregistrent jamais
    assert "if (replaying) return;" in SNIPPET
    # le repli xpath (posé à l'enregistrement) est essayé quand le sélecteur
    # primaire ne résout plus
    assert "resolveByXPath(xpath)" in SNIPPET
    assert "play: playSteps" in SNIPPET
    # arrêt au premier échec, ligne marquée
    assert "replayState.failed = i;" in SNIPPET


def test_replay_resolves_via_the_same_engines():
    assert "function findBySid(sid)" in SNIPPET       # WebGUI lsdata (2 encodages)
    assert "function findWc(cells)" in SNIPPET
    assert "function findDom(cells)" in SNIPPET
    assert "function waitUi5Idle(" in SNIPPET         # Wait For UI5 Ready rejouable


# --- repli xpath par step (naissance auto-réparable) --------------------------

def test_recorded_ui5_steps_carry_their_xpath_fallback():
    assert "function withXpathHint(line, cap)" in SNIPPET
    assert "withXpathHint(clickLine(cap), cap)" in SNIPPET
    assert "withXpathHint(fillLine(cap, value), cap)" in SNIPPET


def test_resource_first_converts_xpath_hint_into_fallback_resolution():
    assert "Resolve Ui5 With Fallback    xpath=" in SNIPPET
    assert "Click    ${cible}" in SNIPPET


def test_panel_header_fits_its_buttons_on_one_line():
    """À 380 px l'en-tête débordait ses 7 boutons et `overflow:hidden` rognait
    « stop », inatteignable à la souris (vu à l'image sur une app Fiori Elements).
    Le titre doit s'ellipser, les boutons ne jamais être compressés.
    """
    assert "width:470px" in SNIPPET
    assert "width:380px" not in SNIPPET
    assert "text-overflow:ellipsis" in SNIPPET
    assert "flex:0 0 auto;white-space:nowrap" in SNIPPET


def test_resource_first_fill_targets_the_inner_input_of_a_composite_control():
    """Un champ UI5 composite (sap.m.Input, SearchField) a une <div> pour racine :
    remplir la racine échoue (« Element is not an <input> »). Le keyword généré doit
    descendre dans l'élément interne, comme le fait Fill Ui5 Input.

    Régression attrapée par le run LIVE de la paire exportée contre une app Fiori
    Elements (cap-sflight) ; le dryrun, lui, passait.
    """
    assert "Fill Text    ${cible} >> css=input, textarea    ${valeur}" in SNIPPET
    assert "Fill Text    ${cible}    ${valeur}" not in SNIPPET


# --- multi-scénarios ----------------------------------------------------------

def test_multi_scenario_markers_split_every_export():
    assert "function splitScenarios()" in SNIPPET
    assert "TEST_MARKER" in SNIPPET
    assert "addTestMarker" in SNIPPET                 # API (+ bouton +test)
    # le bootstrap New Browser/New Page ne vit que dans le premier test
    assert "if (gi === 0)" in SNIPPET


# --- import d'un .robot exporté -----------------------------------------------

def test_import_robot_round_trips_steps():
    assert "function parseRobotSuite(text)" in SNIPPET
    assert "applyImportedText" in SNIPPET
    assert "importer un .robot" in SNIPPET            # entrée du menu export
    assert "importRobotText" in SNIPPET               # API testable


# --- édition in-place ---------------------------------------------------------

def test_steps_are_editable_in_place():
    assert "function startEditStep(i, row, txt)" in SNIPPET
    assert "dblclick" in SNIPPET


# --- régression attrapée par le smoke live (2026-07-19) -----------------------

def test_download_anchor_is_parented_to_the_panel_not_the_document():
    # L'ancre de téléchargement doit vivre DANS le panneau (inOurUI) : sinon la
    # capture dom intercepte son propre clic synthétique : une ancre href a le
    # rôle 'link', donc cible interactive → preventDefault → téléchargement
    # annulé. Attrapé live par recorder_web_smoke lors du passage à captureDom.
    assert "panel.appendChild(a);" in SNIPPET
    assert "document.documentElement.appendChild(a);" not in SNIPPET


# --- synchronisation des artefacts générés + extension ------------------------

def test_generated_recorder_files_are_in_sync_with_source():
    for name in ("recorder_snippet.js", os.path.join("extension", "recorder.js")):
        path = os.path.join(_RECORDER_WEB, name)
        with open(path, "r", encoding="utf-8") as fh:
            assert fh.read() == SNIPPET, "%s diverge : python -m SapFioriLibrary.regen_recorder" % name


def test_extension_manifest_bumped_for_recorder_features():
    with open(os.path.join(_RECORDER_WEB, "extension", "manifest.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["version"] == "0.9.2"
    # Le Chrome Web Store refuse une description > 132 caractères : bloquant
    # de soumission attrapé lors de la revue croisée avec rf-web-recorder.
    assert len(manifest["description"]) <= 132
    # scripting world MAIN nécessite Chrome 111+ : l'annoncer évite des
    # installations cassées sur les Chrome plus anciens.
    assert manifest["minimum_chrome_version"] == "111"


# --- corrections de la revue de pair (2026-07-20) -----------------------------

def test_bundle_normalizes_whitespace_for_text_and_name_matching():
    # le nom/texte ENREGISTRÉ est à espaces simples (cellule RF) : le haystack
    # DOM (textContent indenté, multi-nœuds) doit être replié pareil, sinon un
    # `name=` capturé ne re-résout jamais
    assert "function wsCollapse(s)" in BUNDLE
    assert "valueMatches(wsCollapse(el.textContent), sel.text)" in BUNDLE
    assert "valueMatches(wsCollapse(accName(el)), sel.name)" in BUNDLE
    # la capture wc normalise aussi son texte (un retour à la ligne dans une
    # cellule RF est invalide)
    assert "const txt = wsCollapse(el.textContent).slice(0, 80);" in BUNDLE


def test_listener_dedup_window_also_covers_keyboard_key():
    # deux Entrées volontaires (double validation) au-delà de la fenêtre de
    # 500 ms produisent bien deux steps : même exemption que les clics
    assert "/^(Click |Keyboard Key)/" in SNIPPET


def test_listener_wraps_text_assertion_pairs_in_resource_first():
    # la paire `${texte} = Get Wc/Dom Text` + `Should Be Equal` devient UN
    # keyword métier dans l'export resource-first (convention n°1 : aucun
    # localisateur dans la suite)
    assert "function textAssertPair(line, nextLine)" in SNIPPET
    assert "function wrapTextAssert(pair)" in SNIPPET
    assert "${valeur_attendue}" in SNIPPET


def test_listener_spec_export_keeps_locator_bearing_raw_steps_out_of_steps():
    # étape inconnue AVEC localisateur : la ligne exacte vit en « Points de
    # vigilance », pas dans les étapes (contrat specs/)
    assert "technique \\u00e0 traduire" in SNIPPET
    assert "hasLocator" in SNIPPET


# --- portages rf-web-recorder 0.4.1 (2026-08-05) ------------------------------

def test_listener_masks_password_payment_and_otp_fields():
    # password -> <REDACTED> (graphie UI5 WC 'Password' incluse) ; paiement et
    # OTP -> <SECRET>, via tokens autocomplete OU motifs name/id/aria-label
    # (portage rf-web-recorder : les vraies valeurs n'atteignent jamais
    # recorded.robot / sessionStorage / le presse-papiers)
    assert "function sensitiveMask(t)" in SNIPPET
    assert "'<REDACTED>'" in SNIPPET
    assert "'<SECRET>'" in SNIPPET
    assert "cc-number|cc-csc|cc-exp(-month|-year)?|one-time-code" in SNIPPET
    assert "current-password|new-password" in SNIPPET
    assert "cvv|cvc|card.?number" in SNIPPET
    # le masque s'applique AVANT l'échappement RF : la vraie valeur n'entre
    # jamais dans un step, quel que soit le moteur (cap/sid/wc/dom)
    assert "var mask = sensitiveMask(t);" in SNIPPET
    assert "var value = mask || rfEscape(t.value, true);" in SNIPPET
    # tout champ masqué (plus seulement password) garde sa ligne xpath de
    # secours : le locator reste exploitable pour rebrancher une vraie valeur
    assert "if (mask) {" in SNIPPET


def test_listener_copy_has_honest_execcommand_fallback():
    # sans navigator.clipboard (origine http non sécurisée : WebGUI intranet),
    # le repli execCommand copie réellement ; le bouton n'affiche jamais un
    # « copied » optimiste quand rien n'a été copié
    assert "function legacyCopy()" in SNIPPET
    assert "document.execCommand && document.execCommand('copy')" in SNIPPET
    assert "flash(ok ? 'copied' : 'copy failed');" in SNIPPET
    # writeText rejeté = repli tenté (pas un simple 'copy failed')
    assert "p.then(function () { flash('copied'); }, legacyCopy);" in SNIPPET
    assert "} catch (e) { legacyCopy(); }" in SNIPPET


def test_listener_storage_and_download_failures_are_surfaced():
    # écriture sessionStorage en échec = console.warn UNE seule fois (sinon
    # les steps se perdent en silence au rechargement) ; download() en échec =
    # message dans le bandeau du panneau, la copie presse-papiers en secours
    assert "function warnStorage(e)" in SNIPPET
    assert "if (storageWarned) return;" in SNIPPET
    assert "catch (e) { warnStorage(e); }" in SNIPPET
    assert "\\u00c9chec du t\\u00e9l\\u00e9chargement de " in SNIPPET
    assert "Utiliser la copie presse-papiers." in SNIPPET


def test_listener_exports_bootstrap_on_recording_start_url():
    # portage rf-web-recorder : New Page amorce l'URL de DÉBUT d'enregistrement
    # (mémorisée au premier rec, jamais écrasée par la reprise post-navigation),
    # pas l'URL du moment de l'export. Constaté live sur OrangeHRM : un record
    # login -> dashboard exporté depuis le dashboard rejouait au mauvais
    # endroit. clear purge l'URL, l'import d'un .robot la restaure (round-trip).
    assert "var URL_KEY = '__ui5RecorderStartUrl';" in SNIPPET
    assert "function rememberUrl()" in SNIPPET
    assert ("if (!sessionStorage.getItem(URL_KEY)) "
            "sessionStorage.setItem(URL_KEY, location.href);") in SNIPPET
    assert "if (on) rememberUrl();" in SNIPPET
    # les DEUX bootstraps (.robot complet + paire resource-first) et les DEUX
    # documents (spec, rapport) parlent de l'URL de départ
    assert SNIPPET.count("New Page    ' + startUrl()") == 2
    assert "New Page    ' + location.href" not in SNIPPET
    assert "' + startUrl() + '\\n';" in SNIPPET
    assert "escapeHtml(startUrl())" in SNIPPET
    assert "sessionStorage.removeItem(URL_KEY);" in SNIPPET
    assert "trimmed.match(/^New Page\\s{2,}(\\S+)/)" in SNIPPET


def test_listener_panel_carries_the_aicabra_icon_and_drag_affordance():
    # picto aicabra en data-URI (bundle auto-contenu : aucune requete reseau),
    # repli silencieux si une CSP img-src stricte bloque data:, et l'indice de
    # deplacement (title + cursor move) sur l'en-tete DEJA draggable
    from SapFioriLibrary._ui5_js import _AICABRA_ICON, spy_snippet
    assert _AICABRA_ICON.startswith("data:image/png;base64,")
    rendered = spy_snippet()
    assert "__AICABRA_ICON__" not in rendered          # token remplace au rendu
    assert _AICABRA_ICON in rendered
    assert "logo.onerror = function () { logo.style.display = 'none'; };" in SNIPPET
    assert "head.appendChild(logo);" in SNIPPET
    assert "SAPFX Recorder : glisser l\\'en-t\\u00eate" in SNIPPET
