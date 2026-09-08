"""Reprises sans reexecution implicite et refus des jalons incoherents."""
import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import agent_journal as journal


def test_interruption_after_dispatch_requires_reconciliation(tmp_path):
    journal.record(tmp_path, "mission", "action", "planned")
    assert journal.recovery(journal.read_action(tmp_path, "mission", "action")) == "authorization_required"
    journal.record(tmp_path, "mission", "action", "sent")
    assert journal.recovery(journal.read_action(tmp_path, "mission", "action")) == "reconcile_before_retry"
    journal.record(tmp_path, "mission", "action", "confirmed", "proof-1")
    assert journal.recovery(journal.read_action(tmp_path, "mission", "action")) == "do_not_replay"


def test_absence_does_not_automatically_authorize_retry(tmp_path):
    journal.record(tmp_path, "mission", "action", "planned")
    journal.record(tmp_path, "mission", "action", "sent")
    journal.record(tmp_path, "mission", "action", "reconciled_absent", "proof-1")
    assert journal.recovery(journal.read_action(tmp_path, "mission", "action")) == "new_authorization_required"


def test_event_cannot_be_overwritten(tmp_path):
    journal.record(tmp_path, "mission", "action", "planned")
    with pytest.raises(ValueError, match="overwritten"):
        journal.record(tmp_path, "mission", "action", "planned")


@pytest.mark.parametrize("phase", ["sent", "confirmed", "reconciled_absent"])
def test_out_of_order_events_are_refused(tmp_path, phase):
    with pytest.raises(ValueError):
        journal.record(tmp_path, "mission", "action", phase, "proof")


def test_stale_lock_requires_human_review(tmp_path):
    folder = tmp_path / "mission"
    folder.mkdir()
    (folder / "action.lock").touch()
    assert journal.main(["recover", "mission", "action", "--root", str(tmp_path)]) == 2


def test_confirmation_without_evidence_is_refused(tmp_path):
    with pytest.raises(ValueError, match="evidence"):
        journal.record(tmp_path, "mission", "action", "confirmed")


def test_no_raw_payload_in_journal(tmp_path):
    event = journal.record(tmp_path, "mission", "action", "planned")
    assert set(event) == {"schema_version", "mission_id", "action_id", "phase", "evidence_id", "timestamp"}
    with pytest.raises(ValueError):
        journal.record(tmp_path, "mission", "action", "sent", "password=private")


@pytest.mark.parametrize("payload", [None, [], {}, {"schema_version": True}])
def test_malformed_event_blocks_recovery(tmp_path, payload):
    folder = tmp_path / "mission"
    folder.mkdir()
    (folder / "action.planned.json").write_text(json.dumps(payload), encoding="utf-8")
    assert journal.main(["recover", "mission", "action", "--root", str(tmp_path)]) == 2
