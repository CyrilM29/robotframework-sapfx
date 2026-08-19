"""Plugins rf-mcp (RobotMCP) pour l'écosystème SAP de ce dépôt.

Exporte SapEccPlugin / SapFioriPlugin / SapApiPlugin pour l'enregistrement par
entry-point (robotmcp.library_plugins) ou par manifeste .robotmcp/plugins/.
"""
from ._compat import warn_version_once
from .api_plugin import SapApiPlugin
from .ecc_plugin import SapEccPlugin
from .fiori_plugin import SapFioriPlugin

# Les plugins se chargent dans n'importe quel serveur rf-mcp, pas seulement
# sous la surcouche `sapfx-mcp` qui, elle, refuse de démarrer hors fenêtre de
# compatibilité. Sur la voie entry point, ce simple avertissement de version
# est tout ce qu'on peut faire sans importer rf-mcp lui-même (import circulaire
# : c'est ce serveur-là qui est en train de nous charger).
warn_version_once()

__all__ = ["SapApiPlugin", "SapEccPlugin", "SapFioriPlugin"]
