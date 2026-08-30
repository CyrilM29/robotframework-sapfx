"""Tests hors navigateur des sondes d'état promues (convention #12) :
perception WebGUI (présence lsdata, menus), inventaire d'iframes, langues
servies, moteur UI5 inactif, et résumé de cookies sans valeur.

Toutes sont des lectures PURES (aucune injection du bundle) : le JS réel est
exercé par les suites live, ici le contrat Python (convention #5).
"""
import datetime

import pytest

from SapFioriLibrary.SapFioriLibrary import SapFioriLibrary
from SapFioriLibrary._ui5_js import (
    IFRAMES_PROBE_JS,
    PAGE_LANGUAGES_PROBE_JS,
    UI5_READY_PROBE_JS,
    UI5_THEME_PROBE_JS,
    WEBGUI_COUNT_PROBE_JS,
    WEBGUI_MENU_ITEMS_PROBE_JS,
    WEBGUI_MENUS_PROBE_JS,
)
from SapFioriLibrary._ui5_runtime import applied_theme


class FakeBrowser:
    def __init__(self, reponses=None, cookies=None):
        self.reponses = reponses or {}
        self.cookies = cookies or []
        self.appels = []

    def evaluate_javascript(self, selector, js, arg=None):
        self.appels.append((js, arg))
        valeur = self.reponses.get(js)
        if isinstance(valeur, Exception):
            raise valeur
        return valeur

    def get_cookies(self, kind):
        self.appels.append(("get_cookies", kind))
        return self.cookies


def _lib(browser):
    lib = SapFioriLibrary(ui5_timeout="2s")
    lib._browser = lambda: browser
    return lib


class TestWebgui:
    def test_presence_et_absence(self):
        assert _lib(FakeBrowser({WEBGUI_COUNT_PROBE_JS: 12})) \
            .webgui_is_present() is True
        assert _lib(FakeBrowser({WEBGUI_COUNT_PROBE_JS: 0})) \
            .webgui_is_present() is False

    def test_page_injoignable_repond_faux_sans_echec(self):
        browser = FakeBrowser({WEBGUI_COUNT_PROBE_JS: RuntimeError("closed")})
        assert _lib(browser).webgui_is_present() is False

    def test_comptage_global_et_par_fenetre(self):
        browser = FakeBrowser({WEBGUI_COUNT_PROBE_JS: 3})
        lib = _lib(browser)
        assert lib.get_webgui_element_count() == 3
        assert browser.appels[-1][1] is None
        assert lib.get_webgui_element_count(window=1) == 3
        assert browser.appels[-1][1] == "1"

    def test_menus_et_items(self):
        menus = ["wnd[0]/mbar/menu[6]-BtnChoiceMenu"]
        items = ["wnd[0]/mbar/menu[6]/menu[13]"]
        browser = FakeBrowser({WEBGUI_MENUS_PROBE_JS: menus,
                               WEBGUI_MENU_ITEMS_PROBE_JS: items})
        lib = _lib(browser)
        assert lib.list_webgui_menus() == menus
        assert browser.appels[-1][1] == "0"
        assert lib.list_webgui_menu_items(menus[0]) == items
        assert browser.appels[-1][1] == menus[0]

    def test_le_savoir_du_canal_vit_dans_la_sonde(self):
        """Suffixe de rendu et items DIRECTS (aucun `/` après le préfixe) :
        le savoir WebGUI relevé live doit vivre dans le JS de la
        bibliothèque, plus dans un page object."""
        assert "-BtnChoiceMenu" in WEBGUI_MENUS_PROBE_JS
        assert "offsetParent" in WEBGUI_MENUS_PROBE_JS
        assert "indexOf('/')" in WEBGUI_MENU_ITEMS_PROBE_JS
        assert "lsdata" in WEBGUI_COUNT_PROBE_JS


class TestIframesEtLangues:
    def test_inventaire_des_iframes(self):
        frames = [{"id": "__container4", "src": "https://x.example/app?y=1"}]
        assert _lib(FakeBrowser({IFRAMES_PROBE_JS: frames})) \
            .list_page_iframes() == frames

    def test_reponse_non_liste_rend_une_liste_vide(self):
        assert _lib(FakeBrowser({IFRAMES_PROBE_JS: None})) \
            .list_page_iframes() == []

    def test_langues_servies(self):
        langues = {"document": "fr", "navigator": "fr-FR"}
        assert _lib(FakeBrowser({PAGE_LANGUAGES_PROBE_JS: langues})) \
            .get_page_languages() == langues

    def test_langues_illisibles_rendent_des_champs_vides(self):
        assert _lib(FakeBrowser({PAGE_LANGUAGES_PROBE_JS: None})) \
            .get_page_languages() == {"document": "", "navigator": ""}


