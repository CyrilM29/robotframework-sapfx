"""Construit le pack de déploiement Windows (bibliothèques + recorders + plugins MCP).

Produit dans ``dist/`` un dossier de staging puis un zip autonome
``sapfx-pack-<version>-win.zip`` déployable sur un PC Windows sans cloner le dépôt :

- ``wheels/`` : le wheel des bibliothèques (`robotframework-sapfx`, qui
  contient `SapEccLibrary`, `SapFioriLibrary`, `SapApiLibrary` et `sapfx_common`)
  et le wheel des plugins rf-mcp (`sap-robotmcp`), construits par
  ``pip wheel --no-deps`` ;
- les recorders (``tools/recorder``, ``tools/recorder_web`` + extension MV3),
    les keywords métier (``resources/``), six suites d'exemple (smokes,
  exploration autonome, sentinelle de dérive, flagship écran↔API) ;
- les scripts de maintenance (``scripts/`` : bot télémétrie→patch
  ``healing_drift_report.py``, garde spec↔suite ``check_spec_sync.py``, tous
  deux stdlib pure, exécutables depuis la racine du pack) ;
- les agents de test (``.claude/agents`` + ``.claude/commands`` pour Claude Code,
  ``.github/chatmodes`` généré pour VS Code/Copilot) et ``specs/`` (contrat +
  plan d'exemple), le cycle plan → génération → réparation de docs/test-agents.md ;
- l'installateur (``install.cmd``/``install.ps1``), les gabarits MCP (Claude Code
  et VS Code) et les READMEs du pack, tous maintenus dans ``packaging/`` (le pack
  lui-même est un artefact, jamais édité à la main : voir packaging/README.fr.md).

C'est un assembleur, pas un générateur de contenu : chaque fichier du pack existe
tel quel dans le dépôt (ou sort du build backend standard) ; le script se limite à
la sélection, la copie et le zip, d'où une logique pure testable hors ligne
(``tests/unit/test_build_release_pack.py``, convention #5 du CLAUDE.md).

Usage ::

    python scripts/build_release_pack.py                # dist/sapfx-pack-<v>-win.zip
    python scripts/build_release_pack.py --outdir chemin  # autre dossier de sortie
    python scripts/build_release_pack.py --skip-wheels    # ré-assemblage seul
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Dossiers jamais embarqués, où qu'ils apparaissent (artefacts locaux/dev).
EXCLUDED_DIR_NAMES = {"__pycache__", "captures", "dist", "store", ".pytest_cache"}
# Fichiers jamais embarqués (suffixe).
EXCLUDED_FILE_SUFFIXES = (".pyc", ".pyo")

# Arborescences copiées récursivement (relatif dépôt -> relatif pack).
# Les définitions d'agents de test (planner/generator/healer) partent telles
# quelles : .claude/ est lu par Claude Code, .github/chatmodes/ par VS Code /
# Copilot (cibles GÉNÉRÉES depuis .claude/agents/ : regen_agent_definitions.py).
PACK_TREES = [
    ("resources", "resources"),
    ("tools/recorder", "tools/recorder"),
    ("tools/recorder_web", "tools/recorder_web"),
    (".claude/agents", ".claude/agents"),
    (".claude/commands", ".claude/commands"),
    # Skill « boîte à outils » (esprit install-as-a-skill de Vibium) : un agent
    # Claude Code qui la charge apprend l'outillage SAPFX en un appel.
    (".claude/skills", ".claude/skills"),
    (".github/chatmodes", ".github/chatmodes"),
]

# Fichiers copiés un à un (relatif dépôt -> relatif pack). Les fichiers de
# packaging/ atterrissent à la racine du pack ; recorder.cmd vient de packaging/
# (variante venv-first), pas de la racine du dépôt (variante PATH).
PACK_FILES = [
    ("LICENSE", "LICENSE"),
    ("NOTICE", "NOTICE"),
    ("tests/robot/ecc_smoke.robot", "tests/robot/ecc_smoke.robot"),
    ("tests/robot/fiori_smoke.robot", "tests/robot/fiori_smoke.robot"),
    # Smoke Browser déterministe et hors ligne : qualifie le wheel installé,
    # Chromium, le moteur Web Components et le recorder sans dépendre d'un CDN.
    ("tests/robot/fiori_wc_smoke.robot", "tests/robot/fiori_wc_smoke.robot"),
    ("tests/robot/fixtures/wc_fixture.html",
     "tests/robot/fixtures/wc_fixture.html"),
    # Suite d'exploration AUTONOME (aucune dépendance à resources/) : l'exemple
    # « données réelles » du pack : inventaire dynamique + vérification SE16.
    ("tests/robot/business_data_exploration.robot",
     "tests/robot/business_data_exploration.robot"),
    # Sentinelle de dérive : surveillance d'écrans sans tests scriptés (les
    # références screen_watch/ se créent au premier passage sur le PC cible).
    ("tests/robot/ecc_drift_sentinel.robot",
     "tests/robot/ecc_drift_sentinel.robot"),
    # Flagship cross-paradigme : le même fait métier vérifié par l'écran ET
    # l'API (SapApiLibrary, embarquée dans le wheel des bibliothèques).
    ("tests/robot/flagship_cross_paradigm.robot",
     "tests/robot/flagship_cross_paradigm.robot"),
    # Outillage de maintenance, stdlib pure, exécutable depuis la racine du
    # pack : bot télémétrie de healing -> patch resources/ proposé, et garde
    # spec <-> suite générée (source de vérité) pour les suites des agents.
    ("scripts/healing_drift_report.py", "scripts/healing_drift_report.py"),
    ("scripts/check_spec_sync.py", "scripts/check_spec_sync.py"),
    ("packaging/README.md", "README.md"),
    ("packaging/README.fr.md", "README.fr.md"),
    ("packaging/install.ps1", "install.ps1"),
    ("packaging/install.cmd", "install.cmd"),
    ("packaging/recorder.cmd", "recorder.cmd"),
    ("packaging/mcp.json.template", "mcp.json.template"),
    ("packaging/vscode-mcp.json.template", "vscode-mcp.json.template"),
    ("packaging/requirements-deploy.txt", "requirements-deploy.txt"),
    ("packaging/constraints-deploy.txt", "constraints-deploy.txt"),
    # Plans de test des agents : le contrat du répertoire + l'exemple de
    # référence seulement ; les plans locaux de l'équipe restent dans le dépôt.
    ("specs/README.md", "specs/README.md"),
    ("specs/sflight-consultation-se16.md", "specs/sflight-consultation-se16.md"),
]

# Projets dont on construit un wheel (chemin relatif dépôt).
WHEEL_PROJECTS = [".", "integrations/robotmcp"]


def read_version(pyproject_text):
    """Extrait ``version = "..."`` de la section [project] d'un pyproject.toml.

    Regex volontairement (pas tomllib) : compatible avec le plancher
    requires-python du dépôt et suffisant pour un champ que nous contrôlons.
    """
    in_project = False
    for line in pyproject_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_project = stripped == "[project]"
            continue
        if in_project:
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    raise ValueError("version introuvable dans la section [project] du pyproject.toml")


def is_excluded(rel_path):
    """Vrai si ce chemin relatif (POSIX ou natif) ne doit pas entrer dans le pack."""
    parts = Path(rel_path).parts
    if any(part in EXCLUDED_DIR_NAMES for part in parts):
        return True
    return parts[-1].endswith(EXCLUDED_FILE_SUFFIXES) if parts else False


def build_manifest(root):
    """Liste des couples (source absolue, destination relative pack), triée.

    Lève FileNotFoundError si un fichier/arbre attendu manque : un pack silencieusement
    incomplet est pire qu'un build qui échoue.
    """
    entries = []
    for src_rel, dest_rel in PACK_FILES:
        src = Path(root) / src_rel
        if not src.is_file():
            raise FileNotFoundError(f"fichier attendu manquant : {src_rel}")
        entries.append((src, Path(dest_rel)))
    for tree_rel, dest_rel in PACK_TREES:
        tree = Path(root) / tree_rel
        if not tree.is_dir():
            raise FileNotFoundError(f"arborescence attendue manquante : {tree_rel}")
        for src in sorted(tree.rglob("*")):
            if not src.is_file():
                continue
            rel_in_tree = src.relative_to(tree)
            if is_excluded(rel_in_tree):
                continue
            entries.append((src, Path(dest_rel) / rel_in_tree))
    return sorted(entries, key=lambda pair: pair[1].as_posix())


def pack_name(version):
    return f"sapfx-pack-{version}-win"


def build_wheels(root, wheels_dir):
    """Construit les wheels des projets du dépôt via ``pip wheel --no-deps``."""
    wheels_dir.mkdir(parents=True, exist_ok=True)
    for project_rel in WHEEL_PROJECTS:
        project = Path(root) / project_rel
        print(f"-- pip wheel {project_rel}")
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps",
             "-w", str(wheels_dir), str(project)],
            check=True,
        )


def normalize_crlf(data):
    """Force les fins de ligne CRLF (idempotent : CRLF existants préservés)."""
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def assemble(root, stage_dir):
    """Copie le manifeste vers le dossier de staging (sans toucher wheels/).

    Les lanceurs batch (``.cmd``) sont normalisés en CRLF : cmd.exe exige des
    fins de ligne Windows (un ``install.cmd`` en LF pur crache des
    « 'M' n'est pas reconnu… » au double-clic, vécu sur le pack 0.6.2), et le
    checkout git du dépôt est en LF (``.gitattributes``).
    """
    for src, dest_rel in build_manifest(root):
        dest = stage_dir / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if dest.suffix.lower() == ".cmd":
            dest.write_bytes(normalize_crlf(dest.read_bytes()))


def write_zip(stage_dir, zip_path):
    """Zippe le staging ; les chemins internes sont préfixés par le nom du pack."""
    prefix = stage_dir.name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage_dir.rglob("*")):
            if path.is_file():
                archive.write(path, f"{prefix}/{path.relative_to(stage_dir).as_posix()}")


def file_sha256(path):
    """SHA-256 d'un fichier, lu par blocs pour borner la mémoire."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_stage_checksums(stage_dir):
    """Écrit le SHA-256 de chaque fichier livré, chemins relatifs triés."""
    stage_dir = Path(stage_dir)
    output = stage_dir / "SHA256SUMS.txt"
    lines = []
    for path in sorted(stage_dir.rglob("*")):
        if path.is_file() and path != output:
            lines.append("%s  %s" % (
                file_sha256(path), path.relative_to(stage_dir).as_posix()))
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    return output


def write_checksum_file(path):
    """Écrit ``<fichier>.sha256`` au format compatible sha256sum."""
    path = Path(path)
    output = path.with_suffix(path.suffix + ".sha256")
    output.write_text("%s  %s\n" % (file_sha256(path), path.name), encoding="ascii")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outdir", default=str(_ROOT / "dist"),
                        help="dossier de sortie (défaut : dist/)")
    parser.add_argument("--skip-wheels", action="store_true",
                        help="ne pas reconstruire les wheels (réutilise wheels/ du staging)")
    args = parser.parse_args(argv)

    version = read_version((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    outdir = Path(args.outdir)
    stage_dir = outdir / pack_name(version)
    wheels_dir = stage_dir / "wheels"

    # Repartir d'un staging propre, en préservant wheels/ si --skip-wheels.
    if stage_dir.exists():
        for child in stage_dir.iterdir():
            if args.skip_wheels and child == wheels_dir:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    stage_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_wheels:
        if wheels_dir.exists():
            shutil.rmtree(wheels_dir)
        build_wheels(_ROOT, wheels_dir)
    wheel_count = len(list(wheels_dir.glob("*.whl"))) if wheels_dir.is_dir() else 0
    if wheel_count < len(WHEEL_PROJECTS):
        print(f"ERREUR : {wheel_count} wheel(s) dans {wheels_dir}, "
              f"{len(WHEEL_PROJECTS)} attendus.", file=sys.stderr)
        return 1

    assemble(_ROOT, stage_dir)
    write_stage_checksums(stage_dir)
    zip_path = outdir / f"{pack_name(version)}.zip"
    write_zip(stage_dir, zip_path)
    checksum_path = write_checksum_file(zip_path)
    print(f"\nPack prêt : {zip_path}")
    print(f"SHA-256    : {checksum_path}")
    print(f"Staging   : {stage_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
