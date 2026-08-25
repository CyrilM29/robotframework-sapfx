"""Moteur record natif : boucles evenementielles, mode semantique live, hardcopy, sentinelle. Doublures dans _recorder_native_fixtures."""
import os

from _recorder_native_fixtures import (  # noqa: F401
    FakeComponent,
    FakeConnection,
    FakeSession,
    _SE16_ELEMENTS,
    _ShotSession,
    _ShotWindow,
    _engine_with,
    _fake_advise,
    spy,
)



def test_record_loop_native_writes_steps_from_change_events(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "native.robot")
    handlers = {}
    connection = FakeConnection()

    events = iter([
        lambda: handlers["change"](FakeComponent("wnd[0]/tbar[0]/okcd", "GuiOkCodeField"),
                                   (("SP", "text", "SE16"),)),   # variant imbriqué (comme live)
        lambda: handlers["change"](FakeComponent("wnd[0]", "GuiMainWindow"),
                                   (("M", "sendVKey", 0),)),
        lambda: handlers["change"](FakeComponent("wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
                                                 "GuiCTextField"),
                                   (("SP", "text", "SFLIGHT"),)),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    written = []
    count = spy.record_loop_native(
        engine, out, _writer=written.append, _max_iterations=5,
        _advise=_fake_advise(handlers, connection), _pump=fake_pump,
        _sleep=lambda s: None)

    assert count == 2
    assert session.Record is False                      # désarmé au teardown
    assert connection.closed is True                    # désabonné au teardown
    content = open(out, encoding="utf-8").read()
    assert "*** Test Cases ***" in content
    assert "Run Transaction    SE16" in content
    assert "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT" in content
    assert "Send Vkey    0" not in content              # absorbé par Run Transaction


def test_record_loop_native_returns_none_when_server_disables_recording(tmp_path):
    session = FakeSession(recording_disabled=True)
    out = str(tmp_path / "never.robot")
    result = spy.record_loop_native(
        _engine_with(session), out, _writer=lambda *_: None,
        _advise=lambda *a, **k: (_ for _ in ()).throw(AssertionError),
        _pump=lambda: None)
    assert result is None                               # -> repli polling côté CLI
    assert not os.path.exists(out)                      # aucun fichier fantôme


def test_record_loop_native_returns_none_when_event_binding_fails(tmp_path):
    session = FakeSession()
    out = str(tmp_path / "unbound.robot")

    def failing_advise(session, **handlers):
        raise OSError("connection point refused")

    result = spy.record_loop_native(
        _engine_with(session), out, _writer=lambda *_: None,
        _advise=failing_advise, _pump=lambda: None)
    assert result is None


def test_capture_loop_native_records_hits_and_focus_dedup(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "capture.txt")
    handlers = {}
    connection = FakeConnection()

    field = FakeComponent("wnd[0]/usr/txtRSYST-BNAME", "GuiTextField", "DEVELOPER")
    events = iter([
        lambda: handlers["hit"](field),
        lambda: handlers["focus"](field),               # même id -> dédupliqué
        lambda: handlers["hit"](FakeComponent("wnd[0]/tbar[0]/btn[3]", "GuiButton")),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    count = spy.capture_loop_native(
        engine, out, _writer=lambda *_: None, _max_iterations=5,
        _advise=_fake_advise(handlers, connection), _pump=fake_pump,
        _sleep=lambda s: None)

    assert count == 2
    assert session.elementVisualizationMode is False    # hit-test désarmé au teardown
    assert connection.closed is True
    content = open(out, encoding="utf-8").read()
    assert "wnd[0]/usr/txtRSYST-BNAME" in content
    assert content.count("[GuiTextField]") == 1         # un seul BLOC malgré Hit+Focus
    assert "wnd[0]/tbar[0]/btn[3]" in content


def test_capture_loop_native_honours_filter(tmp_path):
    session = FakeSession()
    out = str(tmp_path / "filtered.txt")
    handlers = {}

    events = iter([
        lambda: handlers["hit"](FakeComponent("wnd[0]/usr/txtA", "GuiTextField")),
        lambda: handlers["hit"](FakeComponent("wnd[0]/tbar[0]/btn[3]", "GuiButton")),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    count = spy.capture_loop_native(
        engine=_engine_with(session), out_path=out, filter_text="txt",
        _writer=lambda *_: None, _max_iterations=4,
        _advise=_fake_advise(handlers, FakeConnection()), _pump=fake_pump,
        _sleep=lambda s: None)
    assert count == 1
    content = open(out, encoding="utf-8").read()
    assert "btn[3]" not in content


def test_semanticize_input_text_devient_fill_field_by_label():
    line = "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT"
    assert spy.semanticize_step(line, _SE16_ELEMENTS) == (
        "Fill Field By Label    Table Name    SFLIGHT"
        "    # id: wnd[0]/usr/ctxtDATABROWSE-TABLENAME")


def test_semanticize_click_element_devient_click_button_by_label():
    line = "Click Element    wnd[0]/tbar[1]/btn[8]"
    assert spy.semanticize_step(line, _SE16_ELEMENTS) == (
        "Click Button By Label    Execute (F8)    # id: wnd[0]/tbar[1]/btn[8]")


def test_semanticize_checkbox_est_annotee_pas_reecrite():
    line = "Select Checkbox    wnd[0]/usr/chkONLY"
    assert spy.semanticize_step(line, _SE16_ELEMENTS) == (
        "Select Checkbox    wnd[0]/usr/chkONLY    # libellé : Selected entries only")


def test_semanticize_garde_la_ligne_sans_libelle_fiable_ou_sans_elements():
    inconnu = "Input Text    wnd[0]/usr/txtINCONNU    X"
    assert spy.semanticize_step(inconnu, _SE16_ELEMENTS) == inconnu
    assert spy.semanticize_step(inconnu, []) == inconnu
    okcd = "Input Text    wnd[0]/tbar[0]/okcd    SE16"
    assert spy.semanticize_step(okcd, _SE16_ELEMENTS) == okcd
    run = "Run Transaction    SE16"
    assert spy.semanticize_step(run, _SE16_ELEMENTS) == run


def test_record_loop_native_semantic_emet_des_keywords_humains(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "semantic.robot")
    handlers = {}

    events = iter([
        lambda: handlers["change"](FakeComponent("wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
                                                 "GuiCTextField"),
                                   (("SP", "text", "SFLIGHT"),)),
        lambda: handlers["change"](FakeComponent("wnd[0]/tbar[1]/btn[8]", "GuiButton"),
                                   (("M", "press"),)),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    count = spy.record_loop_native(
        engine, out, semantic=True, _writer=lambda *_: None, _max_iterations=4,
        _advise=_fake_advise(handlers, FakeConnection()), _pump=fake_pump,
        _sleep=lambda s: None, _elements_fn=lambda session: _SE16_ELEMENTS)

    assert count == 2
    content = open(out, encoding="utf-8").read()
    assert "Fill Field By Label    Table Name    SFLIGHT" in content
    assert "# id: wnd[0]/usr/ctxtDATABROWSE-TABLENAME" in content
    assert "Click Button By Label    Execute (F8)" in content


def test_record_loop_native_sans_semantic_reste_en_ids(tmp_path):
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "technique.robot")
    handlers = {}
    events = iter([
        lambda: handlers["change"](FakeComponent("wnd[0]/usr/ctxtDATABROWSE-TABLENAME",
                                                 "GuiCTextField"),
                                   (("SP", "text", "SFLIGHT"),)),
    ])

    def fake_pump():
        try:
            next(events)()
        except StopIteration:
            pass

    spy.record_loop_native(
        engine, out, _writer=lambda *_: None, _max_iterations=3,
        _advise=_fake_advise(handlers, FakeConnection()), _pump=fake_pump,
        _sleep=lambda s: None,
        _elements_fn=lambda session: (_ for _ in ()).throw(AssertionError(
            "screen_elements ne doit pas être appelé sans --semantic")))
    content = open(out, encoding="utf-8").read()
    assert "Input Text    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SFLIGHT" in content


def test_hardcopy_screenshot_ecrit_le_png_et_choisit_l_extension(tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    base = str(tmp_path / "step_001")
    path = spy.hardcopy_screenshot(_ShotSession(_ShotWindow(png)), base)
    assert path == base + ".png"
    assert open(path, "rb").read() == png


def test_hardcopy_screenshot_extension_suit_les_magic_bytes_pas_la_demande(tmp_path):
    bmp = b"BM" + b"bitmap-payload"                      # l'API a rendu du BMP
    base = str(tmp_path / "step_002")
    path = spy.hardcopy_screenshot(_ShotSession(_ShotWindow(tuple(bmp))), base)
    assert path == base + ".bmp"
    assert open(path, "rb").read() == bmp


def test_hardcopy_screenshot_none_si_api_absente_ou_buffer_vide(tmp_path):
    base = str(tmp_path / "step_003")
    sans_api = _ShotSession(_ShotWindow(AttributeError("HardCopyToMemory")))
    assert spy.hardcopy_screenshot(sans_api, base) is None
    vide = _ShotSession(_ShotWindow(b""))
    assert spy.hardcopy_screenshot(vide, base) is None


def test_record_loop_native_sarrete_sur_la_sentinelle_avec_son_teardown(tmp_path):
    # Constat n°4 : la GUI ne peut pas envoyer de Ctrl+C (console séparée) ;
    # elle pose une sentinelle, et la boucle sort par son `finally` : Record
    # désarmé, événements désabonnés, OK-code en attente écrit.
    session = FakeSession()
    engine = _engine_with(session)
    out = str(tmp_path / "stop.robot")
    stop = tmp_path / "stop.flag"
    handlers = {}
    connection = FakeConnection()
    pumps = {"n": 0}

    def fake_pump():
        pumps["n"] += 1
        if pumps["n"] == 1:
            handlers["change"](FakeComponent("wnd[0]/tbar[0]/okcd", "GuiOkCodeField"),
                               (("SP", "text", "SE16"),))
        if pumps["n"] == 2:
            stop.write_text("stop", encoding="utf-8")      # « Arrêter » de la GUI

    count = spy.record_loop_native(
        engine, out, stop_file=str(stop), _writer=lambda *_a: None,
        _max_iterations=50, _advise=_fake_advise(handlers, connection),
        _pump=fake_pump, _sleep=lambda s: None)

    assert pumps["n"] < 50                       # sortie AVANT la borne d'itérations
    assert session.Record is False               # teardown déroulé
    assert connection.closed is True
    assert not stop.exists()                     # sentinelle consommée
    # L'OK-code resté en attente est bien écrit (ce qu'un processus tué perdait).
    assert count == 1
    assert "Run Transaction    SE16" in open(out, encoding="utf-8").read()


def test_record_loop_native_compte_les_evenements_perdus(tmp_path):
    # Constat n°5 : le sink COM étouffe tout ce qui remonte d'un handler ; un
    # événement non transcrit doit être COMPTÉ et annoncé, jamais silencieux.
    session = FakeSession()
    out = str(tmp_path / "perdu.robot")
    handlers = {}

    class _Explose:
        @property
        def Id(self):
            raise RuntimeError("COM parti pendant la lecture")

    def fake_pump():
        handlers["change"](_Explose(), (("SP", "text", "SE16"),))

    written = []
    count = spy.record_loop_native(
        engine=_engine_with(session), out_path=out, _writer=written.append,
        _max_iterations=2, _advise=_fake_advise(handlers, FakeConnection()),
        _pump=fake_pump, _sleep=lambda s: None)

    assert count == 0
    texte = "\n".join(written)
    assert "2 événement(s) NON transcrits" in texte
    assert "COM parti pendant la lecture" in texte
