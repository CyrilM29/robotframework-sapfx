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
import sys

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


@pytest.mark.parametrize("library", [p[: -len(".html")] for p in _PAGES])
def test_spec_lists_every_keyword_the_library_exposes(library):
    """Le contenu suit le code, pas seulement le numéro de version.

    La garde de version ci-dessus ne mord qu'à un bump : entre deux releases,
    un keyword ajouté ou retiré laisse les pages publiées incomplètes sans que
    rien ne l'annonce. Constaté le 2026-08-22 : trois keywords manquaient et
    quatre signatures avaient changé (l'option ``per_resolution``) depuis la
    release précédente, toutes les gardes au vert.

    Le contrat vérifié ici est volontairement limité aux NOMS de keywords : ils
    sont la surface publique, ils ne dépendent pas de la langue, et ils se
    comparent sans rien exiger de la traduction anglaise des specs.
    """
    import json

    from robot.libdocpkg import LibraryDocumentation

    spec_path = os.path.join(_LIBDOC_DIR, "spec", f"{library}.json")
    assert os.path.isfile(spec_path), f"spec Libdoc manquante : {spec_path}"
    with open(spec_path, encoding="utf-8") as handle:
        documented = {kw["name"] for kw in json.load(handle)["keywords"]}
    exposed = {kw.name for kw in LibraryDocumentation(library).keywords}

    manquants = sorted(exposed - documented)
    en_trop = sorted(documented - exposed)
    assert not manquants and not en_trop, (
        f"comms/libdoc/spec/{library}.json ne suit plus la bibliothèque : "
        f"absents de la spec {manquants or 'aucun'}, disparus du code "
        f"{en_trop or 'aucun'}. Reporter le delta puis reconstruire les pages "
        "(procédure dans comms/libdoc/README.md).")


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="Python 3.10 applique encore l'Optional implicite de PEP 484 : "
           "get_type_hints y rend Optional[Any] pour un paramètre `Any = None` "
           "(mesuré 2026-08-30 : 3.10.21 rend Optional[Any], 3.11.16 rend Any). "
           "Les usages du type None gagnent donc les keywords à paramètre "
           "`Any = None` sur cette seule version, et AUCUNE spec committée ne "
           "peut satisfaire à la fois 3.10 et 3.11+. La spec est produite par un "
           "interpréteur moderne, la comparaison ne vaut que là ; les noms de "
           "keywords, eux, restent comparés sur toutes les versions.")
@pytest.mark.parametrize("library", [p[: -len(".html")] for p in _PAGES])
def test_spec_typedocs_follow_the_library(library):
    """Les **types documentés** suivent le code, eux aussi.

    L'angle mort que cette garde ferme, relevé le 2026-08-29 : la garde
    voisine compare les NOMS de keywords et rien d'autre, or une spec porte
    aussi des ``typedocs``, dont le champ ``usages`` liste les keywords qui
    emploient chaque type et alimente les liens croisés « used by » des pages
    publiées. Ajouter un keyword enrichit ces listes dans la bibliothèque sans
    rien changer aux noms déjà documentés : la garde des noms reste donc verte
    pendant que les pages publiées perdent des liens, et cela peut durer un
    cycle entier. Mesuré au moment de poser la garde : six types
    (``Any``, ``dictionary``, ``integer``, ``list``, ``None``, ``string``) ne
    listaient qu'un sous-ensemble de leurs keywords.

    Le contrat vérifié est volontairement STRUCTUREL (noms, catégorie de type,
    types acceptés, liste d'usages) et exclut le champ ``doc`` : celui des
    types standards est produit par Robot Framework, donc déjà en anglais et
    identique des deux côtés, mais un type propre au projet pourrait un jour
    porter une documentation française à traduire, et la garde n'a pas à
    interdire cette traduction.
    """
    import json

    from robot.libdocpkg import LibraryDocumentation

    spec_path = os.path.join(_LIBDOC_DIR, "spec", f"{library}.json")
    with open(spec_path, encoding="utf-8") as handle:
        publies = {t["name"]: t for t in json.load(handle).get("typedocs", [])}
    reels = {t.name: t for t in LibraryDocumentation(library).type_docs}

    manquants = sorted(set(reels) - set(publies))
    en_trop = sorted(set(publies) - set(reels))
    assert not manquants and not en_trop, (
        f"comms/libdoc/spec/{library}.json : types absents de la spec "
        f"{manquants or 'aucun'}, disparus du code {en_trop or 'aucun'}. "
        "Reprendre les typedocs de l'export frais puis reconstruire les pages "
        "(procédure dans comms/libdoc/README.md).")

    derives = []
    for nom in sorted(reels):
        attendu = {
            "type": reels[nom].type,
            "accepts": sorted(reels[nom].accepts),
            "usages": sorted(reels[nom].usages),
        }
        trouve = {
            "type": publies[nom].get("type"),
            "accepts": sorted(publies[nom].get("accepts", [])),
            "usages": sorted(publies[nom].get("usages", [])),
        }
        if attendu != trouve:
            oublies = sorted(set(attendu["usages"]) - set(trouve["usages"]))
            derives.append(
                f"{nom} (usages {len(trouve['usages'])} -> "
                f"{len(attendu['usages'])}"
                + (f", manquants {oublies[:5]}" if oublies else "") + ")")
    assert not derives, (
        f"comms/libdoc/spec/{library}.json : typedocs périmés, donc des liens "
        f"« used by » manquants sur la page publiée. {'; '.join(derives)}. "
        "Reprendre les typedocs de l'export frais puis reconstruire les pages "
        "(procédure dans comms/libdoc/README.md).")
