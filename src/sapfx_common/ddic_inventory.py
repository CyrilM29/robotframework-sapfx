"""Inventaire DDIC : périmètre, classification, artefact déterministe, comparaison.

Logique pure (aucune E/S, aucun COM) du canal « inventaire de tables ECC et
S/4HANA » (spec ``specs/inventaire-tables-ecc-s4hana.md``) : validation d'un
périmètre de campagne borné, barème de classification construit depuis le
domaine ``TABCLASS`` relevé sur la cible (jamais de mémoire), assemblage d'un
artefact JSON trié et reproductible, hash de comparaison excluant l'horodatage,
et comparaison de deux artefacts à périmètre équivalent.

Les E/S écran (SE16, sélection multiple, DD02L) vivent dans le mixin
``SapEccLibrary/keywords/_ddic.py`` ; l'écriture du fichier reste dans le
keyword. Relevés live fondateurs (A4H, 2026-08-17) : le domaine ``TABCLASS``
expose ``TRANSP``/``INTTAB``/``VIEW``/``APPEND`` ; ``TRANSP`` est consultable
(SCARR, SFLIGHT), ``VIEW`` est une vue (SCUS_BOOK), ``INTTAB`` est rejeté par
SE16 en type ``E`` (SFL_AUX). ``APPEND`` n'a jamais été observé : il reste
``unknown`` tant qu'une cible n'en fournit pas la preuve.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1

#: Barème appuyé par une observation live (voir docstring du module). Une
#: valeur absente d'ici, ``APPEND`` comprise, se normalise en ``unknown``.
BASE_CLASS_MAP: Mapping[str, str] = {
    "TRANSP": "table",
    "VIEW": "view",
    "INTTAB": "non_consultable_ddic",
}

#: Classes normalisées admises dans un artefact (ordre du résumé).
NORMALIZED_CLASSES = ("table", "view", "non_consultable_ddic", "unknown")

#: Statuts de sonde SE16 admis (spec, « Modèle de classification »).
PROBE_STATUSES = (
    "selection_screen_reached",
    "rejected",
    "authorization_blocked",
    "runtime_error",
    "not_probed",
)


#: Types d'objets TADIR interrogés par défaut : tables ET vues (la découverte
#: aveugle aux vues était l'écart 2 de l'exploration du 2026-08-17).
DEFAULT_OBJECT_TYPES = ("TABL", "VIEW")


def _as_value_list(values: Iterable[str] | str | None) -> list[str]:
    """Une liste de valeurs, robuste au SCALAIRE : une chaîne seule devient
    ``[chaîne]`` au lieu d'être itérée caractère par caractère (le piège des
    variables ``-v`` Robot, toujours scalaires, qui priment sur une liste
    ``@{}`` du fichier)."""
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return list(values)


def validate_scope(
    packages: Sequence[str] | str | None,
    prefixes: Sequence[str] | str | None,
    max_objects: Any,
    batch_size: Any,
    object_types: Sequence[str] | str | None = None,
) -> dict[str, Any]:
    """Valide et normalise le périmètre d'une campagne.

    Retourne ``{"packages": [...], "prefixes": [...], "object_types": [...],
    "max_objects": int, "batch_size": int}`` : entrées épurées (blancs
    retirés, doublons supprimés, tri stable), limites entières strictement
    positives, types d'objets TADIR consignés (``TABL`` et ``VIEW`` par
    défaut : ils font partie du périmètre comparé, pas un détail
    d'implémentation). ``packages``, ``prefixes`` et ``object_types``
    acceptent une liste OU une valeur seule. Lève ``ValueError`` avec la
    cause exacte sinon : sélection vide (ni package ni préfixe), limite
    absente, non entière ou non positive. La campagne refuse un périmètre
    sans borne : c'est ici que le refus est décidé.
    """
    def _clean(values: Sequence[str] | str | None) -> list[str]:
        seen = sorted({str(v).strip() for v in _as_value_list(values)
                       if str(v).strip()})
        return seen

    cleaned_packages = _clean(packages)
    cleaned_prefixes = _clean(prefixes)
    if not cleaned_packages and not cleaned_prefixes:
        raise ValueError(
            "Périmètre vide : au moins un package ou un préfixe est requis.")

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

    cleaned_types = [t.upper() for t in _clean(object_types)]
    return {
        "packages": cleaned_packages,
        "prefixes": cleaned_prefixes,
        "object_types": cleaned_types or sorted(DEFAULT_OBJECT_TYPES),
        "max_objects": _positive_int(max_objects, "max_objects"),
        "batch_size": _positive_int(batch_size, "batch_size"),
    }


def bounded_union(
    discovered: Iterable[Iterable[str] | str],
    max_objects: int,
) -> tuple[list[str], bool]:
    """Union déterministe de plusieurs listes de noms, bornée par ``max_objects``.

    Dédoublonne, trie par nom technique, applique la borne. Un groupe qui est
    une chaîne seule compte pour UN nom (jamais itéré caractère par
    caractère). Retourne ``(noms, truncated)`` : ``truncated=True`` quand la
    borne a retiré des objets, jamais un succès silencieux (spec, scénario 3).
    """
    union = sorted({str(n).strip() for group in discovered
                    for n in _as_value_list(group)
                    if str(n).strip()})
    if len(union) > max_objects:
        return union[:max_objects], True
    return union, False


def classification_map(
    domain_values: Iterable[str],
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Barème de classification restreint aux valeurs RÉELLES du domaine cible.

    ``domain_values`` vient d'un relevé live du domaine ``TABCLASS`` (DD07L) :
    seules les valeurs présentes sur la cible ET appuyées par une observation
    (``BASE_CLASS_MAP``) entrent au barème. ``extra`` permet une surcharge site
    explicite (p.ex. ``{"APPEND": "non_consultable_ddic"}`` une fois la preuve
    faite), refusée si la classe cible n'est pas admise.
    """
    values = {str(v).strip().upper() for v in domain_values if str(v).strip()}
    mapping = {v: BASE_CLASS_MAP[v] for v in sorted(values)
               if v in BASE_CLASS_MAP}
    for raw, normalized in (extra or {}).items():
        if normalized not in NORMALIZED_CLASSES:
            raise ValueError(
                f"Classe normalisée inconnue {normalized!r} pour {raw!r} ; "
                f"admises : {', '.join(NORMALIZED_CLASSES)}.")
        mapping[str(raw).strip().upper()] = normalized
    return mapping


