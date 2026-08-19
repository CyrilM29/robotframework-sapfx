"""Garde de compatibilité de la surcouche ``sapfx-mcp``.

La surcouche (:mod:`sap_robotmcp.server`) monte le serveur rf-mcp INCHANGÉ et
s'appuie sur une poignée de points d'ancrage semi-publics de rf-mcp, tous
validés live le 2026-07-23 (voir les field notes « Test live agent+MCP » de
CLAUDE.md). Un rf-mcp plus récent peut les déplacer sans préavis : plutôt que
d'échouer mystérieusement en pleine session agent, ce garde vérifie TOUT au
démarrage et refuse de lancer le serveur avec la liste exacte des écarts :
le même esprit que ``scripts/check_vendor_drift.py`` pour le code vendorisé.

``SAPFX_MCP_FORCE=1`` outrepasse le refus (démarrage en mode dégradé annoncé),
pour ne jamais bloquer un poste où seul le numéro de version a bougé.

Les plugins, eux, se chargent aussi par entry point dans un serveur ``robotmcp``
STANDARD, où rien de tout cela ne s'exécute (l'installateur du pack retombe
d'ailleurs sur ``robotmcp.exe`` quand ``sapfx-mcp.exe`` manque). Cette voie-là
reçoit :func:`warn_version_once`, un avertissement de version NON bloquant :
elle ne peut pas sonder les points d'ancrage, puisqu'importer
``robotmcp.server`` depuis un plugin en cours de chargement PAR ce serveur
serait circulaire ; la fenêtre de versions, elle, se lit dans les métadonnées.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Valeurs qui ACTIVENT une échappatoire d'environnement. Un simple test de
# véracité accepterait « 0 », « false » ou « off », c'est-à-dire exactement ce
# qu'un exploitant écrit pour dire l'inverse.
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

# Fenêtre de versions rf-mcp validées : [minimum, borne exclue) sur
# (major, minor). 0.31 est la série contre laquelle chaque point d'ancrage a
# été validé live ; la 0.35 a été re-validée le 2026-07-24 (diff du wheel :
# plugins/manager.py et contracts.py inchangés octet à octet, base.py ajout
# rétro-compatible, server.py conserve mcp/execution_engine/main ; les séries
# 0.32/0.33 n'existent pas sur PyPI). Élargir APRÈS re-validation, jamais avant.
TESTED_MIN: Tuple[int, int] = (0, 31)
TESTED_UPPER: Tuple[int, int] = (0, 36)

# Distributions possibles du paquet (le projet PyPI s'appelle rf-mcp, le
# paquet importable robotmcp, on tente les deux noms).
_DIST_NAMES = ("rf-mcp", "robotmcp")

# Points d'ancrage utilisés par la surcouche : (module, [attributs]).
_ANCHORS = [
    ("robotmcp.plugins.manager",
     ["get_library_plugin_manager", "reset_library_plugin_manager_for_tests",
      "iter_entry_point_plugins"]),
    ("robotmcp.server", ["mcp", "execution_engine", "main"]),
    ("fastmcp.utilities.types", ["Image"]),
]


def robotmcp_version() -> Optional[str]:
    """Version installée de rf-mcp (``None`` si introuvable)."""
    for name in _DIST_NAMES:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def _major_minor(version: str) -> Optional[Tuple[int, int]]:
    parts = version.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None


def env_flag_enabled(value: Optional[str]) -> bool:
    """Une échappatoire d'environnement (``SAPFX_MCP_FORCE``) est-elle
    ACTIVÉE ? Seules les valeurs affirmatives comptent : poser la variable à
    « 0 » ou « false » pour documenter « ne jamais contourner » ne doit pas
    produire l'effet exactement inverse."""
    return (value or "").strip().lower() in _TRUE_VALUES


