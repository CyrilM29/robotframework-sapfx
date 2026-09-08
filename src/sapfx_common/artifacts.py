"""Artefacts JSON déterministes : écriture, relecture, comparaison. Logique pure.

Le dépôt produit des artefacts « rejouables » depuis l'inventaire DDIC : un JSON
aux clés triées, une empreinte SHA-256 qui EXCLUT l'horodatage (deux runs aux
mêmes données donnent la même empreinte), une comparaison de deux cibles hors
système. La même mécanique s'était réécrite quatre fois (inventaire DDIC,
croisement de canaux, surface RFC, posture de sécurité), puis une cinquième en
``Evaluate json.dumps(...)`` dans le page object du registre de capacités : la
revue indépendante du 2026-09-07 l'a relevé (backlog § 2.22). Ce module est la
version GÉNÉRIQUE, pour tout nouvel artefact ; les quatre modules historiques
gardent leur sérialisation (des artefacts committés en dépendent).

Importé comme bibliothèque Robot (``Library    sapfx_common.artifacts``) : chaque
fonction de ``__all__`` est un keyword, d'où des fonctions de module à
signatures JSON-safe et des listes acceptées en chaîne à virgules (via rf-mcp
tout argument arrive en chaîne, ``sapfx_common.robot_args``).

Deux propriétés délibérées : l'artefact DIT ce que son empreinte couvre
(``hash_scope``), et la relecture RECALCULE l'empreinte sur ce périmètre, donc
un artefact édité à la main après coup est refusé au lieu d'être comparé.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from typing import Any, Mapping

from sapfx_common.robot_args import as_name_list

__all__ = [
    "deterministic_json",
    "artifact_hash",
    "build_deterministic_artifact",
    "write_deterministic_artifact",
    "read_deterministic_artifact",
    "compare_deterministic_artifacts",
]

TIMESTAMP_KEY = "generated_at"
HASH_KEY = "sha256"
SCOPE_KEY = "hash_scope"
DEFAULT_EXCLUDED = (TIMESTAMP_KEY, HASH_KEY, SCOPE_KEY)


def deterministic_json(payload: Any) -> str:
    """Sérialisation canonique : clés triées, indentation 2, UTF-8 non échappé,
    fin de ligne LF. La même pour le fichier et pour l'empreinte."""
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _scope(payload: Mapping[str, Any], hashed_keys: Any,
           excluded_keys: Any) -> tuple[list[str], list[str]]:
    hashed = as_name_list(hashed_keys, "hashed_keys") if hashed_keys not in (None, "") else []
    excluded = list(DEFAULT_EXCLUDED)
    for key in (as_name_list(excluded_keys, "excluded_keys")
                if excluded_keys not in (None, "") else []):
        if key not in excluded:
            excluded.append(key)
    unknown = [key for key in hashed if key not in payload]
    if unknown:
        raise ValueError(
            "Clé(s) à hacher absente(s) de l'artefact : %s (clés présentes : %s)."
            % (", ".join(unknown), ", ".join(sorted(payload)) or "aucune"))
    return sorted(hashed), sorted(excluded)


def _hashed_subset(payload: Mapping[str, Any], hashed: list[str],
                   excluded: list[str]) -> dict[str, Any]:
    if hashed:
        return {key: payload[key] for key in hashed}
    return {key: value for key, value in payload.items() if key not in excluded}


def artifact_hash(payload: Mapping[str, Any], hashed_keys: Any = None,
                  excluded_keys: Any = None) -> str:
    """SHA-256 du JSON canonique du PÉRIMÈTRE haché : les seules
    ``hashed_keys`` quand elles sont données, sinon tout SAUF les clés exclues
    (l'horodatage, l'empreinte et la portée elle-même, toujours exclus)."""
    if not isinstance(payload, Mapping):
        raise ValueError("Un artefact est un dictionnaire, reçu %s." % type(payload).__name__)
    hashed, excluded = _scope(payload, hashed_keys, excluded_keys)
    subset = _hashed_subset(payload, hashed, excluded)
    return hashlib.sha256(deterministic_json(subset).encode("utf-8")).hexdigest()


def build_deterministic_artifact(payload: Mapping[str, Any], hashed_keys: Any = None,
                                 excluded_keys: Any = None,
                                 timestamp: Any = None) -> dict[str, Any]:
    """L'artefact complet : le contenu, ``hash_scope`` (ce que l'empreinte
    couvre), ``sha256`` et ``generated_at`` (UTC ISO 8601 ; ``timestamp`` =
    une chaîne pour la fixer, ``False`` pour l'omettre)."""
    if not isinstance(payload, Mapping):
        raise ValueError("Un artefact est un dictionnaire, reçu %s." % type(payload).__name__)
    hashed, excluded = _scope(payload, hashed_keys, excluded_keys)
    artifact: dict[str, Any] = {key: value for key, value in payload.items()
                                if key not in (HASH_KEY, SCOPE_KEY, TIMESTAMP_KEY)}
    artifact[SCOPE_KEY] = {"hashed_keys": hashed, "excluded_keys": excluded}
    artifact[HASH_KEY] = hashlib.sha256(
        deterministic_json(_hashed_subset(artifact, hashed, excluded)).encode("utf-8")
    ).hexdigest()
    if timestamp is False or (isinstance(timestamp, str)
                              and timestamp.strip().lower() in ("false", "no", "none")):
        return artifact
    if isinstance(timestamp, str) and timestamp.strip():
        artifact[TIMESTAMP_KEY] = timestamp.strip()
    else:
        artifact[TIMESTAMP_KEY] = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00")
    return artifact