def normalize_class(tabclass: Any, class_map: Mapping[str, str]) -> str:
    """Classe normalisée d'une valeur brute ``TABCLASS`` : ``unknown`` hors barème."""
    return class_map.get(str(tabclass or "").strip().upper(), "unknown")


def build_object_entry(
    object_name: str,
    class_map: Mapping[str, str],
    package: str = "",
    tadir_type: str = "",
    dd02l_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Entrée d'inventaire d'UN objet, valeurs brutes conservées.

    ``dd02l_row`` est la ligne DD02L de l'objet (clés techniques ``TABCLASS``,
    ``AS4LOCAL``, ``AS4VERS``) ou ``None`` quand DD02L ne connaît pas l'objet :
    l'absence est alors SIGNALÉE (``present=False``, motif explicite), jamais
    assimilée à une table vide (spec, scénario 4). La sonde SE16 démarre à
    ``not_probed`` ; ``record_probe`` la met à jour.
    """
    row = dict(dd02l_row or {})
    present = bool(row)
    tabclass = str(row.get("TABCLASS", "")).strip().upper()
    entry: dict[str, Any] = {
        "object_name": str(object_name).strip(),
        "package": str(package).strip(),
        "tadir_type": str(tadir_type).strip(),
        "ddic": {
            "present": present,
            "tabclass": tabclass,
            "as4local": str(row.get("AS4LOCAL", "")).strip(),
            "as4vers": str(row.get("AS4VERS", "")).strip(),
        },
        "class": normalize_class(tabclass, class_map) if present else "unknown",
        "probe": {"status": "not_probed", "message_type": "", "detail": ""},
        "entry_count": None,
        "entry_count_reason": "not_measured",
    }
    if not present:
        entry["class_reason"] = "absent_from_dd02l"
    return entry


def record_probe(
    entry: dict[str, Any],
    status: str,
    message_type: str = "",
    detail: str = "",
    entry_count: Any = None,
) -> dict[str, Any]:
    """Consigne le résultat technique d'une sonde SE16 dans une entrée.

    ``status`` doit appartenir à ``PROBE_STATUSES`` (échec actionnable sinon) ;
    ``message_type`` est le TYPE du message de statut (``E``…), jamais son
    texte localisé. Un ``entry_count`` fourni bascule
    ``entry_count_reason`` à ``measured``. Retourne l'entrée mise à jour.
    """
    if status not in PROBE_STATUSES:
        raise ValueError(
            f"Statut de sonde inconnu {status!r} ; admis : "
            f"{', '.join(PROBE_STATUSES)}.")
    entry["probe"] = {
        "status": status,
        "message_type": str(message_type or ""),
        "detail": str(detail or ""),
    }
    if entry_count is not None:
        entry["entry_count"] = int(entry_count)
        entry["entry_count_reason"] = "measured"
    return entry


def sample_for_probe(
    entries: Sequence[Mapping[str, Any]],
    per_class: int = 2,
    classes: Sequence[str] | str = ("table", "view", "non_consultable_ddic"),
) -> list[str]:
    """Échantillon déterministe et borné pour la sonde SE16 (spec, scénario 5).

    Les ``per_class`` premiers noms (tri technique) de chaque classe demandée
    (``classes`` accepte une liste ou une valeur seule) : jamais tous les
    objets, jamais un choix dépendant de l'ordre d'arrivée.
    """
    sample: list[str] = []
    for wanted in _as_value_list(classes):
        names = sorted(e["object_name"] for e in entries
                       if e.get("class") == wanted)
        sample.extend(names[:max(0, int(per_class))])
    return sample


def build_inventory(
    target_id: str,
    scope: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    observed_at_utc: str,
    truncated: bool = False,
) -> dict[str, Any]:
    """Assemble l'artefact d'inventaire d'UNE cible (spec, scénario 8).

    Objets triés par ``object_name``, résumé recalculé depuis les entrées
    (jamais fourni à la main : la somme des classes couvre tous les objets par
    construction). ``observed_at_utc`` est fourni par l'appelant : ce module
    reste pur et rejouable.
    """
    ordered = sorted((dict(e) for e in entries), key=lambda e: e["object_name"])
    classes: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for entry in ordered:
        classes[entry["class"]] += 1
        statuses[entry["probe"]["status"]] += 1
    summary: dict[str, Any] = {
        "discovered": len(ordered),
        "probed": len(ordered) - statuses["not_probed"],
        "truncated": bool(truncated),
    }
    for wanted in NORMALIZED_CLASSES:
        summary[wanted] = classes[wanted]
    summary["authorization_blocked"] = statuses["authorization_blocked"]
    return {
        "schema_version": SCHEMA_VERSION,
        "target_id": str(target_id),
        "observed_at_utc": str(observed_at_utc),
        "selection": {
            "packages": list(scope.get("packages", [])),
            "prefixes": list(scope.get("prefixes", [])),
            "object_types": list(scope.get("object_types", [])),
            "max_objects": int(scope.get("max_objects", 0)),
            "batch_size": int(scope.get("batch_size", 0)),
        },
        "summary": summary,
        "objects": ordered,
    }


def inventory_json(inventory: Mapping[str, Any]) -> str:
    """Sérialisation déterministe : clés triées, indentation fixe, fins LF."""
    return json.dumps(inventory, ensure_ascii=False, indent=2,
                      sort_keys=True) + "\n"


def comparison_hash(inventory: Mapping[str, Any]) -> str:
    """SHA-256 de l'artefact HORS horodatage.

    Deux campagnes lisant les mêmes données produisent le même hash quel que
    soit le moment du relevé (spec, scénario 8) : ``observed_at_utc`` est
    exclu explicitement, tout le reste compte.
    """
    stripped = {k: v for k, v in inventory.items() if k != "observed_at_utc"}
    return hashlib.sha256(inventory_json(stripped).encode("utf-8")).hexdigest()


def _selection_compatible(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[str]:
    """Raisons d'incompatibilité de deux périmètres (vide = comparables)."""
    reasons = []
    for key in ("packages", "prefixes", "object_types"):
        if sorted(a.get(key, [])) != sorted(b.get(key, [])):
            reasons.append(f"selection.{key} diffère")
    return reasons


