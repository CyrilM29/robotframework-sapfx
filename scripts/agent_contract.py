"""Contrats de mission et verdicts, controles hors application testee."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
HEAL_VERDICTS = frozenset({
    "repaired_verified", "application_defect", "blocked", "needs_human", "not_verified",
})


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
        raise ValueError("Expected a non-sensitive identifier")
    return value


def confined_path(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Expected a relative artifact path")
    path = (root / value).resolve()
    if Path(value).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes the workspace")
    return path


def validate_handoff(data: object, root: Path) -> dict:
    required = {"schema_version", "mission_id", "target", "invariant", "scope",
                "mode", "budgets", "evidence"}
    if not isinstance(data, dict):
        raise ValueError("Handoff is not an object")
    if set(data) != required:
        extra, missing = sorted(set(data) - required), sorted(required - set(data))
        raise ValueError(
            "Invalid handoff fields (extra: %s; missing: %s). The schema is "
            "closed on purpose: a free-form key is where an agent slips an "
            "unchecked claim into an artifact that is supposed to be verified."
            % (", ".join(extra) or "none", ", ".join(missing) or "none"))
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported handoff schema")
    identifier(data["mission_id"])
    identifier(data["target"])
    if not isinstance(data["invariant"], str) or not data["invariant"].strip():
        raise ValueError("Missing business invariant")
    if data["mode"] not in {"read_only", "explore", "full"}:
        raise ValueError("Invalid mission mode")
    if not isinstance(data["scope"], list) or not data["scope"]:
        raise ValueError("Missing authorized scope")
    for item in data["scope"]:
        confined_path(root, item)
    budgets = data["budgets"]
    if not isinstance(budgets, dict) or set(budgets) != {"attempts", "tool_calls", "seconds"}:
        raise ValueError("Invalid budget fields")
    if any(type(value) is not int or value <= 0 for value in budgets.values()):
        raise ValueError("Budgets must be positive integers")
    evidence = data["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Missing evidence")
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("Invalid evidence fields")
        path = confined_path(root, item["path"])
        if not path.is_file():
            raise ValueError("Evidence file is missing: %s" % item["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(
                "Evidence hash mismatch on %s (the file changed after the "
                "handoff was signed; re-sign with --refresh once the change "
                "is intended)" % item["path"])
    return data


def refresh_evidence(data: dict, root: Path) -> list[tuple[str, str, str]]:
    """Recompute every evidence hash in place, returning what moved.

    An explicit, visible gesture rather than a silent repair: a handoff is an
    attestation, so re-signing one is a decision, and the caller must see
    which artifact drifted. It only touches hashes, so a handoff that is
    invalid for any other reason stays invalid and says so.
    """
    moved: list[tuple[str, str, str]] = []
    for item in data.get("evidence", []):
        if not isinstance(item, dict) or "path" not in item:
            continue
        path = confined_path(root, item["path"])
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item.get("sha256"):
            moved.append((item["path"], str(item.get("sha256"))[:12], digest[:12]))
            item["sha256"] = digest
    return moved


def heal_verdict(facts: dict) -> str:
    required = {"failure_class", "target_matches", "invariant_preserved",
                "replay_passed", "scope_complete", "new_skips", "new_baselines",
                "evidence_checked", "budget_exhausted", "unknown_write_outcome"}
    if not isinstance(facts, dict) or set(facts) != required:
        raise ValueError("Incomplete verdict facts")
    for key in required - {"failure_class", "new_skips", "new_baselines"}:
        if type(facts[key]) is not bool:
            raise ValueError("Verdict flags must be booleans")
    for key in ("new_skips", "new_baselines"):
        if type(facts[key]) is not int or facts[key] < 0:
            raise ValueError("Verdict counts must be non-negative integers")
    category = facts["failure_class"]
    if category not in {"locator_drift", "timing", "data_drift", "library_defect",
                        "functional_change", "application_defect", "unknown"}:
        raise ValueError("Unknown failure class")
    if not facts["target_matches"] or facts["unknown_write_outcome"]:
        return "needs_human"
    if not facts["evidence_checked"]:
        return "not_verified"
    if category == "application_defect":
        return "application_defect"
    if category in {"functional_change", "data_drift"}:
        return "needs_human"
    if facts["new_skips"] or facts["new_baselines"] or not facts["invariant_preserved"]:
        return "needs_human"
    if facts["budget_exhausted"]:
        return "blocked"
    if category == "unknown" or not facts["replay_passed"] or not facts["scope_complete"]:
        return "not_verified"
    return "repaired_verified"


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["handoff", "verdict"])
    parser.add_argument("artifact", type=Path, nargs="?")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--all", action="store_true",
                        help="check every specs/*.handoff.json under --root")
    parser.add_argument("--refresh", action="store_true",
                        help="re-sign evidence hashes that drifted, and say which")
    args = parser.parse_args(argv)

    if args.all:
        if args.operation != "handoff":
            parser.error("--all only applies to the handoff operation")
        return _check_every_handoff(args.root, args.refresh)
    if args.artifact is None:
        parser.error("an artifact path is required unless --all is given")
    return _check_one(args.operation, args.artifact, args.root, args.refresh)


def _check_one(operation, artifact: Path, root: Path, refresh: bool) -> int:
    """One artifact, with the REASON printed on refusal.

    The generic wording this used to print ("Invalid or unreadable agent
    artifact") hid the one thing a reader needs: three handoffs of this repo
    were invalid at once, for three different reasons, and telling them apart
    required rewriting the check by hand. A guard that will not say why is a
    guard nobody repairs.
    """
    try:
        data = json.loads(artifact.read_text(encoding="utf-8-sig"))
        if operation != "handoff":
            result = heal_verdict(data)
            print(json.dumps({"verdict": result,
                              "basis": "supplied facts, independent review required"}))
            return 0 if result == "repaired_verified" else 1
        if refresh:
            for path, before, after in refresh_evidence(data, root):
                print("re-signed %s: %s -> %s" % (path, before, after))
            artifact.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8", newline="\n")
        validate_handoff(data, root)
        print("Handoff structure and evidence hashes verified; "
              "business truth not inferred.")
        return 0
    except (ValueError, TypeError, OSError) as err:
        print("%s: %s" % (artifact, err), file=sys.stderr)
        return 2


def _check_every_handoff(root: Path, refresh: bool) -> int:
    """Every sidecar at once, which is what a repository guard needs.

    Checking one file at a time is why this never ran anywhere: a guard has to
    be able to sweep. Missing sidecars are not invented here, an empty sweep
    simply says so rather than passing silently.
    """
    sidecars = sorted((root / "specs").glob("*.handoff.json"))
    if not sidecars:
        print("No handoff sidecar found under specs/.", file=sys.stderr)
        return 2
    failed = 0
    for sidecar in sidecars:
        if _check_one("handoff", sidecar, root, refresh) != 0:
            failed += 1
    print("[agent_contract] %d handoff(s) checked, %d invalid."
          % (len(sidecars), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
