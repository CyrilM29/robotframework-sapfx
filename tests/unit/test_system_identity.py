"""Tests hors SAP de l'identité du système : la logique pure
(``sapfx_common.system_identity``) et le mixin ``SystemIdentityKeywords``
(ouverture PAR POSITION du statut, lecture des trois dialogues, fermeture
vérifiée, sections non lues NOMMÉES et jamais remplacées)."""
import pytest
from pythoncom import com_error

from SapEccLibrary import SapEccLibrary
from sapfx_common.object_tree import ScreenElement
from sapfx_common.system_identity import (
    ANCHOR_KEYS,
    build_identity,
    compare_identities,
    components_from_rows,
    describe_identity,
    expected_mismatches,
    parse_release_list,
    parse_server_name,
)

STATUS = {"txtSYST-MANDT": "001", "txtSYST-UNAME": "DEVELOPER", "txtSYST-LANGU": "EN",
          "txtSHKONTEXT-TCODE": "SESSION_MANAGER", "txtCVERS_TXT-STEXT": "- See Details -",
          "txtCUSTOMER": "DEMOSYSTEM", "txtSERVERNAME": "vhcala4hci_A4H_00",
          "txtSYST-OPSYS": "Linux", "txtDBNAME": "HDB",
          "txtSTATUS_INFO-DATABASE_RELEASE": "2.00.044.00.1571081837"}
KERNEL = {"txtKINFOSTRUC-KERNEL_RELEASE": "777", "txtKINFOSTRUC-KERNEL_PATCH_LEVEL": "500",
          "txtKINFOSTRUC-SUPPORTED_SAP_VERS": "753, 754, 777",
          "txtKINFOSTRUC-IP_ADDRESS": "172.17.0.2"}
ROWS = [{"COMPONENT": "SAP_BASIS", "RELEASE": "754", "EXTRELEASE": "0007",
         "HIGH_PATCH": "SAPK-75407INSAPBASIS", "DESC_TEXT": "SAP Basis Component"},
        {"COMPONENT": "SAP_ABA", "RELEASE": "75E", "EXTRELEASE": "0007",
         "HIGH_PATCH": "SAPK-75E07INSAPABA", "DESC_TEXT": "Cross-Application Component"},
        {"COMPONENT": "", "RELEASE": "", "EXTRELEASE": "", "HIGH_PATCH": "", "DESC_TEXT": ""}]


# -- logique pure --------------------------------------------------------------

def test_parse_server_name_et_release_list():
    assert parse_server_name("vhcala4hci_A4H_00") == {
        "host": "vhcala4hci", "system_id": "A4H", "instance_number": "00"}
    assert parse_server_name("host_with_under_A4H_01") == {
        "host": "host_with_under", "system_id": "A4H", "instance_number": "01"}
    assert parse_server_name("something-else") == {}
    assert parse_server_name("a_b_c") == {}            # SID de 3 caractères, instance numérique
    assert parse_release_list(" 753, 754,777 ") == ["753", "754", "777"]
    assert parse_release_list("") == []


def test_build_identity_derive_sid_release_kernel_et_ancre():
    identity = build_identity(STATUS, KERNEL, ROWS, "A4H", unread=[])
    assert identity["system_id"] == "A4H" and identity["client"] == "001"
    assert identity["application_host"] == "vhcala4hci" and identity["instance_number"] == "00"
    assert identity["basis_release"] == "754" and identity["basis_sp_level"] == "0007"
    assert identity["basis_support_package"] == "SAPK-75407INSAPBASIS"
    assert identity["kernel_release"] == "777" and identity["kernel_patch_level"] == "500"
    assert identity["supported_sap_releases"] == ["753", "754", "777"]
    assert identity["ip_address"] == "172.17.0.2"
    assert [c["component"] for c in identity["components"]] == ["SAP_BASIS", "SAP_ABA"]
    assert identity["unread"] == []
    # Les champs de statut et de kernel que la doublure n'affiche pas sont
    # NOMMÉS, jamais rendus comme une valeur ni confondus avec une section non lue.
    assert "language" not in identity["missing_fields"]["status"]
    assert "machine_type" in identity["missing_fields"]["status"]
    assert "abap_load" in identity["missing_fields"]["kernel"]
    assert "champs absents : status" in describe_identity(identity)
    assert set(identity["anchor"]) == set(ANCHOR_KEYS)
    assert identity["anchor"]["basis_release"] == "754"
    assert "ip_address" not in identity["anchor"]          # volatile, jamais comparé
    assert "SAP_BASIS 754 SP 0007" in describe_identity(identity)
    assert "kernel 777 PL 500" in describe_identity(identity)


