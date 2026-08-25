"""Mixin Se16Keywords : Reach Se16 Selection Screen et Fill Multiple Selection. Doublures dans _ddic_keywords_fixtures (convention #13)."""
import pytest

from _ddic_keywords_fixtures import (  # noqa: F401
    _Recorder,
    _filled_values,
)



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
