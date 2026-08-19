"""Tests hors SAP du mixin ``DdicKeywords`` (E/S écran factices).

Le flux SE16/DD02L est rejoué contre des primitives enregistreuses : ouverture
d'écran de sélection à verdict structuré (statut de type ``E``, dialogue de
message, popup de choix des champs), sélection multiple DÉFILÉE au-delà de la
fenêtre visible, lecture DD02L par colonnes techniques, garde-fous contre les
campagnes « vertes mais fausses » (grille absente hors écran de sélection,
plafond de lecture atteint, sonde canari des critères positionnels), artefact
écrit/hashé et comparé. Le vrai COM n'est jamais requis (pattern fake du
projet, voir ``conftest.py``).
"""
import json

import pytest
from pythoncom import com_error

from SapEccLibrary.keywords._ddic import DdicKeywords
from sapfx_common.ddic_inventory import classification_map

CMAP = classification_map(["TRANSP", "INTTAB", "VIEW", "APPEND"])

MAX_HITS = "wnd[0]/usr/txtMAX_SEL"
MULTI_TABLE = ("wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/"
               "ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE")


class _FakeScrollbar:
    """Scrollbar du table control du dialogue : refuse le défilement quand
    ``locked`` (le cas qui doit devenir un échec actionnable) et PLAFONNE à
    ``maximum`` comme une vraie (au-delà, le vrai contrôle lève un
    ``com_error`` « invalid argument », constaté live sur SE11)."""

    def __init__(self, locked=False, maximum=None):
        self.Position = 0
        self.locked = locked
        if maximum is not None:
            self.Maximum = maximum

    def __setattr__(self, name, value):
        if name == "Position":
            if getattr(self, "locked", False):
                object.__setattr__(self, "Position", 0)   # défilement ignoré
                return
            maximum = getattr(self, "Maximum", None)
            if maximum is not None and int(value) > int(maximum):
                raise com_error("invalid argument")
        object.__setattr__(self, name, value)


class _FakeTable:
    def __init__(self, visible=7, locked=False, scroll_max=None):
        self.VisibleRowCount = visible
        self.VerticalScrollbar = _FakeScrollbar(locked, scroll_max)


class _FakeCheckbox:
    Type = "GuiCheckBox"
    Id = "/app/con[0]/ses[0]/wnd[1]/usr/chkSELFIELD"


class _FakeChildren:
    def __init__(self, items):
        self._items = list(items)
        self.Count = len(self._items)

    def ElementAt(self, index):  # noqa: N802 (API COM)
        return self._items[index]


class _FakeLabel:
    def __init__(self, text):
        self.Text = text


class _FakeSession:
    """Résout les ids que le mixin interroge ; le reste est réputé absent.

    ``popup`` : ``None`` (aucune modale), ``"message"`` (dialogue SAPMSDYP,
    refermé au premier Entrée) ou ``"checkbox"`` (choix des champs). ``screen``
    : ``"grid"``, ``"selection"`` ou ``"blank"`` (ni l'un ni l'autre : mode
    liste classique). Le vrai SE16 n'affiche une grille QUE si la sélection
    ramène des lignes ; le fake reproduit ce lien (``screen`` est recalculé à
    chaque exécution F8), sans quoi les gardes qui distinguent « aucune ligne »
    de « pas de grille » ne seraient pas réellement exercés.
    """

    def __init__(self, screen="grid", popup=None, visible=7, locked=False,
                 scroll_max=None):
        self.screen = screen
        self.popup = popup
        self.table = _FakeTable(visible, locked, scroll_max)
        self.dialogs_dismissed = 0

    def dismiss_popup(self):
        self.popup = None
        self.dialogs_dismissed += 1

    def findById(self, element_id, raise_on_error=True):  # noqa: N802 (API COM)
        if element_id.endswith("tblSAPLALDBSINGLE"):
            return self.table
        if "cntlGRID1" in element_id:
            return object() if self.screen == "grid" else None
        if element_id == MAX_HITS:
            return object() if self.screen in ("grid", "selection") else None
        if element_id.startswith("wnd[1]"):
            if self.popup is None:
                return None
            if "txtMESSTXT" in element_id:
                index = int(element_id.split("txtMESSTXT")[1])
                if self.popup == "message" and index <= 2:
                    return _FakeLabel(["Type FLTP n'est pas admis",
                                       "pour un élément de dynpro"][index - 1])
                return None
            if element_id == "wnd[1]/usr":
                items = ([_FakeCheckbox()] if self.popup == "checkbox" else [])
                return _FakeChildren(items) and _Usr(items)
            return object()
        return object()


