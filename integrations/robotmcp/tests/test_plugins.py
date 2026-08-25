"""Plugins rf-mcp : contrats, capacites, cartes de keywords, guidance, etats applicatifs API/Fiori. Doublures dans _plugins_fixtures (convention #13)."""
import asyncio
import pytest

from _plugins_fixtures import (  # noqa: F401
    ALL_PLUGINS,
    LibraryStateProvider,
    SapApiPlugin,
    SapEccPlugin,
    SapFioriPlugin,
    _FakeSession,
    _UI5_MESSAGES,
    _fiori_state,
    _map_covers_the_library,
    _patch_rf_context,
    _routed_keywords_exist_in,
)



@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_plugin_instancie_et_expose_metadata(cls):
    p = cls()
    md = p.get_metadata()
    assert md.name == md.import_path  # libs importables sous leur nom
    assert md.library_type == "external"
    assert "sap" in md.categories
    caps = p.get_capabilities()
    # le canal API n'a pas d'écran : page source honnêtement non supportée
    assert caps.supports_page_source is (cls is not SapApiPlugin)


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_capacite_application_state_conforme_a_ce_qui_est_implemente(cls):
    """Un provider qui SERT un état applicatif doit le DÉCLARER.

    Le plugin Fiori a vécu un temps avec un provider enrichi déclaré non
    supporté : tout consommateur qui respecte la capacité déclarée aurait sauté
    cet état sans le moindre signal, et la surcouche `sapfx_state` refuse
    désormais explicitement une section déclarée non servie.

    ``hasattr`` ne peut PAS répondre ici : ``LibraryStateProvider`` est un
    Protocol qui DÉCLARE ``get_application_state`` avec un corps ``...``, donc
    tout sous-classement l'hérite et le test dégénérait en tautologie (et
    aurait forcé un futur provider honnête, déclarant False, à mentir). La
    seule question qui a du sens : la méthode servie est-elle celle du
    provider, ou le stub du Protocol ?"""
    provider = cls().get_state_provider()
    implemented = (type(provider).get_application_state
                   is not LibraryStateProvider.get_application_state)
    assert cls().get_capabilities().supports_application_state is implemented


def test_le_garde_de_capacite_detecte_un_provider_qui_n_implemente_rien():
    """Contre-épreuve du garde ci-dessus : sans elle, rien ne prouve qu'il
    puisse échouer. Un provider qui hérite le stub du Protocol doit être vu
    comme NON implémenté, alors que ``hasattr`` le déclarait implémenté."""
    class _Nu(LibraryStateProvider):
        async def get_page_source(self, session, **kwargs):
            return None

    assert hasattr(_Nu(), "get_application_state") is True     # le piège
    assert (type(_Nu()).get_application_state
            is LibraryStateProvider.get_application_state)     # la réalité


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_le_contrat_best_effort_des_sections_detat_est_partage(cls, monkeypatch):
    """Le contrat best-effort (saut de thread, forme des erreurs) vit dans le
    module de contexte partagé, et les trois providers le suivent VRAIMENT.

    Vérification par le COMPORTEMENT, pas par le texte du source : la version
    précédente cherchait la sous-chaîne ``def _structured`` dans chaque module,
    donc ne voyait ni une copie renommée ni la copie INLINE qui survivait
    justement dans le plugin API. Ici, toute défaillance du contexte RF doit
    produire un état servi (jamais une exception), marqué non connecté et
    portant la cause : c'est cela, le contrat."""
    def boom(session, keyword_name, **kwargs):
        raise RuntimeError("%s indisponible" % keyword_name)
    _patch_rf_context(monkeypatch, boom)
    state = asyncio.run(cls().get_state_provider()
                        .get_application_state(_FakeSession()))
    assert state["connected"] is False, (
        "%s ne suit pas le contrat d'état partagé (connected)" % cls.__name__)
    assert "indisponible" in state["state_error"], (
        "%s ne remonte pas la cause réelle" % cls.__name__)


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_state_provider_a_la_bonne_interface(cls):
    import inspect

    sp = cls().get_state_provider()
    # LibraryStateProvider est un Protocol non runtime_checkable : on valide
    # l'interface structurellement (méthode async get_page_source).
    assert inspect.iscoroutinefunction(sp.get_page_source)
    params = inspect.signature(sp.get_page_source).parameters
    assert "session" in params


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_keyword_map_minuscule_et_route_vers_la_lib(cls):
    p = cls()
    kmap = p.get_keyword_library_map()
    assert kmap, "le mapping de keywords ne doit pas être vide"
    for kw, lib in kmap.items():
        assert kw == kw.lower(), f"clé non normalisée: {kw!r}"
        assert lib == p.get_metadata().name


