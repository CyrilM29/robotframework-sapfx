"""Garde-fou de dérive documentaire bilingue (convention CLAUDE.md : chaque doc
a un original anglais `*.md` et une version française `*.fr.md`).

Deux vérifications, toutes deux sans dépendance externe (juste `git` en PATH) :

1. **Appariement structurel** — chaque `*.md` suivi par git (hors exceptions
   volontairement anglais-seul : CLAUDE.md, AGENTS.md, CHANGELOG.md,
   .github/copilot-instructions.md ; et hors arborescences volontairement
   monolingues : définitions d'agents/commands et chat modes générés — des
   prompts techniques, pas des docs — ainsi que `specs/`, rédigé en français,
   la langue de travail de l'équipe) a son pendant `*.fr.md`, et réciproquement.
   Détecte une doc oubliée à sa création ou une traduction orpheline renommée.

2. **Dérive de mise à jour** (avec ``--since <ref>``) — dans l'ensemble de
   fichiers modifiés depuis ``<ref>``, si `X.md` est modifié sans que `X.fr.md`
   le soit (ou l'inverse), avertit : la doc peut avoir dérivé de sa traduction.
   Ce n'est qu'un signal (pas une validation sémantique du contenu traduit).

Usage ::

    python scripts/check_bilingual_docs.py                  # appariement seul
    python scripts/check_bilingual_docs.py --since origin/main  # + dérive PR

Code de sortie non nul si un problème est détecté (adapté à la CI).
"""
import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Docs délibérément anglais-seul (cf. CLAUDE.md "## Language / Langue").
_EN_ONLY = {
    "CLAUDE.md",
    "AGENTS.md",
    "CHANGELOG.md",
    ".github/copilot-instructions.md",
}

# Docs délibérément français-seul : journaux de travail append-only, écrits en
# continu par les agents dans la langue de travail de l'équipe (même logique
# que specs/). Les traduire à chaque entrée n'aurait aucun sens — ce sont des
# traces d'exécution, pas de la documentation destinée à être lue en anglais.
_FR_ONLY = {
    "docs/heal-journal.md",
}

# Arborescences délibérément monolingues, hors du contrat bilingue : les
# définitions d'agents/slash-commands et leurs chat modes générés sont des
# prompts techniques (comme le code) ; specs/ est rédigé directement en
# français par l'agent sap-planner ; comms/ est la base de communication du
# projet (messaging, ton de voix, playbooks), rédigée en français, la langue de
# travail de l'équipe — les *supports* qu'elle produit peuvent, eux, être
# bilingues (le deck existe en FR et en EN) ; memory/ est la mémoire projet
# des assistants IA (fiches de travail anonymisées, rédigées en français, la
# langue de travail — même logique que specs/).
_SINGLE_LANGUAGE_PREFIXES = (
    ".claude/",
    ".github/chatmodes/",
    "comms/",
    "memory/",
    "specs/",
)


def _is_exempt(path):
    """Vrai si ce chemin est hors du contrat bilingue EN/FR."""
    return (path in _EN_ONLY or path in _FR_ONLY
            or path.startswith(_SINGLE_LANGUAGE_PREFIXES))


def _tracked_md_files():
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=_ROOT, capture_output=True,
                         text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def check_pairing(files):
    """Retourne la liste des messages d'erreur (vide si tout est apparié)."""
    problems = []
    files_set = set(files)
    for path in files:
        if _is_exempt(path) or path.endswith(".fr.md"):
            continue
        expected_fr = path[: -len(".md")] + ".fr.md"
        if expected_fr not in files_set:
            problems.append(f"{path} n'a pas de traduction {expected_fr}")
    for path in files:
        if not path.endswith(".fr.md") or _is_exempt(path):
            continue
        expected_en = path[: -len(".fr.md")] + ".md"
        if expected_en not in files_set:
            problems.append(f"{path} est une traduction orpheline (pas de {expected_en})")
    return problems


def check_drift(files, since):
    """Retourne la liste des messages d'avertissement de dérive depuis ``since``."""
    diff = subprocess.run(["git", "diff", "--name-only", f"{since}...HEAD"],
                          cwd=_ROOT, capture_output=True, text=True)
    if diff.returncode != 0:
        print(f"[check_bilingual_docs] impossible de diff contre {since!r} : "
             f"{diff.stderr.strip()} -- vérification de dérive ignorée.", file=sys.stderr)
        return []
    changed = {line for line in diff.stdout.splitlines() if line}
    files_set = set(files)
    warnings = []
    for path in files:
        if _is_exempt(path):
            continue
        if path.endswith(".fr.md"):
            sibling = path[: -len(".fr.md")] + ".md"
        else:
            sibling = path[: -len(".md")] + ".fr.md"
        if sibling not in files_set:
            continue  # déjà signalé par check_pairing
        if path in changed and sibling not in changed:
            warnings.append(f"{path} modifié depuis {since} sans que {sibling} le soit")
    # Dédoublonne les paires signalées deux fois (une fois par sens EN->FR / FR->EN).
    return sorted(set(warnings))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", metavar="REF",
                        help="en plus de l'appariement, avertit si un .md a changé "
                             "depuis REF (ex. origin/main) sans son .fr.md, ou l'inverse")
    args = parser.parse_args(argv)

    files = _tracked_md_files()
    problems = check_pairing(files)
    for p in problems:
        print(f"[ERREUR] {p}")

    warnings = check_drift(files, args.since) if args.since else []
    for w in warnings:
        print(f"[AVERTISSEMENT] {w}")

    if problems:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
