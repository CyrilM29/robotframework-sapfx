"""Le verificateur reste lecteur dans les deux formats d'agents."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("role_regen", ROOT / "scripts/regen_agent_definitions.py")
assert SPEC is not None and SPEC.loader is not None
regen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(regen)
PREFIX = "sap" if (ROOT / ".claude/agents/sap-healer.md").exists() else "rf"


def test_verifier_has_no_execution_or_editing_tools():
    source = ROOT / f".claude/agents/{PREFIX}-verifier.md"
    meta, _ = regen.parse_front_matter(regen._read_text(source))
    assert set(meta["tools"].split(", ")) == {
        "Read", "Glob", "Grep", "mcp__qa-brain__qa_search",
        "mcp__qa-brain__qa_ask", "mcp__qa-brain__qa_status",
    }
    assert any(path.name == f"{PREFIX}-verifier.agent.md" for path, _ in regen.iter_renders(ROOT))


@pytest.mark.parametrize("tool", ["Bash", "Write", "Edit", "mcp__rf-mcp__execute_step"])
def test_generation_refuses_verifier_privilege_expansion(tmp_path, tool):
    folder = tmp_path / ".claude/agents"
    folder.mkdir(parents=True)
    (folder / f"{PREFIX}-verifier.md").write_text(
        f"---\nname: {PREFIX}-verifier\ndescription: Review\ntools: Read, {tool}\n---\nBody\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="read-only"):
        regen.iter_renders(tmp_path)
