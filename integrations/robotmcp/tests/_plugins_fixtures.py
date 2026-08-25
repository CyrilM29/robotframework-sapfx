"""Doublures et helpers partages des tests des plugins rf-mcp (contrats, cartes, guidance, etats) (extraits, convention #13)."""
# ruff: noqa: F401  (surface re-exportee vers les fichiers de tests decoupes)
import asyncio


import pytest


robotmcp = pytest.importorskip("robotmcp", reason="rf-mcp non installé")


from robotmcp.plugins.contracts import LibraryStateProvider  # noqa: E402


from sap_robotmcp import SapApiPlugin, SapEccPlugin, SapFioriPlugin  # noqa: E402


import sap_robotmcp._rf_context as rf_context  # noqa: E402


import sap_robotmcp._staleness as staleness  # noqa: E402


import sap_robotmcp.fiori_plugin as fiori_plugin  # noqa: E402


ALL_PLUGINS = [SapEccPlugin, SapFioriPlugin, SapApiPlugin]


class _FakeSession:
    session_id = "session-1"
    variables = {}


def _patch_rf_context(monkeypatch, fake):
    """Substitue ``run_keyword_in_context`` là où il est RÉSOLU : dans
    ``_rf_context``, le seul module qui l'appelle.

    Les plugins ne l'importent plus : perception et sections d'état passent
    toutes par ``perception_text`` / ``structured_state``. Patcher le namespace
    d'un plugin ne doublait donc plus rien, et un test « best effort » pouvait
    rester vert parce que le VRAI appel échouait faute de contexte RF, pas
    parce que la doublure avait joué son rôle. Ce point de substitution unique
    est ce qui rend la doublure effective ; si un plugin réimportait le nom
    directement, ses tests échoueraient ici, ce qui est le signal voulu."""
    monkeypatch.setattr(rf_context, "run_keyword_in_context", fake)


def _routed_keywords_exist_in(cls, plugin_cls, extra_sources=()):
    """Chaque entrée de la carte de routage correspond à une méthode publique de la
    classe de bibliothèque (nom RF -> snake_case). C'est le test qui aurait attrapé
    la coquille historique « Fill Sid » (le vrai keyword est « Fill Sid Input »)."""
    methods = {name for src in (cls, *extra_sources) for name in dir(src)}
    for kw in plugin_cls().get_keyword_library_map():
        assert kw.replace(" ", "_") in methods, f"keyword routé inexistant: {kw!r}"


def _public_keywords(cls, base=None):
    """Surface publique appelable de ``cls``, moins celle de ``base``."""
    def public(target):
        return {name for name in dir(target)
                if not name.startswith("_")
                and callable(getattr(target, name, None))}
    return public(cls) - (public(base) if base is not None else set())


def _map_covers_the_library(cls, plugin_cls, base=None):
    """Sens INVERSE de `_routed_keywords_exist_in` : chaque keyword public de
    la bibliothèque doit être ROUTÉ.

    Le seul garde existant allait de la carte vers la bibliothèque, donc
    attrapait une coquille mais jamais un OUBLI, et c'est l'oubli qui coûte :
    six des dix keywords DDIC ont été ajoutés, dont pas
    `Reach Se16 Selection Screen`, celui qui ouvre un écran de sélection SE16
    en un seul endroit. Non routé, un agent ré-improvise le statut type E, la
    popup de choix des champs et le dialogue de génération : exactement les
    copies divergentes que ce keyword avait supprimées. `check_guidance_sync`
    ne pouvait rien voir, sa liste de marqueurs étant elle-même tenue à la
    main."""
    manquants = sorted(_public_keywords(cls, base)
                       - {kw.replace(" ", "_")
                          for kw in plugin_cls().get_keyword_library_map()})
    assert manquants == [], (
        "keywords publics de %s absents de la carte d'intention : %s"
        % (cls.__name__, manquants))


_UI5_MESSAGES = {
    "messages": [{"type": "Error", "message": "boom", "target": "",
                  "description": ""}],
    "toasts": [{"text": "Enregistré", "time": 1}],
}


def _fiori_state(monkeypatch, live, compteur=None):
    """Double le keyword d'état agrégé du canal web et rend l'état servi."""
    def fake(session, keyword_name, **kwargs):
        if compteur is not None:
            compteur.append(keyword_name)
        assert keyword_name == fiori_plugin.STATE_KEYWORD, (
            "l'état Fiori doit tenir en UN aller-retour de contexte RF, "
            "or %r a aussi été appelé" % keyword_name)
        if isinstance(live, Exception):
            raise live
        return live
    _patch_rf_context(monkeypatch, fake)
    return asyncio.run(SapFioriPlugin().get_state_provider()
                       .get_application_state(_FakeSession()))


_BASE_SIG_LINES = ["# screen SAPLMEGUI/ME21N/0015"] + [
    "  wnd[0]/usr/lbl%02d\tGuiLabel\ttexte stable" % i for i in range(12)]


_RENAMED_OLD = ("* wnd[0]/usr/subSUB:SAPLMEGUI:0013/ctxtMEPO-EBELN"
                "\tGuiCTextField\t4500000001")


_RENAMED_NEW = ("* wnd[0]/usr/subSUB:SAPLMEGUI:0015/ctxtMEPO-EBELN"
                "\tGuiCTextField\t4500000001")


def _patch_staleness(monkeypatch, message="code modifié, redémarrer rf-mcp"):
    """Force l'avertissement de code périmé. Il se pose désormais par
    ``attach_staleness``, qui résout la sonde dans ``_staleness`` : c'est le
    point unique, et le seul à doubler."""
    monkeypatch.setattr(staleness, "staleness_warning", lambda: message)
    return message


def _state_dispatch(values):
    """Doublure de run_keyword_in_context par keyword (Exception -> levée)."""
    def fake(session, keyword_name, **kwargs):
        result = values[keyword_name]
        if isinstance(result, Exception):
            raise result
        return result
    return fake
