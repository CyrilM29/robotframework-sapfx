"""Tests unitaires hors SAP des NOUVEAUTÉS du recorder bureau (2026-07) :
exports post-enregistrement (suite complète, resource-first, plan specs/),
assertions à chaud (raccourcis Ctrl+Alt+A / Ctrl+Alt+V), suggestion d'offset
pour les zones opaques, mappings natifs étendus (grilles, arbres, menus
contextuels) et helpers du panneau de steps de la GUI (convention #5).

Même chargement par chemin que ``test_desktop_spy.py`` (le recorder vit sous
``tools/``, hors paquet) ; le ``conftest`` voisin fournit le pythoncom factice.
"""
import codecs
import importlib.util
import os

_SPY_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "sapgui_recorder.py"))
_GUI_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "recorder_gui.py"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spy = _load(_SPY_PATH, "sapgui_recorder")
gui = _load(_GUI_PATH, "recorder_gui")


# --- en-tête / relecture / réécriture du fichier d'enregistrement -------------

def test_build_record_header_body_only_keeps_historic_shape():
    header = spy.build_record_header("captures/x.robot")
    assert header.startswith("# Enregistré par SAP GUI Recorder : captures/x.robot")
    assert "*** Settings ***" not in header
    assert header.rstrip().endswith("*** Test Cases ***\n" + spy.DEFAULT_TEST_NAME)


def test_build_record_header_suite_is_replayable():
    header = spy.build_record_header("captures/x.robot", suite=True)
    assert "*** Settings ***" in header
    assert "Library             SapEccLibrary" in header
    # Attach To Open Session, PAS Connect To Session : ce dernier n'obtient que
    # le moteur de scripting, jamais la session (replay impossible, attrapé par
    # le replay live d'un export le 2026-07-19).
    assert "Suite Setup         Attach To Open Session" in header
    assert "Connect To Session\n" not in header
    assert header.index("*** Settings ***") < header.index("*** Test Cases ***")


def test_build_record_header_with_resource_adds_import():
    header = spy.build_record_header("x", resource_file="record_keywords.resource")
    assert "Resource            record_keywords.resource" in header


def test_parse_recorded_body_reads_name_and_steps_from_body_and_suite():
    body = spy.build_record_header("x") + "    Input Text    wnd[0]/usr/txtA    1\n" \
        "    # screenshot: shot.png\n    Send Vkey    0\n"
    name, steps = spy.parse_recorded_body(body)
    assert name == spy.DEFAULT_TEST_NAME
    assert steps == ["Input Text    wnd[0]/usr/txtA    1",
                     "# screenshot: shot.png", "Send Vkey    0"]
    suite = spy.build_record_header("x", suite=True) + "    Run Transaction    SE16\n"
    _name, steps = spy.parse_recorded_body(suite)
    assert steps == ["Run Transaction    SE16"]


def test_replace_recorded_steps_preserves_header_and_swaps_steps():
    text = spy.build_record_header("x", suite=True) + "    Ancien Step\n    Autre\n"
    new = spy.replace_recorded_steps(text, ["Nouveau Step"])
    assert "Ancien Step" not in new and "Autre" not in new
    assert new.endswith("    Nouveau Step\n")
    assert "Suite Setup         Attach To Open Session" in new
    # round-trip : la relecture voit exactement les nouvelles étapes
    _n, steps = spy.parse_recorded_body(new)
    assert steps == ["Nouveau Step"]


# --- export resource-first ----------------------------------------------------

def test_locator_slug_strips_type_prefix_and_sanitizes():
    assert spy.locator_slug("wnd[0]/usr/ctxtDATABROWSE-TABLENAME") == "DATABROWSE_TABLENAME"
    assert spy.locator_slug("wnd[0]/tbar[1]/btn[31]") == "31"
    assert spy.locator_slug("") == "ELEMENT"


def test_resource_first_wraps_ids_and_keeps_business_lines():
    steps = ["Run Transaction    SE16",
             "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000",
             "Click Toolbar Button    wnd[0]/tbar[1]    btn[31]",
             "Send Vkey    0    # Enter"]
    resource, suite = spy.steps_to_resource_first(steps, "Mon test")
    # le resource porte la variable et les keywords métier
    assert "${LOC_DATABROWSE_TABLENAME}    wnd[0]/usr/ctxtDATABROWSE-TABLENAME" in resource
    assert "Saisir DATABROWSE_TABLENAME" in resource
    assert "[Arguments]    ${valeur}" in resource
    assert "Cliquer Bouton 31" in resource
    # la suite ne contient PLUS AUCUN id brut (convention n°1)
    assert "wnd[" not in suite
    assert "Saisir DATABROWSE_TABLENAME    T000" in suite
    assert "Run Transaction    SE16" in suite
    assert "Send Vkey    0    # Enter" in suite
    assert "Resource            record_keywords.resource" in suite


def test_resource_first_reuses_keyword_for_same_id_and_dedups_collisions():
    steps = ["Input Text    wnd[0]/usr/txtA-B    1",
             "Input Text    wnd[0]/usr/txtA-B    2",     # même id -> même keyword
             "Input Text    wnd[1]/usr/ctxtA-B    3"]    # même slug, autre id -> suffixe
    resource, suite = spy.steps_to_resource_first(steps)
    assert resource.count("Saisir A_B\n") == 1
    assert "${LOC_A_B_2}" in resource
    assert "Saisir A_B    1" in suite and "Saisir A_B    2" in suite


def test_resource_first_wraps_assertions_and_password():
    steps = ["Input Password    wnd[0]/usr/pwdRSYST-BCODE    <password>",
             "Element Value Should Be    wnd[0]/usr/txtCOUNT    205"]
    resource, suite = spy.steps_to_resource_first(steps)
    assert "Saisir Mot De Passe RSYST_BCODE" in resource
    assert "Vérifier COUNT" in resource
    assert "Vérifier COUNT    205" in suite
    assert "wnd[" not in suite


