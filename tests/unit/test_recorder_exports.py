"""Exports du recorder bureau : suite, resource-first, spec, ISTQB, rapport HTML. Doublures dans _recorder_exports_fixtures (convention #13)."""
import os

from _recorder_exports_fixtures import (  # noqa: F401
    spy,
)



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
