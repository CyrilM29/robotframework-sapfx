"""Tests hors-SAP du garde de dérive de la base de communication
(``scripts/check_comms_sync.py`` — convention #5 du CLAUDE.md, appliquée ici à
un script d'outillage plutôt qu'à un keyword).

Le cas de régression qui compte est ``test_version_de_reference_perimee_echoue``
: c'est l'incident réel qui a motivé le garde (comms/ né en v0.5.0 / 508 tests
alors que le projet était déjà en 0.5.2 avec 617 tests)."""
import importlib.util
import json
import os

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "check_comms_sync.py"))


def _load():
    spec = importlib.util.spec_from_file_location("check_comms_sync", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def _repo(tmp_path, project="0.5.2", reference="0.5.2", deck_cites=None,
          unit_tests=617):
    """Un faux dépôt minimal : un pyproject, une base comms/ et ses sources deck."""
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "x"\nversion = "{project}"\n', encoding="utf-8")
    comms = tmp_path / "comms"
    (comms / "deck").mkdir(parents=True)
    (comms / "positionnement.md").write_text(
        "# Positionnement\n\n## Les preuves\n\n"
        f"**Référence : v{reference}.**\n\n"
        f"- **{unit_tests}** tests unitaires.\n"
        "- **17/17** scénarios validés.\n"
        "- **94 %** de couverture.\n",
        encoding="utf-8")
    (comms / "proofs.json").write_text(json.dumps({
        "version": project,
        "unit_tests": unit_tests,
        "coverage_percent": 94,
        "coverage_floor": 85,
        "live_scenarios": {
            "passed": 17, "total": 17, "target": "A4H",
            "validated_on": "2026-07-13",
        },
        "ui5_range": {"minimum": "1.60", "maximum": "2.0"},
    }), encoding="utf-8")
    if deck_cites:
        (comms / "deck" / "build_deck_fr.py").write_text(
            f'chips = ["v{deck_cites}", "Apache 2.0"]\n', encoding="utf-8")
    return tmp_path


def test_aligne_ok(tmp_path):
    _repo(tmp_path, project="0.5.2", reference="0.5.2", deck_cites="0.5.2")
    assert mod.check(tmp_path) == []


def test_version_de_reference_perimee_echoue(tmp_path):
    # L'incident réel : la base annonce une version que le projet a dépassée.
    _repo(tmp_path, project="0.5.2", reference="0.5.0")
    problems = mod.check(tmp_path)
    assert problems
    assert "0.5.0" in problems[0] and "0.5.2" in problems[0]


def test_citation_contradictoire_dans_les_sources_du_deck(tmp_path):
    # Le marqueur est à jour mais une slide continue d'afficher l'ancienne version.
    _repo(tmp_path, project="0.5.2", reference="0.5.2", deck_cites="0.5.0")
    problems = mod.check(tmp_path)
    assert any("build_deck_fr.py" in p and "0.5.0" in p for p in problems)


def test_marqueur_absent_echoue(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "0.5.2"\n', encoding="utf-8")
    (tmp_path / "comms").mkdir()
    (tmp_path / "comms" / "positionnement.md").write_text(
        "# Sans marqueur de version\n", encoding="utf-8")
    problems = mod.check(tmp_path)
    assert any("ne déclare pas sa version" in problem for problem in problems)


def test_versions_tierces_non_prefixees_ignorees(tmp_path):
    # « UI5 1.60 → 2.0 » ou « 617 » ne doivent jamais être pris pour la version
    # du projet : seul le préfixe « v » compte.
    repo = _repo(tmp_path, project="0.5.2", reference="0.5.2")
    (repo / "comms" / "comparatif.md").write_text(
        "Compatibilité UI5 1.60 → 2.0, extension 0.4.1, 617 tests.\n", encoding="utf-8")
    assert mod.check(repo) == []


def test_project_version_lit_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "1.2.3"\n', encoding="utf-8")
    assert mod.project_version(tmp_path) == "1.2.3"


def test_un_compte_de_tests_perime_dans_un_support_echoue(tmp_path):
    repo = _repo(tmp_path)
    (repo / "comms" / "web.md").write_text("La preuve : 508 tests.\n", encoding="utf-8")
    problems = mod.check(repo)
    assert any("508 tests" in problem and "617" in problem for problem in problems)


def test_verification_runtime_compare_pytest_et_coverage(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    coverage = repo / "coverage.xml"
    coverage.write_text('<coverage line-rate="0.94"/>', encoding="utf-8")
    monkeypatch.setattr(mod, "collect_pytest_tests", lambda root: 617)
    assert mod.check(repo, verify_runtime=True, coverage_xml="coverage.xml") == []

    monkeypatch.setattr(mod, "collect_pytest_tests", lambda root: 618)
    problems = mod.check(repo, verify_runtime=True, coverage_xml="coverage.xml")
    assert any("pytest collecte 618" in problem for problem in problems)
