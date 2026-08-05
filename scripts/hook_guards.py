"""Hook PostToolUse (Write|Edit) : lance les gardes après toute édition des
artefacts du cycle agentique (specs/, tests/robot/, resources/, variables/).

Deux sévérités, calées sur la nature de chaque garde :

* ``check_conventions.py`` (localisateur brut dans une suite GÉNÉRÉE, ``Sleep``
  n'importe où) : une violation est TOUJOURS un bug de l'artefact → exit 2, le
  message remonte à l'assistant qui doit corriger immédiatement ;
* ``check_spec_sync.py`` (suite périmée, plan marqué PÉRIMÉE) : un échec peut
  être transitoire au milieu d'un cycle légitime (plan annoté puis re-stampé
  par sap-generator) → non bloquant, remonté en information.

Porté depuis rf-test-agents (même auteur). Entrée : le JSON du hook sur stdin ;
sortie : JSON Claude Code le cas échéant.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WATCHED = ("/specs/", "/tests/robot/", "/resources/", "/variables/")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    normalized = file_path.replace("\\", "/")
    root = Path(__file__).resolve().parents[1]

    def run(script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(root / "scripts" / script), *args],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace")

    # Le tiret cadratin se vérifie sur TOUT fichier édité, pas seulement sur les
    # artefacts du cycle agentique : c'est une règle de rédaction globale, et la
    # rattraper à l'écriture coûte une seconde contre une relecture entière.
    if file_path:
        em_dash = run("check_no_em_dash.py", file_path)
        if em_dash.returncode != 0:
            sys.stderr.write(em_dash.stdout + em_dash.stderr)
            return 2  # bloquant : l'assistant doit reformuler tout de suite

    if not any(segment in normalized for segment in WATCHED):
        return 0

    conventions = run("check_conventions.py")
    if conventions.returncode != 0:
        sys.stderr.write(conventions.stdout + conventions.stderr)
        return 2  # bloquant : l'assistant doit corriger la ventilation

    sync = run("check_spec_sync.py")
    if sync.returncode != 0:
        report = (sync.stdout + sync.stderr).strip()
        print(json.dumps({
            "systemMessage": "check_spec_sync : dérive plan ↔ suite détectée "
                             "(voir détail) : re-stamper, régénérer, ou "
                             "ré-explorer si le plan est marqué PÉRIMÉE.",
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": report,
            },
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