def test_les_sections_non_lues_restent_vides_et_nommees():
    identity = build_identity({"txtSYST-MANDT": "001"}, None, None, "A4H",
                              unread=["kernel : bouton absent", ""])
    assert identity["system_id"] == "A4H"           # SID de session, faute de serveur
    assert identity["basis_release"] == "" and identity["kernel_release"] == ""
    assert identity["components"] == [] and identity["supported_sap_releases"] == []
    assert identity["unread"] == ["kernel : bouton absent"]
    assert "non lu : kernel" in describe_identity(identity)
    assert "kernel" not in identity["missing_fields"]      # section non lue, pas champs absents
    assert "client" not in identity["missing_fields"]["status"]


def test_compare_identities_ne_regarde_que_l_ancre():
    a = build_identity(STATUS, KERNEL, ROWS, "A4H")
    b = build_identity(STATUS, dict(KERNEL, **{"txtKINFOSTRUC-KERNEL_RELEASE": "793",
                                              "txtKINFOSTRUC-IP_ADDRESS": "172.17.0.3"}),
                       [dict(ROWS[0], RELEASE="758")], "A4H")
    diffs = compare_identities(a, b)
    assert [d["key"] for d in diffs] == ["basis_release", "kernel_release"]
    assert compare_identities(a, a) == []


def test_expected_mismatches_signale_les_cles_absentes():
    identity = build_identity(STATUS, KERNEL, ROWS, "A4H")
    assert expected_mismatches(identity, {"basis_release": "754", "client": "001"}) == []
    assert expected_mismatches(identity, {"basis_release": 758, "nope": "x"}) == [
        {"key": "basis_release", "expected": "758", "actual": "754"},
        {"key": "nope", "expected": "x", "actual": ""}]


def test_components_from_rows_tolere_les_colonnes_manquantes():
    assert components_from_rows([{"COMPONENT": "ST-PI", "RELEASE": "740"}]) == [
        {"component": "ST-PI", "release": "740", "sp_level": "", "support_package": "",
         "description": ""}]
    assert components_from_rows(None) == []


# -- mixin ---------------------------------------------------------------------

class _Field:
    def __init__(self, text):
        self.Text = text


class _Button:
    def __init__(self, on_press, refuse=False):
        self._on_press = on_press
        self._refuse = refuse

    def press(self):
        if self._refuse:
            raise com_error("button refused")
        self._on_press()


class _Info:
    SystemName = "A4H"


