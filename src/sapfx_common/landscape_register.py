"""Cartographie SAP : rapprocher le relevé d'un système des sources du client.

Deux sources que SAP ne connaît pas, fournies par le client et jamais
devinées (backlog § 2.76, lot 3) :

- la CARTOGRAPHIE APPLICATIVE : groupe, entités, domaines, applications,
  partenaires, une ligne par nœud avec son parent ; l'entité qui exploite le
  système relevé porte ``sap_system`` (``A4H`` ou ``A4H-754`` quand deux
  systèmes partagent le SID) ;
- le RÉFÉRENTIEL D'INTERFACES : une ligne par interface documentée, son tiers
  (un id de la cartographie), son canal et l'objet SAP qui la porte.

Le rapprochement est une RÈGLE sur les clés stables du relevé, jamais un
modèle de langage : ``RFC`` sur le nom de destination, ``IDOC`` sur le sens,
le type de message et le partenaire, ``ODATA`` sur le service, ``HTTP`` sur le
chemin, ``RFCIN`` sur l'hôte appelant. Trois issues, toutes nommées :

- RAPPROCHÉE : l'interface du relevé devient documentée, son tiers est celui
  de la cartographie ;
- SAP SEULEMENT : une interface relevée qu'aucune ligne ne documente devient
  ``documented: False``, donc « non documentée » si elle est active ; les
  bouclages et l'agrégat des services standard restent non jugés ;
- RÉFÉRENTIEL SEULEMENT : une ligne sans trace dans SAP devient une interface
  sans source, documentée : « introuvable dans SAP » (``not_found``) pour un
  canal que SAP devrait porter (RFC, IDoc, OData, HTTP), un écart réel ; « hors
  portée » pour un canal qu'il ne peut pas voir (événements, fichiers).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["APP_KINDS", "SAP_CHANNELS", "register_key", "apply_application_map", "reconcile_register"]

APP_KINDS = ("group", "entity", "domain", "application", "platform", "system", "partner")
SAP_CHANNELS = ("RFC", "IDOC", "ODATA", "HTTP", "RFCIN")
UNJUDGED_KEYS = ("ODATA:*",)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def register_key(row: Mapping[str, Any]) -> str:
    """La clé stable qu'une ligne du référentiel doit retrouver dans le relevé,
    ou chaîne vide pour un canal que SAP ne porte pas (événements, fichiers)."""
    channel = _clean(row.get("channel")).upper()
    obj = _clean(row.get("sap_object"))
    if channel == "IDOC":
        direction = "OUT" if _clean(row.get("direction")).lower() == "outbound" else "IN"
        return "IDOC:%s:%s:%s" % (direction, obj, _clean(row.get("partner")))
    if channel in SAP_CHANNELS and obj:
        return "%s:%s" % (channel, obj)
    return ""


def _target_label(target: Mapping[str, Any]) -> tuple[str, str]:
    sid = _clean(target.get("system")).upper()
    return sid, "%s-%s" % (sid, _clean(target.get("basis_release")))


def apply_application_map(raw: Mapping[str, Any], apps: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Remplace les emplacements « à qualifier » du relevé par la cartographie
    applicative : le système SAP passe sous l'entité qui le déclare, les tiers
    relevés restent dans un domaine « absents de la cartographie »."""
    rows = [dict(r) for r in apps]
    ids = {_clean(r.get("id")) for r in rows}
    sid, sid_rel = _target_label(raw.get("target", {}))
    host = ""
    for row in rows:
        if _clean(row.get("kind")) not in APP_KINDS:
            raise ValueError("Cartographie : nœud %s de type %r inconnu, attendus : %s."
                             % (row.get("id"), row.get("kind"), ", ".join(APP_KINDS)))
        parent = _clean(row.get("parent"))
        if parent and parent not in ids:
            raise ValueError("Cartographie : nœud %s, parent %s introuvable." % (row.get("id"), parent))
        declared = _clean(row.get("sap_system")).upper()
        if declared and declared in (sid, sid_rel):
            if host:
                raise ValueError("Cartographie : deux entités déclarent le système %s (%s et %s) ; "
                                 "écrire SID-release pour les distinguer." % (sid, host, row["id"]))
            host = _clean(row.get("id"))
    if not host:
        raise ValueError("Cartographie : aucune entité ne déclare le système %s (colonne sap_system)." % sid_rel)
    nodes = [{"id": "app:" + _clean(r["id"]), "parent": "app:" + _clean(r["parent"]) if _clean(r.get("parent")) else None,
              "name": _clean(r.get("name")) or _clean(r["id"]), "kind": _clean(r["kind"]),
              **({"scope": _clean(r["scope"])} if _clean(r.get("scope")) else {}),
              **({"illustrative": True} if _clean(r.get("illustrative")).lower() in ("1", "x", "true", "oui") else {}),
              **({"notes": [_clean(r["notes"])]} if _clean(r.get("notes")) else {})}
             for r in rows]
    kept = []
    for node in raw["nodes"]:
        if node["id"] in ("g", "ent"):
            continue
        node = dict(node)
        if node["id"] in ("sap", "d_third"):
            node["parent"] = "app:" + host
        if node["id"] == "d_third":
            node["name"] = "Tiers vus depuis SAP, absents de la cartographie"
        kept.append(node)
    out = dict(raw)
    out["nodes"] = nodes + kept
    out["limits"] = [x for x in raw.get("limits", []) if not x.startswith("Les niveaux groupe")]
    return out


