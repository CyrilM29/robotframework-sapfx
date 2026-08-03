"""Tests off-SAP du lecteur de listes ABAP (convention #5 du CLAUDE.md).

``sapfx_common.abap_list.reconstruct_rows`` (reconstruction géométrique pure :
labels -> lignes/cellules) + le keyword `Read Abap List` du mixin grille.
"""
import pytest

from SapEccLibrary import SapEccLibrary
from sapfx_common.abap_list import reconstruct_rows
from sapfx_common.object_tree import ScreenElement


def _lbl(eid, text, left, top):
    return ScreenElement(id=eid, type="GuiLabel", text=text,
                         left=left, top=top, width=60, height=16)


def test_reconstruct_rows_groupe_par_bande_et_trie_par_gauche():
    elements = [
        _lbl("l3", "LH", 10, 40), _lbl("l4", "0400", 80, 40),      # ligne 2
        _lbl("l1", "Carrier", 10, 20), _lbl("l2", "Conn.", 80, 20),  # ligne 1 (en-tête)
    ]
    assert reconstruct_rows(elements) == [["Carrier", "Conn."], ["LH", "0400"]]


def test_reconstruct_rows_tolere_un_leger_decalage_vertical():
    elements = [_lbl("a", "A", 10, 20), _lbl("b", "B", 80, 22)]   # 2 px d'écart
    assert reconstruct_rows(elements) == [["A", "B"]]
    assert reconstruct_rows(elements, row_tolerance=0) == [["A"], ["B"]]


def test_reconstruct_rows_ignore_labels_vides_ou_sans_geometrie_et_autres_types():
    elements = [
        _lbl("ok", "Seul", 10, 20),
        _lbl("vide", "   ", 80, 20),
        ScreenElement(id="sans-geo", type="GuiLabel", text="Perdu"),
        ScreenElement(id="txt", type="GuiTextField", text="Valeur",
                      left=150, top=20, width=60, height=16),
    ]
    assert reconstruct_rows(elements) == [["Seul"]]


def test_reconstruct_rows_vide_sans_labels():
    assert reconstruct_rows([]) == []


def test_read_abap_list_retourne_les_lignes_reconstruites():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: [
        _lbl("l1", "Carrier", 10, 20), _lbl("l2", "LH", 10, 40),
    ]
    assert lib.read_abap_list() == [["Carrier"], ["LH"]]


def test_read_abap_list_echoue_clairement_sans_liste():
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: []
    with pytest.raises(AssertionError, match="n'expose aucun label"):
        lib.read_abap_list()


def test_read_abap_list_explique_le_rendu_shell_sans_accessibilite():
    # cas observé live (A4H, SAP GUI 8.00) : liste rendue dans un GuiShell
    # opaque, zéro GuiLabel -> l'erreur nomme le mode accessibilité à activer.
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: _SHELL_SCREEN
    with pytest.raises(AssertionError, match="accessibilité"):
        lib.read_abap_list()


# --- préflight : Get List Rendering Status / Abap List Should Be Readable -----

# L'écran de liste tel qu'observé live sans mode accessibilité : un shell
# opaque, zéro label (histogramme réel : GuiCustomControl + GuiContainerShell
# + GuiShell, aucun GuiLabel).
_SHELL_SCREEN = [
    ScreenElement(id="wnd[0]/usr/cntlGRID1", type="GuiCustomControl"),
    ScreenElement(id="wnd[0]/usr/cntlGRID1/shellcont", type="GuiContainerShell"),
    ScreenElement(id="wnd[0]/usr/cntlGRID1/shellcont/shell", type="GuiShell"),
]


def _lib_with(elements):
    lib = SapEccLibrary(screenshots_on_error=False)
    lib._screen_elements = lambda: elements
    return lib


def test_status_detecte_le_shell_sans_labels_et_nomme_l_option():
    status = _lib_with(_SHELL_SCREEN).get_list_rendering_status()
    assert status["readable_labels"] == 0
    assert status["shell_rendered"] is True
    assert status["list_readable"] is False
    assert status["accessibility_mode_needed"] is True
    assert "Accessibility" in status["hint"]


def test_status_liste_lisible_quand_les_labels_sont_la():
    status = _lib_with([_lbl("l1", "Carrier", 10, 20),
                        _lbl("l2", "LH", 10, 40)]).get_list_rendering_status()
    assert status["readable_labels"] == 2
    assert status["list_readable"] is True
    assert status["accessibility_mode_needed"] is False
    assert status["hint"] is None


def test_status_un_ecran_alv_avec_labels_ne_reclame_pas_l_accessibilite():
    # un shell est LÉGITIME sur un écran ALV : tant que des labels existent,
    # rien n'est à corriger (l'ALV se lit avec Read Grid).
    status = _lib_with(_SHELL_SCREEN + [_lbl("l1", "Titre", 10, 20)]) \
        .get_list_rendering_status()
    assert status["shell_rendered"] is True
    assert status["accessibility_mode_needed"] is False


def test_abap_list_should_be_readable_passe_ou_echoue_avec_la_cause():
    _lib_with([_lbl("l1", "Carrier", 10, 20)]).abap_list_should_be_readable()
    with pytest.raises(AssertionError, match="contrôle shell"):
        _lib_with(_SHELL_SCREEN).abap_list_should_be_readable()
    with pytest.raises(AssertionError, match="sans contenu de liste"):
        _lib_with([]).abap_list_should_be_readable()
