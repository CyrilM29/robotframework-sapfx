"""Aplatissement de l'arbre d'objets retourné par ``GuiSession.GetObjectTree``.

L'API SAP GUI Scripting expose ``GetObjectTree(rootId, properties)`` (SAP GUI
récents ; absent des versions anciennes) : **un seul appel COM** retourne tout
le sous-arbre en JSON avec les propriétés demandées, là où la marche COM
classique coûte un aller-retour par nœud : sur un écran riche, c'est l'écart
entre 1 et plusieurs centaines d'appels inter-process. Usage observé chez
RoboSAPiens (imbus, Apache-2.0), qui s'en sert pour ses localisateurs par
libellé ; on en fait ici le chemin rapide de la perception ECC (avec repli
automatique sur la marche COM quand l'API manque).

Le JSON a la forme ``{"properties": {...}, "children": [...]}`` récursive,
parfois coiffée d'un nœud enveloppe sans propriétés. Les valeurs numériques
peuvent arriver en chaînes (c'est le cas observé côté RoboSAPiens, qui active
``AllowReadingFromString``) et ``Changeable`` en ``"true"``/``"false"`` : tout
est normalisé ici. Module pur (json/dataclasses), typé, testé hors SAP.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterator, Optional, Union

# Propriétés demandées à GetObjectTree pour la perception : identité, texte,
# éditabilité et géométrie (ScreenLeft/ScreenTop = coordonnées absolues écran,
# comparables entre nœuds de parents différents ; Left/Top en secours).
OBJECT_TREE_PROPERTIES: tuple[str, ...] = (
    "Id", "Type", "Text", "Tooltip", "Changeable",
    "ScreenLeft", "ScreenTop", "Left", "Top", "Width", "Height",
)


@dataclass(frozen=True)
class ScreenElement:
    """Un contrôle de l'écran, normalisé (id, type, texte, géométrie).

    ``left``/``top`` sont les coordonnées écran absolues quand disponibles
    (``ScreenLeft``/``ScreenTop``), sinon les relatives (``Left``/``Top``) ;
    ``None`` pour un nœud non visuel. C'est la monnaie d'échange entre la
    perception, le healing et le moteur de localisateurs par libellé.
    """
    id: str
    type: str = ""
    text: str = ""
    tooltip: str = ""
    changeable: bool = False
    left: Optional[int] = None
    top: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

    @property
    def right(self) -> Optional[int]:
        if self.left is None or self.width is None:
            return None
        return self.left + self.width

    @property
    def bottom(self) -> Optional[int]:
        if self.top is None or self.height is None:
            return None
        return self.top + self.height


def _get(props: dict, name: str) -> Any:
    """Valeur d'une propriété, insensible à la casse des clés JSON."""
    if name in props:
        return props[name]
    lowered = name.lower()
    for key, value in props.items():
        if isinstance(key, str) and key.lower() == lowered:
            return value
    return None


def _as_int(value: Any) -> Optional[int]:
    """Entier depuis int/float/chaîne numérique ; ``None`` sinon (jamais d'erreur)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(float(text))
        except ValueError:
            return None
    return None


def _as_bool(value: Any) -> bool:
    # "true" COM strict : sémantique distincte du _as_bool RF de
    # SapApiLibrary (_TRUTHY) ; ne pas fusionner.
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _element_from(props: dict) -> Optional[ScreenElement]:
    element_id = _as_text(_get(props, "Id")).strip()
    if not element_id:
        return None
    return ScreenElement(
        id=element_id,
        type=_as_text(_get(props, "Type")).strip(),
        text=_as_text(_get(props, "Text")),
        tooltip=_as_text(_get(props, "Tooltip")),
        changeable=_as_bool(_get(props, "Changeable")),
        left=_as_int(_get(props, "ScreenLeft")) if _get(props, "ScreenLeft") is not None
        else _as_int(_get(props, "Left")),
        top=_as_int(_get(props, "ScreenTop")) if _get(props, "ScreenTop") is not None
        else _as_int(_get(props, "Top")),
        width=_as_int(_get(props, "Width")),
        height=_as_int(_get(props, "Height")),
    )


def _iter_nodes(node: Any) -> Iterator[ScreenElement]:
    """Parcourt récursivement un nœud ``{"properties": ..., "children": [...]}``.

    Tolérant aux variantes : propriétés portées directement par le nœud (pas de
    clé ``properties``), nœud enveloppe sans ``Id`` (simplement traversé),
    entrée non-dict dans ``children`` (ignorée)."""
    if not isinstance(node, dict):
        return
    props = node.get("properties")
    if not isinstance(props, dict):
        props = {k: v for k, v in node.items() if k != "children"}
    element = _element_from(props)
    if element is not None:
        yield element
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            yield from _iter_nodes(child)


def flatten_object_tree(payload: Union[str, dict]) -> list[ScreenElement]:
    """Aplati le JSON de ``GetObjectTree`` en liste de :class:`ScreenElement`
    (parcours en profondeur, ordre du document, le même que la marche COM).

    ``payload`` : la chaîne JSON brute retournée par l'API, ou le dict déjà
    parsé. Lève ``ValueError`` si la chaîne n'est pas du JSON exploitable :
    l'appelant y voit le signal de replier sur la marche COM."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("GetObjectTree did not return parseable JSON: %s" % exc)
    if not isinstance(payload, dict):
        raise ValueError("GetObjectTree returned %s, expected a JSON object"
                         % type(payload).__name__)
    return list(_iter_nodes(payload))
