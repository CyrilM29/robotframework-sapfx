"""Garde pre-execution commun Claude Code/Copilot, sans decision LLM."""
from __future__ import annotations

import json
import os
import sys

READ_TOOLS = frozenset({
    "Read", "Glob", "Grep", "read_file", "file_search", "grep_search",
    "list_dir", "semantic_search", "get_errors", "view_image",
    "search/readFile", "search/fileSearch", "search/textSearch",
    "search/listDirectory",
})
READ_MCP = frozenset({
    "mcp__qa-brain__qa_search", "mcp__qa-brain__qa_ask",
    "mcp__qa-brain__qa_status", "qa-brain/qa_search", "qa-brain/qa_ask",
    "qa-brain/qa_status", "mcp_qa-brain_qa_search", "mcp_qa-brain_qa_ask",
    "mcp_qa-brain_qa_status",
})


def decision(payload: object, *, read_only: bool = False) -> dict:
    """Ne jamais emettre allow : conserver les permissions de base de l'hote."""
    if not isinstance(payload, dict):
        return response("deny", "Invalid hook input.")
    tool = payload.get("tool_name")
    arguments = payload.get("tool_input")
    if not isinstance(tool, str) or not isinstance(arguments, dict):
        return response("deny", "Missing tool name or structured arguments.")
    paths = [arguments[key] for key in ("file_path", "filePath") if key in arguments]
    if any(not isinstance(path, str) for path in paths):
        return response("deny", "Invalid file path.")
    if len(paths) == 2 and paths[0] != paths[1]:
        return response("deny", "Conflicting host file paths.")
    if tool in READ_TOOLS or tool in READ_MCP:
        return {}
    if read_only:
        return response("deny", "Read-only policy: execution, edits and unknown tools are denied.")
    return response(
        "ask",
        "Confirm this exact tool call, target and arguments. Unknown effects require review; "
        "previous approval does not authorize changed arguments or replay after an unknown outcome.",
    )


def response(verdict: str, reason: str) -> dict:
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": verdict,
        "permissionDecisionReason": reason,
    }}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        mode = os.environ.get("RF_AGENT_READ_ONLY", "0")
        if mode not in {"0", "1"}:
            raise ValueError("Invalid policy mode")
        result = decision(payload, read_only=mode == "1")
    except Exception:
        result = response("deny", "Permission hook failed; execution is denied.")
    print(json.dumps(result))
    return 2 if result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny" else 0


if __name__ == "__main__":
    sys.exit(main())
