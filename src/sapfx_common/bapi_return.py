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
                        failing: list[dict[str, Any]]) -> str:
    """Message d'échec auto-corrigible d'un appel BAPI : chaque message
    bloquant sur sa ligne (``TYPE ID/NUMBER : texte``), puis le rappel du
    rollback (une BAPI en échec laisse la LUW ouverte côté serveur)."""
    lines = ["La BAPI %s a retourné %d message(s) bloquant(s) (type E/A/X) :"
             % (function_name, len(failing))]
    for message in failing:
        lines.append("  %s %s/%s : %s" % (
            message.get("type", "?"), message.get("id", ""),
            message.get("number", ""), message.get("message", "")))
    lines.append("Penser à Rollback Bapi Transaction avant de réessayer "
                 "(la LUW reste ouverte côté serveur).")
    return "\n".join(lines)
