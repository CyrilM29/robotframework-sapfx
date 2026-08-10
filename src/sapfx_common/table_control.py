"""Logique pure des **GuiTableControl** (tables de dynpro classiques).

Le dernier grand objet GUI sans couche de confort : contrairement à l'ALV
(GuiGridView, ``keywords/_grid.py``), un table control ne matérialise que
ses lignes VISIBLES ; lire ou viser une ligne absolue impose de piloter la
scrollbar verticale et de ré-acquérir l'objet COM après chaque défilement.
Ce module porte la partie déterministe : correspondance titre de colonne ->
index (ambiguïté toujours remontée, jamais de premier-match silencieux),
plan de défilement par fenêtres, et positionnement (scroll, index local)
d'une ligne absolue. Le pilotage COM vit dans le mixin.
"""
from __future__ import annotations

from typing import Sequence


def unique_titles(raw_titles: Sequence[str]) -> list[str]:
    """Titres de colonnes exploitables comme clés de dict : colonne sans
    titre nommée ``COL<n>`` (1-based), titre en doublon suffixé `` (2)``,
    `` (3)``… Une lecture ne perd JAMAIS une colonne en silence."""
    counts: dict[str, int] = {}
    titles: list[str] = []
    for index, raw in enumerate(raw_titles):
        title = (raw or "").strip() or ("COL%d" % (index + 1))
        counts[title] = counts.get(title, 0) + 1
        titles.append(title if counts[title] == 1
                      else "%s (%d)" % (title, counts[title]))
    return titles


def column_index_by_title(raw_titles: Sequence[str], wanted: str,
                          context: str = "") -> int:
    """Index (0-based) de la colonne au titre ``wanted`` (insensible à la
    casse, blancs de bordure ignorés). Plusieurs colonnes portent ce titre =
    ValueError invitant à employer la forme dédoublonnée (`` (2)``…) de
    `unique_titles` ; aucun = la forme dédoublonnée est aussi tentée, puis
    ValueError listant les titres disponibles."""
    target = str(wanted).strip().casefold()
    matches = [index for index, title in enumerate(raw_titles)
               if (title or "").strip().casefold() == target]
    if len(matches) == 1:
        return matches[0]
    where = " dans '%s'" % context if context else ""
    if len(matches) > 1:
        raise ValueError(
            "Titre de colonne '%s' ambigu%s (%d colonnes le portent) : "
            "employer la forme dédoublonnée ('%s (2)'…) telle que "
            "Read Table Control la retourne." % (wanted, where, len(matches),
                                                 wanted))
    deduplicated = unique_titles(raw_titles)
    matches = [index for index, title in enumerate(deduplicated)
               if title.casefold() == target]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(
        "Aucune colonne titrée '%s'%s. Titres disponibles : %s"
        % (wanted, where, ", ".join(repr(t) for t in deduplicated) or "aucun"))


def window_plan(total_rows: int, visible_rows: int) -> list[tuple[int, int, int]]:
    """Plan de lecture d'une table entière : liste de
    ``(position_scroll, index_local_de_départ, nombre_de_lignes)`` couvrant
    CHAQUE ligne exactement une fois.

    La subtilité, constatée live (SE11, 47 lignes pour 22 visibles) : la
    scrollbar d'un GuiTableControl plafonne à ``total - visible`` (ici 25),
    demander la position 44 lève un ``com_error``. La dernière fenêtre est
    donc bornée et **chevauche** la précédente : elle doit être lue à partir
    d'un index local décalé, sinon les lignes de fin sont lues deux fois et
    les vraies dernières lignes jamais. Table vide : plan vide ; table
    entièrement visible : une seule fenêtre."""
    if total_rows <= 0:
        return []
    if visible_rows <= 0 or visible_rows >= total_rows:
        return [(0, 0, total_rows)]
    plan: list[tuple[int, int, int]] = []
    max_position = total_rows - visible_rows
    next_row = 0
    while next_row < total_rows:
        position = min(next_row, max_position)
        local = next_row - position
        count = visible_rows - local
        plan.append((position, local, count))
        next_row += count
    return plan


def window_for_row(row: int, total_rows: int, visible_rows: int) -> tuple[int, int]:
    """``(position de scroll, index local)`` pour atteindre la ligne ABSOLUE
    ``row``. La position est alignée sur les fenêtres puis bornée au dernier
    scroll possible (``total - visible``, la limite réelle de la scrollbar) :
    la ligne reste dans la fenêtre même en fin de table. Ligne hors bornes =
    ValueError actionnable."""
    if row < 0 or (total_rows > 0 and row >= total_rows):
        raise ValueError(
            "Ligne %d hors bornes : la table compte %d ligne(s) (indices "
            "0..%d)." % (row, total_rows, max(0, total_rows - 1)))
    if visible_rows <= 0:
        return 0, row
    max_position = max(0, total_rows - visible_rows)
    position = min(row - (row % visible_rows), max_position)
    return position, row - position
