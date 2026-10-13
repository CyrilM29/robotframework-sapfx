"""Cartographie SAP : assembler les relevés bruts d'un système en entrée du modèle.

La logique pure du relevé côté SAP. Le mixin RFC lit (destinations, profils
partenaire, trafic IDoc, registre Gateway, jobs, appels tRFC en échec,
statistiques de workload) ; ce module classe et assemble, sans aucun accès au
système, en une entrée que ``sapfx_common.landscape.build_landscape`` valide.

Trois règles de lecture, payées sur les deux images du banc (2026-10-12) :

- une destination n'est pas un tiers : les destinations TCP/IP de programmes
  (``%%SAPGUI%%``, ``%%RFCSERVER%%``) et les destinations internes se COMPTENT,
  elles ne deviennent pas des interfaces ; une destination vers le système
  lui-même (même hôte, ou sans hôte et nommée comme le système) est un BOUCLAGE ;
- une statistique d'appels absente n'est pas un zéro : le collecteur de workload
  peut ne plus tourner (images de démonstration figées au 2017-05-08), le
  volume est alors ``None`` avec la date du dernier relevé ;
- un trafic sans profil partenaire actuel reste une interface : c'est l'écart
  entre déclaré et observé que l'outil doit faire remonter.

Aucun référentiel n'est connu à ce stade : ``documented`` vaut ``None`` partout
(le lot 3 l'apporte), et les niveaux groupe, entité, domaine sont des
emplacements « à qualifier ».
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["classify_destination", "job_stem", "normalize_workload", "plan_workload_reads", "workload_note",
           "assemble_sap_landscape", "INTERFACE_DESTINATION_TYPES"]

INTERFACE_DESTINATION_TYPES = {"3": "RFC", "G": "HTTP", "H": "HTTP ABAP"}
PROGRAM_HOSTS = ("%%SAPGUI%%", "%%RFCSERVER%%")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def classify_destination(dest: Mapping[str, Any], own_hosts: Iterable[str],
                         own_names: Iterable[str]) -> dict[str, Any]:
    """Range une destination : ``external``, ``self``, ``program`` ou ``internal``.

    ``own_hosts`` : les noms d'hôte du système (application et base) ;
    ``own_names`` : son SID et ses systèmes logiques. Rend aussi le nom lisible
    du tiers (l'hôte, le dernier saut ``/H/`` d'une chaîne SAProuter).
    """
    name, kind, host = _clean(dest.get("destination")), _clean(dest.get("type")), _clean(dest.get("target_host"))
    hosts = {h.lower() for h in own_hosts if h}
    names = {n.upper() for n in own_names if n}
    if kind not in INTERFACE_DESTINATION_TYPES:
        role = "program" if kind == "T" else "internal"
        return {"role": role, "party": "", "channel": ""}
    if host.upper() in PROGRAM_HOSTS:
        return {"role": "program", "party": "", "channel": ""}
    if host.startswith("/H/"):
        hops = [part for part in host.split("/") if part]
        last = max(i for i, part in enumerate(hops) if part == "H")
        party = "%s (via SAProuter)" % hops[last + 1] if last + 1 < len(hops) else host
    else:
        party = host + (":%s" % _clean(dest.get("target_port")) if dest.get("target_port") else "")
    is_self = host.lower() in hosts or (not host and kind == "3" and name.upper() in names)
    if is_self:
        return {"role": "self", "party": "", "channel": INTERFACE_DESTINATION_TYPES[kind]}
    return {"role": "external", "party": party or "cible non déclarée (%s)" % name,
            "channel": INTERFACE_DESTINATION_TYPES[kind]}


def job_stem(jobname: str) -> str:
    """Le nom d'un job sans sa partie numérique variable (horodatage, compteur)."""
    match = re.match(r"^([^0-9]*?)[_-]?\d", jobname)
    stem = match.group(1) if match else jobname
    return (stem.rstrip("_-") + "_*") if match else stem


