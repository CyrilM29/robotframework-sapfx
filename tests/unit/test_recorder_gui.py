"""Tests unitaires de la logique du lanceur visuel (`tools/recorder/recorder_gui.py`).

Seule la construction des arguments CLI (`build_args`) est testée ; le câblage Tkinter
ne l'est pas (il n'est importé que dans `main()`, donc importer le module ne requiert
pas d'affichage). Le module vit sous ``tools/`` ; on le charge par chemin.
"""
import datetime
import importlib.util
import os
import subprocess
import sys

import pytest

_GUI_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "tools", "recorder", "recorder_gui.py"))


def _load_gui():
    spec = importlib.util.spec_from_file_location("recorder_gui", _GUI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gui = _load_gui()


def test_dump_modes():
    assert gui.build_args("dump") == []
    assert gui.build_args("dump", filter_text="txt") == ["--filter", "txt"]


def test_json_mode_with_optional_file_and_filter():
    assert gui.build_args("json") == ["--json"]
    assert gui.build_args("json", out="tree.json") == ["--json", "tree.json"]
    assert gui.build_args("json", out="tree.json", filter_text="usr") == \
        ["--json", "tree.json", "--filter", "usr"]


def test_highlight_requires_id():
    assert gui.build_args("highlight", highlight_id="wnd[0]/usr/x") == \
        ["--highlight", "wnd[0]/usr/x"]
    with pytest.raises(ValueError, match="Surligner"):
        gui.build_args("highlight")


def test_capture_mode_options():
    assert gui.build_args("capture") == ["--capture"]
    assert gui.build_args("capture", no_highlight=True, filter_text="btn") == \
        ["--capture", "--no-highlight", "--filter", "btn"]
    assert gui.build_args("capture", out="my.txt") == ["--capture", "--out", "my.txt"]


def test_hover_mode_options():
    assert gui.build_args("hover") == ["--hover"]
    assert gui.build_args("hover", out="h.txt", filter_text="usr") == \
        ["--hover", "--filter", "usr", "--out", "h.txt"]


def test_record_mode_options():
    assert gui.build_args("record") == ["--record"]
    assert gui.build_args("record", out="scenario.robot") == \
        ["--record", "--out", "scenario.robot"]
    # --filter ne s'applique pas au mode record
    assert gui.build_args("record", filter_text="x") == ["--record"]


def test_record_mode_screenshots_option():
    assert gui.build_args("record", screenshots=True) == ["--record", "--screenshots"]
    assert gui.build_args("record", out="s.robot", screenshots=True) == \
        ["--record", "--screenshots", "--out", "s.robot"]
    # sans le flag, ou sur un autre mode : jamais --screenshots
    assert gui.build_args("record", screenshots=False) == ["--record"]
    assert gui.build_args("capture", screenshots=True) == ["--capture"]


def test_engine_option_applies_to_capture_and_record_only():
    assert gui.build_args("record", engine="native") == ["--record", "--engine", "native"]
    assert gui.build_args("capture", engine="poll") == ["--capture", "--engine", "poll"]
    # 'auto' est le défaut de la CLI : on ne l'émet jamais
    assert gui.build_args("record", engine="auto") == ["--record"]
    # hors capture/record, le moteur est ignoré
    assert gui.build_args("dump", engine="native") == []
    assert gui.build_args("hover", engine="poll") == ["--hover"]


def test_engine_option_rejects_unknown_value():
    with pytest.raises(ValueError, match="Moteur inconnu"):
        gui.build_args("record", engine="turbo")


def test_record_mode_semantic_option():
    assert gui.build_args("record", semantic=True) == ["--record", "--semantic"]
    assert gui.build_args("record", screenshots=True, semantic=True, out="s.robot") == \
        ["--record", "--screenshots", "--semantic", "--out", "s.robot"]
    # jamais --semantic hors record
    assert gui.build_args("capture", semantic=True) == ["--capture"]


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="Mode inconnu"):
        gui.build_args("nope")


# --- console_python : ne jamais lancer le recorder via pythonw (pas de stdio) -

def test_console_python_swaps_pythonw_for_python(monkeypatch, tmp_path):
    fake_dir = tmp_path
    (fake_dir / "python.exe").write_bytes(b"")
    pythonw = fake_dir / "pythonw.exe"
    pythonw.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(pythonw))
    assert gui.console_python() == str(fake_dir / "python.exe")


def test_console_python_keeps_pythonw_if_no_console_sibling(monkeypatch, tmp_path):
    pythonw = tmp_path / "pythonw.exe"
    pythonw.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(pythonw))
    assert gui.console_python() == str(pythonw)


def test_console_python_leaves_regular_python_untouched(monkeypatch, tmp_path):
    python_exe = tmp_path / "python.exe"
    python_exe.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(python_exe))
    assert gui.console_python() == str(python_exe)


