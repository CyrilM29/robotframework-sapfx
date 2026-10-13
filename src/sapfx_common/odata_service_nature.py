"""Nature d'un service OData : RAP natif, Gateway ABAP, CAP, ou inconnue.

Né de la fiche scénario 15 (2026-10-13, ABAP Platform 2023, release 758). Un
service OData ne dit pas qui l'a construit, et son NOM ne prouve rien. Ce
module classe un service d'après des marqueurs LUS dans son ``$metadata``,
complétés au besoin par le registre des bindings de service (lu par RFC), et
ne rend une nature que si les marqueurs la prouvent.

Marqueurs mesurés sur la cible (quatorze services, cap-sflight compris) :

- en OData v4, l'espace de noms du schéma porte le dépôt de la Gateway :
  ``com.sap.gateway.srvd.*`` pour un binding RAP, ``com.sap.gateway.default.*``
  pour un service v4 codé ; tout autre dépôt (``srvd_a2x`` compris, qu'aucun
  binding du banc ne porte) reste ``unknown`` ;
- la SAVEUR du brouillon se lit dans l'annotation ``DraftRoot`` : avec
  ``DiscardAction`` pour RAP (v2 et v4), sans ``DiscardAction`` mais avec
  ``ValidationFunction`` pour un brouillon BOPF (SEGW), et pour CAP les actions
  ``draftActivate``/``draftEdit``/``draftPrepare`` avec une entité
  ``DraftAdministrativeData`` (sans ``I_``) ;
- en OData v2, AUCUN marqueur du document ne prouve un binding RAP : l'espace
  de noms ``cds_`` est porté par les bindings mais aussi, selon la
  documentation SAP, par les services ``@OData.publish`` (non mesuré), et
  qu'un binding v2 porte toujours un espace ``cds_`` n'est mesuré que sur le
  banc. Le registre (`binding`) est donc exigé en v2, sans lui la nature reste
  ``unknown`` ; seul un brouillon BOPF, de signature propre, s'en passe.

Ambigus, donc jamais décisifs, et rendus dans ``ambiguous_markers`` :
``IsActiveEntity``, ``DraftRoot`` seul, ``I_DraftAdministrativeData`` (RAP ET
BOPF), les en-têtes ``sap-server`` et ``x-powered-by``. Des marqueurs
contradictoires rendent ``unknown`` en nommant les deux faits, jamais le
premier gagnant.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any, Mapping, Optional, Sequence
from xml.etree import ElementTree

NATURES = ("rap_draft", "rap", "abap_bopf_draft", "abap_gateway", "cap",
           "unknown")

_SAP_DATA_NS = "http://www.sap.com/Protocols/SAPData"
_CAP_DRAFT_ACTIONS = ("draftActivate", "draftEdit", "draftPrepare")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _term_name(term: str) -> str:
    """``SAP__common.DraftRoot`` ou ``Common.DraftRoot`` -> ``DraftRoot`` :
    l'alias du vocabulaire varie d'un serveur à l'autre, le terme non."""
    return term.rsplit(".", 1)[-1]


