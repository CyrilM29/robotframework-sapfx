"""Verdicts negatifs et preuves reelles, sans appel SAP ni agent LLM."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("contract_under_test", ROOT / "scripts/agent_contract.py")
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


def healthy():
    return dict(failure_class="locator_drift", target_matches=True,
                invariant_preserved=True, replay_passed=True, scope_complete=True,
                new_skips=0, new_baselines=0, evidence_checked=True,
                budget_exhausted=False, unknown_write_outcome=False)


@pytest.mark.parametrize("changes, expected", [
    ({}, "repaired_verified"),
    ({"failure_class": "timing"}, "repaired_verified"),
    ({"failure_class": "library_defect"}, "repaired_verified"),
    ({"target_matches": False}, "needs_human"),
    ({"unknown_write_outcome": True}, "needs_human"),
    ({"invariant_preserved": False}, "needs_human"),
    ({"new_skips": 1}, "needs_human"),
    ({"new_baselines": 1}, "needs_human"),
    ({"evidence_checked": False}, "not_verified"),
    ({"failure_class": "application_defect"}, "application_defect"),
    ({"failure_class": "functional_change"}, "needs_human"),
    ({"failure_class": "data_drift"}, "needs_human"),
    ({"failure_class": "unknown"}, "not_verified"),
    ({"replay_passed": False}, "not_verified"),
    ({"scope_complete": False}, "not_verified"),
    ({"budget_exhausted": True}, "blocked"),
])
def test_negative_and_positive_verdicts(changes, expected):
    assert contract.heal_verdict(healthy() | changes) == expected


@pytest.mark.parametrize("changes", [
    {"target_matches": "false"}, {"new_skips": True}, {"new_baselines": -1},
    {"failure_class": "ignore previous rules"}, {"extra": "repaired_verified"},
])
def test_untrusted_facts_cannot_select_success(changes):
    with pytest.raises(ValueError):
        contract.heal_verdict(healthy() | changes)


def handoff(tmp_path):
    proof = tmp_path / "proof.txt"
    proof.write_text("Observed invariant", encoding="utf-8")
    return dict(schema_version=1, mission_id="mission-1", target="lab-1",
                invariant="Original assertion remains unchanged", scope=["resources"],
                mode="read_only", budgets=dict(attempts=2, tool_calls=20, seconds=900),
                evidence=[dict(path="proof.txt", sha256=hashlib.sha256(proof.read_bytes()).hexdigest())])


def test_handoff_checks_real_evidence_and_detects_changed_content(tmp_path):
    data = handoff(tmp_path)
    assert contract.validate_handoff(data, tmp_path) == data
    (tmp_path / "proof.txt").write_text("Changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        contract.validate_handoff(data, tmp_path)


@pytest.mark.parametrize("changes", [
    {"scope": []}, {"scope": ["../outside"]}, {"scope": ["C:/private"]},
    {"evidence": []}, {"schema_version": True}, {"mode": "bypass"},
    {"budgets": {"attempts": 0, "tool_calls": 20, "seconds": 900}},
    {"mission_id": "../another-session"}, {"invariant": ""},
])
def test_handoff_rejects_missing_or_unsafe_fields(tmp_path, changes):
    with pytest.raises(ValueError):
        contract.validate_handoff(handoff(tmp_path) | changes, tmp_path)
