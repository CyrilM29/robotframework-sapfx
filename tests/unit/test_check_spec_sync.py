"""Tests du garde specs/ ↔ tests/robot/ (scripts/check_spec_sync.py) :
marqueur de provenance, détection de suite périmée, stamp idempotent."""
import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_spec_sync.py"
_spec = importlib.util.spec_from_file_location("check_spec_sync", _SCRIPT)
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_spec_sync"] = sync_mod
_spec.loader.exec_module(sync_mod)


def _repo(tmp_path, spec_text="# Plan SFLIGHT\n\nScénario 1.\n"):
    (tmp_path / "specs").mkdir()
    (tmp_path / "tests" / "robot").mkdir(parents=True)
    spec = tmp_path / "specs" / "plan.md"
    spec.write_text(spec_text, encoding="utf-8")
    suite = tmp_path / "tests" / "robot" / "plan.robot"
    suite.write_text(
        "*** Settings ***\n"
        "Documentation       Generated from specs/plan.md by sap-generator.\n"
        "\n*** Test Cases ***\nUn Cas\n    No Operation\n", encoding="utf-8")
    return spec, suite


def test_stamp_puis_garde_ok(tmp_path):
    spec, suite = _repo(tmp_path)
    assert sync_mod.stamp(tmp_path, "tests/robot/plan.robot", "specs/plan.md") == 0
    content = suite.read_text(encoding="utf-8")
    assert "Spec: specs/plan.md (sha256:" in content
    assert sync_mod.check(tmp_path) == 0


def test_spec_modifiee_rend_la_suite_perimee(tmp_path):
    spec, suite = _repo(tmp_path)
    sync_mod.stamp(tmp_path, "tests/robot/plan.robot", "specs/plan.md")
    spec.write_text("# Plan SFLIGHT\n\nScénario 1 MODIFIÉ.\n", encoding="utf-8")
    assert sync_mod.check(tmp_path) == 1


def test_re_stamp_rafraichit_le_marqueur_sans_dupliquer(tmp_path):
    spec, suite = _repo(tmp_path)
    sync_mod.stamp(tmp_path, "tests/robot/plan.robot", "specs/plan.md")
    spec.write_text("# Version 2\n", encoding="utf-8")
    sync_mod.stamp(tmp_path, "tests/robot/plan.robot", "specs/plan.md")
    content = suite.read_text(encoding="utf-8")
    assert content.count("Spec: specs/plan.md") == 1
    assert sync_mod.check(tmp_path) == 0


def test_marqueur_vers_spec_disparue_echoue(tmp_path):
    spec, suite = _repo(tmp_path)
    sync_mod.stamp(tmp_path, "tests/robot/plan.robot", "specs/plan.md")
    spec.unlink()
    assert sync_mod.check(tmp_path) == 1


def test_hash_stable_a_travers_les_fins_de_ligne(tmp_path):
    spec, _ = _repo(tmp_path, spec_text="ligne 1\nligne 2\n")
    digest_lf = sync_mod.spec_digest(spec)
    spec.write_bytes(b"ligne 1\r\nligne 2\r\n")
    assert sync_mod.spec_digest(spec) == digest_lf


def test_specs_sans_suite_informatif_jamais_bloquant(tmp_path, capsys):
    _repo(tmp_path)
    (tmp_path / "specs" / "autre-plan.md").write_text("# X\n", encoding="utf-8")
    (tmp_path / "specs" / "README.md").write_text("contrat\n", encoding="utf-8")
    assert sync_mod.check(tmp_path) == 0
    out = capsys.readouterr().out
    assert "autre-plan.md" in out and "README.md" not in out


def test_suite_sans_ligne_documentation_refuse_le_stamp(tmp_path):
    spec, suite = _repo(tmp_path)
    suite.write_text("*** Test Cases ***\nX\n    No Operation\n", encoding="utf-8")
    assert sync_mod.stamp(tmp_path, "tests/robot/plan.robot", "specs/plan.md") == 1
