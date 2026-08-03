"""Tests hors-SAP du garde-fou de cohérence guidance rf-mcp <-> CLAUDE.md
(``scripts/check_guidance_sync.py`` — convention #5 du CLAUDE.md, appliquée à
un script d'outillage)."""
import importlib.util
import os

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "check_guidance_sync.py"))


def _load():
    spec = importlib.util.spec_from_file_location("check_guidance_sync", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def test_check_passes_against_the_real_repo_files():
    # Garde-fou vivant : contre le vrai CLAUDE.md et le vrai _guidance.py du
    # dépôt, aucune divergence ne doit être détectée.
    assert mod.check() == []


def test_check_flags_a_claude_md_anchor_that_moved_or_was_reworded(monkeypatch, tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("Ce fichier ne parle plus du tout de time.sleep.", encoding="utf-8")
    monkeypatch.setattr(mod, "_CLAUDE_MD", str(claude_md))
    problems = mod.check()
    assert any("introuvable" in p for p in problems)


def test_check_flags_a_guidance_hint_that_dropped_a_tracked_keyword(monkeypatch, tmp_path):
    guidance = tmp_path / "_guidance.py"
    guidance.write_text(
        "COMMON_HINTS = ['Parler le vocabulaire metier, id sap brut interdit.']\n"
        "ECC_HINTS = ['reponse ok']\n"
        "FIORI_HINTS = ['reponse ok']\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_GUIDANCE_PY", str(guidance))
    problems = mod.check()
    # "time.sleep" (convention #2, hints communs) a disparu -> doit être signalé.
    assert any("time.sleep" in p for p in problems)
    # mais "id sap brut" (convention #1) est resté -> pas signalé pour celui-là.
    assert not any("id sap brut" in p and "time.sleep" not in p for p in problems)


def test_check_flags_an_agent_definition_that_dropped_a_marker(monkeypatch, tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    # Mentionne resources/ et le type de message, mais plus l'interdiction des
    # attentes fixes (convention #2) -> doit être signalé, et uniquement lui.
    (agents / "sap-planner.md").write_text(
        "Locators live in resources/. Assert the message type only.",
        encoding="utf-8")
    monkeypatch.setattr(mod, "_AGENTS_DIR", str(agents))
    problems = mod.check()
    assert any("time.sleep" in p and "sap-planner.md" in p for p in problems)
    assert not any("resources/" in p for p in problems)


def test_check_flags_missing_agent_definitions(monkeypatch, tmp_path):
    empty = tmp_path / "agents"
    empty.mkdir()
    monkeypatch.setattr(mod, "_AGENTS_DIR", str(empty))
    problems = mod.check()
    assert any("sap-*.md" in p for p in problems)


def test_check_flags_a_keyword_map_lagging_behind_the_library(monkeypatch, tmp_path):
    # La dérive réelle 0.5.6 -> 0.6.1 : le plugin existe mais sa carte ne
    # mentionne plus un keyword phare d'un mixin -> doit être signalé.
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "ecc_plugin.py").write_text(
        '"Attach To Open Session", "Open Sap Session", "Create Gui Session",\n'
        '"Close All Sap Sessions", "Set Default Timeout", "Set Poll Interval",\n'
        '"Get Annotated Screenshot", "Screen Should Match Baseline",\n'
        '"Check Screen Against Watch", "Click Element At Offset",\n'
        '"Get Screen Map", "Click Screen Ref",\n'
        '"Lookup Business Term", "Client Security Should Be Hardened",\n',
        encoding="utf-8")   # tout... sauf "Get Open Windows"
    (plugins / "fiori_plugin.py").write_text(
        "\n".join('"%s",' % kw for kw in mod._MAP_MARKERS["fiori_plugin.py"]),
        encoding="utf-8")
    monkeypatch.setattr(mod, "_PLUGINS_DIR", str(plugins))
    problems = mod.check()
    assert any("Get Open Windows" in p and "ecc_plugin.py" in p for p in problems)
    assert not any("fiori_plugin.py" in p for p in problems)


def test_check_flags_a_missing_plugin_file(monkeypatch, tmp_path):
    empty = tmp_path / "plugins"
    empty.mkdir()
    monkeypatch.setattr(mod, "_PLUGINS_DIR", str(empty))
    problems = mod.check()
    assert any("plugin rf-mcp introuvable" in p for p in problems)


def test_main_returns_nonzero_and_prints_on_failure(monkeypatch, tmp_path, capsys):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("rien d'utile ici", encoding="utf-8")
    monkeypatch.setattr(mod, "_CLAUDE_MD", str(claude_md))
    rc = mod.main([])
    assert rc == 1
    assert "ECHEC" in capsys.readouterr().out
