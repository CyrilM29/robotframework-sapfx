"""Touches virtuelles SAP GUI (VKey), logique pure.

La table des combinaisons et leur numéro d'API (``sendVKey``) viennent de
robotframework-sapguilibrary 1.2.1 (Copyright Frank van der Kuur, Apache
License 2.0, voir NOTICE), absorbée et réécrite pour SAPFX le 2026-10-06 :
résolution d'un numéro ou d'une combinaison en clavier lisible, et l'inverse
pour nommer une touche dans un message.

Un numéro est transmis tel quel, comme dans l'amont : la table ne couvre que
les touches documentées, et une autre version de SAP GUI peut en connaître
d'autres. Seule la combinaison passe par la table, et l'échec d'une
combinaison inconnue propose les plus proches au lieu d'un simple
« invalide ».
"""
from __future__ import annotations

import difflib
from typing import Any

#: Numéro d'API -> combinaison, dans la forme normalisée (majuscules, sans
#: espace, ``CTRL``/``DEL``/``INS``). Les trous de la numérotation SAP (13,
#: 49 à 69, 95, 96) n'ont pas de combinaison.
VKEYS: dict[int, str] = {
    0: "ENTER", 1: "F1", 2: "F2", 3: "F3", 4: "F4", 5: "F5", 6: "F6", 7: "F7",
    8: "F8", 9: "F9", 10: "F10", 11: "F11", 12: "F12",
    14: "SHIFT+F2", 15: "SHIFT+F3", 16: "SHIFT+F4", 17: "SHIFT+F5",
    18: "SHIFT+F6", 19: "SHIFT+F7", 20: "SHIFT+F8", 21: "SHIFT+F9",
    22: "CTRL+SHIFT+0", 23: "SHIFT+F11", 24: "SHIFT+F12",
    25: "CTRL+F1", 26: "CTRL+F2", 27: "CTRL+F3", 28: "CTRL+F4", 29: "CTRL+F5",
    30: "CTRL+F6", 31: "CTRL+F7", 32: "CTRL+F8", 33: "CTRL+F9", 34: "CTRL+F10",
    35: "CTRL+F11", 36: "CTRL+F12",
    37: "CTRL+SHIFT+F1", 38: "CTRL+SHIFT+F2", 39: "CTRL+SHIFT+F3",
    40: "CTRL+SHIFT+F4", 41: "CTRL+SHIFT+F5", 42: "CTRL+SHIFT+F6",
    43: "CTRL+SHIFT+F7", 44: "CTRL+SHIFT+F8", 45: "CTRL+SHIFT+F9",
    46: "CTRL+SHIFT+F10", 47: "CTRL+SHIFT+F11", 48: "CTRL+SHIFT+F12",
    70: "CTRL+E", 71: "CTRL+F", 72: "CTRL+A", 73: "CTRL+D", 74: "CTRL+N",
    75: "CTRL+O", 76: "SHIFT+DEL", 77: "CTRL+INS", 78: "SHIFT+INS",
    79: "ALT+BACKSPACE", 80: "CTRL+PAGEUP", 81: "PAGEUP", 82: "PAGEDOWN",
    83: "CTRL+PAGEDOWN", 84: "CTRL+G", 85: "CTRL+R", 86: "CTRL+P", 87: "CTRL+B",
    88: "CTRL+K", 89: "CTRL+T", 90: "CTRL+Y", 91: "CTRL+X", 92: "CTRL+C",
    93: "CTRL+V", 94: "SHIFT+F10", 97: "CTRL+#",
}

#: Synonymes acceptés en plus de la table : la seconde touche d'une même
#: fonction SAP (F11 sauvegarde aussi par Ctrl+S, F12 annule aussi par Échap).
ALIASES: dict[str, int] = {"CTRL+S": 11, "ESC": 12, "ESCAPE": 12}

_BY_NAME = {name: number for number, name in VKEYS.items()}


def normalize_combination(text: Any) -> str:
    """``"Ctrl + Shift + F1"`` -> ``"CTRL+SHIFT+F1"`` : majuscules, espaces
    retirés, ``CONTROL``/``DELETE``/``INSERT`` ramenés à leur abréviation."""
    combination = str(text).upper().replace(" ", "")
    for long_name, short in (("CONTROL", "CTRL"), ("DELETE", "DEL"), ("INSERT", "INS")):
        combination = combination.replace(long_name, short)
    return combination


def resolve_vkey(value: Any) -> int:
    """Le numéro d'API d'une touche donnée par son numéro (``8``, ``"8"``,
    transmis tel quel) ou sa combinaison (``"F8"``, ``"Ctrl + Shift + F1"``,
    ``"Esc"``). Une combinaison inconnue lève ``ValueError`` en nommant les
    touches les plus proches."""
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    combination = normalize_combination(text)
    if combination in _BY_NAME:
        return _BY_NAME[combination]
    if combination in ALIASES:
        return ALIASES[combination]
    close = difflib.get_close_matches(combination, list(_BY_NAME) + list(ALIASES), n=3)
    hint = " ; voulait-on dire %s ?" % ", ".join(close) if close else ""
    raise ValueError(
        "Combinaison de touches %r inconnue : donner un numéro de VKey (0 à 97) ou "
        "une combinaison comme F8, Ctrl+S, Shift+F3%s" % (str(value), hint))


def vkey_name(number: int) -> str:
    """La combinaison d'un numéro de VKey, pour un message (``8`` -> ``F8``) ;
    chaîne vide si le numéro n'est pas dans la table."""
    return VKEYS.get(int(number), "")