# --- export spec (plan specs/) ------------------------------------------------

def test_spec_export_has_no_raw_ids_in_steps_and_lists_them_in_vigilance():
    steps = ["Run Transaction    SE16",
             "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000",
             "Send Vkey    0    # Enter",
             "Element Value Should Be    wnd[0]/usr/txtG_DBCOUNT    100"]
    md = spy.steps_to_spec(steps, "Comptage T000")
    etapes = md.split("## Scénarios")[1].split("## Points de vigilance")[0]
    assert "wnd[" not in etapes                      # contrat specs/ : pas d'id dans les étapes
    assert "Lancer la transaction `SE16`" in etapes
    assert "Saisir `T000` dans le champ `DATABROWSE_TABLENAME`" in etapes
    assert "Envoyer la touche `Enter`" in etapes
    assert "Vérifier que `G_DBCOUNT` vaut `100`" in etapes
    vigilance = md.split("## Points de vigilance")[1]
    assert "`wnd[0]/usr/ctxtDATABROWSE-TABLENAME`" in vigilance
    assert "- **Canal** : ECC (SAP GUI)" in md
    assert "Brouillon" in md


def test_spec_export_unknown_step_stays_verbatim_as_raw():
    md = spy.steps_to_spec(["Mon Keyword Exotique    arg"])
    assert "Étape brute à traduire : `Mon Keyword Exotique    arg`" in md


# --- export ISTQB (plan de test + cas de test) --------------------------------

def test_istqb_export_covers_plan_sections_table_and_replay_block():
    steps = ["Run Transaction    SE16",
             "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000",
             "Send Vkey    0",
             "Click Toolbar Button    wnd[0]    wnd[0]/tbar[1]/btn[31]",
             "Element Value Should Be    wnd[1]/usr/txtG_DBCOUNT    1"]
    md = spy.steps_to_istqb(steps, "Comptage T000", source="demo.robot")
    for section in ("## 1. Objectif et périmètre",
                    "## 2. Préconditions et données de test",
                    "## 3. Critères d'entrée / de sortie",
                    "## 4. Cas de test",
                    "## 5. Traçabilité",
                    "## 6. Risques et points de vigilance"):
        assert section in md, section
    assert "- **Identifiant** : TP-comptage-t000" in md
    assert "### TC-01 : Comptage T000" in md
    assert "| # | Action | Données | Résultat attendu |" in md
    assert ("| 2 | Saisir `T000` dans le champ `DATABROWSE_TABLENAME` "
            "| `T000` | La valeur est acceptée |") in md
    # bloc replay : actions normalisées + localisateur relégué en hint
    assert "channel: sap-gui" in md
    assert "  - action: run_transaction" in md
    assert "    value: 'T000'" in md
    assert ("    hint: {engine: 'sapgui-id', "
            "locator: 'wnd[0]/usr/ctxtDATABROWSE-TABLENAME'}") in md
    assert "  - action: assert_value" in md
    assert "    expected: '1'" in md
    # le tableau humain ne porte AUCUN id brut (ils vivent dans les hints)
    table = md.split("| # | Action")[1].split("Bloc rejouable")[0]
    assert "wnd[" not in table
    # la touche pressée est l'action, jamais une donnée
    assert "| 3 | Envoyer la touche `Entrée` |  |" in md
    # accents translittérés dans l'identifiant (attrapé au premier live)
    assert "TP-scenario-enregistre" in spy.steps_to_istqb(
        ["Run Transaction    SE16"], "Scénario enregistré")


def test_istqb_export_semantic_visual_and_unknown_steps():
    steps = ["Fill Field By Label    Table Name    T000"
             "    # id: wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
             "Click Button By Label    Number of Entries",
             "Screen Should Match Baseline    se16_t000",
             "Mon Keyword Exotique    arg"]
    md = spy.steps_to_istqb(steps)
    # l'id relevé par --semantic prime sur l'ancre de libellé
    assert ("hint: {engine: 'sapgui-id', "
            "locator: 'wnd[0]/usr/ctxtDATABROWSE-TABLENAME'}") in md
    assert "hint: {engine: 'sapgui-label', locator: 'Number of Entries'}" in md
    assert "  - action: assert_visual" in md
    # étape inconnue : action raw portant la ligne Robot Framework exacte
    assert "  - action: raw" in md
    assert "    line: 'Mon Keyword Exotique    arg'" in md


def test_istqb_export_never_carries_a_password_and_quotes_yaml():
    steps = ["Input Password    wnd[0]/usr/pwdRSYST-BCODE    secret123",
             "Input Text    wnd[0]/usr/txtX    l'apostrophe"]
    md = spy.steps_to_istqb(steps)
    assert "  - action: fill_secret" in md
    assert "secret123" not in md                     # jamais un mot de passe
    assert "note: 'mot de passe à fournir au replay, jamais enregistré'" in md
    # guillemets simples YAML doublés
    assert "value: 'l''apostrophe'" in md


# --- run_record_exports (E/S autour des fonctions pures) ----------------------

def test_run_record_exports_writes_resource_pair_and_spec(tmp_path):
    out = tmp_path / "demo.robot"
    out.write_text(spy.build_record_header(str(out))
                   + "    Input Text    wnd[0]/usr/txtX    1\n", encoding="utf-8")
    messages = []
    spy.run_record_exports(str(out), export_resources=True, export_spec=True,
                           _writer=messages.append)
    resource = (tmp_path / "demo_keywords.resource").read_text(encoding="utf-8")
    suite = (tmp_path / "demo_resource_first.robot").read_text(encoding="utf-8")
    spec = (tmp_path / "demo.spec.md").read_text(encoding="utf-8")
    assert "${LOC_X}" in resource and "Saisir X    1" in suite and "# " in spec
    # l'enregistrement BRUT n'est jamais modifié
    assert "Input Text    wnd[0]/usr/txtX    1" in out.read_text(encoding="utf-8")
    assert any("resource-first" in m for m in messages)