def test_guidance_fiori_interdit_les_ids_dom():
    hints = SapFioriPlugin().get_hints()
    blob = " ".join(hints.error_hints).lower()
    # phrase précise (pas juste "ui5" et "dom" isolés, présents ailleurs sans rapport)
    assert "jamais des ids dom" in blob


def test_guidance_ecc_impose_le_type_de_message():
    hints = SapEccPlugin().get_hints()
    blob = " ".join(hints.error_hints).lower()
    # assertion locale-indépendante : type de message, pas texte localisé
    assert "type du message de barre d'état (e/s/w/i)" in blob
    assert "jamais le texte localisé" in blob


@pytest.mark.parametrize("cls", ALL_PLUGINS)
def test_prompt_bundle_present(cls):
    bundle = cls().get_prompt_bundle()
    assert bundle.recommendation and "SAP" in bundle.recommendation


def test_fiori_map_route_des_keywords_reels():
    SapFioriLibrary = pytest.importorskip(
        "SapFioriLibrary", reason="SapFioriLibrary non importable").SapFioriLibrary
    _routed_keywords_exist_in(SapFioriLibrary, SapFioriPlugin)
    _map_covers_the_library(SapFioriLibrary, SapFioriPlugin, base=object)


def test_ecc_map_route_des_keywords_reels():
    mod = pytest.importorskip(
        "SapEccLibrary", reason="SapEccLibrary non importable (pywin32 requis)")
    _routed_keywords_exist_in(mod.SapEccLibrary, SapEccPlugin)
    # Côté ECC, la carte couvre la valeur ajoutée du FORK : les centaines de
    # keywords hérités du code vendorisé passent par la découverte standard.
    base = pytest.importorskip(
        "SapEccLibrary._vendor.sapgui_base",
        reason="base vendorisée non importable").SapGuiBase
    _map_covers_the_library(mod.SapEccLibrary, SapEccPlugin, base=base)


def test_api_map_route_des_keywords_reels():
    SapApiLibrary = pytest.importorskip(
        "SapApiLibrary", reason="SapApiLibrary non importable").SapApiLibrary
    _routed_keywords_exist_in(SapApiLibrary, SapApiPlugin)
    _map_covers_the_library(SapApiLibrary, SapApiPlugin, base=object)


def test_api_page_source_explains_that_the_channel_has_no_screen():
    provider = SapApiPlugin().get_state_provider()
    result = asyncio.run(provider.get_page_source(_FakeSession()))
    assert result["success"] is False
    assert result["supported"] is False
    assert "n'a pas d'écran" in result["error"]
    assert "List Api Sessions" in result["error"]
    # Le MÊME motif alimente le refus porté par la capacité déclarée : la
    # surcouche n'a pas à réinventer une explication moins utile.
    assert provider.unsupported_reason("page_source") == result["error"]
    assert provider.unsupported_reason("application_state") is None


