"""Garde-fou de dérive de la base de communication (`comms/` ↔ `pyproject.toml`).

`comms/` affirme des choses au monde extérieur : une version, un nombre de tests,
une couverture. Ces chiffres vieillissent en silence — c'est exactement ce qui
s'est produit à la création du dossier, né en « v0.5.0 / 508 tests » alors que le
projet était déjà en 0.5.2 avec 617 tests. Une consigne (« pensez à mettre à
jour ») n'a rien empêché ; ce dépôt ne tourne pas aux intentions mais aux codes
de sortie, d'où ce script.

**Ce qu'il vérifie** :

1. **Le marqueur canonique** : `comms/positionnement.md` déclare la version de
   référence (``**Référence : vX.Y.Z.**``) et elle égale celle de
   `pyproject.toml`.
2. **Aucune citation contradictoire** : toute version ``vX.Y.Z`` écrite ailleurs
   dans `comms/` (les docs, mais aussi les sources du deck sous `comms/deck/`,
   d'où sortent les chips et le pied de page des slides) égale la même.
3. **Les preuves chiffrées** : `comms/proofs.json` porte le total de tests, la
    couverture et le ratio live ; `positionnement.md` et toute citation de tests
    dans `comms/` doivent les reprendre exactement.
4. Avec ``--verify-runtime``, le total est comparé à la collecte pytest réelle
    et la couverture à `coverage.xml`. Le ratio live reste une preuve datée et
    déclarative : son système cible et sa date sont obligatoires dans le manifeste.

Usage ::

    python scripts/check_comms_sync.py
    python scripts/check_comms_sync.py --verify-runtime --coverage-xml coverage.xml

Code de sortie non nul si une divergence est détectée (adapté à la CI).
"""
import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Une version du projet citée dans comms/ : « v0.5.2 ». Les versions d'autres
# produits (UI5 1.60 → 2.0, etc.) ne portent pas ce préfixe et ne matchent pas.
_VERSION_RE = re.compile(r"v(\d+\.\d+\.\d+)")

# Le marqueur canonique de la section « Les preuves ».
_ANCHOR_FILE = "comms/positionnement.md"
_ANCHOR_RE = re.compile(r"\*\*Référence : v(\d+\.\d+\.\d+)\.\*\*")
_PROOFS_FILE = "comms/proofs.json"
_TEST_COUNT_RE = re.compile(r"\b(\d+)\s+tests\b", re.IGNORECASE)
_LIVE_WORDING_RE = re.compile(r"\b(\d+)\s+scénarios\s+sur\s+(\d+)\b", re.IGNORECASE)
_LIVE_RATIO_RE = re.compile(
    r"\b(\d+)\s*/\s*(\d+)\b(?=[^\n]*(?:scénarios|scenarios))",
    re.IGNORECASE)

# Extensions scannées : les docs et les sources du deck (qui citent la version
# dans les chips et le pied de page des slides).
_SCANNED_SUFFIXES = (".md", ".py")


