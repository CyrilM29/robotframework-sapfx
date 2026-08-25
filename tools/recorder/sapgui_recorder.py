"""SAP GUI Recorder : capture de localisateurs pour le client bureau (phase 2).

Cinq usages, du plus simple au plus interactif :

1. **Dump** (par défaut) : parcourt l'arbre d'objets SAP GUI en direct via l'API de
   scripting et liste chaque élément avec son id complet, son type et son texte.
   Cet id est exactement ce que l'on colle dans un mot-clé SapEccLibrary
   (``wnd[0]/usr/txtRSYST-BNAME``).
2. **Surlignage** (``--highlight ID``) : encadre un contrôle **en rouge à l'écran**
   via la méthode native ``Visualize`` de SAP GUI Scripting, pour vérifier
   visuellement à quoi correspond un id.
3. **Clic-à-capturer** (``--capture``) : surveille l'élément qui a le **focus** dans
   SAP GUI (``ActiveWindow.GuiFocus``) ; à chaque fois que tu cliques/tabules sur un
   champ, il enregistre son id, le surligne, et propose une **ligne de mot-clé prête
   à coller** (``Input Text``, ``Click Element``…). C'est le vrai enregistreur.
4. **Survol** (``--hover``) : encadre en continu le contrôle **sous le curseur** (et
   non celui qui a le focus) : associe la position souris (``win32api.GetCursorPos``)
   au plus petit rectangle écran (``ScreenLeft/Top/Width/Height``) qui la contient.
   Inspecteur live ; avec ``--out``, enregistre aussi chaque contrôle survolé.
5. **Enregistreur** (``--record``) : suit tes manipulations et transcrit le déroulé
   en une **séquence de keywords rejouable** (un corps ``*** Test Cases ***``). Modèle
   par aller-retour : entre deux écrans, diff des champs éditables -> ``Input Text``…
   puis l'action de soumission (``Run Transaction`` si OK-code saisi, sinon ``Send Vkey 0``).
   Avec ``--screenshots``, capture aussi (best-effort, bitmap) l'écran d'arrivée de
   chaque aller-retour, utile pour diagnostiquer visuellement un replay qui diverge.

Utilisation (avec SAP Logon Pad ouvert et une session en cours) :
    python sapgui_recorder.py                      # arbre complet -> terminal
    python sapgui_recorder.py --json               # dump JSON -> captures/dump_<horodatage>.json
    python sapgui_recorder.py --json out.json      # dump JSON -> captures/out.json
    python sapgui_recorder.py --filter txt         # ids/types contenant "txt"
    python sapgui_recorder.py --highlight wnd[0]/usr/ctxtDATABROWSE-TABLENAME
    python sapgui_recorder.py --capture            # focus : capture 1 locator (Ctrl+C)
    python sapgui_recorder.py --hover              # curseur : inspecteur (Ctrl+C)
    python sapgui_recorder.py --record             # enregistreur de déroulé (Ctrl+C)
    python sapgui_recorder.py --record --out scenario.robot
    python sapgui_recorder.py --record --semantic  # keywords humains (Fill Field By Label…),
                                                   # id technique en commentaire (moteur natif)

Politique de sauvegarde unifiée : tout artefact (dump JSON et captures) atterrit dans
``tools/recorder/captures/`` : horodaté si aucun nom n'est donné, sous ``captures/`` pour un
chemin relatif, et tel quel pour un chemin absolu. Le dump sans ``--json`` reste un
simple affichage terminal.

Prérequis : pywin32, et le scripting activé côté serveur et client.
"""
import argparse
import json
import os
import sys


