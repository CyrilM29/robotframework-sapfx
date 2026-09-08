"""Tests hors SAP de ``sapfx_common.combo_box`` (entrées d'une GuiComboBox)."""
from sapfx_common.combo_box import (
    entries_as_dicts,
    find_by_key,
    find_by_label,
    format_entries,
)


class _Entry:
    def __init__(self, key, value):
        self.Key = key
        self.Value = value


def test_entries_as_dicts_garde_la_cle_telle_quelle_et_normalise_la_valeur():
    entries = entries_as_dicts([("A", "Dialog   "), _Entry("", "1.234.567,89"), (" ", " ")])
    assert entries == [{"key": "A", "value": "Dialog"},
                       {"key": "", "value": "1.234.567,89"},
                       {"key": " ", "value": ""}]    # deux clés distinctes, vide et blanc


def test_find_by_key_strict_d_abord_puis_sans_blancs_si_unique():
    entries = entries_as_dicts([("A", "Dialog"), ("B", "System"), ("", "none"), (" ", "blank")])
    assert find_by_key(entries, " ")["value"] == "blank"     # strict : le blanc est une clé
    assert find_by_key(entries, "")["value"] == "none"
    assert find_by_key(entries, " A ")["value"] == "Dialog"  # sans blancs, unique
    assert find_by_key(entries, "Z") is None


def test_find_by_label():
    entries = entries_as_dicts([("A", "Dialog"), ("B", "System"), ("S", "Service")])
    assert [e["key"] for e in find_by_label(entries, "s")] == ["B", "S"]
    assert [e["key"] for e in find_by_label(entries, "System", exact=True)] == ["B"]
    assert find_by_label(entries, "") == []


def test_format_entries_liste_et_tronque():
    text = format_entries(entries_as_dicts([("A", "Dialog"), ("B", "")]), limit=1)
    assert "'A' : Dialog" in text and "2 entrées en tout" in text
