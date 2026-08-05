"""Tests off-SAP de ``sapfx_common.object_tree`` (convention #5 du CLAUDE.md).

Aplatissement du JSON de ``GuiSession.GetObjectTree`` : forme récursive
``properties``/``children``, nœud enveloppe, nombres en chaînes (comportement
observé de l'API ; RoboSAPiens active ``AllowReadingFromString`` pour la même
raison), ``Changeable`` en ``"true"``/``"false"``, entrées malformées.
"""
import pytest

from sapfx_common.object_tree import ScreenElement, flatten_object_tree


def _node(props, children=()):
    return {"properties": props, "children": list(children)}


def test_flatten_parcourt_en_profondeur_dans_l_ordre_du_document():
    tree = _node(
        {"Id": "/app/con[0]/ses[0]/wnd[0]", "Type": "GuiMainWindow"},
        [
            _node({"Id": "/app/con[0]/ses[0]/wnd[0]/usr", "Type": "GuiUserArea"},
                  [_node({"Id": "/app/con[0]/ses[0]/wnd[0]/usr/txtA", "Type": "GuiTextField"})]),
            _node({"Id": "/app/con[0]/ses[0]/wnd[0]/tbar[0]", "Type": "GuiToolbar"}),
        ],
    )
    ids = [el.id for el in flatten_object_tree(tree)]
    assert ids == [
        "/app/con[0]/ses[0]/wnd[0]",
        "/app/con[0]/ses[0]/wnd[0]/usr",
        "/app/con[0]/ses[0]/wnd[0]/usr/txtA",
        "/app/con[0]/ses[0]/wnd[0]/tbar[0]",
    ]


def test_flatten_accepte_le_json_en_chaine_et_le_noeud_enveloppe():
    # GetObjectTree coiffe le sous-arbre demandé d'un nœud enveloppe sans
    # propriétés : il doit être traversé sans produire d'élément.
    import json
    wrapper = {"children": [_node({"Id": "wnd[0]", "Type": "GuiMainWindow"})]}
    elements = flatten_object_tree(json.dumps(wrapper))
    assert [el.id for el in elements] == ["wnd[0]"]


def test_flatten_normalise_nombres_en_chaines_et_changeable_texte():
    tree = _node({
        "Id": "wnd[0]/usr/txtA", "Type": "GuiTextField", "Text": "42",
        "Changeable": "true", "ScreenLeft": "10", "ScreenTop": "20",
        "Width": "110", "Height": "22",
    })
    el = flatten_object_tree(tree)[0]
    assert el.changeable is True
    assert (el.left, el.top, el.width, el.height) == (10, 20, 110, 22)
    assert el.right == 120 and el.bottom == 42


def test_flatten_prefere_screenleft_mais_replie_sur_left():
    avec_screen = flatten_object_tree(_node(
        {"Id": "a", "ScreenLeft": 100, "Left": 5, "ScreenTop": 200, "Top": 7}))[0]
    sans_screen = flatten_object_tree(_node({"Id": "b", "Left": 5, "Top": 7}))[0]
    assert (avec_screen.left, avec_screen.top) == (100, 200)
    assert (sans_screen.left, sans_screen.top) == (5, 7)


def test_flatten_cles_insensibles_a_la_casse_et_proprietes_au_niveau_du_noeud():
    # variante défensive : propriétés directement sur le nœud, casse différente
    tree = {"id": "wnd[0]/usr/btnGO", "type": "GuiButton",
            "children": [{"id": "wnd[0]/usr/btnGO/x"}]}
    elements = flatten_object_tree(tree)
    assert elements[0] == ScreenElement(id="wnd[0]/usr/btnGO", type="GuiButton")
    assert elements[1].id == "wnd[0]/usr/btnGO/x"


def test_flatten_ignore_noeuds_sans_id_et_enfants_non_dict():
    tree = _node({"Type": "GuiWrapper"},                 # pas d'Id -> traversé
                 [_node({"Id": "ok"}), "bruit", None])   # entrées non-dict ignorées
    assert [el.id for el in flatten_object_tree(tree)] == ["ok"]


def test_flatten_geometrie_absente_donne_none_et_right_bottom_none():
    el = flatten_object_tree(_node({"Id": "wnd[0]", "Width": 800}))[0]
    assert el.left is None and el.top is None
    assert el.right is None and el.bottom is None


def test_flatten_leve_valueerror_sur_json_invalide():
    with pytest.raises(ValueError):
        flatten_object_tree("pas du json {")
    with pytest.raises(ValueError):
        flatten_object_tree("[1, 2, 3]")   # JSON valide mais pas un objet
