"""Plugins rf-mcp (RobotMCP) pour l'écosystème SAP de ce dépôt.

Exporte SapEccPlugin / SapFioriPlugin / SapApiPlugin pour l'enregistrement par
entry-point (robotmcp.library_plugins) ou par manifeste .robotmcp/plugins/.
"""
from .api_plugin import SapApiPlugin
from .ecc_plugin import SapEccPlugin
from .fiori_plugin import SapFioriPlugin

__all__ = ["SapApiPlugin", "SapEccPlugin", "SapFioriPlugin"]
