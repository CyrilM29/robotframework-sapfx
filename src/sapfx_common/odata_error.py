"""Corps d'une réponse d'erreur OData de la Gateway SAP, logique pure.

Né du scénario 11 (2026-10-07, a4h, release 754) : le corps d'une erreur
Gateway porte, en plus du message, l'identifiant de TRANSACTION et
l'horodatage de la requête (``innererror``), les mêmes que la Gateway écrit
dans son journal d'erreurs (``/IWFND/SU_ERRLOG``, champs ``TRANSACTION_ID``
et ``TIMESTAMP``). C'est le lien le plus fort entre ce que le client a reçu
et ce que le système a journalisé.

Formes mesurées : ``/IWFND/MED/170`` (service inexistant, HTTP 403, le code
est une identité de message ``CLASSE/NUMÉRO``) et le 404 d'une ressource
absente d'un service réel (le code y est un identifiant de texte, pas une
identité de message). Le corps arrive en JSON ou en XML selon la négociation.
Le ``message`` est localisé : il est rendu pour le lecteur, jamais pour une
assertion (convention n°3).

Typed.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Mapping, Optional

# Une identité de message SAP : classe (espace de noms compris) puis numéro.
_IDENTITY = re.compile(r"^(/?[A-Z0-9_]+(?:/[A-Z0-9_]+)*)/(\d{3})$")


def message_identity(code: Any) -> str:
    """``/IWFND/MED/170`` reste ``/IWFND/MED/170`` ; un code qui n'est pas une
    identité ``CLASSE/NUMÉRO`` (identifiant de texte d'un 404) rend vide."""
    text = "" if code is None else str(code).strip().upper()
    return text if _IDENTITY.match(text) else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _from_xml(body: str) -> Optional[dict[str, Any]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    if _local(root.tag) != "error":
        return None

    def first(name: str) -> str:
        for el in root.iter():
            if _local(el.tag) == name:
                return (el.text or "").strip()
        return ""
    return {"code": first("code"), "message": first("message"), "transaction_id": first("transactionid"),
            "timestamp": first("timestamp"), "service_id": first("service_id"),
            "service_version": first("service_version")}


def _from_json(body: str) -> Optional[dict[str, Any]]:
    try:
        doc = json.loads(body)
    except ValueError:
        return None
    err = doc.get("error") if isinstance(doc, dict) else None
    if not isinstance(err, dict):
        return None
    msg = err.get("message")
    inner_raw = err.get("innererror")
    inner: dict[str, Any] = inner_raw if isinstance(inner_raw, dict) else {}
    app_raw = inner.get("application")
    app: dict[str, Any] = app_raw if isinstance(app_raw, dict) else {}
    return {"code": str(err.get("code") or "").strip(),
            "message": str(msg.get("value", "") if isinstance(msg, dict) else msg or "").strip(),
            "transaction_id": str(inner.get("transactionid") or "").strip(),
            "timestamp": str(inner.get("timestamp") or "").strip(),
            "service_id": str(app.get("service_id") or "").strip(),
            "service_version": str(app.get("service_version") or "").strip()}


def parse_odata_error(response: Mapping[str, Any]) -> dict[str, Any]:
    """Depuis le dict de `Get Http Response` (``status``, ``body``), rend
    ``{status, code, message_identity, transaction_id, timestamp, service_id,
    service_version, message}``. ``transaction_id`` en majuscules, comme le
    journal l'écrit. Un statut de succès (inférieur à 400, ou absent : la
    requête n'a pas abouti) et un corps qui n'est pas une erreur OData (page
    HTML, corps vide ou tronqué) sont REFUSÉS en le disant, jamais rendus
    vides."""
    body = str(response.get("body") or "").strip()
    status = response.get("status")
    if not isinstance(status, int) or status < 400:
        raise AssertionError(
            "La réponse n'est pas une erreur HTTP (statut %r%s) : rien à lire comme erreur OData."
            % (status, ", %s" % response.get("error") if response.get("error") else ""))
    parsed = (_from_json(body) if body.startswith("{") else _from_xml(body)) if body else None
    if parsed is None:
        hint = " (corps tronqué : augmenter max_chars)" if response.get("truncated") else ""
        raise AssertionError(
            "La réponse (statut %s) ne porte pas d'erreur OData lisible%s : %r."
            % (status, hint, body[:160]))
    parsed["transaction_id"] = parsed["transaction_id"].upper()
    return {"status": status, "message_identity": message_identity(parsed["code"]), **parsed}
