"""Tests hors-SAP du garde-fou de dérive vendor (``scripts/check_vendor_drift.py``
: convention #5 du CLAUDE.md, appliquée à un script d'outillage)."""
import importlib.util
import os

_SCRIPT_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "check_vendor_drift.py"))


def _load():
    spec = importlib.util.spec_from_file_location("check_vendor_drift", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()

_UPSTREAM_BODY = (
    "import pythoncom\n"
    "\n"
    "class SapGuiLibrary:\n"
    '    """The SapGuiLibrary is a library that enables users to create tests."""\n'
    "\n"
    "    __version__ = '1.2'\n"
    "    def foo(self):\n"
    "        pass\n"
)

_VENDOR_HEADER = (
    "# -----------------------------------------------------------------\n"
    "# VENDORED CODE: DO NOT EDIT EXCEPT FOR UPSTREAM SYNC\n"
    "# -----------------------------------------------------------------\n"
)

_VENDOR_BODY_OK = (
    "import pythoncom\n"
    "\n"
    "class SapGuiBase:\n"
    '    """The SapGuiLibrary is a library that enables users to create tests."""\n'
    "\n"
    "    __version__ = '1.2'  # upstream version this vendor snapshot tracks\n"
    "    def foo(self):\n"
    "        pass\n"
)


def test_check_passes_when_only_the_tolerated_changes_are_present(tmp_path):
    upstream = tmp_path / "upstream.py"
    vendor = tmp_path / "vendor.py"
    upstream.write_text(_UPSTREAM_BODY, encoding="utf-8")
    vendor.write_text(_VENDOR_HEADER + _VENDOR_BODY_OK, encoding="utf-8")
    assert mod.check(str(upstream), str(vendor)) == []


def test_check_flags_a_line_changed_beyond_the_tolerated_class_rename(tmp_path):
    upstream = tmp_path / "upstream.py"
    vendor = tmp_path / "vendor.py"
    bad_vendor_body = _VENDOR_BODY_OK.replace("def foo(self):", "def foo(self, extra):")
    upstream.write_text(_UPSTREAM_BODY, encoding="utf-8")
    vendor.write_text(_VENDOR_HEADER + bad_vendor_body, encoding="utf-8")
    problems = mod.check(str(upstream), str(vendor))
    assert len(problems) == 1
    assert "def foo" in problems[0][1] and "extra" in problems[0][2]


def test_check_does_not_tolerate_renaming_prose_mentions_outside_the_class_line(tmp_path):
    # Seule la déclaration `class SapGuiLibrary:` elle-même est renommée dans le
    # vendor réel -- les mentions en prose dans les docstrings restent identiques
    # mot pour mot à l'upstream. Une VRAIE divergence sur une ligne de prose (pas
    # juste "toujours identique") doit être détectée.
    upstream = tmp_path / "upstream.py"
    vendor = tmp_path / "vendor.py"
    changed_body = _UPSTREAM_BODY.replace(
        '"""The SapGuiLibrary is a library that enables users to create tests."""',
        '"""The SapGuiLibrary is a totally different description."""',
    )
    upstream.write_text(_UPSTREAM_BODY, encoding="utf-8")
    vendor.write_text(_VENDOR_HEADER + changed_body.replace(
        "class SapGuiLibrary:", "class SapGuiBase:"), encoding="utf-8")
    problems = mod.check(str(upstream), str(vendor))
    assert len(problems) == 1
    assert "totally different" in problems[0][2]


def test_check_tolerates_a_missing_version_comment_too(tmp_path):
    # Le commentaire de fin de ligne sur __version__ est optionnel dans les deux sens.
    upstream = tmp_path / "upstream.py"
    vendor = tmp_path / "vendor.py"
    vendor_body = _VENDOR_BODY_OK.replace(
        "__version__ = '1.2'  # upstream version this vendor snapshot tracks",
        "__version__ = '1.2'")
    upstream.write_text(_UPSTREAM_BODY, encoding="utf-8")
    vendor.write_text(_VENDOR_HEADER + vendor_body, encoding="utf-8")
    assert mod.check(str(upstream), str(vendor)) == []


def test_check_flags_a_line_count_mismatch_as_a_single_problem(tmp_path):
    upstream = tmp_path / "upstream.py"
    vendor = tmp_path / "vendor.py"
    upstream.write_text(_UPSTREAM_BODY, encoding="utf-8")
    vendor.write_text(_VENDOR_HEADER + _VENDOR_BODY_OK + "extra_line = 1\n", encoding="utf-8")
    problems = mod.check(str(upstream), str(vendor))
    assert len(problems) == 1


def test_main_succeeds_and_skips_when_upstream_file_is_absent(tmp_path, capsys):
    rc = mod.main(["--upstream-file", str(tmp_path / "nope.py")])
    assert rc == 0
    assert "introuvable" in capsys.readouterr().out


def test_main_against_the_real_repo_vendor_file_if_a_local_upstream_clone_exists():
    # Garde-fou vivant : si le clone local _upstream/ est présent sur cette
    # machine (cf. docs/audit-upstream.md), le vrai fichier vendorisé du dépôt
    # ne doit diverger que par les changements tolérés.
    if not os.path.isfile(mod._DEFAULT_UPSTREAM):
        return   # clone non présent (cas normal en CI) -- rien à vérifier ici
    assert mod.main([]) == 0
