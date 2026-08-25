"""Tests hors SAP et hors réseau des DEUX keywords de bibliothèque ajoutés par
la campagne de croisement (convention 5).

- ``DdicKeywords.get_se16_selection_criteria`` et ``read_ddic_table_fields``
  (canal ECC) : le flux SE16/DD03L rejoué contre des primitives enregistreuses,
  critères résolus par NOM (jamais par position), et les trois garde-fous
  « jamais vert et faux » (plafond atteint, résultat vide, grille absente hors
  écran de sélection) ;
- ``SapApiLibrary.probe_odata_entity_sets`` (canal API) : le mode TOLÉRANT,
  celui qui enregistre un refus et poursuit, par opposition au tout ou rien de
  ``post_odata_batch`` qui reste le bon comportement pour préparer un jeu de
  données.
"""
import pytest

from SapApiLibrary import SapApiLibrary
from SapEccLibrary.keywords._ddic import DdicKeywords
from SapEccLibrary.keywords._se16 import Se16Keywords
from sapfx_common.object_tree import ScreenElement

MAX_HITS = "wnd[0]/usr/txtMAX_SEL"

#: Écran de sélection DD03L tel qu'il est perçu live : chaque critère porte son
#: nom TECHNIQUE de champ, ce qui rend la carte dérivable au lieu d'être
#: maintenue à la main.
DD03L_SCREEN = [
    ScreenElement(id="wnd[0]/usr/lblTABNAME", type="GuiLabel", text="TABNAME",
                  left=10, top=100, width=80, height=10),
    ScreenElement(id="wnd[0]/usr/ctxtI1-LOW", type="GuiCTextField",
                  changeable=True, left=100, top=100, width=60, height=10),
    ScreenElement(id="wnd[0]/usr/lblFIELDNAME", type="GuiLabel",
                  text="FIELDNAME", left=10, top=120, width=80, height=10),
    ScreenElement(id="wnd[0]/usr/ctxtI2-LOW", type="GuiCTextField",
                  changeable=True, left=100, top=120, width=60, height=10),
    ScreenElement(id="wnd[0]/usr/lblAS4LOCAL", type="GuiLabel",
                  text="AS4LOCAL", left=10, top=140, width=80, height=10),
    ScreenElement(id="wnd[0]/usr/ctxtI3-LOW", type="GuiCTextField",
                  changeable=True, left=100, top=140, width=60, height=10),
    ScreenElement(id="wnd[0]/usr/lblMAX", type="GuiLabel",
                  text="Maximum No. of Hits", left=10, top=200, width=120,
                  height=10),
    ScreenElement(id=MAX_HITS, type="GuiTextField", changeable=True,
                  left=140, top=200, width=40, height=10),
]

FIELDS = [
    {"FIELDNAME": "PRODUCT_ID", "POSITION": "0003", "KEYFLAG": "",
     "DATATYPE": "CHAR"},
    {"FIELDNAME": "CLIENT", "POSITION": "0001", "KEYFLAG": "X",
     "DATATYPE": "CLNT"},
    {"FIELDNAME": "NODE_KEY", "POSITION": "0002", "KEYFLAG": "X",
     "DATATYPE": "RAW"},
]


class _FakeSession:
    def __init__(self, screen="grid"):
        self.screen = screen

    def findById(self, element_id, raise_on_error=True):  # noqa: N802 (API COM)
        if "cntlGRID1" in element_id:
            return object() if self.screen == "grid" else None
        if element_id == MAX_HITS:
            return object() if self.screen in ("grid", "selection") else None
        if element_id.startswith("wnd[1]"):
            return None
        return object()


