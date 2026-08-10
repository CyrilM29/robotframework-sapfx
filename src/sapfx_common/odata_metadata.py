"""Perception du canal API : parsing du ``$metadata`` OData (v2 ET v4).

Le canal API n'a pas d'écran : sa « signature d'écran », c'est le document
``$metadata`` du service (entity sets, clés, propriétés, libellés
``sap:label``) et le catalogue Gateway (la liste des services actifs). Ce
module est la logique PURE de cette perception : parsing XML (stdlib
``xml.etree``), extraction tolérante aux espaces de noms (v2
``schemas.microsoft.com``, v4 ``docs.oasis-open.org``), recherche de
propriété par libellé humain (le pendant API des localisateurs par libellé
du canal GUI) et simplification des entrées du catalogue de services. Les
E/S HTTP restent dans ``SapApiLibrary``.

Contrat d'ambiguïté maison : ``find_property_by_label`` retourne TOUS les
candidats, jamais un premier-match silencieux ; l'appelant tranche.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence
from xml.etree import ElementTree


def _local(tag: str) -> str:
    """Nom local d'un tag XML, sans son espace de noms (``{ns}Nom`` -> ``Nom``)."""
    return tag.rsplit("}", 1)[-1]


def _attr_local(element: ElementTree.Element, name: str) -> Optional[str]:
    """Valeur du premier attribut dont le nom LOCAL est ``name`` (les libellés
    SAP arrivent en ``sap:label``, c'est-à-dire ``{http://www.sap.com/...}label``)."""
    for attr, value in element.attrib.items():
        if attr.rsplit("}", 1)[-1] == name:
            return value
    return None


