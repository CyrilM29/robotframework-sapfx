"""Ce qu'un chemin OData désigne : le service, l'entity set, la clé (backlog
2.83, lot 2, 2026-10-20).

Les keywords OData de ``SapApiLibrary`` ne prennent pas un ``entity_set`` : ils
prennent un CHEMIN (``/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner``)
où le service et l'entity set sont noyés. ``parse_odata_path`` les en extrait,
pour les outils de couverture (une matrice de traçabilité), pour le journal
des touches et pour la garde de politique.

Règle maison : une valeur qu'on ne sait pas lire reste INCONNUE, jamais
devinée. Deux préfixes SAP sont reconnus par leur structure (``odata`` en v2,
``odata4`` en v4). Pour tout autre chemin (un service CAP sous ``/processor``),
le service ne se déduit pas du seul texte : l'appelant donne les racines de
service qu'il connaît (``service_roots``, les valeurs des arguments
``ODataServicePath`` de la suite) ; sans elles, ``confidence`` vaut
``unresolved`` et le service comme l'entity set restent ``None``.

``entity_set`` est le PREMIER segment de ressource après la racine du service :
un entity set, ou un function import quand le service en déclare un (seul le
``$metadata`` tranche).

Typed.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional
from urllib.parse import urlsplit

__all__ = ["parse_odata_path", "odata_service_root"]

_V2 = re.compile(
    r"^/sap/opu/odata/(?P<namespace>[^/;]+)/(?P<name>[^/;]+)(?P<version>;[^/]*)?"
    r"(?P<rest>/.*)?$", re.IGNORECASE)
_V4 = re.compile(
    r"^/sap/opu/odata4/(?P<namespace>[^/]+)/(?P<binding>[^/]+)/(?P<repository>[^/]+)"
    r"/(?P<namespace2>[^/]+)/(?P<name>[^/]+)/(?P<version>\d{1,4})(?P<rest>/.*)?$",
    re.IGNORECASE)
_SYSTEM_SEGMENTS = ("$count", "$value", "$ref", "$metadata", "$batch")


def _path_only(value: Any) -> str:
    """Le chemin d'une adresse ou d'un chemin, sans requête, sans ancre et sans
    barre finale, avec une barre initiale."""
    text = str(value or "").strip()
    if "://" in text:
        text = urlsplit(text).path
    text = re.split(r"[?#]", text, maxsplit=1)[0].strip()
    if not text:
        return ""
    text = re.sub(r"/{2,}", "/", text if text.startswith("/") else "/" + text)
    return text.rstrip("/") or "/"


def _split_segments(rest: str) -> list[str]:
    """Les segments d'un chemin, sans couper une clé entre parenthèses
    (``Products('a/b')``)."""
    segments: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ""
    for char in rest:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in ("'", '"') and depth > 0:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "/" and depth == 0:
            if current:
                segments.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        segments.append("".join(current))
    return segments


def _name_and_key(segment: str) -> tuple[str, Optional[str]]:
    if "(" in segment and segment.endswith(")"):
        name, _, key = segment.partition("(")
        return name, key[:-1]
    return segment, None


def _resource(rest: str) -> dict[str, Any]:
    entity_set: Optional[str] = None
    key: Optional[str] = None
    system: Optional[str] = None
    navigation: list[str] = []
    segments = _split_segments(rest)
    for index, segment in enumerate(segments):
        if segment.lower() in _SYSTEM_SEGMENTS:
            system = system or segment.lower()
            continue
        name, segment_key = _name_and_key(segment)
        if index == 0 and entity_set is None:
            entity_set, key = name, segment_key
        else:
            navigation.append(name)
    return {"entity_set": entity_set, "key": key, "navigation": navigation,
            "system": system}


def _empty(path: str, reason: str) -> dict[str, Any]:
    return {"path": path, "confidence": "unresolved", "version": None,
            "namespace": None, "service": None, "service_root": None,
            "entity_set": None, "key": None, "navigation": [], "system": None,
            "reason": reason}


def parse_odata_path(path: Any, service_roots: Iterable[Any] = ()) -> dict[str, Any]:
    """Ce que ``path`` désigne : ``{path, confidence, version, namespace,
    service, service_root, entity_set, key, navigation, system, reason}``.

    ``confidence`` : ``sap_prefix`` (chemin ``/sap/opu/odata`` ou
    ``/sap/opu/odata4``, lu par sa structure), ``known_root`` (le chemin
    commence par une racine de ``service_roots``) ou ``unresolved``. Une
    adresse complète est ramenée à son chemin, la requête (``?$filter=...``)
    est ignorée. ``system`` vaut ``$metadata``, ``$batch``, ``$count``,
    ``$value`` ou ``$ref`` quand le chemin en porte un, ``entity_set`` reste
    ``None`` pour ``$metadata`` et ``$batch``."""
    normalized = _path_only(path)
    if not normalized or normalized == "/":
        return _empty(normalized, "chemin vide")
    if any(marker in str(path) for marker in ("${", "@{", "&{", "%{")):
        return _empty(normalized, "variable Robot non résolue")
    roots = sorted({_path_only(root) for root in service_roots if _path_only(root) not in ("", "/")},
                   key=len, reverse=True)
    for root in roots:
        if normalized.lower() == root.lower() or normalized.lower().startswith(root.lower() + "/"):
            parsed = _resource(normalized[len(root):])
            return {"path": normalized, "confidence": "known_root", "version": None,
                    "namespace": None, "service": root.rsplit("/", 1)[-1],
                    "service_root": root, "reason": "", **parsed}
    for version, pattern in (("v4", _V4), ("v2", _V2)):
        match = pattern.match(normalized)
        if match:
            parts = match.groupdict()
            root = normalized[:len(normalized) - len(parts.get("rest") or "")]
            parsed = _resource(parts.get("rest") or "")
            return {"path": normalized, "confidence": "sap_prefix", "version": version,
                    "namespace": parts["namespace"], "service": parts["name"],
                    "service_root": root, "reason": "", **parsed}
    return _empty(normalized, "service non reconnu : donner service_roots, ou un chemin "
                              "/sap/opu/odata ou /sap/opu/odata4")


def odata_service_root(path: Any, service_roots: Iterable[Any] = ()) -> Optional[str]:
    """La racine du service qu'un chemin désigne, ou ``None``."""
    return parse_odata_path(path, service_roots)["service_root"]