def test_run_record_exports_writes_istqb(tmp_path):
    out = tmp_path / "demo.robot"
    out.write_text(spy.build_record_header(str(out))
                   + "    Input Text    wnd[0]/usr/txtX    1\n", encoding="utf-8")
    messages = []
    spy.run_record_exports(str(out), export_istqb=True, _writer=messages.append)
    md = (tmp_path / "demo.istqb.md").read_text(encoding="utf-8")
    assert "# Plan de test ISTQB :" in md and "channel: sap-gui" in md
    assert "- **Références** : `demo.robot`" in md
    # l'enregistrement BRUT n'est jamais modifié
    assert "Input Text    wnd[0]/usr/txtX    1" in out.read_text(encoding="utf-8")
    assert any("ISTQB" in m for m in messages)


def test_run_record_exports_noop_without_flags(tmp_path):
    out = tmp_path / "demo.robot"
    spy.run_record_exports(str(out))                 # fichier absent : silencieux
    assert list(tmp_path.iterdir()) == []


# --- export rapport HTML (documentation d'un enregistrement) ------------------
# Concept observé chez RoboSAPiens (saveHtmlReport, NOTICE) ; réimplémenté par
# STEP, texte -> texte pur, chargeur de captures injectable.

def test_report_documents_steps_with_human_phrase_and_exact_line():
    steps = ["Run Transaction    SE16",
             "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000",
             "Send Vkey    0    # Enter"]
    page = spy.steps_to_report(steps, "Mon test", source="demo.robot")
    assert page.startswith("<!doctype html>")
    assert "<title>Mon test</title>" in page
    assert "3 étape(s)" in page and "demo.robot" in page
    # phrase métier SANS les backticks Markdown de l'export spec…
    assert "Saisir T000 dans le champ DATABROWSE_TABLENAME" in page
    # …et la ligne RF exacte en regard : le rapport n'invente rien
    assert "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000" in page
    # auto-contenu : aucun script, aucune ressource externe
    assert "<script" not in page and 'src="http' not in page


def test_report_attaches_screenshots_to_previous_step_and_flags_missing():
    steps = ["Send Vkey    0",
             "# screenshot: shots/step_001.png",
             "# screenshot: shots/step_002.png"]

    def loader(path):
        return ("image/png", b"\x89PNG-fake") if path.endswith("step_001.png") else None

    page = spy.steps_to_report(steps, screenshot_loader=loader)
    assert "data:image/png;base64," in page
    # capture illisible = mention honnête nommant le fichier, jamais un silence
    assert "Capture introuvable" in page and "step_002.png" in page


def test_report_screenshot_before_any_step_becomes_initial_state():
    page = spy.steps_to_report(["# screenshot: a.png"])   # sans chargeur
    assert "État initial" in page
    assert "Capture introuvable" in page


def test_report_escapes_html_in_recorded_values():
    page = spy.steps_to_report(["Input Text    wnd[0]/usr/txtX    <b>gras</b>"])
    assert "<b>" not in page and "&lt;b&gt;" in page


def test_report_covers_fiori_and_api_channels():
    # déroulé mixte cross-canal : écran UI5, navigation FLP, recoupement OData
    steps = ["Click Ui5 Control    controlType=Button    properties={'text': 'Go'}",
             "Fill Ui5 Input    Aussie    idSuffix=fe::FilterBar::Travel::BasicSearchField",
             "Open App By Intent    Travel-manage",
             "Get Odata Count    SEPMRA_SHOP/Products",
             "Open Api Session    http://host:50000/sap/opu/odata    "
             "user=DEVELOPER    password=Secret123"]
    page = spy.steps_to_report(steps)
    assert "Cliquer le contrôle" in page
    assert "Saisir Aussie dans le contrôle" in page
    assert "Ouvrir l'app Fiori Travel-manage" in page
    assert "Compter les entités OData SEPMRA_SHOP/Products" in page
    # un rapport ne montre JAMAIS un secret : argument nommé masqué
    assert "Secret123" not in page and "password=***" in page


def test_strip_md_code_unwraps_nested_backticks():
    assert spy._strip_md_code("Saisir `T000` dans `X`") == "Saisir T000 dans X"
    # un code span md_code à clôture longue (contenu portant des backticks)
    assert spy._strip_md_code("Valeur %s" % spy.md_code("`tick`")) == "Valeur `tick`"


def test_report_screenshot_loader_resolves_paths_and_rejects_unknown(tmp_path):
    shots = tmp_path / "rec_shots"
    shots.mkdir()
    (shots / "s.png").write_bytes(b"\x89PNG")
    (shots / "s.txt").write_bytes(b"x")
    loader = spy.report_screenshot_loader(str(tmp_path))
    # relatif : résolu depuis le dossier de l'enregistrement ; absolu : tel quel
    assert loader(os.path.join("rec_shots", "s.png")) == ("image/png", b"\x89PNG")
    assert loader(str(shots / "s.png")) == ("image/png", b"\x89PNG")
    assert loader("absent.png") is None
    assert loader(str(shots / "s.txt")) is None      # extension inconnue


