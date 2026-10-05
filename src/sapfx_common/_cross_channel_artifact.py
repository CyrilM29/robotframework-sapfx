"""Croisement DDIC/OData, moitie ARTEFACT (prive) : verdicts de couple,
candidats d'ecriture, artefact deterministe et comparaison de deux cibles.

L'autre moitie du socle de ``sapfx_common.cross_channel`` (la porte d'entree
publique, importee comme bibliotheque Robot) : verdict calcule d'un couple
entity set / table, liste blanche des candidats d'ecriture (``evidence``
derive de ``declared_allowed`` : une annotation PRESENTE n'est pas
PERMISSIVE), criteres de selection SE16, description DDIC, artefact JSON trie
+ hash SHA-256 hors horodatage, comparaison et rapport Markdown. La moitie
contrat vit dans ``_cross_channel_contract.py``.

Extrait de ``cross_channel.py`` (convention #13). Module pur, type, teste a
travers l'API publique.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from ._cross_channel_contract import (
    _CLIENT_DATATYPE,
    _SELECTION_LOW,
    COUPLE_EXPECTATIONS,
    SCHEMA_VERSION,
    _as_value_list,
    normalize_identifier,
)

def build_couple_verdict(couple: Any, api_count: Any = None,
                         ddic_count: Any = None,
                         api_count_unfiltered: Any = None) -> dict[str, Any]:
    """Verdict volumétrique d'UN couple déclaré, JSON-safe.

    ``couple`` porte ``entity_set``, ``service``, ``table``, les filtres
    éventuels (``api_filter``, ``ddic_filter``), le verdict attendu
    (``expected``) et son ``reason`` quand il n'est pas ``equal``.

    Trois lectures, et une seule assertion possible pour chacune :

    - ``equal`` : les deux comptes doivent être égaux ;
    - ``equal_under_filter`` : égaux **une fois les filtres déclarés
      appliqués** ; l'écart sans filtre est consigné (``api_count_unfiltered``)
      au lieu d'être masqué, puisque c'est lui qui documente la projection ou
      les brouillons ;
    - ``not_comparable`` : jamais asserté en égalité, motif consigné.

    ``verdict`` vaut ``match``, ``mismatch`` ou ``not_compared`` ; ``match``
    reste ``False`` pour un couple non comparable, qui n'est ni un succès de
    croisement ni un échec.
    """
    record = dict(couple or {})
    expected = str(record.get("expected", "equal")).strip() or "equal"
    if expected not in COUPLE_EXPECTATIONS:
        raise ValueError(
            f"Verdict attendu inconnu {expected!r} ; admis : "
            f"{', '.join(COUPLE_EXPECTATIONS)}.")
    api = None if api_count is None else int(api_count)
    ddic = None if ddic_count is None else int(ddic_count)
    unfiltered = None if api_count_unfiltered is None \
        else int(api_count_unfiltered)
    if expected == "not_comparable":
        verdict = "not_compared"
    elif api is None or ddic is None:
        verdict = "not_compared"
    else:
        verdict = "match" if api == ddic else "mismatch"
    return {
        "entity_set": str(record.get("entity_set", "")),
        "service": str(record.get("service", "")),
        "table": str(record.get("table", "")),
        "api_filter": str(record.get("api_filter", "")),
        "ddic_filter": str(record.get("ddic_filter", "")),
        "expected": expected,
        "reason": str(record.get("reason", "")),
        "api_count": api,
        "api_count_unfiltered": unfiltered,
        "ddic_count": ddic,
        "verdict": verdict,
        "match": verdict == "match",
    }


def shortlist_write_candidates(candidates: Any, allowlist: Any = None,
                               require_declared: bool = True
                               ) -> list[dict[str, Any]]:
    """Réduit les candidats d'écriture à ceux qu'une campagne peut retenir.

    ``candidates`` vient de ``sapfx_common.odata_metadata
    .write_simulation_candidates`` ; ``allowlist`` est la **liste blanche
    métier** portée par la couche ``resources/``.

    Deux gardes, dans cet ordre, et la première est une correction que la
    mesure live a imposée :

    - ``require_declared`` (défaut) ne retient que les candidats dont
      ``evidence`` vaut ``declared``. Une capacité obtenue par DÉFAUT ne prouve
      rien : le service s'est tu, et le silence de la Gateway vaut permission.
      Mesuré live, un service de démonstration déclarait une restriction sur un
      entity set tout en restant muet sur quatre autres, lesquels paraissaient
      donc entièrement écrivables. Une garde posée au niveau du service aurait
      été verte, et fausse ;
    - la liste blanche : un objet non listé n'est jamais candidat, fût-il
      déclaré modifiable. « Déclaré modifiable » est un critère nécessaire,
      jamais suffisant.

    Chaque fiche retenue porte ``reversibility_observed`` à ``unknown`` :
    seule une observation datée remplit ce champ, jamais une déclaration de
    métadonnées.

    ``declared_allowed`` croise les capacités effectivement autorisées et
    celles réellement déclarées. Le champ a d'abord été ajouté pour rendre
    VISIBLE une nuance que la garde laissait passer : un entity set peut
    déclarer des restrictions (``creatable="false"``) tout en devant sa seule
    capacité autorisée au silence du service sur un autre verbe. Mesuré live,
    les deux candidats d'une cible réelle étaient dans ce cas.

    La nuance a depuis été traitée à sa source : ``evidence`` se dérive de
    ``declared_allowed`` dans ``odata_metadata.write_simulation_candidates``,
    donc un verbe n'engage que s'il est explicitement PERMIS, et une
    interdiction déclarée ne fait plus office d'appui. Sur la cible mesurée,
    la conséquence est qu'aucun entity set ne reste candidat : c'est le
    résultat honnête, préférable à deux fiches que rien n'appuie.
    """
    entries = candidates
    if isinstance(candidates, Mapping):
        entries = candidates.get("candidates", [])
    allowed = {str(name).strip() for name in _as_value_list(allowlist)
               if str(name).strip()}
    shortlist: list[dict[str, Any]] = []
    for entry in entries or []:
        if not isinstance(entry, Mapping):
            continue
        name = str(entry.get("entity_set", ""))
        if allowed and name not in allowed:
            continue
        if require_declared and str(entry.get("evidence", "")) != "declared":
            continue
        allowed_flags = sorted(str(f) for f in entry.get("allowed", []) or [])
        declared_flags = sorted(str(f) for f in entry.get("declared", []) or [])
        shortlist.append({
            "entity_set": name,
            "channel": "api",
            "addressable": bool(entry.get("addressable", True)),
            "allowed": allowed_flags,
            "declared": declared_flags,
            "declared_allowed": [f for f in allowed_flags
                                 if f in declared_flags],
            "evidence": str(entry.get("evidence", "")),
            "keys": [str(k) for k in entry.get("keys", []) or []],
            "reversibility_observed": "unknown",
        })

    return sorted(shortlist, key=lambda c: c["entity_set"])


def selection_criteria(signature: Any) -> dict[str, str]:
    """Carte ``{CHAMP: localisateur}`` d'un écran de sélection SE16, DÉRIVÉE
    de la perception sémantique au lieu d'être maintenue à la main.

    ``signature`` : la vue affordances de l'écran (texte ou liste de lignes),
    chaque ligne au format ``* <libellé>\\t<id>\\t<Type>[\\t= <valeur>]``. Seuls
    les critères ``I<n>-LOW`` sont retenus, et seulement quand le libellé
    perçu est un nom TECHNIQUE de champ : sur un écran de sélection généré par
    SE16, ce libellé est le nom du champ de la table, donc indépendant de la
    langue (convention 3). Les champs de portée générale de l'écran, dont le
    libellé est une phrase traduite (le nombre maximal de résultats), sont
    ainsi naturellement écartés.

    Pourquoi dériver plutôt que déclarer : les critères sont POSITIONNELS
    (``I1``, ``I2``…) et leur ordre dépend du choix des champs de sélection,
    qui persiste par utilisateur. Un dictionnaire écrit à la main dérive en
    silence ; la perception, non. Relevé live sur DD03L : 31 critères présents
    là où le plan en avait observé 17.
    """
    lines: Iterable[str]
    if isinstance(signature, str):
        lines = signature.splitlines()
    else:
        lines = [str(line) for line in (signature or [])]
    criteria: dict[str, str] = {}
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        label = parts[0].lstrip("*").strip()
        locator = parts[1].strip()
        if not _SELECTION_LOW.search(locator):
            continue
        if not label or label == "?":
            continue
        if normalize_identifier(label) != label.upper():
            continue
        if " " in label:
            continue
        criteria.setdefault(label.upper(), locator)
    return criteria


def _client_dependent(fields: Any) -> bool:
    for row in fields or []:
        if isinstance(row, Mapping) and str(
                row.get("DATATYPE", "")).strip().upper() == _CLIENT_DATATYPE:
            return True
    return False


def _key_fields(fields: Any) -> list[str]:
    return sorted({str(row.get("FIELDNAME", "")).strip().upper()
                   for row in fields or []
                   if isinstance(row, Mapping)
                   and str(row.get("KEYFLAG", "")).strip().upper() == "X"})


def describe_ddic_table(table: str, fields: Any,
                        entry_count: Any = None) -> dict[str, Any]:
    """Fiche d'une table du périmètre, telle que l'artefact doit la porter.

    ``client_dependent`` se lit sur la présence d'un champ de type ``CLNT``,
    ``key_fields`` sur l'indicateur de clé : les deux attributs dont une
    future suite d'écriture a besoin pour savoir quoi cibler sans
    re-explorer.
    """
    rows = [row for row in (fields or []) if isinstance(row, Mapping)]
    return {
        "table": str(table).strip().upper(),
        "field_count": len(rows),
        "client_dependent": _client_dependent(rows),
        "key_fields": _key_fields(rows),
        "entry_count": None if entry_count is None else int(entry_count),
    }


def build_cross_channel_artifact(target_id: str, scope: Any,
                                 observed_at_utc: str, catalog: Any = None,
                                 services: Any = None, probes: Any = None,
                                 couples: Any = None, contracts: Any = None,
                                 tables: Any = None, candidates: Any = None,
                                 truncated: bool = False) -> dict[str, Any]:
    """Assemble l'artefact de croisement d'UNE cible (plan, scénario 7).

    Tout est trié par nom technique et le résumé est RECALCULÉ depuis les
    sections : il ne peut donc pas mentir sur son propre contenu.
    ``observed_at_utc`` est fourni par l'appelant, ce module restant pur et
    rejouable ; c'est aussi le seul champ que l'empreinte exclut.

    Les paramètres de campagne font partie de l'artefact : sans eux, deux
    exécutions de périmètres différents seraient comparables par accident.
    """
    scope_map = dict(scope or {})
    catalog_map = dict(catalog or {})
    service_records = sorted(
        (dict(s) for s in (services or []) if isinstance(s, Mapping)),
        key=lambda s: str(s.get("service_path", "")))
    probe_records = sorted(
        (dict(p) for p in (probes or []) if isinstance(p, Mapping)),
        key=lambda p: (str(p.get("service", "")), str(p.get("entity_set", ""))))
    couple_records = sorted(
        (dict(c) for c in (couples or []) if isinstance(c, Mapping)),
        key=lambda c: (str(c.get("service", "")), str(c.get("entity_set", ""))))
    contract_records = sorted(
        (dict(c) for c in (contracts or []) if isinstance(c, Mapping)),
        key=lambda c: (str(c.get("entity_set", "")), str(c.get("table", ""))))
    table_records = sorted(
        (dict(t) for t in (tables or []) if isinstance(t, Mapping)),
        key=lambda t: str(t.get("table", "")))
    candidate_records = sorted(
        (dict(c) for c in (candidates or []) if isinstance(c, Mapping)),
        key=lambda c: str(c.get("entity_set", "")))
    verdicts: dict[str, int] = {}
    for probe in probe_records:
        key = str(probe.get("verdict", "unknown"))
        verdicts[key] = verdicts.get(key, 0) + 1
    summary = {
        "services": len(service_records),
        "services_missing_from_catalog": len(catalog_map.get("missing", [])),
        "entity_sets": sum(len(s.get("entity_sets", []))
                           for s in service_records),
        "probe_verdicts": dict(sorted(verdicts.items())),
        "couples": len(couple_records),
        "couples_matched": sum(1 for c in couple_records if c.get("match")),
        "couples_not_compared": sum(
            1 for c in couple_records
            if str(c.get("verdict", "")) == "not_compared"),
        "field_contracts": len(contract_records),
        "write_candidates": len(candidate_records),
        "truncated": bool(truncated) or any(
            bool(s.get("truncated")) for s in service_records),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "target_id": str(target_id),
        "observed_at_utc": str(observed_at_utc),
        "scope": {
            "services": list(scope_map.get("services", [])),
            "client": str(scope_map.get("client", "")),
            "max_entity_sets": int(scope_map.get("max_entity_sets", 0)),
            "max_couples": int(scope_map.get("max_couples", 0)),
            "max_field_contracts": int(scope_map.get("max_field_contracts", 0)),
        },
        "catalog": {
            "size": int(catalog_map.get("catalog_size", 0)),
            "published": list(catalog_map.get("published", [])),
            "missing": list(catalog_map.get("missing", [])),
        },
        "summary": summary,
        "services": service_records,
        "probes": probe_records,
        "couples": couple_records,
        "field_contracts": contract_records,
        "tables": table_records,
        "write_candidates": candidate_records,
    }


def cross_channel_artifact_json(artifact: Any) -> str:
    """Sérialisation déterministe : clés triées, indentation fixe, fins LF."""
    return json.dumps(artifact, ensure_ascii=False, indent=2,
                      sort_keys=True) + "\n"


def cross_channel_hash(artifact: Any) -> str:
    """SHA-256 de l'artefact HORS horodatage : deux campagnes lisant les mêmes
    données produisent la même empreinte, quel que soit le moment du relevé."""
    stripped = {k: v for k, v in dict(artifact).items()
                if k != "observed_at_utc"}
    return hashlib.sha256(
        cross_channel_artifact_json(stripped).encode("utf-8")).hexdigest()


def _scope_incompatibilities(a: Mapping[str, Any],
                             b: Mapping[str, Any]) -> list[str]:
    reasons = []
    if sorted(a.get("services", [])) != sorted(b.get("services", [])):
        reasons.append("scope.services diffère")
    return reasons


def _entity_index(artifact: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for service in artifact.get("services", []):
        path = str(service.get("service_path", ""))
        for record in service.get("entity_sets", []):
            index["%s|%s" % (path, record.get("entity_set", ""))] = dict(record)
    return index


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes)) else []


def _as_artifact(value: Any) -> dict[str, Any]:
    """Un artefact, qu'il arrive en dict ou en TEXTE JSON. Accepter le texte
    évite à la couche ``resources/`` de désérialiser elle-même le fichier
    qu'elle vient de lire : une primitive pure reste atteinte par un keyword,
    jamais par un ``Evaluate`` qui importerait un module dans une suite."""
    if isinstance(value, (str, bytes)):
        try:
            loaded = json.loads(value)
        except ValueError as err:
            raise ValueError(
                f"Artefact illisible en JSON ({err}) : le fichier a-t-il bien "
                "été écrit par Write Cross Channel Artifact ?")
        return dict(loaded)
    return dict(value or {})


def compare_cross_channel_artifacts(artifact_a: Any,
                                    artifact_b: Any) -> dict[str, Any]:
    """Compare deux artefacts de même schéma, à périmètre équivalent.

    Les deux arguments acceptent un dict ou le TEXTE JSON du fichier.

    Retour JSON-safe séparant volontairement les trois natures d'écart que le
    plan distingue : **disponibilité** (entity set apparu ou disparu,
    adressabilité changée), **volumétrie** (verdict de couple changé) et
    **schéma** (contrat de champs dégradé, mesuré sur le nombre d'appariements
    et sur les orphelins).

    Aucune égalité stricte n'est exigée entre une cible ECC et une cible
    S/4HANA : c'est l'écart qui porte l'information. L'ordre, la langue et
    l'horodatage n'en créent aucun ; des périmètres différents marquent la
    comparaison non équivalente au lieu de produire des écarts trompeurs.
    """
    a = _as_artifact(artifact_a)
    b = _as_artifact(artifact_b)
    if a.get("schema_version") != b.get("schema_version"):
        raise ValueError(
            "schema_version différent : comparaison impossible "
            f"({a.get('schema_version')!r} vs {b.get('schema_version')!r}).")
    reasons = _scope_incompatibilities(a.get("scope", {}), b.get("scope", {}))
    index_a, index_b = _entity_index(a), _entity_index(b)
    common = sorted(set(index_a) & set(index_b))
    addressability = [
        {"entity_set": key, "a": index_a[key].get("addressable"),
         "b": index_b[key].get("addressable")}
        for key in common
        if bool(index_a[key].get("addressable")) != bool(
            index_b[key].get("addressable"))]

    couples_a = {str(c.get("entity_set", "")): dict(c)
                 for c in _sequence(a.get("couples"))}
    couples_b = {str(c.get("entity_set", "")): dict(c)
                 for c in _sequence(b.get("couples"))}
    volume_changed = [
        {"entity_set": name, "a": couples_a[name].get("verdict"),
         "b": couples_b[name].get("verdict")}
        for name in sorted(set(couples_a) & set(couples_b))
        if couples_a[name].get("verdict") != couples_b[name].get("verdict")]

    contracts_a = {str(c.get("entity_set", "")): dict(c)
                   for c in _sequence(a.get("field_contracts"))}
    contracts_b = {str(c.get("entity_set", "")): dict(c)
                   for c in _sequence(b.get("field_contracts"))}
    schema_changed = []
    for name in sorted(set(contracts_a) & set(contracts_b)):
        summary_a = dict(contracts_a[name].get("summary", {}))
        summary_b = dict(contracts_b[name].get("summary", {}))
        if summary_a != summary_b:
            schema_changed.append({"entity_set": name, "a": summary_a,
                                   "b": summary_b})
    return {
        "compatible": not reasons,
        "incompatibility_reasons": reasons,
        "target_a": str(a.get("target_id", "")),
        "target_b": str(b.get("target_id", "")),
        "only_in_a": sorted(set(index_a) - set(index_b)),
        "only_in_b": sorted(set(index_b) - set(index_a)),
        "common": len(common),
        "addressability_changed": addressability,
        "volume_verdict_changed": volume_changed,
        "field_contract_changed": schema_changed,
    }


def render_cross_channel_report(comparison: Any) -> str:
    """Rapport Markdown d'une comparaison, lisible hors SAP."""
    data = dict(comparison or {})
    lines = [
        "# Comparaison de croisements DDIC et OData",
        "",
        f"Cibles : `{data.get('target_a', '')}` vs `{data.get('target_b', '')}`.",
    ]
    if not data.get("compatible", True):
        lines.append("")
        lines.append("**Périmètres non équivalents, comparaison non probante :**")
        lines.extend(f"- {reason}"
                     for reason in data.get("incompatibility_reasons", []))
    lines.append("")
    lines.append(f"- entity sets communs : {data.get('common', 0)}")
    for key, label in (("only_in_a", "présents seulement sur A"),
                       ("only_in_b", "présents seulement sur B")):
        names = list(data.get(key, []))
        lines.append(f"- {label} : {len(names)}"
                     + (f" ({', '.join(names)})" if names else ""))
    for key, label in (("addressability_changed", "adressabilité changée"),
                       ("volume_verdict_changed", "verdict volumétrique changé"),
                       ("field_contract_changed", "contrat de champs changé")):
        diffs = list(data.get(key, []))
        lines.append(f"- {label} : {len(diffs)}")
        lines.extend(
            f"  - `{d.get('entity_set', '')}` : {d.get('a')} -> {d.get('b')}"
            for d in diffs)
    return "\n".join(lines) + "\n"