def read_service_markers(metadata_xml: str) -> dict[str, Any]:
    """Relève dans un ``$metadata`` (v2 ou v4) les marqueurs utiles à la
    qualification, sans rien conclure : version, espace de noms du schéma
    qui porte le conteneur, enregistrements ``DraftRoot`` (propriétés
    déclarées et action d'activation), noms d'actions, entités
    d'administration du brouillon, présence de ``IsActiveEntity`` et des
    attributs ``sap:``. Un document qui n'est pas un ``$metadata`` lève
    ``ValueError``."""
    try:
        root = ElementTree.fromstring(metadata_xml)
    except ElementTree.ParseError as err:
        raise ValueError("Document $metadata illisible : %s" % err) from err
    if _local(root.tag) != "Edmx":
        raise ValueError("Ce document n'est pas un $metadata OData (racine <%s>)."
                         % _local(root.tag))
    version = root.attrib.get("Version", "")
    odata_version = "4.0" if version.startswith("4") else "2.0"
    schemas = [el for el in root.iter() if _local(el.tag) == "Schema"]
    container_ns = ""
    for schema in schemas:
        if any(_local(child.tag) == "EntityContainer" for child in schema):
            container_ns = schema.attrib.get("Namespace", "")
            break
    if not container_ns and schemas:
        container_ns = schemas[0].attrib.get("Namespace", "")
    draft_roots: list[dict[str, Any]] = []
    for element in root.iter():
        if _local(element.tag) != "Annotation":
            continue
        if _term_name(element.attrib.get("Term", "")) != "DraftRoot":
            continue
        values = {pv.attrib.get("Property", ""): pv.attrib.get("String", "")
                  for pv in element.iter() if _local(pv.tag) == "PropertyValue"}
        draft_roots.append({"properties": sorted(values),
                            "activation_action": values.get("ActivationAction", "")})
    operations = sorted({el.attrib.get("Name", "") for el in root.iter()
                         if _local(el.tag) in ("Action", "Function", "FunctionImport")})
    entity_types = {el.attrib.get("Name", "") for el in root.iter()
                    if _local(el.tag) == "EntityType"}
    properties = {el.attrib.get("Name", "") for el in root.iter()
                  if _local(el.tag) == "Property"}
    sap_attributes = any(attr.startswith("{%s}" % _SAP_DATA_NS)
                         for el in root.iter() for attr in el.attrib)
    return {
        "odata_version": odata_version,
        "schema_namespace": container_ns,
        "draft_roots": draft_roots,
        "operations": operations,
        "draft_admin_entities": sorted(
            name for name in entity_types
            if re.fullmatch(r"(I_)?DraftAdministrativeData(Type)?", name)),
        "has_is_active_entity": "IsActiveEntity" in properties,
        "sap_attributes": sap_attributes,
    }


def draft_flavour(markers: Mapping[str, Any]) -> dict[str, Any]:
    """Saveur du brouillon déclaré : ``none`` (aucun ``DraftRoot``), ``rap``,
    ``bopf``, ``cap``, ``unknown`` (un ``DraftRoot`` sans signature connue) ou
    ``conflict`` (plusieurs racines de saveurs différentes). Rend
    ``{flavour, evidence, flavours}``."""
    roots = markers.get("draft_roots") or []
    if not roots:
        return {"flavour": "none", "evidence": [], "flavours": []}
    admin = set(markers.get("draft_admin_entities") or [])
    found = []
    evidence = []
    for root in roots:
        props = set(root.get("properties") or [])
        activation = _term_name(root.get("activation_action", "").replace("/", "."))
        if "DiscardAction" in props:
            found.append("rap")
            evidence.append("DraftRoot avec DiscardAction")
        elif "ValidationFunction" in props:
            found.append("bopf")
            evidence.append("DraftRoot sans DiscardAction, avec ValidationFunction")
        elif activation in _CAP_DRAFT_ACTIONS and admin & {"DraftAdministrativeData"}:
            found.append("cap")
            evidence.append("DraftRoot à action %s et entité DraftAdministrativeData"
                            % activation)
        else:
            found.append("unknown")
            evidence.append("DraftRoot sans signature connue (propriétés %s)"
                            % ", ".join(sorted(props)))
    distinct = sorted(set(found))
    flavour = distinct[0] if len(distinct) == 1 else "conflict"
    return {"flavour": flavour, "evidence": sorted(set(evidence)),
            "flavours": distinct}


def _ambiguous(markers: Mapping[str, Any],
               headers: Optional[Mapping[str, str]]) -> list[str]:
    found = []
    if markers.get("has_is_active_entity"):
        found.append("IsActiveEntity")
    if markers.get("draft_roots"):
        found.append("DraftRoot")
    if "I_DraftAdministrativeDataType" in (markers.get("draft_admin_entities") or []):
        found.append("I_DraftAdministrativeData")
    lowered = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    for name in ("sap-server", "x-powered-by"):
        if name in lowered:
            found.append("%s: %s" % (name, lowered[name]))
    return found


