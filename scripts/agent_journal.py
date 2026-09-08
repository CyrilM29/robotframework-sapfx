"""Journal de reprise a jalons immuables, sans donnees d'execution brutes."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent_contract import confined_path, identifier

PHASES = ("planned", "sent", "confirmed", "reconciled_absent", "abandoned")


def read_action(root: Path, mission: str, action: str) -> dict:
    folder = confined_path(root, identifier(mission))
    identifier(action)
    events = {}
    for phase in PHASES:
        path = folder / f"{action}.{phase}.json"
        if path.exists():
            event = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(event, dict) or set(event) != {
                "schema_version", "mission_id", "action_id", "phase", "evidence_id", "timestamp"
            }:
                raise ValueError("Invalid journal schema")
            if type(event["schema_version"]) is not int or event["schema_version"] != 1:
                raise ValueError("Invalid journal version")
            if event["evidence_id"]:
                identifier(event["evidence_id"])
            if phase in {"confirmed", "reconciled_absent"} and not event["evidence_id"]:
                raise ValueError("Missing observation evidence")
            datetime.fromisoformat(event["timestamp"])
            if (event.get("mission_id"), event.get("action_id"), event.get("phase")) != (
                mission, action, phase
            ):
                raise ValueError("Journal identity mismatch")
            events[phase] = event
    if events and "planned" not in events:
        raise ValueError("Missing planned event")
    if any(phase in events for phase in ("confirmed", "reconciled_absent")) and "sent" not in events:
        raise ValueError("Missing sent event")
    if sum(phase in events for phase in ("confirmed", "reconciled_absent", "abandoned")) > 1:
        raise ValueError("Conflicting terminal events")
    return events


def recovery(events: dict) -> str:
    if "confirmed" in events:
        return "do_not_replay"
    if "abandoned" in events:
        return "needs_human"
    if "reconciled_absent" in events:
        return "new_authorization_required"
    if "sent" in events:
        return "reconcile_before_retry"
    return "authorization_required"


def record(root: Path, mission: str, action: str, phase: str, evidence: str = "") -> dict:
    if phase not in PHASES:
        raise ValueError("Unknown event phase")
    if evidence:
        identifier(evidence)
    if phase in {"confirmed", "reconciled_absent"} and not evidence:
        raise ValueError("A terminal observation needs an evidence identifier")
    folder = confined_path(root, identifier(mission))
    identifier(action)
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / f"{action}.lock"
    with lock.open("x", encoding="utf-8") as lock_stream:
        try:
            events = read_action(root, mission, action)
            if phase in events:
                raise ValueError("An event cannot be overwritten")
            if any(terminal in events for terminal in ("confirmed", "reconciled_absent", "abandoned")):
                raise ValueError("Action already terminated")
            if phase != "planned" and "planned" not in events:
                raise ValueError("Plan before execution")
            if phase in {"confirmed", "reconciled_absent"} and "sent" not in events:
                raise ValueError("Record dispatch before its outcome")
            event = dict(schema_version=1, mission_id=mission, action_id=action,
                         phase=phase, evidence_id=evidence,
                         timestamp=datetime.now(timezone.utc).isoformat())
            with (folder / f"{action}.{phase}.json").open("x", encoding="utf-8") as stream:
                json.dump(event, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            return event
        finally:
            lock_stream.close()
            lock.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["record", "recover"])
    parser.add_argument("mission")
    parser.add_argument("action")
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--evidence", default="")
    parser.add_argument("--root", type=Path, default=Path("results/agent_runs"))
    args = parser.parse_args(argv)
    try:
        if args.operation == "record":
            record(args.root, args.mission, args.action, args.phase, args.evidence)
        events = read_action(args.root, args.mission, args.action)
        if (args.root / identifier(args.mission) / f"{identifier(args.action)}.lock").exists():
            raise ValueError("Journal locked: interrupted or concurrent writer")
        print(json.dumps({"next_action": recovery(events), "events": len(events)}))
        return 0
    except (ValueError, TypeError, OSError):
        print("Journal unavailable or inconsistent; stop and reconcile manually.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
