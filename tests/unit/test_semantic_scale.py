"""Les localisateurs humains suivent l'ÉCHELLE DE RENDU de l'écran.

Le défaut reproduit : la géométrie que rend l'API Scripting est en pixels
physiques, donc un facteur d'échelle Windows ou une session RDP depuis un
poste à écran dense (mesuré : 4676x2550 pour un bureau 1920x1080, facteur
~2,4) multiplie toutes les distances, et des tolérances FIXES ne rattachaient
plus aucun libellé : `Get Se16 Selection Criteria` rendait « aucun critère »
sur un écran de sélection parfaitement rendu (vécu le 2026-09-18 sur deux
campagnes EPM). La géométrie de ces tests est celle relevée live sur A4H.
"""
import pytest

from sapfx_common._cross_channel_artifact import selection_criteria
from sapfx_common.semantic import (
    MAX_GEOMETRY_SCALE,
    describe_element,
    geometry_scale,
    resolve_semantic,
    scaled,
    screen_affordances,
)

from _semantic_fixtures import (
    GRID,
    LOGIN,
    SCOPED,
    SE16_SELECTION,
    SELECTION_ROW,
    _el,
    _ids,
    scale_elements,
)

SO_ID_LOW = "wnd[0]/usr/txtI2-LOW"


# -- la mesure de l'échelle -----------------------------------------------------

def test_reference_rendering_is_scale_one():
    # 24 px = la hauteur de référence (mesurée live) : échelle 1, à l'identique.
    assert geometry_scale(SELECTION_ROW) == 1.0
    assert geometry_scale(SE16_SELECTION) == 1.0


def test_smaller_rendering_never_tightens_the_tolerances():
    # Champs de 20 px (thème ancien, doublures) : bornée à 1, jamais 0,83.
    assert geometry_scale(LOGIN) == 1.0
    assert geometry_scale(GRID) == 1.0


def test_no_measurable_height_means_scale_one():
    assert geometry_scale([]) == 1.0
    assert geometry_scale([_el("wnd[0]/usr/txtX", "GuiTextField", changeable=True)]) == 1.0
    # une hauteur nulle ou négative n'est pas une mesure
    assert geometry_scale([_el("wnd[0]/usr/txtX", "GuiTextField",
                               box=(0, 0, 10, 0))]) == 1.0


@pytest.mark.parametrize("factor", [1.25, 1.5, 2.0, 2.435])
def test_scale_is_derived_from_the_field_height(factor):
    assert geometry_scale(scale_elements(SE16_SELECTION, factor)) == pytest.approx(factor, abs=0.05)


def test_scale_ignores_layout_heights_and_is_capped():
    # un shell de 800 px de haut n'est pas une métrique de police
    screen = SE16_SELECTION + [_el("wnd[0]/usr/cntlGRID1/shellcont/shell", "GuiShell",
                                    box=(0, 300, 1900, 800))]
    assert geometry_scale(screen) == 1.0
    huge = [_el("wnd[0]/usr/txtX", "GuiTextField", changeable=True,
                box=(0, 0, 100, 24 * 50))]
    assert geometry_scale(huge) == MAX_GEOMETRY_SCALE


def test_scaled_rounds_to_pixels():
    assert scaled(30, 1.0) == 30
    assert scaled(30, 2.435) == 73
    assert scaled(5, 1.25) == 6


# -- le défaut reproduit, puis corrigé ------------------------------------------

@pytest.mark.parametrize("factor", [1.25, 2.0, 2.435])
def test_fixed_tolerances_lose_every_label_once_the_rendering_is_scaled(factor):
    """La contre-épreuve : avec l'échelle FORCÉE à 1 (le comportement
    historique), l'écran rendu à ``factor`` ne rattache plus aucun libellé."""
    screen = scale_elements(SE16_SELECTION, factor)
    assert resolve_semantic(screen, "SO_ID", _scale=1.0) == []
    assert describe_element(screen, SO_ID_LOW, _scale=1.0) is None


@pytest.mark.parametrize("factor", [1.0, 1.25, 2.0, 2.435])
def test_labels_anchor_at_every_rendering_scale(factor):
    screen = scale_elements(SE16_SELECTION, factor)
    assert _ids(resolve_semantic(screen, "SO_ID", changeable_only=True)) == [SO_ID_LOW]
    assert describe_element(screen, SO_ID_LOW) == "SO_ID"
    # la borne HIGH reste la 2e position de la grille horizontale
    assert _ids(resolve_semantic(screen, "SO_ID @ 2", changeable_only=True)) \
        == ["wnd[0]/usr/txtI2-HIGH"]


@pytest.mark.parametrize("factor", [1.0, 2.435])
def test_se16_selection_criteria_are_derived_at_every_scale(factor):
    """Ce que `Get Se16 Selection Criteria` calcule : la carte des critères
    dérivée de la vue affordances, identique à toute échelle."""
    criteria = selection_criteria(screen_affordances(scale_elements(SE16_SELECTION, factor)))
    assert criteria == {
        "NODE_KEY": "wnd[0]/usr/txtI1-LOW",
        "SO_ID": SO_ID_LOW,
        "CREATED_BY": "wnd[0]/usr/ctxtI3-LOW",
    }


def test_scaling_is_proportional_never_an_amnesty():
    """Un champ hors tolérance à 100 % le reste à toute échelle : l'échelle
    multiplie la tolérance ET l'écart, elle n'élargit rien en proportion."""
    far = [
        _el("wnd[0]/usr/txtLBL", "GuiTextField", "Zone", box=(27, 170, 231, 24)),
        _el("wnd[0]/usr/txtFAR", "GuiTextField", "", changeable=True,
            box=(258 + 31, 170, 151, 24)),   # écart 31 > 30
    ]
    assert resolve_semantic(far, "Zone") == []
    assert resolve_semantic(scale_elements(far, 2.435), "Zone") == []


def test_scope_radius_follows_the_rendering_scale():
    # SCOPED : champs de 20 px, donc échelle 1 à l'identique ; rendu x2, la
    # portée `>>` (100 px de référence) suit et le voisinage reste résolu.
    assert _ids(resolve_semantic(SCOPED, "Header >> Amount")) == ["wnd[0]/usr/txtAMOUNTH"]
    doubled = scale_elements(SCOPED, 2.0)
    assert geometry_scale(doubled) == pytest.approx(40 / 24)
    assert _ids(resolve_semantic(doubled, "Header >> Amount")) == ["wnd[0]/usr/txtAMOUNTH"]
    assert _ids(resolve_semantic(doubled, "Item >> Amount")) == ["wnd[0]/usr/txtAMOUNTI"]


def test_explicit_tolerances_are_reference_pixels_too():
    # Un appelant qui passe une tolérance la donne à 100 % ; elle suit l'échelle.
    screen = scale_elements(SE16_SELECTION, 2.435)
    assert resolve_semantic(screen, "SO_ID", max_horizontal_gap=20) == []      # 20 < 25
    assert _ids(resolve_semantic(screen, "SO_ID", max_horizontal_gap=26,
                                 changeable_only=True)) == [SO_ID_LOW]
