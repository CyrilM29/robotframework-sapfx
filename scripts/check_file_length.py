"""Garde mécanique de la convention #13 : aucun fichier de code au-delà de 500 lignes.

Un fichier qui franchit la ligne fait plusieurs métiers : il se découpe le
long d'une couture que le dépôt pratique déjà (un mixin par capacité sous
``keywords/``, logique pure extraite vers ``sapfx_common``, un module par
préoccupation, la couche d'exports du recorder à côté de son pilote), jamais
par une coupe à la ligne 500 pour satisfaire le chiffre. La règle vit dans
CLAUDE.md (convention #13) ; ce garde la rend mécanique, dans l'esprit de
``check_no_em_dash.py`` : énoncée ET tenue.

Périmètre (celui de la règle) : tout fichier suivi qu'une machine exécute,
quel que soit le langage (Python, JavaScript y compris les gabarits
``*.js.tpl`` injectés, PowerShell, batch, shell), tests unitaires compris.

Hors périmètre, comme la règle le dit :

* ``comms/`` (générateurs de deck, atlas, visuels) et ``_vendor/``
  (convention #4 : upstream verbatim, indécoupable) ;
* les artefacts GÉNÉRÉS, dont la limite s'applique au générateur :
  ``recorder_snippet.js`` et ``extension/recorder.js`` sortent de
  ``regen_recorder.py`` ;
* tout ce qui n'est pas du code exécuté : Markdown, HTML, suites ``.robot``
  et ``.resource`` (leur longueur suit les scénarios et l'écran qu'elles
  nomment), données.

L'allowlist ``ALLOWED`` est le seul échappatoire, sur le modèle du garde du
cadratin : chaque entrée épingle un COMPTE EXACT de lignes et sa raison ; le
fichier qui bouge doit se découper ou re-déclarer son compte, jamais grossir
en silence. La dette initiale (23 fichiers le 2026-08-25) a été apurée par la
passe de remasterisation du même jour : la carte est VIDE, et l'état visé est
qu'elle le reste.

Usage::

    python scripts/check_file_length.py                    # tout l'arbre suivi
    python scripts/check_file_length.py src/foo.py         # ciblé (hook)
    python scripts/check_file_length.py tools/recorder/    # ciblé, récursif
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from _common import force_utf8_stdio

_ROOT = Path(__file__).resolve().parents[1]

#: Plafond de la convention #13.
MAX_LINES = 500

#: Extensions DANS le périmètre : du code qu'une machine exécute.
CODE_SUFFIXES = (
    ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx",
    ".ps1", ".psm1", ".cmd", ".bat", ".sh", ".tpl",
)

#: Hors périmètre : vendorisé (convention #4), comms (supports graphiques et
#: générateurs de deck/atlas), artefacts de run.
EXEMPT_PREFIXES = (
    "src/SapEccLibrary/_vendor/",
    "comms/",
    "results/",
    "dist/",
    "build/",
)

#: Fichiers GÉNÉRÉS suivis par git : la limite s'applique à leur générateur
#: (``python -m SapFioriLibrary.regen_recorder``), pas à l'artefact.
GENERATED = frozenset({
    "tools/recorder_web/recorder_snippet.js",
    "tools/recorder_web/extension/recorder.js",
})

#: chemin -> (compte de lignes EXACT, raison). Modèle ``check_no_em_dash`` :
#: une entrée est une dette IDENTIFIÉE et bornée, jamais un blanc-seing. Vide
#: depuis l'apurement du 2026-08-25 ; l'état visé est qu'elle le reste.
ALLOWED: dict[str, tuple[int, str]] = {}


def tracked_files(root: Path) -> list[str]:
    """Chemins suivis par git, en POSIX : la liste que voit la CI."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True).stdout
    return [p for p in out.split("\0") if p]


def is_scanned(rel: str) -> bool:
    """Un chemin entre-t-il dans le périmètre du garde ?"""
    posix = rel.replace("\\", "/")
    if posix.startswith(EXEMPT_PREFIXES) or posix in GENERATED:
        return False
    return posix.lower().endswith(CODE_SUFFIXES)


def line_count(path: Path) -> int | None:
    """Nombre de lignes, ou ``None`` pour un fichier illisible/absent (un
    chemin suivi mais supprimé du disque n'est pas une violation)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def relative_target(target: str, root: Path) -> str | None:
    """Chemin relatif POSIX d'une cible, ou ``None`` si elle est hors dépôt
    (le hook post-édition voit passer des fichiers d'autres arbres)."""
    try:
        rel = os.path.relpath(os.path.abspath(target), root)
    except ValueError:
        return None   # autre lecteur Windows : forcément hors dépôt
    rel = rel.replace("\\", "/")
    return None if rel.startswith("../") else rel


def expand_targets(root: Path, targets: list[str]) -> list[str]:
    """Chemins relatifs scannables des cibles, répertoires développés."""
    out: list[str] = []
    for target in targets:
        rel = relative_target(target, root)
        if rel is None:
            continue
        path = root / rel
        if path.is_dir():
            out.extend(p for p in tracked_files(root)
                       if p.startswith(rel.rstrip("/") + "/") and is_scanned(p))
        elif is_scanned(rel):
            out.append(rel)
    return out


def check(root: Path, rels: list[str]) -> list[str]:
    """Messages d'erreur pour les fichiers hors contrat (liste vide = OK)."""
    problems: list[str] = []
    for rel in sorted(set(rels)):
        count = line_count(root / rel)
        if count is None:
            continue
        allowed = ALLOWED.get(rel)
        if allowed is not None:
            expected, reason = allowed
            if count != expected:
                problems.append(
                    "%s : %d lignes, l'allowlist en épingle %d (%s). Le "
                    "fichier a bougé : le découper (convention #13), ou "
                    "re-déclarer le compte exact avec sa raison."
                    % (rel, count, expected, reason))
            continue
        if count > MAX_LINES:
            problems.append(
                "%s : %d lignes (> %d). Un fichier qui franchit la ligne "
                "fait plusieurs métiers : le découper le long d'une couture "
                "du dépôt (mixin par capacité, logique pure vers "
                "sapfx_common, un module par préoccupation), jamais couper "
                "à la ligne %d pour satisfaire le chiffre (convention #13)."
                % (rel, count, MAX_LINES, MAX_LINES))
    return problems


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("targets", nargs="*",
                        help="fichiers ou répertoires à contrôler "
                             "(défaut : tout l'arbre suivi)")
    args = parser.parse_args(argv)

    if args.targets:
        rels = expand_targets(_ROOT, args.targets)
        scope = "ciblé"
    else:
        rels = [p for p in tracked_files(_ROOT) if is_scanned(p)]
        scope = "arbre suivi"

    problems = check(_ROOT, rels)
    if problems:
        print("[check_file_length] ÉCHEC : %d fichier(s) hors contrat."
              % len(problems), file=sys.stderr)
        for problem in problems:
            print("  - " + problem, file=sys.stderr)
        return 1
    print("[check_file_length] OK (%s) : aucun fichier de code au-delà de "
          "%d lignes hors allowlist." % (scope, MAX_LINES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
