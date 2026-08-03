"""Localisateurs « humains » SAP GUI : résolution par libellé visible et géométrie.

Idée portée de RoboSAPiens (imbus, Apache-2.0 — attribution dans NOTICE) : cibler
un contrôle comme un humain le décrit — « le champ à droite du libellé Table »,
« le bouton Exécuter » — au lieu d'un id technique ``wnd[0]/usr/ctxt...``. Un
libellé survit aux renumérotations de sous-écrans qui cassent les ids ; c'est à
la fois un langage de test lisible ET une ancre de réparation pour le healing.

Deux différences délibérées avec RoboSAPiens :

* **l'ambiguïté est détectée, jamais tranchée en silence** (eux retournent le
  premier match, faiblesse assumée dans leur TODO) : le résolveur retourne TOUS
  les matches de l'étape gagnante, l'appelant échoue avec la liste si besoin ;
* **les tolérances géométriques sont paramétrables** (chez eux codées en dur),
  car sensibles au thème/zoom/DPI — les défauts reprennent leurs valeurs
  éprouvées.

Grammaire de ``resolve_semantic`` (étendue au-delà du sous-ensemble initial —
toujours réimplémentée sur notre modèle de perception, jamais portée verbatim) :

* ``libellé``        : cascade — élément ancré au libellé (à droite **ou** en
  dessous, en une seule étape : deux directions qui désignent des éléments
  différents sont une ambiguïté à remonter, pas une préférence à trancher),
  sinon élément dont le texte propre correspond (boutons/onglets), sinon tooltip ;
* ``@ libellé``      : uniquement l'élément SOUS le libellé ;
* ``gauche @ haut``  : intersection — à droite de ``gauche`` ET sous ``haut``
  (grilles de champs, séparateur `` @ `` entouré d'espaces) ;
* ``= contenu``      : élément par son texte propre exact ;
* ``N @ libellé``    : le N-ième champ (1-based) de la **grille verticale**
  alignée sous ``libellé`` (``N`` entier positif), trié par proximité —
  ``position (1,2,..) @ label`` chez RoboSAPiens ;
* ``libellé @ N``    : le N-ième champ (1-based) de la **grille horizontale**
  alignée à droite de ``libellé`` — leur ``label @ position (1,2,..)`` ;
* ``ancre >> reste``  : réduit d'abord l'univers de résolution au **voisinage**
  du libellé ``ancre`` (doit être unique sur tout l'écran, sinon aucun match),
  puis résout ``reste`` récursivement dans ce seul voisinage — avec n'importe
  quelle forme ci-dessus, y compris un nouveau ``>>``. Couvre leurs deux cas
  « libellé non-unique ailleurs mais proche d'une ancre unique » et « champ
  sans libellé propre, identifié par son tooltip (l'équivalent F1) près d'une
  ancre unique ». Le voisinage est la bounding box de l'ancre étendue de
  ``scope_radius`` px (défaut :data:`SCOPE_RADIUS`) : contrairement aux
  tolérances d'alignement (du bruit de rendu), ce rayon exprime une
  **intention** — « jusqu'où s'étend ce que j'appelle le voisinage » — et se
  passe donc en paramètre quand la région visée dépasse le défaut ; un ``>>``
  imbriqué hérite du même rayon. :func:`scope_hint` diagnostique un échec de
  portée (ancre absente, ambiguë, ou voisinage trop étroit) pour des erreurs
  auto-corrigibles.

``exact=False`` (défaut) : correspondance par **préfixe**, insensible à la casse
— l'équivalent du ``~`` RoboSAPiens, pensé pour les tooltips SAP qui finissent
par le raccourci clavier (``Exécuter (F8)``).

Module pur (géométrie sur :class:`~sapfx_common.object_tree.ScreenElement`),
typé, testé hors SAP.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .object_tree import ScreenElement

# Tolérances par défaut, en pixels (valeurs éprouvées par RoboSAPiens :
# alignement 5, voisinage horizontal ~20-30, vertical ~25).
ALIGN_TOLERANCE = 5
MAX_HORIZONTAL_GAP = 30
MAX_VERTICAL_GAP = 25

# Rayon (px) du voisinage exploré par l'opérateur `>>` autour de son ancre —
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
    non modifiable — la façon dont les dynpros affichent du texte statique)."""
    if element.type == "GuiLabel":
        return True
    return element.type in _LABEL_FIELD_TYPES and not element.changeable


def _is_default_target(element: ScreenElement) -> bool:
    return element.type not in _STRUCTURAL_TYPES and not is_label(element)


