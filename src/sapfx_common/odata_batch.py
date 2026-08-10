"""Construction et parsing des requêtes OData ``$batch`` (multipart/mixed).

Le format multipart est accepté par les DEUX générations : Gateway v2 ET
services v4 (qui acceptent multipart en plus du batch JSON), une seule
implémentation couvre donc tout le périmètre du canal API. La sémantique
SAP qui compte pour la préparation de données : les écritures regroupées
dans UN changeset forment une unité ATOMIQUE (tout passe ou tout est
annulé), les lectures restent des parties indépendantes.

Logique pure (bytes -> bytes) : les E/S HTTP, le protocole CSRF et l'URL
``<service>/$batch`` restent dans ``SapApiLibrary``.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Iterable, Optional

_ALLOWED_METHODS = ("GET", "POST", "PATCH", "PUT", "DELETE", "MERGE")
_CRLF = "\r\n"


def build_batch(operations: Iterable[dict[str, Any]],
                boundary: Optional[str] = None,
                changeset_boundary: Optional[str] = None,
                atomic: bool = True) -> tuple[bytes, str]:
    """Assemble un corps ``$batch`` multipart depuis ``operations`` (dicts
    ``{"method", "path", "payload"?, "headers"?}``, ``path`` relatif à la
    racine du service). Retourne ``(corps_bytes, content_type)``.

    ``atomic=True`` (défaut) : TOUTES les écritures partent dans un seul
    changeset (unité atomique SAP), inséré à la position de la première
    écriture ; les lectures gardent leur position. ``atomic=False`` : chaque
    écriture devient son propre changeset (échecs indépendants). Chaque
    écriture reçoit un ``Content-ID`` séquentiel (1, 2, …), réutilisable dans
    les corps suivants via la référence ``$<n>`` du protocole OData.
    """
    ops = [_normalize_operation(op, index) for index, op in enumerate(operations)]
    if not ops:
        raise ValueError("Post Odata Batch : aucune opération fournie.")
    boundary = boundary or ("batch_%s" % uuid.uuid4().hex)
    changeset_boundary = changeset_boundary or ("changeset_%s" % uuid.uuid4().hex)

    writes = [op for op in ops if op["method"] != "GET"]
    content_ids = {id(op): str(number) for number, op in enumerate(writes, start=1)}

    blocks: list[str] = []
    pending_changeset: list[str] = []
    for op in ops:
        if op["method"] == "GET":
            blocks.append(_http_part(op, content_id=None))
        elif atomic:
            pending_changeset.append(_http_part(op, content_ids[id(op)]))
            if len(pending_changeset) == len(writes):
                blocks.append(_changeset(pending_changeset, changeset_boundary))
        else:
            suffix = content_ids[id(op)]
            blocks.append(_changeset([_http_part(op, suffix)],
                                     "%s_%s" % (changeset_boundary, suffix)))

    body = ""
    for block in blocks:
        body += "--%s%s%s%s" % (boundary, _CRLF, block, _CRLF)
    body += "--%s--%s" % (boundary, _CRLF)
    return body.encode("utf-8"), "multipart/mixed; boundary=%s" % boundary


def _normalize_operation(op: Any, index: int) -> dict[str, Any]:
    if not isinstance(op, dict):
        raise ValueError(
            "Post Odata Batch : l'opération n°%d n'est pas un dict "
            "(reçu %r)." % (index + 1, type(op).__name__))
    method = str(op.get("method", "")).upper().strip()
    if method not in _ALLOWED_METHODS:
        raise ValueError(
            "Post Odata Batch : méthode %r inconnue (opération n°%d) ; "
            "attendu : %s." % (op.get("method"), index + 1,
                               ", ".join(_ALLOWED_METHODS)))
    path = str(op.get("path", "")).strip().lstrip("/")
    if not path:
        raise ValueError(
            "Post Odata Batch : 'path' manquant (opération n°%d)." % (index + 1))
    return {"method": method, "path": path,
            "payload": op.get("payload"),
            "headers": dict(op.get("headers") or {})}


def _http_part(op: dict[str, Any], content_id: Optional[str]) -> str:
    payload = op["payload"]
    if payload is None:
        body = ""
    elif isinstance(payload, str):
        body = payload
    else:
        body = json.dumps(payload)
    lines = ["Content-Type: application/http",
             "Content-Transfer-Encoding: binary"]
    if content_id is not None:
        lines.append("Content-ID: %s" % content_id)
    lines.append("")
    lines.append("%s %s HTTP/1.1" % (op["method"], op["path"]))
    headers = {"Accept": "application/json"}
    if body:
        headers["Content-Type"] = "application/json"
    headers.update(op["headers"])
    for name, value in headers.items():
        lines.append("%s: %s" % (name, value))
    lines.append("")
    lines.append(body)
    return _CRLF.join(lines)


def _changeset(parts: list[str], boundary: str) -> str:
    lines = ["Content-Type: multipart/mixed; boundary=%s" % boundary, ""]
    for part in parts:
        lines.append("--%s" % boundary)
        lines.append(part)
    lines.append("--%s--" % boundary)
    return _CRLF.join(lines)


def parse_batch_response(body: bytes, content_type: str) -> list[dict[str, Any]]:
    """Parse la réponse d'un ``$batch`` en liste ordonnée de réponses
    individuelles ``{"status", "reason", "headers", "body", "json"}`` (les
    changesets imbriqués sont aplatis dans l'ordre). ``json`` vaut ``None``
    quand le corps n'est pas du JSON."""
    boundary = _boundary_of(content_type)
    if boundary is None:
        raise ValueError(
            "Réponse $batch sans boundary dans son Content-Type (%r) : "
            "le serveur a-t-il vraiment répondu en multipart ?" % content_type)
    return _parse_multipart(body, boundary.encode("ascii"))


def _boundary_of(content_type: str) -> Optional[str]:
    for parameter in (content_type or "").split(";"):
        name, _, value = parameter.strip().partition("=")
        if name.strip().lower() == "boundary":
            return value.strip().strip('"')
    return None


def _parse_multipart(data: bytes, boundary: bytes) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for chunk in data.split(b"--" + boundary)[1:]:
        if chunk.startswith(b"--"):
            break   # terminateur --boundary--
        chunk = chunk.lstrip(b"\r\n")
        head, body = _split_headers(chunk)
        headers = _parse_headers(head)
        part_type = headers.get("content-type", "")
        if "multipart/mixed" in part_type:
            inner = _boundary_of(part_type)
            if inner:
                results.extend(_parse_multipart(body, inner.encode("ascii")))
            continue
        results.append(_parse_http_payload(body))
    return results


def _split_headers(data: bytes) -> tuple[bytes, bytes]:
    for separator in (b"\r\n\r\n", b"\n\n"):
        if separator in data:
            head, _, rest = data.partition(separator)
            return head, rest
    return data, b""


def _parse_headers(head: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in head.decode("utf-8", errors="replace").splitlines():
        name, _, value = line.partition(":")
        if _ and name.strip():
            headers[name.strip().lower()] = value.strip()
    return headers


def _parse_http_payload(data: bytes) -> dict[str, Any]:
    data = data.lstrip(b"\r\n")
    head, body = _split_headers(data)
    lines = head.decode("utf-8", errors="replace").splitlines()
    status_line = lines[0] if lines else ""
    status, reason = 0, status_line
    parts = status_line.split(None, 2)
    if len(parts) >= 2 and parts[1].isdigit():
        status = int(parts[1])
        reason = parts[2] if len(parts) == 3 else ""
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if _ and name.strip():
            headers[name.strip().lower()] = value.strip()
    text = body.decode("utf-8-sig", errors="replace").strip()
    try:
        parsed: Any = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = None
    return {"status": status, "reason": reason, "headers": headers,
            "body": text, "json": parsed}
