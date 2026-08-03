"""Petit utilitaire : exécuter un keyword de perception dans le contexte RF live.

C'est le pattern qu'emploie rf-mcp lui-même (cf. PageSourceService
._get_page_source_via_rf_context) pour atteindre l'instance de bibliothèque
vivante sans y accéder directement : on demande au gestionnaire de contexte RF
natif d'exécuter un keyword côté session et on récupère sa sortie.
"""
from __future__ import annotations

import logging

from sapfx_common.com_safety import ensure_com_initialized

logger = logging.getLogger(__name__)


def run_keyword_in_context(session, keyword_name: str, *,
                           arguments=None,
                           allow_structured: bool = False):
    """Exécute ``keyword_name`` dans le contexte RF de ``session`` et retourne
    sa sortie texte. ``arguments`` : arguments positionnels optionnels du
    keyword (chaînes, comme en Robot).

    ``allow_structured=True`` accepte aussi une valeur de retour structurée
    (dict/list/tuple JSON-safe — jamais un objet COM, cf. field notes MCP × COM)
    au lieu d'exiger du texte : le canal des keywords d'état applicatif
    (``Get Open Windows``, ``Get Session Telemetry``…).

    Lève ``RuntimeError`` (message explicite) si le gestionnaire de contexte RF
    est indisponible, si le keyword échoue côté RF, ou si sa sortie est vide —
    les appelants (state providers) sont responsables de convertir cette
    exception en réponse ``{"success": False, "error": ...}`` afin que la vraie
    cause reste visible côté agent, plutôt qu'un "keyword absent ?" générique.

    Bloquant (entre dans _suppress_stdout côté rf-mcp) : les appelants async
    doivent l'envelopper dans ``asyncio.to_thread``. ``asyncio.to_thread`` pioche
    un thread dans le pool par défaut de l'event loop, potentiellement différent
    (et non sérialisé par le verrou d'exécution de rf-mcp) de celui qui a fait le
    login SAP GUI — sur ce thread-là, COM peut n'avoir jamais été initialisé,
    d'où le même `ensure_com_initialized` défensif que
    `ConnectionKeywords.connect_to_session` (voir
    `src/SapEccLibrary/keywords/_connection.py`) pour éviter RPC_E_WRONG_THREAD.
    """
    ensure_com_initialized()

    try:
        from robotmcp.components.execution.rf_native_context_manager import (
            get_rf_native_context_manager,
        )

        rf_mgr = get_rf_native_context_manager()
        res = rf_mgr.execute_keyword_with_context(
            session_id=session.session_id,
            keyword_name=keyword_name,
            arguments=list(arguments or []),
            assign_to=None,
            session_variables=dict(getattr(session, "variables", {}) or {}),
        )
    except Exception as exc:  # pragma: no cover - défensif
        logger.debug("run_keyword_in_context(%s) a échoué : %s", keyword_name, exc)
        raise RuntimeError(f"{keyword_name} a levé une exception : {exc}") from exc

    if not res or not res.get("success"):
        reason = (res or {}).get("error") or (res or {}).get("message") or "échec inconnu"
        raise RuntimeError(f"{keyword_name} a échoué côté RF : {reason}")
    if allow_structured:
        # ``result`` porte la valeur de retour du keyword ; ``output`` sa forme
        # texte. Priorité à la valeur structurée quand elle existe.
        out = res.get("result")
        if out is None:
            out = res.get("output")
        if out is None:
            raise RuntimeError(f"{keyword_name} a renvoyé une sortie vide")
        return out
    out = res.get("output") or res.get("result")
    if not (isinstance(out, str) and out):
        raise RuntimeError(f"{keyword_name} a renvoyé une sortie vide")
    return out