# Module charge par CHEMIN (Robot `Library`, spec_from_file_location des
# tests) : son dossier n'est pas forcement sur sys.path, on l'y pose pour que
# les imports entre modules voisins du recorder fonctionnent partout.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from recorder_com import (  # noqa: E402,F401
    com_error as com_error,
    pythoncom as pythoncom,
    win32com as win32com,
    win32api as win32api,
    win32con as win32con,
    win32gui as win32gui,
    win32ui as win32ui,
    _SESSION_PREFIX as _SESSION_PREFIX,
    _matches_filter as _matches_filter,
    active_window as active_window,
    relative_id as relative_id,
    get_scripting_engine as get_scripting_engine,
    walk as walk,
    _safe as _safe,
    collect as collect,
    find_element as find_element,
    highlight as highlight,
    _walk_objects as _walk_objects,
    iter_active_window_elements as iter_active_window_elements,
    element_rect as element_rect,
    capture_rect_to_bmp as capture_rect_to_bmp,
    rect_contains as rect_contains,
    element_at as element_at,
    hardcopy_screenshot as hardcopy_screenshot,
)
from recorder_capture import (  # noqa: E402,F401
    CAPTURES_DIR as CAPTURES_DIR,
    active_focus as active_focus,
    current_focus as current_focus,
    suggest_keyword as suggest_keyword,
    format_capture_block as format_capture_block,
    _timestamped_path as _timestamped_path,
    default_capture_path as default_capture_path,
    default_dump_path as default_dump_path,
    resolve_save_path as resolve_save_path,
    make_stop_checker as make_stop_checker,
    clear_stop_file as clear_stop_file,
    capture_loop as capture_loop,
    hover_loop as hover_loop,
    offset_suggestion as offset_suggestion,
)
from recorder_poll import (  # noqa: E402,F401
    first_session as first_session,
    screen_key as screen_key,
    okcode_value as okcode_value,
    _field_value as _field_value,
    snapshot_fields as snapshot_fields,
    _field_step as _field_step,
    diff_to_steps as diff_to_steps,
    submit_step as submit_step,
    screen_signature as screen_signature,
    scan_active_window as scan_active_window,
    process_poll as process_poll,
    default_record_path as default_record_path,
    make_hotkey_poller as make_hotkey_poller,
    assertion_step_for_element as assertion_step_for_element,
    visual_assertion_step as visual_assertion_step,
    hotkey_assertion_lines as hotkey_assertion_lines,
    open_record_file as open_record_file,
    record_loop as record_loop,
)
from recorder_native import (  # noqa: E402,F401
    _NOISE_PROPERTIES as _NOISE_PROPERTIES,
    _TRUE_STRINGS as _TRUE_STRINGS,
    _VKEY_NAMES as _VKEY_NAMES,
    set_vkey_resolver as set_vkey_resolver,
    _vkey_comment as _vkey_comment,
    normalize_command as normalize_command,
    _is_true as _is_true,
    map_change_command as map_change_command,
    initial_native_state as initial_native_state,
    _is_enter_on_main_window as _is_enter_on_main_window,
    process_change as process_change,
    flush_native_state as flush_native_state,
    recording_disabled as recording_disabled,
    _elem_int as _elem_int,
    screen_elements as screen_elements,
    semanticize_step as semanticize_step,
)
from recorder_native_loop import (  # noqa: E402,F401
    SessionEventConnection as SessionEventConnection,
    advise_session_events as advise_session_events,
    record_loop_native as record_loop_native,
    capture_loop_native as capture_loop_native,
)
from recorder_replay import (  # noqa: E402,F401
    _vbs_guess_type as _vbs_guess_type,
    _vbs_literal as _vbs_literal,
    _split_vbs_args as _split_vbs_args,
    decode_vbs_source as decode_vbs_source,
    transpile_vbs as transpile_vbs,
    replay_recorded_steps as replay_recorded_steps,
    _default_replay_lib as _default_replay_lib,
    _resource_first_hint as _resource_first_hint,
    run_replay as run_replay,
    run_record_exports as run_record_exports,
)
# --- Exports post-enregistrement : extraits dans recorder_exports.py ----------
#
# La logique pure texte -> texte (suite, resource-first, spec, ISTQB, rapport
# HTML) vit dans ``recorder_exports.py`` à côté de ce fichier ; tout est
# ré-exporté ici pour les consommateurs historiques (GUI, tests, suites).
# Ce module étant chargé par CHEMIN (Robot `Library`, spec_from_file_location
# des tests), son dossier n'est pas forcément sur sys.path : on l'y pose.
from recorder_exports import (  # noqa: E402
    DEFAULT_TEST_NAME as DEFAULT_TEST_NAME,
    _ISTQB_GENERIC_EXPECTED as _ISTQB_GENERIC_EXPECTED,
    _ISTQB_TABLE_EXPECTED as _ISTQB_TABLE_EXPECTED,
    _LOC_PREFIX as _LOC_PREFIX,
    _REPORT_CSS as _REPORT_CSS,
    _REPORT_MIMES as _REPORT_MIMES,
    _RESOURCE_WRAPPERS as _RESOURCE_WRAPPERS,
    _SCREENSHOT_COMMENT as _SCREENSHOT_COMMENT,
    _SECRET_ARG as _SECRET_ARG,
    _SUITE_SETTINGS as _SUITE_SETTINGS,
    _esc as _esc,
    _humanize_channel_step as _humanize_channel_step,
    _humanize_step as _humanize_step,
    _istqb_slug as _istqb_slug,
    _istqb_step as _istqb_step,
    _istqb_yaml_lines as _istqb_yaml_lines,
    _mask_secret_args as _mask_secret_args,
    _md_cell as _md_cell,
    _report_shots as _report_shots,
    _split_step as _split_step,
    _strip_md_code as _strip_md_code,
    _yq as _yq,
    build_record_header as build_record_header,
    count_test_cases as count_test_cases,
    locator_slug as locator_slug,
    md_code as md_code,
    parse_recorded_body as parse_recorded_body,
    replace_recorded_steps as replace_recorded_steps,
    report_screenshot_loader as report_screenshot_loader,
    rf_escape_value as rf_escape_value,
    rf_unescape_value as rf_unescape_value,
    steps_to_istqb as steps_to_istqb,
    steps_to_report as steps_to_report,
    steps_to_resource_first as steps_to_resource_first,
    steps_to_spec as steps_to_spec,
)



