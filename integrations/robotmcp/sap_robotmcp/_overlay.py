"""Logique des outils de la surcouche ``sapfx-mcp``, testable off-SAP.

Le montage FastMCP (décorateurs, contenu image, point d'entrée) vit dans
:mod:`sap_robotmcp.server` ; ici, les fonctions reçoivent leurs dépendances en
paramètres (moteur d'exécution rf-mcp, manager de plugins, exécuteur de
keyword) et se testent avec des doublures, sans serveur ni SAP.

Les trois outils comblent, côté surcouche, les manques du contrat plugin
rf-mcp 0.31 constatés live le 2026-07-23 (field notes CLAUDE.md) :

- ``sapfx_state`` : appelle NOS state providers directement, avec ``page_source``
  avec la vraie sémantique ``full_source`` (le mode diff s'exerce par défaut),
  ``application_state`` enrichi (``modal_open``…, jamais routé par rf-mcp) ;
- ``sapfx_screenshot`` : le canal VISION (le contrat plugin n'a pas de canal
  image ; fastmcp si) : écran brut ou annoté Set-of-Mark avec sa légende ;
- ``sapfx_reload`` : le protocole de hot-reload de la couche plugin validé
  live (reload modules → reset du manager → ré-enregistrement), encodé au
  lieu d'être une séquence d'Evaluate à rejouer à la main.
"""
from __future__ import annotations

import base64
import importlib
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional

from ._rf_context import run_keyword_in_context
from ._staleness import staleness_warning

# Bibliothèques SAPFX dont les providers sont servis par la surcouche.
SAPFX_LIBRARIES = ("SapEccLibrary", "SapFioriLibrary", "SapApiLibrary")

# Sections d'état servies par sapfx_state.
STATE_SECTIONS = ("page_source", "application_state")

# Sous-modules du paquet rechargés par sapfx_reload, dans l'ordre des
# dépendances. La surcouche elle-même (server/_overlay/_compat) est EXCLUE :
# les outils enregistrés référencent les fonctions déjà montées, la recharger
# ne les remplacerait pas (redémarrer pour ça).
RELOAD_ORDER = ("_last_seen", "_filtering", "_guidance", "_staleness",
                "_rf_context", "ecc_plugin", "fiori_plugin", "api_plugin")


def _error(message: str, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"success": False, "error": message}
    payload.update(extra)
    return payload


def resolve_session(execution_engine: Any, session_id: str) -> Optional[Any]:
    """Session rf-mcp par id via l'accesseur public du moteur (``None`` si
    introuvable/illisible, jamais d'exception)."""
    try:
        return execution_engine.get_session(session_id)
    except Exception:
        return None


def pick_library(session: Any, library: str = "") -> Any:
    """Choisit la bibliothèque SAPFX dont le provider servira l'état.

    ``library`` explicite gagne (validée) ; sinon la seule bibliothèque SAPFX
    importée dans la session. Deux bibliothèques SAPFX importées = ambiguïté
    remontée (jamais de premier-match silencieux, règle maison). Retourne le
    nom, ou un dict d'erreur actionnable."""
    if library:
        if library not in SAPFX_LIBRARIES:
            return _error(
                "library %r inconnue ; valides : %s"
                % (library, ", ".join(SAPFX_LIBRARIES)))
        return library
    imported = set(getattr(session, "imported_libraries", []) or [])
    imported |= set(getattr(session, "loaded_libraries", []) or [])
    present = [lib for lib in SAPFX_LIBRARIES if lib in imported]
    if not present:
        return _error(
            "aucune bibliothèque SAPFX dans cette session (importées : %s) ; "
            "manage_session init avec SapEccLibrary ou SapFioriLibrary d'abord."
            % (sorted(imported) or "aucune"))
    if len(present) > 1:
        return _error(
            "session hybride (%s) : préciser library=... pour choisir le "
            "provider." % ", ".join(present))
    return present[0]


async def collect_state(execution_engine: Any, plugin_manager: Any,
                        session_id: str,
                        sections: Optional[Iterable[str]] = None,
                        full_source: bool = False,
                        filtered: bool = False,
                        filtering_level: str = "standard",
                        library: str = "") -> Dict[str, Any]:
    """Assemble l'état SAP d'une session en appelant les state providers SAPFX
    directement : les sections que rf-mcp 0.31 ne route pas (ou mal)."""
    session = resolve_session(execution_engine, session_id)
    if session is None:
        return _error("session rf-mcp introuvable : %r" % session_id)
    picked = pick_library(session, library)
    if isinstance(picked, dict):
        return picked
    provider = plugin_manager.get_state_provider(picked)
    if provider is None:
        return _error(
            "aucun state provider pour %s ; plugins SAP non enregistrés ? "
            "(sapfx_reload peut ré-enregistrer)" % picked)

    wanted = [str(s) for s in (sections or STATE_SECTIONS)]
    unknown = [s for s in wanted if s not in STATE_SECTIONS]
    result: Dict[str, Any] = {
        "success": True,
        "session_id": session_id,
        "library": picked,
        "sections": {},
    }
    if unknown:
        result["unknown_sections"] = unknown
    if "page_source" in wanted:
        try:
            result["sections"]["page_source"] = await provider.get_page_source(
                session, full_source=full_source, filtered=filtered,
                filtering_level=filtering_level)
        except Exception as exc:
            result["sections"]["page_source"] = _error(str(exc))
    if "application_state" in wanted:
        try:
            result["sections"]["application_state"] = (
                await provider.get_application_state(session))
        except Exception as exc:
            result["sections"]["application_state"] = _error(str(exc))
    warning = staleness_warning()
    if warning:
        result["stale_code_warning"] = warning
    return result