class _Usr:
    def __init__(self, items):
        self.Children = _FakeChildren(items)


class _Recorder(DdicKeywords):
    """DdicKeywords sur primitives enregistreuses : chaque action est journalisée,
    la grille SE16 sert des lignes DD02L prédéfinies."""

    poll_interval = 0.01

    def __init__(self, rows=(), screen="grid", popup=None, visible=7,
                 locked=False, status=("", ""), alv_mode=True,
                 scroll_max=None):
        self.session = _FakeSession(screen, popup, visible, locked, scroll_max)
        self.calls = []
        self._rows = list(rows)
        self._status = status
        self.screenshots = 0
        self.alv_mode = alv_mode
        self._selected = []      # noms sélectionnés (I1-LOW ou dialogue)
        self._matched = list(rows)

    # -- primitives factices ------------------------------------------------

    def run_transaction(self, tcode):
        self.calls.append(("run_transaction", tcode))

    def wait_until_busy_done(self, timeout=None):
        pass

    def wait_until_element_present(self, element_id, timeout=None):
        self.calls.append(("wait_present", element_id))
        if self.session.findById(element_id, False) is None:
            raise AssertionError("Element '%s' did not appear." % element_id)

    def input_text(self, element_id, text):
        self.calls.append(("input", element_id, text))
        if element_id.endswith("I1-LOW"):
            self._selected = [text.strip().upper()] if text.strip() else []
        elif "SLOW_I" in element_id:
            self._selected.append(text.strip().upper())

    def click_element(self, element_id):
        self.calls.append(("click", element_id))

    def send_vkey(self, vkey, window=0):
        self.calls.append(("vkey", vkey, window))
        if window == 1 and vkey == 0:
            self.session.dismiss_popup()
        if vkey == 8:
            self._execute_selection()

    def _execute_selection(self):
        """F8 : SE16 n'ouvre la grille que si la sélection ramène des lignes."""
        self._matched = [r for r in self._rows
                         if not self._selected
                         or str(r.get("TABNAME", "")).upper() in self._selected]
        self._selected = []
        if not self.alv_mode:
            self.session.screen = "blank"     # sortie liste classique
        else:
            self.session.screen = "grid" if self._matched else "selection"

    def get_status_message(self):
        return self._status

    def select_checkbox(self, element_id):
        self.calls.append(("checkbox", element_id))

    def take_screenshot(self):
        self.screenshots += 1

    def read_full_grid(self, table_id, max_rows=None, columns=None):
        self.calls.append(("read_grid", table_id, max_rows, tuple(columns or ())))
        rows = self._matched if max_rows is None else self._matched[:int(max_rows)]
        return list(rows)

    def _timeout_secs(self, timeout):
        return 0.05 if timeout is None else 0.05


def _filled_values(recorder):
    return [text for kind, element_id, text in
            [c for c in recorder.calls if c[0] == "input"]
            if "SLOW_I" in element_id]


# ------------------------------------------- ouverture d'écran de sélection

def test_reach_selection_screen_reports_reached():
    lib = _Recorder(screen="selection")
    state = lib.reach_se16_selection_screen("dd02l")
    assert state["reached"] is True
    assert state["verdict"] == "reached"
    assert ("input", "wnd[0]/usr/ctxtDATABROWSE-TABLENAME", "DD02L") in lib.calls