def compare_inventories(
    inventory_a: Mapping[str, Any],
    inventory_b: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare deux artefacts du même schéma à périmètre équivalent.

    Retour JSON-safe : compatibilité (périmètres différents = comparaison
    marquée non équivalente, jamais des écarts trompeurs), ensembles
    ``only_in_a``/``only_in_b``/``common``, et pour les objets communs les
    reclassements, changements de consultabilité SE16, blocages d'autorisation
    et écarts de volumétrie quand elle existe des deux côtés. L'ordre, la
    langue et l'horodatage ne créent aucun écart (spec, scénario 9).
    """
    if inventory_a.get("schema_version") != inventory_b.get("schema_version"):
        raise ValueError(
            "schema_version différent : comparaison impossible "
            f"({inventory_a.get('schema_version')!r} vs "
            f"{inventory_b.get('schema_version')!r}).")
    reasons = _selection_compatible(inventory_a.get("selection", {}),
                                    inventory_b.get("selection", {}))
    objects_a = {e["object_name"]: e for e in inventory_a.get("objects", [])}
    objects_b = {e["object_name"]: e for e in inventory_b.get("objects", [])}
    common = sorted(set(objects_a) & set(objects_b))
    reclassified = []
    probe_changed = []
    count_changed = []
    for name in common:
        entry_a, entry_b = objects_a[name], objects_b[name]
        if entry_a["class"] != entry_b["class"]:
            reclassified.append({"object_name": name,
                                 "a": entry_a["class"], "b": entry_b["class"]})
        if entry_a["probe"]["status"] != entry_b["probe"]["status"]:
            probe_changed.append({
                "object_name": name,
                "a": entry_a["probe"]["status"],
                "b": entry_b["probe"]["status"]})
        count_a, count_b = entry_a.get("entry_count"), entry_b.get("entry_count")
        if count_a is not None and count_b is not None and count_a != count_b:
            count_changed.append({"object_name": name,
                                  "a": count_a, "b": count_b})
    return {
        "compatible": not reasons,
        "incompatibility_reasons": reasons,
        "target_a": inventory_a.get("target_id", ""),
        "target_b": inventory_b.get("target_id", ""),
        "only_in_a": sorted(set(objects_a) - set(objects_b)),
        "only_in_b": sorted(set(objects_b) - set(objects_a)),
        "common": len(common),
        "reclassified": reclassified,
        "probe_changed": probe_changed,
        "count_changed": count_changed,
    }


def render_comparison_report(comparison: Mapping[str, Any]) -> str:
    """Rapport Markdown d'une comparaison, lisible hors SAP."""
    lines = [
        "# Comparaison d'inventaires DDIC",
        "",
        f"Cibles : `{comparison['target_a']}` vs `{comparison['target_b']}`.",
    ]
    if not comparison["compatible"]:
        lines.append("")
        lines.append("**Périmètres non équivalents, comparaison non probante :**")
        lines.extend(f"- {reason}" for reason
                     in comparison["incompatibility_reasons"])
    lines.append("")
    lines.append(f"- objets communs : {comparison['common']}")
    for key, label in (("only_in_a", "présents seulement sur A"),
                       ("only_in_b", "présents seulement sur B")):
        names = comparison[key]
        lines.append(f"- {label} : {len(names)}"
                     + (f" ({', '.join(names)})" if names else ""))
    for key, label in (("reclassified", "reclassés"),
                       ("probe_changed", "consultabilité SE16 changée"),
                       ("count_changed", "volumétrie changée")):
        diffs = comparison[key]
        lines.append(f"- {label} : {len(diffs)}")
        lines.extend(
            f"  - `{d['object_name']}` : {d['a']} -> {d['b']}" for d in diffs)
    return "\n".join(lines) + "\n"
