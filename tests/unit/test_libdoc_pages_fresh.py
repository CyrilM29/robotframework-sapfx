"""Garde de fraîcheur des pages Libdoc publiées (comms/libdoc).

Les pages de documentation des keywords (le pendant SAPFX de la page
SapGuiLibrary.html du projet amont) sont committées dans ``comms/libdoc`` puis
publiées sur GitHub Pages. Une page générée embarque la version de la
bibliothèque au moment de la génération : si elle ne suit pas un bump de
version, la documentation publiée ment sur le produit (la même famille de
dérive que celle couverte par ``check_published_versions.py`` pour la prose).
Ce garde échoue donc à chaque release tant que les pages n'ont pas été
régénérées : la procédure est dans ``comms/libdoc/README.md``.

``index.html`` (page d'accueil rédigée à la main) est volontairement sans
numéro de version : le garde vérifie seulement qu'elle relie bien les trois
pages générées.

Second contrat, depuis que ces pages sont AUSSI livrées dans l'arbre public
(``docs/libdoc``, copiées par ``scripts/export_public_tree.py``) : elles ne
doivent porter aucun chemin de poste. Libdoc grave le chemin ABSOLU du fichier
source dans chaque champ ``source`` (la bibliothèque et chaque keyword) : il se
relativise dans la spec avant reconstruction, sinon l'export public s'arrête
sur son scan anti-fuite, au pire moment (le jour de la release).
"""
import importlib.util
import os
import re

import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LIBDOC_DIR = os.path.join(_ROOT, "comms", "libdoc")
_PAGES = ["SapEccLibrary.html", "SapFioriLibrary.html", "SapApiLibrary.html"]

# Les pages sont régénérées dans le studio (dépôt privé) ; l'arbre public en
# reçoit une COPIE sous ``docs/libdoc`` mais pas le dossier ``comms/``. Ce test
# est livré comme les autres et se saute alors proprement, comme le fait
# ``test_export_public_tree`` quand son script est absent.
pytestmark = pytest.mark.skipif(
    not os.path.isdir(_LIBDOC_DIR),
    reason="source des pages Libdoc absente (arbre public exporté)")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _project_version():
    # Même source unique que test_version_consistency : le parseur du builder.
    spec = importlib.util.spec_from_file_location(
        "build_release_pack", os.path.join(_ROOT, "scripts", "build_release_pack.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_version(_read(os.path.join(_ROOT, "pyproject.toml")))


@pytest.mark.parametrize("page", _PAGES)
def test_generated_page_matches_project_version(page):
    path = os.path.join(_LIBDOC_DIR, page)
    assert os.path.isfile(path), (
        f"page Libdoc manquante : comms/libdoc/{page} "
        "(régénération : comms/libdoc/README.md)")
    match = re.search(r'"version":\s*"([^"]+)"', _read(path))
    assert match, f"comms/libdoc/{page} sans champ version : sortie Libdoc inattendue"
    assert match.group(1) == _project_version(), (
        f"comms/libdoc/{page} générée pour la version {match.group(1)} alors que le "
        f"projet est en {_project_version()} : régénérer les pages Libdoc puis "
        "republier GitHub Pages (procédure dans comms/libdoc/README.md)")


def test_index_links_every_generated_page():
    index = _read(os.path.join(_LIBDOC_DIR, "index.html"))
    for page in _PAGES:
        assert f'href="{page}"' in index, (
            f"index.html ne relie pas {page} : page d'accueil incomplète")


# ------------------------------------------------- pages publiables (docs/libdoc)
#: Un chemin de poste : lettre de lecteur suivie d'un séparateur, sous ses deux
#: formes (``C:\\…`` brut ou ``C:\\\\…`` échappé dans le JSON embarqué). Le
#: lookbehind écarte les schémas d'URL, où la même forme apparaît (``http://``).
_MACHINE_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")

#: Ce que l'export public copie dans ``docs/libdoc`` : les pages, pas les specs.
_PUBLISHED = _PAGES + ["index.html"]


@pytest.mark.parametrize("name", _PUBLISHED + [os.path.join("spec", p.replace(".html", ".json"))
                                               for p in _PAGES])
def test_no_machine_path_in_libdoc_files(name):
    """Aucun chemin de poste dans les pages ni dans les specs qui les fabriquent.

    Libdoc grave un ``source`` ABSOLU : après régénération, relativiser les
    chemins dans ``spec/*.json`` (``src/…``) AVANT de reconstruire les pages,
    procédure dans comms/libdoc/README.md.
    """
    text = _read(os.path.join(_LIBDOC_DIR, name))
    found = _MACHINE_PATH.search(text)
    assert not found, (
        f"comms/libdoc/{name} porte un chemin de poste ({found.group(0)}…) : "
        "relativiser les champs `source` de spec/*.json puis reconstruire les "
        "pages (comms/libdoc/README.md). L'export public refuserait l'arbre.")


@pytest.mark.parametrize("page", _PAGES)
def test_generated_page_keeps_repo_relative_sources(page):
    """Le champ ``source`` reste renseigné, mais relatif à la racine du dépôt."""
    sources = set(re.findall(r'"source":\s*"([^"]*)"', _read(
        os.path.join(_LIBDOC_DIR, page))))
    assert sources, f"comms/libdoc/{page} sans champ source : sortie Libdoc inattendue"
    assert all(s.startswith("src/") for s in sources), (
        f"comms/libdoc/{page} : sources attendues relatives à la racine "
        f"(`src/…`), trouvé {sorted(sources)[:3]}")
