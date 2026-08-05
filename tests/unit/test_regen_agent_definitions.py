"""Tests hors-ligne du déclinateur de définitions d'agents
(``scripts/regen_agent_definitions.py``, convention #5 du CLAUDE.md, appliquée
à un script d'outillage, comme ``test_build_release_pack.py``). Vérifie le
parse du frontmatter plat, la table de correspondance des outils Claude Code →
VS Code, le rendu chat mode, la détection de dérive ``--check``, et, sur le
VRAI dépôt, que les chat modes committés sont à jour (pendant pytest du check CI)."""
import importlib.util
import os

import pytest

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "regen_agent_definitions.py"))
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load():
    spec = importlib.util.spec_from_file_location(
        "regen_agent_definitions", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()

_SAMPLE = (
    "---\n"
    "name: sap-demo\n"
    "description: Demo agent, with: a colon and \"quotes\".\n"
    "tools: Read, Glob, Write, mcp__rf-mcp-sap__execute_step\n"
    "---\n"
    "\n"
    "Body line 1.\n"
)


# --- parse_front_matter -----------------------------------------------------------

def test_parse_front_matter_splits_meta_and_body():
    meta, body = mod.parse_front_matter(_SAMPLE)
    assert meta["name"] == "sap-demo"
    # partition sur le PREMIER ':' seulement : la description peut en contenir.
    assert meta["description"] == 'Demo agent, with: a colon and "quotes".'
    assert body == "\nBody line 1.\n"


def test_parse_front_matter_requires_leading_marker():
    with pytest.raises(ValueError):
        mod.parse_front_matter("pas de frontmatter\n")


def test_parse_front_matter_requires_closing_marker():
    with pytest.raises(ValueError):
        mod.parse_front_matter("---\nname: x\n")


# --- map_tools --------------------------------------------------------------------

def test_map_tools_emits_qualified_builtins_sorted_by_reference_order():
    # Formes qualifiées et tri : le dialecte émis par le generateAgents.ts de
    # Playwright (edit/* d'abord, puis search/*, runCommands en dernier).
    assert mod.map_tools("Read, Glob, Grep, Write, Edit, Bash") == [
        "edit/createFile", "edit/createDirectory", "edit/editFiles",
        "search/fileSearch", "search/textSearch", "search/readFile",
        "runCommands"]


def test_map_tools_qualifies_mcp_tools_per_tool_after_builtins():
    # Granularité par outil préservée (rf-mcp-sap/<outil>), MCP après les
    # builtins, dans l'ordre d'apparition.
    tools = "mcp__rf-mcp-sap__manage_session, mcp__rf-mcp-sap__execute_step, Read"
    assert mod.map_tools(tools) == [
        "search/readFile",
        "rf-mcp-sap/manage_session", "rf-mcp-sap/execute_step"]


def test_map_tools_fails_loud_on_unknown_tool():
    with pytest.raises(ValueError):
        mod.map_tools("Read, OutilInconnu")


@pytest.mark.parametrize("malformed", ["mcp__seulement-le-serveur", "mcp__srv__"])
def test_map_tools_rejects_malformed_mcp_name(malformed):
    with pytest.raises(ValueError):
        mod.map_tools(malformed)


# --- render_chatmode ---------------------------------------------------------------

def test_render_chatmode_produces_valid_front_matter_banner_and_body():
    meta, body = mod.parse_front_matter(_SAMPLE)
    out = mod.render_chatmode(".claude/agents/sap-demo.md", meta, body)
    # Frontmatter VS Code : description JSON-quotée (sous-ensemble YAML) + tools.
    assert out.startswith(
        '---\ndescription: "Demo agent, with: a colon and \\"quotes\\"."\n')
    assert ('tools: ["edit/createFile", "edit/createDirectory", '
            '"search/fileSearch", "search/readFile", '
            '"rf-mcp-sap/execute_step"]\n---\n') in out
    assert "FICHIER GÉNÉRÉ" in out and ".claude/agents/sap-demo.md" in out
    assert out.endswith("\nBody line 1.\n")


def test_render_chatmode_requires_description_and_tools():
    with pytest.raises(ValueError):
        mod.render_chatmode("src.md", {"description": "x"}, "body")


# --- iter_renders / main ------------------------------------------------------------

def _fake_workspace(tmp_path):
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "sap-demo.md").write_text(_SAMPLE, encoding="utf-8")
    return tmp_path


def test_iter_renders_names_destination_after_the_meta_name(tmp_path):
    root = _fake_workspace(tmp_path)
    ((dest, content),) = mod.iter_renders(root)
    assert dest == root / ".github" / "chatmodes" / "sap-demo.chatmode.md"
    assert "Body line 1." in content


def test_iter_renders_without_sources_raises(tmp_path):
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        mod.iter_renders(tmp_path)


def test_main_generates_then_check_detects_drift(tmp_path, capsys):
    root = _fake_workspace(tmp_path)
    assert mod.main(["--root", str(root)]) == 0
    assert mod.main(["--root", str(root), "--check"]) == 0
    # Dérive : la cible est modifiée à la main -> --check doit échouer.
    dest = root / ".github" / "chatmodes" / "sap-demo.chatmode.md"
    dest.write_text(dest.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
    assert mod.main(["--root", str(root), "--check"]) == 1
    assert "obsolète" in capsys.readouterr().out
    # Cible manquante -> --check doit échouer aussi.
    dest.unlink()
    assert mod.main(["--root", str(root), "--check"]) == 1


def test_check_is_insensitive_to_crlf_checkouts(tmp_path):
    # Un checkout Windows (autocrlf) peut réécrire source ET cible en CRLF :
    # la comparaison doit rester stable.
    root = _fake_workspace(tmp_path)
    assert mod.main(["--root", str(root)]) == 0
    for path in [root / ".claude" / "agents" / "sap-demo.md",
                 root / ".github" / "chatmodes" / "sap-demo.chatmode.md"]:
        crlf = path.read_text(encoding="utf-8").replace("\n", "\r\n")
        path.write_bytes(crlf.encode("utf-8"))
    assert mod.main(["--root", str(root), "--check"]) == 0


def test_committed_chatmodes_are_up_to_date_on_the_real_repo():
    # Garde-fou vivant (pendant pytest du --check CI) : oublier de régénérer
    # .github/chatmodes/ après avoir édité .claude/agents/ doit casser la CI.
    assert mod.main(["--root", _REPO_ROOT, "--check"]) == 0
