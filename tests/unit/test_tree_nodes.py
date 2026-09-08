"""Tests hors SAP de ``sapfx_common.tree_nodes`` (arbres SAP GUI, logique pure)."""
import pytest

from sapfx_common.tree_nodes import (
    TreeNode,
    find_nodes_by_text,
    format_candidates,
    is_progid,
    split_path,
    unique_match,
)

NODES = [
    TreeNode("Favo", "Favorites", folder=True, children=1),
    TreeNode("F00002", "URL - URL - Guides and Tutorials"),
    TreeNode("Root", "User Menu for John Doe", folder=True, children=4),
    TreeNode("0000000003", "Plain ABAP", folder=True),
    TreeNode("0000000029", "URL - ABAP Samples"),
    TreeNode("01  1      1", "", columns={"TEXT": "SAP Customizing Implementation Guide"}),
]


def test_find_nodes_by_text_prefixe_insensible_a_la_casse_et_exact():
    assert [n.key for n in find_nodes_by_text(NODES, "url -")] == ["F00002", "0000000029"]
    assert [n.key for n in find_nodes_by_text(NODES, "plain abap", exact=True)] == ["0000000003"]
    assert find_nodes_by_text(NODES, "") == []


def test_unique_match_rend_le_seul_noeud_et_refuse_absence_et_ambiguite():
    assert unique_match(NODES, "Plain", False, "dans l'arbre").key == "0000000003"
    with pytest.raises(ValueError, match="Aucun nœud 'ZZ'"):
        unique_match(NODES, "ZZ", False, "dans l'arbre")
    with pytest.raises(ValueError, match="ambigu.*2 correspondances") as exc:
        unique_match(NODES, "URL", False, "dans l'arbre")
    assert "'F00002'" in str(exc.value) and "exact=True" in str(exc.value)


def test_split_path_et_format_candidates():
    assert split_path(" Favorites > URL - ABAP Samples ") == ["Favorites", "URL - ABAP Samples"]
    assert split_path("") == []
    text = format_candidates(NODES, limit=2)
    assert "'Favo' -> Favorites" in text and "6 nœuds en tout" in text


def test_la_cle_completee_a_gauche_est_rendue_telle_quelle():
    node = NODES[-1]
    assert node.key == "01  1      1"
    assert node.as_dict()["columns"]["TEXT"].startswith("SAP Customizing")


@pytest.mark.parametrize("text, expected", [
    ("SAP.TableTreeControl.1", True), ("SAPGUI.AbapEditor.1", True),
    ("SAPGUI.GridViewCtrl.1", True), ("T000", False), ("SAP SE", False),
    ("", False), (None, False), ("1.234.567,89", False),
])
def test_is_progid(text, expected):
    assert is_progid(text) is expected
