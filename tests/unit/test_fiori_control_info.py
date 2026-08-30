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
from SapFioriLibrary._ui5_js import BUNDLE, CONTROL_INFO_JS


class FakeBrowser:
    def __init__(self, reponse):
        self.reponse = reponse
        self.charges = []

    def evaluate_javascript(self, selector, js, arg=None):
        if js == CONTROL_INFO_JS:
            self.charges.append(json.loads(arg))
            return self.reponse
        return None


def _lib(browser):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    return lib


_FICHE = {"id": "__item3", "type": "sap.m.StandardListItem",
          "rendered": True, "properties": {"title": "Apparence"},
          "binding": {"path": "/entries/2", "object": {"id": "themes"},
                      "object_keys": ["id", "name", "component"]}}


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


def test_le_bundle_expose_bien_la_fonction_appelee():
    """Contre-épreuve du câblage : le nom appelé côté Python doit exister dans
    le bundle JS livré, sinon l'erreur n'apparaîtrait qu'en live."""
    assert "controlInfo: controlInfo" in BUNDLE
    assert "window.__SAPFX.controlInfo(arg)" in CONTROL_INFO_JS
    # les deux distinctions du contrat vivent bien dans le JS livré
    assert "__no_aggregation" in BUNDLE
    assert "__out_of_range" in BUNDLE