# --- screenshot (canal vision) ------------------------------------------------

_MIME_FORMATS = {"image/png": "png", "image/jpeg": "jpeg",
                 "image/bmp": "bmp", "image/gif": "gif"}


def take_screenshot_payload(session: Any, annotated: bool = False,
                            include_types: str = "",
                            runner: Callable[..., Any] = run_keyword_in_context,
                            ) -> Dict[str, Any]:
    """Capture l'écran SAP de la session : ``{success, data(bytes), format,
    legend|None}``. Bloquant (contexte RF) : l'appelant async passe par
    ``asyncio.to_thread``.

    ``annotated=True`` = screenshot Set-of-Mark (boîtes numérotées) + légende
    ``numéro -> id``, canal ECC (le keyword d'annotation vit dans
    SapEccLibrary) ; ``include_types`` restreint l'annotation (ex.
    ``GuiShell,GuiCustomControl``). En capture BRUTE, une session Fiori est
    couverte par le repli Browser (``Take Screenshot ... return_as=base64``) :
    la conversion d'arguments RF passe par le contexte natif, donc l'enum
    ``return_as`` est convertie correctement (leçon `_wait_visible`)."""
    try:
        if annotated:
            args = [include_types] if include_types else None
            shot = runner(session, "Get Annotated Screenshot",
                          arguments=args, allow_structured=True)
            if not isinstance(shot, dict) or "image" not in shot:
                return _error(
                    "Get Annotated Screenshot a retourné une forme inattendue "
                    ": %r" % type(shot).__name__)
            data = base64.b64decode(shot["image"])
            mime = str(shot.get("mime") or "image/png")
            legend = shot.get("legend") or {}
        else:
            try:
                b64 = runner(session, "Get Screenshot As Base64")
            except Exception:
                # Session Fiori/web : pas de keyword ECC, repli Browser.
                b64 = runner(session, "Take Screenshot",
                             arguments=["EMBED", "return_as=base64"])
            data = base64.b64decode(b64)
            mime = "image/png"
            legend = None
    except Exception as exc:
        return _error(str(exc))
    return {
        "success": True,
        "data": data,
        "format": _MIME_FORMATS.get(mime, "png"),
        "legend": legend,
    }


# --- hot-reload de la couche plugin ------------------------------------------

def reload_plugin_layer(manager_module: Any = None,
                        package: str = "sap_robotmcp") -> Dict[str, Any]:
    """Recharge la couche plugin SAPFX dans le process serveur SANS
    redémarrage : ``importlib.reload`` des sous-modules (ordre des
    dépendances), reset du manager singleton rf-mcp, puis ré-enregistrement
    des plugins entry-point. Protocole validé live le 2026-07-23 : le tool
    rf-mcp ``manage_library_plugins reload`` seul ne suffit pas (instances en
    cache)."""
    try:
        if manager_module is None:
            manager_module = importlib.import_module("robotmcp.plugins.manager")
        reloaded: List[str] = []
        for suffix in RELOAD_ORDER:
            name = "%s.%s" % (package, suffix)
            module = sys.modules.get(name)
            if module is not None:
                importlib.reload(module)
                reloaded.append(name)
        root = sys.modules.get(package)
        if root is not None:
            importlib.reload(root)
            reloaded.append(package)

        manager_module.reset_library_plugin_manager_for_tests()
        manager = manager_module.get_library_plugin_manager()
        registered: List[str] = []
        for plugin in manager_module.iter_entry_point_plugins():
            manager.register_plugin(plugin)
            try:
                registered.append(plugin.get_metadata().name)
            except Exception:
                registered.append(type(plugin).__name__)
    except Exception as exc:
        return _error(str(exc))
    return {
        "success": True,
        "reloaded_modules": reloaded,
        "registered_plugins": registered,
        "library_layer_note": (
            "Seule la couche PLUGIN est rechargée. Une bibliothèque "
            "(SapEccLibrary/SapFioriLibrary) modifiée sur disque exige le "
            "hot-swap en contexte RF (importlib.reload + instance.__class__ + "
            "Reload Library ; field notes CLAUDE.md) ou un redémarrage du "
            "serveur ; les state providers le signalent via "
            "stale_code_warning."),
    }
