"""Reconstruction d'une liste ABAP classique à partir des labels positionnés.

Une liste ABAP (sortie SE38, SE16 sans ALV, protocoles…) n'expose **aucun objet
table scriptable** : l'écran n'est qu'une nuée de ``GuiLabel`` disposés en
grille. L'idée (observée chez RoboSAPiens, Apache-2.0, ``AbapList.cs``) : la
géométrie suffit à retrouver la structure : les labels d'une même bande
horizontale forment une ligne, l'ordre ``left`` donne les colonnes.

Version volontairement simple : des lignes de cellules texte, sans typage de
colonnes (assez pour « le rapport contient X » et les comparaisons ligne à
ligne). Module pur sur :class:`~sapfx_common.object_tree.ScreenElement`, typé,
testé hors SAP. NB : SAP GUI ne peuple finement les labels de liste qu'avec le
**mode accessibilité** activé (Options SAP GUI → Accessibilité), même
prérequis que RoboSAPiens documente.

Depuis le 2026-10-01 (fiche scénario 9), le module rend aussi les lignes
ALIGNÉES sur l'en-tête (`aligned_rows`) : la reconstruction géométrique jette
les cellules vides, donc une ligne à trou décale toutes ses valeurs d'une
colonne, et la ligne de texte « liste vide » d'une liste sans donnée sort
comme une ligne de données. Les listes classiques portent pourtant mieux que
la géométrie : l'identifiant de chaque label dit sa COLONNE de caractère et
sa LIGNE de liste (``lbl[64,13]``), et les listes sélectionnables (SM37,
SP01) portent une case ``chk[1,13]`` sur chaque ligne de données. Mesuré sur
SM36, SM37 et SP01 de la release 754.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from .object_tree import ScreenElement

# Deux labels dont les ``top`` diffèrent d'au plus cette tolérance (pixels)
# appartiennent à la même ligne (léger décalage de rendu possible).
ROW_TOLERANCE = 3

#: Modes de sélection des lignes de données de `aligned_rows`.
ROW_MODES = ("auto", "selectable", "all")

_LIST_CELL = re.compile(r"/usr/(lbl|chk|txt|ctxt)\[(\d+),(\d+)\]$")


def reconstruct_rows(elements: Sequence[ScreenElement],
                     row_tolerance: int = ROW_TOLERANCE) -> list[list[str]]:
    """Reconstruit les lignes d'une liste ABAP : ``[[cellule, ...], ...]`` de
    haut en bas, cellules de gauche à droite.

    Ne retient que les ``GuiLabel`` porteurs de texte ET de géométrie ; les
    écrans sans liste (aucun label positionné) donnent ``[]`` : l'appelant en
    fait une erreur explicite s'il attendait une liste."""
    cells = [(int(el.top), int(el.left), el.id, el.text.strip())
             for el in elements
             if el.type == "GuiLabel" and (el.text or "").strip()
             and el.top is not None and el.left is not None]
    cells.sort()
    tolerance = max(0, int(row_tolerance))
    bands: list[tuple[int, list[tuple[int, int, str, str]]]] = []
    for cell in cells:
        if bands and abs(cell[0] - bands[-1][0]) <= tolerance:
            bands[-1][1].append(cell)
        else:
            bands.append((cell[0], [cell]))
    return [[text for _, _, _, text in sorted(band, key=lambda c: (c[1], c[2]))]
            for _, band in bands]


@dataclass(frozen=True)
class ListCell:
    """Une cellule de liste classique : nature (``lbl`` texte, ``chk`` case,
    ``txt``/``ctxt`` champ), colonne et ligne de liste, texte, identifiant."""
    kind: str
    column: int
    row: int
    text: str
    id: str


