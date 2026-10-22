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
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence, Union

from sapfx_common import __version__ as _package_version
from robot.api.deco import keyword

#: Version de ce module quand Robot l'importe comme bibliothèque (Libdoc, journal) :
#: celle du paquet, jamais une seconde valeur à aligner à chaque release.
ROBOT_LIBRARY_VERSION = _package_version

#: Seules les fonctions décorées par ``@keyword`` deviennent des keywords :
#: Robot lit aussi ``__all__``, mais le chargeur de rf-mcp ne lit que ce
#: drapeau, et sans lui y publiait les fonctions importées d'ailleurs.
ROBOT_AUTO_KEYWORDS = False

#: Les keywords que ``Library    sapfx_common.robot_args`` expose. Sans
#: ``__all__``, Robot fait un keyword de toute fonction publique du module ET de
#: toute fonction qu'il importe ; les types (``NameList``…) restent importables
#: depuis Python.
__all__ = ["displayed_count"]


def as_name_list(value: Any, argument: str = "columns") -> list[str]:
    """Liste de NOMS depuis ce que la frontière Robot/MCP peut livrer : une
    liste ou un tuple (normalisés), une chaîne à virgules (``"A,B,C"`` :
    découpage sans ambiguïté, un identifiant technique SAP ne contient pas de
    virgule), ou une chaîne liste-littérale (``"['A', 'B']"``, la forme
    qu'émet un agent qui sérialise sa liste Python). Entrées dépouillées,
    vides ignorées, ``None`` -> ``[]``.

    Un *mapping* rend ses CLÉS, dans l'ordre : c'est la forme que produit
    `Get Grid Column Titles` (``{id technique: titre affiché}``), et la passer
    telle quelle est le geste naturel de l'appelant. Sans ce cas, le dict
    partait en ``str()`` puis en découpage par virgules, et les fragments
    obtenus faisaient échouer l'appel sur un message qui n'aurait désigné ni la
    cause ni le remède.

    Exemple :
    | ${columns}=    `As Name List`    CARRID,CARRNAME
    | Should Be Equal    ${columns}    ${{ ['CARRID', 'CARRNAME'] }}
    """
    if value is None:
        return []
    items: Any
    if isinstance(value, Mapping):
        items = list(value.keys())
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        text = str(value).strip()
        if _looks_like_list_literal(text):
            items = _literal_items(text, argument)
        else:
            items = text.split(",")
    return [str(item).strip() for item in items if str(item).strip()]


class NameList(list[str]):
    """Liste de noms : une liste Robot (``@{names}``), une chaîne à virgules
    (``CARRID,CARRNAME``), une liste littérale (``['CARRID', 'CARRNAME']``,
    la forme qu'envoie un agent par MCP) ou un dictionnaire, dont les CLÉS
    sont prises dans l'ordre (la carte que rend ``Get Grid Column Titles``).
    Les noms sont dépouillés et les entrées vides ignorées ; la casse est
    gardée, le keyword décide (un nom ABAP est mis en majuscules par le
    keyword qui le lit).
    """

    # Le convertisseur que Robot Framework appelle (ROBOT_LIBRARY_CONVERTERS),
    # sans docstring : Libdoc publierait la sienne à la place du contrat
    # ci-dessus. `list[str]` ne convient pas : Robot y refuse « A,B », que les
    # appels par MCP envoient. Une NameList EST une liste, donc le corps du
    # keyword, qui normalise encore par as_name_list (un appel Python direct
    # ne passe pas par la conversion), la reçoit telle quelle.
    @classmethod
    def from_value(cls, value: str | int | list | tuple | dict | None) -> NameList | None:
        # None reste None : un argument facultatif s'annote NameList (et non
        # « NameList | None »), parce que Robot ne rend, pour une union, que
        # « cannot be converted to NameList or None », sans le message précis
        # du convertisseur, celui qu'un agent lit pour se corriger.
        return None if value is None else cls(as_name_list(value, ""))


# L'annotation des keywords : à l'exécution c'est NameList (Robot convertit,
# Libdoc publie NameList) ; pour mypy, tout ce que le corps du keyword accepte,
# parce qu'un keyword appelé en Python par un autre (``self.read_rfc_table(t,
# ["A", "B"])``) ne passe pas par la conversion.
if TYPE_CHECKING:
    NameListInput = Union[NameList, Sequence[str], str, Mapping[str, Any]]
    OptionalNameListInput = Optional[NameListInput]
else:
    NameListInput = NameList
    OptionalNameListInput = NameList


def as_optional_int(value: Any, argument: str, hint: str = "") -> int | None:
    """Entier optionnel dont l'échec de conversion NOMME l'argument (et joint
    ``hint``, le remède propre à l'appelant). ``None`` et la chaîne vide
    rendent ``None`` (argument non fourni). Un booléen est refusé : c'est un
    ``int`` pour Python, jamais un plafond voulu.

    Exemple :
    | ${limit}=    `As Optional Int`    50    max_rows
    | Should Be Equal As Integers    ${limit}    50
    """
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


@keyword
def displayed_count(value: Any) -> int:
    """Compteur AFFICHÉ par SAP -> entier : seuls les chiffres sont gardés.

    Un compte rendu à l'écran (popup « Number of Entries » de SE16, popup
    WebGUI) porte des séparateurs de milliers dépendants de la locale et
    parfois du texte autour : le filtre par chiffres est locale-indépendant
    par construction, sans regex (un ``\\D`` traverse mal l'échappement
    Robot, leçon 2026-07-10). Deux copies vivaient dans la couche resources
    (ECC et WebGUI) : promues ici, une seule vérité (convention #12).
    ``None`` et une chaîne sans chiffre rendent ``0``.

    Exemple :
    | ${count}=    `Displayed Count`    1.639
    | Should Be Equal As Integers    ${count}    1639
    """
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return int(digits) if digits else 0


def _looks_like_list_literal(text: str) -> bool:
    return (text.startswith("[") and text.endswith("]")) or (
        text.startswith("(") and text.endswith(")"))


def _literal_items(text: str, argument: str) -> list[Any]:
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        subject = "L'argument %s" % argument if argument else "La valeur"
        raise ValueError(
            "%s ressemble à une liste-littérale mais ne se parse "
            "pas : %r. Passer une liste, ou une chaîne de noms séparés par "
            "des virgules." % (subject, text)) from None
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
