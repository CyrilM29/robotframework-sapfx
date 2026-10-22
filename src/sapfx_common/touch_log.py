"""Journal des touches : ce qu'un run a RÉELLEMENT touché sur le système SAP
(backlog 2.83, lot 4, 2026-10-20).

Les types d'arguments et les tags Libdoc disent ce qu'une suite touche d'après
son texte. Le journal dit ce qu'un run a touché pour de vrai, transactions
lancées en interne comprises, requêtes OData lues comme écrites, modules
fonction et tables lus par RFC. Une matrice de couverture peut ainsi croiser
les deux et rapporter l'écart (un chemin qu'un texte ne montre pas, une
variable que le texte ne résolvait pas).

**Distinct du journal d'audit** (``audit_log``, ``SAPFX_AUDIT_LOG``) : celui-ci
est la trace de GOUVERNANCE, il exclut les lectures à dessein (une campagne en
fait des milliers) ; celui-là est un journal de COUVERTURE, il les inscrit
toutes. Il est **désactivé par défaut** : sans ``SAPFX_TOUCH_LOG=<chemin>``,
chaque point de passage fait un test de variable d'environnement et rien
d'autre. Il n'est jamais en cause dans un échec : une erreur d'E/S ou de
lecture est signalée une fois en avertissement et le geste continue.

Le journal dit ce qui a été TENTÉ, pas ce qui a réussi : une transaction
inexistante ou refusée par SAP (``Transaction Start Should Be Refused``) est
inscrite, une requête que le serveur refuse aussi. Seul un geste que la
politique de session a refusé avant de partir n'y figure pas.

Une entrée est une ligne JSON (``timestamp``, ``library``, ``channel`` ``gui``,
``http`` ou ``rfc``, ``action``, ``method`` pour HTTP, ``path`` sans sa requête,
``targets`` au format de ``touch_targets``, ``test``). Un chemin HTTP qui ne se lit pas
comme de l'OData est inscrit comme ``http_resource`` (le chemin lui-même), jamais comme un
service ou un entity set. Elle ne porte JAMAIS une
valeur saisie, un corps de requête, un paramètre d'appel (hors le nom de la
table lue) ni un identifiant de connexion : seulement ce qui est touché.

Typed.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlsplit

from sapfx_common.audit_log import current_test_name, strip_query
from sapfx_common.touch_targets import touched_by_argument, touched_by_http_path

__all__ = ["ENV_VAR", "read_touch_log", "record_batch", "record_http", "record_rfc",
           "record_touch", "record_transaction", "summarize_touches", "touch_log_path"]

ENV_VAR = "SAPFX_TOUCH_LOG"

_LOCK = threading.Lock()
_WARNED: set[str] = set()

#: Le paramètre d'un module fonction qui NOMME la table touchée. Un module qui
#: n'y figure pas ne désigne aucune table (le nom du module est la touche).
_TABLE_PARAMETERS = {"RFC_READ_TABLE": "QUERY_TABLE"}
_COUNT_FUNCTION = "EM_GET_NUMBER_OF_ENTRIES"


def touch_log_path() -> Optional[str]:
    """Le fichier du journal des touches, ``None`` sans variable."""
    value = os.environ.get(ENV_VAR, "").strip()
    return value or None


def _warn_once(path: str, error: BaseException) -> None:
    if path in _WARNED:
        return
    _WARNED.add(path)
    try:
        from robot.api import logger
        logger.warn("Journal des touches %s non écrit (%s) : le run continue, l'entrée "
                    "est perdue." % (path, error))
    except Exception:                       # noqa: BLE001 (hors Robot)
        pass


def record_touch(library: str, channel: str, action: str, targets: list[dict[str, Any]],
                 **fields: Any) -> None:
    """Inscrit une touche. Sans ``SAPFX_TOUCH_LOG``, ne fait rien. Ne lève
    jamais : un journal de couverture ne doit jamais faire échouer un geste."""
    path = touch_log_path()
    if not path:
        return
    try:
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "library": library, "channel": channel, "action": action, **fields,
                 "targets": targets, "test": current_test_name()}
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with _LOCK:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
    except Exception as error:               # noqa: BLE001 : jamais en cause dans un geste
        _warn_once(path, error)


def record_transaction(library: str, okcode: Any) -> None:
    """Une transaction démarrée par un code ou un OK-code. Un OK-code système
    (``/nex``) ne démarre rien et n'est pas inscrit."""
    if not touch_log_path():
        return
    try:
        targets = touched_by_argument("TransactionCode", okcode)
    except Exception as error:               # noqa: BLE001
        _warn_once(touch_log_path() or "", error)
        return
    if targets:
        record_touch(library, "gui", "start_transaction", targets)


