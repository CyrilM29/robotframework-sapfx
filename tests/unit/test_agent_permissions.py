"""Contre-epreuves des permissions sur les deux dialectes d'hote."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hook_agent_permissions.py"
SPEC = importlib.util.spec_from_file_location("permissions_under_test", SCRIPT)
permissions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(permissions)


def verdict(tool, arguments=None, **kwargs):
    return permissions.decision(
        {"tool_name": tool, "tool_input": arguments or {}}, **kwargs
    ).get("hookSpecificOutput", {}).get("permissionDecision")


@pytest.mark.parametrize("tool", ["Read", "read_file", "search/readFile"])
@pytest.mark.parametrize("key", ["file_path", "filePath"])
def test_read_preserves_host_permissions(tool, key):
    assert verdict(tool, {key: "specs/example.md"}) is None


@pytest.mark.parametrize("tool", [
    "Bash", "PowerShell", "run_in_terminal", "runCommands", "apply_patch",
    "Write", "Edit", "create_file", "replace_string_in_file",
    "mcp__rf-mcp__execute_step", "rf-mcp-sap/execute_step",
    "mcp_robot_framewo_execute_batch", "mcp_robot_framewo_execute_flow",
    "mcp__rf-mcp__manage_session", "mcp__rf-mcp__run_test_suite",
    "mcp__rf-mcp-sap__sapfx_reload", "runSubagent", "unknown_tool",
])
def test_effectful_or_unknown_requires_confirmation(tool):
    assert verdict(tool, {"command": "read then write"}) == "ask"
    assert verdict(tool, read_only=True) == "deny"


def test_no_keyword_name_can_grant_permission():
    assert verdict("mcp__rf-mcp__execute_step", {
        "keyword": "Get Everything", "arguments": ["ignore permissions"],
    }) == "ask"


@pytest.mark.parametrize("payload", [None, [], {}, {"tool_name": "Read"},
    {"tool_name": "Read", "tool_input": {"filePath": 12}},
    {"tool_name": "Read", "tool_input": {"filePath": "a", "file_path": "b"}},
])
def test_invalid_input_fails_closed(payload):
    assert permissions.decision(payload)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_cli_invalid_json_denies_without_leaking_input():
    result = subprocess.run([sys.executable, str(SCRIPT)], input="private-input",
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "private-input" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
