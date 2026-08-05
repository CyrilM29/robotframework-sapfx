"""Garde mécanique du tiret cadratin : le tic n°1 qui trahit un texte généré.

CLAUDE.md l'énonce et l'étend depuis le 2026-08-04 à TOUTE la rédaction du
dépôt (docs, README, ``llms.txt``, ``specs/``, mémoire projet, NOTICE,
CHANGELOG), puis
aux docstrings (elles deviennent la doc Libdoc que lisent les utilisateurs) et
aux supports d'assistants. Une règle en prose n'est pas un contrat : ce garde la
rend mécanique, dans l'esprit de ``check_conventions.py``.

Ce qu'il refuse : le caractère U+2014 (« — »), partout dans les fichiers texte
suivis par git. Le remplacement se choisit selon le contexte, jamais
mécaniquement : deux-points, virgule, parenthèses, ou couper la phrase. En
français, l'espace précède le deux-points (« terme : explication ») ; en
anglais, non (``term: explanation``).

Ce qu'il ne refuse PAS :

* le demi-cadratin « – » (U+2013) et le trait d'union « - », qui sont d'autres
  signes, avec d'autres usages (intervalles, mots composés) ;
* les fichiers de l'allowlist ci-dessous, chacun justifié et **borné par un
  compte exact** : une fiche qui doit CITER le caractère (l'énoncé de la règle
  lui-même) garde son occurrence, mais une seconde ferait échouer le garde. Pas
  d'exemption ouverte : une exemption non bornée redevient une porte ouverte ;
* le code vendorisé ``src/SapEccLibrary/_vendor/`` : upstream verbatim, la
  convention #4 interdit d'y toucher.

Garde de cohérence, pas générateur (comme ``check_bilingual_docs`` /
``check_conventions``) : il nomme le fichier, la ligne et le fragment fautif,
la correction reste un choix de rédaction humain.

Usage::

    python scripts/check_no_em_dash.py                 # tout l'arbre suivi
    python scripts/check_no_em_dash.py docs/architecture.md   # ciblé (hook)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

EM_DASH = "—"

_ROOT = Path(__file__).resolve().parents[1]

# Répertoires hors périmètre : code amont vendorisé (convention #4 : verbatim,
# jamais édité) et artefacts de run.
EXEMPT_PREFIXES = (
    "src/SapEccLibrary/_vendor/",
    "results/",
    "dist/",
)

# Extensions binaires / médias : rien à lire.
EXEMPT_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".mp4", ".zip", ".pyc",
    ".pptx", ".woff", ".woff2", ".ttf", ".pdf",
)

# Fichiers autorisés à CITER le caractère, avec le compte EXACT attendu.
# Une occurrence de plus (ou de moins) fait échouer le garde : l'exemption est
# une citation identifiée, pas un blanc-seing.
ALLOWED = {
    "CLAUDE.md": (1, "énonce la règle dans la section Language"),
    "AGENTS.md": (1, "miroir condensé de la règle (convention #7)"),
    ".github/copilot-instructions.md": (1, "miroir condensé de la règle (convention #7)"),
    ".claude/agents/sap-planner.md": (1, "interdit le caractère dans les specs qu'il écrit"),
    ".claude/agents/sap-generator.md": (1, "interdit le caractère dans les specs qu'il écrit"),
    ".claude/agents/sap-healer.md": (1, "interdit le caractère dans specs/ et heal-journal"),
    ".github/chatmodes/sap-planner.chatmode.md": (1, "généré depuis .claude/agents/"),
    ".github/chatmodes/sap-generator.chatmode.md": (1, "généré depuis .claude/agents/"),
    ".github/chatmodes/sap-healer.chatmode.md": (1, "généré depuis .claude/agents/"),
    "scripts/check_no_em_dash.py": (2, "ce garde nomme le caractère qu'il refuse"),
    "tests/unit/test_no_em_dash.py": (8, "teste le garde sur des cas portant le caractère"),
}


def tracked_files(root: Path) -> list[str]:
    """Chemins suivis par git, en POSIX : la liste que voit la CI."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True).stdout
    return [p for p in out.split("\0") if p]


def is_scanned(rel: str) -> bool:
    """Un chemin entre-t-il dans le périmètre du garde ?"""
    posix = rel.replace("\\", "/")
    if posix.startswith(EXEMPT_PREFIXES):
        return False
    return not posix.lower().endswith(EXEMPT_SUFFIXES)


