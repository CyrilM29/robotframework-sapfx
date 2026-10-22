"""Journal d'audit des gestes gouvernés par la politique de session (backlog
§ 2.1, 2026-10-08).

Chaque décision qui compte s'y inscrit : politique chargée ou changée,
approbation, transaction lancée, écriture permise, approuvée ou refusée. Les
LECTURES ne s'y inscrivent pas (une campagne en fait des milliers, et elles
ne changent rien sur la cible).

Deux supports : la mémoire de l'instance de bibliothèque (portée de la
suite) et, en option, un fichier **JSONL cumulatif**
(``SAPFX_AUDIT_LOG=<chemin>``, une ligne par entrée, en append), sur le patron
de ``healing_telemetry``. Une entrée porte la DÉCISION et sa CIBLE nommée
(code de transaction, identifiant d'élément, méthode et chemin HTTP sans la
requête, nom de module fonction) et, pour une approbation et l'écriture
qu'elle autorise, QUI a approuvé (``approver`` : ``agent`` ou ``human``),
jamais une valeur saisie, un corps, un
paramètre ni un identifiant de connexion. L'écriture du fichier est
best-effort : une erreur d'E/S est signalée en avertissement et ne fait pas
échouer le geste, qui reste dans la trace en mémoire.

Typed.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional

ENV_VAR = "SAPFX_AUDIT_LOG"

_LOCK = threading.Lock()


def audit_path() -> Optional[str]:
    """Le fichier du journal cumulatif, ``None`` sans variable."""
    value = os.environ.get(ENV_VAR, "").strip()
    return value or None


def current_test_name() -> str:
    """Le test Robot en cours, vide hors exécution ou entre deux tests."""
    try:
        from robot.running.context import EXECUTION_CONTEXTS
        context = EXECUTION_CONTEXTS.current
        test = getattr(context, "test", None) if context is not None else None
        return str(getattr(test, "full_name", "") or getattr(test, "name", "") or "")
    except Exception:                       # noqa: BLE001 (best-effort)
        return ""


def strip_query(path: str) -> str:
    """Un chemin HTTP sans sa requête : un filtre peut porter des valeurs
    métier, le journal n'en garde que la ressource visée."""
    return str(path or "").split("?", 1)[0]


class AuditTrail:
    """La trace d'audit d'une instance de bibliothèque."""

    def __init__(self, library: str) -> None:
        self.library = library
        self.entries: list[dict[str, Any]] = []
        self.write_errors = 0

    def record(self, channel: str, action: str, target: str, decision: str,
               reason: str, mode: str, policy_hash: str,
               approver: str = "") -> dict[str, Any]:
        """Inscrit une décision. ``approver`` (``agent`` ou ``human``) dit qui a
        approuvé, sur une approbation et sur l'écriture qu'elle autorise ;
        vide ailleurs."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "library": self.library, "channel": channel, "action": action,
            "target": target, "decision": decision, "reason": reason, "mode": mode,
            "policy_hash": policy_hash, "approver": approver,
            "test": current_test_name(),
        }
        self.entries.append(entry)
        self._append(entry)
        return entry

    def _append(self, entry: dict[str, Any]) -> None:
        path = audit_path()
        if not path:
            return
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        try:
            with _LOCK:
                directory = os.path.dirname(path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(path, "a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line + "\n")
        except OSError as exc:
            self.write_errors += 1
            try:
                from robot.api import logger
                logger.warn("Journal d'audit %s non écrit (%s) : l'entrée reste dans "
                            "la trace en mémoire." % (path, exc))
            except Exception:               # noqa: BLE001 (hors Robot)
                pass

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self.entries]