def test_run_record_exports_writes_report(tmp_path):
    out = tmp_path / "demo.robot"
    shots = tmp_path / "demo_shots"
    shots.mkdir()
    (shots / "step_001.png").write_bytes(b"\x89PNG-fake")
    out.write_text(spy.build_record_header(str(out))
                   + "    Input Text    wnd[0]/usr/txtX    1\n"
                   + "    # screenshot: %s\n" % (shots / "step_001.png"),
                   encoding="utf-8")
    messages = []
    spy.run_record_exports(str(out), export_report=True, _writer=messages.append)
    report = (tmp_path / "demo_report.html").read_text(encoding="utf-8")
    assert "data:image/png;base64," in report
    assert any("rapport" in m for m in messages)
    # l'enregistrement BRUT n'est jamais modifié
    assert "Input Text    wnd[0]/usr/txtX    1" in out.read_text(encoding="utf-8")


# --- noms de vkeys : table statique + résolveur GetVKeyDescription ------------

def test_vkey_comment_uses_session_resolver_beyond_static_table():
    assert spy._vkey_comment(8) == "    # F8"        # table statique prioritaire
    calls = []

    def resolver(code):
        calls.append(code)
        return "  Shift+F5\n"

    previous = spy.set_vkey_resolver(resolver)
    try:
        assert spy._vkey_comment(17) == "    # Shift+F5"   # blancs normalisés
        assert spy._vkey_comment(8) == "    # F8" and calls == [17]
    finally:
        spy.set_vkey_resolver(previous)
    assert spy._vkey_comment(17) == ""               # résolveur débranché


def test_vkey_resolver_failure_never_crashes():
    def boom(code):
        raise RuntimeError("COM en échec")

    previous = spy.set_vkey_resolver(boom)
    try:
        assert spy._vkey_comment(17) == ""
    finally:
        spy.set_vkey_resolver(previous)


# --- assertions à chaud (hotkeys) --------------------------------------------

def test_hotkey_poller_fires_on_rising_edge_only():
    pressed = {"keys": set()}

    def key_state(code):
        return 0x8000 if code in pressed["keys"] else 0

    poll = spy.make_hotkey_poller(key_state)
    assert poll() is None
    pressed["keys"] = {0x11, 0x12, 0x41}             # Ctrl+Alt+A enfoncé
    assert poll() == "value"
    assert poll() is None                            # tenu : ne re-déclenche pas
    pressed["keys"] = set()
    assert poll() is None
    pressed["keys"] = {0x11, 0x12, 0x56}             # Ctrl+Alt+V
    assert poll() == "visual"


def test_assertion_step_prefers_value_but_never_for_passwords():
    assert spy.assertion_step_for_element("wnd[0]/usr/txtA", "GuiTextField", "T000") \
        == "Element Value Should Be    wnd[0]/usr/txtA    T000"
    assert spy.assertion_step_for_element("wnd[0]/usr/pwdA", "GuiPasswordField", "secret") \
        == "Element Should Be Present    wnd[0]/usr/pwdA"
    assert spy.assertion_step_for_element("wnd[0]/usr/btnB", "GuiButton", "") \
        == "Element Should Be Present    wnd[0]/usr/btnB"
    assert spy.assertion_step_for_element("", "GuiTextField", "x") is None


def test_visual_assertion_step_sanitizes_baseline_name():
    assert spy.visual_assertion_step("record 2026!", 3) \
        == "Screen Should Match Baseline    record_2026_etape_03"


# --- suggestion d'offset (zones opaques) --------------------------------------

def test_offset_suggestion_only_for_opaque_types_with_cursor_inside():
    rect = (100, 200, 200, 100)
    line = spy.offset_suggestion("GuiShell", "wnd[0]/usr/shell", rect, 150, 250)
    assert line.startswith("Click Element At Offset    wnd[0]/usr/shell    0.25    0.50")
    # type scriptable -> pas de suggestion ; curseur hors rect -> pas de suggestion
    assert spy.offset_suggestion("GuiButton", "wnd[0]/tbar[0]/btn[0]", rect, 150, 250) is None
    assert spy.offset_suggestion("GuiShell", "wnd[0]/usr/shell", rect, 10, 10) is None
    assert spy.offset_suggestion("GuiShell", "wnd[0]/usr/shell", None, 150, 250) is None


# --- mappings natifs étendus --------------------------------------------------

def test_map_change_selected_rows_single_row_maps_to_keyword():
    line = spy.map_change_command("wnd[0]/usr/cntlGRID1/shellcont/shell", "GuiShell",
                                  ["SP", "selectedRows", "3"])
    assert line == "Select Table Row    wnd[0]/usr/cntlGRID1/shellcont/shell    3"
    ranged = spy.map_change_command("g", "GuiShell", ["SP", "selectedRows", "1-4"])
    assert ranged.startswith("# grille g : sélection de lignes '1-4'")


def test_map_change_tree_nodes_map_to_select_node():
    assert spy.map_change_command("tree", "GuiShell", ["M", "selectNode", "N42"]) \
        == "Select Node    tree    N42"
    assert spy.map_change_command("tree", "GuiShell", ["M", "expandNode", "N42"]) \
        == "Select Node    tree    N42    True"


def test_process_change_pairs_context_menu_button_and_item():
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("M", "pressToolbarContextButton", "&MB_EXPORT"))
    assert lines == []                               # bouton retenu, rien d'émis
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("M", "selectContextMenuItem", "&PC"))
    assert lines == ["Select Context Menu Item    grid    &MB_EXPORT    &PC"]
    assert state.get("ctx_button") is None           # consommé


def test_process_change_tracks_current_cell_for_grid_clicks():
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("SP", "currentCellRow", "5"))
    assert lines == []
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("SP", "currentCellColumn", "CARRID"))
    assert lines == []
    state, lines = spy.process_change(state, "grid", "GuiShell",
                                      ("M", "doubleClickCurrentCell"))
    assert lines == ["# grille grid : double-clic cellule ligne 5, colonne CARRID"
                     ", lecture : Get Cell Value    grid    5    CARRID"]


