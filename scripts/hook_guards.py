"""Hook PostToolUse (Write|Edit) : lance les gardes après toute édition des
artefacts du cycle agentique (specs/, tests/robot/, resources/, variables/).

Deux sévérités, calées sur la nature de chaque garde :

* ``check_conventions.py`` (localisateur brut dans une suite GÉNÉRÉE, ``Sleep``
  n'importe où) : une violation est TOUJOURS un bug de l'artefact → exit 2, le
  message remonte à l'assistant qui doit corriger immédiatement ;
* ``check_spec_sync.py`` (suite périmée, plan marqué PÉRIMÉE) : un échec peut
  être transitoire au milieu d'un cycle légitime (plan annoté puis re-stampé
  par sap-generator) → non bloquant, remonté en information.

La décision vit dans :func:`decide`, séparée des entrées/sorties : le hook
relaie des sous-processus, c'est la seule façon d'en tester les quatre
branches sans dépôt jetable ni garde en échec pour de bon
(``tests/unit/test_hook_guards.py``, convention #5 appliquée à l'outillage).

Porté depuis rf-test-agents (même auteur). Entrée : le JSON du hook sur stdin ;
sortie : JSON Claude Code le cas échéant.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

from _common import force_utf8_stdio

WATCHED = ("/specs/", "/tests/robot/", "/resources/", "/variables/")

#: Signature d'un lanceur de garde : ``run(script, *args) -> CompletedProcess``.
Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def make_runner(root: Path) -> Runner:
    """Lanceur réel : un garde du dépôt, exécuté depuis sa racine.

    ``encoding="utf-8"`` : les gardes forcent leur sortie en UTF-8, la décoder
    dans l'encodage du poste rendrait mojibake ce que le hook doit relayer.
    """
    def run(script: str, *args: str) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            [sys.executable, str(root / "scripts" / script), *args],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
    return run


def decide(file_path: str, run: Runner) -> tuple[int, str, str]:
    """Retourne ``(code de sortie, texte pour stderr, texte pour stdout)``.

    Aucune écriture ici : c'est ce qui rend les quatre branches testables.
    """
    normalized = file_path.replace("\\", "/")

    # Le tiret cadratin se vérifie sur TOUT fichier édité, pas seulement sur les
    # artefacts du cycle agentique : c'est une règle de rédaction globale, et la
    # rattraper à l'écriture coûte une seconde contre une relecture entière.
    if file_path:
        em_dash = run("check_no_em_dash.py", file_path)
        if em_dash.returncode != 0:
            # bloquant : l'assistant doit reformuler tout de suite
            return 2, em_dash.stdout + em_dash.stderr, ""

        # Éditer un README/doc publié est LE moment où une version périmée (nom
        # du pack, épinglage pip) ou un badge de version gravé se glisse : le
        # garde tourne tout de suite plutôt qu'à la release suivante.
        if normalized.endswith((".md", ".txt")):
            versions = run("check_published_versions.py")
            if versions.returncode != 0:
                # bloquant : la version citée doit suivre pyproject
                return 2, versions.stdout + versions.stderr, ""

    if not any(segment in normalized for segment in WATCHED):
        return 0, "", ""

    conventions = run("check_conventions.py")
    if conventions.returncode != 0:
        # bloquant : l'assistant doit corriger la ventilation
        return 2, conventions.stdout + conventions.stderr, ""

    sync = run("check_spec_sync.py")
    if sync.returncode != 0:
        report = (sync.stdout + sync.stderr).strip()
        message = json.dumps({
            "systemMessage": "check_spec_sync : dérive plan ↔ suite détectée "
                             "(voir détail) : re-stamper, régénérer, ou "
                             "ré-explorer si le plan est marqué PÉRIMÉE.",
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": report,
            },
        }, ensure_ascii=False)
        return 0, "", message
    return 0, "", ""


def main() -> int:
    # Ce hook RELAIE la sortie des gardes, qui nomment des caractères et des
    # écrans hors cp1252 : sans cette bascule, sous Windows, le message
    # actionnable arrivait en mojibake sur ``stderr`` et la branche
    # d'information ci-dessous mourait en UnicodeEncodeError sur ``stdout``
    # (le « ↔ » de son systemMessage). Un hook qui plante au lieu d'informer
    # est pire que pas de hook.
    force_utf8_stdio()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    root = Path(__file__).resolve().parents[1]

    code, err, out = decide(file_path, make_runner(root))
    if err:
        sys.stderr.write(err)
    if out:
        print(out)
    return code


if __name__ == "__main__":
    sys.exit(main())