class _Recorder(DdicKeywords, Se16Keywords):
    """DdicKeywords sur primitives enregistreuses : l'écran perçu et les lignes
    de grille sont fournis, chaque action est journalisée."""

    poll_interval = 0.01

    def __init__(self, rows=FIELDS, screen="grid", elements=None,
                 status=("", "")):
        # L'écran de sélection d'abord, puis ce que l'exécution (F8) donne :
        # le vrai SE16 n'ouvre une grille que si la sélection ramène des
        # lignes, et reste sur l'écran de sélection sinon.
        self.session = _FakeSession("selection")
        self._result_screen = screen
        self.calls = []
        self._rows = list(rows)
        self._status = status
        self._elements = list(DD03L_SCREEN if elements is None else elements)
        self.screenshots = 0

    def _screen_elements(self):
        return self._elements

    def run_transaction(self, tcode):
        self.calls.append(("run_transaction", tcode))

    def wait_until_busy_done(self, timeout=None):
        pass

    def wait_until_element_present(self, element_id, timeout=None):
        if self.session.findById(element_id, False) is None:
            raise AssertionError("Element '%s' did not appear." % element_id)

    def input_text(self, element_id, text):
        self.calls.append(("input", element_id, text))

    def send_vkey(self, vkey, window=0):
        self.calls.append(("vkey", vkey, window))
        if vkey == 8:
            self.session.screen = self._result_screen

    def get_status_message(self):
        return self._status

    def take_screenshot(self):
        self.screenshots += 1

    def read_full_grid(self, table_id, max_rows=None, columns=None):
        self.calls.append(("read_grid", table_id, max_rows,
                           tuple(columns or ())))
        rows = self._rows if max_rows is None else self._rows[:int(max_rows)]
        return list(rows)

    def _timeout_secs(self, timeout):
        return 0.05


def _inputs(lib):
    return {element_id: text for kind, element_id, text in
            [c for c in lib.calls if c[0] == "input"]}


# --- carte des critères ------------------------------------------------------

def test_la_carte_des_criteres_est_derivee_de_l_ecran_reel():
    criteria = _Recorder().get_se16_selection_criteria()
    assert criteria == {"TABNAME": "wnd[0]/usr/ctxtI1-LOW",
                        "FIELDNAME": "wnd[0]/usr/ctxtI2-LOW",
                        "AS4LOCAL": "wnd[0]/usr/ctxtI3-LOW"}


def test_un_ecran_sans_critere_reconnaissable_est_un_echec_actionnable():
    lib = _Recorder(elements=[])
    with pytest.raises(AssertionError) as err:
        lib.get_se16_selection_criteria()
    assert "Get Screen Signature" in str(err.value)


# --- lecture DD03L -----------------------------------------------------------

def test_la_lecture_filtre_par_nom_et_sur_la_version_active():
    lib = _Recorder()
    lib.read_ddic_table_fields("snwd_pd")
    saisies = _inputs(lib)
    assert saisies["wnd[0]/usr/ctxtI1-LOW"] == "SNWD_PD"
    assert saisies["wnd[0]/usr/ctxtI3-LOW"] == "A"
    assert ("vkey", 8, 0) in lib.calls


def test_les_criteres_sont_resolus_par_nom_pas_par_position():
    """Le choix des champs de sélection persiste par utilisateur et déplace les
    critères : la résolution par nom est ce qui rend le keyword insensible."""
    permuted = [
        ScreenElement(id="wnd[0]/usr/lblAS4LOCAL", type="GuiLabel",
                      text="AS4LOCAL", left=10, top=100, width=80, height=10),
        ScreenElement(id="wnd[0]/usr/ctxtI1-LOW", type="GuiCTextField",
                      changeable=True, left=100, top=100, width=60, height=10),
        ScreenElement(id="wnd[0]/usr/lblTABNAME", type="GuiLabel",
                      text="TABNAME", left=10, top=120, width=80, height=10),
        ScreenElement(id="wnd[0]/usr/ctxtI2-LOW", type="GuiCTextField",
                      changeable=True, left=100, top=120, width=60, height=10),
        ScreenElement(id=MAX_HITS, type="GuiTextField", changeable=True,
                      left=140, top=200, width=40, height=10),
    ]
    lib = _Recorder(elements=permuted)
    lib.read_ddic_table_fields("SNWD_PD")
    saisies = _inputs(lib)
    assert saisies["wnd[0]/usr/ctxtI2-LOW"] == "SNWD_PD"
    assert saisies["wnd[0]/usr/ctxtI1-LOW"] == "A"


