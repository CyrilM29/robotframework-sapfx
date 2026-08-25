"""Modele et blocs geometriques des localisateurs humains (prive).

Le socle de ``sapfx_common.semantic`` : la dataclass :class:`SemanticMatch`,
les predicats de texte et de libelle, et les blocs geometriques de la
grammaire (ancrage droite/dessous, grilles par position, voisinage de
l'operateur ``>>``). L'API publique (``resolve_semantic``, ``scope_hint``,
``describe_element``, ``nearby_labels``, perception semantique) vit dans
``semantic.py``, qui re-exporte ce dont ses consommateurs ont besoin :
importer ``sapfx_common.semantic`` reste la seule porte d'entree.

Extrait de ``semantic.py`` (convention #13). Module pur, type, teste hors SAP
a travers l'API publique.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .object_tree import ScreenElement

# alignement 5, voisinage horizontal ~20-30, vertical ~25).
ALIGN_TOLERANCE = 5
MAX_HORIZONTAL_GAP = 30
MAX_VERTICAL_GAP = 25

# Rayon (px) du voisinage exploré par l'opérateur `>>` autour de son ancre :
# plus généreux que les tolérances d'ancrage direct ci-dessus car le repère
# est ici la région visuelle autour du libellé, pas son voisin immédiat.
SCOPE_RADIUS = 100

# Séparateur de l'opérateur de portée « ancre >> reste » (espaces obligatoires,
# même convention que le séparateur `` @ `` de l'intersection).
_SCOPE_SEPARATOR = " >> "

# Un « libellé » d'écran SAP : un GuiLabel, ou un champ texte non modifiable
# (les dynpros affichent souvent les libellés comme champs en lecture seule).
_LABEL_FIELD_TYPES = ("GuiTextField", "GuiCTextField")

# Types purement structurels : jamais la cible d'un localisateur humain.
_STRUCTURAL_TYPES = frozenset({
    "GuiMainWindow", "GuiModalWindow", "GuiUserArea", "GuiSimpleContainer",
    "GuiScrollContainer", "GuiSplitterContainer", "GuiContainerShell",
    "GuiToolbar", "GuiTabStrip", "GuiMenubar", "GuiTitlebar", "GuiStatusbar",
})


@dataclass(frozen=True)
class SemanticMatch:
    """Un match du résolveur : l'élément, la voie qui l'a trouvé
    (``right-of-label`` / ``below-label`` / ``right-of-label-grid`` /
    ``below-label-grid`` / ``intersection`` / ``text`` / ``tooltip`` /
    ``content``), l'ancre éventuelle et la distance en pixels."""
    element: ScreenElement
    via: str
    anchor: Optional[ScreenElement] = None
    distance: int = 0


def text_matches(actual: Optional[str], wanted: Optional[str],
                 exact: bool = False) -> bool:
    """Comparaison de textes d'écran : espaces normalisés, casse ignorée ;
    ``exact=False`` accepte ``wanted`` comme préfixe de ``actual``."""
    actual_n = (actual or "").strip().casefold()
    wanted_n = (wanted or "").strip().casefold()
    if not wanted_n:
        return False
    if exact:
        return actual_n == wanted_n
    return actual_n.startswith(wanted_n)


def is_label(element: ScreenElement) -> bool:
    """Vrai si l'élément peut servir de libellé-ancre (GuiLabel, ou champ texte
    non modifiable : la façon dont les dynpros affichent du texte statique)."""
    if element.type == "GuiLabel":
        return True
    return element.type in _LABEL_FIELD_TYPES and not element.changeable


def _is_default_target(element: ScreenElement) -> bool:
    return element.type not in _STRUCTURAL_TYPES and not is_label(element)


def _target_filter(elements: Iterable[ScreenElement],
                   types: Optional[Sequence[str]],
                   changeable_only: bool = False) -> list[ScreenElement]:
    """``changeable_only`` : ne garde que les cibles **modifiables**, requis par
    la saisie (un champ non modifiable ne peut pas la recevoir : c'est le
    séparateur « to » des selection screens, un champ affiché en lecture seule…).
    Sans lui, un filtre de types explicite ré-admettrait ces champs-libellés dans
    les positions de grille (``libellé @ N``) : constaté live sur SE16/T000."""
    if types is not None:
        allowed = set(types)
        candidates = [el for el in elements if el.type in allowed]
    else:
        candidates = [el for el in elements if _is_default_target(el)]
    if changeable_only:
        candidates = [el for el in candidates if el.changeable]
    return candidates


