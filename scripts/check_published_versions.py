"""Vérifie qu'aucune **instruction publiée** ne cite une version périmée de SAPFX.

Née de la release 0.6.6 : le badge PyPI d'un README affichait encore la version
précédente. C'était en réalité du **cache** (shields.io répond
``max-age=10800``, et PyPI sert l'image via son proxy camo/Fastly), donc un
faux problème ; mais la vraie leçon est que la parade instinctive, écrire la
version en dur, aurait créé une dette invisible : exacte le jour même, fausse
à la release suivante, et rien pour l'attraper. Ce garde ferme les deux
portes à la fois.

Ce qu'il refuse, dans les fichiers d'INSTRUCTIONS destinés aux utilisateurs
(READMEs, ``docs/``, ``llms.txt``, ``packaging/``) :

1. une **version SAPFX écrite en dur et périmée** dans un artefact que le
   lecteur va chercher ou taper : nom du pack (``sapfx-pack-X.Y.Z-win.zip``),
   nom de wheel, épinglage ``robotframework-sapfx==X.Y.Z`` ;
2. un **badge de version STATIQUE** (``shields.io/badge/pypi-vX.Y.Z-…``) là où
   le badge dynamique (``shields.io/pypi/v/<paquet>``) se met à jour tout seul.

Ce qu'il ne regarde pas, volontairement : les versions **tierces** (rf-mcp,
fastmcp, Docker, UI5, Python : elles n'ont aucune raison de suivre la nôtre) et
les fichiers d'HISTOIRE, où une ancienne version est le propos même
(``CHANGELOG.md``, ``CLAUDE.md``, ``memory/``, ``specs/``,
``docs/heal-journal.md``). C'est aussi pourquoi il cible des motifs précis
plutôt que « tout ce qui ressemble à X.Y.Z » : un garde qui crie au loup finit
désactivé.

Usage : python scripts/check_published_versions.py [--version X.Y.Z]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Fichiers d'INSTRUCTIONS balayés (ce qu'un utilisateur lit pour agir).
#: `docs/heal-journal.md` en est exclu : c'est un journal, ses versions sont
#: des faits datés.
SCANNED_GLOBS = (
    ("", ("README.md", "README.fr.md", "llms.txt")),
    ("docs", None),
    ("packaging", None),
)
SCANNED_SUFFIXES = (".md", ".txt", ".ps1", ".cmd", ".template")
EXCLUDED_NAMES = frozenset({"heal-journal.md"})

#: Motifs (nom, regex à UN groupe capturant la version, remède affiché).
#: Chaque motif vise un artefact que le lecteur va chercher ou taper.
PATTERNS = (
    ("nom du pack",
     re.compile(r"sapfx-pack-(\d+\.\d+\.\d+)-win"),
     "le pack livré s'appelle sapfx-pack-<version>-win.zip"),
    ("wheel des bibliothèques",
     re.compile(r"robotframework_sapfx-(\d+\.\d+\.\d+(?:\.post\d+)?)-py3"),
     "le wheel est nommé d'après la version du paquet"),
    ("wheel du plugin rf-mcp",
     re.compile(r"sap_robotmcp-(\d+\.\d+\.\d+(?:\.post\d+)?)-py3"),
     "le wheel du plugin suit la même version"),
    ("épinglage pip",
     re.compile(r"robotframework-sapfx==(\d+\.\d+\.\d+(?:\.post\d+)?)"),
     "un épinglage publié doit pointer la version courante"),
)

#: Badge de version STATIQUE : la version y est gravée, donc fausse dès la
#: release suivante. Le badge dynamique de shields.io n'a pas ce défaut.
STATIC_BADGE = re.compile(
    r"shields\.io/badge/(?:pypi|version|release)-v?(\d+\.\d+\.\d+)", re.I)

#: Exceptions justifiées, une par une : {(motif, chemin relatif POSIX)}.
#: Vide à dessein : toute entrée future doit porter sa justification ici.
ALLOWED: frozenset[tuple[str, str]] = frozenset()


def current_version(root: str = _ROOT) -> str:
    """Version du projet, lue dans le ``pyproject.toml`` racine (la source de
    vérité que ``test_version_consistency`` fait déjà régner partout)."""
    path = os.path.join(root, "pyproject.toml")
    with open(path, "r", encoding="utf-8") as handle:
        match = re.search(r'^version = "([^"]+)"', handle.read(), re.MULTILINE)
    if not match:
        raise SystemExit("version introuvable dans pyproject.toml")
    return match.group(1)


def scanned_files(root: str = _ROOT) -> list[str]:
    """Chemins relatifs (POSIX) des fichiers d'instructions à balayer."""
    found: list[str] = []
    for folder, names in SCANNED_GLOBS:
        base = os.path.join(root, folder) if folder else root
        if names is not None:
            found.extend(os.path.join(folder, name) if folder else name
                         for name in names
                         if os.path.isfile(os.path.join(base, name)))
            continue
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name in EXCLUDED_NAMES or not name.endswith(SCANNED_SUFFIXES):
                continue
            if os.path.isfile(os.path.join(base, name)):
                found.append("%s/%s" % (folder, name) if folder else name)
    return found


def check_text(rel: str, text: str, version: str) -> list[str]:
    """Problèmes trouvés dans UN fichier (liste vide = conforme)."""
    problems = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern, remedy in PATTERNS:
            for found in pattern.finditer(line):
                if found.group(1) == version or (label, rel) in ALLOWED:
                    continue
                problems.append(
                    "%s:%d : %s cité en %s alors que la version courante est "
                    "%s (%s)." % (rel, line_number, label, found.group(1),
                                  version, remedy))
        for found in STATIC_BADGE.finditer(line):
            problems.append(
                "%s:%d : badge de version STATIQUE (v%s gravé dans l'URL). "
                "Employer le badge dynamique shields.io/pypi/v/<paquet>, qui "
                "suit PyPI tout seul : ce qu'on voit juste après une release "
                "est du cache (shields.io max-age=10800 + proxy camo de "
                "PyPI/GitHub), pas une erreur à corriger à la main."
                % (rel, line_number, found.group(1)))
    return problems


def check(root: str = _ROOT, version: str | None = None) -> list[str]:
    """Retourne la liste des problèmes (vide si tout est aligné)."""
    version = version or current_version(root)
    problems: list[str] = []
    for rel in scanned_files(root):
        with open(os.path.join(root, rel), "r", encoding="utf-8",
                  errors="replace") as handle:
            problems.extend(check_text(rel, handle.read(), version))
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="version attendue (défaut : pyproject.toml)")
    args = parser.parse_args(argv)
    problems = check(version=args.version)
    if not problems:
        print("[check_published_versions] OK : aucune version SAPFX périmée "
              "dans les instructions publiées.")
        return 0
    print("[check_published_versions] ECHEC :")
    for problem in problems:
        print("  - %s" % problem)
    return 1


if __name__ == "__main__":
    sys.exit(main())
