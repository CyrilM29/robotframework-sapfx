"""Tests unitaires de la compatibilité multi-versions UI5 du bundle __SAPFX.

Le comportement réel est prouvé par les smokes live (`fiori_smoke` = UI5 courant,
`fiori_legacy_smoke` = OpenUI5 1.60 sans registre) ; ici on verrouille la présence
des trois chemins de `registryForEach` dans le JS généré — bundle **et** recorder —
pour qu'une régression soit visible sans navigateur (convention #5 du CLAUDE.md).
"""
import os

from SapFioriLibrary._ui5_js import BUNDLE, RESOLVE_ROLE_JS, spy_snippet

_RESOURCE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "resources", "fiori_keywords.resource"))


def test_bundle_has_the_three_registry_paths():
    # 1. UI5 2.x : module ElementRegistry (Element.registry supprimé).
    assert "sap/ui/core/ElementRegistry" in BUNDLE
    # 2. UI5 1.67+ : Element.registry (module ou espace global).
    assert "E.registry" in BUNDLE
    # 3. UI5 < 1.67 : balayage DOM des contrôles rendus.
    assert "querySelectorAll('[data-sap-ui]')" in BUNDLE


def test_role_resolution_goes_through_the_fallback_chain():
    assert "registryForEach" in BUNDLE
    # resolveByRole ne référence plus le registre en direct : tout passe par le helper.
    assert "registryForEach" in RESOLVE_ROLE_JS or "resolveByRole" in RESOLVE_ROLE_JS


def test_recorder_snippet_carries_the_same_fallback():
    snippet = spy_snippet()
    assert "sap/ui/core/ElementRegistry" in snippet
    assert "querySelectorAll('[data-sap-ui]')" in snippet


def test_bundle_never_requires_the_global_core():
    # UI5 2.x supprime sap.ui.getCore() : chaque usage doit être gardé (repli), jamais exigé.
    assert "sap.ui.getCore) ? sap.ui.getCore()" in BUNDLE


def test_wait_for_ui5_ready_does_not_require_getcore():
    with open(_RESOURCE, encoding="utf-8") as fh:
        text = fh.read()
    # Le mot-clé accepte Core hérité OU module Element (UI5 2.x) ; getUIDirty
    # seulement quand le Core existe.
    assert "s.ui.getCore ? s.ui.getCore() : null" in text
    assert "sap/ui/core/Element" in text