def normalize_workload(days: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    """Additionne les agrégats quotidiens de la collecte de workload.

    Chaque jour porte les tables de ``SWNC_COLLECTOR_GET_AGGREGATES`` :
    ``RFCCLNTDEST`` (appels SORTANTS par destination, champ ``TARGET``),
    ``RFCSRVRDEST`` (appels ENTRANTS, par destination distante et utilisateur)
    et ``WEBS`` (requêtes HTTP reçues, par chemin).
    """
    out: dict[str, dict[str, int]] = {"rfc_client": {}, "rfc_server": {}, "http_server": {}}

    def add(bucket: str, key: str, count: Any) -> None:
        if key:
            out[bucket][key] = out[bucket].get(key, 0) + int(_clean(count) or 0)

    for day in days:
        for row in day.get("RFCCLNTDEST") or []:
            add("rfc_client", _clean(row.get("TARGET")), row.get("COUNTER"))
        for row in day.get("RFCSRVRDEST") or []:
            add("rfc_server", "%s|%s" % (_clean(row.get("REMOT_DEST")), _clean(row.get("USERID"))),
                row.get("COUNTER"))
        for row in day.get("WEBS") or []:
            add("http_server", _clean(row.get("PATH")), row.get("COUNTER"))
    return out


def plan_workload_reads(index: Iterable[Mapping[str, Any]], component: str, start: Any,
                        end: Any) -> tuple[str | None, list[tuple[str, str]]]:
    """Les lectures à faire dans la collecte de workload : ``(dernier jour
    collecté, [(jour, composant)…])`` sur la fenêtre ``[start, end]``.

    Un jour se lit sur le ``component`` demandé quand l'index le porte ; pour
    ``TOTAL``, un jour qui n'a pas encore son agrégat ``TOTAL`` (produit une
    fois par jour, après le collecteur horaire) se lit sur ses composants
    d'instance, additionnés ensuite par :func:`normalize_workload`.
    """
    low, high = (d.strftime("%Y%m%d") if hasattr(d, "strftime") else str(d) for d in (start, end))
    by_day: dict[str, set[str]] = {}
    for row in index:
        day = _clean(row.get("PERIODSTRT"))
        if day:
            by_day.setdefault(day, set()).add(_clean(row.get("COMPONENT")))
    wanted_component = _clean(component) or "TOTAL"
    reads: list[tuple[str, str]] = []
    for day in sorted(d for d in by_day if low <= d <= high):
        comps = by_day[day]
        if wanted_component in comps:
            reads.append((day, wanted_component))
        elif wanted_component == "TOTAL":
            reads += [(day, comp) for comp in sorted(comps) if comp != "TOTAL"]
    return (max(by_day) if by_day else None), reads


def workload_note(workload: Mapping[str, Any]) -> str:
    """Pourquoi l'activité n'est pas mesurée, en une phrase datée."""
    last = _clean(workload.get("last_collection"))
    if not last:
        return "aucune collecte de workload trouvée"
    return "collecte de workload arrêtée depuis le %s-%s-%s" % (last[:4], last[4:6], last[6:8])


class _Builder:
    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.interfaces: list[dict[str, Any]] = []
        self.ids: set[str] = set()

    def node(self, node_id: str, parent: Any, name: str, kind: str, **extra: Any) -> str:
        if node_id not in self.ids:
            self.ids.add(node_id)
            self.nodes.append({"id": node_id, "parent": parent, "name": name, "kind": kind,
                               **{k: v for k, v in extra.items() if v not in (None, "", [])}})
        return node_id

    def interface(self, **item: Any) -> None:
        item["id"] = "I%02d" % (len(self.interfaces) + 1)
        item.setdefault("documented", None)
        self.interfaces.append(item)


def _observed(count: Any, sources: list[str], note: str = "", unit: str = "appels") -> dict[str, Any]:
    out: dict[str, Any] = {"count": count, "sources": sources if count is not None or not note else [],
                           "unit": unit}
    if note:
        out["note"] = note
    return out


def assemble_sap_landscape(identity: Mapping[str, Any], clients: Iterable[Mapping[str, Any]],
                           destinations: Iterable[Mapping[str, Any]],
                           outbound_profiles: Iterable[Mapping[str, Any]],
                           inbound_profiles: Iterable[Mapping[str, Any]],
                           idoc_traffic: Iterable[Mapping[str, Any]] | None,
                           gateway_services: Iterable[Mapping[str, Any]],
                           jobs: Iterable[Mapping[str, Any]], trfc_errors: Iterable[Mapping[str, Any]],
                           workload: Mapping[str, Any], window: Mapping[str, Any],
                           icf_activation: Mapping[str, bool] | None = None) -> dict[str, Any]:
    """L'entrée du modèle (``target``, ``window``, ``nodes``, ``interfaces``,
    ``limits``) assemblée depuis les relevés bruts. ``idoc_traffic`` à ``None``
    = trafic illisible (volumes ``None``, jamais zéro). ``icf_activation`` donne,
    par chemin HTTP servi, l'activation de son nœud ICF : la seconde source."""
    sid = _clean(identity.get("system")) or "SAP"
    client = _clean(identity.get("client"))
    logsys = _clean(identity.get("logical_system"))
    days = window.get("days", "?")
    b = _Builder()
    root = b.node("g", None, "Paysage vu depuis %s" % sid, "group")
    ent = b.node("ent", root, "Exploitant de %s (à qualifier)" % sid, "entity",
                 notes=["niveau à fournir par la cartographie applicative"])
    third = b.node("d_third", ent, "Tiers vus depuis SAP (non qualifiés)", "domain")
    sap = b.node("sap", ent, "SAP %s · %s" % (sid, _clean(identity.get("basis_release"))), "sap_system",
                 scope="sap", notes=["BASIS %s · kernel %s" % (_clean(identity.get("basis_release")),
                                                            _clean(identity.get("kernel")))])
    for row in sorted(clients, key=lambda r: _clean(r.get("MANDT"))):
        mandt = _clean(row.get("MANDT"))
        b.node("c_" + mandt, sap, "Mandant %s" % mandt, "client",
               notes=[" · ".join(filter(None, ["catégorie %s" % _clean(row.get("CCCATEGORY")),
                                                _clean(row.get("LOGSYS"))]))])
    work = "c_" + client
    if work not in b.ids:
        work = b.node(work, sap, "Mandant %s" % client, "client")
    available = bool(workload.get("available"))
    note = "" if available else workload_note(workload)
    totals = workload.get("totals") or {}

    # ---- RFC
    l_rfc = b.node("l_rfc", work, "RFC", "layer", layer="rfc", control="SM59 · SM58")
    dests = sorted(destinations, key=lambda d: _clean(d.get("destination")))
    counted = {"program": 0, "internal": 0}
    hosts = [_clean(identity.get(k)) for k in ("host", "db_host")]
    for dest in dests:
        name = _clean(dest.get("destination"))
        cls = classify_destination(dest, hosts, [sid, logsys])
        if cls["role"] in counted:
            counted[cls["role"]] += 1
            continue
        obj = b.node("dst_" + name, l_rfc, name, "destination",
                     notes=[" · ".join(filter(None, ["type %s" % _clean(dest.get("type")),
                                                     "client %s" % _clean(dest.get("target_client")) if dest.get("target_client") else "",
                                                     "logon stocké" if dest.get("stored_logon") else ""]))])
        count = (totals.get("rfc_client") or {}).get(name, 0) if available else None
        common = {"sap_objects": [obj], "channel": cls["channel"], "direction": "outbound",
                  "declared_sources": ["RFCDES"],
                  "proof": {"screen": "SM59", "destination": name, "rfc_type": _clean(dest.get("type"))},
                  "observed": _observed(count, ["SWNC (profil RFC client)"], note)}
        if cls["role"] == "self":
            b.interface(key="RFC:" + name, label="Destination %s vers %s lui-même" % (name, sid), party=sap,
                        self_loop=True, **common)
        else:
            party = b.node("p_dst_" + name, third, cls["party"], "system",
                           notes=["destination %s" % name])
            b.interface(key="RFC:" + name, label="Destination %s" % name, party=party, **common)
    if counted["program"]:
        b.node("dst_programs", l_rfc, "%d destinations TCP/IP" % counted["program"], "inventory",
               notes=["programmes externes, comptés, non qualifiés"])
    if counted["internal"]:
        b.node("dst_internal", l_rfc, "%d destinations internes" % counted["internal"], "inventory",
               notes=["types I, L, X : internes au système"])
    failures: dict[str, int] = {}
    for row in trfc_errors:
        failures[_clean(row.get("destination"))] = failures.get(_clean(row.get("destination")), 0) + 1
    for dest_name, n in sorted(failures.items()):
        obj = b.node("trfc_" + dest_name, l_rfc, "tRFC en échec · %s" % dest_name, "channel",
                     notes=["%d appel(s) en erreur dans ARFCSSTATE" % n])
        b.interface(key="TRFC:" + dest_name, label="tRFC en échec vers %s" % dest_name, party=sap,
                    self_loop=True, sap_objects=[obj],
                    channel="tRFC", direction="outbound", declared_sources=["ARFCSSTATE"], reachable=False,
                    observed=_observed(None, ["ARFCSSTATE"], "%d appel(s) en échec, à relancer ou purger (SM58)" % n))

    # ---- ALE / IDoc
    traffic_known = idoc_traffic is not None
    traffic: dict[tuple[str, str, str], int] = {}
    for row in idoc_traffic or []:
        direction = "outbound" if _clean(row.get("direction")) == "1" else "inbound"
        partner = _clean(row.get("receiver") if direction == "outbound" else row.get("sender"))
        key = (direction, _clean(row.get("message_type")), partner)
        traffic[key] = traffic.get(key, 0) + int(row.get("count") or 0)
    declared: dict[tuple[str, str, str], str] = {}
    partner_types: dict[tuple[str, str, str], str] = {}
    for direction_name, rows, table in (("outbound", outbound_profiles, "EDP13"), ("inbound", inbound_profiles, "EDP21")):
        for row in rows:
            profile = (direction_name, _clean(row.get("message_type")), _clean(row.get("partner")))
            declared[profile] = table
            partner_types[profile] = _clean(row.get("partner_type"))
    l_idoc = b.node("l_idoc", work, "ALE / IDoc", "layer", layer="idoc", control="WE20 · WE02 · BD87",
                    count="%d IDocs sur %s j" % (sum(traffic.values()), days) if traffic_known else "trafic illisible")
    for key in sorted(set(traffic) | set(declared)):
        direction, mestyp, partner = key
        obj = b.node("msg_" + mestyp, l_idoc, mestyp, "message")
        source = declared.get(key)
        for node in b.nodes:
            if node["id"] == obj:
                node.setdefault("notes", []).append("%s %s" % ("profil" if source else "AUCUN profil actuel",
                                                            "sortant" if direction == "outbound" else "entrant"))
        observed = _observed(traffic.get(key, 0) if traffic_known else None, ["EDIDC"],
                             "" if traffic_known else "trafic IDoc illisible", unit="IDocs")
        common = {"sap_objects": [obj], "channel": "IDoc", "direction": direction,
                  "declared_sources": [source] if source else [], "observed": observed}
        label = "%s %s %s" % (mestyp, "vers" if direction == "outbound" else "depuis", partner or "?")
        common["key"] = "IDOC:%s:%s:%s" % ("OUT" if direction == "outbound" else "IN", mestyp, partner)
        if source and partner_types.get(key):
            # le profil déclaré se constate dans WE20 ; sans profil, il n'y a rien à y montrer
            common["proof"] = {"screen": "WE20", "partner": partner, "partner_type": partner_types[key],
                               "direction": direction, "message_type": mestyp}
        if partner and partner.upper() in {logsys.upper(), sid.upper()}:
            b.interface(label=label + " (bouclage)", party=sap, self_loop=True, **common)
        else:
            party = b.node("p_ls_" + partner, third, "Système logique %s" % partner, "system")
            b.interface(label=label, party=party, **common)

    # ---- RFC entrant observé : aucune destination ne le déclare côté SAP,
    # c'est l'appelant qui porte la sienne. L'écart déclaré contre observé.
    own = {h.lower() for h in hosts if h}
    inbound: dict[str, int] = {}
    for key, n in ((totals.get("rfc_server") or {}).items() if available else []):
        remote = key.split("|", 1)[0]
        if remote and not any(remote.lower().startswith(h) for h in own):
            inbound[remote] = inbound.get(remote, 0) + n
    for remote, n in sorted(inbound.items()):
        obj = b.node("rfcin_" + remote, l_rfc, "Appels entrants · %s" % remote, "caller",
                     notes=["aucune destination ne le déclare côté SAP"])
        party = b.node("p_rfcin_" + remote, third, remote, "system", notes=["appelant RFC entrant"])
        b.interface(key="RFCIN:" + remote, label="RFC entrant depuis %s" % remote, party=party,
                    sap_objects=[obj], channel="RFC", direction="inbound", declared_sources=[],
                    observed=_observed(n, ["SWNC (profil RFC serveur)"], "", "appels reçus"))

    def http_callers() -> str:
        return b.node("p_http", third, "Appelants HTTP (non qualifiés)", "application",
                      notes=["navigateurs, applications, intégrations"])

    # ---- ICF : les chemins HTTP réellement servis (hors OData, rangé au Gateway)
    served = sorted(((p, n) for p, n in ((totals.get("http_server") or {}).items() if available else [])
                     if "/sap/opu/odata" not in p.lower()), key=lambda kv: (-kv[1], kv[0]))
    if served:
        l_icf = b.node("l_icf", work, "ICF", "layer", layer="icf", control="SICF",
                       count="%d chemins servis sur %s j" % (len(served), days))
        for path, n in served[:5]:
            active = (icf_activation or {}).get(path)
            state = "activation non lue" if active is None else ("nœud actif" if active else "nœud INACTIF")
            obj = b.node("icf_" + path, l_icf, path, "icf_node", notes=["%d requête(s) · %s" % (n, state)])
            b.interface(key="HTTP:" + path, label="HTTP %s" % path, party=http_callers(), sap_objects=[obj],
                        channel="HTTP", direction="inbound",
                        declared_sources=["ICFSERVLOC"] if active else [],
                        proof={"screen": "SICF", "path": path},
                        observed=_observed(n, ["SWNC (profil HTTP)"], "", "requêtes"))
        if len(served) > 5:
            b.node("icf_rest", l_icf, "+ %d autres chemins" % (len(served) - 5), "inventory",
                   notes=["%d requête(s)" % sum(n for _, n in served[5:])])

    # ---- Gateway
    services = sorted(gateway_services, key=lambda s: _clean(s.get("SERVICE_NAME")))
    custom = [s for s in services if _clean(s.get("SERVICE_NAME"))[:1] in ("Z", "Y")
              or _clean(s.get("NAMESPACE")).startswith(("/Z", "/Y"))]
    l_gw = b.node("l_gw", work, "Gateway OData", "layer", layer="gateway", control="/IWFND/MAINT_SERVICE",
                  count="%d services enregistrés" % len(services))
    if services:
        callers = http_callers()
        http = totals.get("http_server") or {}
        odata = sum(n for path, n in http.items() if "/sap/opu/odata" in path.lower()) if available else None
        rest = len(services) - len(custom)
        inv = b.node("svc_rest", l_gw, "%d services standard" % rest, "inventory",
                     notes=["enregistrés, consommateurs à qualifier"]) if rest else None
        for svc in custom:
            name = _clean(svc.get("SERVICE_NAME"))
            obj = b.node("svc_" + name, l_gw, name, "service")
            count = sum(n for path, n in http.items() if name.lower() in path.lower()) if available else None
            b.interface(key="ODATA:" + name, label="Service %s" % name, party=callers, sap_objects=[obj], channel="OData",
                        direction="inbound", declared_sources=["/IWFND/I_MED_SRH"],
                        proof={"screen": "MAINT_SERVICE", "service": name,
                               "namespace": _clean(svc.get("NAMESPACE")), "version": _clean(svc.get("SERVICE_VERSION"))},
                        observed=_observed(count, ["SWNC (profil HTTP)"], note, "requêtes"))
        if inv:
            b.interface(key="ODATA:*", label="Gateway OData, %d services standard" % rest, party=callers, sap_objects=[inv],
                        channel="OData", direction="inbound", declared_sources=["/IWFND/I_MED_SRH"],
                        observed=_observed(odata, ["SWNC (profil HTTP)"], note, "requêtes"))

    # ---- Jobs
    runs: dict[str, int] = {}
    for job in jobs:
        stem = job_stem(_clean(job.get("JOBNAME")))
        runs[stem] = runs.get(stem, 0) + int(job.get("runs") or 1)
    l_jobs = b.node("l_jobs", work, "Jobs", "layer", layer="jobs", control="SM37",
                    count="%d exécutions sur %s j" % (sum(runs.values()), days))
    ranked = sorted(runs.items(), key=lambda kv: (-kv[1], kv[0]))
    for stem, n in ranked[:4]:
        b.node("job_" + stem, l_jobs, stem, "job", notes=["%d exécution(s)" % n])
    if len(ranked) > 4:
        b.node("job_rest", l_jobs, "+ %d autres familles" % (len(ranked) - 4), "inventory",
               notes=["%d exécution(s)" % sum(n for _, n in ranked[4:])])

    limits = ["Activité : " + (note or "statistiques de workload lues sur la fenêtre") + ".",
              "Aucun référentiel d'interfaces fourni : « documentée » n'est pas jugé (lot 3).",
              "Les niveaux groupe, entité et domaine sont des emplacements à qualifier par la cartographie applicative.",
              "Les destinations TCP/IP de programmes et les destinations internes sont comptées, pas qualifiées.",
              "Le relevé nomme des objets, il ne lit aucune donnée métier transportée."]
    target = {"system": sid, "client": client, "basis_release": _clean(identity.get("basis_release")),
              "kernel": _clean(identity.get("kernel")), "proven_by": ["RFC"],
              "mode": "lecture seule (politique read_only)", "active_gestures": "aucun geste actif", "mockup": False}
    return {"target": target, "window": dict(window), "nodes": b.nodes, "interfaces": b.interfaces,
            "limits": limits}
