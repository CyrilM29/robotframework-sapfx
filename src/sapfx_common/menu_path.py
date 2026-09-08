"""Barre de menus SAP GUI : résolution d'un chemin, logique pure.

Un menu SAP GUI est un ``GuiMenu`` dont l'id porte sa POSITION
(``wnd[0]/mbar/menu[4]/menu[11]``) et dont le texte est LOCALISÉ (« System »
en EN, « Système » en FR). Aucune des deux ancres n'est parfaite : la position
varie par transaction (le menu System est en règle générale l'avant-dernier,
mais pas toujours) et le texte varie par langue de session. Ce module résout
un chemin dans les deux grammaires, niveau par niveau :

* ``System > Status`` : chemin de TEXTES, comparés par préfixe insensible à
  la casse et aux points de suspension (« Status... » matche « Status ») ;
* ``4 > 11`` : chemin de POSITIONS (entiers, 0-based comme dans l'id).

Les deux se mélangent (``System > 11``). L'ambiguïté d'un niveau est rendue
avec ses candidats, jamais tranchée. Un chemin de textes est un choix de
LISIBILITÉ que la convention 3 tolère dans un page object (jamais dans une
assertion) : le keyword le dit dans sa documentation. Typé, testé hors SAP.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

PATH_SEPARATOR = ">"
_MENU_SEGMENT = re.compile(r"/menu\[(\d+)\]")


@dataclass(frozen=True)
class MenuItem:
    """Une entrée de menu perçue : id complet, texte, positions (les indices
    ``menu[N]`` de l'id, du haut vers le bas)."""
    id: str
    text: str
    positions: tuple[int, ...]

    @property
    def depth(self) -> int:
        return len(self.positions)


def menu_items_from_elements(elements: Iterable, window: str = "wnd[0]") -> list[MenuItem]:
    """Extrait les entrées de menu d'une perception (``ScreenElement`` ou tout
    objet portant ``id``/``type``/``text``) sous la barre de ``window``."""
    prefix = "%s/mbar" % window
    items: list[MenuItem] = []
    for element in elements:
        if getattr(element, "type", "") != "GuiMenu":
            continue
        element_id = str(getattr(element, "id", "") or "")
        if not element_id.startswith(prefix + "/"):
            continue
        positions = tuple(int(n) for n in _MENU_SEGMENT.findall(element_id))
        if not positions:
            continue
        items.append(MenuItem(element_id, str(getattr(element, "text", "") or "").strip(),
                              positions))
    return items


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("...", "").replace("…", "").split()).casefold()


def _segment_matches(item: MenuItem, segment: str) -> bool:
    if segment.isdigit():
        return item.positions[-1] == int(segment)
    wanted = _normalize_text(segment)
    return bool(wanted) and _normalize_text(item.text).startswith(wanted)


def split_path(path: str, separator: str = PATH_SEPARATOR) -> list[str]:
    return [part.strip() for part in str(path or "").split(separator) if part.strip()]


def resolve_menu_path(items: Sequence[MenuItem], path: str) -> MenuItem:
    """L'entrée de menu désignée par ``path``, niveau par niveau. Lève une
    ``ValueError`` actionnable : chemin vide, niveau sans correspondance (les
    entrées de ce niveau listées), niveau ambigu (les candidats listés)."""
    segments = split_path(path)
    if not segments:
        raise ValueError("Chemin de menu vide : attendu 'Menu > Sous-menu' ou '4 > 11'.")
    parent: tuple[int, ...] = ()
    chosen: MenuItem | None = None
    for depth, segment in enumerate(segments, start=1):
        level = [item for item in items
                 if item.depth == depth and item.positions[:-1] == parent]
        matches = [item for item in level if _segment_matches(item, segment)]
        if len(matches) == 1:
            chosen = matches[0]
            parent = chosen.positions
            continue
        available = ", ".join("%d=%s" % (item.positions[-1], item.text or "(vide)")
                              for item in level) or "(aucune entrée à ce niveau)"
        if not matches:
            raise ValueError(
                "Chemin de menu %r : aucune entrée %r au niveau %d. Entrées "
                "disponibles : %s" % (path, segment, depth, available))
        raise ValueError(
            "Chemin de menu %r : %r est ambigu au niveau %d (%s) : préciser le "
            "texte ou utiliser la position."
            % (path, segment, depth,
               ", ".join("%d=%s" % (m.positions[-1], m.text) for m in matches)))
    assert chosen is not None
    return chosen


DIALOG_SUFFIXES = ("...", "…")


def dialog_entry_before_last(items: Sequence[MenuItem]) -> tuple[MenuItem | None, str]:
    """L'AVANT-DERNIÈRE entrée d'un menu, à condition qu'elle ouvre un dialogue
    (points de suspension, une convention d'interface que SAP ne localise pas).

    C'est l'ancre de « System > Status » qui tient sur deux releases, là où un
    indice gravé ne tenait que sur une : 754 = 13 entrées, « Status... » en 11 ;
    758 = 12 entrées (l'entrée « List » a disparu), « Status... » en 10 ; « Log
    Off » ferme la liste des deux côtés (mesuré le 2026-09-08). Rendre
    ``(None, raison)`` plutôt que de laisser cliquer une entrée qui n'ouvre
    pas de dialogue : l'indice 11 gravé cliquait « Log Off » sur la 758.
    """
    ordered = sorted(items, key=lambda item: item.positions[-1])
    if len(ordered) < 2:
        return None, "moins de deux entrées perçues (%d)" % len(ordered)
    candidate = ordered[-2]
    text = candidate.text.rstrip()
    if not text.endswith(DIALOG_SUFFIXES):
        return None, ("l'avant-dernière entrée %r n'ouvre pas un dialogue (aucun "
                      "point de suspension) : refus de la cliquer" % candidate.text)
    return candidate, ""


def describe_menu(items: Sequence[MenuItem]) -> list[dict]:
    """Liste JSON-safe ``{id, text, positions, path}`` des entrées, ordre de
    perception ; ``path`` = les positions jointes par ``>`` (rejouable telle
    quelle par ``resolve_menu_path``)."""
    return [{"id": item.id, "text": item.text, "positions": list(item.positions),
             "path": " > ".join(str(p) for p in item.positions)}
            for item in items]