def test_reach_selection_screen_reports_status_type_e_without_text_assertion():
    lib = _Recorder(screen="blank", status=("E", "Structure, pas une table"))
    state = lib.reach_se16_selection_screen("SFL_AUX")
    assert state == {"reached": False, "verdict": "rejected", "message_type": "E",
                     "status_text": "Structure, pas une table", "dialog_text": ""}


def test_reach_selection_screen_absorbs_message_dialog_and_continues():
    lib = _Recorder(screen="selection", popup="message")
    state = lib.reach_se16_selection_screen("SGEOCITY")
    assert state["reached"] is True
    assert "FLTP" in state["dialog_text"]        # relevé pour le journal
    assert lib.session.dialogs_dismissed == 1


def test_reach_selection_screen_reports_dialog_rejection():
    lib = _Recorder(screen="blank", popup="message")
    state = lib.reach_se16_selection_screen("ZBROKEN")
    assert state["reached"] is False
    assert state["verdict"] == "dialog"
    assert state["dialog_text"]


def test_reach_selection_screen_ticks_the_wide_table_checkbox_with_a_relative_id():
    lib = _Recorder(screen="selection", popup="checkbox")
    state = lib.reach_se16_selection_screen("DD02L")
    assert state["reached"] is True
    ticked = [c for c in lib.calls if c[0] == "checkbox"]
    # Id RELATIF à la session : un id absolu /app/con[0]/... casse findById.
    assert ticked == [("checkbox", "wnd[1]/usr/chkSELFIELD")]


def test_reach_selection_screen_ticks_nothing_when_the_popup_has_no_checkbox():
    """Modale sans case à cocher ni ligne MESSTXT : rien n'est coché, la
    modale est laissée en place et le verdict le dit (l'ancien parsing de
    signature rendait une chaîne vide, silencieusement ignorée)."""
    lib = _Recorder(screen="selection", popup="empty")
    state = lib.reach_se16_selection_screen("DD02L")
    assert state["verdict"] == "modal"
    assert not [c for c in lib.calls if c[0] == "checkbox"]


def test_reach_selection_screen_leaves_an_unknown_modal_in_place():
    lib = _Recorder(screen="selection", popup="other")
    state = lib.reach_se16_selection_screen("DD02L")
    assert state["verdict"] == "modal"
    assert state["reached"] is False


# ------------------------------------------------- sélection multiple bornée

def test_fill_multiple_selection_fills_visible_rows_and_takes_over():
    lib = _Recorder()
    lib.fill_multiple_selection(["SCARR", " SPFLI ", ""])
    assert _filled_values(lib) == ["SCARR", "SPFLI"]
    assert ("click", "wnd[1]/tbar[0]/btn[8]") in lib.calls


def test_fill_multiple_selection_scrolls_beyond_the_visible_window():
    lib = _Recorder(visible=3)
    lib.fill_multiple_selection([f"T{i}" for i in range(7)])
    assert _filled_values(lib) == [f"T{i}" for i in range(7)]
    # 3 fenêtres : deux défilements, aux lignes absolues 3 puis 6.
    assert lib.session.table.VerticalScrollbar.Position == 6


def test_fill_multiple_selection_ecrit_a_l_index_decale_quand_le_defilement_plafonne():
    # Comme tout GuiTableControl, la scrollbar du dialogue plafonne (ici à 4) :
    # la dernière fenêtre CHEVAUCHE la précédente et doit s'écrire à un index
    # local décalé, sinon les dernières valeurs écrasent les précédentes.
    lib = _Recorder(visible=3, scroll_max=4)
    lib.fill_multiple_selection([f"T{i}" for i in range(7)])
    cells = [(element_id, text) for kind, element_id, text in
             [c for c in lib.calls if c[0] == "input"] if "SLOW_I" in element_id]
    assert [text for _, text in cells] == [f"T{i}" for i in range(7)]
    # fenêtres 0-2 puis 3-5 (position 3), puis T6 à l'index local 2 de la
    # fenêtre plafonnée en 4 : la ligne absolue visée reste 6.
    assert cells[-1][0].endswith("[1,2]")
    assert lib.session.table.VerticalScrollbar.Position == 4