def test_un_critere_attendu_absent_liste_ceux_qui_sont_presents():
    sans_tabname = [
        ScreenElement(id="wnd[0]/usr/lblFIELDNAME", type="GuiLabel",
                      text="FIELDNAME", left=10, top=100, width=80, height=10),
        ScreenElement(id="wnd[0]/usr/ctxtI1-LOW", type="GuiCTextField",
                      changeable=True, left=100, top=100, width=60, height=10),
        ScreenElement(id=MAX_HITS, type="GuiTextField", changeable=True,
                      left=140, top=200, width=40, height=10),
    ]
    with pytest.raises(AssertionError) as err:
        _Recorder(elements=sans_tabname).read_ddic_table_fields("SNWD_PD")
    assert "TABNAME" in str(err.value)
    assert "FIELDNAME" in str(err.value)


def test_la_lecture_est_restreinte_aux_colonnes_techniques_consommees():
    lib = _Recorder()
    lib.read_ddic_table_fields("SNWD_PD")
    read = [c for c in lib.calls if c[0] == "read_grid"][0]
    assert read[3] == ("FIELDNAME", "POSITION", "KEYFLAG", "ROLLNAME",
                       "DATATYPE", "LENG", "DECIMALS", "DOMNAME", "CHECKTABLE")


def test_les_champs_sont_rendus_tries_par_position():
    fields = _Recorder().read_ddic_table_fields("SNWD_PD")
    assert [f["FIELDNAME"] for f in fields] == ["CLIENT", "NODE_KEY",
                                                "PRODUCT_ID"]


def test_la_version_active_peut_etre_relachee_explicitement():
    lib = _Recorder()
    lib.read_ddic_table_fields("SNWD_PD", active_only=False)
    assert "wnd[0]/usr/ctxtI3-LOW" not in _inputs(lib)


# --- garde-fous « jamais vert et faux » --------------------------------------

def test_un_plafond_de_lecture_atteint_est_un_echec_jamais_une_troncature_muette():
    lib = _Recorder(rows=FIELDS)
    with pytest.raises(AssertionError) as err:
        lib.read_ddic_table_fields("SNWD_PD", max_fields=3)
    assert "max_fields" in str(err.value)


def test_un_resultat_vide_est_un_echec_pas_un_contrat_de_champs_vide():
    lib = _Recorder(rows=[], screen="selection")
    with pytest.raises(AssertionError) as err:
        lib.read_ddic_table_fields("SNWD_INCONNUE")
    assert "unknown to the dictionary" in str(err.value)


def test_une_grille_absente_hors_ecran_de_selection_nomme_le_mode_liste():
    lib = _Recorder(screen="blank")
    with pytest.raises(AssertionError) as err:
        lib.read_ddic_table_fields("SNWD_PD")
    assert "Use ALV" in str(err.value)


def test_un_rejet_de_se16_est_rapporte_par_son_type_de_message():
    lib = _Recorder(screen="blank", status=("E", "Structure, pas une table"))
    with pytest.raises(AssertionError) as err:
        lib.read_ddic_table_fields("SFL_AUX")
    assert "verdict 'rejected'" in str(err.value)


def test_une_borne_non_positive_est_refusee():
    with pytest.raises(AssertionError):
        _Recorder().read_ddic_table_fields("SNWD_PD", max_fields=0)


def test_un_nom_de_table_vide_est_refuse():
    with pytest.raises(AssertionError):
        _Recorder().read_ddic_table_fields("   ")


