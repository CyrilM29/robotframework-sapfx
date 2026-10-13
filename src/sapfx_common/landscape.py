"""Cartographie des interfaces d'un système SAP : le modèle, logique pure.

Un relevé de paysage est un arbre de NŒUDS (groupe, entité, domaine,
application, système SAP, mandant, couche d'interface, objet SAP, puis
fonction, programme, transaction ou table), chacun avec son parent, et une
liste d'INTERFACES qui relient un tiers à des objets SAP. Chaque interface
porte ce que SAP DÉCLARE (destination, profil partenaire, service enregistré),
ce qui a été OBSERVÉ sur la fenêtre (un volume, ou ``None`` quand la source
n'a pas pu être lue) et ce que le référentiel du client DOCUMENTE.

Le verdict est une règle, jamais un modèle de langage : ``confirmed`` exige
deux sources indépendantes, un volume illisible donne ``not_measured`` et
jamais zéro, une interface que SAP ne peut pas voir reste ``out_of_reach``.
L'outil fait remonter ce que l'architecte doit vérifier, il ne tranche rien.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

SCHEMA = "sapfx.landscape/1"

NODE_KINDS = (
    "group", "entity", "domain", "application", "platform", "system", "partner",
    "sap_system", "client", "layer",
    "service", "icf_node", "destination", "caller", "idoc_type", "message",
    "job", "channel", "inventory",
    "function", "program", "transaction", "table", "cds_view", "entity_set",
    "logical_path", "process_code", "tile", "intent", "catalog", "fiori_app", "traffic",
)
SCOPES = ("group", "internal", "external", "sap")
DIRECTIONS = ("inbound", "outbound", "both", "unknown")
STATUSES = ("confirmed", "active", "to_verify", "undocumented", "dormant",
            "unreachable", "not_served", "not_found", "out_of_reach", "not_measured")
# Gravité pour colorer un nœud porteur de plusieurs interfaces : le pire gagne.
STATUS_RANK = {"not_served": 8, "unreachable": 8, "not_found": 8, "undocumented": 7, "not_measured": 6,
               "to_verify": 5, "out_of_reach": 4, "dormant": 3, "active": 2, "confirmed": 1}
LAYER_ORDER = ("gateway", "icf", "rfc", "idoc", "jobs", "events")

__all__ = [
    "SCHEMA", "NODE_KINDS", "SCOPES", "DIRECTIONS", "STATUSES", "STATUS_RANK", "LAYER_ORDER",
    "interface_verdict", "build_landscape", "landscape_summary", "node_path",
    "children_of", "interfaces_of_node", "worst_status", "compare_landscapes",
]


def _text(value: Any, field: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("%s est vide." % field)
    return text


def _sources(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = [part for part in value.split(",")]
    return sorted({str(part).strip() for part in value if str(part).strip()})


def interface_verdict(declared_sources: Any = None, observed_count: Any = None,
                      observed_sources: Any = None, documented: Any = None,
                      reachable: Any = None, served: Any = None,
                      expected_in_sap: Any = False) -> dict[str, Any]:
    """Le verdict d'une interface, par une règle explicite.

    ``declared_sources`` : ce que SAP déclare (``RFCDES``, ``EDP13``…).
    ``observed_count`` : le volume sur la fenêtre, ``None`` = non mesuré.
    ``documented`` : ``True``/``False`` selon le référentiel, ``None`` quand
    aucun référentiel n'a été fourni. ``reachable``/``served`` à ``False``
    disent qu'une connexion a échoué ou qu'un service n'est pas publié.
    ``expected_in_sap`` : la ligne documentée porte un canal que SAP devrait
    montrer (RFC, IDoc, OData, HTTP) ; sans trace elle est ``not_found``,
    un écart réel, sinon ``out_of_reach`` (SAP ne peut pas la voir).
    Rend ``{status, reasons, sources}``.
    """
    declared = _sources(declared_sources)
    observed = _sources(observed_sources)
    sources = sorted(set(declared) | set(observed))
    reasons: list[str] = []
    if not sources:
        if documented is True and expected_in_sap:
            return {"status": "not_found", "sources": [],
                    "reasons": ["documentée, canal porté par SAP, introuvable dans le système"]}
        if documented is True:
            return {"status": "out_of_reach", "sources": [],
                    "reasons": ["documentée, aucune trace possible côté SAP"]}
        raise ValueError("Une interface sans aucune source ni documentation n'existe pas : "
                         "il faut une source SAP, une observation ou une ligne du référentiel.")
    if served is False:
        return {"status": "not_served", "sources": sources, "reasons": ["déclarée, non servie"]}
    if reachable is False:
        return {"status": "unreachable", "sources": sources, "reasons": ["déclarée, non joignable"]}
    if observed_count is None or observed_count == "":
        return {"status": "not_measured", "sources": sources,
                "reasons": ["activité non mesurée : source illisible ou absente, jamais zéro"]}
    try:
        count = int(observed_count)
    except (TypeError, ValueError):
        raise ValueError("observed_count doit être un entier ou None, reçu %r." % (observed_count,))
    if count < 0:
        raise ValueError("observed_count négatif : %d." % count)
    if count == 0:
        reasons.append("aucune activité sur la fenêtre")
        return {"status": "dormant", "sources": sources, "reasons": reasons}
    if documented is False:
        return {"status": "undocumented", "sources": sources,
                "reasons": ["active, absente du référentiel"]}
    if documented is None:
        return {"status": "active", "sources": sources,
                "reasons": ["active, référentiel non fourni"]}
    if len(sources) < 2:
        return {"status": "to_verify", "sources": sources,
                "reasons": ["documentée et active, mais une seule source : deux sont exigées"]}
    return {"status": "confirmed", "sources": sources,
            "reasons": ["documentée, active, %d sources indépendantes" % len(sources)]}


def _check_nodes(nodes: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in nodes:
        node = dict(raw)
        node["id"] = _text(node.get("id"), "id de nœud")
        if node["id"] in seen:
            raise ValueError("Nœud en double : %s." % node["id"])
        seen.add(node["id"])
        node["name"] = _text(node.get("name"), "nom du nœud %s" % node["id"])
        if node.get("kind") not in NODE_KINDS:
            raise ValueError("Nœud %s : type %r inconnu, attendus : %s."
                             % (node["id"], node.get("kind"), ", ".join(NODE_KINDS)))
        node["parent"] = node.get("parent") or None
        if node.get("scope") not in (None, *SCOPES):
            raise ValueError("Nœud %s : périmètre %r inconnu." % (node["id"], node.get("scope")))
        node["illustrative"] = bool(node.get("illustrative", False))
        out.append(node)
    by_id = {node["id"]: node for node in out}
    for node in out:
        parent, hops = node["parent"], 0
        if parent is not None and parent not in by_id:
            raise ValueError("Nœud %s : parent %s introuvable." % (node["id"], parent))
        while parent is not None:
            hops += 1
            if hops > len(out):
                raise ValueError("Cycle de parenté autour de %s." % node["id"])
            parent = by_id[parent]["parent"]
    return out


def _check_interface(raw: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    item = dict(raw)
    item["id"] = _text(item.get("id"), "id d'interface")
    if item.get("direction", "unknown") not in DIRECTIONS:
        raise ValueError("Interface %s : sens %r inconnu." % (item["id"], item.get("direction")))
    item.setdefault("direction", "unknown")
    party = _text(item.get("party"), "tiers de l'interface %s" % item["id"])
    refs = [party, *list(item.get("sap_objects") or []),
            *list(filter(None, [item.get("via"), item.get("owner")]))]
    for ref in refs:
        if ref not in by_id:
            raise ValueError("Interface %s : nœud %s introuvable." % (item["id"], ref))
    item["sap_objects"] = list(item.get("sap_objects") or [])
    observed = dict(item.get("observed") or {})
    verdict = interface_verdict(item.get("declared_sources"), observed.get("count"),
                                observed.get("sources"), item.get("documented"),
                                item.get("reachable"), item.get("served"), item.get("expected_in_sap"))
    item["declared_sources"] = _sources(item.get("declared_sources"))
    observed["sources"] = _sources(observed.get("sources"))
    item["observed"] = observed
    item.update(verdict)
    item["self_loop"] = bool(item.get("self_loop", False))
    item["illustrative"] = bool(item.get("illustrative", False))
    return item


def build_landscape(target: Mapping[str, Any], window: Mapping[str, Any],
                    nodes: Iterable[Mapping[str, Any]], interfaces: Iterable[Mapping[str, Any]],
                    limits: Any = None) -> dict[str, Any]:
    """Assemble et VALIDE un relevé : ids uniques, parents existants, aucun
    cycle, références d'interface résolues, verdict calculé pour chacune.
    L'ordre des nœuds est conservé : c'est l'ordre de lecture des rendus."""
    checked = _check_nodes(nodes)
    by_id = {node["id"]: node for node in checked}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in interfaces:
        item = _check_interface(raw, by_id)
        if item["id"] in seen:
            raise ValueError("Interface en double : %s." % item["id"])
        seen.add(item["id"])
        items.append(item)
    return {"schema": SCHEMA, "target": dict(target), "window": dict(window),
            "nodes": checked, "interfaces": items, "limits": list(limits or [])}


