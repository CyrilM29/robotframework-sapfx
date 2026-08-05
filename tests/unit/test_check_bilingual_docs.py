"""Tests hors-SAP du garde-fou de dérive documentaire bilingue
(``scripts/check_bilingual_docs.py``, convention #5 du CLAUDE.md, appliquée
ici à un script d'outillage plutôt qu'à un keyword)."""
import importlib.util
import os
import subprocess

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "check_bilingual_docs.py"))


def _load():
    spec = importlib.util.spec_from_file_location("check_bilingual_docs", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


# --- appariement structurel ---------------------------------------------------

def test_pairing_ok_when_every_md_has_its_fr_counterpart():
    files = ["docs/foo.md", "docs/foo.fr.md", "README.md", "README.fr.md"]
    assert mod.check_pairing(files) == []


def test_pairing_flags_missing_translation():
    files = ["docs/foo.md"]
    problems = mod.check_pairing(files)
    assert len(problems) == 1
    assert "docs/foo.md" in problems[0] and "docs/foo.fr.md" in problems[0]


def test_pairing_flags_orphaned_translation():
    files = ["docs/foo.fr.md"]
    problems = mod.check_pairing(files)
    assert len(problems) == 1
    assert "orpheline" in problems[0]


def test_pairing_ignores_english_only_exceptions():
    files = ["CLAUDE.md", "AGENTS.md", "CHANGELOG.md", ".github/copilot-instructions.md"]
    assert mod.check_pairing(files) == []


def test_pairing_ignores_single_language_trees():
    # Prompts d'agents (Claude Code + chat modes générés), plans specs/ et base
    # de communication comms/ (français natif) : hors du contrat bilingue, dans
    # les deux sens.
    files = [
        ".claude/agents/sap-planner.md",
        ".claude/commands/sap-plan.md",
        ".github/chatmodes/sap-planner.chatmode.md",
        "specs/README.md",
        "specs/sflight-consultation-se16.md",
        "comms/README.md",
        "comms/positionnement.md",
        "comms/posts/01-intro-projet.md",
        "memory/README.md",
        "memory/rfmcp-plugin-hot-reload.md",
    ]
    assert mod.check_pairing(files) == []


# --- dérive de mise à jour -----------------------------------------------------

def test_drift_warns_when_only_the_english_side_changed(monkeypatch):
    files = ["docs/foo.md", "docs/foo.fr.md"]

    def fake_run(cmd, cwd, capture_output, text):
        assert cmd[:3] == ["git", "diff", "--name-only"]
        return subprocess.CompletedProcess(cmd, 0, stdout="docs/foo.md\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)

    warnings = mod.check_drift(files, since="origin/main")
    assert len(warnings) == 1
    assert "docs/foo.md" in warnings[0] and "docs/foo.fr.md" in warnings[0]


def test_drift_silent_when_both_sides_changed_together(monkeypatch):
    files = ["docs/foo.md", "docs/foo.fr.md"]

    def fake_run(cmd, cwd, capture_output, text):
        return subprocess.CompletedProcess(
            cmd, 0, stdout="docs/foo.md\ndocs/foo.fr.md\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert mod.check_drift(files, since="origin/main") == []


def test_drift_silent_when_unpaired_file_already_flagged_by_pairing(monkeypatch):
    files = ["docs/orphan.md"]   # pas de .fr.md du tout

    def fake_run(cmd, cwd, capture_output, text):
        return subprocess.CompletedProcess(cmd, 0, stdout="docs/orphan.md\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert mod.check_drift(files, since="origin/main") == []


def test_drift_gracefully_ignored_when_git_diff_fails(monkeypatch, capsys):
    files = ["docs/foo.md", "docs/foo.fr.md"]

    def fake_run(cmd, cwd, capture_output, text):
        return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="unknown revision")
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert mod.check_drift(files, since="not-a-real-ref") == []
    assert "impossible de diff" in capsys.readouterr().err


# --- main() : code de sortie ---------------------------------------------------

def test_main_returns_nonzero_only_on_real_repo_pairing_problems():
    # Contre le vrai dépôt (pas de mock) : sert de garde-fou vivant contre une
    # doc ajoutée sans sa traduction.
    assert mod.main([]) == 0
