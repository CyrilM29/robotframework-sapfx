"""Tests hors SAP du mixin ``WindowKeywords`` : `Dismiss Modal Window` referme
un modal par la touche, sinon par le bouton de sa barre, sinon par le bouton
SPOP, vérifie la disparition, et échoue en listant les boutons réels."""
import pytest
from pythoncom import com_error

from SapEccLibrary import SapEccLibrary
from sapfx_common.object_tree import ScreenElement


class FakeWindow:
    def __init__(self, session, accepts_vkey):
        self._session = session
        self._accepts = accepts_vkey
        self.vkeys = []

    def sendVKey(self, vkey):
        if not self._accepts:
            raise com_error("Cannot send Vkey")
        self.vkeys.append(vkey)
        self._session.close()


class FakeButton:
    def __init__(self, session):
        self._session = session
        self.pressed = 0

    def press(self):
        self.pressed += 1
        self._session.close()


class FakeSession:
    def __init__(self, accepts_vkey=True, buttons=()):
        self.Busy = False
        self.window = FakeWindow(self, accepts_vkey)
        self.objects = {"wnd[1]": self.window}
        for suffix in buttons:
            self.objects["wnd[1]/" + suffix] = FakeButton(self)

    def close(self):
        self.objects = {}

    def findById(self, element_id, raise_on_missing=True):
        if element_id in self.objects:
            return self.objects[element_id]
        if raise_on_missing:
            raise com_error("not found")
        return None


def _lib(session):
    lib = SapEccLibrary(screenshots_on_error=False, poll_interval="0.01s")
    lib.session = session
    lib._screen_elements = lambda: [
        ScreenElement(id="wnd[1]/tbar[0]/btn[0]", type="GuiButton", text="Continue"),
        ScreenElement(id="wnd[1]/usr/btnZZ", type="GuiButton", tooltip="Custom"),
    ]
    return lib


def test_la_touche_suffit_quand_le_modal_l_accepte():
    session = FakeSession(accepts_vkey=True)
    assert _lib(session).dismiss_modal_window() is True
    assert session.window.vkeys == [12]


def test_le_bouton_de_la_barre_prend_le_relais_quand_la_touche_est_refusee():
    session = FakeSession(accepts_vkey=False, buttons=["tbar[0]/btn[12]"])
    assert _lib(session).dismiss_modal_window() is True
    assert session.objects == {}


def test_confirm_utilise_entree_puis_le_bouton_spop_oui():
    session = FakeSession(accepts_vkey=False, buttons=["usr/btnSPOP-OPTION1"])
    assert _lib(session).dismiss_modal_window(confirm=True) is True


def test_aucune_fenetre_rend_faux_sans_rien_faire():
    session = FakeSession()
    session.close()
    assert _lib(session).dismiss_modal_window() is False


def test_un_modal_informatif_sans_annuler_se_ferme_par_son_seul_bouton():
    # le « Details » d'une grille SE16 : btn[0] « Close window » et btn[71]
    # Find, ni Annuler ni question SPOP (relevé live 2026-09-07)
    session = FakeSession(accepts_vkey=False, buttons=["tbar[0]/btn[0]", "tbar[0]/btn[71]"])
    assert _lib(session).dismiss_modal_window() is True


def test_un_dialogue_de_question_n_est_jamais_valide_par_defaut():
    # Oui/Non SPOP sans Annuler : refuser de presser Oui à la place d'Annuler
    session = FakeSession(accepts_vkey=False, buttons=["tbar[0]/btn[0]", "usr/btnSPOP-OPTION1"])
    with pytest.raises(AssertionError, match="restée ouverte"):
        _lib(session).dismiss_modal_window()
    assert session.objects["wnd[1]/usr/btnSPOP-OPTION1"].pressed == 0


def test_une_fenetre_qui_resiste_echoue_en_listant_ses_boutons():
    session = FakeSession(accepts_vkey=False, buttons=[])
    with pytest.raises(AssertionError, match="restée ouverte") as exc:
        _lib(session).dismiss_modal_window()
    assert "wnd[1]/tbar[0]/btn[0] (Continue)" in str(exc.value)
    assert "wnd[1]/usr/btnZZ (Custom)" in str(exc.value)