def _binding_state(binding: Any) -> str:
    """``absent`` (aucun relevé fourni), ``not_found`` (le registre ne le
    porte pas) ou la version OData du binding trouvé (``V2``/``V4``)."""
    if binding is None or binding == "":
        return "absent"
    if isinstance(binding, str):
        # via rf-mcp (`execute_step`), tout argument arrive en chaîne
        try:
            binding = ast.literal_eval(binding.strip())
        except (ValueError, SyntaxError):
            try:
                binding = json.loads(binding)
            except ValueError:
                raise ValueError("binding illisible : %r (attendu le dict rendu "
                                 "par `Get Service Binding`)." % binding) from None
    if not isinstance(binding, Mapping):
        raise ValueError("binding attendu : le dict rendu par `Get Service Binding`, "
                         "reçu %r." % (binding,))
    if not binding.get("found"):
        return "not_found"
    return str(binding.get("odata_version") or "").upper() or "V?"


def classify_service_nature(metadata_xml: str,
                            headers: Optional[Mapping[str, str]] = None,
                            binding: Any = None) -> dict[str, Any]:
    """Classe un service OData d'après son ``$metadata`` (et le relevé du
    registre des bindings, ``binding``, exigé en OData v2). Rend un dict
    JSON-safe ``{nature, odata_version, schema_namespace, repository,
    draft_flavour, evidence, ambiguous_markers, missing_proof, conflicts,
    candidates}`` ; ``nature`` est l'une de :data:`NATURES`. Une nature n'est
    rendue que prouvée : sinon ``unknown``, avec ce qui manque
    (``missing_proof``), ce qui se contredit (``conflicts``) et les natures
    encore possibles (``candidates``)."""
    markers = read_service_markers(metadata_xml)
    flavour = draft_flavour(markers)
    version = markers["odata_version"]
    namespace = markers["schema_namespace"]
    state = _binding_state(binding)
    evidence = list(flavour["evidence"])
    missing: list[str] = []
    conflicts: list[str] = []
    candidates: list[str] = []
    repository = ""
    nature = "unknown"
    kind = flavour["flavour"]

    if flavour["flavour"] == "conflict":
        conflicts.append("racines de brouillon de saveurs différentes : %s"
                         % ", ".join(flavour["flavours"]))
    elif version == "4.0":
        match = re.match(r"com\.sap\.gateway\.([^.]+)\.", namespace)
        repository = match.group(1) if match else ""
        if state in ("V2", "V?"):
            conflicts.append("document OData v4, binding du registre en %s" % state)
        elif repository == "srvd":
            evidence.append("espace de noms %s (dépôt srvd : binding RAP)" % namespace)
            if state == "not_found":
                conflicts.append("dépôt srvd, mais binding absent du registre")
            elif kind == "rap":
                nature = "rap_draft"
            elif kind == "none":
                nature = "rap"
            else:
                conflicts.append("dépôt srvd, brouillon de saveur %s" % kind)
        elif repository == "default":
            evidence.append("espace de noms %s (dépôt default : service v4 codé)"
                            % namespace)
            if state == "V4":
                conflicts.append("dépôt default, mais binding RAP au registre")
            elif kind == "none":
                nature = "abap_gateway"
            else:
                conflicts.append("dépôt default, brouillon de saveur %s" % kind)
        elif repository:
            missing.append("dépôt Gateway « %s » jamais mesuré sur le banc" % repository)
            candidates.append("rap" if repository.startswith("srvd") else "abap_gateway")
        elif kind == "cap":
            evidence.append("espace de noms %s hors Gateway SAP" % namespace)
            if state == "V4":
                conflicts.append("brouillon de saveur CAP, binding RAP au registre")
            else:
                nature = "cap"
        else:
            missing.append("aucun marqueur de dépôt Gateway ni de brouillon CAP")
            candidates.append("cap")
    else:
        sap_doc = markers["sap_attributes"]
        cds = namespace.startswith("cds_")
        if not sap_doc:
            missing.append("document v2 sans attribut sap: (serveur non SAP ?)")
        elif state == "V4":
            conflicts.append("document OData v2, binding du registre en V4")
        elif state == "V?":
            missing.append("binding trouvé au registre, version OData illisible")
        elif state == "V2":
            evidence.append("binding V2 au registre")
            if kind == "rap":
                nature = "rap_draft"
            elif kind == "none":
                nature = "rap"
            else:
                conflicts.append("binding RAP au registre, brouillon de saveur %s" % kind)
        elif kind == "bopf":
            nature = "abap_bopf_draft"
            if state == "not_found":
                evidence.append("binding absent du registre")
        elif kind == "rap":
            if state == "not_found":
                conflicts.append("brouillon de saveur rap, binding absent du registre")
            else:
                missing.append("binding non prouvé : registre requis en OData v2")
                candidates.append("rap_draft")
        elif kind != "none":
            missing.append("brouillon de saveur %s sur un service v2 SAP" % kind)
        elif cds:
            if state == "not_found":
                missing.append("espace cds_ sans binding au registre "
                               "(@OData.publish, jamais mesuré)")
                candidates.append("abap_gateway")
            else:
                missing.append("binding non prouvé : registre requis en OData v2")
                candidates.extend(["rap", "abap_gateway"])
        elif state == "not_found":
            evidence.append("espace de noms %s (nom de service, attributs sap:)"
                            % namespace)
            evidence.append("binding absent du registre")
            nature = "abap_gateway"
        else:
            # qu'un binding RAP v2 porte toujours un espace cds_ n'est mesuré
            # que sur le banc : sans registre, rien ne prouve son absence
            missing.append("binding non prouvé : registre requis en OData v2")
            candidates.append("abap_gateway")
    return {
        "nature": nature,
        "odata_version": version,
        "schema_namespace": namespace,
        "repository": repository,
        "draft_flavour": kind,
        "evidence": evidence,
        "ambiguous_markers": _ambiguous(markers, headers),
        "missing_proof": missing,
        "conflicts": conflicts,
        "candidates": candidates,
    }