# --- resolve_record_out : relancer un record n'écrase jamais le précédent -----

def test_resolve_record_out_generates_fresh_name_when_empty():
    import datetime
    now = datetime.datetime(2026, 7, 20, 10, 0, 0)
    out, auto = gui.resolve_record_out("", None, now=now)
    assert out == "record_20260720_100000.robot"
    assert auto == out


def test_resolve_record_out_regenerates_when_field_kept_the_auto_name():
    # le champ contient encore le nom auto-généré du lancement précédent :
    # un nouveau lancement doit produire un NOUVEAU nom (pas de troncature
    # silencieuse de l'enregistrement précédent)
    import datetime
    first = "record_20260720_100000.robot"
    now = datetime.datetime(2026, 7, 20, 10, 5, 0)
    out, auto = gui.resolve_record_out(first, first, now=now)
    assert out == "record_20260720_100500.robot"
    assert auto == out


def test_resolve_record_out_respects_a_user_typed_name():
    # un nom saisi par l'utilisateur est respecté tel quel (écraser devient
    # son choix explicite), et le nom auto mémorisé n'est pas perdu
    out, auto = gui.resolve_record_out("mon_scenario.robot", "record_x.robot")
    assert out == "mon_scenario.robot"
    assert auto == "record_x.robot"


# --- bandeau identite : poignee de deplacement (2026-08-05) -------------------

def test_banner_drag_position_follows_the_mouse_delta():
    # la fenetre suit le delta souris depuis l'enfoncement : meme contrat que
    # le drag de l'en-tete du panneau du recorder web
    assert gui.banner_drag_position((100, 200), (10, 20), (130, 250)) == (40, 70)


def test_banner_drag_position_is_stable_without_motion():
    assert gui.banner_drag_position((5, 5), (300, 400), (5, 5)) == (300, 400)


def test_banner_drag_position_supports_negative_screen_coordinates():
    # multi-ecrans : l'ecran secondaire a gauche donne des coordonnees negatives
    assert gui.banner_drag_position((0, 0), (-1920, 10), (-50, -8)) == (-1970, 2)


# --- revue de code des tools (2026-08-19) : arret propre du bouton « Arreter » -

class _FakeProc:
    """Processus factice : ``poll`` rend None tant qu'il tourne ; ``wait`` sort
    quand la sentinelle a ete vue, ou leve TimeoutExpired si on le lui demande."""

    def __init__(self, honore_la_sentinelle=True, deja_fini=False):
        self.honore = honore_la_sentinelle
        self.fini = deja_fini
        self.terminated = False

    def poll(self):
        return 0 if self.fini else None

    def wait(self, timeout=None):
        if not self.honore:
            raise subprocess.TimeoutExpired("sapgui_recorder.py", timeout)
        self.fini = True
        return 0

    def terminate(self):
        self.terminated = True
        self.fini = True


def test_stop_file_path_reste_sous_captures(tmp_path):
    chemin = gui.stop_file_path("record_20260819_101500.robot")
    assert os.path.dirname(chemin) == gui.CAPTURES_DIR
    assert chemin.endswith("record_20260819_101500.robot.stop")
    # sans fichier de sortie (capture / survol) : horodate, jamais vide
    auto = gui.stop_file_path("", now=datetime.datetime(2026, 8, 19, 10, 15, 0))
    assert auto.endswith("20260819_101500.stop")
    # un nom porteur de chemin ne fait pas sortir la sentinelle de captures/
    assert os.path.dirname(gui.stop_file_path("../../evil")) == gui.CAPTURES_DIR


def test_request_stop_pose_la_sentinelle_avant_de_tuer(tmp_path):
    # Constat n°4 : terminate() sautait le teardown du recorder (OK-code en
    # attente perdu, Session.Record laisse actif cote SAP GUI).
    stop = tmp_path / "record.robot.stop"
    proc = _FakeProc()
    assert gui.request_stop(proc, str(stop), timeout=0.1) == "propre"
    assert stop.exists()                       # le recorder l'efface lui-meme
    assert proc.terminated is False


def test_request_stop_force_si_le_recorder_ne_rend_pas_la_main(tmp_path):
    stop = tmp_path / "record.robot.stop"
    proc = _FakeProc(honore_la_sentinelle=False)
    assert gui.request_stop(proc, str(stop), timeout=0.01) == "forcé"
    assert proc.terminated is True


def test_request_stop_ne_fait_rien_sur_un_processus_deja_arrete(tmp_path):
    proc = _FakeProc(deja_fini=True)
    assert gui.request_stop(proc, str(tmp_path / "x.stop")) == "déjà arrêté"
    assert proc.terminated is False
    assert gui.request_stop(None, str(tmp_path / "x.stop")) == "déjà arrêté"