def write_deterministic_artifact(path: str, payload: Mapping[str, Any],
                                 hashed_keys: Any = None, excluded_keys: Any = None,
                                 timestamp: Any = None) -> str:
    """Écrit `build_deterministic_artifact` dans ``path`` (UTF-8, LF, dossier
    créé) et retourne le chemin absolu."""
    artifact = build_deterministic_artifact(payload, hashed_keys, excluded_keys, timestamp)
    target = os.path.abspath(str(path))
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(deterministic_json(artifact))
    return target


def _load(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    with open(str(value), encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("L'artefact %s n'est pas un objet JSON." % value)
    return data


def read_deterministic_artifact(path: Any) -> dict[str, Any]:
    """Relit un artefact et VÉRIFIE son empreinte sur le périmètre qu'il
    déclare : une empreinte absente ou qui ne se recalcule pas = ``ValueError``
    (artefact altéré ou écrit par un autre outil), jamais une comparaison sur
    du contenu douteux."""
    artifact = _load(path)
    scope = artifact.get(SCOPE_KEY)
    recorded = artifact.get(HASH_KEY)
    if not isinstance(scope, Mapping) or not recorded:
        raise ValueError(
            "L'artefact %s ne porte pas de périmètre d'empreinte (%s) et d'empreinte "
            "(%s) : il n'a pas été écrit par Write Deterministic Artifact."
            % (path, SCOPE_KEY, HASH_KEY))
    hashed = list(scope.get("hashed_keys") or [])
    excluded = list(scope.get("excluded_keys") or DEFAULT_EXCLUDED)
    missing = [key for key in hashed if key not in artifact]
    if missing:
        raise ValueError("L'artefact %s a perdu des clés hachées : %s."
                         % (path, ", ".join(missing)))
    actual = hashlib.sha256(
        deterministic_json(_hashed_subset(artifact, hashed, excluded)).encode("utf-8")
    ).hexdigest()
    if actual != recorded:
        raise ValueError(
            "Empreinte de l'artefact %s invalide : enregistrée %s, recalculée %s "
            "(artefact modifié après écriture ?)." % (path, recorded, actual))
    return artifact


def _differences(a: Any, b: Any, path: str, out: list[dict[str, str]]) -> None:
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        for key in sorted(set(a) | set(b)):
            child = "%s.%s" % (path, key) if path else str(key)
            if key not in a:
                out.append({"path": child, "a": "", "b": json.dumps(b[key], ensure_ascii=False, sort_keys=True)})
            elif key not in b:
                out.append({"path": child, "a": json.dumps(a[key], ensure_ascii=False, sort_keys=True), "b": ""})
            else:
                _differences(a[key], b[key], child, out)
        return
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for index, (left, right) in enumerate(zip(a, b, strict=True)):
            _differences(left, right, "%s[%d]" % (path, index), out)
        return
    if a != b:
        out.append({"path": path, "a": json.dumps(a, ensure_ascii=False, sort_keys=True),
                    "b": json.dumps(b, ensure_ascii=False, sort_keys=True)})


def compare_deterministic_artifacts(a: Any, b: Any) -> dict[str, Any]:
    """Compare deux artefacts (chemins ou dicts, empreintes VÉRIFIÉES) sur leur
    périmètre haché : ``{identical, sha256_a, sha256_b, differences}`` où
    chaque différence nomme son chemin (``capabilities.tree.read_nodes.verdict``).
    Deux périmètres différents sont REFUSÉS (non probants), jamais moyennés."""
    left = read_deterministic_artifact(a)
    right = read_deterministic_artifact(b)
    if left[SCOPE_KEY] != right[SCOPE_KEY]:
        raise ValueError(
            "Périmètres d'empreinte différents, comparaison non probante : %s contre %s."
            % (json.dumps(left[SCOPE_KEY], sort_keys=True),
               json.dumps(right[SCOPE_KEY], sort_keys=True)))
    hashed = list(left[SCOPE_KEY].get("hashed_keys") or [])
    excluded = list(left[SCOPE_KEY].get("excluded_keys") or DEFAULT_EXCLUDED)
    differences: list[dict[str, str]] = []
    _differences(_hashed_subset(left, hashed, excluded),
                 _hashed_subset(right, hashed, excluded), "", differences)
    return {
        "identical": left[HASH_KEY] == right[HASH_KEY],
        "sha256_a": left[HASH_KEY],
        "sha256_b": right[HASH_KEY],
        "differences": differences,
    }