def test_fill_multiple_selection_fails_actionably_when_scrolling_is_refused():
    lib = _Recorder(visible=3, locked=True)
    with pytest.raises(AssertionError, match="batches of at most 3"):
        lib.fill_multiple_selection([f"T{i}" for i in range(7)])
    assert ("vkey", 12, 1) in lib.calls     # dialogue refermé avant l'échec


def test_fill_multiple_selection_refuses_a_lone_string():
    with pytest.raises(AssertionError, match="must be a LIST"):
        _Recorder().fill_multiple_selection("SCARR")


def test_fill_multiple_selection_refuses_empty_list():
    with pytest.raises(AssertionError, match="no value provided"):
        _Recorder().fill_multiple_selection(["", "  "])


# --------------------------------------------------------- classification

def test_classify_single_name_skips_the_dialog():
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP",
                           "AS4LOCAL": "A", "AS4VERS": "0000"}])
    entries = lib.classify_ddic_objects(["scarr"], CMAP)
    assert entries["SCARR"]["class"] == "table"
    assert not any(c[0] == "click" and "VALU_PUSH" in c[1] for c in lib.calls)


def test_classify_reads_only_the_technical_columns_it_consumes():
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}])
    lib.classify_ddic_objects(["SCARR"], CMAP)
    reads = [c for c in lib.calls if c[0] == "read_grid"]
    assert reads and reads[0][3] == ("TABNAME", "TABCLASS", "AS4LOCAL", "AS4VERS")


def test_classify_batches_and_flags_missing_objects():
    rows = [{"TABNAME": "SCARR", "TABCLASS": "TRANSP"},
            {"TABNAME": "SFL_AUX", "TABCLASS": "INTTAB"},
            {"TABNAME": "SCUS_BOOK", "TABCLASS": "VIEW"}]
    lib = _Recorder(rows=rows)
    names = ["SCARR", "SFL_AUX", "SCUS_BOOK", "ZGHOST"]
    entries = lib.classify_ddic_objects(names, CMAP, batch_size=2)
    assert entries["SCARR"]["class"] == "table"
    assert entries["SFL_AUX"]["class"] == "non_consultable_ddic"
    assert entries["SCUS_BOOK"]["class"] == "view"
    ghost = entries["ZGHOST"]
    assert ghost["ddic"]["present"] is False
    assert ghost["class"] == "unknown"
    assert ghost["class_reason"] == "absent_from_dd02l"
    # 4 noms, lots de 2 : deux passages SE16 complets.
    assert [c for c in lib.calls if c[0] == "run_transaction"] == [
        ("run_transaction", "SE16")] * 2


def test_classify_honours_a_batch_size_larger_than_the_legacy_cap():
    rows = [{"TABNAME": f"T{i}", "TABCLASS": "TRANSP"} for i in range(9)]
    lib = _Recorder(rows=rows, visible=12)
    lib.classify_ddic_objects([f"T{i}" for i in range(9)], CMAP, batch_size=9)
    # Un seul passage SE16 : le plafond figé à 7 ne s'impose plus au dialogue.
    assert [c for c in lib.calls if c[0] == "run_transaction"] == [
        ("run_transaction", "SE16")]


def test_classify_refuses_a_non_positive_batch_size():
    lib = _Recorder()
    with pytest.raises(AssertionError, match="strictly positive"):
        lib.classify_ddic_objects(["SCARR"], CMAP, batch_size=0)
    with pytest.raises(AssertionError, match="strictly positive"):
        lib.classify_ddic_objects(["SCARR"], CMAP, batch_size=-3)


