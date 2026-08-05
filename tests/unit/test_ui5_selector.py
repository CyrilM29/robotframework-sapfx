"""Tests unitaires hors navigateur pour la logique de sélecteur UI5.

Ces tests valident la couche pure données/chaînes du côté Fiori (construction
et sérialisation des sélecteurs de contrôles UI5 ainsi que la forme du bundle JS
injecté) sans navigateur ni Playwright. La résolution en page elle-même est
exercée par la suite de fumée contre l'OpenUI5 Demo Kit
(voir docs/testing-without-sap.md).
"""
import json

import pytest

from SapFioriLibrary._ui5_js import (
    ALLOWED_PROPERTY_PRIORITY,
    BUNDLE,
    OBVIOUS_TEXT_PROPERTIES,
    READ_TABLE_JS,
    RESOLVE_ROLE_JS,
    RESOLVE_XPATH_JS,
    build_call,
)
from SapFioriLibrary._ui5_runtime import (
    build_control_selector,
    selector_to_json,
)


def test_build_selector_keeps_provided_keys():
    sel = build_control_selector(controlType="sap.m.Button", properties={"text": "Go"})
    assert sel == {"controlType": "sap.m.Button", "properties": {"text": "Go"}}


def test_build_selector_parses_dict_literal_string_properties():
    # Robot passe `properties={'text': 'Go'}` comme une CHAÎNE -> doit être parsée en dict.
    sel = build_control_selector(controlType="sap.m.Button",
                                 properties="{'text': 'Go'}")
    assert sel == {"controlType": "sap.m.Button", "properties": {"text": "Go"}}
    # idem bindingPath ; un vrai dict (appel Python) reste intact
    sel2 = build_control_selector(bindingPath="{'path': '/Orders'}")
    assert sel2 == {"bindingPath": {"path": "/Orders"}}
    sel3 = build_control_selector(properties={"text": "Go"})
    assert sel3 == {"properties": {"text": "Go"}}


def test_build_selector_rejects_non_dict_properties_string():
    with pytest.raises(ValueError, match="must be a dict"):
        build_control_selector(properties="'not a dict'")


def test_build_selector_drops_none_values():
    sel = build_control_selector(controlType="sap.m.Input", id=None)
    assert sel == {"controlType": "sap.m.Input"}


def test_build_selector_rejects_unknown_key():
    with pytest.raises(ValueError, match="Unknown UI5 selector key"):
        build_control_selector(contolType="typo")  # misspelled on purpose


def test_build_selector_rejects_empty():
    with pytest.raises(ValueError, match="Empty UI5 selector"):
        build_control_selector()


def test_selector_to_json_is_deterministic():
    a = build_control_selector(properties={"text": "X"}, controlType="sap.m.Button")
    b = build_control_selector(controlType="sap.m.Button", properties={"text": "X"})
    # Même sélecteur logique, ordre de kwargs différent -> sérialisation identique.
    assert selector_to_json(a) == selector_to_json(b)
    assert json.loads(selector_to_json(a)) == {
        "controlType": "sap.m.Button",
        "properties": {"text": "X"},
    }


def test_resolve_js_round_trips_the_selector_json():
    sel = build_control_selector(controlType="sap.m.Button", properties={"text": "Go"})
    payload = selector_to_json(sel)
    assert json.loads(payload) == sel


def test_bundle_call_starts_with_paren():
    # Playwright ne *peut pas appeler* un littéral de fonction qui commence par un espace.
    assert RESOLVE_ROLE_JS.startswith("(first, second) =>")
    assert RESOLVE_XPATH_JS.startswith("(first, second) =>")
    assert build_call("capture").startswith("(first, second) =>")


def test_bundle_installs_namespace_and_resolvers():
    assert "window.__SAPFX" in RESOLVE_ROLE_JS
    assert "resolveByRole" in RESOLVE_ROLE_JS
    assert "resolveByXPath" in RESOLVE_XPATH_JS
    # L'arbre de contrôles porté et le moteur XPath sont présents.
    assert "buildTree" in RESOLVE_XPATH_JS and "document.evaluate" in RESOLVE_XPATH_JS


def test_matchprops_uses_explicit_regex_form_not_loose_slash_check():
    # Régression : l'ancienne détection (w[0] === '/') classait à tort des valeurs
    # comme '/Orders' ou '/a/b' en regex. La forme stricte exige /motif/drapeaux.
    assert "function matchProps" in BUNDLE
    assert r"/^\/(.+)\/([a-z]*)$/" in BUNDLE      # détection regex explicite et bornée
    assert "w[0] === '/'" not in BUNDLE           # ancienne détection trop large retirée


def test_matchprops_bounds_pattern_and_haystack_length_against_redos():
    # Un `properties=/pattern/flags` forgé (agent MCP, test data-driven) pourrait
    # sinon bloquer le thread JS via backtracking catastrophique.
    assert "MATCH_PROPS_MAX_PATTERN_LENGTH" in BUNDLE
    assert "MATCH_PROPS_MAX_HAYSTACK_LENGTH" in BUNDLE
    assert "rx[1].length <= MATCH_PROPS_MAX_PATTERN_LENGTH" in BUNDLE
    assert ".slice(0, MATCH_PROPS_MAX_HAYSTACK_LENGTH)" in BUNDLE


def test_bundle_exposes_read_table_for_parity_with_ecc_grid():
    assert "function readTable" in BUNDLE and "getCells" in BUNDLE
    assert "readTable: readTable" in BUNDLE        # exporté sur __SAPFX
    assert READ_TABLE_JS.startswith("(first, second) =>") and "readTable" in READ_TABLE_JS


def test_property_priority_lists_are_sane():
    # Les propriétés textuelles viennent en premier et sont un sous-ensemble de la liste de priorité.
    assert ALLOWED_PROPERTY_PRIORITY[0] == "text"
    assert set(OBVIOUS_TEXT_PROPERTIES).issubset(set(ALLOWED_PROPERTY_PRIORITY))
    assert len(ALLOWED_PROPERTY_PRIORITY) == len(set(ALLOWED_PROPERTY_PRIORITY))  # pas de doublons
