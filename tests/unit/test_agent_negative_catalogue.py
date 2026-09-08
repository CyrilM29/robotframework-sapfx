"""Les oracles du catalogue ne mesurent pas le comportement d'un modele."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("negative_contract", ROOT / "scripts/agent_contract.py")
assert SPEC is not None and SPEC.loader is not None
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)
CASES = json.loads((ROOT / "tests/agent_eval/cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_catalogue_oracles(case):
    facts = dict(failure_class="locator_drift", target_matches=True,
                 invariant_preserved=True, replay_passed=True, scope_complete=True,
                 new_skips=0, new_baselines=0, evidence_checked=True,
                 budget_exhausted=False, unknown_write_outcome=False)
    assert case["fixture"] and case["forbidden"]
    assert contract.heal_verdict(facts | case["facts"]) == case["expected"]
    assert case["expected"] != "repaired_verified"


def test_trial_ids_are_unique():
    assert len({case["id"] for case in CASES}) == len(CASES)