class FakeSession:
    """Trois dialogues : le statut (wnd[1]) s'ouvre par le clic sur l'entrée de
    menu, le kernel et les composants (wnd[2]) par leurs boutons ; chaque
    ``dismiss`` retire la fenêtre. ``status_layout`` = False simule un écran
    dont l'entrée 11 n'ouvre pas le statut."""

    def __init__(self, status_layout=True, kernel_button=True, details_button=True,
                 details_refused=False):
        self.Busy = False
        self.Info = _Info()
        self.objects = {}
        self.status_layout = status_layout
        self.kernel_button = kernel_button
        self.details_button = details_button
        self.details_refused = details_refused
        self.opened = []

    def open_status(self):
        self.opened.append("status")
        self.objects["wnd[1]"] = object()
        if not self.status_layout:
            self.objects["wnd[1]/usr/txtOTHER"] = _Field("x")
            return
        for suffix, text in STATUS.items():
            self.objects["wnd[1]/usr/" + suffix] = _Field(text)
        if self.kernel_button:
            self.objects["wnd[1]/tbar[0]/btn[17]"] = _Button(self.open_kernel)
        if self.details_button:
            self.objects["wnd[1]/usr/btnPRELINFO"] = _Button(self.open_details,
                                                              self.details_refused)

    def open_kernel(self):
        self.opened.append("kernel")
        self.objects["wnd[2]"] = object()
        for suffix, text in KERNEL.items():
            self.objects["wnd[2]/usr/" + suffix] = _Field(text)

    def open_details(self):
        self.opened.append("details")
        self.objects["wnd[2]"] = object()
        self.objects["wnd[2]/usr/tabsVERSDETAILS/tabpCOMP_VERS/"
                     "ssubDETAIL_SUBSCREEN:SAPLOCS_UI_CONTROLS:0301/"
                     "cntlSCV_CU_CONTROL/shellcont/shell"] = object()

    def close(self, window):
        prefix = "wnd[%s]" % window
        self.objects = {k: v for k, v in self.objects.items() if not k.startswith(prefix)}

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self.objects:
            return self.objects[element_id]
        if raise_on_missing:
            raise com_error("not found")
        return None


# Les entrées du menu System relevées live : 754 (13 entrées, « Status... »
# en 11), 758 (12 entrées, « List » disparue, « Status... » en 10). « Log Off »
# ferme la liste des deux côtés : l'ancre est « avant-dernière entrée ».
_ENTRIES_754 = ["New GUI Window", "Close GUI Window", "User Profile", "Services",
                "Utilities", "List", "Services for Object", "My Objects",
                "Own Spool Requests", "Own Jobs", "Short Message", "Status...", "Log Off"]
_ENTRIES_758 = [e for e in _ENTRIES_754 if e != "List"]
_LAYOUTS = {"754": _ENTRIES_754, "758": _ENTRIES_758, "none": [],
            # une disposition inconnue où l'avant-dernière entrée n'ouvre pas
            # de dialogue : refus AVANT tout clic
            "no_dialog": ["User Profile", "Status", "Log Off"]}


def _lib(session, menus=(("System", 4), ("Help", 5)), layout="754"):
    lib = SapEccLibrary(screenshots_on_error=False, poll_interval="0.01s")
    lib.session = session
    elements = []
    for text, position in menus:
        elements.append(ScreenElement(id="wnd[0]/mbar/menu[%d]" % position,
                                      type="GuiMenu", text=text))
    status_index = None
    for index, text in enumerate(_LAYOUTS[layout]):
        elements.append(ScreenElement(id="wnd[0]/mbar/menu[%d]/menu[%d]" % (menus[-2][1], index),
                                      type="GuiMenu", text=text))
        if text == "Status...":
            status_index = index
    lib._screen_elements = lambda: elements
    lib.clicked = []

    def click(element_id):
        lib.clicked.append(element_id)
        if status_index is not None and element_id.endswith("/menu[%d]" % status_index):
            session.open_status()
    lib.click_element = click
    lib.wait_until_busy_done = lambda *a, **k: None
    lib.dismissed = []

    def dismiss(window=1, confirm=False):
        lib.dismissed.append(window)
        session.close(window)
        return True
    lib.dismiss_modal_window = dismiss
    lib.read_grid = lambda grid_id, max_rows=None, columns=None: [dict(r) for r in ROWS]
    return lib


def test_get_system_identity_lit_les_trois_dialogues_et_referme_tout():
    session = FakeSession()
    lib = _lib(session)
    identity = lib.get_system_identity()
    assert lib.clicked == ["wnd[0]/mbar/menu[4]/menu[11]"]   # System = avant-dernier
    assert session.opened == ["status", "kernel", "details"]
    assert identity["basis_release"] == "754" and identity["kernel_release"] == "777"
    assert identity["system_id"] == "A4H" and identity["client"] == "001"
    assert identity["unread"] == []
    assert lib.dismissed == [2, 2, 1]                          # kernel, composants, statut
    assert session.objects == {}                               # plus aucune fenêtre