def _right_of_gap(anchor: ScreenElement, element: ScreenElement,
                  align_tolerance: int, max_gap: int) -> Optional[int]:
    """Distance si ``element`` est le voisin de droite de ``anchor`` (même
    ligne, à droite, écart borné), ``None`` sinon."""
    if (element.left is None or element.top is None
            or anchor.left is None or anchor.right is None or anchor.top is None):
        return None
    if element.left <= anchor.left:
        return None
    if abs(element.top - anchor.top) > align_tolerance:
        return None
    gap = abs(element.left - anchor.right)
    if gap > max_gap:
        return None
    return gap


def _below_gap(anchor: ScreenElement, element: ScreenElement,
               align_tolerance: int, max_gap: int) -> Optional[int]:
    """Distance si ``element`` est sous ``anchor`` (aligné à gauche ou centré,
    écart vertical borné), ``None`` sinon."""
    if (element.left is None or element.top is None
            or anchor.left is None or anchor.top is None):
        return None
    if element.top <= anchor.top:
        return None
    left_aligned = abs(element.left - anchor.left) <= align_tolerance
    center_aligned = False
    if (not left_aligned and element.width is not None
            and anchor.width is not None):
        center_aligned = abs((element.left + element.width // 2)
                             - (anchor.left + anchor.width // 2)) <= align_tolerance
    if not (left_aligned or center_aligned):
        return None
    base = anchor.bottom if anchor.bottom is not None else anchor.top
    gap = element.top - base
    if gap < -align_tolerance or gap > max_gap:
        return None
    return max(gap, 0)


def _dedupe_sorted(matches: Iterable[SemanticMatch]) -> list[SemanticMatch]:
    """Un match par élément (la plus petite distance gagne), tri déterministe
    par (distance, id)."""
    best: dict[str, SemanticMatch] = {}
    for match in matches:
        current = best.get(match.element.id)
        if current is None or match.distance < current.distance:
            best[match.element.id] = match
    return sorted(best.values(), key=lambda m: (m.distance, m.element.id))


def _anchored(elements: Sequence[ScreenElement], label: str, direction: str,
              types: Optional[Sequence[str]], exact: bool,
              align_tolerance: int, max_gap: int,
              changeable_only: bool = False) -> list[SemanticMatch]:
    anchors = [el for el in elements if is_label(el) and text_matches(el.text, label, exact)]
    targets = _target_filter(elements, types, changeable_only)
    gap_of = _right_of_gap if direction == "right-of-label" else _below_gap
    matches = []
    for anchor in anchors:
        candidates = []
        for element in targets:
            if element.id == anchor.id:
                continue
            gap = gap_of(anchor, element, align_tolerance, max_gap)
            if gap is not None:
                candidates.append(SemanticMatch(element, direction, anchor, gap))
        if candidates:
            # une ancre ne désigne que SON plus proche voisin : les champs
            # suivants de la même ligne/colonne appartiennent à d'autres libellés.
            matches.append(min(candidates, key=lambda m: (m.distance, m.element.id)))
    return _dedupe_sorted(matches)


def _as_position(text: str) -> Optional[int]:
    """``text`` est-il un entier positif (une position 1-based) ? ``None`` sinon.
    Utilisé pour distinguer ``N @ libellé`` / ``libellé @ N`` de l'intersection
    ``gauche @ haut`` ordinaire."""
    text = text.strip()
    if text.isdigit():
        value = int(text)
        return value if value > 0 else None
    return None


def _grid_column(elements: Sequence[ScreenElement], label: str, position: int,
                 types: Optional[Sequence[str]], exact: bool,
                 align_tolerance: int,
                 changeable_only: bool = False) -> list[SemanticMatch]:
    """``N @ libellé`` : le N-ième champ (1-based) de la grille **verticale**
    alignée sous ``libellé``, du plus proche au plus lointain. Sans plafond de
    distance (au-delà de l'alignement) : une grille peut s'étendre sur plusieurs
    lignes, contrairement au voisin unique de ``@ libellé``."""
    anchors = [el for el in elements if is_label(el) and text_matches(el.text, label, exact)]
    targets = _target_filter(elements, types, changeable_only)
    matches = []
    for anchor in anchors:
        if anchor.left is None or anchor.top is None:
            continue
        column = []
        for element in targets:
            if element.id == anchor.id or element.left is None or element.top is None:
                continue
            if element.top <= anchor.top:
                continue
            left_aligned = abs(element.left - anchor.left) <= align_tolerance
            center_aligned = False
            if (not left_aligned and element.width is not None
                    and anchor.width is not None):
                center_aligned = abs((element.left + element.width // 2)
                                     - (anchor.left + anchor.width // 2)) <= align_tolerance
            if left_aligned or center_aligned:
                column.append(element)
        column.sort(key=lambda el: (el.top, el.id))
        if 0 < position <= len(column):
            chosen = column[position - 1]
            assert chosen.top is not None   # garanti par le filtre ci-dessus
            base = anchor.bottom if anchor.bottom is not None else anchor.top
            matches.append(SemanticMatch(chosen, "below-label-grid", anchor,
                                         max(chosen.top - base, 0)))
    return _dedupe_sorted(matches)


def _grid_row(elements: Sequence[ScreenElement], label: str, position: int,
             types: Optional[Sequence[str]], exact: bool,
             align_tolerance: int,
             changeable_only: bool = False) -> list[SemanticMatch]:
    """``libellé @ N`` : le N-ième champ (1-based) de la grille **horizontale**
    alignée à droite de ``libellé``, du plus proche au plus lointain."""
    anchors = [el for el in elements if is_label(el) and text_matches(el.text, label, exact)]
    targets = _target_filter(elements, types, changeable_only)
    matches = []
    for anchor in anchors:
        if anchor.left is None or anchor.top is None or anchor.right is None:
            continue
        row = []
        for element in targets:
            if element.id == anchor.id or element.left is None or element.top is None:
                continue
            if element.left <= anchor.left:
                continue
            if abs(element.top - anchor.top) > align_tolerance:
                continue
            row.append(element)
        row.sort(key=lambda el: (el.left, el.id))
        if 0 < position <= len(row):
            chosen = row[position - 1]
            assert chosen.left is not None   # garanti par le filtre ci-dessus
            matches.append(SemanticMatch(chosen, "right-of-label-grid", anchor,
                                         max(chosen.left - anchor.right, 0)))
    return _dedupe_sorted(matches)


def _scope_to_anchor(elements: Sequence[ScreenElement], anchor_text: str,
                     exact: bool, radius: int = SCOPE_RADIUS
                     ) -> Optional[list[ScreenElement]]:
    """Réduit ``elements`` au voisinage (bounding box étendue de ``radius`` px
    dans les 4 directions) du libellé nommé ``anchor_text`` : la portée de
    l'opérateur ``>>``. ``None`` si ``anchor_text`` ne désigne pas EXACTEMENT un
    libellé (absent ou ambigu) : un ``>>`` sur une ancre douteuse ne devine
    jamais, il ne produit aucun match (cohérent avec la politique du module)."""
    anchors = [el for el in elements if is_label(el) and text_matches(el.text, anchor_text, exact)]
    if len(anchors) != 1:
        return None
    anchor = anchors[0]
    if anchor.left is None or anchor.top is None:
        return None
    zone_left = anchor.left - radius
    zone_right = (anchor.right if anchor.right is not None else anchor.left) + radius
    zone_top = anchor.top - radius
    zone_bottom = (anchor.bottom if anchor.bottom is not None else anchor.top) + radius
    neighborhood = []
    for element in elements:
        if element.id == anchor.id or element.left is None or element.top is None:
            continue
        element_right = element.right if element.right is not None else element.left
        element_bottom = element.bottom if element.bottom is not None else element.top
        if element.left > zone_right or element_right < zone_left:
            continue
        if element.top > zone_bottom or element_bottom < zone_top:
            continue
        neighborhood.append(element)
    return neighborhood


def _by_own_text(elements: Sequence[ScreenElement], wanted: str, attr: str,
                 types: Optional[Sequence[str]], exact: bool,
                 changeable_only: bool = False) -> list[SemanticMatch]:
    via = "text" if attr == "text" else "tooltip"
    return _dedupe_sorted(
        SemanticMatch(el, via)
        for el in _target_filter(elements, types, changeable_only)
        if text_matches(getattr(el, attr), wanted, exact))


