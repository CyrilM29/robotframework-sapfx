"""Tests hors-SAP de l'assembleur du pack de déploiement
(``scripts/build_release_pack.py`` — convention #5 du CLAUDE.md, appliquée à un
script d'outillage). Aucun wheel n'est construit ici : on teste la logique pure
(version, exclusions, manifeste, zip) sur des arborescences factices."""
import importlib.util
import os
import zipfile

import pytest

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "build_release_pack.py"))
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load():
    spec = importlib.util.spec_from_file_location("build_release_pack", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


# --- read_version ---------------------------------------------------------------

def test_read_version_reads_project_section():
    text = '[project]\nname = "x"\nversion = "1.2.3"\n'
    assert mod.read_version(text) == "1.2.3"


def test_read_version_ignores_other_sections():
    # Un `version = "9.9"` hors [project] (ex. config d'outil) ne doit pas gagner.
    text = '[tool.autre]\nversion = "9.9"\n[project]\nversion = "0.1.0"\n'
    assert mod.read_version(text) == "0.1.0"


def test_read_version_missing_raises():
    with pytest.raises(ValueError):
        mod.read_version('[project]\nname = "x"\n')


def test_read_version_on_real_pyproject():
    with open(os.path.join(_REPO_ROOT, "pyproject.toml"), encoding="utf-8") as handle:
        version = mod.read_version(handle.read())
    assert version and version[0].isdigit()


# --- is_excluded ----------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "__pycache__/x.py",
    "extension/__pycache__/gen.pyc",
    "captures/shot1.png",
    "extension/dist/pack.zip",
    "extension/store/screenshot.png",
    "module.pyc",
])
def test_is_excluded_true(path):
    assert mod.is_excluded(path)


@pytest.mark.parametrize("path", [
    "sapgui_recorder.py",
    "extension/manifest.json",
    "extension/recorder.js",
    "README.fr.md",
])
def test_is_excluded_false(path):
    assert not mod.is_excluded(path)


# --- build_manifest -------------------------------------------------------------

def _fake_repo(tmp_path):
    """Reproduit la forme minimale du dépôt attendue par le manifeste."""
    for rel, _dest in mod.PACK_FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("contenu", encoding="utf-8")
    for tree, _dest in mod.PACK_TREES:
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)
    (tmp_path / "resources" / "ecc_keywords.resource").write_text("k", encoding="utf-8")
    (tmp_path / "tools/recorder/sapgui_recorder.py").write_text("py", encoding="utf-8")
    # Pollution qui doit être filtrée.
    (tmp_path / "tools/recorder/__pycache__").mkdir()
    (tmp_path / "tools/recorder/__pycache__/x.pyc").write_text("x", encoding="utf-8")
    (tmp_path / "tools/recorder_web/captures").mkdir()
    (tmp_path / "tools/recorder_web/captures/shot.png").write_text("x", encoding="utf-8")
    return tmp_path


def test_build_manifest_includes_expected_and_filters_pollution(tmp_path):
    repo = _fake_repo(tmp_path)
    dests = [dest.as_posix() for _src, dest in mod.build_manifest(repo)]
    assert "README.md" in dests                      # packaging/README.md renommé à la racine
    assert "recorder.cmd" in dests
    assert "resources/ecc_keywords.resource" in dests
    assert "tools/recorder/sapgui_recorder.py" in dests
    assert not any("__pycache__" in dest for dest in dests)
    assert not any("captures" in dest for dest in dests)
    assert dests == sorted(dests)                    # déterministe (zip reproductible)


def test_build_manifest_missing_file_raises(tmp_path):
    repo = _fake_repo(tmp_path)
    (repo / "packaging" / "install.ps1").unlink()
    with pytest.raises(FileNotFoundError):
        mod.build_manifest(repo)