def children_of(model: Mapping[str, Any], node_id: Any) -> list[dict[str, Any]]:
    """Les enfants directs d'un nœud, dans l'ordre du relevé (``None`` = racines)."""
    return [node for node in model["nodes"] if node["parent"] == node_id]


def node_path(model: Mapping[str, Any], node_id: str) -> list[str]:
    """Les noms de la racine jusqu'au nœud : la lignée parent → enfant."""
    by_id = {node["id"]: node for node in model["nodes"]}
    if node_id not in by_id:
        raise ValueError("Nœud %s introuvable." % node_id)
    names: list[str] = []
    current: Any = node_id
    while current is not None:
        names.append(by_id[current]["name"])
        current = by_id[current]["parent"]
    return list(reversed(names))


def interfaces_of_node(model: Mapping[str, Any], node_id: str) -> list[dict[str, Any]]:
    """Les interfaces qui touchent un nœud, comme tiers, relais, application
    porteuse (``owner``, celle qui porte un bouclage) ou objet SAP."""
    return [item for item in model["interfaces"]
            if node_id in (item["party"], item.get("via"), item.get("owner")) or node_id in item["sap_objects"]]


def worst_status(statuses: Iterable[str]) -> str | None:
    """Le statut le plus grave d'une liste, ``None`` si elle est vide."""
    ranked = [status for status in statuses if status in STATUS_RANK]
    return max(ranked, key=lambda status: STATUS_RANK[status]) if ranked else None


