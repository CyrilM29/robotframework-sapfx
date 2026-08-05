"""Vérifie que le fichier vendorisé (``src/SapEccLibrary/_vendor/sapgui_base.py``)
ne diverge de l'upstream QUE par les changements documentés et tolérés
(convention #4 du CLAUDE.md, ``docs/audit-upstream.md``) : un bloc
d'attribution ajouté en tête, le renommage de classe ``SapGuiLibrary`` ->
``SapGuiBase``, et un commentaire ajouté en fin de ligne ``__version__``. Toute
autre différence signale soit une édition directe du fichier vendorisé
(interdite par la convention 4), soit une nouvelle version amont à auditer
avant de re-synchroniser.

Usage (nécessite un clone local de l'upstream : voir docs/audit-upstream.md
pour la procédure de re-sync manuelle que ce script automatise le contrôle) ::

    python scripts/check_vendor_drift.py
    python scripts/check_vendor_drift.py --upstream-file path/to/SapGuiLibrary.py

Si le fichier upstream n'est pas trouvé (clone local ``_upstream/`` absent,
c'est le cas par défaut, il est gitignored, cf. CLAUDE.md), le script réussit
en le signalant : ce n'est pas un échec bloquant pour la CI principale. Un
clone frais et la vérification tournent séparément, périodiquement, dans
``.github/workflows/vendor-drift.yml``.
"""
import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_UPSTREAM = os.path.join(_ROOT, "_upstream", "SapGuiLibrary", "SapGuiLibrary.py")
_DEFAULT_VENDOR = os.path.join(_ROOT, "src", "SapEccLibrary", "_vendor", "sapgui_base.py")

_OLD_CLASS = "SapGuiLibrary"
_NEW_CLASS = "SapGuiBase"


def _strip_header_block(lines):
    """Retire le bloc d'attribution ajouté en tête du fichier vendorisé (lignes
    vides ou commentaires avant la première ligne de code réelle)."""
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
        i += 1
    return lines[i:]


def _normalize_version_comment(line):
    """Retire un commentaire de fin de ligne ajouté sur la ligne ``__version__``
    (toléré : n'affecte pas la valeur trackée, juste un repère lisible)."""
    if line.strip().startswith("__version__") and "#" in line:
        return line.split("#", 1)[0].rstrip()
    return line


def check(upstream_path, vendor_path):
    """Retourne la liste des divergences non tolérées, en tuples
    ``(n° ligne upstream, ligne upstream attendue, ligne vendor réelle)``."""
    with open(upstream_path, "r", encoding="utf-8") as f:
        upstream_lines = f.read().splitlines()
    with open(vendor_path, "r", encoding="utf-8") as f:
        vendor_lines = _strip_header_block(f.read().splitlines())

    if len(upstream_lines) != len(vendor_lines):
        return [(0, "(%d lignes de code, hors en-tête)" % len(upstream_lines),
                 "(%d lignes de code, hors en-tête)" % len(vendor_lines))]

    problems = []
    for n, (u_line, v_line) in enumerate(
            zip(upstream_lines, vendor_lines, strict=True), start=1):
        expected = u_line
        # Le renommage documenté ne porte QUE sur la déclaration de classe elle-même
        # (docs/audit-upstream.md : "single change") -- pas sur chaque mention
        # textuelle de "SapGuiLibrary" dans les docstrings, qui doivent donc rester
        # identiques mot pour mot à l'upstream (et sont volontairement laissées
        # telles quelles dans le fichier vendorisé).
        if expected.strip().startswith("class %s" % _OLD_CLASS):
            expected = expected.replace(_OLD_CLASS, _NEW_CLASS, 1)
        expected = _normalize_version_comment(expected)
        actual = _normalize_version_comment(v_line)
        if actual != expected:
            problems.append((n, u_line, v_line))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-file", default=_DEFAULT_UPSTREAM)
    parser.add_argument("--vendor-file", default=_DEFAULT_VENDOR)
    args = parser.parse_args(argv)

    if not os.path.isfile(args.upstream_file):
        print("[check_vendor_drift] fichier upstream introuvable (%s) -- clone "
             "local absent, vérification ignorée. Voir docs/audit-upstream.md."
             % args.upstream_file)
        return 0

    problems = check(args.upstream_file, args.vendor_file)
    if not problems:
        print("[check_vendor_drift] OK -- seule différence : renommage de classe "
             "%s -> %s (+ en-tête d'attribution)." % (_OLD_CLASS, _NEW_CLASS))
        return 0

    print("[check_vendor_drift] ECHEC -- %d ligne(s) divergent au-delà du "
         "renommage toléré :" % len(problems))
    for n, u_line, v_line in problems[:20]:
        print("  ligne upstream %d:" % n)
        print("    upstream: %s" % u_line)
        print("    vendor:   %s" % v_line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