def reconcile_register(raw: Mapping[str, Any], register: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Rapproche le référentiel d'interfaces du relevé (cartographie déjà
    appliquée) et rend une nouvelle entrée, plus ``target.reconciliation``."""
    node_ids = {n["id"] for n in raw["nodes"]}
    items = [dict(i) for i in raw["interfaces"]]
    by_key = {i.get("key"): i for i in items if i.get("key")}
    matched: list[str] = []
    register_only: list[str] = []
    seen_refs: set[str] = set()
    for row in register:
        ref = _clean(row.get("ref"))
        if not ref or ref in seen_refs:
            raise ValueError("Référentiel : référence vide ou en double (%r)." % ref)
        seen_refs.add(ref)
        party = "app:" + _clean(row.get("party"))
        if party not in node_ids:
            raise ValueError("Référentiel %s : tiers %s absent de la cartographie." % (ref, row.get("party")))
        key = register_key(row)
        found = by_key.get(key) if key else None
        if found is not None:
            found.update(documented=True, register_ref=ref, label="%s (%s)" % (_clean(row.get("name")) or ref,
                                                                               found.get("label", key)))
            if found.get("self_loop"):
                found["owner"] = party  # le tiers d'un bouclage reste le système lui-même
            else:
                found["party"] = party
            matched.append(ref)
            continue
        channel = _clean(row.get("channel")).upper()
        note = ("déclarée au référentiel, introuvable dans SAP (%s)" % key) if key else \
               "canal %s : aucune trace possible côté SAP" % (channel or "?")
        items.append({"key": "REG:" + ref, "label": _clean(row.get("name")) or ref, "party": party,
                      "sap_objects": [], "channel": channel or "?",
                      "direction": _clean(row.get("direction")).lower() or "unknown",
                      "declared_sources": [], "observed": {"count": None, "sources": [], "note": note},
                      "documented": True, "register_ref": ref, "expected_in_sap": bool(key)})
        register_only.append(ref)
    sap_only = []
    for item in items:
        if "register_ref" in item or item.get("self_loop") or item.get("key") in UNJUDGED_KEYS:
            continue
        item["documented"] = False
        sap_only.append(item.get("key", item.get("label", "")))
    numbered = []
    for n, item in enumerate(items, start=1):
        item["id"] = "I%02d" % n
        numbered.append(item)
    used = {i["party"] for i in numbered} | {i.get("via") for i in numbered}
    nodes = [n for n in raw["nodes"]
             if not (n["id"].startswith(("p_dst_", "p_ls_", "p_rfcin_", "p_http")) and n["id"] not in used)]
    if not any(n["parent"] == "d_third" for n in nodes):
        nodes = [n for n in nodes if n["id"] != "d_third"]
    target = dict(raw.get("target", {}))
    target["reconciliation"] = {"matched": matched, "register_only": register_only, "sap_only": sap_only}
    out = dict(raw)
    out.update(nodes=nodes, interfaces=numbered, target=target)
    out["limits"] = ["Rapprochement : %d interface(s) rapprochée(s), %d relevée(s) sans ligne au référentiel, "
                     "%d documentée(s) sans trace dans SAP." % (len(matched), len(sap_only), len(register_only))] + \
        [x for x in raw.get("limits", []) if not x.startswith("Aucun référentiel")]
    return out