def parse_metadata(xml_text: str) -> dict[str, Any]:
    """Parse un document ``$metadata`` OData v2 ou v4 en dict JSON-safe :
    ``{"version", "entity_sets": {nom: {"entity_type", "keys", "properties"}},
    "function_imports": [...], "actions": [...]}``.

    Chaque propriété porte ``{"type", "nullable", "label"}`` (``label`` =
    ``sap:label`` v2 ou annotation absente -> ``None``). Tolérant aux espaces
    de noms : le matching se fait sur les noms locaux, jamais sur les URLs de
    schéma (qui varient entre versions et implémentations).
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as err:
        raise ValueError(
            "Document $metadata illisible en XML (%s) : le chemin pointe-t-il "
            "bien la racine du service (…/<SERVICE>/$metadata) ?" % err)

    version = root.get("Version")
    entity_types: dict[str, dict[str, Any]] = {}
    entity_sets: dict[str, dict[str, Any]] = {}
    function_imports: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    for schema in (el for el in root.iter() if _local(el.tag) == "Schema"):
        namespace = schema.get("Namespace") or ""
        alias = schema.get("Alias")
        for element in schema:
            local = _local(element.tag)
            if local == "EntityType":
                parsed = _parse_entity_type(element)
                name = element.get("Name") or ""
                entity_types["%s.%s" % (namespace, name)] = parsed
                if alias:
                    entity_types["%s.%s" % (alias, name)] = parsed
            elif local == "EntityContainer":
                for item in element:
                    item_local = _local(item.tag)
                    if item_local == "EntitySet":
                        entity_sets[item.get("Name") or ""] = {
                            "entity_type": item.get("EntityType") or ""}
                    elif item_local == "FunctionImport":
                        function_imports.append({
                            "name": item.get("Name"),
                            "http_method": _attr_local(item, "HttpMethod") or "GET",
                            "return_type": item.get("ReturnType"),
                        })
                    elif item_local == "ActionImport":
                        actions.append({"kind": "action_import",
                                        "name": item.get("Name"),
                                        "target": item.get("Action")})
            elif local in ("Action", "Function"):
                actions.append({
                    "kind": local.lower(),
                    "name": element.get("Name"),
                    "bound": (element.get("IsBound", "false").lower() == "true"),
                })

    for info in entity_sets.values():
        entity_type = _resolve_type(entity_types, info["entity_type"])
        info["keys"] = list(entity_type.get("keys", []))
        info["properties"] = entity_type.get("properties", {})

    if version in (None, "1.0") and "schemas.microsoft.com/ado" in xml_text:
        # L'edmx v2 s'annonce Version="1.0" : la version OData utile est 2.0.
        version = "2.0"
    return {
        "version": version,
        "entity_sets": entity_sets,
        "function_imports": function_imports,
        "actions": actions,
    }


def _parse_entity_type(element: ElementTree.Element) -> dict[str, Any]:
    keys: list[str] = []
    properties: dict[str, dict[str, Any]] = {}
    for sub in element:
        local = _local(sub.tag)
        if local == "Key":
            keys = [ref.get("Name") or "" for ref in sub
                    if _local(ref.tag) == "PropertyRef"]
        elif local == "Property":
            properties[sub.get("Name") or ""] = {
                "type": sub.get("Type"),
                "nullable": (sub.get("Nullable", "true").lower() != "false"),
                "label": _attr_local(sub, "label"),
            }
    return {"keys": keys, "properties": properties}


def _resolve_type(entity_types: dict[str, dict[str, Any]],
                  full_name: str) -> dict[str, Any]:
    """Résout ``NS.Type`` avec repli sur le nom local seul (les conteneurs v2
    référencent parfois le type via l'alias du schéma)."""
    if full_name in entity_types:
        return entity_types[full_name]
    short = full_name.rsplit(".", 1)[-1]
    for known, parsed in entity_types.items():
        if known.rsplit(".", 1)[-1] == short:
            return parsed
    return {"keys": [], "properties": {}}


def find_property_by_label(metadata: dict[str, Any], label: str,
                           entity_set: Optional[str] = None) -> list[dict[str, Any]]:
    """Cherche les propriétés dont le ``sap:label`` correspond à ``label``
    (exact insensible à la casse d'abord, puis sous-chaîne). Retourne TOUS les
    candidats ``{"entity_set", "property", "label", "type", "match"}`` : le
    contrat d'ambiguïté maison, l'appelant tranche, jamais de premier-match
    silencieux. Liste vide si rien ne correspond."""
    wanted = label.strip().casefold()
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    sets = metadata.get("entity_sets", {})
    for set_name, info in sorted(sets.items()):
        if entity_set is not None and set_name != entity_set:
            continue
        for prop_name, prop in sorted(info.get("properties", {}).items()):
            prop_label = (prop.get("label") or "").strip()
            if not prop_label:
                continue
            candidate = {"entity_set": set_name, "property": prop_name,
                         "label": prop_label, "type": prop.get("type")}
            folded = prop_label.casefold()
            if folded == wanted:
                exact.append(dict(candidate, match="exact"))
            elif wanted and wanted in folded:
                partial.append(dict(candidate, match="partial"))
    return exact if exact else partial


def known_labels(metadata: dict[str, Any], limit: int = 20) -> list[str]:
    """Échantillon trié des libellés présents dans le service (pour rendre un
    échec de recherche actionnable : « aucun libellé X ; libellés connus : … »)."""
    labels = sorted({
        (prop.get("label") or "").strip()
        for info in metadata.get("entity_sets", {}).values()
        for prop in info.get("properties", {}).values()
        if (prop.get("label") or "").strip()})
    return labels[:limit]


_CATALOG_FIELDS = (
    ("id", ("ID", "Id")),
    ("title", ("Title", "Description")),
    ("technical_name", ("TechnicalServiceName", "TechnicalName")),
    ("service_url", ("ServiceUrl", "ServiceURL", "Url")),
    ("version", ("TechnicalServiceVersion", "Version")),
)


def simplify_catalog_entries(entries: Sequence[Any]) -> list[dict[str, Any]]:
    """Réduit les entrées du catalogue Gateway (``ServiceCollection``) à un
    dict stable ``{"id", "title", "technical_name", "service_url", "version"}``
    par service, tolérant aux variations de casse des propriétés entre
    versions de Gateway. Les entrées non-dict sont ignorées."""
    simplified: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        row: dict[str, Any] = {}
        for target, candidates in _CATALOG_FIELDS:
            value = None
            for name in candidates:
                if name in entry:
                    value = entry[name]
                    break
            row[target] = value
        simplified.append(row)
    return simplified