def test_process_change_okcode_flow_still_merges_into_run_transaction():
    # non-régression : le flux OK-code + Entrée -> Run Transaction est inchangé
    state = spy.initial_native_state()
    state, lines = spy.process_change(state, "wnd[0]/tbar[0]/okcd", "GuiOkCodeField",
                                      ("SP", "text", "SE16"))
    assert lines == []
    state, lines = spy.process_change(state, "wnd[0]", "GuiMainWindow",
                                      ("M", "sendVKey", "0"))
    assert lines == ["Run Transaction    SE16"]


# --- export resource-first AUTO-RÉPARABLE (lignes sémantiques + # id:) --------

def test_resource_first_semantic_lines_become_healing_keywords():
    steps = ["Fill Field By Label    Table Name    T000"
             "    # id: wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
             "Click Button By Label    Execute    # id: wnd[0]/tbar[1]/btn[8]"]
    resource, suite = spy.steps_to_resource_first(steps)
    assert ("Resolve Element With Healing    ${LOC_DATABROWSE_TABLENAME}"
            "    label=Table Name") in resource
    assert "Input Text    ${cible}    ${valeur}" in resource
    assert "Resolve Element With Healing    ${LOC_8}    label=Execute" in resource
    assert "Click Element    ${cible}" in resource
    assert "Saisir DATABROWSE_TABLENAME    T000" in suite
    assert "Cliquer 8" in suite
    assert "wnd[" not in suite                       # convention n°1 intacte


# --- transpile VBS (enregistrements ALT+F12) ----------------------------------

_VBS_SAMPLE = """\
If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
' commentaire VBS
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nse16"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").text = "T000"
session.findById("wnd[0]/tbar[1]/btn[8]").press
session.findById("wnd[0]/usr/chkFLAG").selected = true
"""


def test_transpile_vbs_merges_okcode_and_maps_actions():
    steps = spy.transpile_vbs(_VBS_SAMPLE)
    joined = "\n".join(steps)
    assert "Run Transaction    /nse16" in joined     # fusion OK-code + Entrée
    assert "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000" in joined
    assert "Click Element    wnd[0]/tbar[1]/btn[8]" in joined
    assert "Select Checkbox    wnd[0]/usr/chkFLAG" in joined
    # commande sans keyword -> commentaire, jamais perdue en silence
    assert any(s.startswith("# non mappé") and "maximize" in s for s in steps)


def test_transpile_vbs_keeps_quoted_commas_together():
    steps = spy.transpile_vbs('session.findById("g").selectContextMenuItem "A,B"')
    assert any("A,B" in s for s in steps)


def test_transpile_vbs_flushes_trailing_okcode():
    steps = spy.transpile_vbs('session.findById("wnd[0]/tbar[0]/okcd").text = "/nex"')
    assert steps == ["Run Transaction    /nex"]


def test_default_replay_lib_disables_screenshot_handler(monkeypatch):
    # Hors contexte Robot, le handler screenshot d'échec remplacerait l'erreur
    # réelle du step par « Cannot access execution context » (constaté live
    # 2026-07-21, l'échec du replay devenait indiagnosticable) : la fabrique
    # CLI du replay doit désarmer screenshots_on_error.
    import sys
    import types
    calls = {}

    class StubLib:
        def __init__(self, screenshots_on_error=True):
            calls["screenshots_on_error"] = screenshots_on_error

        def attach_to_open_session(self):
            calls["attached"] = True

    stub = types.ModuleType("SapEccLibrary")
    stub.SapEccLibrary = StubLib
    monkeypatch.setitem(sys.modules, "SapEccLibrary", stub)
    lib = spy._default_replay_lib()
    assert isinstance(lib, StubLib)
    assert calls == {"screenshots_on_error": False, "attached": True}


# --- décodage des sources VBS (encodages du monde réel) ------------------------

# Valeur accentuée dans un littéral : le témoin qui révèle un mauvais décodage.
_VBS_ACCENTED = 'session.findById("wnd[0]/usr/txtNAME").text = "Société Générale"'


def test_decode_vbs_source_utf8_sans_bom():
    assert spy.decode_vbs_source(_VBS_ACCENTED.encode("utf-8")) == _VBS_ACCENTED


def test_decode_vbs_source_utf8_avec_bom():
    data = codecs.BOM_UTF8 + _VBS_ACCENTED.encode("utf-8")
    assert spy.decode_vbs_source(data) == _VBS_ACCENTED


def test_decode_vbs_source_utf16_le_avec_bom():
    # encode("utf-16") écrit le BOM LE : la forme « Unicode » du Bloc-notes
    # et d'``Out-File`` PowerShell 5.1.
    assert spy.decode_vbs_source(_VBS_ACCENTED.encode("utf-16")) == _VBS_ACCENTED


def test_decode_vbs_source_utf16_be_avec_bom():
    data = codecs.BOM_UTF16_BE + _VBS_ACCENTED.encode("utf-16-be")
    assert spy.decode_vbs_source(data) == _VBS_ACCENTED


def test_decode_vbs_source_utf16_le_sans_bom():
    # Le cas perfide : les octets NUL de l'UTF-16 sont du UTF-8 VALIDE,
    # l'ancien décodage UTF-8 forcé « réussissait » et la transpilation
    # sortait 0 step, sans la moindre exception.
    data = _VBS_ACCENTED.encode("utf-16-le")
    assert spy.decode_vbs_source(data) == _VBS_ACCENTED


def test_decode_vbs_source_ansi_cp1252():
    # 'é' en cp1252 = 0xE9 seul, séquence UTF-8 invalide -> repli ANSI.
    # (encodage de repli passé explicitement : déterministe sur toute CI.)
    data = _VBS_ACCENTED.encode("cp1252")
    assert spy.decode_vbs_source(data, ansi_encoding="cp1252") == _VBS_ACCENTED


