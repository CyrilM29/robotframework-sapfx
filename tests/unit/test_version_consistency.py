"""Garde de cohérence des versions de la distribution (convention #5 appliquée
à la release elle-même). Dérive détectée en préparant la 0.3.0 : les entrées
CHANGELOG 0.2.0 et 0.2.5 annonçaient des bumps de ``__version__`` jamais
appliqués : ``SapEccLibrary`` et ``sapfx_common`` étaient restés à 0.1.0,
``SapFioriLibrary`` était parti seul à 0.3.0. Ce module verrouille : les deux
``pyproject.toml`` (distributions) et les trois ``__version__`` des paquets
portent LA MÊME version, et le CHANGELOG a une section datée pour elle."""
import importlib.util
import os
import re

import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_BUILDER = os.path.join(_ROOT, "scripts", "build_release_pack.py")

_PYPROJECTS = [
    "pyproject.toml",
    os.path.join("integrations", "robotmcp", "pyproject.toml"),
]
_PACKAGE_INITS = [
    os.path.join("src", "SapEccLibrary", "__init__.py"),
    os.path.join("src", "SapFioriLibrary", "__init__.py"),
    os.path.join("src", "SapApiLibrary", "__init__.py"),
    os.path.join("src", "sapfx_common", "__init__.py"),
    # attributs de CLASSE (version affichée par Robot pour la lib) : SapEccLibrary
    # resté à 0.2.5 pendant la 0.3.0, puis SapFioriLibrary resté à 0.2.5 pendant
    # la 0.4.0, car le garde ne couvrait que les __init__ : TOUTES les classes de
    # bibliothèque sont désormais suivies (la regex tolère l'indentation).
    os.path.join("src", "SapEccLibrary", "SapEccLibrary.py"),
    os.path.join("src", "SapFioriLibrary", "SapFioriLibrary.py"),
    os.path.join("src", "SapApiLibrary", "SapApiLibrary.py"),
]


def _read(rel_path):
    with open(os.path.join(_ROOT, rel_path), encoding="utf-8") as handle:
        return handle.read()


def _builder_read_version():
    # Réutilise le parseur du builder (source unique du numéro embarqué dans le
    # nom du pack) plutôt qu'une regex parallèle qui pourrait diverger.
    spec = importlib.util.spec_from_file_location("build_release_pack", _BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_version


def _collect_versions():
    read_version = _builder_read_version()
    versions = {rel: read_version(_read(rel)) for rel in _PYPROJECTS}
    for rel in _PACKAGE_INITS:
        match = re.search(r'^\s*__version__\s*=\s*"([^"]+)"', _read(rel), re.MULTILINE)
        assert match, f"pas de __version__ dans {rel}"
        versions[rel] = match.group(1)
    return versions


def test_distributions_and_packages_share_one_version():
    versions = _collect_versions()
    distinct = sorted(set(versions.values()))
    assert len(distinct) == 1, (
        "versions divergentes (bump incomplet, voir CHANGELOG 0.3.0 Fixed) : "
        + ", ".join(f"{rel}={v}" for rel, v in sorted(versions.items())))


def test_changelog_has_a_dated_section_for_the_current_version():
    version = next(iter(_collect_versions().values()))
    changelog = _read("CHANGELOG.md")
    # Forme Keep a Changelog (tiret ASCII) : celle qu'attendent les parseurs de
    # changelog, et la seule admise depuis que le cadratin est banni de la prose
    # publiée (règle du 2026-08-04, section Language de CLAUDE.md).
    assert re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$",
                     changelog, re.MULTILINE), (
        f"CHANGELOG.md n'a pas de section datée '## [{version}] - AAAA-MM-JJ' "
        "pour la version courante : release notes oubliées ?")


@pytest.mark.parametrize("rel", _PYPROJECTS + _PACKAGE_INITS)
def test_every_tracked_version_file_still_exists(rel):
    # Un fichier déplacé rendrait le garde silencieusement partiel : échouer fort.
    assert os.path.isfile(os.path.join(_ROOT, rel)), f"fichier suivi manquant : {rel}"