def project_version(root=_ROOT):
    """La version déclarée dans `pyproject.toml` — la source de vérité."""
    text = (Path(root) / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("version introuvable dans pyproject.toml")
    return match.group(1)


def _comms_files(root=_ROOT):
    comms = Path(root) / "comms"
    if not comms.is_dir():
        return []
    return sorted(p for p in comms.rglob("*")
                  if p.is_file() and p.suffix in _SCANNED_SUFFIXES)


def _load_proofs(root):
    path = Path(root) / _PROOFS_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    live = data["live_scenarios"]
    if not live.get("target") or not live.get("validated_on"):
        raise ValueError("live_scenarios requires target and validated_on")
    return data


def collect_pytest_tests(root=_ROOT):
    """Compte les tests par la collecte pytest réelle, sans scanner les sources."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=root, capture_output=True, text=True, check=False)
    output = result.stdout + "\n" + result.stderr
    match = re.search(r"(\d+) tests collected", output)
    if result.returncode != 0 or not match:
        raise RuntimeError("Could not obtain the pytest collection count")
    return int(match.group(1))


def read_coverage_percent(path):
    """Pourcentage entier publié, arrondi depuis le line-rate de coverage.xml."""
    line_rate = float(ET.parse(path).getroot().attrib["line-rate"])
    return int(line_rate * 100 + 0.5)


def check(root=_ROOT, verify_runtime=False, coverage_xml=None):
    """Retourne la liste des messages d'erreur (vide si tout est aligné)."""
    root = Path(root)
    problems = []
    version = project_version(root)

    try:
        proofs = _load_proofs(root)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        problems.append(f"{_PROOFS_FILE} invalide : {exc}.")
        proofs = None

    if proofs is not None and proofs.get("version") != version:
        problems.append(f"{_PROOFS_FILE} annonce la v{proofs.get('version')} alors que "
                        f"pyproject.toml est en {version}.")

    anchor_path = root / _ANCHOR_FILE
    if not anchor_path.exists():
        problems.append(f"{_ANCHOR_FILE} est introuvable : la base de communication "
                        f"doit déclarer sa version de référence.")
    else:
        anchor_text = anchor_path.read_text(encoding="utf-8")
        anchor = _ANCHOR_RE.search(anchor_text)
        if not anchor:
            problems.append(
                f"{_ANCHOR_FILE} ne déclare pas sa version de référence "
                f'(attendu : "**Référence : v{version}.**" dans la section « Les preuves »).')
        elif anchor.group(1) != version:
            problems.append(
                f"{_ANCHOR_FILE} annonce la v{anchor.group(1)} alors que pyproject.toml "
                f"est en {version} : relire la section « Les preuves » (version, nombre "
                f"de tests, couverture) puis régénérer le deck.")

        if proofs is not None:
            live = proofs["live_scenarios"]
            expected = (
                f'**{proofs["unit_tests"]}** tests unitaires',
                f'**{live["passed"]}/{live["total"]}** scénarios',
                f'**{proofs["coverage_percent"]} %** de couverture',
            )
            for marker in expected:
                if marker not in anchor_text:
                    problems.append(f"{_ANCHOR_FILE} ne contient pas la preuve {marker!r}.")

    for path in _comms_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for cited in sorted(set(_VERSION_RE.findall(text))):
            if cited != version:
                problems.append(f"{rel} cite la v{cited} alors que pyproject.toml "
                                f"est en {version}.")
        if proofs is not None:
            for cited in sorted(set(_TEST_COUNT_RE.findall(text))):
                if int(cited) != proofs["unit_tests"]:
                    problems.append(f"{rel} cite {cited} tests alors que "
                                    f"{_PROOFS_FILE} en déclare {proofs['unit_tests']}.")
            live_expected = (proofs["live_scenarios"]["passed"],
                             proofs["live_scenarios"]["total"])
            live_citations = _LIVE_RATIO_RE.findall(text) + _LIVE_WORDING_RE.findall(text)
            for passed, total in sorted(set(live_citations)):
                if (int(passed), int(total)) != live_expected:
                    problems.append(f"{rel} cite {passed}/{total} scénarios live alors que "
                                    f"{_PROOFS_FILE} déclare {live_expected[0]}/{live_expected[1]}.")

    if verify_runtime and proofs is not None:
        actual_tests = collect_pytest_tests(root)
        if actual_tests != proofs["unit_tests"]:
            problems.append(f"pytest collecte {actual_tests} tests, mais "
                            f"{_PROOFS_FILE} en déclare {proofs['unit_tests']}.")
        if coverage_xml is None:
            problems.append("--coverage-xml est requis avec --verify-runtime.")
        else:
            actual_coverage = read_coverage_percent(Path(root) / coverage_xml)
            if actual_coverage != proofs["coverage_percent"]:
                problems.append(f"coverage.xml mesure {actual_coverage} %, mais "
                                f"{_PROOFS_FILE} déclare {proofs['coverage_percent']} %.")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-runtime", action="store_true",
                        help="compare les preuves à pytest et coverage.xml")
    parser.add_argument("--coverage-xml", default=None,
                        help="chemin de coverage.xml, relatif à la racine du dépôt")
    args = parser.parse_args(argv)

    problems = check(verify_runtime=args.verify_runtime,
                     coverage_xml=args.coverage_xml)
    for problem in problems:
        print(f"[ERREUR] {problem}")
    if problems:
        print("\n[check_comms_sync] La base de communication a dérivé du code. "
              "Mettre à jour comms/positionnement.md § Les preuves, puis "
              "régénérer le deck (voir comms/deck.md).")
        return 1
    print("[check_comms_sync] OK -- comms/ aligné sur pyproject.toml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