def list_cells(elements: Sequence[ScreenElement]) -> list[ListCell]:
    """Les cellules d'une liste classique, lues dans les identifiants
    ``usr/lbl[c,r]`` (et ``chk``, ``txt``, ``ctxt``), triées par ligne puis
    colonne. Les éléments sans coordonnées de liste sont ignorés."""
    cells = []
    for element in elements:
        match = _LIST_CELL.search(element.id or "")
        if not match:
            continue
        cells.append(ListCell(kind=match.group(1), column=int(match.group(2)),
                              row=int(match.group(3)),
                              text=(element.text or "").strip(), id=element.id))
    cells.sort(key=lambda cell: (cell.row, cell.column))
    return cells


def _text_cells(cells: Sequence[ListCell]) -> list[ListCell]:
    return [cell for cell in cells if cell.kind != "chk" and cell.text]


def _by_row(cells: Sequence[ListCell]) -> dict[int, list[ListCell]]:
    rows: dict[int, list[ListCell]] = {}
    for cell in cells:
        rows.setdefault(cell.row, []).append(cell)
    return rows


def boxed_rows(cells: Sequence[ListCell]) -> set[int]:
    """Les lignes ENCADRÉES d'une liste classique : bornées à gauche ET à
    droite par un label VIDE (le trait vertical d'un cadre), au plus deux
    cellules texte entre les deux (un libellé et sa valeur, ou un message).

    Mesuré sur SM58, SMQ1 et SMQ2 (754 et 758, 2026-10-18) : le bloc de
    synthèse en tête de liste (« Number of Entries Displayed » et sa valeur)
    a des labels vides en colonnes 1 et 49 sur chaque ligne, et le message
    « Nothing was selected. » est encadré de même (colonnes 1 et 63). Une
    ligne d'en-tête ou de données porte plus de deux cellules texte : la
    borne protège une liste à séparateurs verticaux d'être prise pour un
    cadre."""
    rows = _by_row([cell for cell in cells if cell.kind == "lbl"])
    boxed = set()
    for number, row_cells in rows.items():
        texts = _text_cells(row_cells)
        if not texts or len(texts) > 2:
            continue
        left = min(row_cells, key=lambda cell: cell.column)
        right = max(row_cells, key=lambda cell: cell.column)
        if left.text or right.text or left is right:
            continue
        if all(left.column < cell.column < right.column for cell in texts):
            boxed.add(number)
    return boxed


