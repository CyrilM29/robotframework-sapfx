"""Détection de code SAPFX modifié APRÈS le démarrage du serveur rf-mcp.

Piège connu (field notes CLAUDE.md) : rf-mcp importe les bibliothèques à la
première session et **fige classe ET instance** pour toute la vie du process :
après une modification du code de ``src/``, un simple ``manage_session init``
resservira l'ANCIENNE classe, et l'agent debuggue un comportement qui n'existe
plus dans les sources. Ce module transforme ce piège en avertissement
actionnable : les state providers comparent le mtime des fichiers des modules
SAPFX déjà chargés à l'heure de démarrage du process et, en cas d'écart,
ajoutent ``stale_code_warning`` à leurs réponses.

Best-effort par construction : jamais d'exception (une erreur de stat est
ignorée), jamais bloquant : un scan de ``sys.modules`` filtré par préfixe.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Iterable, List, Optional

# Préfixes de modules surveillés : les quatre paquets SAPFX + les plugins
# eux-mêmes (une modification de sap_robotmcp exige tout autant un redémarrage).
WATCHED_PREFIXES = ("SapEccLibrary", "SapFioriLibrary", "SapApiLibrary",
                    "sapfx_common", "sap_robotmcp")

# Référence temporelle : l'import de ce module ≈ le démarrage du process
# rf-mcp (les plugins sont chargés par entry points au démarrage du serveur).
_STARTED_AT = time.time()


def stale_modules(prefixes: Iterable[str] = WATCHED_PREFIXES,
                  since: Optional[float] = None) -> List[str]:
    """Noms (triés) des modules chargés dont le fichier source a été modifié
    sur disque APRÈS ``since`` (défaut : le démarrage du process)."""
    reference = _STARTED_AT if since is None else since
    watched = tuple(prefixes)
    stale: List[str] = []
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith(watched):
            continue
        path = getattr(module, "__file__", None)
        if not path:
            continue
        try:
            if os.path.getmtime(path) > reference:
                stale.append(name)
        except OSError:
            continue
    return sorted(stale)


def staleness_warning(prefixes: Iterable[str] = WATCHED_PREFIXES,
                      since: Optional[float] = None) -> Optional[str]:
    """Message d'avertissement prêt à joindre à une réponse de state provider,
    ou ``None`` si aucun module surveillé n'a changé sur disque."""
    names = stale_modules(prefixes, since)
    if not names:
        return None
    return (
        "Le code de %s a changé sur disque APRÈS le démarrage du serveur "
        "rf-mcp, qui fige classes et instances de bibliothèques pour tout le "
        "process : cette session utilise encore l'ANCIENNE version. "
        "Redémarrer le serveur rf-mcp avant de diagnostiquer quoi que ce soit."
        % ", ".join(names))


def attach_staleness(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Joint l'avertissement à une réponse de state provider, s'il y a lieu.
    Retourne ``payload`` (chaînable).

    Le geste est le MÊME sur chaque sortie de chaque provider (page source,
    état applicatif, et jusqu'à l'assemblage de la surcouche) : le factoriser
    ici est ce qui garantit qu'un nouveau chemin de sortie ne l'oublie pas, et
    qu'un changement de clé ou de condition d'émission n'ait qu'un seul point
    d'application."""
    warning = staleness_warning()
    if warning:
        payload["stale_code_warning"] = warning
    return payload
