"""Tests hors SAP du mixin ``ComboBoxKeywords`` : sélection par clé, surcharge
actionnable de `Select From List By Label`, formats de l'utilisateur (SU3) et
saisie de dates/nombres convertis."""
import pytest

from SapEccLibrary import SapEccLibrary


class _Entry:
    def __init__(self, key, value):
        self.Key = key
        self.Value = value


class FakeCombo:
    def __init__(self, entries, key, changeable=True):
        self.Type = "GuiComboBox"
        self.Entries = [_Entry(k, v) for k, v in entries]
        self.Key = key
        self.Changeable = changeable

    @property
    def Text(self):
        return next((e.Value for e in self.Entries if e.Key == self.Key), "")


class FakeSession:
    def __init__(self, objects):
        self._objects = objects
        self.Busy = False

    def findById(self, element_id, raise_on_missing=True):
        key = element_id.replace(" ", "")
        if key in self._objects:
            return self._objects[key]
        if raise_on_missing:
            raise KeyError(element_id)
        return None


def _lib(objects):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = FakeSession(objects)
    lib.get_element_type = lambda eid: getattr(lib.session.findById(eid), "Type", "GuiTextField")
    return lib


def test_entries_key_et_selection_par_cle():
    combo = FakeCombo([("A", "Dialog"), ("B", "System")], "A")
    lib = _lib({"cmb": combo})
    assert lib.get_combo_box_entries("cmb") == [{"key": "A", "value": "Dialog"},
                                                {"key": "B", "value": "System"}]
    assert lib.get_combo_box_key("cmb") == "A"
    assert lib.select_combo_box_entry_by_key("cmb", "B") == "B"
    assert combo.Key == "B"


def test_la_cle_lue_est_rendue_telle_quelle_blanc_compris():
    # SM37 « Or after event » : deux clés distinctes "" et " " ; lire " "
    # comme "" rendrait une restauration invérifiable.
    combo = FakeCombo([("", ""), (" ", ""), ("*", "*")], " ")
    lib = _lib({"cmb": combo})
    assert lib.get_combo_box_key("cmb") == " "
    assert lib.select_combo_box_entry_by_key("cmb", "*") == "*"
    assert lib.select_combo_box_entry_by_key("cmb", " ") == " "
    assert lib.get_combo_box_key("cmb") == " "
    combo.Key = None
    assert lib.get_combo_box_key("cmb") == ""


def test_selection_par_cle_refuse_affichage_et_cle_absente_en_listant():
    lib = _lib({"cmb": FakeCombo([("A", "Dialog")], "A", changeable=False)})
    with pytest.raises(ValueError, match="AFFICHAGE"):
        lib.select_combo_box_entry_by_key("cmb", "A")
    lib = _lib({"cmb": FakeCombo([("A", "Dialog")], "A")})
    with pytest.raises(ValueError, match="clé 'Z'") as exc:
        lib.select_combo_box_entry_by_key("cmb", "Z")
    assert "'A' : Dialog" in str(exc.value)


def test_select_from_list_by_label_surcharge_est_actionnable():
    combo = FakeCombo([("A", "Dialog"), ("B", "System"), ("S", "Service")], "A")
    lib = _lib({"cmb": combo})
    assert lib.select_from_list_by_label("cmb", "System") == "B"
    with pytest.raises(ValueError, match="LOCALISÉ"):
        lib.select_from_list_by_label("cmb", "ZZ_NOPE")
    with pytest.raises(ValueError, match="ambigu"):
        lib.select_from_list_by_label("cmb", "S")
    assert lib.select_from_list_by_label("cmb", "Service") == "S"   # l'exact gagne


def test_un_element_qui_n_est_pas_une_combo_est_refuse():
    class Field:
        Type = "GuiTextField"
    with pytest.raises(ValueError, match="pas une GuiComboBox"):
        _lib({"txt": Field()}).get_combo_box_entries("txt")


def _su3_lib():
    sub = "wnd[0]/usr/tabsTABSTRIP1/tabpDEFA/ssubMAINAREA:SAPLSUID_MAINTENANCE:1105/"
    tab = type("Tab", (), {"Type": "GuiTab", "select": lambda self: None})()
    objects = {
        "wnd[0]/usr/tabsTABSTRIP1/tabpDEFA": tab,
        sub + "cmbSUID_ST_NODE_DEFAULTS-DCPFM": FakeCombo([("", "1.234.567,89")], " "),
        sub + "cmbSUID_ST_NODE_DEFAULTS-DATFM": FakeCombo([("1", "DD.MM.YYYY")], "1"),
        sub + "cmbSUID_ST_NODE_DEFAULTS-TIMEFM": FakeCombo([("0", "24h")], "0"),
        "wnd[0]/usr/txtDATE": type("F", (), {"Type": "GuiTextField", "text": ""})(),
    }
    lib = _lib(objects)
    calls = []
    lib.run_transaction = lambda tcode, **k: calls.append(tcode)
    lib.wait_until_element_present = lambda *a, **k: None
    lib.wait_until_busy_done = lambda *a, **k: None
    lib.send_vkey = lambda vkey, window=0: calls.append("vkey%s" % vkey)
    lib.input_text = lambda eid, text: calls.append((eid, text))
    return lib, calls


def test_get_user_formats_lit_les_cles_de_su3_et_revient_par_f3():
    lib, calls = _su3_lib()
    formats = lib.get_user_formats()
    assert calls[0] == "SU3" and calls[-1] == "vkey3"
    assert formats["date_format"] == "1" and formats["decimal_notation"] == ""
    assert formats["date_pattern"] == "DD.MM.YYYY"


def test_input_date_et_input_number_convertissent_au_format_de_l_utilisateur():
    lib, calls = _su3_lib()
    with pytest.raises(AssertionError, match="Get User Formats"):
        lib.input_date("wnd[0]/usr/txtDATE", "2026-09-01")
    assert lib.input_date("wnd[0]/usr/txtDATE", "2026-09-01", date_format="2") == "09/01/2026"
    lib.get_user_formats()
    assert lib.input_date("wnd[0]/usr/txtDATE", "2026-09-01") == "01.09.2026"
    assert lib.input_number("wnd[0]/usr/txtDATE", "1234.5") == "1234,5"
    assert lib.input_number("wnd[0]/usr/txtDATE", "1234.5", decimal_notation="X",
                            decimals=2) == "1234.50"
    assert ("wnd[0]/usr/txtDATE", "01.09.2026") in calls