def _boxed_runs(boxed: set[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for number in sorted(boxed):
        if runs and number == runs[-1][-1] + 1:
            runs[-1].append(number)
        else:
            runs.append([number])
    return runs


def list_summary(elements: Sequence[ScreenElement]) -> list[dict[str, Any]]:
    """Le bloc de synthèse ENCADRÉ en tête d'une liste classique : une entrée
    ``{row, label, value}`` par ligne, dans l'ordre (ligne de titre :
    ``value`` vide). Un bloc est une suite de lignes encadrées consécutives
    dont au moins une porte DEUX cellules (libellé et valeur) ; un message
    encadré seul (« Nothing was selected. ») n'en est pas un, et une liste
    sans bloc rend ``[]``. Libellés localisés : rendus pour le page object
    qui les ancre, jamais une clé d'assertion."""
    cells = list_cells(elements)
    by_row = _by_row(cells)
    summary: list[dict[str, Any]] = []
    for run in _boxed_runs(boxed_rows(cells)):
        if not any(len(_text_cells(by_row[number])) == 2 for number in run):
            continue
        for number in run:
            texts = _text_cells(by_row[number])
            summary.append({"row": number, "label": texts[0].text,
                            "value": texts[1].text if len(texts) > 1 else ""})
    return summary


def _messages(by_row: dict[int, list[ListCell]], boxed: set[int]) -> list[dict[str, Any]]:
    """Les messages encadrés isolés (une ligne, une cellule) : jamais une donnée."""
    found = []
    for run in _boxed_runs(boxed):
        texts = _text_cells(by_row[run[0]])
        if len(run) == 1 and len(texts) == 1:
            found.append({"_row": run[0], "text": texts[0].text})
    return found


def _find_header_row(rows: dict[int, list[ListCell]], header: Any,
                     selectable: Sequence[int],
                     boxed: frozenset[int] = frozenset()) -> Optional[int]:
    """Le numéro de ligne de l'en-tête : ``header`` entier (numéro de ligne
    de liste), texte (première ligne portant une cellule égale), ou ``auto``.

    ``auto`` dans une liste à cases : parmi les lignes SANS case situées
    au-dessus de la dernière ligne à case, celle dont les débuts de cellule
    coïncident le plus souvent avec ceux des cellules texte des lignes à
    case qui la SUIVENT (un en-tête est écrit aux colonnes de ses données) ;
    à égalité, celle qui porte le plus de cellules texte, puis la plus
    basse. Mesuré sur SM37 : le rappel des critères de sélection en tête de
    liste porte lui aussi des cases (``chk[65,5]``, ``chk[0,6]``), donc
    « au-dessus de la première ligne à case » désignait un critère. Mesuré
    sur la liste SE16 standard (2026-10-06) : la ligne d'information
    « Displayed Fields: 4 of 5 Fixed Columns: 2 List Width 0250 » porte
    huit cellules contre quatre à l'en-tête, et « la plus fournie » la
    prenait pour l'en-tête, chaque ligne rendant alors ses trois premières
    valeurs fondues dans une seule colonne. Sans case : la première ligne
    d'au moins deux cellules texte. Les lignes ENCADRÉES (`boxed_rows` :
    bloc de synthèse, message) cèdent la place à toute autre candidate
    (mesuré le 2026-10-18 : sur SM58 et SMQ1, « Number of Entries
    Displayed » et sa valeur étaient pris pour l'en-tête). Une liste qui ne
    porte QUE des lignes encadrées, dont un message isolé (« Nothing was
    selected. »), n'a pas d'en-tête : ``None``."""
    text = str(header).strip() if header is not None else "auto"
    if text.isdigit():
        number = int(text)
        if number not in rows:
            raise ValueError("Ligne d'en-tête %d absente de la liste (lignes : %s)."
                             % (number, sorted(rows)))
        return number
    if text.lower() != "auto":
        for number in sorted(rows):
            if any(cell.text == text for cell in _text_cells(rows[number])):
                return number
        raise ValueError("Aucune ligne de la liste ne porte la cellule d'en-tête %r." % text)
    last_selectable = max(selectable) if selectable else None
    candidates = [number for number in sorted(rows)
                  if len(_text_cells(rows[number])) >= 2
                  and number not in selectable
                  and (last_selectable is None or number < last_selectable)]
    unboxed = [number for number in candidates if number not in boxed]
    if unboxed:
        candidates = unboxed
    elif boxed and not selectable and _messages(rows, set(boxed)) and all(
            number in boxed for number in rows if _text_cells(rows[number])):
        # bloc de synthèse et message encadré seulement : aucune donnée. Sans
        # message isolé, l'ancienne règle s'applique (une liste à séparateurs
        # verticaux encadre aussi ses lignes)
        return None
    if not candidates:
        raise ValueError(
            "Aucune ligne d'en-tête détectable (au moins deux cellules texte%s) : "
            "passer header=<texte d'une cellule d'en-tête> ou son numéro de ligne."
            % (" au-dessus des lignes sélectionnables" if selectable else ""))
    if last_selectable is None:
        return candidates[0]

    def rank(number: int) -> tuple[int, int, int]:
        starts = {cell.column for cell in _text_cells(rows[number])}
        aligned = sum(1 for below in selectable if below > number
                      for cell in _text_cells(rows.get(below, []))
                      if cell.column in starts)
        return aligned, len(starts), number

    return max(candidates, key=rank)


def _titles(header_cells: Sequence[ListCell]) -> list[str]:
    titles: list[str] = []
    for cell in header_cells:
        title, rank = cell.text, 2
        while title in titles:
            title = "%s (%d)" % (cell.text, rank)
            rank += 1
        titles.append(title)
    return titles


def _spans_header_columns(cells: Sequence[ListCell], starts: Sequence[int]) -> bool:
    """Vrai pour une ligne d'UNE seule cellule texte qui recouvre au moins
    deux débuts de colonne d'en-tête : la forme STRUCTURELLE d'une ligne de
    message (« liste vide »), jamais lue sur son texte localisé."""
    texts = _text_cells(cells)
    if len(texts) != 1:
        return False
    cell = texts[0]
    end = cell.column + len(cell.text)
    return sum(1 for start in starts if cell.column <= start < end) >= 2


def aligned_rows(elements: Sequence[ScreenElement], header: Any = "auto",
                 rows: str = "auto") -> dict[str, Any]:
    """Lignes de données d'une liste classique, chaque cellule rattachée à
    sa colonne d'en-tête par la colonne de son identifiant : ``{"header_row",
    "columns", "rows", "ignored"}``.

    Chaque ligne est un dict ``{titre d'en-tête: valeur}`` complet (cellule
    absente = ``""``, jamais une colonne qui glisse), plus ``_row`` (ligne de
    liste), ``_selectable`` et ``_checkbox`` (identifiant de la case, vide
    sans case). Une cellule rattachée à la colonne d'en-tête qui commence au
    plus tard à sa gauche ; une cellule à gauche de la première colonne prend
    la clé ``_col<c>``. Titres répétés suffixés ``(2)``.

    ``rows`` : ``selectable`` (seules les lignes à case : une liste
    sélectionnable SANS donnée rend ``[]``), ``all`` (toutes les lignes sous
    l'en-tête), ``auto`` (``selectable`` si la liste porte au moins une case,
    sinon ``all`` moins les lignes de message, rendues dans ``ignored``)."""
    mode = str(rows or "auto").strip().lower()
    if mode not in ROW_MODES:
        raise ValueError("rows=%r inconnu ; attendu : %s." % (rows, ", ".join(ROW_MODES)))
    cells = list_cells(elements)
    by_row = _by_row(cells)
    checkboxes = {cell.row: cell.id for cell in cells if cell.kind == "chk"}
    boxed = boxed_rows(cells)
    header_row = _find_header_row(by_row, header, sorted(checkboxes), frozenset(boxed))
    if header_row is None:
        # liste réduite à un bloc de synthèse et/ou un message encadré : aucune
        # donnée, et le message n'en est pas une (SM58 et SMQ1 sans sélection)
        return {"header_row": None, "columns": [], "rows": [],
                "ignored": _messages(by_row, boxed)}
    header_cells = _text_cells(by_row[header_row])
    titles = _titles(header_cells)
    starts = [cell.column for cell in header_cells]
    effective = mode if mode != "auto" else ("selectable" if checkboxes else "all")
    data: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for number in sorted(by_row):
        if number <= header_row:
            continue
        if effective == "selectable" and number not in checkboxes:
            continue
        row_cells = by_row[number]
        texts = _text_cells(row_cells)
        if number not in checkboxes and not texts:
            continue
        if mode == "auto" and not checkboxes and _spans_header_columns(row_cells, starts):
            ignored.append({"_row": number, "text": texts[0].text})
            continue
        record: dict[str, Any] = {title: "" for title in titles}
        for cell in texts:
            index = max((i for i, start in enumerate(starts) if start <= cell.column),
                        default=None)
            key = titles[index] if index is not None else "_col%d" % cell.column
            record[key] = (str(record.get(key, "")) + " " + cell.text).strip()
        record["_row"] = number
        record["_selectable"] = number in checkboxes
        record["_checkbox"] = checkboxes.get(number, "")
        data.append(record)
    return {"header_row": header_row,
            "columns": [{"column": start, "title": title}
                        for start, title in zip(starts, titles, strict=True)],
            "rows": data, "ignored": ignored}


def matching_rows(rows: Sequence[dict[str, Any]], text: Any,
                  column: Optional[str] = None) -> list[dict[str, Any]]:
    """Les lignes dont une cellule (ou la cellule de la colonne ``column``)
    vaut EXACTEMENT ``text`` (blancs des bords ignorés). Une colonne inconnue
    lève ``ValueError`` en listant les colonnes."""
    wanted = str(text).strip()
    if column is not None and rows and column not in rows[0]:
        known = [key for key in rows[0] if not key.startswith("_")]
        raise ValueError("Colonne %r inconnue ; colonnes : %s." % (column, known))
    found = []
    for row in rows:
        values = ([row.get(column, "")] if column is not None
                  else [value for key, value in row.items() if not key.startswith("_")])
        if any(str(value).strip() == wanted for value in values):
            found.append(row)
    return found


def find_list_cell(elements: Sequence[ScreenElement], text: Any,
                   column: Optional[str] = None, header: Any = "auto") -> ListCell:
    """Le label d'une ligne de données dont le texte vaut EXACTEMENT ``text``
    (dans la colonne d'en-tête ``column`` si elle est donnée) : la cible d'un
    double-clic de liste (descendre d'un niveau dans SMQ2, ouvrir un spool).

    Aucune cellule = ``ValueError`` avec un échantillon ; plusieurs =
    ``ValueError`` les listant (jamais la première venue) ; colonne inconnue
    = ``ValueError`` listant les colonnes ; liste sans en-tête (rien que des
    lignes encadrées) = ``ValueError``."""
    result = aligned_rows(elements, header=header, rows="all")
    if result["header_row"] is None:
        raise ValueError("La liste n'a ni en-tête ni donnée (bloc de synthèse ou message "
                         "seulement) : aucune cellule à viser.")
    starts = [entry["column"] for entry in result["columns"]]
    titles = [entry["title"] for entry in result["columns"]]
    if column is not None and column not in titles:
        raise ValueError("Colonne %r inconnue ; colonnes : %s." % (column, titles))
    data_rows = {int(row["_row"]) for row in result["rows"]}
    wanted = str(text).strip()
    found = []
    for cell in list_cells(elements):
        if cell.kind != "lbl" or cell.row not in data_rows or cell.text != wanted:
            continue
        index = max((i for i, start in enumerate(starts) if start <= cell.column), default=None)
        if column is None or (index is not None and titles[index] == column):
            found.append(cell)
    if not found:
        sample = sorted({value for row in result["rows"][:10] for key, value in row.items()
                         if not key.startswith("_") and value})[:12]
        raise ValueError("Aucune cellule de la liste ne vaut %r%s ; échantillon : %s."
                         % (wanted, " dans la colonne %r" % column if column else "", sample))
    if len(found) > 1:
        raise ValueError("%d cellules valent %r%s (%s) : préciser column=."
                         % (len(found), wanted, " dans la colonne %r" % column if column else "",
                            [cell.id for cell in found]))
    return found[0]


def attach_icons(result: Mapping[str, Any], icons: Mapping[str, str]) -> list[dict[str, Any]]:
    """Ajoute à chaque ligne de :func:`aligned_rows` une clé ``_icons``
    ``{titre d'en-tête: nom d'icône}`` à partir de ``icons`` (identifiant de
    label -> ``IconName`` non vide). Une liste classique rend un état par une
    ICÔNE dans un label sans texte (« Actv » de SMICM : ``S_OKAY`` sur un
    service actif, rien sur un inactif, mesuré le 2026-10-08) : le texte de la
    cellule est vide dans les deux cas. Le nom d'icône est technique, donc
    locale-safe. Une icône à gauche de la première colonne prend
    ``_col<c>``."""
    starts = [column["column"] for column in result.get("columns", [])]
    titles = [column["title"] for column in result.get("columns", [])]
    by_row: dict[int, dict[str, str]] = {}
    for element_id, icon in icons.items():
        match = _LIST_CELL.search(element_id or "")
        if not match or not icon:
            continue
        column, row = int(match.group(2)), int(match.group(3))
        index = max((i for i, start in enumerate(starts) if start <= column), default=None)
        key = titles[index] if index is not None else "_col%d" % column
        by_row.setdefault(row, {})[key] = str(icon)
    rows = []
    for record in result.get("rows", []):
        enriched = dict(record)
        enriched["_icons"] = by_row.get(int(record["_row"]), {})
        rows.append(enriched)
    return rows
