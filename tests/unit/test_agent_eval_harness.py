"""Tests off-SAP du harnais d'évaluation des agents
(``scripts/agent_eval_harness.py`` — convention #5 appliquée à l'outillage).

On rejoue le cycle inject → (healer simulé) → verify sur un mini-dépôt
temporaire : aucun robot, aucun agent, aucun SAP.
"""
import importlib.util
import json
import os

import pytest

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "agent_eval_harness.py"))


def _load():
    spec = importlib.util.spec_from_file_location("agent_eval_harness", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()

_RESOURCE = (
    "*** Variables ***\n"
    "${SE16_COUNT_BUTTON}        wnd[0]/tbar[1]/btn[31]             # comptage\n")


@pytest.fixture()
def fake_repo(tmp_path):
    (tmp_path / "resources").mkdir()
    (tmp_path / "resources" / "ecc_keywords.resource").write_text(
        _RESOURCE, encoding="utf-8")
    (tmp_path / "resources" / "fiori_keywords.resource").write_text(
        "*** Variables ***\n", encoding="utf-8")
    robot_dir = tmp_path / "tests" / "robot"
    robot_dir.mkdir(parents=True)
    (robot_dir / "ecc_scarr_spfli_liaisons.robot").write_text(
        "*** Test Cases ***\nCompter\n    Count Table Entries    SCARR\n",
        encoding="utf-8")
    return str(tmp_path)


def _resource_text(root):
    path = os.path.join(root, "resources", "ecc_keywords.resource")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_inject_applies_the_drift_and_backs_up_the_original(fake_repo):
    messages = mod.inject("se16-count-button", root=fake_repo)
    assert any("btn[31] -> " in m or "btn[13]" in m for m in messages)
    text = _resource_text(fake_repo)
    assert "btn[13]" in text and "btn[31]" not in text
    state_path = os.path.join(fake_repo, mod.STATE_DIR, "se16-count-button.json")
    backup_path = os.path.join(fake_repo, mod.STATE_DIR, "se16-count-button.orig")
    assert os.path.exists(state_path) and os.path.exists(backup_path)
    with open(backup_path, "r", encoding="utf-8") as f:
        assert f.read() == _RESOURCE
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    # la surface protégée couvre les tests ET l'autre resource, pas la cible
    assert "tests/robot/ecc_scarr_spfli_liaisons.robot" in state["protected"]
    assert "resources/fiori_keywords.resource" in state["protected"]
    assert "resources/ecc_keywords.resource" not in state["protected"]


def test_inject_refuses_a_double_injection(fake_repo):
    mod.inject("se16-count-button", root=fake_repo)
    with pytest.raises(mod.HarnessError, match="déjà injecté"):
        mod.inject("se16-count-button", root=fake_repo)


def test_inject_refuses_an_ambiguous_target(fake_repo):
    path = os.path.join(fake_repo, "resources", "ecc_keywords.resource")
    with open(path, "a", encoding="utf-8") as f:
        f.write("${AUTRE}    wnd[0]/tbar[1]/btn[31]\n")
    with pytest.raises(mod.HarnessError, match="ambiguë"):
        mod.inject("se16-count-button", root=fake_repo)


def test_inject_refuses_an_unknown_scenario(fake_repo):
    with pytest.raises(mod.HarnessError, match="scénario inconnu"):
        mod.inject("nope", root=fake_repo)


def test_verify_passes_when_the_healer_repaired_the_one_line(fake_repo):
    mod.inject("se16-count-button", root=fake_repo)
    # healer simulé : restaure exactement la ligne d'origine
    path = os.path.join(fake_repo, "resources", "ecc_keywords.resource")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_RESOURCE)
    ok, messages = mod.verify("se16-count-button", root=fake_repo)
    assert ok is True
    assert any("PASS" in m for m in messages)
    assert any("à l'identique" in m for m in messages)
    # PASS nettoie l'état : le harnais est prêt pour la prochaine éval
    assert not os.path.exists(
        os.path.join(fake_repo, mod.STATE_DIR, "se16-count-button.json"))


def test_verify_fails_when_the_drift_was_not_repaired(fake_repo):
    mod.inject("se16-count-button", root=fake_repo)
    ok, messages = mod.verify("se16-count-button", root=fake_repo)
    assert ok is False
    assert any("toujours présent" in m for m in messages)
    assert any("FAIL" in m for m in messages)
    # l'état est conservé pour restore
    assert os.path.exists(
        os.path.join(fake_repo, mod.STATE_DIR, "se16-count-button.json"))


def test_verify_fails_when_a_test_file_was_touched(fake_repo):
    mod.inject("se16-count-button", root=fake_repo)
    path = os.path.join(fake_repo, "resources", "ecc_keywords.resource")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_RESOURCE)
    test_path = os.path.join(fake_repo, "tests", "robot",
                             "ecc_scarr_spfli_liaisons.robot")
    with open(test_path, "a", encoding="utf-8") as f:
        f.write("# le healer n'a PAS le droit de faire ça\n")
    ok, messages = mod.verify("se16-count-button", root=fake_repo)
    assert ok is False
    assert any("fichiers protégés modifiés" in m
               and "ecc_scarr_spfli_liaisons.robot" in m for m in messages)


def test_verify_passes_with_a_note_when_repaired_differently(fake_repo):
    mod.inject("se16-count-button", root=fake_repo)
    path = os.path.join(fake_repo, "resources", "ecc_keywords.resource")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_RESOURCE + "# note du healer\n")
    ok, messages = mod.verify("se16-count-button", root=fake_repo)
    assert ok is True
    assert any("diffère de" in m for m in messages)


def test_restore_puts_the_original_back(fake_repo):
    mod.inject("se16-count-button", root=fake_repo)
    messages = mod.restore("se16-count-button", root=fake_repo)
    assert any("restauré" in m for m in messages)
    assert _resource_text(fake_repo) == _RESOURCE
    state_dir = os.path.join(fake_repo, mod.STATE_DIR)
    assert not os.listdir(state_dir)
    # après restore, une nouvelle injection est possible
    mod.inject("se16-count-button", root=fake_repo)


def test_restore_without_backup_is_an_actionable_error(fake_repo):
    with pytest.raises(mod.HarnessError, match="rien à restaurer"):
        mod.restore("se16-count-button", root=fake_repo)


def test_the_default_scenario_matches_the_real_repo_resource():
    # Garde vivant : la cible du scénario canonique existe (exactement une
    # occurrence) dans la vraie resource du dépôt — sinon le harnais est mort.
    scenario = mod.SCENARIOS["se16-count-button"]
    real = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", scenario["file"]))
    with open(real, "r", encoding="utf-8") as f:
        text = f.read()
    assert text.count(scenario["old"]) == 1
    assert scenario["new"] not in text


def test_main_cli_list_and_error_paths(fake_repo, capsys, monkeypatch):
    assert mod.main(["list"]) == 0
    assert "se16-count-button" in capsys.readouterr().out
    assert mod.main(["inject"]) == 2          # scénario manquant
    monkeypatch.setattr(mod, "_ROOT", fake_repo)
    assert mod.main(["inject", "se16-count-button"]) == 0
    assert mod.main(["verify", "se16-count-button"]) == 1   # pas réparé
    assert mod.main(["restore", "se16-count-button"]) == 0
    assert mod.main(["inject", "nope"]) == 2
