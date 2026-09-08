"""Un hook commun aux deux hotes, sans approbation implicite."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("tool, argument", [
    ("Edit", {"file_path": "resources/example.resource"}),
    ("replace_string_in_file", {"filePath": "resources/example.resource"}),
])
def test_real_config_executes_confirmation_gate(tool, argument):
    # `.claude/settings.json` porte les permissions du poste de développement :
    # l'export public l'EXCLUT nommément. Ce test se saute donc sur l'arbre
    # exporté, qui est validé avant d'être publié, au lieu d'y échouer sur une
    # absence voulue (même règle que les gardes dont le périmètre vient de
    # `git ls-files`). Le fichier de configuration livré par le pack Windows,
    # lui, est `packaging/agent-settings.json`, contrôlé juste en dessous : la
    # propriété n'est jamais vérifiée à vide.
    settings = ROOT / ".claude/settings.json"
    if not settings.exists():
        pytest.skip("arbre sans .claude/settings.json (export public) : "
                    "la configuration du poste n'y est pas publiée")
    config = json.loads(settings.read_text(encoding="utf-8"))
    hooks = config["hooks"]["PreToolUse"]
    assert len(hooks) == 1 and hooks[0]["matcher"] == ".*"
    hook = hooks[0]["hooks"][0]
    # Le chemin du script est ancré sur le dépôt, jamais relatif au répertoire
    # de travail de la session. Vécu le 2026-09-08 : une session dont le shell
    # était passé dans un dépôt voisin a vu le hook échouer sur « fichier
    # introuvable », donc TOUT appel d'outil refusé, y compris le `cd` qui
    # aurait ramené le shell. Un hook qui plante bloque, il ne dégrade pas.
    assert hook["command"] == (
        'python "$CLAUDE_PROJECT_DIR/scripts/hook_agent_permissions.py"')
    result = subprocess.run(
        [sys.executable, "scripts/hook_agent_permissions.py"], cwd=ROOT,
        input=json.dumps(dict(tool_name=tool, tool_input=argument)),
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_le_pack_livre_le_meme_hook_ancre_sur_le_depot():
    """La configuration que le pack Windows dépose en `.claude/settings.json`.

    Elle est publiée, donc elle survit à l'export : c'est ce contrôle qui
    empêche le test voisin de ne rien prouver là où il se saute. Un poste qui
    déplie le pack hérite du même ancrage, et le même blocage total lui serait
    arrivé avec un chemin relatif.
    """
    config = json.loads(
        (ROOT / "packaging/agent-settings.json").read_text(encoding="utf-8"))
    hooks = config["hooks"]["PreToolUse"]
    assert len(hooks) == 1 and hooks[0]["matcher"] == ".*"
    assert hooks[0]["hooks"][0]["command"] == (
        'python "$CLAUDE_PROJECT_DIR/scripts/hook_agent_permissions.py"')
    # Le pack livre le script que ce hook appelle (garde de clôture voisine).
    assert (ROOT / "scripts/hook_agent_permissions.py").exists()
