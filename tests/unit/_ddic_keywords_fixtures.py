"""Doublures et helpers partages des tests des mixins SE16/DDIC (E/S ecran factices) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import json


import pytest


from pythoncom import com_error


from SapEccLibrary.keywords._ddic import DdicKeywords


from SapEccLibrary.keywords._se16 import Se16Keywords


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


class _FakeRadio:
    """Un radio du dialogue des paramètres SE16 : coché ou non."""

    def __init__(self, selected):
        self.Selected = selected


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
                 scroll_max=None, output_radio="radRSEUMOD-TBALV_GRID"):
        self.screen = screen
        self.popup = popup
        self.table = _FakeTable(visible, locked, scroll_max)
        self.dialogs_dismissed = 0
        #: Le radio COCHÉ du dialogue des paramètres SE16 (suffixe d'id) ;
        #: ``None`` = aucun (dialogue d'une autre forme).
        self.output_radio = output_radio

    def dismiss_popup(self):
        self.popup = None
        self.dialogs_dismissed += 1

    def findById(self, element_id, raise_on_error=True):  # noqa: N802 (API COM)
        if element_id.endswith("tblSAPLALDBSINGLE"):
            return self.table
        # Popup « Number of Entries » : son compteur n'existe QUE lorsque le
        # popup est ouvert (le clic sur btn[31] le pose), comme le vrai SE16.
        if "txtG_DBCOUNT" in element_id:
            return object() if self.popup == "count" else None
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
            if self.popup == "alv" and "/rad" in element_id:
                return _FakeRadio(self.output_radio is not None
                                  and element_id.endswith(self.output_radio))
            return object()
        return object()


class _Usr:
    def __init__(self, items):
        self.Children = _FakeChildren(items)


class _Recorder(DdicKeywords, Se16Keywords):
    """DdicKeywords sur primitives enregistreuses : chaque action est journalisée,
    la grille SE16 sert des lignes DD02L prédéfinies."""

    poll_interval = 0.01

    def __init__(self, rows=(), screen="grid", popup=None, visible=7,
                 locked=False, status=("", ""), alv_mode=True,
                 scroll_max=None, count_text="0",
                 output_radio="radRSEUMOD-TBALV_GRID"):
        self.session = _FakeSession(screen, popup, visible, locked, scroll_max,
                                    output_radio)
        self.calls = []
        #: Ce que le popup de comptage AFFICHE (séparateurs de milliers
        #: compris : ils dépendent du profil utilisateur).
        self.count_text = count_text
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
        # Les deux gestes qui OUVRENT une modale sur les écrans SE16 pilotés
        # par le mixin : le comptage et le réglage d'affichage.
        if element_id == "wnd[0]/tbar[1]/btn[31]":
            self.session.popup = "count"
        elif element_id == "wnd[0]/mbar/menu[3]/menu[0]":
            self.session.popup = "alv"

    def get_value(self, element_id):
        self.calls.append(("get_value", element_id))
        return self.count_text

    def select_radio_button(self, element_id):
        self.calls.append(("radio", element_id))

    def dismiss_modal_window(self, window=1, confirm=False):
        self.calls.append(("dismiss", window))
        if self.session.popup is not None:
            self.session.dismiss_popup()
            return True
        return False

    def send_vkey(self, vkey, window=0):
        self.calls.append(("vkey", vkey, window))
        # Entrée valide une modale, F12 l'annule : les deux la referment.
        if window == 1 and vkey in (0, 12):
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


def _entry(name="SCARR", klass="table"):
    return {"object_name": name, "package": "", "tadir_type": "",
            "ddic": {"present": True, "tabclass": "TRANSP", "as4local": "A",
                     "as4vers": "0000"},
            "class": klass,
            "probe": {"status": "not_probed", "message_type": "", "detail": ""},
            "entry_count": None, "entry_count_reason": "not_measured"}