def record_http(library: str, method: Any, path: Any) -> None:
    """Une requête HTTP : méthode et chemin SANS requête (un filtre peut porter
    des valeurs métier), plus ce que le chemin désigne s'il se lit."""
    if not touch_log_path():
        return
    try:
        clean = strip_query(str(path or ""))
        if "://" in clean:
            clean = urlsplit(clean).path       # jamais l'hôte, ni un identifiant d'URL
        targets = touched_by_http_path(clean)
        record_touch(library, "http", "request", targets, method=str(method or "").upper(),
                     path=clean)
    except Exception as error:               # noqa: BLE001
        _warn_once(touch_log_path() or "", error)


def record_batch(library: str, service_root: Any, operations: Any) -> None:
    """Les opérations d'un ``$batch`` : le chemin de la requête n'est que
    ``<service>/$batch``, les entity sets touchés sont dans ses parties. Chaque
    opération (méthode, chemin relatif à la racine du service) est inscrite
    comme une requête, sans son corps."""
    if not touch_log_path():
        return
    try:
        root = str(service_root or "").rstrip("/")
        for operation in operations or []:
            if isinstance(operation, Mapping) and operation.get("path"):
                record_http(library, operation.get("method"),
                            root + "/" + str(operation["path"]).lstrip("/"))
    except Exception as error:               # noqa: BLE001
        _warn_once(touch_log_path() or "", error)


def _rfc_tables(function: str, params: Mapping[str, Any]) -> list[str]:
    parameter = _TABLE_PARAMETERS.get(function)
    if parameter:
        name = params.get(parameter)
        return [str(name)] if isinstance(name, str) and name.strip() else []
    if function == _COUNT_FUNCTION:
        rows = params.get("IT_TABLES")
        if isinstance(rows, (list, tuple)):
            return [str(row.get("TABNAME")) for row in rows
                    if isinstance(row, Mapping) and str(row.get("TABNAME") or "").strip()]
    return []


def record_rfc(library: str, function_name: Any, params: Optional[Mapping[str, Any]] = None) -> None:
    """Un module fonction appelé, et la table qu'il lit quand le module la
    nomme dans ses paramètres (``RFC_READ_TABLE``). Aucune autre valeur de
    paramètre n'est inscrite."""
    if not touch_log_path():
        return
    try:
        function = str(function_name or "").strip().upper()
        targets = touched_by_argument("RfcFunctionName", function)
        for table in _rfc_tables(function, params or {}):
            targets += touched_by_argument("TableName", table)
        record_touch(library, "rfc", "call", targets)
    except Exception as error:               # noqa: BLE001
        _warn_once(touch_log_path() or "", error)


def read_touch_log(path: Any) -> list[dict[str, Any]]:
    """Les entrées d'un journal des touches. Une ligne illisible (la dernière,
    coupée par un run interrompu) est ignorée et ne fait pas perdre les autres ;
    un fichier absent rend ``[]``."""
    entries: list[dict[str, Any]] = []
    try:
        with open(str(path), encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except FileNotFoundError:
        return []
    return entries


def summarize_touches(entries: Iterable[Mapping[str, Any]],
                      service_roots: Iterable[Any] = ()) -> dict[str, list[dict[str, Any]]]:
    """Les cibles distinctes touchées par test : ``{test: [cible, ...]}``, triées
    par genre puis identifiant ; une touche hors test porte la clé ``""``.
    ``service_roots`` relit les chemins HTTP avec les racines de service que
    l'appelant connaît (un service CAP) ; sans elles, un chemin qui n'était pas
    lisible reste ``resolved: False``."""
    roots = list(service_roots)
    by_test: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for entry in entries:
        targets = entry.get("targets") or []
        if entry.get("channel") == "http" and roots and entry.get("path"):
            targets = touched_by_http_path(entry["path"], roots)
        for target in targets:
            key = (str(target.get("kind")), str(target.get("id") or target.get("reason") or ""))
            by_test.setdefault(str(entry.get("test") or ""), {}).setdefault(key, dict(target))
    return {test: [found[key] for key in sorted(found)] for test, found in by_test.items()}
