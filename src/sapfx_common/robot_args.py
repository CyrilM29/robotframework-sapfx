"""Normalisation des arguments qui franchissent la frontière Robot/MCP.

Via ``execute_step`` (rf-mcp), TOUT argument arrive en chaîne : une liste de
colonnes devient ``"A,B,C"`` ou la liste-littérale ``"['A', 'B']"``, et une
liste passée en POSITION d'un argument entier sort en
``TypeError: int() argument must be ... not 'list'`` nu, sans nommer
l'argument fautif. Trois incidents d'agents vécus le 2026-08-27 (relecture
CabrIA) partagent cette racine : le keyword était correct à chaque fois,
c'est la frontière qui laissait l'ambiguïté s'installer, et un agent ne lit
que le message. Ce module la ferme : logique pure, aucune dépendance.

À ne pas confondre avec ``rfc_tables.as_field_list`` (qui capitalise pour le
dictionnaire ABAP) : ici la casse est préservée, l'appelant décide.
"""
from __future__ import annotations

import ast
from typing import Any


def as_name_list(value: Any, argument: str = "columns") -> list[str]:
    """Liste de NOMS depuis ce que la frontière Robot/MCP peut livrer : une
    liste ou un tuple (normalisés), une chaîne à virgules (``"A,B,C"`` :
    découpage sans ambiguïté, un identifiant technique SAP ne contient pas de
    virgule), ou une chaîne liste-littérale (``"['A', 'B']"``, la forme
    qu'émet un agent qui sérialise sa liste Python). Entrées dépouillées,
    vides ignorées, ``None`` -> ``[]``."""
    if value is None:
        return []
    items: Any
    if isinstance(value, (list, tuple)):
        items = value
    else:
        text = str(value).strip()
        if _looks_like_list_literal(text):
            items = _literal_items(text, argument)
        else:
            items = text.split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def as_optional_int(value: Any, argument: str, hint: str = "") -> int | None:
    """Entier optionnel dont l'échec de conversion NOMME l'argument (et joint
    ``hint``, le remède propre à l'appelant). ``None`` et la chaîne vide
    rendent ``None`` (argument non fourni). Un booléen est refusé : c'est un
    ``int`` pour Python, jamais un plafond voulu."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(_int_error(argument, value, hint))
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            raise ValueError(_int_error(argument, value, hint)) from None
    raise ValueError(_int_error(argument, value, hint))


def displayed_count(value: Any) -> int:
    """Compteur AFFICHÉ par SAP -> entier : seuls les chiffres sont gardés.

    Un compte rendu à l'écran (popup « Number of Entries » de SE16, popup
    WebGUI) porte des séparateurs de milliers dépendants de la locale et
    parfois du texte autour : le filtre par chiffres est locale-indépendant
    par construction, sans regex (un ``\\D`` traverse mal l'échappement
    Robot, leçon 2026-07-10). Deux copies vivaient dans la couche resources
    (ECC et WebGUI) : promues ici, une seule vérité (convention #12).
    ``None`` et une chaîne sans chiffre rendent ``0``."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return int(digits) if digits else 0


def _looks_like_list_literal(text: str) -> bool:
    return (text.startswith("[") and text.endswith("]")) or (
        text.startswith("(") and text.endswith(")"))


def _literal_items(text: str, argument: str) -> list[Any]:
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        raise ValueError(
            "L'argument %s ressemble à une liste-littérale mais ne se parse "
            "pas : %r. Passer une liste, ou une chaîne de noms séparés par "
            "des virgules." % (argument, text)) from None
    if isinstance(parsed, (list, tuple)):
        return list(parsed)
    return [parsed]


def _int_error(argument: str, value: Any, hint: str) -> str:
    message = ("L'argument %s doit être un entier, reçu %s (%r)."
               % (argument, type(value).__name__, value))
    if isinstance(value, (list, tuple)):
        message += (" Une liste ici trahit un décalage d'arguments "
                    "POSITIONNELS.")
    if hint:
        message += " " + hint
    return message
