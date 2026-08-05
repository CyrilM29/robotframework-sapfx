"""Garde mécanique des conventions #1 et #2 : celles qu'un linter peut prouver.

Les agents (sap-generator, sap-healer) et CLAUDE.md promettent en prose que :

* **convention #1** : les tests ne contiennent aucun localisateur brut ; les
  ids d'éléments SAP GUI (``wnd[0]/usr/ctxt…``, ``/app/con[0]/ses[0]/…``), les
  adresses de contrôles UI5 et les sélecteurs DOM (``css=``, ``xpath=``,
  ``//…``) vivent dans ``resources/`` ou ``variables/locators.py``, jamais dans
  un fichier de ``tests/robot/`` ;
* **convention #2** : jamais de ``Sleep`` pour attendre SAP ; les attentes
  réelles (``Wait Until Busy Done``, ``Wait Until Element Present``,
  ``Wait For UI5 Ready``) uniquement, dans les tests COMME dans la couche
  ``resources/``.

Pourquoi ce garde existe : ``check_guidance_sync.py`` vérifie que les
conventions restent *énoncées* (dans CLAUDE.md, dans les hints rf-mcp, dans les
définitions d'agents), mais rien ne vérifiait qu'elles soient *tenues* par les
artefacts produits. Une règle en prose n'est pas un contrat : ce garde la rend
mécanique. Il est appelé comme gate par sap-generator (entre le dry run et le
run live), par le hook post-édition du workspace et par la CI. Échec = un
artefact viole une convention → corriger la ventilation (déplacer le
localisateur dans un page object, remplacer le ``Sleep`` par une attente
réelle), jamais contourner le garde.

Porté depuis le projet rf-test-agents (même auteur, cœur universel du cycle
plan → generate → heal), avec les motifs SAP en plus : le garde y était né du
constat que les conventions #1/#2 n'étaient tenues que par la discipline du
modèle.

**Périmètre de la convention #1 : la nuance propre à ce dépôt.** Ici, deux
familles de suites cohabitent sous ``tests/robot/`` :

* les suites **générées depuis un plan** par sap-generator, elles portent le
  marqueur de provenance ``Spec: specs/<plan>.md (sha256:…)``. Ce sont des
  tests *métier*, dérivés d'un plan relu par le métier : la convention #1 y est
  **bloquante**, sans exception ;
* les suites **écrites à la main pour valider la bibliothèque** elle-même
  (``business_data_exploration``, ``exploratory_campaign_a4h``,
  ``ecc_multisession_smoke``, ``cross_paradigm_api_visual``…). Leur objet EST
  de piloter SAP par ses ids bruts pour prouver que ``SapEccLibrary`` les
  résout : leur y interdire les ids bruts n'aurait aucun sens. Elles sont donc
  **signalées à titre informatif**, jamais bloquantes (``--strict`` les rend
  bloquantes, pour un chantier de mise en conformité assumé).

La convention #2 (``Sleep``), elle, est **universelle et bloquante partout**,
tests comme resources, générés ou pas : aucune attente fixe ne se justifie.

Ce découpage est auto-maintenu : il se lit sur le marqueur de provenance, il
n'y a aucune liste d'exemptions à tenir à jour.

Limites assumées : détection par motifs sur les cellules Robot Framework
(séparateur 2+ espaces ou tabulation) ; les blocs ``Documentation`` et les
commentaires sont ignorés (on peut y CITER un localisateur). Un localisateur
exotique peut passer : le garde attrape les violations franches, la revue
humaine garde le reste.

Usage::

    python scripts/check_conventions.py              # tout le workspace
    python scripts/check_conventions.py tests/robot/ecc_smoke.robot   # ciblé
    python scripts/check_conventions.py --strict     # tout est bloquant
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Stratégies de localisation explicites (SeleniumLibrary, Browser, UI5) en tête
# de cellule. `timeout=`, `text=`… la liste est fermée pour éviter les faux
# positifs sur les arguments nommés courants.
_STRATEGY = re.compile(
    r"^(css|xpath|id|link|partial link|name|class|tag|dom|jquery)"
    r"\s*[:=]", re.IGNORECASE)
# XPath nu : la cellule commence par // ou (//
_BARE_XPATH = re.compile(r"^\(?//")
# Sélecteur chaîné Browser : `parent >> child`
_CHAINED = re.compile(r"\s>>\s")
# Ids d'éléments SAP GUI : chemin de la hiérarchie de contrôles SAP.
#   wnd[0]/usr/ctxtRF02K-KUNNR · wnd[1]/tbar[0]/btn[0]
#   /app/con[0]/ses[0]/wnd[0]/... (forme absolue)
_SAP_GUI_ID = re.compile(r"(^|/)(wnd|usr|tbar|mbar|ses|con)\[?[0-9]*\]?/")
# Adresse de contrôle UI5 passée en clair (le vocabulaire métier doit
# l'encapsuler) : controlType=..., bindingPath=..., idSuffix=...
_UI5_ADDRESS = re.compile(
    r"^(controlType|bindingPath|idSuffix|viewName|properties)\s*[:=]",
    re.IGNORECASE)

_CELL_SPLIT = re.compile(r"\t|[ ]{2,}")

# Marqueur de provenance apposé par check_spec_sync.py --stamp : sa présence
# signe une suite GÉNÉRÉE depuis un plan (cf. § Périmètre de la convention #1).
_PROVENANCE = re.compile(r"Spec:\s*specs/[^\s]+\.md\s*\(sha256:")


def is_generated_suite(path: Path) -> bool:
    """Vrai si la suite porte le marqueur de provenance de sap-generator."""
    try:
        return bool(_PROVENANCE.search(
            path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def _cells(line: str) -> list[str]:
    """Cellules RF de la ligne, commentaires (# …) tronqués."""
    cells = [c.strip() for c in _CELL_SPLIT.split(line.rstrip())]
    kept = []
    for cell in cells:
        if cell.startswith("#"):
            break
        if cell:
            kept.append(cell)
    return kept


def _is_sleep(cell: str) -> bool:
    # RF matche les keywords sans casse ; `BuiltIn.Sleep` est le nom qualifié.
    return cell.lower() in ("sleep", "builtin.sleep")


def _is_raw_locator(cell: str) -> bool:
    if cell.startswith(("http://", "https://")):
        return False
    return bool(_STRATEGY.match(cell) or _BARE_XPATH.match(cell)
                or _CHAINED.search(cell) or _SAP_GUI_ID.search(cell)
                or _UI5_ADDRESS.match(cell))


def scan_file(path: Path, forbid_locators: bool) -> list[tuple[int, str, int]]:
    """(ligne, message, n° de convention) pour chaque violation du fichier.

    ``forbid_locators=True`` pour les fichiers de tests (convention #1) ;
    le ``Sleep`` (convention #2) est interdit partout.
    """
    problems = []
    in_doc = False
    for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(),
            start=1):
        cells = _cells(line)
        if not cells:
            continue
        first = cells[0]
        # Blocs Documentation : on peut y citer un localisateur en prose.
        if first in ("Documentation", "[Documentation]"):
            in_doc = True
            continue
        if in_doc and first == "...":
            continue
        in_doc = False
        for cell in cells:
            if _is_sleep(cell):
                problems.append(
                    (lineno, "Sleep interdit (convention #2) : utiliser "
                             "Wait Until Busy Done / Wait Until Element "
                             "Present / Wait For UI5 Ready", 2))
                break
        if forbid_locators:
            for cell in cells[1:] if first != "..." else cells:
                if _is_raw_locator(cell):
                    problems.append(
                        (lineno, "localisateur brut dans un test "
                                 "(convention #1) : « %s » ; le déplacer dans "
                                 "resources/page_objects/ ou "
                                 "variables/locators.py" % cell, 1))
    return problems


