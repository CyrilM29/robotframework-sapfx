"""Petit utilitaire : exécuter un keyword de perception dans le contexte RF live.

C'est le pattern qu'emploie rf-mcp lui-même (cf. PageSourceService
._get_page_source_via_rf_context) pour atteindre l'instance de bibliothèque
vivante sans y accéder directement : on demande au gestionnaire de contexte RF
natif d'exécuter un keyword côté session et on récupère sa sortie.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from sapfx_common.com_safety import ensure_com_initialized

from ._staleness import attach_staleness

logger = logging.getLogger(__name__)

# rf-mcp ne renvoie JAMAIS de sortie texte vide sur un succès : quand le keyword
# retourne ``None``, il écrit la chaîne "OK" dans ``output`` (deux sites de
# retour de son rf_native_context_manager). Sans cette sentinelle, le garde de
# sortie vide ci-dessous est inatteignable et une section d'état absente
# arriverait à l'agent sous la forme d'un franc « OK ».
_NONE_OUTPUT_SENTINEL = "OK"


def run_keyword_in_context(session, keyword_name: str, *,
                           arguments=None,
                           allow_structured: bool = False,
                           needs_com: bool = True):
    """Exécute ``keyword_name`` dans le contexte RF de ``session`` et retourne
    sa sortie texte. ``arguments`` : arguments positionnels optionnels du
    keyword (chaînes, comme en Robot).

    ``allow_structured=True`` accepte aussi une valeur de retour structurée
    (dict/list/tuple JSON-safe, jamais un objet COM, cf. field notes MCP × COM)
    au lieu d'exiger du texte : le canal des keywords d'état applicatif
    (``Get Open Windows``, ``Get Session Telemetry``…).

    Lève ``RuntimeError`` (message explicite) si le gestionnaire de contexte RF
    est indisponible, si le keyword échoue côté RF, ou si sa sortie est vide ;
    les appelants (state providers) sont responsables de convertir cette
    exception en réponse ``{"success": False, "error": ...}`` afin que la vraie
    cause reste visible côté agent, plutôt qu'un "keyword absent ?" générique.

    Bloquant (entre dans _suppress_stdout côté rf-mcp) : les appelants async
    doivent l'envelopper dans ``asyncio.to_thread``. ``asyncio.to_thread`` pioche
    un thread dans le pool par défaut de l'event loop, potentiellement différent
    (et non sérialisé par le verrou d'exécution de rf-mcp) de celui qui a fait le
    login SAP GUI : sur ce thread-là, COM peut n'avoir jamais été initialisé,
    d'où le même `ensure_com_initialized` défensif que
    `ConnectionKeywords.connect_to_session` (voir
    `src/SapEccLibrary/keywords/_connection.py`) pour éviter RPC_E_WRONG_THREAD.
    Corollaire : rien ne garantit que deux appels consécutifs tombent sur le
    MÊME thread du pool, alors que le scripting SAP GUI est du COM STA. Le
    marshaling défensif rend l'accès croisé fonctionnel ; le rail strict
    (``SAPFX_STRICT_COM_THREAD=1``) le rend au contraire bruyant, et c'est
    justement pour cela qu'un appelant ne doit pas l'avaler (voir
    :func:`structured_state`).

    ``needs_com=False`` saute cette initialisation : les canaux Fiori
    (Playwright/CDP) et API (HTTP) n'ont aucun objet COM, et un
    ``CoInitialize`` sans ``CoUninitialize`` y ferait entrer durablement en
    appartement STA chaque worker frais du pool, pour rien.
    """
    if needs_com:
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
    out = _payload(res)
    if allow_structured:
        # ``result`` porte la valeur de retour du keyword ; ``output`` sa forme
        # texte. Priorité à la valeur structurée quand elle existe.
        if out is None:
            raise RuntimeError(f"{keyword_name} a renvoyé une sortie vide")
        return out
    if not (isinstance(out, str) and out):
        raise RuntimeError(f"{keyword_name} a renvoyé une sortie vide")
    return out


def _payload(res: Dict[str, Any]) -> Any:
    """Valeur de retour réelle d'une réponse rf-mcp en succès, ``None`` si le
    keyword n'a rien retourné.

    ``result`` fait FOI dès qu'il est présent : rf-mcp le pose systématiquement
    à côté de ``output``, et un ``result`` à ``None`` est un vrai retour vide,
    pas une invitation à lire la forme texte. Le repli sur ``output`` ne sert
    qu'aux réponses (anciennes ou défensives) sans clé ``result``, et y neutralise
    la sentinelle "OK" que rf-mcp substitue justement à un retour ``None``.
    """
    if "result" in res:
        return res["result"]
    out = res.get("output")
    return None if out == _NONE_OUTPUT_SENTINEL else out


async def perception_text(session, keyword_name: str, *,
                          needs_com: bool = True) -> str:
    """Keyword de perception à sortie TEXTE (signature d'écran, arbre UI5),
    exécuté hors de l'event loop. Lève ``RuntimeError`` : les state providers
    convertissent en ``{"success": False, "error": ...}``.

    Le saut de thread vit ici, jamais chez l'appelant : c'est le point unique
    où se règle l'arbitrage pool de threads / affinité COM décrit dans
    :func:`run_keyword_in_context`.
    """
    return await asyncio.to_thread(
        run_keyword_in_context, session, keyword_name, needs_com=needs_com)


async def structured_state(session, keyword_name: str,
                           errors: Dict[str, str], *,
                           section: Optional[str] = None,
                           needs_com: bool = True) -> Any:
    """Keyword d'état à sortie structurée, en BEST-EFFORT : retourne ``None``
    et consigne la cause dans ``errors`` au lieu de lever.

    C'est le contrat d'appel commun aux trois state providers (ECC, Fiori,
    API) : chaque section d'un état applicatif est facultative, un keyword
    indisponible ne doit jamais priver l'agent des autres sections. Le saut
    de thread (``asyncio.to_thread``) est ici parce que le contexte RF est
    synchrone, et il n'a de sens qu'associé à ce contrat ; le regrouper évite
    qu'une évolution (timeout, normalisation des erreurs, interaction avec le
    staleness) ne s'applique qu'à deux canaux sur trois.

    ``section`` : clé sous laquelle consigner l'échec, quand elle diffère du
    nom du keyword (deux sections peuvent interroger le même keyword ; une
    seule entrée d'erreur par NOM masquerait la moitié des dégradations).
    """
    try:
        return await asyncio.to_thread(
            run_keyword_in_context, session, keyword_name,
            allow_structured=True, needs_com=needs_com)
    except Exception as exc:      # noqa: BLE001 (contrat best-effort)
        errors[section or keyword_name] = str(exc)
        return None


def finalize_state(state: Dict[str, Any],
                   errors: Optional[Dict[str, str]] = None,
                   not_applicable: Optional[Dict[str, str]] = None,
                   ) -> Dict[str, Any]:
    """Queue COMMUNE à tout état applicatif servi par un state provider :
    joindre les sections dégradées, celles qui sont sans objet, puis
    l'avertissement de code périmé.

    Elle existe parce que l'épilogue était recopié à chaque sortie de chaque
    provider, y compris deux fois dans une même méthode (le retour anticipé
    « non connecté » et le retour nominal) : une copie oubliée sur un chemin
    de sortie, et ce canal cesse silencieusement d'avertir que le code SAPFX a
    changé sur disque, ce que `_staleness` existe précisément pour éviter.

    ``collection_errors`` (quelque chose a ÉCHOUÉ) et ``not_applicable``
    (la section n'a pas de sens ici) sont deux clés distinctes à dessein : une
    page sans runtime UI5 est une cible parfaitement supportée, la ranger
    parmi les erreurs apprend à l'agent à ignorer un signal qui doit rester
    fiable sur les autres canaux.
    """
    if errors:
        state["collection_errors"] = dict(errors)
    if not_applicable:
        state["not_applicable"] = dict(not_applicable)
    return attach_staleness(state)