def version_problem() -> Optional[str]:
    """Écart de VERSION rf-mcp vis-à-vis de la fenêtre validée, ou ``None``.

    Séparé de :func:`check_compat` parce qu'il se lit dans les métadonnées de
    distribution, sans importer le moindre module rf-mcp : c'est la seule
    partie du garde utilisable depuis un plugin chargé par entry point."""
    version = robotmcp_version()
    if version is None:
        return ("rf-mcp introuvable (distributions cherchées : %s) ; "
                "pip install rf-mcp." % ", ".join(_DIST_NAMES))
    pair = _major_minor(version)
    if pair is None:
        return ("version rf-mcp illisible : %r ; fenêtre validée [%d.%d, %d.%d)."
                % (version, *TESTED_MIN, *TESTED_UPPER))
    if not (TESTED_MIN <= pair < TESTED_UPPER):
        return ("rf-mcp %s hors de la fenêtre validée [%d.%d, %d.%d) : "
                "re-valider les points d'ancrage de la surcouche (field notes "
                "« Test live agent+MCP » de CLAUDE.md) puis élargir "
                "sap_robotmcp/_compat.py." % (version, *TESTED_MIN, *TESTED_UPPER))
    return None


def warn_version_once() -> Optional[str]:
    """Avertit UNE fois (log WARNING) si la version rf-mcp est hors fenêtre.

    C'est le filet de la voie entry point : les plugins SAP se chargent dans
    n'importe quel serveur rf-mcp, y compris le ``robotmcp`` standard, qui
    n'exécute jamais le refus au démarrage de la surcouche. Non bloquant à
    dessein : refuser ici ferait tomber un serveur qui, lui, n'a rien demandé.
    Retourne le message émis (``None`` si tout va bien ou si déjà averti)."""
    global _WARNED_ONCE
    if _WARNED_ONCE:
        return None
    _WARNED_ONCE = True
    problem = version_problem()
    if problem:
        logger.warning("[sapfx] compatibilité rf-mcp : %s", problem)
    return problem


_WARNED_ONCE = False


def check_compat() -> List[str]:
    """Retourne la liste des problèmes de compatibilité (vide si tout est là)."""
    problems: List[str] = []

    problem = version_problem()
    if problem:
        problems.append(problem)

    for module_name, attrs in _ANCHORS:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            problems.append("module d'ancrage inimportable : %s (%s)"
                            % (module_name, exc))
            continue
        for attr in attrs:
            if not hasattr(module, attr):
                problems.append(
                    "point d'ancrage disparu : %s.%s ; l'interne rf-mcp a "
                    "bougé, adapter la surcouche." % (module_name, attr))

    # L'accesseur de session est un point d'ancrage de 2e niveau. Depuis
    # rf-mcp 0.34, ``robotmcp.server.execution_engine`` est un PROXY LAZY
    # (fast-mcp-handshake-lazy-init) : un ``hasattr`` sur le proxy
    # matérialiserait tout le moteur d'exécution pendant ce check et rendrait
    # au handshake MCP la lenteur que l'upstream vient d'enlever. On sonde donc
    # la CLASSE ExecutionCoordinator ; repli sur l'instance pour un rf-mcp
    # antérieur qui ne l'exposerait pas à ce chemin.
    if not _has_get_session_anchor():
        problems.append(
            "point d'ancrage disparu : robotmcp.server.execution_engine"
            ".get_session ; adapter la résolution de session de la "
            "surcouche.")

    return problems


def _has_get_session_anchor() -> bool:
    """``get_session`` est-il présent sur le moteur d'exécution rf-mcp ?

    Sonde d'abord la classe ``ExecutionCoordinator`` (aucune construction) ;
    en dernier recours seulement, l'attribut d'instance sur
    ``robotmcp.server.execution_engine`` (peut matérialiser le moteur).
    Retourne ``True`` aussi quand ``robotmcp.server`` est inimportable : ce
    cas est déjà remonté par la boucle des ancres de module."""
    try:
        coordinator = importlib.import_module(
            "robotmcp.components.execution.execution_coordinator")
    except Exception:
        coordinator = None
    if coordinator is not None:
        cls = getattr(coordinator, "ExecutionCoordinator", None)
        if cls is not None:
            return hasattr(cls, "get_session")
    try:
        server = importlib.import_module("robotmcp.server")
    except Exception:
        return True
    engine = getattr(server, "execution_engine", None)
    return engine is None or hasattr(engine, "get_session")