def test_la_position_du_menu_system_suit_la_barre_percue():
    session = FakeSession()
    lib = _lib(session, menus=(("Table Entry", 0), ("Edit", 1), ("Goto", 2),
                               ("Settings", 3), ("System", 5), ("Help", 6)))
    lib.get_system_identity(kernel=False, components=False)
    assert lib.clicked == ["wnd[0]/mbar/menu[5]/menu[11]"]
    assert session.opened == ["status"]


def test_l_entree_status_est_resolue_sur_la_758_ou_elle_est_en_position_10():
    """Le registre de la seconde release (2026-09-08) : l'indice 11 gravé y
    cliquait « Log Off ». L'avant-dernière entrée du menu System, elle, tient
    sur les deux dispositions."""
    session = FakeSession()
    lib = _lib(session, layout="758")
    identity = lib.get_system_identity(kernel=False, components=False)
    assert lib.clicked == ["wnd[0]/mbar/menu[4]/menu[10]"]
    assert "Log Off" not in str(lib.clicked)
    assert identity["client"] == "001"


def test_open_system_status_rend_l_id_de_l_entree_cliquee():
    """La trace de la résolution (revue indépendante du tour 2, réserve R3) :
    un test la confronte à un relevé du menu qui ne dépend pas d'elle."""
    lib = _lib(FakeSession(), layout="758")
    assert lib.open_system_status() == "wnd[0]/mbar/menu[4]/menu[10]"
    assert lib.clicked == ["wnd[0]/mbar/menu[4]/menu[10]"]


def test_une_avant_derniere_entree_sans_dialogue_est_refusee_avant_tout_clic():
    lib = _lib(FakeSession(), layout="no_dialog")
    with pytest.raises(AssertionError, match="n'ouvre pas un dialogue"):
        lib.open_system_status()
    assert lib.clicked == []                                   # rien n'a été cliqué


def test_les_sections_facultatives_non_lues_sont_nommees_jamais_inventees():
    session = FakeSession(kernel_button=False, details_refused=True)
    identity = _lib(session).get_system_identity()
    assert identity["kernel_release"] == "" and identity["basis_release"] == ""
    assert any("kernel" in item for item in identity["unread"])
    assert any("composants" in item for item in identity["unread"])
    assert session.objects == {}


def test_une_entree_11_qui_n_ouvre_pas_le_statut_est_refermee_et_nommee():
    session = FakeSession(status_layout=False)
    lib = _lib(session)
    with pytest.raises(AssertionError, match="Select Menu Item"):
        lib.get_system_identity()
    assert lib.dismissed == [1]                                # le modal inattendu est refermé


def test_sans_entrees_l_echec_nomme_la_voie_manuelle():
    lib = _lib(FakeSession(), layout="none")
    with pytest.raises(AssertionError, match="moins de deux entrées.*Select Menu Item"):
        lib.open_system_status()
    assert lib.clicked == []


def test_un_modal_deja_ouvert_est_refuse():
    session = FakeSession()
    session.objects["wnd[1]"] = object()
    with pytest.raises(AssertionError, match="déjà ouvert"):
        _lib(session).open_system_status()


def test_system_identity_should_be_compare_l_ancre_et_refuse_le_volatile():
    session = FakeSession()
    lib = _lib(session)
    identity = lib.system_identity_should_be(basis_release="754", kernel_release="777",
                                             client="001")
    assert identity["basis_release"] == "754"
    with pytest.raises(AssertionError, match="basis_release attendu '758', lu '754'"):
        lib.system_identity_should_be(identity=identity, basis_release="758")
    with pytest.raises(ValueError, match="hors ancre"):
        lib.system_identity_should_be(identity=identity, ip_address="172.17.0.2")
    with pytest.raises(ValueError, match="Aucune attente"):
        lib.system_identity_should_be(identity=identity)
