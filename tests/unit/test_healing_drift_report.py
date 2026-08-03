"""Tests du rapport de dérive de healing (scripts/healing_drift_report.py) :
agrégation stable/instable, filtre temporel, localisation dans resources/,
application des patches (stables uniquement), rendu et codes retour."""
import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "healing_drift_report.py"
_spec = importlib.util.spec_from_file_location("healing_drift_report", _SCRIPT)
drift_mod = importlib.util.module_from_spec(_spec)
sys.modules["healing_drift_report"] = drift_mod
_spec.loader.exec_module(drift_mod)


def _write_log(path, events):
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")


def _event(original, healed, channel="ecc", timestamp="2026-07-13T10:00:00+00:00"):
    return {"timestamp": timestamp, "channel": channel,
            "original": original, "healed": healed}


def test_aggregate_separe_stable_et_instable():
    events = [
        _event("wnd[0]/tbar[1]/btn[31]", "wnd[0]/tbar[1]/btn[13]"),
        _event("wnd[0]/tbar[1]/btn[31]", "wnd[0]/tbar[1]/btn[13]"),
        _event("wnd[0]/usr/txtA", "wnd[0]/usr/txtB"),
        _event("wnd[0]/usr/txtA", "wnd[0]/usr/txtC"),
        _event("wnd[0]/usr/txtSEUL", "wnd[0]/usr/txtX"),   # 1 seule fois
    ]
    drifts = drift_mod.aggregate(events, min_count=2)
    by_original = {d.original: d for d in drifts}
    assert set(by_original) == {"wnd[0]/tbar[1]/btn[31]", "wnd[0]/usr/txtA"}
    assert by_original["wnd[0]/tbar[1]/btn[31]"].stable
    assert by_original["wnd[0]/tbar[1]/btn[31]"].healed == "wnd[0]/tbar[1]/btn[13]"
    assert not by_original["wnd[0]/usr/txtA"].stable


def test_aggregate_filtre_since():
    events = [
        _event("old", "x", timestamp="2026-07-01T00:00:00+00:00"),
        _event("old", "x", timestamp="2026-07-02T00:00:00+00:00"),
        _event("recent", "y", timestamp="2026-07-12T00:00:00+00:00"),
        _event("recent", "y", timestamp="2026-07-13T00:00:00+00:00"),
    ]
    drifts = drift_mod.aggregate(events, min_count=2, since="2026-07-10")
    assert [d.original for d in drifts] == ["recent"]


def test_load_events_ignore_les_lignes_illisibles(tmp_path):
    log = tmp_path / "h.jsonl"
    log.write_text('{"original": "a", "healed": "b"}\nPAS DU JSON\n{"x": 1}\n',
                   encoding="utf-8")
    events = drift_mod.load_events(log)
    assert len(events) == 1 and events[0]["original"] == "a"


def test_load_events_tolere_le_bom_windows(tmp_path):
    # Un journal retouché via Out-File PowerShell arrive avec un BOM UTF-8 :
    # la première ligne doit rester lisible (constaté au premier essai CLI).
    log = tmp_path / "h.jsonl"
    log.write_bytes(b'\xef\xbb\xbf{"original": "a", "healed": "b"}\n')
    assert len(drift_mod.load_events(log)) == 1


def test_propose_et_applique_les_patches_stables_seulement(tmp_path):
    resources = tmp_path / "resources"
    resources.mkdir()
    resource = resources / "ecc_keywords.resource"
    resource.write_text(
        "*** Variables ***\n"
        "${BTN_COUNT}    wnd[0]/tbar[1]/btn[31]\n"
        "${INSTABLE}     wnd[0]/usr/txtA\n", encoding="utf-8")
    events = [
        _event("wnd[0]/tbar[1]/btn[31]", "wnd[0]/tbar[1]/btn[13]"),
        _event("wnd[0]/tbar[1]/btn[31]", "wnd[0]/tbar[1]/btn[13]"),
        _event("wnd[0]/usr/txtA", "wnd[0]/usr/txtB"),
        _event("wnd[0]/usr/txtA", "wnd[0]/usr/txtC"),
    ]
    drifts = drift_mod.aggregate(events)
    patches = drift_mod.propose_patches(drifts, resources)
    # seule la dérive STABLE est patchée, jamais l'instable
    assert len(patches) == 1
    assert patches[0].line_no == 2
    changed = drift_mod.apply_patches(patches)
    assert changed == 1
    content = resource.read_text(encoding="utf-8")
    assert "wnd[0]/tbar[1]/btn[13]" in content
    assert "wnd[0]/usr/txtA" in content   # l'instable est intact


def test_render_markdown_liste_stables_patches_et_instables(tmp_path):
    resources = tmp_path / "r"
    resources.mkdir()
    (resources / "k.resource").write_text("id wnd[0]/tbar[1]/btn[31] ici\n",
                                          encoding="utf-8")
    events = [
        _event("wnd[0]/tbar[1]/btn[31]", "wnd[0]/tbar[1]/btn[13]"),
        _event("wnd[0]/tbar[1]/btn[31]", "wnd[0]/tbar[1]/btn[13]"),
        _event("inline_locator", "inline_fixed"),
        _event("inline_locator", "inline_fixed"),
        _event("multi", "a"), _event("multi", "b"),
    ]
    drifts = drift_mod.aggregate(events)
    patches = drift_mod.propose_patches(drifts, resources)
    report = drift_mod.render_markdown(drifts, patches)
    assert "Stables" in report and "btn[13]" in report
    assert "hors resources/" in report and "inline_locator" in report
    assert "Instables" in report and "multi" in report


def test_main_codes_retour(tmp_path, capsys):
    log = tmp_path / "h.jsonl"
    # journal vide de dérives -> 0
    _write_log(log, [_event("a", "b")])
    assert drift_mod.main(["--log", str(log),
                           "--resources-dir", str(tmp_path)]) == 0
    # dérive récurrente sans --apply -> 1 (signal CI)
    _write_log(log, [_event("a", "b"), _event("a", "b")])
    assert drift_mod.main(["--log", str(log),
                           "--resources-dir", str(tmp_path)]) == 1
    # journal absent -> 0 (pas encore de télémétrie, pas une erreur)
    assert drift_mod.main(["--log", str(tmp_path / "absent.jsonl")]) == 0
    capsys.readouterr()
