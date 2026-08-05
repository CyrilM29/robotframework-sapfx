"""``sapfx-mcp`` : point d'entrée de la surcouche SAP au-dessus de rf-mcp.

PAS un fork : ce module importe l'instance FastMCP de rf-mcp TELLE QUELLE
(tous ses outils restent servis, comportement inchangé) et y AJOUTE trois
outils que le contrat plugin rf-mcp 0.31 ne permet pas (constaté live le
2026-07-23, field notes « Test live agent+MCP » de CLAUDE.md) :

- ``sapfx_state``       : état SAP par NOS state providers, ``page_source``
  en vraie sémantique diff par défaut, ``application_state`` enrichi
  (``modal_open``, statut, télémétrie, jamais routé par rf-mcp) ;
- ``sapfx_screenshot``  : le canal VISION, vraie image MCP (brute ou
  annotée Set-of-Mark + légende ``numéro -> id``) ;
- ``sapfx_reload``      : hot-reload de la couche plugin sans redémarrage.

Au démarrage, le garde de compatibilité (:mod:`sap_robotmcp._compat`) vérifie
la fenêtre de versions rf-mcp validée et chaque point d'ancrage, et REFUSE de
démarrer en cas d'écart (``SAPFX_MCP_FORCE=1`` pour outrepasser). Transport
stdio : toute sortie de la surcouche part sur stderr, stdout appartient au
protocole MCP.

Lancement (mêmes arguments que ``robotmcp``, délégués tels quels) :

    sapfx-mcp --transport stdio --without-frontend
    python -m sap_robotmcp.server --transport stdio --without-frontend
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, List, Optional

from ._compat import check_compat

# Noms des outils ajoutés par la surcouche (contrat vérifié par test).
OVERLAY_TOOL_NAMES = ("sapfx_state", "sapfx_screenshot", "sapfx_reload")


def build_overlay(mcp: Any, execution_engine: Any) -> List[str]:
    """Enregistre les outils ``sapfx_*`` sur l'instance FastMCP de rf-mcp.

    Retourne les noms enregistrés. Séparé de :func:`main` pour être exerçable
    en test (montage sur la vraie instance rf-mcp, sans lancer le serveur).
    """
    from fastmcp.utilities.types import Image
    from robotmcp.plugins.manager import get_library_plugin_manager

    from ._overlay import (STATE_SECTIONS, collect_state, reload_plugin_layer,
                           resolve_session, take_screenshot_payload)

    @mcp.tool
    async def sapfx_state(session_id: str,
                          sections: Optional[List[str]] = None,
                          full_source: bool = False,
                          filtered: bool = False,
                          filtering_level: str = "standard",
                          library: str = "") -> dict:
        """SAP session state served DIRECTLY by the SAPFX state providers.

        Sections (default: both): 'page_source', the screen perception with
        the REAL differential semantics (an already-seen screen that changed
        returns a compact smart diff unless full_source=true), and
        'application_state', the live enriched state: transaction, window
        stack with modal_open (the leftover-error-modal trap), status-message
        type, session telemetry. 'library' picks the provider explicitly
        (SapEccLibrary/SapFioriLibrary) when the session imports both.
        """
        return await collect_state(
            execution_engine, get_library_plugin_manager(), session_id,
            sections=sections or list(STATE_SECTIONS),
            full_source=full_source, filtered=filtered,
            filtering_level=filtering_level, library=library)

    @mcp.tool
    async def sapfx_screenshot(session_id: str,
                               annotated: bool = False,
                               include_types: str = ""):
        """Screenshot of the live SAP screen as REAL MCP image content.

        Works on both channels: SAP GUI desktop sessions use the ECC
        in-memory capture; Fiori/web sessions fall back to the Browser
        library's screenshot. annotated=true (ECC only) draws the
        Set-of-Mark boxes (numbered actionable targets) and appends the
        legend mapping number -> element id as a text block: read the number
        on the image, feed the id to a deterministic keyword. include_types
        restricts annotation to given control types (e.g.
        'GuiShell,GuiCustomControl').
        """
        session = resolve_session(execution_engine, session_id)
        if session is None:
            return {"success": False,
                    "error": "session rf-mcp introuvable : %r" % session_id}
        payload = await asyncio.to_thread(
            take_screenshot_payload, session, annotated, include_types)
        if not payload.get("success"):
            return payload
        image = Image(data=payload["data"], format=payload["format"])
        if annotated:
            legend = json.dumps(payload.get("legend") or {},
                                ensure_ascii=False, sort_keys=True)
            return [image, "legende (numero -> id) : %s" % legend]
        return image

    @mcp.tool
    def sapfx_reload() -> dict:
        """Hot-reload the SAPFX plugin layer without restarting the server.

        Reloads the sap_robotmcp modules, resets the rf-mcp plugin manager
        and re-registers the entry-point plugins, the live-validated
        protocol (the builtin 'manage_library_plugins reload' alone serves
        cached instances). Library code (SapEccLibrary/...) changed on disk
        still needs the RF-context hot-swap or a server restart; see the
        returned note and the providers' stale_code_warning.
        """
        return reload_plugin_layer()

    return list(OVERLAY_TOOL_NAMES)


def main(argv: Optional[List[str]] = None) -> int:
    """Garde de compat, montage de la surcouche, puis délégation au serveur
    rf-mcp inchangé (mêmes arguments CLI)."""
    problems = check_compat()
    if problems:
        for problem in problems:
            print("[sapfx-mcp] COMPAT : %s" % problem, file=sys.stderr)
        if not os.environ.get("SAPFX_MCP_FORCE"):
            print("[sapfx-mcp] refus de démarrer (SAPFX_MCP_FORCE=1 pour "
                  "outrepasser en mode dégradé).", file=sys.stderr)
            return 1
        print("[sapfx-mcp] SAPFX_MCP_FORCE actif : démarrage en mode dégradé "
              "malgré les écarts ci-dessus.", file=sys.stderr)

    import robotmcp.server as robot_server

    registered = build_overlay(robot_server.mcp, robot_server.execution_engine)
    print("[sapfx-mcp] surcouche active sur rf-mcp %s : %s"
          % (getattr(robot_server, "__name__", "?"), ", ".join(registered)),
          file=sys.stderr)
    robot_server.main(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