# --- sonde tolérante du canal API -------------------------------------------

def _api_with(responses):
    lib = SapApiLibrary()
    lib.batch_calls = []

    def fake_batch(service_path, operations, alias="default", atomic=True,
                   fail_on_error=True):
        lib.batch_calls.append({"service_path": service_path,
                                "operations": list(operations),
                                "fail_on_error": fail_on_error})
        return list(responses)

    lib.post_odata_batch = fake_batch
    return lib


def test_la_sonde_enregistre_un_refus_et_poursuit():
    lib = _api_with([
        {"status": 200, "reason": "OK", "body": "205", "json": 205},
        {"status": 403, "reason": "Forbidden",
         "body": '{"error":{"code":"CX_SADL_GW_PRIVIL_VIOLATION"}}',
         "json": {"error": {"code": "CX_SADL_GW_PRIVIL_VIOLATION",
                            "message": {"value": "texte localisé"}}}},
        {"status": 200, "reason": "OK", "body": "21", "json": 21},
    ])
    result = lib.probe_odata_entity_sets(
        "/svc", ["ProductSet", "I_DraftAdministrativeData",
                 "BusinessPartnerSet"])
    assert result["truncated"] is False
    assert [p["entity_set"] for p in result["probed"]] == [
        "ProductSet", "I_DraftAdministrativeData", "BusinessPartnerSet"]
    assert result["probed"][0]["count"] == 205
    assert result["probed"][1]["count"] is None
    assert result["probed"][1]["error_code"] == "CX_SADL_GW_PRIVIL_VIOLATION"
    assert result["probed"][2]["count"] == 21


def test_la_sonde_emprunte_explicitement_le_mode_tolerant_du_batch():
    lib = _api_with([{"status": 200, "reason": "OK", "body": "1", "json": 1}])
    lib.probe_odata_entity_sets("/svc", ["A"])
    assert lib.batch_calls[0]["fail_on_error"] is False
    assert lib.batch_calls[0]["operations"] == [
        {"method": "GET", "path": "A/$count"}]


def test_un_compte_nul_n_est_jamais_confondu_avec_un_acces_refuse():
    lib = _api_with([
        {"status": 200, "reason": "OK", "body": "0", "json": 0},
        {"status": 500, "reason": "Server Error", "body": "boom", "json": None},
    ])
    result = lib.probe_odata_entity_sets("/svc", ["Vide", "Casse"])
    assert result["probed"][0]["count"] == 0
    assert result["probed"][1]["count"] is None
    assert result["probed"][1]["error_code"] == ""


def test_la_borne_de_sondage_est_visible_jamais_silencieuse():
    lib = _api_with([{"status": 200, "reason": "OK", "body": "1", "json": 1}])
    result = lib.probe_odata_entity_sets("/svc", ["A", "B", "C"],
                                         max_entity_sets=1)
    assert result["truncated"] is True
    assert len(result["probed"]) == 1
    assert lib.batch_calls[0]["operations"] == [
        {"method": "GET", "path": "A/$count"}]


def test_une_liste_vide_ne_declenche_aucun_aller_retour():
    lib = _api_with([])
    result = lib.probe_odata_entity_sets("/svc", [])
    assert result == {"service_path": "/svc", "probed": [], "truncated": False}
    assert lib.batch_calls == []


def test_un_nom_seul_compte_pour_un_ensemble_pas_pour_ses_caracteres():
    lib = _api_with([{"status": 200, "reason": "OK", "body": "3", "json": 3}])
    result = lib.probe_odata_entity_sets("/svc", "ProductSet")
    assert [p["entity_set"] for p in result["probed"]] == ["ProductSet"]


def test_une_borne_non_positive_de_sondage_est_refusee():
    with pytest.raises(AssertionError):
        _api_with([]).probe_odata_entity_sets("/svc", ["A"], max_entity_sets=0)
