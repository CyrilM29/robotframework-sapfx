"""Tests hors navigateur de la fiche de contrôle (`Get Ui5 Control Info` /
`Get Ui5 Aggregation Info`).

La capacité promue (convention #12) : lire le TYPE plein d'un contrôle rendu,
son contexte de liaison (la clé d'un item à identifiant généré) et les
enfants d'une agrégation, rendus OU NON (les items d'un `Select` n'existent
pas dans le DOM popover fermé, donc invisibles au moteur role). Le JS réel
est exercé live ; ici le contrat Python (convention #5).
"""
import json

import pytest

from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import (BUNDLE, CONTROL_INFO_JS,
                                     CONTROL_METADATA_JS)


class FakeBrowser:
    def __init__(self, reponse, js_attendu=CONTROL_INFO_JS):
        self.reponse = reponse
        self.js_attendu = js_attendu
        self.charges = []

    def evaluate_javascript(self, selector, js, arg=None):
        if js == self.js_attendu:
            self.charges.append(json.loads(arg))
            return self.reponse
        return None


def _lib(browser):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    return lib


_FICHE = {"id": "__item3", "type": "sap.m.StandardListItem",
          "rendered": True, "properties": {"title": "Apparence"},
          "property_keys": ["fieldGroupIds", "title"],
          "binding": {"path": "/entries/2", "object": {"id": "themes"},
                      "object_keys": ["id", "name", "component"]}}

_INVENTAIRE = {"id": "__button1", "type": "sap.m.Button",
               "lineage": ["sap.m.Button", "sap.ui.core.Control"],
               "properties": {
                   "text": {"borrowed": False, "origin": "sap.m.Button",
                            "type": "string", "default": ""},
                   "fieldGroupIds": {"borrowed": True,
                                     "origin": "sap.ui.core.Control",
                                     "type": "string[]", "default": []}},
               "aggregations": {}, "associations": {}, "events": {}}


class TestControlInfo:
    def test_fiche_des_controles_matches(self):
        browser = FakeBrowser([_FICHE])
        fiches = _lib(browser).get_ui5_control_info(idSuffix="settingsList")
        assert fiches == [_FICHE]
        charge = browser.charges[0]
        assert charge["selector"]["idSuffix"] == "settingsList"
        assert "aggregation" not in charge

    def test_model_nomme_traverse_la_charge(self):
        browser = FakeBrowser([])
        _lib(browser).get_ui5_control_info(model="settings", id="x")
        assert browser.charges[0]["model"] == "settings"

    def test_sans_runtime_l_echec_nomme_la_sonde(self):
        with pytest.raises(AssertionError) as erreur:
            _lib(FakeBrowser(None)).get_ui5_control_info(id="x")
        assert "Ui5 Runtime Is Present" in str(erreur.value)

    def test_aucune_correspondance_rend_une_liste_vide(self):
        assert _lib(FakeBrowser([])).get_ui5_control_info(id="x") == []


class TestAggregationInfo:
    def test_enfants_d_agregation_rendus_ou_non(self):
        enfants = [dict(_FICHE), dict(_FICHE, rendered=False)]
        browser = FakeBrowser(enfants)
        items = _lib(browser).get_ui5_aggregation_info(
            "items", idSuffix="languageSelectionSelect")
        assert items == enfants
        charge = browser.charges[0]
        assert charge["aggregation"] == "items"
        assert charge["index"] == 0

    def test_selecteur_sans_correspondance_echoue(self):
        browser = FakeBrowser({"__out_of_range": 0})
        with pytest.raises(AssertionError, match="No UI5 control matched"):
            _lib(browser).get_ui5_aggregation_info("items", id="absent")

    def test_index_hors_bornes_echoue_en_le_disant(self):
        browser = FakeBrowser({"__out_of_range": 2})
        with pytest.raises(AssertionError, match="out of range"):
            _lib(browser).get_ui5_aggregation_info("items", index=5, id="x")

    def test_agregation_inconnue_echoue_en_la_nommant(self):
        browser = FakeBrowser({"__no_aggregation": "lignes"})
        with pytest.raises(AssertionError) as erreur:
            _lib(browser).get_ui5_aggregation_info("lignes", id="x")
        message = str(erreur.value)
        assert "lignes" in message
        assert "Get Ui5 Control Info" in message


class TestControlMetadata:
    """L'inventaire DÉCLARÉ (types, défauts, provenance borrowed), le
    complément de la fiche : c'est lui qui permet de confronter la doc d'API
    au contrôle vivant sans dépendre de la primitivité des valeurs
    (fieldGroupIds, tableau, invisible dans la fiche réduite)."""

    def test_inventaire_des_controles_matches(self):
        browser = FakeBrowser([_INVENTAIRE], js_attendu=CONTROL_METADATA_JS)
        inventaires = _lib(browser).get_ui5_control_metadata(
            controlType="Button")
        assert inventaires == [_INVENTAIRE]
        assert browser.charges[0]["selector"]["controlType"] == "Button"

    def test_sans_runtime_l_echec_nomme_la_sonde(self):
        browser = FakeBrowser(None, js_attendu=CONTROL_METADATA_JS)
        with pytest.raises(AssertionError) as erreur:
            _lib(browser).get_ui5_control_metadata(id="x")
        assert "Ui5 Runtime Is Present" in str(erreur.value)

    def test_aucune_correspondance_rend_une_liste_vide(self):
        browser = FakeBrowser([], js_attendu=CONTROL_METADATA_JS)
        assert _lib(browser).get_ui5_control_metadata(id="x") == []


def test_le_bundle_expose_bien_la_fonction_appelee():
    """Contre-épreuve du câblage : le nom appelé côté Python doit exister dans
    le bundle JS livré, sinon l'erreur n'apparaîtrait qu'en live."""
    assert "controlInfo: controlInfo" in BUNDLE
    assert "window.__SAPFX.controlInfo(arg)" in CONTROL_INFO_JS
    assert "controlMetadata: controlMetadata" in BUNDLE
    assert "window.__SAPFX.controlMetadata(arg)" in CONTROL_METADATA_JS
    # les deux distinctions du contrat vivent bien dans le JS livré
    assert "__no_aggregation" in BUNDLE
    assert "__out_of_range" in BUNDLE


def test_la_reduction_aux_primitives_est_annoncee():
    """La fiche ne peut plus omettre une propriété sans trace : la liste
    complète des clés lues (property_keys) accompagne les valeurs primitives,
    comme object_keys accompagne le contexte de liaison (relevé 2026-09-05 :
    fieldGroupIds, valeur tableau, disparaissait en silence)."""
    assert "info.property_keys = Object.keys(p).sort()" in BUNDLE


def test_une_valeur_tableau_franchit_la_frontiere_en_tableau():
    """Get Ui5 Property ne coerce plus un tableau en chaîne : String([])
    rendait '' (indiscernable d'une chaîne vide) et String(['a','b']) rendait
    'a,b' (structure perdue) ; jsonSafeValue garde les éléments primitifs."""
    assert "function jsonSafeValue(v)" in BUNDLE
    assert "out.values.push(jsonSafeValue(v))" in BUNDLE
    # l'ancienne coercition globale a bien disparu du lecteur de propriété
    assert "if (v !== null && typeof v === 'object') v = String(v);" not in BUNDLE
