"""Croisement DDIC/OData, moitie CONTRAT (prive) : perimetre, catalogue,
rapprochement de proprietes, sondes d'entity sets.

Socle de ``sapfx_common.cross_channel`` (la porte d'entree publique, importee
comme bibliotheque Robot) : perimetre valide et borne, couverture du
catalogue, normaliseur d'identifiants conscient des acronymes, contrat de
service ``$metadata``, classement des sondes, rapprochement proprietes OData
et champs DD03L. L'autre moitie (verdicts de couple, artefact, comparaison)
vit dans ``_cross_channel_artifact.py``.

Extrait de ``cross_channel.py`` (convention #13). Module pur, type, teste a
travers l'API publique.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from sapfx_common import odata_metadata

SCHEMA_VERSION = 1

#: Verdicts admis pour un couple déclaré. ``not_comparable`` n'est pas un
#: renoncement : c'est la seule façon honnête de consigner un entity set dont
#: le périmètre dépend de l'utilisateur ou de la session.
COUPLE_EXPECTATIONS = ("equal", "equal_under_filter", "not_comparable")

#: Propriété d'état d'activité des services draft-enabled : sa présence suffit
#: à savoir que le ``$count`` nu agrège actives et brouillons.
_DRAFT_PROPERTY = "IsActiveEntity"

#: Type de données DDIC d'un champ mandant. Sa présence rend le comptage SE16
#: dépendant du mandant de connexion, donc comparable au seul canal API du
#: MÊME mandant.
_CLIENT_DATATYPE = "CLNT"

_CAMEL_AFTER_LOWER = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_CAMEL_BEFORE_WORD = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_ANY_UPPER = re.compile(r"(?<=.)(?=[A-Z])")
_NON_WORD = re.compile(r"[^0-9A-Za-z]+")
#: Borne BASSE d'un critère positionnel d'écran de sélection SE16, préfixée du
#: type de contrôle relevé live (``ctxtI2-LOW``, ``txtI3-LOW``) : le type varie
#: d'un champ à l'autre, la position et le suffixe non.
_SELECTION_LOW = re.compile(r"(?:^|/)[a-z]*I\d+-LOW$")


def _as_value_list(values: Any) -> list[str]:
    """Une liste de valeurs, robuste au SCALAIRE : une chaîne seule devient
    ``[chaîne]`` au lieu d'être itérée caractère par caractère (le piège des
    variables ``-v`` Robot, toujours scalaires)."""
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return [str(v) for v in values]


def _positive_int(value: Any, name: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(
            f"{name} doit être un entier strictement positif, reçu {value!r}.")
    if number <= 0:
        raise ValueError(
            f"{name} doit être strictement positif, reçu {number}.")
    return number


def validate_cross_channel_scope(services: Any, ecc_client: Any,
                                 api_client: Any, max_entity_sets: Any = 60,
                                 max_couples: Any = 20,
                                 max_field_contracts: Any = 5
                                 ) -> dict[str, Any]:
    """Valide et normalise le périmètre d'une campagne de croisement.

    Retourne ``{"services", "client", "max_entity_sets", "max_couples",
    "max_field_contracts"}``. ``services`` accepte une liste ou une valeur
    seule ; les chemins sont épurés, dédoublonnés et triés (déterminisme de
    l'artefact).

    Deux refus, tous deux volontairement bloquants :

    - **mandants divergents** : le comptage SE16 se fait dans le mandant de la
      session GUI et le ``$count`` dans celui du canal API. Les faire diverger
      compare deux populations et fabrique un écart qui n'existe pas ; la
      campagne refuse l'exécution plutôt que de rapporter une incohérence ;
    - **périmètre non borné** : aucune limite n'a de mode illimité implicite.
    """
    cleaned = sorted({s.strip() for s in _as_value_list(services) if s.strip()})
    if not cleaned:
        raise ValueError(
            "Périmètre vide : au moins un service à instruire est requis.")
    ecc = str(ecc_client or "").strip()
    api = str(api_client or "").strip()
    if not ecc or not api:
        raise ValueError(
            "Mandant manquant : le mandant du canal GUI et celui du canal API "
            "sont tous deux requis pour prouver qu'ils coïncident.")
    if ecc != api:
        raise ValueError(
            f"Mandants divergents (GUI {ecc!r}, API {api!r}) : le comptage "
            "SE16 et le $count porteraient sur deux populations distinctes. "
            "Aligner les deux canaux sur le même mandant avant de relancer.")
    return {
        "services": cleaned,
        "client": ecc,
        "max_entity_sets": _positive_int(max_entity_sets, "max_entity_sets"),
        "max_couples": _positive_int(max_couples, "max_couples"),
        "max_field_contracts": _positive_int(max_field_contracts,
                                             "max_field_contracts"),
    }


def _service_tail(path: str) -> str:
    return str(path).rstrip("/").rsplit("/", 1)[-1].casefold()


def catalog_coverage(services: Any, catalog: Any) -> dict[str, Any]:
    """Recoupe le périmètre demandé avec le catalogue Gateway de la cible.

    Retourne ``{"catalog_size", "published", "missing"}``. Un service du
    périmètre absent du catalogue est un **écart de portabilité rapporté**
    (la cible ne publie pas ce service), jamais une erreur de configuration
    silencieuse : c'est l'information utile quand la même campagne passe d'une
    cible ECC à une cible S/4HANA.

    L'appariement se fait sur le chemin publié (``service_url`` se termine par
    le chemin demandé) puis, à défaut, sur le dernier segment comparé au nom
    technique ou au titre, préfixe ``Z`` d'espace de noms client toléré : le
    catalogue observé publie ``ZGWSAMPLE_BASIC`` pour le service exposé sous
    ``/sap/opu/odata/iwbep/GWSAMPLE_BASIC``.
    """
    entries = [e for e in (catalog or []) if isinstance(e, Mapping)]
    published: list[str] = []
    missing: list[str] = []
    for service in sorted({s.strip() for s in _as_value_list(services)
                           if s.strip()}):
        wanted_path = service.rstrip("/").casefold()
        tail = _service_tail(service)
        found = False
        for entry in entries:
            url = str(entry.get("service_url") or "").rstrip("/").casefold()
            if url.endswith(wanted_path):
                found = True
                break
            for key in ("technical_name", "title", "id"):
                name = str(entry.get(key) or "").casefold()
                if name in (tail, "z" + tail):
                    found = True
                    break
            if found:
                break
        (published if found else missing).append(service)
    return {"catalog_size": len(entries), "published": published,
            "missing": missing}


def normalize_identifier(name: str, acronym_aware: bool = True) -> str:
    """Normalise un identifiant en ``MAJUSCULES_SOULIGNÉES``.

    ``acronym_aware=True`` (défaut) traite une suite de majuscules comme UN
    jeton : ``ProductID`` devient ``PRODUCT_ID`` et ``TaxTarifCode`` devient
    ``TAX_TARIF_CODE``. À ``False``, la coupure a lieu devant CHAQUE majuscule
    (``PRODUCT_I_D``) : la variante naïve, conservée parce qu'elle rend la
    différence mesurable au lieu de la postuler (six points d'écart sur les 21
    propriétés de ``ProductSet``, relevé live).

    Un nom déjà en majuscules (le cas des champs DDIC) traverse inchangé, aux
    séparateurs près.
    """
    raw = str(name or "").strip()
    if not raw:
        return ""
    cleaned = _NON_WORD.sub("_", raw).strip("_")
    if not cleaned:
        return ""
    if not any(character.islower() for character in cleaned):
        return re.sub(r"_+", "_", cleaned).upper()
    if acronym_aware:
        spaced = _CAMEL_AFTER_LOWER.sub("_", cleaned)
        spaced = _CAMEL_BEFORE_WORD.sub("_", spaced)
    else:
        spaced = "_".join(
            _ANY_UPPER.sub("_", part) for part in cleaned.split("_"))
    return re.sub(r"_+", "_", spaced).strip("_").upper()


def _property_names(properties: Any) -> list[str]:
    if isinstance(properties, Mapping):
        return sorted(str(name) for name in properties)
    return sorted(str(name) for name in _as_value_list(properties))


def _property_type(properties: Any, name: str) -> str:
    if isinstance(properties, Mapping):
        info = properties.get(name)
        if isinstance(info, Mapping):
            return str(info.get("type") or "")
    return ""


def describe_service_contract(metadata: Any,
                              max_entity_sets: Any = 60) -> dict[str, Any]:
    """Fiche de contrat d'un service, un enregistrement par entity set.

    Consomme le dict de ``Get Odata Metadata`` (enrichi des annotations
    ``sap:`` de niveau entity set) et retourne ``{"service_path", "version",
    "declared", "truncated", "entity_sets": [...]}``, chaque entity set portant
    ``{"entity_set", "label", "keys", "addressable", "creatable", "updatable",
    "deletable", "declared_capabilities", "draft_enabled",
    "property_count"}``.

    ``draft_enabled`` se lit sur la présence de la propriété d'état
    d'activité : c'est ce qui explique qu'un ``$count`` nu dépasse la
    volumétrie de la table (les brouillons s'y ajoutent), et donc pourquoi
    l'égalité n'a de sens que sous filtre d'activité.

    ``truncated`` devient vrai quand la limite a écarté des entity sets : une
    borne atteinte reste visible, jamais un succès silencieux.
    """
    limit = _positive_int(max_entity_sets, "max_entity_sets")
    sets = metadata.get("entity_sets", {}) if isinstance(metadata, Mapping) \
        else {}
    names = sorted(str(name) for name in sets)
    kept = names[:limit]
    records: list[dict[str, Any]] = []
    declared_total = 0
    for name in kept:
        info = sets[name] if isinstance(sets, Mapping) else {}
        capabilities = info.get("capabilities", {}) if isinstance(
            info, Mapping) else {}
        declared = sorted(str(flag) for flag
                          in info.get("declared_capabilities", []) or [])
        declared_total += len(declared)
        properties = info.get("properties", {}) if isinstance(info, Mapping) \
            else {}
        records.append({
            "entity_set": name,
            "label": info.get("label"),
            "keys": sorted(str(key) for key in info.get("keys", []) or []),
            "addressable": bool(capabilities.get("addressable", True)),
            "creatable": bool(capabilities.get("creatable", True)),
            "updatable": bool(capabilities.get("updatable", True)),
            "deletable": bool(capabilities.get("deletable", True)),
            "declared_capabilities": declared,
            "draft_enabled": _DRAFT_PROPERTY in _property_names(properties),
            "property_count": len(_property_names(properties)),
        })
    return {
        "service_path": str(metadata.get("service_path", ""))
        if isinstance(metadata, Mapping) else "",
        "version": str(metadata.get("version", ""))
        if isinstance(metadata, Mapping) else "",
        "declared": declared_total > 0,
        "truncated": len(names) > len(kept),
        "entity_sets": records,
    }


def write_simulation_candidates(metadata: Any) -> dict[str, Any]:
    """Qualification d'écriture d'un service, déléguée à
    ``sapfx_common.odata_metadata.write_simulation_candidates``.

    Ce module étant celui que la couche ``resources/`` importe comme
    bibliothèque Robot, la fonction est ré-exposée ici pour qu'une campagne
    l'atteigne par un KEYWORD, jamais par un ``Evaluate`` qui importerait un
    module dans une suite. Aucune logique n'est dupliquée : la qualification,
    ses valeurs par défaut de Gateway et la distinction entre capacité
    déclarée et capacité par défaut vivent en un seul endroit.
    """
    return odata_metadata.write_simulation_candidates(dict(metadata or {}))


def odata_error_code(payload: Any) -> str:
    """Code d'erreur TECHNIQUE d'une réponse OData en échec (``error.code``),
    chaîne vide quand la réponse n'en porte pas.

    C'est l'ancre indépendante de la langue du canal API, le pendant du type
    de message de la barre de statut côté écran : le refus mesuré live portait
    le code ``CX_SADL_GW_PRIVIL_VIOLATION``, dont le message, lui, arrive dans
    la langue de la session. Les deux formes ``{"error": {...}}`` (v2 et v4)
    et ``{"error": {"code": ...}}`` imbriquée dans ``odata.error`` sont
    lues.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return ""
    if not isinstance(payload, Mapping):
        return ""
    for key in ("error", "odata.error"):
        node = payload.get(key)
        if isinstance(node, Mapping):
            code = node.get("code")
            if code is not None:
                return str(code)
    return ""


def classify_entity_set_probes(contract: Any, probes: Any) -> list[dict[str, Any]]:
    """Verdict par entity set, en croisant ce que le service DÉCLARE et ce que
    la sonde a MESURÉ.

    ``contract`` : la fiche de :func:`describe_service_contract`. ``probes`` :
    les résultats de la sonde tolérante (``{"entity_set", "status",
    "error_code", "count"}``), ceux des entity sets réellement interrogés.

    Quatre verdicts, et c'est leur asymétrie qui porte le sens :

    - ``available`` : déclaré adressable, répond ;
    - ``declared_not_addressable`` : déclaré non adressable, écarté du
      sondage. Ce n'est pas une anomalie, c'est une déclaration honorée ;
    - ``unexpected_refusal`` : déclaré adressable et refusé. C'est LA seule
      anomalie du niveau ;
    - ``not_probed`` : hors du lot sondé (borne atteinte), jamais confondu
      avec un compte nul.

    La somme des verdicts couvre par construction tous les entity sets de la
    fiche de contrat.
    """
    measured = {}
    for probe in probes or []:
        if isinstance(probe, Mapping):
            measured[str(probe.get("entity_set", ""))] = probe
    results: list[dict[str, Any]] = []
    records = contract.get("entity_sets", []) if isinstance(contract, Mapping) \
        else []
    for record in records:
        name = str(record.get("entity_set", ""))
        addressable = bool(record.get("addressable", True))
        probe = measured.get(name)
        status = int(probe.get("status", 0)) if probe else 0
        if not addressable and probe is None:
            verdict = "declared_not_addressable"
        elif probe is None:
            verdict = "not_probed"
        elif status < 400:
            verdict = "available"
        elif not addressable:
            verdict = "declared_not_addressable"
        else:
            verdict = "unexpected_refusal"
        results.append({
            "entity_set": name,
            "declared_addressable": addressable,
            "probed": probe is not None,
            "http_status": status,
            "error_code": str(probe.get("error_code", "")) if probe else "",
            "count": probe.get("count") if probe else None,
            "verdict": verdict,
        })
    return sorted(results, key=lambda r: r["entity_set"])


def compare_odata_properties_with_ddic_fields(
        properties: Any, fields: Any, aliases: Any = None,
        keys: Any = None, acronym_aware: bool = True) -> dict[str, Any]:
    """Rapproche les propriétés d'un entity type et les champs d'une table DDIC.

    Trois passes ORDONNÉES, et rien au-delà : (1) alias explicitement déclaré
    pour le couple, (2) normalisation consciente des acronymes, (3) rien. Une
    propriété que ces deux passes ne trouvent pas reste **non appariée et
    rapportée** : aucun appariement de force, aucun score approximatif.

    ``properties`` : le dict ``{nom: {"type", ...}}`` du ``$metadata`` (une
    simple liste de noms est acceptée). ``fields`` : les lignes DD03L
    (``{"FIELDNAME", "POSITION", "KEYFLAG", "DATATYPE", ...}``). ``aliases`` :
    ``{Propriété: CHAMP}``, prioritaire sur la normalisation. ``keys`` : les
    clés de l'entity type, vérifiées séparément.

    Retour JSON-safe : ``matched`` (avec la passe qui a conclu), les deux
    ensembles d'orphelins, ``unmatched_keys`` et un ``summary`` à trois
    nombres. C'est ce triplet qui rend une dérive de schéma ECC vers S/4HANA
    lisible, là où un verdict binaire ne dirait rien.

    Une propriété de type complexe (hors espace ``Edm.``) est classée
    ``complex_type`` et non « échec d'appariement » : elle ne correspond à
    aucun champ plat par construction.
    """
    alias_map = {str(k): str(v).strip().upper()
                 for k, v in dict(aliases or {}).items()}
    rows = [row for row in (fields or []) if isinstance(row, Mapping)]
    field_names = sorted({str(row.get("FIELDNAME", "")).strip().upper()
                          for row in rows
                          if str(row.get("FIELDNAME", "")).strip()})
    by_normalized: dict[str, str] = {}
    for field in field_names:
        by_normalized.setdefault(normalize_identifier(field), field)

    matched: list[dict[str, str]] = []
    unmatched_properties: list[dict[str, str]] = []
    consumed: set[str] = set()
    for name in _property_names(properties):
        property_type = _property_type(properties, name)
        alias = alias_map.get(name)
        if alias and alias in field_names:
            matched.append({"property": name, "field": alias, "via": "alias"})
            consumed.add(alias)
            continue
        candidate = by_normalized.get(
            normalize_identifier(name, acronym_aware=acronym_aware))
        if candidate is not None:
            matched.append({"property": name, "field": candidate,
                            "via": "normalization"})
            consumed.add(candidate)
            continue
        reason = "complex_type" if (
            property_type and not property_type.startswith("Edm.")) \
            else "no_match"
        unmatched_properties.append({"property": name, "type": property_type,
                                     "reason": reason})

    matched_by_property = {m["property"]: m["field"] for m in matched}
    key_names = [str(k) for k in _as_value_list(keys)]
    unmatched_keys = sorted(k for k in key_names
                            if k not in matched_by_property)
    unmatched_fields = sorted(f for f in field_names if f not in consumed)
    return {
        "matched": sorted(matched, key=lambda m: m["property"]),
        "unmatched_properties": sorted(unmatched_properties,
                                       key=lambda p: p["property"]),
        "unmatched_fields": unmatched_fields,
        "keys": sorted(key_names),
        "unmatched_keys": unmatched_keys,
        "summary": {
            "properties": len(_property_names(properties)),
            "ddic_fields": len(field_names),
            "matched": len(matched),
            "unmatched_properties": len(unmatched_properties),
            "unmatched_fields": len(unmatched_fields),
            "unmatched_keys": len(unmatched_keys),
        },
    }