def landscape_summary(model: Mapping[str, Any]) -> dict[str, Any]:
    """Les chiffres clés : interfaces par statut, tiers reliés par périmètre,
    objets techniques par type, nœuds sans aucune interface."""
    by_id = {node["id"]: node for node in model["nodes"]}
    statuses = {status: 0 for status in STATUSES}
    parties: set[str] = set()
    for item in model["interfaces"]:
        statuses[item["status"]] += 1
        if not item["self_loop"]:
            parties.add(item["party"])
            if item.get("via"):
                parties.add(item["via"])
    scopes = {scope: 0 for scope in SCOPES}
    for party in parties:
        scope = by_id[party].get("scope")
        if scope in scopes:
            scopes[scope] += 1
    tech_kinds = NODE_KINDS[NODE_KINDS.index("service"):]
    kinds: dict[str, int] = {}
    for node in model["nodes"]:
        if node["kind"] in tech_kinds:
            kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
    touched = {ref for item in model["interfaces"]
               for ref in (item["party"], item.get("via"), item.get("owner"), *item["sap_objects"]) if ref}
    unlinked = sorted(node["id"] for node in model["nodes"]
                      if node["kind"] in ("application", "platform", "system", "partner")
                      and node["id"] not in touched)
    return {"interfaces": len(model["interfaces"]), "statuses": statuses,
            "linked_parties": len(parties), "scopes": scopes, "object_kinds": kinds,
            "self_loops": sum(1 for item in model["interfaces"] if item["self_loop"]),
            "unlinked_systems": unlinked,
            "illustrative_nodes": sum(1 for node in model["nodes"] if node["illustrative"])}


def compare_landscapes(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    """Ce qui a bougé entre deux relevés : nœuds et interfaces apparus ou
    disparus, statuts changés, interfaces appariées par leur clé stable. Deux cibles différentes se comparent aussi
    (DEV contre PRD) : la comparaison le dit, elle ne le refuse pas."""
    nodes_a = {node["id"] for node in a["nodes"]}
    nodes_b = {node["id"] for node in b["nodes"]}
    # La clé stable (``key``) apparie deux relevés ; le numéro affiché (``id``)
    # est séquentiel et désignerait une autre interface d'un relevé à l'autre.
    items_a = {item.get("key") or item["id"]: item for item in a["interfaces"]}
    items_b = {item.get("key") or item["id"]: item for item in b["interfaces"]}
    changed = [{"id": key, "from": items_a[key]["status"], "to": items_b[key]["status"]}
               for key in sorted(set(items_a) & set(items_b))
               if items_a[key]["status"] != items_b[key]["status"]]
    return {"same_target": dict(a.get("target", {})) == dict(b.get("target", {})),
            "nodes_added": sorted(nodes_b - nodes_a), "nodes_removed": sorted(nodes_a - nodes_b),
            "interfaces_added": sorted(set(items_b) - set(items_a)),
            "interfaces_removed": sorted(set(items_a) - set(items_b)),
            "status_changes": changed}