def main(argv=None):
    parser = argparse.ArgumentParser(description="Dump / surligne / capture / enregistre l'arbre d'objets SAP GUI en direct.")
    parser.add_argument("--json", metavar="FILE", nargs="?", const="", default=None,
                        help="écrit le dump JSON (sans valeur -> captures/dump_<horodatage>.json ; "
                             "chemin relatif -> sous captures/ ; chemin absolu -> tel quel)")
    parser.add_argument("--filter", metavar="TEXT",
                        help="ne retient que les éléments dont l'id ou le type contient TEXT "
                             "(insensible à la casse), s'applique au dump, à --capture et à --hover")
    # Modes mutuellement exclusifs : combiner --capture/--hover/--record/--highlight
    # n'a pas de sens (chacun boucle ou quitte immédiatement) ; sans ce groupe, un
    # tel mélange était honoré silencieusement par ordre de priorité fixe dans
    # main() ci-dessous, sans avertir l'utilisateur.
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--highlight", metavar="ID",
                            help="encadre l'élément ID en rouge à l'écran (Visualize) puis quitte")
    mode_group.add_argument("--capture", action="store_true",
                            help="mode interactif : enregistre chaque élément focalisé (Ctrl+C pour arrêter)")
    mode_group.add_argument("--hover", action="store_true",
                            help="mode survol : encadre le contrôle SOUS LE CURSEUR en continu "
                                 "(avec --out, enregistre aussi ; Ctrl+C pour arrêter)")
    mode_group.add_argument("--record", action="store_true",
                            help="mode enregistreur : transcrit tes manipulations en une séquence de "
                                 "keywords rejouable (diff par aller-retour ; Ctrl+C pour arrêter)")
    mode_group.add_argument("--replay", metavar="FILE",
                            help="rejoue un enregistrement (corps ou suite) contre la session SAP GUI "
                                 "déjà ouverte (Attach To Open Session), arrêt au premier échec, "
                                 "step fautif nommé")
    mode_group.add_argument("--transpile-vbs", metavar="FILE",
                            help="convertit un enregistrement VBS du recorder ALT+F12 intégré à "
                                 "SAP GUI en steps SapEccLibrary (mêmes fusions que le moteur "
                                 "natif ; --suite/--export-resources/--export-spec s'appliquent) ; "
                                 "ne requiert AUCUNE session SAP")
    parser.add_argument("--out", metavar="FILE",
                        help="destination des captures (défaut : captures/capture_<horodatage>.txt ; "
                             "chemin relatif -> sous captures/ ; chemin absolu -> tel quel)")
    parser.add_argument("--engine", choices=("auto", "native", "poll"), default="auto",
                        help="moteur de --record/--capture : 'native' = événements de l'API "
                             "(Session.Record + Change ; hit-test pour --capture), capte boutons, "
                             "grilles, arbres ; 'poll' = sondage (diff d'écran / focus) ; "
                             "'auto' (défaut) essaie native puis replie sur poll")
    parser.add_argument("--stop-file", metavar="FILE",
                        help="chemin d'une sentinelle d'arrêt : dès que ce fichier "
                             "apparaît, la boucle interactive (capture/survol/record) "
                             "s'arrête PROPREMENT, teardown compris (Session.Record "
                             "remis à False, événements désabonnés, dernières étapes "
                             "écrites) ; utilisé par le bouton « Arrêter » de la GUI, "
                             "qui n'a pas de console où envoyer un Ctrl+C")
    parser.add_argument("--no-highlight", action="store_true",
                        help="en mode capture, ne pas surligner les éléments enregistrés")
    parser.add_argument("--screenshots", action="store_true",
                        help="en mode record, capture (best-effort ; HardCopyToMemory, repli "
                             "bitmap GDI) l'écran d'arrivée de chaque aller-retour, sous "
                             "<out>_shots/ ; sans effet hors --record")
    parser.add_argument("--semantic", action="store_true",
                        help="en mode record NATIF, émet des keywords « humains » (Fill Field "
                             "By Label, Click Button By Label ; libellé vérifié re-résolvant "
                             "vers le même élément, id technique en commentaire) au lieu des "
                             "ids ; requiert le paquet sapfx_common ; sans effet en polling")
    # Forme du fichier d'enregistrement : depuis 2026-08-05 le DÉFAUT est la
    # suite complète (Settings + Library SapEccLibrary + Suite Setup Attach To
    # Open Session) : un fichier .robot produit doit se lancer tel quel (un
    # corps nu échouait en « keyword introuvable », constaté au test live).
    shape_group = parser.add_mutually_exclusive_group()
    shape_group.add_argument("--suite", action="store_true",
                             help="(défaut depuis 2026-08-05) en mode record, écrit un fichier "
                                  ".robot COMPLET et rejouable (Settings + Library + Suite Setup "
                                  "Attach To Open Session) ; drapeau conservé pour compatibilité")
    shape_group.add_argument("--body-only", action="store_true",
                             help="en mode record, n'écrit que le corps *** Test Cases *** "
                                  "(l'ancienne forme fragment, à coller dans une suite existante ; "
                                  "sans Library, ce fichier ne se lance pas tel quel)")
    parser.add_argument("--export-resources", action="store_true",
                        help="après l'enregistrement, génère la paire resource-first : "
                             "<out>_keywords.resource (variables ${LOC_…} + keywords métier) "
                             "et <out>_resource_first.robot (suite sans aucun id brut, "
                             "convention n°1) ; l'enregistrement brut reste intact")
    parser.add_argument("--export-spec", action="store_true",
                        help="après l'enregistrement, génère aussi <out>.spec.md : un plan "
                             "Markdown au format specs/ (étapes en langage métier, ids en "
                             "notes) : l'entrée du cycle sap-planner/sap-generator")
    parser.add_argument("--export-report", action="store_true",
                        help="après l'enregistrement, génère aussi <out>_report.html : un "
                             "rapport HTML auto-contenu documentant le déroulé (phrases "
                             "métier + lignes exactes + captures inline si --screenshots) "
                             ": documentation, pas un test")
    parser.add_argument("--export-istqb", action="store_true",
                        help="après l'enregistrement, génère aussi <out>.istqb.md : un "
                             "plan de test + cas de test ISTQB (tableau Action/Données/"
                             "Résultat attendu + bloc replay YAML aux actions normalisées, "
                             "rejouable par une IA quel que soit le framework)")
    args = parser.parse_args(argv)

    def _resolved(path, factory):
        """resolve_save_path, mais imprime une erreur conviviale plutôt que de
        laisser remonter un ValueError brut jusqu'à l'utilisateur de la CLI."""
        try:
            return resolve_save_path(path, factory)
        except ValueError as exc:
            print("Erreur : %s" % exc, file=sys.stderr)
            return None

    # Forme effective du fichier : suite complète par défaut (--body-only =
    # l'ancien fragment ; --suite reste accepté, redondant depuis 2026-08-05).
    suite_mode = not args.body_only

    # --transpile-vbs et --replay ne passent pas par get_scripting_engine :
    # le premier n'a besoin d'AUCUNE session SAP, le second se rattache lui-même.
    if args.transpile_vbs:
        out_path = _resolved(args.out, default_record_path)
        if out_path is None:
            return 1
        try:
            with open(args.transpile_vbs, "rb") as fh:
                steps = transpile_vbs(decode_vbs_source(fh.read()))
        except OSError as exc:
            print("Erreur : %s" % exc, file=sys.stderr)
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(build_record_header(out_path, suite=suite_mode))
            for step in steps:
                fh.write("    " + step + "\n")
        print("Transpilé %d step(s) depuis %s -> %s"
              % (len(steps), args.transpile_vbs, out_path))
        run_record_exports(out_path, export_resources=args.export_resources,
                           export_spec=args.export_spec,
                           export_report=args.export_report,
                           export_istqb=args.export_istqb)
        return 0

    if args.replay:
        return run_replay(args.replay)

    try:
        engine = get_scripting_engine()
    except RuntimeError as exc:
        print("Erreur : %s" % exc, file=sys.stderr)
        return 1

    if args.highlight:
        if highlight(engine, args.highlight):
            print("Surligné : %s" % args.highlight)
            return 0
        print("Erreur : élément introuvable -> %s" % args.highlight, file=sys.stderr)
        return 1

    if args.capture:
        out_path = _resolved(args.out, default_capture_path)
        if out_path is None:
            return 1
        captured = None
        if args.engine in ("auto", "native"):
            try:
                captured = capture_loop_native(engine, out_path, filter_text=args.filter,
                                               stop_file=args.stop_file)
            except KeyboardInterrupt:
                raise
            except Exception as exc:      # défaillance COM imprévue -> repli, jamais un crash
                print("Mode natif en échec (%s) : repli sur le polling." % exc,
                      file=sys.stderr)
                captured = None
            if captured is None and args.engine == "native":
                print("Erreur : mode capture natif indisponible (voir message ci-dessus).",
                      file=sys.stderr)
                return 1
        if captured is None:
            capture_loop(engine, out_path, do_highlight=not args.no_highlight,
                         filter_text=args.filter, stop_file=args.stop_file)
        return 0

    if args.hover:
        out_path = _resolved(args.out, default_capture_path) if args.out else None
        if args.out and out_path is None:
            return 1
        hover_loop(engine, out_path=out_path, filter_text=args.filter,
                   stop_file=args.stop_file)
        return 0

    if args.record:
        out_path = _resolved(args.out, default_record_path)
        if out_path is None:
            return 1
        screenshot_dir = None
        if args.screenshots:
            base, _ext = os.path.splitext(out_path)
            screenshot_dir = base + "_shots"
        recorded = None
        # --screenshots capture l'écran d'arrivée de chaque aller-retour, un
        # concept du moteur polling (frontière = diff de signature) : en auto,
        # sa présence privilégie donc le polling ; --engine native l'ignore.
        use_native = (args.engine == "native"
                      or (args.engine == "auto" and not args.screenshots))
        if use_native:
            try:
                recorded = record_loop_native(engine, out_path, semantic=args.semantic,
                                              suite=suite_mode,
                                              stop_file=args.stop_file)
            except KeyboardInterrupt:
                raise
            except Exception as exc:      # défaillance COM imprévue -> repli, jamais un crash
                print("Mode natif en échec (%s) : repli sur le polling." % exc,
                      file=sys.stderr)
                recorded = None
            if recorded is None and args.engine == "native":
                print("Erreur : mode record natif indisponible (voir message ci-dessus).",
                      file=sys.stderr)
                return 1
        if recorded is None:
            if args.semantic:
                print("--semantic requiert le moteur natif : déroulé en ids techniques.",
                      file=sys.stderr)
            record_loop(engine, out_path, screenshot_dir=screenshot_dir,
                        suite=suite_mode, stop_file=args.stop_file)
        run_record_exports(out_path, export_resources=args.export_resources,
                           export_spec=args.export_spec,
                           export_report=args.export_report,
                           export_istqb=args.export_istqb)
        return 0

    elements = collect(engine)

    if args.filter:
        needle = args.filter.lower()
        elements = [e for e in elements
                    if needle in e["id"].lower() or needle in e["type"].lower()]

    if args.json is not None:
        out_path = _resolved(args.json or None, default_dump_path)
        if out_path is None:
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(elements, fh, indent=2, ensure_ascii=False)
        print("Wrote %s elements to %s" % (len(elements), out_path))
    else:
        for e in elements:
            indent = "  " * e["depth"]
            text = (" = %r" % e["text"]) if e["text"] else ""
            print("%s[%s] %s%s" % (indent, e["type"], e["id"], text))
    return 0




if __name__ == "__main__":
    sys.exit(main())
