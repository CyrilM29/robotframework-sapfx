"""Lecture des structures ``BAPIRET2`` retournées par les BAPIs.

Le pattern SAP de préparation de données robuste : appeler la BAPI, LIRE sa
table ``RETURN`` (un appel « réussi » techniquement peut porter un message
d'erreur métier), échouer sur les types bloquants ``E``/``A``/``X``, puis
``BAPI_TRANSACTION_COMMIT``. Conformément à la convention n°3 du projet
(assertions indépendantes de la locale), la DÉCISION se prend sur le TYPE du
message, jamais sur son texte : le texte n'est joint que pour le lecteur
humain. Logique pure ; l'appel RFC lui-même vit dans ``SapApiLibrary``.
"""
from __future__ import annotations

from typing import Any, Mapping

from sapfx_common.robot_args import as_name_list

#: Types de message BAPIRET2 bloquants : Error, Abort, eXit.
FAILING_TYPES = ("E", "A", "X")


def iter_bapi_messages(result: Mapping[str, Any],
                       return_key: str = "RETURN") -> list[dict[str, Any]]:
    """Normalise la structure ``RETURN`` d'un résultat de BAPI en liste de
    messages ``{"type", "id", "number", "message"}``. Tolère les trois formes
    rencontrées : table (liste de dicts), structure seule (dict), absente
    (liste vide). Les clés BAPIRET2 sont lues en majuscules (``TYPE``,
    ``ID``, ``NUMBER``, ``MESSAGE``)."""
    raw = result.get(return_key)
    if raw is None:
        return []
    entries = raw if isinstance(raw, (list, tuple)) else [raw]
    messages: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        message_type = str(entry.get("TYPE", "")).strip().upper()
        if not message_type and not entry.get("MESSAGE"):
            continue   # ligne vide (structure RETURN initiale non remplie)
        messages.append({
            "type": message_type,
            "id": str(entry.get("ID", "")).strip(),
            "number": str(entry.get("NUMBER", "")).strip(),
            "message": str(entry.get("MESSAGE", "")).strip(),
        })
    return messages


def failing_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filtre les messages dont le TYPE est bloquant (``E``/``A``/``X``)."""
    return [m for m in messages if m.get("type") in FAILING_TYPES]


def format_bapi_failure(function_name: str,
                        failing: list[dict[str, Any]],
                        rollback_hint: bool = True) -> str:
    """Message d'échec auto-corrigible d'un appel BAPI : chaque message
    bloquant sur sa ligne (``TYPE ID/NUMBER : texte``), puis le rappel du
    rollback (une BAPI en échec laisse la LUW ouverte côté serveur).
    ``rollback_hint=False`` l'omet pour une LECTURE (XBP), qui n'ouvre aucune
    LUW : le rappel y envoyait chercher une écriture qui n'existe pas."""
    lines = ["La BAPI %s a retourné %d message(s) bloquant(s) (type E/A/X) :"
             % (function_name, len(failing))]
    for message in failing:
        lines.append("  %s %s/%s : %s" % (
            message.get("type", "?"), message.get("id", ""),
            message.get("number", ""), message.get("message", "")))
    if rollback_hint:
        lines.append("Penser à Rollback Bapi Transaction avant de réessayer "
                     "(la LUW reste ouverte côté serveur).")
    return "\n".join(lines)


def message_identity(message: Mapping[str, Any]) -> str:
    """L'identifiant ``CLASSE/TYPE/NUMÉRO`` d'un message BAPIRET2
    (``R11/E/657``), la forme des canaux écran et RFC : rien de localisé n'y
    entre (convention n°3). Numéro complété à trois chiffres ; chaîne VIDE si
    une des trois parties manque, jamais un identifiant inventé."""
    parts = (str(message.get("id", "")).strip().upper(),
             str(message.get("type", "")).strip().upper(),
             str(message.get("number", "")).strip())
    if not all(parts):
        return ""
    number = parts[2].zfill(3) if parts[2].isdigit() else parts[2]
    return "%s/%s/%s" % (parts[0], parts[1], number)


def expected_message_ids(value: Any, argument: str = "accept") -> list[str]:
    """Normalise des identifiants de REFUS attendus ou tolérés, donnés en
    liste, en chaîne à virgules ou en liste-littérale (frontière Robot/MCP).

    Refusé AVANT tout appel : une forme autre que ``CLASSE/TYPE/NUMÉRO``
    (``R11-657``, ``R11/657``) et un type non bloquant (``W``, ``S``, ``I``),
    qui ne fait jamais échouer une BAPI et dont la mention cacherait une faute
    de frappe. La classe peut porter un espace de noms (``/BOBF/FRW_COMMON``),
    d'où un découpage par la DROITE."""
    ids = []
    for raw in as_name_list(value, argument):
        parts = raw.strip().upper().rsplit("/", 2)
        if (len(parts) != 3 or not all(parts) or len(parts[1]) != 1
                or not parts[2].isdigit()):
            raise ValueError(
                "%s : %r n'est pas un identifiant de message CLASSE/TYPE/NUMÉRO "
                "(exemple : R11/E/657)." % (argument, raw))
        if parts[1] not in FAILING_TYPES:
            raise ValueError(
                "%s : %r est de type %s, qui ne fait jamais échouer une BAPI "
                "(seuls %s bloquent) : rien à attendre ni à tolérer."
                % (argument, raw, parts[1], "/".join(FAILING_TYPES)))
        ids.append("%s/%s/%s" % (parts[0], parts[1], parts[2].zfill(3)))
    return ids


def split_by_identity(failing: list[dict[str, Any]], accepted: list[str]
                      ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(tolérés, bloquants)`` : un message bloquant n'est toléré que si son
    identifiant EXACT figure dans ``accepted`` ; un message sans identifiant
    complet reste bloquant."""
    tolerated = [m for m in failing if message_identity(m) in accepted]
    return tolerated, [m for m in failing if m not in tolerated]


def describe_bapi_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les messages avec leur identifiant (``message_id``), JSON-safe."""
    return [dict(m, message_id=message_identity(m)) for m in messages]


def format_bapi_message_id_mismatch(function_name: str, expected: str,
                                    failing: list[dict[str, Any]]) -> str:
    """La BAPI a refusé, mais pas avec l'identifiant attendu : les
    identifiants observés d'abord, les textes ensuite, pour information."""
    observed = ", ".join(message_identity(m) or "(sans identifiant)" for m in failing)
    texts = " | ".join(m.get("message", "") for m in failing)
    return ("La BAPI %s a bien refusé, mais pas avec l'identifiant attendu : "
            "attendu %s, observé %s. Textes du serveur, pour information "
            "seulement : %s" % (function_name, expected, observed, texts))


def format_bapi_missing_failure(function_name: str, expected: str,
                                messages: list[dict[str, Any]]) -> str:
    """La BAPI n'a RIEN refusé là où un refus était attendu : un oracle vert
    parce que rien n'a échoué ne prouverait rien."""
    seen = ", ".join(message_identity(m) or m.get("type", "?") for m in messages)
    return ("La BAPI %s devait refuser avec %s, mais sa table RETURN ne porte "
            "aucun message bloquant (%s). Le refus attendu ne se produit plus : "
            "la cible a changé, ou l'appel ne provoque plus le cas visé."
            % (function_name, expected, seen or "RETURN vide"))