def test_classify_refuses_a_lone_string():
    with pytest.raises(AssertionError, match="must be a LIST"):
        _Recorder().classify_ddic_objects("SCARR", CMAP)


def test_classify_active_only_filters_on_as4local():
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}])
    lib.classify_ddic_objects(["SCARR"], CMAP, active_only=True)
    assert ("input", "wnd[0]/usr/ctxtI2-LOW", "A") in lib.calls
    lib2 = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}])
    lib2.classify_ddic_objects(["SCARR"], CMAP, active_only="False")
    assert not any(c[1].endswith("I2-LOW") for c in lib2.calls
                   if c[0] == "input")


def test_classify_treats_an_empty_selection_screen_as_no_matching_row():
    """Écran de sélection conservé = aucune ligne (cas légitime), à condition
    que la sonde canari confirme les critères positionnels."""
    lib = _Recorder(rows=[{"TABNAME": "DD02L", "TABCLASS": "TRANSP"}])
    entries = lib.classify_ddic_objects(["ZGHOST"], CMAP)
    assert entries["ZGHOST"]["class"] == "unknown"
    assert entries["ZGHOST"]["class_reason"] == "absent_from_dd02l"


def test_classify_fails_when_the_data_browser_is_not_in_alv_mode():
    """Ni grille ni écran de sélection : sortie liste classique. L'ancien code
    rapportait « absent de DD02L » pour TOUT le lot, campagne verte et fausse."""
    lib = _Recorder(rows=[{"TABNAME": "SCARR", "TABCLASS": "TRANSP"}],
                    alv_mode=False)
    with pytest.raises(AssertionError, match="Use ALV Grid In Data Browser"):
        lib.classify_ddic_objects(["SCARR"], CMAP)


def test_classify_fails_when_the_row_cap_is_reached():
    """Plafond ATTEINT = troncature possible : les noms suivants seraient
    marqués absents à tort. L'échec le dit au lieu de mentir."""
    rows = [{"TABNAME": "SCARR", "TABCLASS": "TRANSP"} for _ in range(20)]
    lib = _Recorder(rows=rows)
    with pytest.raises(AssertionError, match="row cap"):
        lib.classify_ddic_objects(["SCARR"], CMAP)


def test_classify_canary_probe_detects_shifted_positional_criteria():
    """Lot vide + canari vide = les critères I1/I2 ne sont plus TABNAME/AS4LOCAL
    (choix des champs persistant par utilisateur)."""
    lib = _Recorder(rows=[], screen="selection")
    with pytest.raises(AssertionError, match="canary probe"):
        lib.classify_ddic_objects(["ZGHOST"], CMAP)


def test_classify_canary_probe_runs_once_per_instance():
    lib = _Recorder(rows=[{"TABNAME": "DD02L", "TABCLASS": "TRANSP"}],
                    screen="selection")
    lib.classify_ddic_objects(["ZGHOST", "ZOTHER"], CMAP, batch_size=1)
    canary = [c for c in lib.calls
              if c[0] == "input" and c[1].endswith("I1-LOW") and c[2] == "DD02L"]
    assert len(canary) == 1


# ------------------------------------------------------- helpers exposés

def test_sample_keyword_accepts_the_entries_dict():
    lib = _Recorder()
    entries = {
        "SCARR": {"object_name": "SCARR", "class": "table"},
        "SFLIGHT": {"object_name": "SFLIGHT", "class": "table"},
        "SBOOK": {"object_name": "SBOOK", "class": "table"},
        "SFL_AUX": {"object_name": "SFL_AUX", "class": "non_consultable_ddic"},
    }
    assert lib.sample_ddic_objects_for_probe(entries, per_class=2) == [
        "SBOOK", "SCARR", "SFL_AUX"]
    assert lib.sample_ddic_objects_for_probe(entries, per_class=1,
                                             classes="table") == ["SBOOK"]


