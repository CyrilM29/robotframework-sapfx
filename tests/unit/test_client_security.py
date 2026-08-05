"""Tests hors SAP du préflight de posture de sécurité du poste client :
``sapfx_common.client_security`` (logique pure) et les keywords
`Get Client Security Status` / `Client Security Should Be Hardened` du mixin
diagnostics. Fake COM, convention #5."""
import pytest

from sapfx_common.client_security import (
    INPUT_HISTORY_PATCHED,
    INPUT_HISTORY_UNKNOWN,
    INPUT_HISTORY_VULNERABLE,
    default_history_dirs,
    find_history_databases,
    input_history_cve_status,
)
from SapEccLibrary.SapEccLibrary import SapEccLibrary


class FakeInfo:
    def __init__(self, **props):
        for key, value in props.items():
            setattr(self, key, value)


def _lib(sapapp=None):
    lib = SapEccLibrary(screenshots_on_error=False)
    if sapapp is not None:
        lib.sapapp = sapapp
    return lib


# --- input_history_cve_status : classification CVE-2025-0055 --------------------

@pytest.mark.parametrize("major,minor,pl,expected", [
    (8, 0, 9, INPUT_HISTORY_PATCHED),        # le seuil exact du correctif
    (8, 0, 15, INPUT_HISTORY_PATCHED),
    (8, 0, 8, INPUT_HISTORY_VULNERABLE),
    (8, 0, 0, INPUT_HISTORY_VULNERABLE),
    (8, 10, 0, INPUT_HISTORY_PATCHED),       # 8.10 : publiée après le correctif
    (9, 0, 0, INPUT_HISTORY_PATCHED),
    (7, 70, 12, INPUT_HISTORY_UNKNOWN),      # branche antérieure : voir note SAP
    (8, 0, None, INPUT_HISTORY_UNKNOWN),     # patch level non exposé
    (None, None, None, INPUT_HISTORY_UNKNOWN),
])
def test_cve_status_classifies_versions(major, minor, pl, expected):
    assert input_history_cve_status(major, minor, pl) == expected


def test_cve_status_accepts_com_strings_and_rejects_garbage():
    # les propriétés COM remontent parfois des chaînes
    assert input_history_cve_status("8", "0", "9") == INPUT_HISTORY_PATCHED
    assert input_history_cve_status("8", "0", " 6 ") == INPUT_HISTORY_VULNERABLE
    assert input_history_cve_status("huit", "0", "9") == INPUT_HISTORY_UNKNOWN
    assert input_history_cve_status(8, 0, "PL9") == INPUT_HISTORY_UNKNOWN
    assert input_history_cve_status(True, 0, 9) == INPUT_HISTORY_UNKNOWN


# --- find_history_databases : scan best-effort ----------------------------------

def test_find_history_databases_lists_only_db_files_sorted(tmp_path):
    history = tmp_path / "History"
    history.mkdir()
    (history / "SAPHistoryUSER2.db").write_bytes(b"x")
    (history / "SAPHistoryUSER1.db").write_bytes(b"x")
    (history / "notes.txt").write_text("pas une base")
    found = find_history_databases([history, tmp_path / "absent"])
    assert [f.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for f in found] == [
        "SAPHistoryUSER1.db", "SAPHistoryUSER2.db"]


def test_find_history_databases_empty_when_nothing_found(tmp_path):
    assert find_history_databases([tmp_path]) == []
    assert find_history_databases([tmp_path / "nope"]) == []


def test_default_history_dirs_follow_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    dirs = [str(d) for d in default_history_dirs()]
    assert any(d.endswith("History") and "SAP GUI" in d for d in dirs)
    assert any("LocalLow" in d for d in dirs)
    monkeypatch.delenv("APPDATA")
    monkeypatch.delenv("USERPROFILE")
    assert default_history_dirs() == []


# --- Get Client Security Status --------------------------------------------------

def test_client_security_status_flags_vulnerable_client_and_history(tmp_path):
    history = tmp_path / "hist"
    history.mkdir()
    (history / "SAPHistoryX.db").write_bytes(b"x")
    lib = _lib(sapapp=FakeInfo(MajorVersion=8, MinorVersion=0, Patchlevel=6))
    status = lib.get_client_security_status(history_dirs=str(history))
    assert status["gui_version"] == "8.0 PL6"
    assert status["input_history_cve"] == INPUT_HISTORY_VULNERABLE
    assert status["input_history_present"] is True
    assert len(status["input_history_files"]) == 1
    assert set(status["scripting"]) == {
        "disabled_by_server", "read_only", "recording_disabled"}
    assert len(status["hints"]) == 2
    assert "CVE-2025-0055" in status["hints"][0]


def test_client_security_status_clean_on_patched_client(tmp_path):
    lib = _lib(sapapp=FakeInfo(MajorVersion=8, MinorVersion=0, Patchlevel=9))
    status = lib.get_client_security_status(history_dirs=[tmp_path])
    assert status["input_history_cve"] == INPUT_HISTORY_PATCHED
    assert status["input_history_present"] is False
    assert status["hints"] == []


def test_client_security_status_unknown_version_gets_a_hint(tmp_path):
    status = _lib().get_client_security_status(history_dirs=[tmp_path])
    assert status["gui_version"] is None
    assert status["input_history_cve"] == INPUT_HISTORY_UNKNOWN
    assert any("3472837" in hint for hint in status["hints"])


# --- Client Security Should Be Hardened ------------------------------------------

def test_hardened_passes_on_patched_client_without_history(tmp_path):
    lib = _lib(sapapp=FakeInfo(MajorVersion=8, MinorVersion=10, Patchlevel=0))
    lib.client_security_should_be_hardened(history_dirs=[tmp_path])  # ne lève pas


def test_hardened_fails_on_vulnerable_client(tmp_path):
    lib = _lib(sapapp=FakeInfo(MajorVersion=8, MinorVersion=0, Patchlevel=6))
    with pytest.raises(AssertionError, match="CVE-2025-0055"):
        lib.client_security_should_be_hardened(history_dirs=[tmp_path])


def test_hardened_fails_on_present_history_unless_allowed(tmp_path):
    history = tmp_path / "hist"
    history.mkdir()
    (history / "SAPHistoryX.db").write_bytes(b"x")
    lib = _lib(sapapp=FakeInfo(MajorVersion=8, MinorVersion=0, Patchlevel=9))
    with pytest.raises(AssertionError, match="historique de saisie"):
        lib.client_security_should_be_hardened(history_dirs=[str(history)])
    # tolérance explicite, y compris sous la forme chaîne envoyée par Robot
    lib.client_security_should_be_hardened(
        allow_input_history="True", history_dirs=[str(history)])


def test_hardened_unknown_patch_level_tolerated_by_default(tmp_path):
    lib = _lib()   # aucune version exposée
    lib.client_security_should_be_hardened(history_dirs=[tmp_path])
    with pytest.raises(AssertionError, match="indéterminé"):
        lib.client_security_should_be_hardened(
            allow_unknown_patch_level="False", history_dirs=[tmp_path])