def binding_name_from_path(service_path: str) -> str:
    """Nom du binding de service déduit de l'adresse OData (forme mesurée sur
    les bindings ``/DMO/`` seulement) : v4
    ``/sap/opu/odata4/<ns>/<binding>/srvd/<ns>/<service>/<version>``, v2
    ``/sap/opu/odata/<ns>/<binding>``, l'espace ``sap`` désignant un nom sans
    préfixe. Une adresse d'une autre forme lève ``ValueError``."""
    parts = [p for p in service_path.split("?", 1)[0].strip().split("/") if p]
    try:
        start = parts.index("opu") + 1
    except ValueError:
        raise ValueError("Adresse OData SAP attendue (/sap/opu/odata…), reçu %r."
                         % service_path) from None
    if len(parts) < start + 3 or parts[start] not in ("odata", "odata4"):
        raise ValueError("Adresse OData SAP attendue (/sap/opu/odata/<ns>/<binding> "
                         "ou /sap/opu/odata4/<ns>/<binding>/...), reçu %r."
                         % service_path)
    namespace, name = parts[start + 1], parts[start + 2]
    name = name.split(";", 1)[0].upper()
    if namespace.lower() == "sap":
        return name
    return "/%s/%s" % (namespace.upper(), name)


def describe_binding(binding_rows: Sequence[Mapping[str, str]],
                     service_rows: Sequence[Mapping[str, str]],
                     binding_name: str) -> dict[str, Any]:
    """Assemble le relevé du registre (lignes actives de ``SRVB_BIND_TYPE`` et
    de ``SRVB_SERVICES``) en ``{found, binding, bind_type, odata_version,
    category, services}``. Binding absent : ``found`` faux, jamais une
    exception. ``category`` vaut ``ui`` (0) ou ``web_api`` (1)."""
    if not binding_rows:
        return {"found": False, "binding": binding_name, "bind_type": "",
                "odata_version": "", "category": "", "services": []}
    if len(binding_rows) > 1:
        raise ValueError("Binding %s porté par %d lignes actives du registre."
                         % (binding_name, len(binding_rows)))
    row = binding_rows[0]
    category = {"0": "ui", "1": "web_api"}.get(
        str(row.get("BIND_TYPE_CATEGORY", "")).strip(),
        str(row.get("BIND_TYPE_CATEGORY", "")).strip())
    services = [{"service_name": s.get("SERVICE_NAME", "").strip(),
                 "service_version": s.get("SERVICE_VERSION", "").strip(),
                 "service_definition": s.get("SRVDNAME", "").strip()}
                for s in service_rows]
    return {"found": True, "binding": binding_name,
            "bind_type": str(row.get("BIND_TYPE", "")).strip(),
            "odata_version": str(row.get("BIND_TYPE_VERSION", "")).strip().upper(),
            "category": category, "services": services}
