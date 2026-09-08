"""Combo box SAP GUI (``GuiComboBox``) : logique pure des entrées.

Une combo expose ses entrées en couples ``(Key, Value)`` : la CLÉ est la
donnée technique (``A`` pour « Dialog » dans SU01, ``1`` pour ``DD.MM.YYYY``),
la valeur le libellé LOCALISÉ. Le keyword hérité ne sélectionne que par
libellé, ce qui lie une suite à la langue de session (convention 3) ; la
sélection par clé est la voie locale-safe. Ce module normalise la liste, y
retrouve une entrée par clé ou par libellé (préfixe insensible à la casse,
ambiguïté rendue) et formate les messages. Typé, testé hors SAP.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence


def entries_as_dicts(entries: Iterable) -> list[dict]:
    """``[(key, value), ...]`` (ou objets COM ``Key``/``Value``) -> liste de
    ``{"key": ..., "value": ...}`` JSON-safe, blancs de bordure de la VALEUR
    retirés (SAP la complète à droite), clé conservée TELLE QUELLE. Relevé
    live (SM37 « Or after event », SU01 « Decimal Notation », 2026-09-07) :
    une combo peut porter deux clés distinctes ``""`` et ``" "``, et poser
    ``""`` là où SAP attend ``" "`` sort en ``com_error`` « invalid
    argument » : la clé ne se normalise jamais à l'écriture."""
    normalized: list[dict] = []
    for entry in entries:
        if isinstance(entry, (tuple, list)) and len(entry) >= 2:
            key, value = entry[0], entry[1]
        else:
            key, value = getattr(entry, "Key", ""), getattr(entry, "Value", "")
        normalized.append({"key": str(key if key is not None else ""),
                           "value": str(value if value is not None else "").strip()})
    return normalized


def find_by_key(entries: Sequence[dict], key: object) -> Optional[dict]:
    """L'entrée de clé ``key`` : égalité STRICTE d'abord (``" "`` est une clé
    à part entière), puis, faute de mieux, égalité des clés débarrassées de
    leurs blancs de bordure quand elle est unique (``"A "`` pour ``"A"``)."""
    wanted = str(key if key is not None else "")
    for entry in entries:
        if entry["key"] == wanted:
            return entry
    loose = [entry for entry in entries if entry["key"].strip() == wanted.strip()]
    return loose[0] if len(loose) == 1 else None


def find_by_label(entries: Sequence[dict], label: object,
                  exact: bool = False) -> list[dict]:
    """Toutes les entrées dont la valeur correspond (préfixe insensible à la
    casse, ou égalité stricte avec ``exact=True``). Une valeur vide ne matche
    que ``exact=True`` avec un libellé vide."""
    wanted = " ".join(str(label if label is not None else "").split()).casefold()
    matches = []
    for entry in entries:
        actual = " ".join(entry["value"].split()).casefold()
        if exact:
            if actual == wanted:
                matches.append(entry)
        elif wanted and actual.startswith(wanted):
            matches.append(entry)
    return matches


def format_entries(entries: Sequence[dict], limit: int = 20) -> str:
    lines = ["  - %r : %s" % (entry["key"], entry["value"] or "(vide)")
             for entry in list(entries)[:limit]]
    if len(entries) > limit:
        lines.append("  ... (%d entrées en tout)" % len(entries))
    return "\n".join(lines)
