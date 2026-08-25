"""Exports du recorder : CLI, echappement RF des valeurs, garde-fous du replay et de la sentinelle. Doublures dans _recorder_exports_fixtures."""
import os
import pytest

from _recorder_exports_fixtures import (  # noqa: F401
    _FakeReplayLib,
    _LibSansKeywords,
    gui,
    spy,
)



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


@pytest.mark.skipif(
    os.name != "nt",
    reason="Forme de chemin propre à Windows : `os.path.splitdrive` ne "
           "reconnaît un lecteur que sous ntpath, donc `E:fichier` est un nom "
           "relatif ordinaire ailleurs. La garde vise le vrai contexte du "
           "recorder desktop, qui ne tourne que sous Windows.")
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
