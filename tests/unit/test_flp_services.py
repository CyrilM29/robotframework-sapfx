"""Tests hors navigateur des services launchpad promus (convention #12).

Ces keywords vivaient en JS inline, en DOUBLE, dans deux page objects
(`abap_flp` et `workzone_*`) : promus dans `SapFioriLibrary` (mixin
`_flp_services.py`), ils se testent ici avec une doublure de Browser
(convention #5). La partie ushell réelle est exercée par les campagnes live.
"""
import json

import pytest

from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import (
    FLP_APPS_PROBE_JS,
    FLP_CATALOGS_PROBE_JS,
    FLP_CONTAINER_PROBE_JS,
    FLP_GROUPS_PROBE_JS,
    FLP_INTENT_SUPPORT_PROBE_JS,
    FLP_SERVICE_PROBE_JS,
    FLP_USER_PROBE_JS,
)


class FakeBrowser:
    """Sert une réponse cannée par sonde et mémorise ce qui part au JS."""

    def __init__(self, reponses):
        self.reponses = reponses
        self.appels = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.appels.append((js, arg))
        if js in self.reponses:
            valeur = self.reponses[js]
            if isinstance(valeur, Exception):
                raise valeur
            return valeur
        return None

    def get_url(self):
        raise AssertionError(
            "get_url ne doit pas être sollicité pour décomposer une adresse "
            "fournie via url=.")


def _lib(browser):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    return lib


class TestPredicats:
    def test_conteneur_present(self):
        assert _lib(FakeBrowser({FLP_CONTAINER_PROBE_JS: True})) \
            .flp_container_is_present() is True

    def test_conteneur_absent_ou_page_injoignable(self):
        assert _lib(FakeBrowser({FLP_CONTAINER_PROBE_JS: False})) \
            .flp_container_is_present() is False
        assert _lib(FakeBrowser({FLP_CONTAINER_PROBE_JS: RuntimeError("x")})) \
            .flp_container_is_present() is False

    def test_l_assertion_echoue_en_nommant_la_portee(self):
        with pytest.raises(AssertionError) as erreur:
            _lib(FakeBrowser({FLP_CONTAINER_PROBE_JS: False})) \
                .flp_container_should_be_present()
        assert "Get Ui5 Frame Stack" in str(erreur.value)

    def test_service_disponible_et_indisponible(self):
        browser = FakeBrowser({FLP_SERVICE_PROBE_JS: True})
        lib = _lib(browser)
        assert lib.flp_service_is_available("SearchableContent") is True
        assert browser.appels[0][1] == "SearchableContent"
        assert _lib(FakeBrowser({FLP_SERVICE_PROBE_JS: RuntimeError("x")})) \
            .flp_service_is_available("LaunchPage") is False


class TestLectures:
    def test_identite_utilisateur(self):
        reponse = {"id": "GUID", "language": "fr", "theme": "sap_horizon"}
        assert _lib(FakeBrowser({FLP_USER_PROBE_JS: reponse})) \
            .get_flp_user() == reponse

    def test_conteneur_absent_echoue_en_nommant_le_remede(self):
        browser = FakeBrowser({FLP_USER_PROBE_JS: {"__no_container": True}})
        with pytest.raises(AssertionError) as erreur:
            _lib(browser).get_flp_user()
        message = str(erreur.value)
        assert "sap.ushell.Container" in message
        assert "Pop Ui5 Frame" in message

    def test_inventaire_des_applications(self):
        apps = [{"title": "T", "viz_title": "V", "intent": "So-act",
                 "target_url": "#So-act?x=1"}]
        assert _lib(FakeBrowser({FLP_APPS_PROBE_JS: apps})) \
            .list_flp_apps() == apps

    def test_service_absent_echoue_en_nommant_le_predicat(self):
        """SearchableContent absent (ushell 1.71 : module 404) : l'échec doit
        envoyer vers la sonde de branchement, pas accuser la page."""
        browser = FakeBrowser({FLP_APPS_PROBE_JS: {"__no_service": "404"}})
        with pytest.raises(AssertionError) as erreur:
            _lib(browser).list_flp_apps()
        message = str(erreur.value)
        assert "SearchableContent" in message
        assert "Flp Service Is Available" in message

    def test_catalogues_avec_et_sans_tuiles(self):
        cats = [{"id": "CAT", "tiles": []}]
        browser = FakeBrowser({FLP_CATALOGS_PROBE_JS: cats})
        lib = _lib(browser)
        assert lib.list_flp_catalogs() == cats
        assert browser.appels[-1][1] == "tiles"
        lib.list_flp_catalogs(include_tiles=False)
        assert browser.appels[-1][1] == "no_tiles"
        # la frontière rf-mcp livre les booléens en chaîne
        lib.list_flp_catalogs(include_tiles="False")
        assert browser.appels[-1][1] == "no_tiles"

    def test_groupes(self):
        groupes = [{"id": "G1", "tile_count": 7}]
        assert _lib(FakeBrowser({FLP_GROUPS_PROBE_JS: groupes})) \
            .list_flp_groups() == groupes

    def test_resolvabilite_par_lot_et_frontiere_chaine(self):
        verdicts = [{"intent": "A-b", "supported": True}]
        browser = FakeBrowser({FLP_INTENT_SUPPORT_PROBE_JS: verdicts})
        lib = _lib(browser)
        assert lib.get_flp_intent_support(["A-b", "C-d"]) == verdicts
        assert json.loads(browser.appels[0][1]) == ["A-b", "C-d"]
        # une chaîne à virgules (frontière execute_step) passe aussi
        lib.get_flp_intent_support("A-b,C-d")
        assert json.loads(browser.appels[-1][1]) == ["A-b", "C-d"]


class TestGetPageLocationUrl:
    """L'extension url=/base= : décomposer une adresse SANS toucher la page
    (le remplacement des `Evaluate __import__` de la couche Robot)."""

    def test_url_fournie_decomposee_sans_navigateur(self):
        ou = _lib(FakeBrowser({})).get_page_location(
            url="https://site.example/flp#Shell-home")
        assert ou["host"] == "site.example"
        assert ou["intent"] == "Shell-home"

    def test_base_resout_une_adresse_relative(self):
        ou = _lib(FakeBrowser({})).get_page_location(
            url="/sap/keepalive", base="https://site.example/flp")
        assert ou["host"] == "site.example"
        assert ou["path"] == "/sap/keepalive"

    def test_base_sans_url_est_refusee(self):
        with pytest.raises(ValueError, match="base= sans url="):
            _lib(FakeBrowser({})).get_page_location(base="https://x.example")