def test_decode_vbs_source_transpile_utf16_bout_en_bout():
    # Un enregistrement complet en UTF-16 traverse décodage + transpilation.
    steps = spy.transpile_vbs(spy.decode_vbs_source(_VBS_SAMPLE.encode("utf-16")))
    assert "Run Transaction    /nse16" in "\n".join(steps)


# --- replay contre la session ouverte -----------------------------------------

class _FakeReplayLib:
    def __init__(self):
        self.calls = []

    def run_transaction(self, code):
        self.calls.append(("run_transaction", code))

    def input_text(self, eid, value):
        self.calls.append(("input_text", eid, value))

    def send_vkey(self, *args):
        self.calls.append(("send_vkey",) + args)

    def element_value_should_be(self, eid, value):
        self.calls.append(("check", eid, value))
        if value == "BOOM":
            raise AssertionError("valeur inattendue")


def test_replay_runs_methods_in_order_and_skips_comments_and_unknown():
    lib = _FakeReplayLib()
    steps = ["Run Transaction    SE16",
             "# screenshot: x.png",
             "Input Text    wnd[0]/usr/txtA    T000",
             "Send Vkey    0    # Enter",
             "Mon Keyword Site    x"]                # keyword hors bibliothèque
    executed, skipped, failed, _msg = spy.replay_recorded_steps(
        steps, lib, writer=lambda *_a: None)
    assert failed is None
    assert executed == 3 and skipped == 1
    assert lib.calls == [("run_transaction", "SE16"),
                         ("input_text", "wnd[0]/usr/txtA", "T000"),
                         ("send_vkey", "0")]


def test_replay_stops_on_first_failure_with_index_and_message():
    lib = _FakeReplayLib()
    steps = ["Element Value Should Be    wnd[0]/usr/txtA    BOOM",
             "Run Transaction    SE16"]
    executed, _skipped, failed, msg = spy.replay_recorded_steps(
        steps, lib, writer=lambda *_a: None)
    assert failed == 0 and "valeur inattendue" in msg
    assert executed == 0
    assert ("run_transaction", "SE16") not in lib.calls


def test_run_replay_reads_file_attaches_and_reports(tmp_path):
    out = tmp_path / "r.robot"
    out.write_text(spy.build_record_header(str(out), suite=True)
                   + "    Run Transaction    SE16\n", encoding="utf-8")
    lib = _FakeReplayLib()
    messages = []
    rc = spy.run_replay(str(out), _lib_factory=lambda: lib, _writer=messages.append)
    assert rc == 0
    assert ("run_transaction", "SE16") in lib.calls
    assert any("Replay OK" in m for m in messages)


def test_run_replay_fails_cleanly_on_missing_file_or_empty(tmp_path):
    messages = []
    assert spy.run_replay(str(tmp_path / "absent.robot"),
                          _lib_factory=lambda: _FakeReplayLib(),
                          _writer=messages.append) == 1
    empty = tmp_path / "vide.robot"
    empty.write_text(spy.build_record_header(str(empty)), encoding="utf-8")
    assert spy.run_replay(str(empty), _lib_factory=lambda: _FakeReplayLib(),
                          _writer=messages.append) == 1


# --- défaut CLI : suite complète (un .robot produit se lance tel quel) --------