class TestMoteurInactif:
    def test_pret_et_pas_pret(self):
        assert _lib(FakeBrowser({UI5_READY_PROBE_JS: True})) \
            .ui5_runtime_is_ready() is True
        assert _lib(FakeBrowser({UI5_READY_PROBE_JS: False})) \
            .ui5_runtime_is_ready() is False
        assert _lib(FakeBrowser({UI5_READY_PROBE_JS: RuntimeError("x")})) \
            .ui5_runtime_is_ready() is False

    def test_l_assertion_nomme_les_causes(self):
        with pytest.raises(AssertionError) as erreur:
            _lib(FakeBrowser({UI5_READY_PROBE_JS: False})) \
                .ui5_runtime_should_be_ready()
        assert "Get Page Composition" in str(erreur.value)

    def test_le_predicat_couvre_les_trois_marches(self):
        """Runtime présent (Core OU module Element), pas de mise à jour en
        attente, pas d'indicateur d'occupation : le prédicat historique de
        `Wait For UI5 Ready`, promu tel quel."""
        assert "getUIDirty" in UI5_READY_PROBE_JS
        assert "sap/ui/core/Element" in UI5_READY_PROBE_JS
        assert "sapUiLocalBusyIndicator" in UI5_READY_PROBE_JS


class TestResumeDeCookies:
    def test_la_sentinelle_1969_ne_passe_pas_pour_une_expiration(self):
        cookies = [
            {"name": "session", "domain": "x.example", "value": "SECRET",
             "expires": datetime.datetime(1969, 12, 31, 23, 59, 59)},
            {"name": "durable", "domain": "x.example", "value": "AUTRE",
             "expires": datetime.datetime(2999, 1, 1)},
        ]
        resume = _lib(FakeBrowser(cookies=cookies)).get_session_cookie_summary()
        par_nom = {c["name"]: c for c in resume}
        assert par_nom["session"]["future_expiration"] is False
        assert par_nom["durable"]["future_expiration"] is True

    def test_aucune_valeur_de_cookie_ne_sort(self):
        cookies = [{"name": "sid", "domain": "x", "value": "JETON-SECRET"}]
        resume = _lib(FakeBrowser(cookies=cookies)).get_session_cookie_summary()
        assert "JETON-SECRET" not in str(resume)
        assert sorted(resume[0]) == ["domain", "future_expiration", "name"]


class TestTheme:
    def test_les_deux_valeurs_sont_rendues(self):
        sonde = {"requested": "sap_horizon_dark",
                 "classes": "sapUiBody sapUiTheme-sap_horizon_dark sapUiSizeCozy"}
        assert _lib(FakeBrowser({UI5_THEME_PROBE_JS: sonde})).get_ui5_theme() == {
            "requested": "sap_horizon_dark", "applied": "sap_horizon_dark"}

    def test_la_fenetre_transitoire_sans_classe_de_theme_est_lisible(self):
        # Mesuré live : juste après le clic, <html> ne porte plus AUCUNE classe
        # sapUiTheme-*, alors que le thème demandé porte déjà la cible. Rendre
        # les deux valeurs est ce qui permet à l'appelant d'attendre au lieu de
        # conclure sur une lecture unique.
        sonde = {"requested": "sap_horizon_dark", "classes": "sapUiBody sapUiSizeCozy"}
        etat = _lib(FakeBrowser({UI5_THEME_PROBE_JS: sonde})).get_ui5_theme()
        assert etat == {"requested": "sap_horizon_dark", "applied": ""}

    def test_page_sans_runtime_ne_fait_pas_echouer_la_lecture(self):
        assert _lib(FakeBrowser({UI5_THEME_PROBE_JS: None})).get_ui5_theme() == {
            "requested": "", "applied": ""}

    def test_la_sonde_lit_le_module_theming_et_replie_sur_le_core_herite(self):
        # UI5 2.x supprime sap.ui.getCore() : la voie actuelle est le module,
        # le Core hérité n'est que le repli.
        assert "sap/ui/core/Theming" in UI5_THEME_PROBE_JS
        assert "getConfiguration" in UI5_THEME_PROBE_JS

    @pytest.mark.parametrize("classes, attendu", [
        ("sapUiTheme-sap_fiori_3", "sap_fiori_3"),
        ("a sapUiTheme-sap_horizon b", "sap_horizon"),
        ("sapUiBody", ""),
        ("sapUiTheme-", ""),          # jeton nu : pas un nom de thème
        (None, ""),
    ])
    def test_extraction_du_theme_applique(self, classes, attendu):
        assert applied_theme(classes) == attendu
