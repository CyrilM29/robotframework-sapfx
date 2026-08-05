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
"""
from __future__ import annotations

from typing import Sequence

from .object_tree import ScreenElement

# Deux labels dont les ``top`` diffèrent d'au plus cette tolérance (pixels)
# appartiennent à la même ligne (léger décalage de rendu possible).
ROW_TOLERANCE = 3


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