def check(repo_root: Path, targets: list[str] | None = None,
          strict: bool = False) -> int:
    """0 = conventions tenues, 1 = au moins une violation bloquante.

    Bloquant = toute violation de la convention #2, plus les violations de la
    convention #1 dans les suites **générées** (marqueur de provenance) ou
    partout si ``strict``. Le reste est rapporté en information : ce sont les
    suites de validation de la bibliothèque, dont l'objet est justement de
    piloter SAP par ses ids bruts.
    """
    if targets:
        paths = [repo_root / t for t in targets]
    else:
        paths = [repo_root / "tests" / "robot", repo_root / "resources"]
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.robot")))
            files.extend(sorted(path.rglob("*.resource")))
        elif path.exists():
            files.append(path)
    tests_root = (repo_root / "tests" / "robot").resolve()
    blocking, informative = [], []
    total = 0
    for file in files:
        in_tests = tests_root in file.resolve().parents
        problems = scan_file(file, forbid_locators=in_tests)
        # Une suite non générée n'est pas tenue par la convention #1.
        lenient = in_tests and not strict and not is_generated_suite(file)
        for lineno, message, convention in problems:
            entry = "%s:%d : %s" % (
                file.relative_to(repo_root), lineno, message)
            if convention == 1 and lenient:
                informative.append(entry)
            else:
                blocking.append(entry)
        total += 1
    if blocking:
        print("[check_conventions] ÉCHEC :")
        for entry in blocking:
            print("  - %s" % entry)
    if informative:
        by_file: dict[str, int] = {}
        for entry in informative:
            by_file[entry.split(":")[0]] = by_file.get(
                entry.split(":")[0], 0) + 1
        print("  (info : convention #1 dans des suites NON générées, dont "
              "l'objet est de piloter SAP par ses ids bruts ; --strict pour "
              "les rendre bloquantes)")
        for name, count in sorted(by_file.items()):
            print("    · %s : %d" % (name, count))
    if blocking:
        return 1
    print("[check_conventions] OK : %d fichier(s), aucune violation bloquante."
          % total)
    return 0


def main(argv: list[str] | None = None) -> int:
    # Console Windows en cp1252 : le rapport contient des caractères hors page
    # de code : UTF-8 best-effort plutôt qu'un plantage à l'affichage.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("targets", nargs="*",
                        help="fichiers/répertoires à contrôler (défaut : "
                             "tests/robot/ et resources/)")
    parser.add_argument("--root", default=".",
                        help="racine du dépôt (défaut : répertoire courant)")
    parser.add_argument("--strict", action="store_true",
                        help="rend la convention #1 bloquante même dans les "
                             "suites non générées (validation de la lib)")
    args = parser.parse_args(argv)
    return check(Path(args.root).resolve(), args.targets or None,
                 strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