def find_occurrences(text: str) -> list[tuple[int, str]]:
    """``(numéro de ligne, extrait)`` pour chaque cadratin. L'extrait cadre le
    caractère pour que le message dise QUOI corriger, pas seulement où."""
    found = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        start = 0
        while (idx := line.find(EM_DASH, start)) != -1:
            excerpt = line[max(0, idx - 30):idx + 31].strip()
            found.append((lineno, excerpt))
            start = idx + 1
    return found


def read_text(path: Path) -> str | None:
    """Lecture tolérante : un fichier illisible en UTF-8 est ignoré (il ne peut
    pas porter de cadratin UTF-8 mal formé sans être déjà cassé par ailleurs)."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def check(root: Path | str, targets: list[str] | None = None) -> list[str]:
    """Retourne la liste des problèmes (vide = conforme).

    ``root`` est accepté en ``str`` comme en ``Path`` : les appelants (test,
    hook, CLI) ne partagent pas la même convention, et un ``str`` silencieux
    faisait exploser la concaténation de chemins plus bas.
    """
    root = Path(root)
    problems: list[str] = []
    if targets:
        files = []
        for target in targets:
            try:
                rel = os.path.relpath(os.path.abspath(target), root)
            except ValueError:
                # Sous Windows, ``relpath`` lève quand la cible est sur un AUTRE
                # disque (scratchpad en C:, dépôt en E:). C'est forcément hors
                # dépôt : passer, plutôt que faire planter le hook post-édition.
                continue
            rel = rel.replace("\\", "/")
            # Un chemin qui remonte hors du dépôt (``../``) n'est pas à nous :
            # le hook post-édition voit passer des fichiers d'autres arbres (la
            # base mémoire privée, par exemple), qui ont leurs propres règles.
            if rel.startswith("../"):
                continue
            if is_scanned(rel):
                files.append(rel)
    else:
        files = [f for f in tracked_files(root) if is_scanned(f)]

    seen_allowed: dict[str, int] = {}
    for rel in files:
        text = read_text(root / rel)
        if text is None:
            continue
        found = find_occurrences(text)
        if not found:
            continue
        if rel in ALLOWED:
            seen_allowed[rel] = len(found)
            continue
        for lineno, excerpt in found:
            problems.append(
                "%s:%d : tiret cadratin, à remplacer par un deux-points, une "
                "virgule, des parenthèses, ou en coupant la phrase\n      … %s …"
                % (rel, lineno, excerpt))

    # Les citations autorisées sont BORNÉES : dériver du compte attendu est une
    # violation, dans les deux sens (occurrence ajoutée, ou règle disparue).
    # On ne l'exige QUE sur les fichiers réellement scannés : un fichier encore
    # non suivi par git (garde tout juste écrit, avant `git add`) sortirait
    # sinon un échec fantôme « 0 occurrence attendues N ».
    scanned = set(files)
    for rel, (expected, reason) in ALLOWED.items():
        if rel not in scanned:
            continue
        actual = seen_allowed.get(rel, 0)
        if actual != expected:
            problems.append(
                "%s : %d occurrence(s) alors que l'allowlist en attend %d "
                "(%s) : si la citation a bougé, ajuster ALLOWED dans "
                "scripts/check_no_em_dash.py ; sinon corriger le texte."
                % (rel, actual, expected, reason))
    return problems


def main(argv: list[str] | None = None) -> int:
    # Les extraits fautifs embarquent volontiers des flèches (« → », « ↔ ») :
    # sur une console Windows en cp1252, les imprimer brut ferait planter le
    # garde au lieu de rapporter la violation. Même parade que les autres
    # gardes du dépôt.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*",
                        help="fichiers à vérifier (défaut : tout l'arbre suivi)")
    args = parser.parse_args(argv)

    problems = check(_ROOT, args.paths or None)
    if problems:
        print("[check_no_em_dash] ÉCHEC :")
        for problem in problems:
            print("  - %s" % problem)
        print("\n  Règle : jamais de tiret cadratin dans la rédaction du dépôt "
              "(CLAUDE.md § Language).\n  En français l'espace précède le "
              "deux-points (« terme : explication ») ; en anglais non "
              "(term: explanation).")
        return 1
    scope = "ciblé" if args.paths else "arbre suivi"
    print("[check_no_em_dash] OK (%s) : aucun tiret cadratin hors citations "
          "autorisées." % scope)
    return 0


if __name__ == "__main__":
    sys.exit(main())
