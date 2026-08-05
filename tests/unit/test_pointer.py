"""Tests de l'effecteur coordonnées (PointerKeywords) : géométrie écran pure,
calcul du point relatif, validation des offsets/boutons ; le geste win32 et la
mise au premier plan sont stubbés (aucune souris ne bouge en CI)."""
import pytest

from SapEccLibrary import SapEccLibrary


class _FakeElement:
    def __init__(self, left=100, top=200, width=400, height=50):
        self.ScreenLeft = left
        self.ScreenTop = top
        self.Width = width
        self.Height = height


class _FakeSession:
    def __init__(self, elements):
        self._elements = elements

    def findById(self, element_id):
        if element_id not in self._elements:
            raise AttributeError("element '%s' not found" % element_id)
        return self._elements[element_id]


def _pointer_lib(elements=None):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.session = _FakeSession(elements or {"wnd[0]/usr/shell": _FakeElement()})
    lib.clicks = []
    lib.focused = []
    lib._send_hardware_click = lambda x, y, button: lib.clicks.append((x, y, button))
    lib._focus_sap_window = lambda: lib.focused.append(True)
    return lib


def test_get_element_screen_region_retourne_la_geometrie_ecran():
    region = _pointer_lib().get_element_screen_region("wnd[0]/usr/shell")
    assert region == {"left": 100, "top": 200, "width": 400, "height": 50}


def test_element_inconnu_echoue_clairement():
    with pytest.raises(AssertionError) as err:
        _pointer_lib().get_element_screen_region("wnd[0]/usr/absent")
    assert "wnd[0]/usr/absent" in str(err.value)


def test_click_au_centre_par_defaut_avec_focus():
    lib = _pointer_lib()
    point = lib.click_element_at_offset("wnd[0]/usr/shell")
    assert point == {"x": 300, "y": 225}          # 100+400*0.5, 200+50*0.5
    assert lib.clicks == [(300, 225, "left")]
    assert lib.focused == [True]


def test_click_offset_relatif_et_bouton_droit_sans_focus():
    lib = _pointer_lib()
    point = lib.click_element_at_offset("wnd[0]/usr/shell", x_pct=0.1,
                                        y_pct="0.15", button="RIGHT",
                                        focus=False)
    assert point == {"x": 140, "y": 207}          # 100+40, 200+7 (int tronqué)
    assert lib.clicks == [(140, 207, "right")]
    assert lib.focused == []


def test_offsets_hors_element_refuses():
    lib = _pointer_lib()
    with pytest.raises(ValueError):
        lib.click_element_at_offset("wnd[0]/usr/shell", x_pct=1.5)
    with pytest.raises(ValueError):
        lib.click_element_at_offset("wnd[0]/usr/shell", y_pct=-0.1)
    assert lib.clicks == []


def test_bouton_inconnu_refuse():
    with pytest.raises(ValueError) as err:
        _pointer_lib().click_element_at_offset("wnd[0]/usr/shell", button="middle")
    assert "left / right / double" in str(err.value)


def test_double_clic_emet_deux_sequences():
    # le stub ne compte qu'un appel : vérifier la table des événements du vrai
    # geste (down/up left répétés) au niveau du module
    from SapEccLibrary.keywords._pointer import _BUTTON_EVENTS
    assert _BUTTON_EVENTS["double"] == _BUTTON_EVENTS["left"]
    lib = _pointer_lib()
    lib.click_element_at_offset("wnd[0]/usr/shell", button="double")
    assert lib.clicks == [(300, 225, "double")]
