"""Tests du journal JSONL cumulatif de healing (``sapfx_common.healing_telemetry``)
et de son branchement dans les deux canaux : ECC (`Resolve Element With Healing`)
et Fiori (`Resolve Ui5 With Fallback`). Fake COM / fake Browser, convention #5."""
import json

from sapfx_common.healing_telemetry import ENV_VAR, record_healing, telemetry_path

# Doublures partagées avec les tests existants (pythonpath tests/unit, pyproject).
from test_diagnostics_and_healing import FakeNode, FakeSession, _lib as _ecc_lib
from test_fiori_frames_and_fallback import FakeBrowser, _lib as _fiori_lib


def _read_events(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# --- module pur ---------------------------------------------------------------------

def test_disabled_without_env_var(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert telemetry_path() is None
    assert record_healing("ecc", "old", "new") is False
    assert list(tmp_path.iterdir()) == []          # rien écrit nulle part


def test_appends_one_json_line_per_healing(monkeypatch, tmp_path):
    log = tmp_path / "healing.jsonl"
    monkeypatch.setenv(ENV_VAR, str(log))
    assert record_healing("ecc", "wnd[0]/usr/old", "wnd[0]/usr/new", score=0.8768) is True
    assert record_healing("fiori", "role {'controlType': 'Button'}",
                          "xpath //Button", engine="xpath") is True
    events = _read_events(log)
    assert len(events) == 2
    assert events[0]["channel"] == "ecc"
    assert events[0]["original"] == "wnd[0]/usr/old"
    assert events[0]["healed"] == "wnd[0]/usr/new"
    assert events[0]["score"] == 0.877              # arrondi à 3 décimales
    assert "engine" not in events[0]                # champs optionnels omis, pas null
    assert events[1]["engine"] == "xpath"
    assert "score" not in events[1]
    assert all("timestamp" in e for e in events)


def test_io_errors_are_swallowed_never_raised(monkeypatch, tmp_path):
    # un chemin inécrivable (répertoire) ne doit JAMAIS faire échouer le test appelant
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    assert record_healing("ecc", "old", "new") is False


# --- branchement ECC : Resolve Element With Healing ---------------------------------

def _window_with(*fields):
    return FakeNode("/app/con[0]/ses[0]/wnd[0]", "GuiMainWindow", "", list(fields))


def test_ecc_healing_is_recorded_with_score(monkeypatch, tmp_path):
    log = tmp_path / "healing.jsonl"
    monkeypatch.setenv(ENV_VAR, str(log))
    present = ("/app/con[0]/ses[0]/wnd[0]/usr/subSUB0:SAPLMEGUI:0015/"
               "ctxtMEPO_TOPLINE-BSART")
    session = FakeSession(window=_window_with(FakeNode(present, "GuiCTextField")))
    _ecc_lib(session).resolve_element_with_healing(
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0013/ctxtMEPO_TOPLINE-BSART")
    events = _read_events(log)
    assert len(events) == 1
    assert events[0]["channel"] == "ecc"
    assert events[0]["healed"].endswith(":0015/ctxtMEPO_TOPLINE-BSART")
    assert events[0]["score"] >= 0.6


def test_ecc_nominal_resolution_writes_nothing(monkeypatch, tmp_path):
    # le chemin nominal (id présent tel quel) n'est PAS une réparation
    log = tmp_path / "healing.jsonl"
    monkeypatch.setenv(ENV_VAR, str(log))
    session = FakeSession(present_ids=["wnd[0]/usr/txtA"])
    _ecc_lib(session).resolve_element_with_healing("wnd[0]/usr/txtA")
    assert not log.exists()


# --- branchement Fiori : Resolve Ui5 With Fallback -----------------------------------

def test_fiori_fallback_healing_is_recorded_with_engine(monkeypatch, tmp_path):
    log = tmp_path / "healing.jsonl"
    monkeypatch.setenv(ENV_VAR, str(log))
    browser = FakeBrowser(role_ids=[], xpath_ids=["__btn2"])
    _fiori_lib(browser).resolve_ui5_with_fallback(
        controlType="Button", properties={"text": "Gone"},
        xpath="//Dialog//Button", attempt_timeout="0.05s")
    events = _read_events(log)
    assert len(events) == 1
    assert events[0]["channel"] == "fiori"
    assert events[0]["engine"] == "xpath"
    assert events[0]["original"].startswith("role ")
    assert events[0]["healed"].startswith("xpath ")


def test_fiori_primary_resolution_writes_nothing(monkeypatch, tmp_path):
    log = tmp_path / "healing.jsonl"
    monkeypatch.setenv(ENV_VAR, str(log))
    browser = FakeBrowser(role_ids=["__btn1"])
    _fiori_lib(browser).resolve_ui5_with_fallback(
        controlType="Button", xpath="//Button", attempt_timeout="0.05s")
    assert not log.exists()
