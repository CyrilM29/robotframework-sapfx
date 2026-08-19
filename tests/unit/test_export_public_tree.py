# -*- coding: utf-8 -*-
"""Tests hors-SAP des briques pures de l'export public
(``scripts/export_public_tree.py``, convention #5 du CLAUDE.md).

Le script est volontairement EXCLU de l'arbre public exporté (il énumère les
motifs interdits) : ce test, lui, est livré et se saute proprement quand le
script est absent. Aucun littéral sensible ici : tout est synthétique.
"""
import importlib.util
import os

import pytest

_SCRIPT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "export_public_tree.py"))

pytestmark = pytest.mark.skipif(
    not os.path.exists(_SCRIPT_PATH),
    reason="script d'export absent (arbre public exporté)")


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("export_public_tree", _SCRIPT_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------ apply_transform
def test_transform_litteral_applique(mod):
    out = mod.apply_transform("a lien b lien c", "lien", "URL", 2, False)
    assert out == "a URL b URL c"


def test_transform_compte_errone_echoue(mod):
    with pytest.raises(mod.ExportError, match="attendu 2x, trouvé 1x"):
        mod.apply_transform("a lien c", "lien", "URL", 2, False)


def test_transform_regex_multiligne(mod):
    text = "## Section privee\ncontenu\nsur deux lignes\n## Suite\n"
    out = mod.apply_transform(
        text, r"## Section privee\n.*?\n## Suite\n", "## Suite\n", 1, True)
    assert out == "## Suite\n"


def test_transform_regex_absente_echoue(mod):
    with pytest.raises(mod.ExportError):
        mod.apply_transform("rien ici", r"## Introuvable\n.*?fin", "", 1, True)


# ----------------------------------------------------------------- scan_bytes
def test_scan_detecte_motif_interdit(mod):
    forbidden = {b"secret-interne": set()}
    hits = mod.scan_bytes("docs/x.md", b"voir le Secret-INTERNE ici", forbidden)
    assert hits == [("docs/x.md", "secret-interne")]


def test_scan_respecte_la_tolerance_par_fichier(mod):
    forbidden = {b"secret-interne": {"docs/tolere.md"}}
    assert mod.scan_bytes("docs/tolere.md", b"secret-interne", forbidden) == []
    assert mod.scan_bytes("docs/autre.md", b"secret-interne", forbidden)


def test_scan_octets_binaires(mod):
    forbidden = {b"marqueur": set()}
    data = b"\x89PNG\x00\x01MARQUEUR\xff"
    assert mod.scan_bytes("assets/i.png", data, forbidden)


# ------------------------------------------------------------------ check_top
def test_check_top_refuse_l_inconnu(mod):
    with pytest.raises(mod.ExportError, match="nouveau-dossier"):
        mod.check_top({"src", "nouveau-dossier"}, expected={"src", "docs"})


def test_check_top_accepte_le_classe(mod):
    mod.check_top({"src", "docs"}, expected={"src", "docs"})  # ne lève pas


def test_check_top_refuse_une_disparition(mod):
    # Symétrie : un dossier sorti de HEAD produisait un arbre public amputé,
    # publié sans un mot, dans un script fail-closed partout ailleurs.
    with pytest.raises(mod.ExportError, match="docs"):
        mod.check_top({"src"}, expected={"src", "docs"})


def test_le_perimetre_attendu_correspond_au_depot_reel(mod):
    """EXPECTED_TOP décrit le VRAI premier niveau : ni entrée fantôme, ni
    dossier non classé (les deux feraient échouer l'export le jour de la
    release, le pire moment pour le découvrir)."""
    import subprocess
    head = set(subprocess.run(
        ["git", "ls-tree", "--name-only", "HEAD"], cwd=str(mod.SRC),
        capture_output=True, text=True, encoding="utf-8", check=True).stdout.split())
    assert head == mod.EXPECTED_TOP


# ---------------------------------------------------------------- pypi_readme
def _readme(mod, banner=True, logo=True, alt=True, links=True):
    """README minimal : banner EN/FR + le bloc médaillon que la variante PyPI
    réécrit, plus un lien relatif de dépôt (absolutisé pour PyPI)."""
    src = mod._PYPI_LOGO[0] if logo else "ailleurs.png"
    attr = mod._PYPI_LOGO_ALT[0] if alt else 'alt="autre chose"'
    body = "corps [archi](docs/architecture.md) fin\n" if links else "corps\n"
    return ((mod._PYPI_BANNER if banner else "")
            + f'<p align="center">\n  <img src="{src}" {attr} width="240">\n</p>\n\n'
            + "# Titre\n\n" + body)


def test_pypi_readme_retire_le_banner(mod):
    assert mod._PYPI_BANNER not in mod.pypi_readme(_readme(mod))


def test_pypi_readme_bascule_le_medaillon_sur_la_variante_library(mod):
    out = mod.pypi_readme(_readme(mod))
    assert mod._PYPI_LOGO[1] in out and mod._PYPI_LOGO[0] not in out
    assert mod._PYPI_LOGO_ALT[1] in out and mod._PYPI_LOGO_ALT[0] not in out


def test_pypi_readme_banner_absent_echoue(mod):
    with pytest.raises(mod.ExportError, match="banner"):
        mod.pypi_readme(_readme(mod, banner=False))


@pytest.mark.parametrize("absent", ["logo", "alt"])
def test_pypi_readme_medaillon_absent_echoue(mod, absent):
    with pytest.raises(mod.ExportError, match="médaillon"):
        mod.pypi_readme(_readme(mod, **{absent: False}))


def test_pypi_readme_absolutise_les_liens_de_depot(mod):
    """Sur PyPI, un lien relatif vers docs/ ne mène nulle part (constaté en
    0.6.5) : la variante PyPI les rend absolus, le README du dépôt garde ses
    liens relatifs (forme correcte sur GitHub)."""
    out = mod.pypi_readme(_readme(mod))
    assert "](docs/architecture.md)" not in out
    assert f"]({mod._BLOB}/docs/architecture.md)" in out


@pytest.mark.parametrize("text,expected", [
    ("[a](docs/x.md) [b](./CHANGELOG.md)", 2),   # relatifs, avec ou sans ./
    ("[a](https://ex.com/x.md) [b](#ancre) [c](mailto:a@b.md)", 0),
    ("![img](assets/logo.png)", 0),              # non-.md : hors périmètre
])
def test_absolutize_repo_links_perimetre(mod, text, expected):
    out, count = mod.absolutize_repo_links(text)
    assert count == expected
    assert out.count(mod._BLOB) == expected


def test_pypi_readme_sans_aucun_lien_echoue(mod):
    """Fail-closed : plus aucun lien relatif = motif changé, on refuse plutôt
    que de publier une page silencieusement appauvrie."""
    with pytest.raises(mod.ExportError, match="lien relatif"):
        mod.pypi_readme(_readme(mod, links=False))


def test_le_vrai_readme_porte_le_medaillon_attendu(mod):
    """Le README réel reste réécrivable : une retouche du bandeau casse ici, pas au build."""
    readme = os.path.join(os.path.dirname(_SCRIPT_PATH), "..", "README.md")
    text = open(readme, encoding="utf-8").read()
    assert mod._PYPI_LOGO[0] in text
    assert mod._PYPI_LOGO_ALT[0] in text


# ------------------------------------------------- cohérence du périmètre
def test_le_script_est_auto_exclu(mod):
    assert "scripts/export_public_tree.py" in mod.EXCLUDE_PREFIXES


def test_les_transformations_visent_des_fichiers_publies(mod):
    exclus = tuple(p.rstrip("/") for p in mod.EXCLUDE_PREFIXES)
    for rel, *_ in mod.TRANSFORMS:
        assert not rel.startswith(exclus), rel


def test_les_copies_sortent_du_perimetre_exclu(mod):
    """Une copie n'a de sens que d'un dossier EXCLU vers un dossier PUBLIÉ."""
    exclus = tuple(p.rstrip("/") for p in mod.EXCLUDE_PREFIXES)
    for src, dst in mod.EXTRA_COPIES.items():
        assert src.startswith(exclus), f"{src} est déjà publié : copie inutile"
        assert not dst.startswith(exclus), f"{dst} retombe dans une exclusion"


def test_les_pages_libdoc_et_leurs_images_sont_copiees(mod):
    """Les pages de documentation des keywords sont un livrable UTILISATEUR :
    produites dans le studio, elles doivent atterrir dans l'arbre public (les
    specs JSON, matière de travail, restent privées)."""
    copies = mod.EXTRA_COPIES
    for page in ("index.html", "SapEccLibrary.html", "SapFioriLibrary.html",
                 "SapApiLibrary.html", "logo-library.png", "picto_light.png"):
        src = f"comms/libdoc/{page}"
        assert copies.get(src) == f"docs/libdoc/{page}", (
            f"{src} absent des copies publiques (page Libdoc non publiée ?)")
    assert not any(s.startswith("comms/libdoc/spec/") for s in copies)


def test_les_images_libdoc_gardent_une_exception_gitignore(mod):
    """`*.png` est ignoré globalement : sans exception RÉÉCRITE vers la
    destination publique, les images des pages publiées seraient absentes du
    dépôt public (le filtre GITIGNORE_DROP retire les lignes citant comms)."""
    rewrite = [t for t in mod.TRANSFORMS if t[0] == ".gitignore"]
    assert rewrite, "aucune réécriture .gitignore : les PNG des pages seraient ignorés"
    replacement = "".join(t[2] for t in rewrite)
    for png in ("logo-library.png", "picto_light.png"):
        assert f"!docs/libdoc/{png}" in replacement
        assert mod.GITIGNORE_DROP_SUBSTRING not in f"!docs/libdoc/{png}"