def test_cli_default_writes_complete_suite_with_library(tmp_path):
    # Attrapé au test live du 2026-08-05 : un enregistrement sans --suite
    # produisait un corps nu SANS Library, qui échouait lancé tel quel.
    # Verrouillé par la voie --transpile-vbs (aucune session SAP requise).
    vbs = tmp_path / "rec.vbs"
    vbs.write_text('session.findById("wnd[0]/usr/txtX").text = "1"\n',
                   encoding="utf-8")
    out = tmp_path / "defaut.robot"
    assert spy.main(["--transpile-vbs", str(vbs), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "*** Settings ***" in text
    assert "Library             SapEccLibrary" in text
    assert "Suite Setup         Attach To Open Session" in text
    # --body-only = l'ancien fragment, sur demande explicite seulement
    out2 = tmp_path / "fragment.robot"
    assert spy.main(["--transpile-vbs", str(vbs), "--out", str(out2),
                     "--body-only"]) == 0
    text2 = out2.read_text(encoding="utf-8")
    assert "*** Settings ***" not in text2
    assert text2.lstrip("#").lstrip().startswith("Enregistré par SAP GUI Recorder")


# --- GUI : nouvelles options + panneau de steps -------------------------------

def test_build_args_record_new_flags():
    # suite complète = le DÉFAUT CLI depuis 2026-08-05 : aucun drapeau émis ;
    # décocher la case = --body-only (l'ancien fragment sans Library).
    assert gui.build_args("record") == ["--record"]
    assert gui.build_args("record", suite=True) == ["--record"]
    assert gui.build_args("record", suite=False) == ["--record", "--body-only"]
    assert gui.build_args("record", export_resources=True, export_spec=True) == \
        ["--record", "--export-resources", "--export-spec"]
    assert gui.build_args("record", export_report=True) == \
        ["--record", "--export-report"]
    assert gui.build_args("record", export_istqb=True) == \
        ["--record", "--export-istqb"]
    # hors record, sans effet
    assert gui.build_args("capture", suite=False, export_resources=True,
                          export_report=True, export_istqb=True) == ["--capture"]


def test_gui_default_record_name_and_path_resolution():
    import datetime
    now = datetime.datetime(2026, 7, 19, 10, 30, 0)
    assert gui.default_record_name(now) == "record_20260719_103000.robot"
    assert gui.record_file_path("x.robot") == os.path.join(gui.CAPTURES_DIR, "x.robot")
    absolute = os.path.abspath(os.path.join(os.sep, "tmp", "y.robot"))
    assert gui.record_file_path(absolute) == absolute


# --- échappement RF des valeurs (miroir du rfEscape/rfUnescape web) -----------

def test_rf_escape_value_round_trips_special_values():
    cases = ["", "T000", "a  b", "  gauche", "droite  ", "#commentaire",
             "${TAX} 10  %", "chemin\\dossier", "ligne1\nligne2", "text=hello"]
    for value in cases:
        assert spy.rf_unescape_value(spy.rf_escape_value(value)) == value


def test_rf_escape_value_neutralizes_rf_syntax():
    assert spy.rf_escape_value("") == "${EMPTY}"
    assert spy.rf_escape_value("${VAR}") == "\\${VAR}"
    assert spy.rf_escape_value("a  b") == "a \\ b"
    assert spy.rf_escape_value("#note") == "\\#note"
    assert spy.rf_escape_value("text=hello") == "text\\=hello"


def test_native_input_text_and_hot_assertion_escape_values():
    # moteur natif : la valeur saisie est échappée ; vider un champ = ${EMPTY}
    line = spy.map_change_command("wnd[0]/usr/txtX", "GuiTextField",
                                  ["SP", "text", "PO  42"])
    assert line == "Input Text    wnd[0]/usr/txtX    PO \\ 42"
    line = spy.map_change_command("wnd[0]/usr/txtX", "GuiTextField",
                                  ["SP", "text", ""])
    assert line == "Input Text    wnd[0]/usr/txtX    ${EMPTY}"
    # assertion à chaud : le texte lu à l'écran est échappé aussi
    line = spy.assertion_step_for_element("wnd[0]/usr/txtX", "GuiTextField",
                                          "1.234,56  EUR")
    assert line == "Element Value Should Be    wnd[0]/usr/txtX    1.234,56 \\ EUR"


def test_replay_unescapes_values_before_invoking_keywords():
    calls = []

    class _Lib:
        def input_text(self, *args):
            calls.append(("input_text",) + args)

    steps = ["Input Text    wnd[0]/usr/txtX    PO \\ 42",
             "Input Text    wnd[0]/usr/txtY    ${EMPTY}"]
    executed, skipped, failed, _msg = spy.replay_recorded_steps(
        steps, _Lib(), writer=lambda *_a: None)
    assert (executed, skipped, failed) == (2, 0, None)
    assert calls == [("input_text", "wnd[0]/usr/txtX", "PO  42"),
                     ("input_text", "wnd[0]/usr/txtY", "")]


def test_spec_export_unknown_step_with_id_moves_to_vigilance():
    # contrat specs/ : une étape inconnue PORTANT un id ne laisse pas l'id dans
    # les étapes : la ligne exacte part en « Points de vigilance »
    md = spy.steps_to_spec(["Mon Keyword Exotique    wnd[0]/usr/txtX    12"])
    etapes = md.split("## Scénarios")[1].split("## Points de vigilance")[0]
    assert "wnd[" not in etapes
    assert "Étape technique à traduire" in etapes
    vigilance = md.split("## Points de vigilance")[1]
    assert "`Mon Keyword Exotique    wnd[0]/usr/txtX    12`" in vigilance


def test_spec_export_humanizes_escaped_values_back():
    md = spy.steps_to_spec(["Input Text    wnd[0]/usr/txtX    PO \\ 42"])
    assert "Saisir `PO  42` dans le champ" in md


def test_spec_export_markdown_metacharacters_stay_literal():
    # Un joker SAP '*LH*' entre guillemets français rendait « LH » en italique
    # au rendu Markdown du plan ; en code span il reste littéral.
    md = spy.steps_to_spec(["Input Text    wnd[0]/usr/ctxtCARRID-LOW    *LH*"])
    assert "Saisir `*LH*` dans le champ" in md


def test_spec_et_istqb_masquent_les_arguments_secrets_des_lignes_brutes():
    # Parité avec le rapport HTML : un password= ajouté à la main dans un
    # déroulé mixte ne fuit ni dans le plan spec ni dans le plan ISTQB.
    steps = ["Open Api Session    http://h    user=U    password=Secret:xyz",
             "Mon Keyword Exotique    wnd[0]/usr/txtX    password=enclair"]
    spec = spy.steps_to_spec(steps)
    assert "Secret:xyz" not in spec and "enclair" not in spec
    assert "password=***" in spec
    istqb = spy.steps_to_istqb(steps)
    assert "Secret:xyz" not in istqb and "enclair" not in istqb
    assert "password=***" in istqb


def test_md_code_survit_aux_backticks_du_contenu():
    # La parade CommonMark complète : un backtick DANS la donnée ne casse pas
    # le code span (clôture plus longue), un backtick en bord est isolé.
    assert spy.md_code("x") == "`x`"
    assert spy.md_code("a`b") == "``a`b``"
    assert spy.md_code("`debut") == "`` `debut ``"


# --- revue de code des tools (2026-08-19) : correctifs verrouillés ------------
#
# Neuf constats de la revue ; les tests ci-dessous fixent le comportement des
# six qui touchent le recorder bureau (les trois autres vivent dans le pack,
# la GUI et la configuration mypy/couverture).

def test_split_step_accepte_les_vrais_separateurs_robot():
    # Constat n°2 : le découpage supposait EXACTEMENT quatre espaces. Robot
    # sépare à partir de DEUX espaces, ou par tabulation, et un déroulé édité
    # à la main (panneau de steps de la GUI) est du RF valide quelconque.
    attendu = (["Input Text", "wnd[0]/usr/ctxtX", "T000"], "")
    assert spy._split_step("Input Text    wnd[0]/usr/ctxtX    T000") == attendu
    assert spy._split_step("Input Text  wnd[0]/usr/ctxtX  T000") == attendu
    assert spy._split_step("Input Text\twnd[0]/usr/ctxtX\tT000") == attendu
    # 5 espaces : le séparateur est gourmand, plus d'espace de tête parasite
    # dans la cellule (une valeur silencieusement fausse au replay).
    assert spy._split_step("Input Text     wnd[0]/usr/ctxtX     T000") == attendu
    # Le commentaire de fin reste séparé, quel que soit le séparateur.
    assert spy._split_step("Send Vkey\t0\t# F8") == (["Send Vkey", "0"], "# F8")


def test_split_step_preserve_les_espaces_echappes_dune_valeur():
    # Une valeur à espaces multiples ou à espace final est échappée `\ ` par
    # rf_escape_value : le découpage ne doit pas la couper sur son PROPRE
    # échappement, et le déséchappement doit rendre la valeur d'origine.
    for brut in ("a  b", "fin ", "  début"):
        cellule = spy.rf_escape_value(brut)
        cells, _c = spy._split_step("Input Text    wnd[0]/usr/txtX    " + cellule)
        assert len(cells) == 3, brut
        assert spy.rf_unescape_value(cells[2]) == brut


def test_count_test_cases_voit_les_scenarios_multiples():
    # Constat n°1 (volet multi-tests) : parse_recorded_body ne rend que le
    # PREMIER test ; le compte permet au replay de le dire.
    texte = ("*** Test Cases ***\nPremier\n    Run Transaction    SE16\n"
             "\nSecond\n    Run Transaction    SE38\n")
    assert spy.count_test_cases(texte) == 2
    assert spy.count_test_cases(spy.build_record_header("x", suite=True)) == 1
    assert spy.count_test_cases("*** Settings ***\nLibrary    X\n") == 0


class _LibSansKeywords:
    """Bibliothèque qui ne porte AUCUN des keywords du déroulé (le cas de la
    suite resource-first, dont les steps sont des keywords métier)."""


def test_run_replay_echoue_quand_des_steps_nont_pas_ete_rejoues(tmp_path):
    # Constat n°1 : « Replay OK : 0 step(s) exécuté(s) » en code 0 était vert
    # ET faux. Un step sans keyword dans la bibliothèque fait désormais échouer.
    out = tmp_path / "resource_first.robot"
    out.write_text("*** Settings ***\nLibrary             SapEccLibrary\n"
                   "Resource            rec_keywords.resource\n\n"
                   "*** Test Cases ***\nScénario\n"
                   "    Saisir DATABROWSE_TABLENAME    T000\n", encoding="utf-8")
    messages = []
    rc = spy.run_replay(str(out), _lib_factory=lambda: _LibSansKeywords(),
                        _writer=messages.append)
    assert rc == 1
    texte = "\n".join(messages)
    assert "ÉCHEC" in texte and "PAS été rejoués" in texte
    # ... en nommant le cas resource-first et le bon outil pour la rejouer.
    assert "resource-first" in texte and "robot" in texte
    assert "Replay OK" not in texte


def test_run_replay_signale_les_tests_non_rejoues(tmp_path):
    out = tmp_path / "multi.robot"
    out.write_text("*** Test Cases ***\nPremier\n    Run Transaction    SE16\n"
                   "\nSecond\n    Run Transaction    SE38\n", encoding="utf-8")
    lib = _FakeReplayLib()
    messages = []
    assert spy.run_replay(str(out), _lib_factory=lambda: lib,
                          _writer=messages.append) == 0
    texte = "\n".join(messages)
    assert "seul le PREMIER est rejoué" in texte
    assert lib.calls == [("run_transaction", "SE16")]


def test_resolve_save_path_refuse_un_chemin_relatif_a_un_lecteur():
    # Constat n°7 : ``E:fichier`` porte un lecteur sans être absolu ; le
    # message parlait de traversée de chemin, il nomme maintenant la forme.
    try:
        spy.resolve_save_path("E:fichier.txt", spy.default_capture_path)
    except ValueError as exc:
        assert "relatif à un lecteur" in str(exc)
    else:                                            # pragma: no cover
        raise AssertionError("un chemin relatif à un lecteur doit être refusé")
    # Le refus de traversée d'origine ne bouge pas.
    try:
        spy.resolve_save_path(os.path.join("..", "..", "evil.txt"),
                              spy.default_capture_path)
    except ValueError as exc:
        assert "sort de" in str(exc)
    else:                                            # pragma: no cover
        raise AssertionError("la traversée hors de captures/ doit être refusée")


def test_com_error_est_toujours_defini_meme_sans_pywin32():
    # Constat n°6 : le repli d'import laissait `com_error` indéfini, alors que
    # des dizaines de clauses ``except (AttributeError, com_error)`` le citent
    # (une clause d'exception est évaluée AU MOMENT de l'erreur : NameError
    # opaque à la place de l'erreur réelle).
    assert isinstance(spy.com_error, type)
    assert issubclass(spy.com_error, BaseException)


def test_sentinelle_darret_arme_puis_declenche(tmp_path):
    # Constat n°4 : l'arrêt EXTERNE (bouton « Arrêter » de la GUI) doit sortir
    # des boucles par leur `finally`, pas par un processus tué.
    stop = tmp_path / "record.robot.stop"
    stop.write_text("périmé", encoding="utf-8")      # sentinelle d'un run passé
    should_stop = spy.make_stop_checker(str(stop))
    assert not stop.exists()                         # armement = nettoyage
    assert should_stop() is False
    stop.write_text("stop", encoding="utf-8")
    assert should_stop() is True
    spy.clear_stop_file(str(stop))
    assert not stop.exists()
    spy.clear_stop_file(str(stop))                   # idempotent
    assert spy.make_stop_checker(None)() is False    # sonde inerte
