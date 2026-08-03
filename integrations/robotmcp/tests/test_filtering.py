"""Tests off-SAP du filtrage de perception (``sap_robotmcp._filtering``),
convention #5 du CLAUDE.md. Pur post-traitement de texte/XML déjà obtenu --
aucune session SAP/navigateur nécessaire."""
import pytest

from sap_robotmcp._filtering import (
    filter_ecc_signature,
    filter_ui5_tree,
    normalize_level,
)


# --- ECC ------------------------------------------------------------------

_SIG = "\n".join([
    "# screen SAPLSE16/SE16/0100",
    "* wnd[0]/usr/ctxtDATABROWSE-TABLENAME\tGuiCTextField\tT000",   # éditable
    "  wnd[0]/usr/lblEmpty\tGuiLabel\t",                             # bruit pur
    "  wnd[0]/usr/lblHint\tGuiLabel\tEnter a table name",            # info, non structurel
    "  wnd[0]/usr/tbar\tGuiToolbar\tToolbar",                        # structurel, avec texte
])


def test_filter_ecc_signature_always_keeps_the_header():
    for level in ("minimal", "standard", "aggressive"):
        assert filter_ecc_signature(_SIG, level).splitlines()[0] == "# screen SAPLSE16/SE16/0100"


def test_filter_ecc_signature_always_keeps_editable_fields():
    for level in ("minimal", "standard", "aggressive"):
        assert "ctxtDATABROWSE-TABLENAME" in filter_ecc_signature(_SIG, level)


def test_filter_ecc_signature_minimal_drops_only_pure_noise():
    out = filter_ecc_signature(_SIG, "minimal")
    assert "lblEmpty" not in out                 # bruit pur -> retiré même en minimal
    assert "lblHint" in out                       # texte utile -> conservé
    assert "GuiToolbar" in out                    # structurel mais avec texte -> conservé en minimal


def test_filter_ecc_signature_standard_also_drops_known_structural_types():
    out = filter_ecc_signature(_SIG, "standard")
    assert "lblEmpty" not in out
    assert "lblHint" in out                       # info non structurelle -> toujours conservée
    assert "GuiToolbar" not in out                 # structurel -> retiré dès standard


def test_filter_ecc_signature_aggressive_keeps_only_editable_fields():
    out = filter_ecc_signature(_SIG, "aggressive")
    lines = out.splitlines()
    assert len(lines) == 2                        # en-tête + le seul champ éditable
    assert lines[1].startswith("* ")


def test_filter_ecc_signature_never_drops_malformed_lines_defensively():
    sig = "# screen X\nligne-sans-tabulations"
    for level in ("minimal", "standard", "aggressive"):
        assert "ligne-sans-tabulations" in filter_ecc_signature(sig, level)


def test_filter_ecc_signature_handles_optional_geometry_column():
    # signature produite avec include_geometry=True : 4e colonne `@x,y LxH` --
    # le filtrage décide sur id/type/texte et ignore la géométrie.
    sig = "\n".join([
        "# screen SAPLSE16/SE16/0100",
        "* wnd[0]/usr/ctxtX\tGuiCTextField\tT000\t@10,20 110x22",   # éditable
        "  wnd[0]/usr/lblVide\tGuiLabel\t\t@10,44 60x22",            # bruit pur
    ])
    out = filter_ecc_signature(sig, "minimal")
    assert "ctxtX" in out
    assert "lblVide" not in out


def test_filter_ecc_signature_handles_header_only_signature():
    assert filter_ecc_signature("# screen X", "aggressive") == "# screen X"


# --- Fiori ------------------------------------------------------------------

def test_filter_ui5_tree_returns_malformed_xml_unchanged():
    bad = "<not valid xml"
    assert filter_ui5_tree(bad, "standard") == bad


def test_filter_ui5_tree_always_keeps_interactive_leaves():
    xml = '<UI5Tree><Button id="b1" text="Go"/></UI5Tree>'
    for level in ("minimal", "standard", "aggressive"):
        assert 'id="b1"' in filter_ui5_tree(xml, level)


def test_filter_ui5_tree_minimal_drops_only_totally_empty_leaves():
    xml = ('<UI5Tree><Label id="l1"/><Label id="l2" text="Hello"/>'
          '<Label/></UI5Tree>')
    out = filter_ui5_tree(xml, "minimal")
    assert 'id="l1"' in out        # a un attribut (id) -> conservé en minimal
    assert 'id="l2"' in out        # a du texte -> conservé
    assert "<Label />" not in out and "<Label/>" not in out   # aucun attribut -> élagué


def test_filter_ui5_tree_standard_drops_non_interactive_leaves_without_text():
    xml = '<UI5Tree><Label id="l1"/><Label id="l2" text="Hello"/></UI5Tree>'
    out = filter_ui5_tree(xml, "standard")
    assert 'id="l1"' not in out    # pas de texte -> élagué dès standard
    assert 'id="l2"' in out        # texte utile -> conservé


def test_filter_ui5_tree_aggressive_drops_non_interactive_leaves_even_with_text():
    xml = '<UI5Tree><Label id="l2" text="Hello"/><Button id="b1" text="Go"/></UI5Tree>'
    out = filter_ui5_tree(xml, "aggressive")
    assert 'id="l2"' not in out    # texte mais non actionnable -> élagué en aggressive
    assert 'id="b1"' in out        # actionnable -> toujours conservé


def test_filter_ui5_tree_preserves_ancestor_chain_of_surviving_nodes():
    # Élagage ascendant : Panel n'est PAS lui-même actionnable/textuel, mais il a
    # un descendant (Button) qui survit -> Panel doit rester pour préserver la
    # hiérarchie/le chemin XPath du Button.
    xml = ('<UI5Tree><Page id="p1"><Panel id="panel1">'
          '<Label id="l1"/><Button id="b1" text="Go"/>'
          '</Panel></Page></UI5Tree>')
    out = filter_ui5_tree(xml, "aggressive")
    assert 'id="b1"' in out
    assert 'id="panel1"' in out    # conservé malgré lui-même "pas intéressant"
    assert 'id="p1"' in out
    assert 'id="l1"' not in out    # feuille non actionnable -> élaguée


def test_filter_ui5_tree_collapses_a_subtree_that_becomes_fully_empty():
    # Tout le sous-arbre de Panel est du bruit pur -> Panel disparaît aussi
    # (élagage en cascade, pas seulement les feuilles d'origine).
    xml = '<UI5Tree><Panel id="panel1"><Label id="l1"/></Panel></UI5Tree>'
    out = filter_ui5_tree(xml, "standard")
    assert "panel1" not in out
    assert out == "<UI5Tree />" or out == "<UI5Tree></UI5Tree>"


def test_filter_ui5_tree_root_always_survives_even_if_everything_is_pruned():
    xml = '<UI5Tree><Label id="l1"/></UI5Tree>'
    out = filter_ui5_tree(xml, "aggressive")
    assert out.startswith("<UI5Tree")


# --- normalize_level ---------------------------------------------------------

@pytest.mark.parametrize("level", ["minimal", "standard", "aggressive"])
def test_normalize_level_passes_through_known_values(level):
    assert normalize_level(level) == level


def test_normalize_level_falls_back_on_unknown_value():
    assert normalize_level("ultra-mega-filtered") == "standard"
    assert normalize_level(None) == "standard"
    assert normalize_level("") == "standard"


def test_normalize_level_respects_custom_fallback():
    assert normalize_level("bogus", fallback="minimal") == "minimal"
