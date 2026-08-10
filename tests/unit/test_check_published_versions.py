"""Tests hors-SAP du garde des versions publiées
(``scripts/check_published_versions.py``, convention #5 appliquée à un script
d'outillage).

Le cas de régression qui compte est ``test_badge_statique_refuse`` : c'est la
demande née de la release 0.6.6, où le badge PyPI semblait périmé (en fait du
cache) et où la parade instinctive, graver la version dans l'URL, aurait créé
une dette invisible. Les autres tests couvrent l'autre moitié : les artefacts
qu'un lecteur va chercher ou taper (pack, wheels, épinglage pip)."""
import importlib.util
import os

import pytest

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts",
    "check_published_versions.py"))


def _load():
    spec = importlib.util.spec_from_file_location("check_published_versions",
                                                  _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def _repo(tmp_path, readme="# SAPFX\n", docs=None, packaging=None,
          version="0.6.6"):
    """Faux dépôt minimal : un pyproject, un README, et de quoi peupler
    docs/ et packaging/ (les deux autres répertoires balayés)."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "%s"\n' % version, encoding="utf-8")
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    for folder, files in (("docs", docs), ("packaging", packaging)):
        if not files:
            continue
        target = tmp_path / folder
        target.mkdir(exist_ok=True)
        for name, text in files.items():
            (target / name).write_text(text, encoding="utf-8")
    return str(tmp_path)


# --- le cas fondateur : badge de version gravé -------------------------------

def test_badge_statique_refuse(tmp_path):
    root = _repo(tmp_path, readme=(
        "[![PyPI](https://img.shields.io/badge/pypi-v0.6.6-blue)]"
        "(https://pypi.org/project/robotframework-sapfx/)\n"))
    problems = mod.check(root)
    # Refusé MÊME quand la version gravée est la bonne : elle sera fausse à la
    # release suivante, et rien d'autre ne l'attraperait.
    assert len(problems) == 1
    assert "STATIQUE" in problems[0]
    assert "shields.io/pypi/v/" in problems[0]
    assert "cache" in problems[0]


def test_badge_dynamique_accepte(tmp_path):
    root = _repo(tmp_path, readme=(
        "[![PyPI](https://img.shields.io/pypi/v/robotframework-sapfx)]"
        "(https://pypi.org/project/robotframework-sapfx/)\n"))
    assert mod.check(root) == []


# --- artefacts qu'un lecteur va chercher ou taper ----------------------------

@pytest.mark.parametrize("citation,attendu", [
    ("Télécharger `sapfx-pack-0.6.5-win.zip`", "nom du pack"),
    ("pip install robotframework-sapfx==0.6.5", "épinglage pip"),
    ("wheels/robotframework_sapfx-0.6.5-py3-none-any.whl", "wheel des bibliothèques"),
    ("wheels/sap_robotmcp-0.6.5-py3-none-any.whl", "wheel du plugin rf-mcp"),
])
def test_version_perimee_dans_une_instruction_echoue(tmp_path, citation, attendu):
    root = _repo(tmp_path, docs={"deployment-pack.md": citation + "\n"})
    problems = mod.check(root)
    assert len(problems) == 1, problems
    assert attendu in problems[0]
    assert "0.6.5" in problems[0] and "0.6.6" in problems[0]
    assert "docs/deployment-pack.md:1" in problems[0]


@pytest.mark.parametrize("citation", [
    "Télécharger `sapfx-pack-0.6.6-win.zip`",
    "pip install robotframework-sapfx==0.6.6",
    "wheels/robotframework_sapfx-0.6.6-py3-none-any.whl",
])
def test_version_courante_acceptee(tmp_path, citation):
    root = _repo(tmp_path, docs={"deployment-pack.md": citation + "\n"})
    assert mod.check(root) == []


def test_post_release_reconnue(tmp_path):
    """Une page PyPI corrigée après coup se publie en post-release
    (précédent 0.6.4.post1) : la forme doit être acceptée telle quelle."""
    root = _repo(tmp_path, version="0.6.4.post1",
                 docs={"x.md": "pip install robotframework-sapfx==0.6.4.post1\n"})
    assert mod.check(root) == []


# --- ce que le garde NE doit PAS attraper ------------------------------------

@pytest.mark.parametrize("ligne", [
    "vérifié contre rf-mcp **0.31.2** et re-validé",     # version tierce
    "fastmcp (3.4.2 ici), dont les outils",               # version tierce
    "| Docker | **27.5.1 ✓** |",                          # version tierce
    "compatibilité UI5 1.60 → 2.0",                       # version tierce
    "`__version__ = '1.2'` contre le tag `1.2.1`",        # upstream audité
    "127.0.0.1   vhcala4hci",                             # même pas une version
])
def test_versions_tierces_ignorees(tmp_path, ligne):
    """Un garde qui crie au loup finit désactivé : les versions des AUTRES
    n'ont aucune raison de suivre la nôtre."""
    root = _repo(tmp_path, docs={"mcp-integration.md": ligne + "\n"})
    assert mod.check(root) == []


def test_fichiers_d_histoire_hors_perimetre(tmp_path):
    """CHANGELOG, CLAUDE.md, memory/, specs/ et le heal-journal PARLENT
    d'anciennes versions : c'est leur propos, pas une dérive."""
    root = _repo(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "Pack reconstruit : `sapfx-pack-0.5.2-win.zip`.\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text(
        "Pack : `dist/sapfx-pack-0.5.8-win.zip`.\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "heal-journal.md").write_text(
        "validation de la version 0.6.2, sapfx-pack-0.6.2-win.zip\n",
        encoding="utf-8")
    assert mod.check(root) == []
    assert "docs/heal-journal.md" not in mod.scanned_files(root)


# --- surface du garde --------------------------------------------------------

def test_le_depot_reel_est_conforme():
    """Le garde tourne vert sur l'arbre réel : il documente un état tenu, pas
    un vœu (et il balaie vraiment quelque chose)."""
    assert mod.check() == []
    assert len(mod.scanned_files()) > 20


def test_version_lue_dans_pyproject():
    assert mod.current_version() == mod.current_version(mod._ROOT)
    assert mod.current_version().count(".") >= 2


def test_allowed_est_vide_par_defaut():
    """Chaque exception futée devra porter sa justification : on part de zéro."""
    assert mod.ALLOWED == frozenset()