def test_build_manifest_on_real_repo_covers_the_three_deliverables():
    """Le vrai dépôt doit produire un manifeste couvrant bibliothèques (via wheels,
    hors manifeste), recorders, plugins MCP (config) et keywords métier."""
    dests = [dest.as_posix() for _src, dest in mod.build_manifest(_REPO_ROOT)]
    assert "tools/recorder/recorder_gui.py" in dests
    assert "tools/recorder_web/recorder_snippet.js" in dests
    assert "tools/recorder_web/extension/manifest.json" in dests
    assert "mcp.json.template" in dests
    assert "vscode-mcp.json.template" in dests
    assert "resources/fiori_keywords.resource" in dests
    assert "tests/robot/fiori_smoke.robot" in dests
    assert "tests/robot/fiori_wc_smoke.robot" in dests
    assert "tests/robot/fixtures/wc_fixture.html" in dests
    # Sentinelle + flagship (0.5.0) : la veille sans tests et la démonstration
    # écran <-> API font partie des suites d'exemple livrées.
    assert "tests/robot/ecc_drift_sentinel.robot" in dests
    assert "tests/robot/flagship_cross_paradigm.robot" in dests
    # Outillage de maintenance embarqué (stdlib pure, racine du pack).
    assert "scripts/healing_drift_report.py" in dests
    assert "scripts/check_spec_sync.py" in dests
    assert "LICENSE" in dests and "NOTICE" in dests  # attribution Apache-2.0 embarquée
    # Agents de test : définitions Claude Code + chat modes VS Code générés +
    # slash-commands + plans d'exemple (cycle plan -> generate -> heal du pack).
    assert ".claude/agents/sap-planner.md" in dests
    assert ".claude/agents/sap-generator.md" in dests
    assert ".claude/agents/sap-healer.md" in dests
    assert ".claude/commands/sap-plan.md" in dests
    # Skill « boîte à outils » (install-as-a-skill) embarquée avec les agents.
    assert ".claude/skills/sapfx/SKILL.md" in dests
    assert ".github/chatmodes/sap-planner.chatmode.md" in dests
    assert "specs/README.md" in dests
    assert "specs/sflight-consultation-se16.md" in dests
    assert not any("__pycache__" in dest for dest in dests)
    assert not any(dest.endswith(".pyc") for dest in dests)


# --- assemble : lanceurs batch en CRLF -------------------------------------------

def test_normalize_crlf_converts_and_is_idempotent():
    assert mod.normalize_crlf(b"@echo off\nREM a\n") == b"@echo off\r\nREM a\r\n"
    assert mod.normalize_crlf(b"@echo off\r\nREM a\r\n") == b"@echo off\r\nREM a\r\n"


def test_assemble_forces_crlf_on_cmd_launchers(tmp_path):
    """cmd.exe exige du CRLF : un install.cmd livré en LF pur (checkout git eol=lf)
    crache «'M' n'est pas reconnu…» au double-clic — vécu sur le pack 0.6.2."""
    repo = _fake_repo(tmp_path / "repo")
    (repo / "packaging" / "install.cmd").write_bytes(b"@echo off\nREM x\n")
    (repo / "packaging" / "README.md").write_bytes(b"ligne1\nligne2\n")
    stage = tmp_path / "stage"
    stage.mkdir()
    mod.assemble(repo, stage)
    assert (stage / "install.cmd").read_bytes() == b"@echo off\r\nREM x\r\n"
    # Seuls les .cmd sont normalisés — le reste du manifeste est copié tel quel.
    assert (stage / "README.md").read_bytes() == b"ligne1\nligne2\n"


# --- pack_name / write_zip --------------------------------------------------------

def test_pack_name():
    assert mod.pack_name("0.1.0") == "sapfx-pack-0.1.0-win"


def test_write_zip_prefixes_entries_with_pack_name(tmp_path):
    stage = tmp_path / "sapfx-pack-0.1.0-win"
    (stage / "wheels").mkdir(parents=True)
    (stage / "wheels" / "a.whl").write_text("w", encoding="utf-8")
    (stage / "README.md").write_text("r", encoding="utf-8")
    zip_path = tmp_path / "pack.zip"
    mod.write_zip(stage, zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(archive.namelist())
    assert names == ["sapfx-pack-0.1.0-win/README.md", "sapfx-pack-0.1.0-win/wheels/a.whl"]


def test_checksums_cover_stage_and_zip_without_self_reference(tmp_path):
    stage = tmp_path / "sapfx-pack-0.1.0-win"
    stage.mkdir()
    (stage / "README.md").write_text("contenu", encoding="utf-8")
    checksums = mod.write_stage_checksums(stage)
    text = checksums.read_text(encoding="ascii")
    assert mod.file_sha256(stage / "README.md") in text
    assert "README.md" in text
    assert "SHA256SUMS.txt" not in text

    zip_path = tmp_path / "pack.zip"
    mod.write_zip(stage, zip_path)
    sidecar = mod.write_checksum_file(zip_path)
    assert sidecar.read_text(encoding="ascii") == (
        "%s  pack.zip\n" % mod.file_sha256(zip_path))