def _target_filter(elements: Iterable[ScreenElement],
                   types: Optional[Sequence[str]],
                   changeable_only: bool = False) -> list[ScreenElement]:
    """``changeable_only`` : ne garde que les cibles **modifiables** — requis par
    la saisie (un champ non modifiable ne peut pas la recevoir : c'est le
    séparateur « to » des selection screens, un champ affiché en lecture seule…).
    Sans lui, un filtre de types explicite ré-admettrait ces champs-libellés dans
    les positions de grille (``libellé @ N``) — constaté live sur SE16/T000."""
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
    ligne, à droite, écart borné) — ``None`` sinon."""
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
    écart vertical borné) — ``None`` sinon."""
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
    """``text`` est-il un entier positif (une position 1-based) ? ``None`` sinon
    — utilisé pour distinguer ``N @ libellé`` / ``libellé @ N`` de l'intersection
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
    dans les 4 directions) du libellé nommé ``anchor_text`` — la portée de
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


def resolve_semantic(elements: Sequence[ScreenElement], locator: str,
                     types: Optional[Sequence[str]] = None, exact: bool = False,
                     align_tolerance: int = ALIGN_TOLERANCE,
                     max_horizontal_gap: int = MAX_HORIZONTAL_GAP,
                     max_vertical_gap: int = MAX_VERTICAL_GAP,
                     changeable_only: bool = False,
                     scope_radius: Optional[int] = None) -> list[SemanticMatch]:
    """Résout un localisateur humain sur la liste des contrôles de l'écran.

    Retourne TOUS les matches de la première étape qui en produit (voir la
    grammaire dans l'en-tête du module) — dédupliqués par élément, triés par
    (distance, id). C'est à l'appelant d'exiger l'unicité et de formuler
    l'erreur (liste des candidats) : ce module ne tranche jamais en silence.

    ``changeable_only=True`` restreint les **cibles** (jamais les ancres) aux
    éléments modifiables — le contrat d'une saisie. Indispensable aux positions
    de grille : sans lui, le « to » en lecture seule d'un selection screen
    compterait comme position et ``libellé @ 2`` désignerait le séparateur au
    lieu de la borne HIGH (constaté live sur SE16/T000).

    ``scope_radius`` (px) étend le voisinage de l'opérateur ``>>`` au-delà du
    défaut :data:`SCOPE_RADIUS` — une intention (« le voisinage que je vise »),
    pas une tolérance de rendu ; hérité par les ``>>`` imbriqués."""
    locator = (locator or "").strip()
    if not locator:
        return []
    if _SCOPE_SEPARATOR in locator:
        anchor_text, rest = (part.strip() for part in locator.split(_SCOPE_SEPARATOR, 1))
        radius = scope_radius if scope_radius is not None else SCOPE_RADIUS
        neighborhood = _scope_to_anchor(elements, anchor_text, exact, radius)
        if not neighborhood or not rest:
            return []
        # Récursion dans le seul voisinage de l'ancre : `reste` accepte
        # n'importe quelle forme de la grammaire (y compris un `>>` imbriqué,
        # qui hérite du même rayon).
        return resolve_semantic(neighborhood, rest, types=types, exact=exact,
                                align_tolerance=align_tolerance,
                                max_horizontal_gap=max_horizontal_gap,
                                max_vertical_gap=max_vertical_gap,
                                changeable_only=changeable_only,
                                scope_radius=scope_radius)
    if locator.startswith("="):
        content = locator[1:].strip()
        return _dedupe_sorted(
            SemanticMatch(el, "content")
            for el in _target_filter(elements, types, changeable_only)
            if text_matches(el.text, content, exact=True))
    if locator.startswith("@"):
        return _anchored(elements, locator[1:].strip(), "below-label",
                         types, exact, align_tolerance, max_vertical_gap,
                         changeable_only)
    if " @ " in locator:
        left_part, right_part = (part.strip() for part in locator.split(" @ ", 1))
        right_position = _as_position(right_part)
        if right_position is not None:
            return _grid_row(elements, left_part, right_position, types, exact,
                             align_tolerance, changeable_only)
        left_position = _as_position(left_part)
        if left_position is not None:
            return _grid_column(elements, right_part, left_position, types, exact,
                                align_tolerance, changeable_only)
        left_label, top_label = left_part, right_part
        rights = {m.element.id: m for m in _anchored(
            elements, left_label, "right-of-label", types, exact,
            align_tolerance, max_horizontal_gap, changeable_only)}
        belows = {m.element.id: m for m in _anchored(
            elements, top_label, "below-label", types, exact,
            align_tolerance, max_vertical_gap, changeable_only)}
        return _dedupe_sorted(
            SemanticMatch(rights[eid].element, "intersection",
                          rights[eid].anchor,
                          rights[eid].distance + belows[eid].distance)
            for eid in rights.keys() & belows.keys())
    # étape ancrée : droite ET dessous ensemble — si les deux directions
    # désignent des éléments différents, c'est une ambiguïté (remontée à
    # l'appelant), jamais une préférence implicite ; le même élément atteint
    # par les deux voies est naturellement dédupliqué.
    anchored = _dedupe_sorted(
        _anchored(elements, locator, "right-of-label", types, exact,
                  align_tolerance, max_horizontal_gap, changeable_only)
        + _anchored(elements, locator, "below-label", types, exact,
                    align_tolerance, max_vertical_gap, changeable_only))
    if anchored:
        return anchored
    for attr in ("text", "tooltip"):
        matches = _by_own_text(elements, locator, attr, types, exact,
                               changeable_only)
        if matches:
            return matches
    return []


def scope_hint(elements: Sequence[ScreenElement], locator: str,
               exact: bool = False,
               scope_radius: Optional[int] = None) -> Optional[str]:
    """Diagnostic d'un échec de l'opérateur de portée ``ancre >> reste`` —
    ``None`` si ``locator`` n'utilise pas ``>>``.

    Pur, sans effet de bord : l'appelant (keyword, plugin rf-mcp) l'ajoute à son
    message d'échec pour une erreur **auto-corrigible** — la politique du module
    (ne jamais deviner) n'a de valeur que si l'échec dit quoi corriger : ancre
    absente, ancre ambiguë, ou voisinage trop étroit (rayon à élargir)."""
    locator = (locator or "").strip()
    if _SCOPE_SEPARATOR not in locator:
        return None
    anchor_text, rest = (part.strip() for part in locator.split(_SCOPE_SEPARATOR, 1))
    radius = scope_radius if scope_radius is not None else SCOPE_RADIUS
    anchors = [el for el in elements
               if is_label(el) and text_matches(el.text, anchor_text, exact)]
    if not anchors:
        return ("l'ancre de portée '%s' ne correspond à aucun libellé visible"
                % anchor_text)
    if len(anchors) > 1:
        return ("l'ancre de portée '%s' est ambiguë (%d libellés à l'écran) — "
                "une ancre de '>>' doit être unique" % (anchor_text, len(anchors)))
    if anchors[0].left is None or anchors[0].top is None:
        return ("l'ancre de portée '%s' est unique mais sans géométrie — "
                "impossible de délimiter son voisinage" % anchor_text)
    neighborhood = _scope_to_anchor(elements, anchor_text, exact, radius)
    if not neighborhood:
        return ("l'ancre de portée '%s' est unique mais son voisinage est vide "
                "dans un rayon de %d px — élargir via scope_radius"
                % (anchor_text, radius))
    return ("aucun match pour '%s' dans le voisinage de '%s' (%d éléments, "
            "rayon %d px) — élargir scope_radius si la cible est plus loin"
            % (rest, anchor_text, len(neighborhood), radius))


def describe_element(elements: Sequence[ScreenElement], element_id: str,
                     align_tolerance: int = ALIGN_TOLERANCE,
                     max_horizontal_gap: int = MAX_HORIZONTAL_GAP,
                     max_vertical_gap: int = MAX_VERTICAL_GAP) -> Optional[str]:
    """Localisateur humain **vérifié** pour un élément donné — l'inverse de
    :func:`resolve_semantic`, pensé pour le recorder : transcrire l'id technique
    d'un événement en libellé rejouable.

    Candidats essayés dans l'ordre : texte propre, tooltip, puis les
    libellés-ancres dont l'élément est le voisin (droite/dessous), du plus
    proche au plus lointain. Un candidat n'est retenu QUE s'il **re-résout**
    (via ``resolve_semantic``) vers ce seul élément — garantie de rejouabilité
    que RoboSAPiens n'offre pas (premier match non vérifié). ``None`` si aucun
    localisateur humain fiable n'existe (l'appelant garde alors l'id technique
    — jamais de perte d'information)."""
    target = next((el for el in elements if el.id == element_id), None)
    if target is None:
        return None
    candidates: list[str] = []
    # Texte/tooltip propres : candidats sauf pour les champs de SAISIE, dont le
    # texte est la VALEUR en cours — volatile, jamais un localisateur. Le test
    # est is_editable_field, pas `changeable` : le vrai SAP GUI marque
    # Changeable=True sur des boutons de toolbar (constaté live A4H) dont le
    # texte est bien un libellé.
    if not is_editable_field(target):
        for own in (target.text, target.tooltip):
            own = (own or "").strip()
            if own and own not in candidates:
                candidates.append(own)
    anchored: list[tuple[int, str]] = []
    for label in elements:
        text = (label.text or "").strip()
        if not text or not is_label(label) or label.id == element_id:
            continue
        for gap_fn, max_gap in ((_right_of_gap, max_horizontal_gap),
                                (_below_gap, max_vertical_gap)):
            gap = gap_fn(label, target, align_tolerance, max_gap)
            if gap is not None:
                anchored.append((gap, text))
    for _, text in sorted(anchored):
        if text not in candidates:
            candidates.append(text)
    for locator in candidates:
        # exact=False : les mêmes sémantiques (préfixe) que le défaut des
        # keywords au replay — l'unicité sous préfixe implique l'unicité
        # exacte, l'inverse est faux.
        matches = resolve_semantic(
            elements, locator, exact=False,
            align_tolerance=align_tolerance,
            max_horizontal_gap=max_horizontal_gap,
            max_vertical_gap=max_vertical_gap)
        if len(matches) == 1 and matches[0].element.id == element_id:
            return locator
    return None


def nearby_labels(elements: Sequence[ScreenElement], limit: int = 12) -> list[str]:
    """Les textes de libellés visibles à l'écran (dédupliqués, ordre du
    document) — la matière d'un message d'erreur auto-corrigible : « ce libellé
    n'existe pas, voici ceux qui existent »."""
    seen: list[str] = []
    for element in elements:
        if not is_label(element):
            continue
        text = (element.text or "").strip()
        if text and text not in seen:
            seen.append(text)
        if len(seen) >= max(0, int(limit)):
            break
    return seen


# -- perception sémantique : la vue « formulaire » d'un écran ------------------

# Types actionnables SANS être modifiables : ce qu'un humain clique. Les
# GuiMenu en sont exclus pour la même raison que dans Click Button By Label
# (les menus dupliquent le texte des boutons de toolbar — constaté live A4H).
_ACTIONABLE_TYPES = frozenset({"GuiButton", "GuiTab"})


def is_editable_field(element: ScreenElement) -> bool:
    """Vrai si l'élément est un champ de SAISIE au sens humain : modifiable ET
    ni structurel ni actionnable-par-clic. Le vrai SAP GUI marque ``Changeable``
    des choses qui n'en sont pas (GuiUserArea, boutons de toolbar — constaté
    live sur A4H) : ``changeable`` seul ne suffit jamais."""
    return (element.changeable
            and element.type not in _STRUCTURAL_TYPES
            and element.type not in _ACTIONABLE_TYPES)


def actionable_targets(elements: Sequence[ScreenElement]) -> list[ScreenElement]:
    """Les cibles **actionnables** d'un écran, ordre du document : champs
    de saisie (:func:`is_editable_field`) + boutons/onglets (clic). C'est le
    sous-ensemble que partagent la vue affordances (``mode=semantic``) et le
    screenshot annoté — ce sur quoi un agent peut AGIR, débarrassé du bruit
    structurel."""
    return [el for el in elements
            if is_editable_field(el) or el.type in _ACTIONABLE_TYPES]


def screen_affordances(elements: Sequence[ScreenElement],
                       align_tolerance: int = ALIGN_TOLERANCE,
                       max_horizontal_gap: int = MAX_HORIZONTAL_GAP,
                       max_vertical_gap: int = MAX_VERTICAL_GAP) -> list[str]:
    """La vue **formulaire** d'un écran : une ligne par cible actionnable,
    portant son localisateur humain *vérifié* (:func:`describe_element` — émis
    seulement s'il re-résout vers ce seul élément) à côté de l'id technique.

    Format : ``* <libellé>\\t<id>\\t<Type>[\\t= <valeur>]`` pour un champ
    modifiable (``*`` = saisissable, ``= valeur`` = contenu courant), et
    ``  <libellé>\\t<id>\\t<Type>`` pour un bouton/onglet. Un élément sans
    localisateur humain fiable garde ``?`` en colonne libellé — jamais de
    devinette : l'id technique reste alors le seul chemin.

    C'est la perception la plus directement actionnable pour un agent (et la
    moins chère en tokens) : chaque ligne se rejoue telle quelle en
    ``Fill Field By Label`` / ``Click Button By Label`` — ou par id."""
    lines: list[str] = []
    for element in actionable_targets(elements):
        label = describe_element(
            elements, element.id,
            align_tolerance=align_tolerance,
            max_horizontal_gap=max_horizontal_gap,
            max_vertical_gap=max_vertical_gap)
        editable = is_editable_field(element)
        mark = "* " if editable else "  "
        line = "%s%s\t%s\t%s" % (mark, label if label is not None else "?",
                                 element.id, element.type)
        if editable:
            line += "\t= %s" % (element.text or "").strip()
        lines.append(line)
    return lines