def test_api_application_state_serves_the_live_channel_state(monkeypatch):
    _patch_rf_context(monkeypatch,
                        lambda session, keyword_name, **kwargs: {
                            "api_sessions": [
                                {"alias": "default",
                                 "base_url": "http://vhcala4hci:50000",
                                 "sap_client": "001", "authenticated": True,
                                 "csrf_token_cached": False}],
                            "rfc_connections": []})
    provider = SapApiPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["active_library"] == "SapApiLibrary"
    assert state["connected"] is True
    assert state["api_sessions"][0]["alias"] == "default"
    assert state["api_sessions"][0]["authenticated"] is True
    assert state["rfc_connections"] == []


def test_api_application_state_degrades_with_the_reason(monkeypatch):
    def boom(session, keyword_name, **kwargs):
        raise RuntimeError("List Api Sessions indisponible")
    _patch_rf_context(monkeypatch, boom)
    provider = SapApiPlugin().get_state_provider()
    state = asyncio.run(provider.get_application_state(_FakeSession()))
    assert state["active_library"] == "SapApiLibrary"
    assert state["connected"] is False
    assert "indisponible" in state["state_error"]


def test_fiori_application_state_serves_frames_and_messages(monkeypatch):
    appels = []
    state = _fiori_state(monkeypatch, {
        "frame_stack": ["iframe[src*='app']"],
        "ui5_runtime": True,
        "messages": _UI5_MESSAGES,
    }, appels)
    assert state["active_library"] == "SapFioriLibrary"
    assert state["connected"] is True
    assert state["frame_stack"] == ["iframe[src*='app']"]
    assert state["ui5_runtime"] is True
    assert state["ui5_messages"] == _UI5_MESSAGES
    assert "collection_errors" not in state
    assert "not_applicable" not in state
    # UN aller-retour : la section est servie à chaque tour d'agent, et c'est
    # la traversée du contexte RF qui coûte, pas le JS.
    assert len(appels) == 1


def test_fiori_application_state_shows_the_real_message_shape(monkeypatch):
    """La section sert le dict de la bibliothèque TEL QUEL : c'est
    ``ui5_messages["messages"]`` qui porte les messages, et le type se lit
    là (convention n°3 : jamais le texte localisé)."""
    state = _fiori_state(monkeypatch, {"frame_stack": [], "ui5_runtime": True,
                                       "messages": _UI5_MESSAGES})
    assert state["ui5_messages"]["messages"][0]["type"] == "Error"
    assert state["ui5_messages"]["toasts"][0]["text"] == "Enregistré"


def test_fiori_sans_runtime_ui5_la_section_messages_est_sans_objet(monkeypatch):
    """Page UI5 Web Components, WebGUI ou zone non-SAP : cibles LÉGITIMES.

    `Get Ui5 Messages` y échoue durement, donc le lire sans condition faisait
    porter à ces sessions une erreur de collecte permanente, à chaque tour
    d'agent : le signal `collection_errors` doit rester rare pour rester lu."""
    state = _fiori_state(monkeypatch, {"frame_stack": [], "ui5_runtime": False})
    assert state["connected"] is True
    assert state["ui5_runtime"] is False
    assert "ui5_messages" not in state
    assert "collection_errors" not in state
    assert "pas de runtime UI5" in state["not_applicable"]["ui5_messages"]


def test_fiori_application_state_sections_degrade_best_effort(monkeypatch):
    # Runtime UI5 présent mais lecture des messages en échec : la section est
    # tracée, le reste de l'état est servi (jamais d'exception à travers MCP).
    state = _fiori_state(monkeypatch, {
        "frame_stack": ["<iframe>"], "ui5_runtime": True,
        "messages_error": "Pas de page ouverte"})
    assert state["connected"] is True
    assert state["frame_stack"] == ["<iframe>"]
    assert "ui5_messages" not in state
    assert state["collection_errors"]["ui5_messages"] == "Pas de page ouverte"


def test_fiori_application_state_forme_inattendue_est_dite(monkeypatch):
    """Une réponse qui n'est pas un dict ne doit pas être servie à moitié."""
    state = _fiori_state(monkeypatch, "OK")
    assert state["connected"] is False
    assert "forme inattendue" in state["state_error"]