def test_merge_name_lists_keyword_returns_names_and_truncation():
    lib = _Recorder()
    names, truncated = lib.merge_ddic_name_lists([["B", "A"], ["A", "C"]], 2)
    assert names == ["A", "B"]
    assert truncated is True


def test_classification_map_keyword_translates_an_invalid_extra():
    lib = _Recorder()
    assert lib.get_ddic_classification_map(["TRANSP"]) == {"TRANSP": "table"}
    with pytest.raises(AssertionError, match="Classe normalisée inconnue"):
        lib.get_ddic_classification_map(["TRANSP"], {"APPEND": "table_bidon"})


# ---------------------------------------------------------------- artefact

def _entry(name="SCARR", klass="table"):
    return {"object_name": name, "package": "", "tadir_type": "",
            "ddic": {"present": True, "tabclass": "TRANSP", "as4local": "A",
                     "as4vers": "0000"},
            "class": klass,
            "probe": {"status": "not_probed", "message_type": "", "detail": ""},
            "entry_count": None, "entry_count_reason": "not_measured"}


def test_write_artifact_round_trips_and_hash_ignores_timestamp(tmp_path):
    lib = _Recorder()
    scope = {"packages": ["SAPBC_DATAMODEL"], "prefixes": [],
             "object_types": ["TABL"], "max_objects": 10, "batch_size": 7}
    entries = {"SCARR": _entry()}
    path = tmp_path / "inventory.json"
    proof = lib.write_ddic_inventory_artifact(str(path), "a4h", scope, entries)
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["summary"]["table"] == 1
    assert on_disk["target_id"] == "a4h"
    proof2 = lib.write_ddic_inventory_artifact(str(path), "a4h", scope, entries)
    assert proof["sha256"] == proof2["sha256"]  # l'horodatage ne compte pas
    assert proof["summary"]["discovered"] == 1


def test_compare_artifacts_keyword_reads_two_files(tmp_path):
    lib = _Recorder()
    scope = {"packages": ["P"], "prefixes": [], "object_types": ["TABL"],
             "max_objects": 10, "batch_size": 7}
    path_a, path_b = tmp_path / "a.json", tmp_path / "b.json"
    lib.write_ddic_inventory_artifact(str(path_a), "a4h", scope,
                                      {"SCARR": _entry()})
    lib.write_ddic_inventory_artifact(
        str(path_b), "s4h", scope,
        {"SCARR": _entry(klass="view"), "ZNEW": _entry("ZNEW")})
    comparison = lib.compare_ddic_inventory_artifacts(str(path_a), str(path_b))
    assert comparison["compatible"] is True
    assert comparison["only_in_b"] == ["ZNEW"]
    assert comparison["reclassified"] == [
        {"object_name": "SCARR", "a": "table", "b": "view"}]


def test_validate_and_probe_keywords_translate_errors():
    lib = _Recorder()
    with pytest.raises(AssertionError, match="package ou un préfixe"):
        lib.validate_ddic_scope([], [], 10, 7)
    entry = {"probe": {}, "entry_count": None, "entry_count_reason": ""}
    with pytest.raises(AssertionError, match="Statut de sonde inconnu"):
        lib.record_ddic_probe(entry, "explosion")
    lib.record_ddic_probe(entry, "rejected", message_type="E")
    assert entry["probe"]["message_type"] == "E"


def test_validate_scope_keyword_accepts_a_scalar_override():
    """-v CAMPAIGN_PACKAGES:X passe un SCALAIRE : le nom ne doit pas être
    éclaté en lettres."""
    lib = _Recorder()
    scope = lib.validate_ddic_scope("SAPBC_DATAMODEL", "", 10, 7)
    assert scope["packages"] == ["SAPBC_DATAMODEL"]
