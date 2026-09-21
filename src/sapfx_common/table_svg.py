"""Rendu d'un relevé tabulaire en **SVG**, logique pure.

Le dépôt sait déjà restituer une mesure en JSON déterministe
(:mod:`sapfx_common.artifacts`) et en Markdown (les rapports de posture, de
sentinelle, de croisement). Il lui manquait la restitution qu'un rapport
d'audit ou une page de documentation consomme directement : une image
VECTORIELLE du tableau relevé, lisible sans SAP, sans tableur et sans police
particulière.

Ce que ce module rend n'est pas une capture d'écran : c'est le CONTENU lu par
l'API de scripting, redessiné. La différence compte pour une preuve. Une
capture montre ce que le client a peint, avec son profil d'affichage et la
résolution du poste ; le relevé redessiné est reproductible, et deux runs sur
la même donnée produisent le même fichier à l'octet près. C'est la même
propriété que les artefacts JSON du dépôt, et elle est délibérée : aucun
horodatage n'est injecté, le sous-titre est un argument.

L'en-tête, lui, est au choix de l'appelant : les identifiants TECHNIQUES par
défaut (indépendants de la langue, donc comparables entre deux systèmes), ou
les titres AFFICHÉS via ``headers`` quand le document est destiné à un lecteur
humain. Le second choix rend le fichier localisé : c'est voulu, et c'est
pourquoi il se demande.

**Trois choix de rendu, et leurs raisons.**

1. Police monospace pour les cellules. La largeur d'une colonne se CALCULE
   alors (avance fixe), là qu'une police proportionnelle obligerait soit à
   mesurer le texte (impossible sans moteur de rendu), soit à surdimensionner.
2. Fond clair explicite. Un SVG sans fond hérite de celui de la visionneuse,
   donc un texte sombre devient illisible sur un thème sombre.
3. Une troncature n'est jamais muette. Une cellule coupée porte une ellipse,
   une infobulle SVG avec sa valeur complète, et le pied de page annonce le
   nombre de cellules concernées. C'est la règle que le dépôt applique déjà à
   ses lectures de grille, transposée au rendu.

Typé, sans dépendance : importable comme bibliothèque Robot
(``Library    sapfx_common.table_svg``), donc les primitives s'atteignent par
un KEYWORD et jamais par un ``Evaluate __import__(...)`` dans une suite.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

from sapfx_common._tabular import cell_text as _cell_text
from sapfx_common._tabular_io import write_text
from sapfx_common._tabular import header_labels, normalize_rows
from sapfx_common._tabular import table_columns, xml_escape
from sapfx_common._tabular import row_limit
from sapfx_common.robot_args import as_optional_int

__all__ = [
    "CHAR_WIDTH_RATIO",
    "svg_escape",
    "table_columns",
    "column_widths",
    "render_table_svg",
    "write_table_svg",
]

#: Avance d'un caractère dans une police monospace, en fraction de la taille de
#: police. 0.6 est la valeur des monospaces courantes (Consolas, DejaVu Sans
#: Mono, Liberation Mono) ; elle est légèrement majorée à dessein, un tableau
#: un peu large valant mieux qu'un tableau dont le texte déborde.
CHAR_WIDTH_RATIO = 0.62

_PALETTE = {
    "page": "#ffffff",
    "ink": "#1b1f24",
    "muted": "#57606a",
    "rule": "#d0d7de",
    "header_bg": "#f2f4f7",
    "zebra": "#f8f9fb",
    "accent": "#0b4f8a",
}


def svg_escape(text: Any) -> str:
    """Échappe une valeur pour du contenu XML.

    Les cinq caractères le sont, ``&`` en premier pour ne pas ré-échapper les
    entités que les autres viennent de produire, et les caractères de contrôle
    sont retirés : non représentables en XML 1.0, ils feraient rejeter le
    document ENTIER par une visionneuse stricte, et une valeur lue sur un
    écran peut en porter. Une valeur ``None`` devient une chaîne vide.
    """
    return xml_escape(text)


def column_widths(rows: Sequence[Mapping[str, Any]], columns: Sequence[str],
                  font_size: int = 12, padding: int = 12,
                  max_chars: int = 80,
                  labels: Optional[Sequence[str]] = None) -> list[int]:
    """Largeur en pixels de chaque colonne, dérivée du contenu le plus long.

    L'en-tête entre dans le calcul : une colonne à valeurs courtes mais au nom
    technique long reste lisible. Le plafond ``max_chars`` borne la largeur,
    et c'est lui qui décide des cellules tronquées : les deux mesures viennent
    donc de la même règle, et un rendu ne peut pas couper un texte que le
    calcul de largeur aurait cru entier.
    """
    largeurs = []
    entetes = list(labels) if labels else [str(c) for c in columns]
    for colonne, entete in zip(columns, entetes, strict=True):
        plus_long = len(str(entete))
        for ligne in rows:
            texte, _ = _cell_text(ligne.get(colonne), max_chars)
            plus_long = max(plus_long, len(texte))
        largeurs.append(
            int(round(plus_long * font_size * CHAR_WIDTH_RATIO)) + 2 * padding)
    return largeurs


def render_table_svg(rows: Iterable[Mapping[str, Any]],
                     columns: Optional[Sequence[str]] = None,
                     title: Optional[str] = None,
                     subtitle: Optional[str] = None,
                     headers: Optional[Mapping[str, Any]] = None,
                     max_rows: Optional[int] = None,
                     max_cell_chars: int = 80,
                     font_size: int = 12,
                     row_height: int = 20) -> str:
    """Rend un relevé tabulaire en un document SVG autonome.

    ``rows`` est une liste de dicts telle que ``Read Grid`` la produit.
    ``columns`` restreint et ordonne les colonnes (par défaut : toutes, dans
    l'ordre rencontré). ``title`` et ``subtitle`` coiffent le tableau ;
    aucun horodatage n'est ajouté, de sorte que deux rendus de la même donnée
    sont identiques à l'octet près et qu'un artefact committé se compare.

    ``max_rows`` borne le nombre de lignes rendues et ``max_cell_chars`` la
    largeur d'une cellule (``0`` retire le plafond). Les deux troncatures sont
    ANNONCÉES dans le pied du document, et une cellule coupée porte sa valeur
    complète en infobulle : un tableau rendu ne doit jamais faire croire qu'il
    montre tout.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    # Via rf-mcp et la ligne de commande Robot, tout argument arrive en
    # chaîne : la conversion nomme l'argument plutôt que de lever un
    # `int('')` qui ne désignerait rien.
    plafond = max(0, as_optional_int(max_cell_chars, "max_cell_chars") or 0)
    borne = row_limit(max_rows)
    total = len(lignes)
    if borne is not None and borne >= 0:
        lignes = lignes[:borne]
    rendues = len(lignes)

    # Les largeurs tiennent compte du libellé AFFICHÉ, sans quoi un titre
    # SAP plus long que son identifiant technique déborderait de sa colonne.
    largeurs = column_widths(lignes, colonnes, font_size=font_size,
                             max_chars=plafond,
                             labels=header_labels(colonnes, headers))
    marge = 24
    hauteur_entete = row_height + 8
    haut_tableau = marge + (28 if title else 0) + (20 if subtitle else 0)
    largeur_tableau = sum(largeurs)
    largeur = largeur_tableau + 2 * marge
    bas_tableau = haut_tableau + hauteur_entete + rendues * row_height
    notes = _footer_notes(total, rendues, lignes, colonnes, plafond)
    hauteur = bas_tableau + marge + len(notes) * 16

    out: list[str] = []
    out.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="Consolas, \'DejaVu Sans Mono\', '
        'monospace">' % (largeur, hauteur, largeur, hauteur))
    if title:
        out.append('<title>%s</title>' % svg_escape(title))
    out.append('<rect width="%d" height="%d" fill="%s"/>'
               % (largeur, hauteur, _PALETTE["page"]))
    y = marge + 4
    if title:
        out.append(_text(marge, y + 12, svg_escape(title), font_size + 6,
                         _PALETTE["ink"], weight="bold"))
        y += 28
    if subtitle:
        out.append(_text(marge, y + 10, svg_escape(subtitle), font_size - 1,
                         _PALETTE["muted"]))

    out.extend(_render_header(header_labels(colonnes, headers), largeurs,
                              marge, haut_tableau, hauteur_entete, font_size))
    out.extend(_render_body(lignes, colonnes, largeurs, marge,
                            haut_tableau + hauteur_entete, row_height,
                            font_size, plafond, largeur_tableau))
    out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" '
               'stroke="%s"/>' % (marge, haut_tableau, largeur_tableau,
                                  hauteur_entete + rendues * row_height,
                                  _PALETTE["rule"]))
    for index, note in enumerate(notes):
        out.append(_text(marge, bas_tableau + 16 + index * 16,
                         svg_escape(note), font_size - 1, _PALETTE["muted"]))
    out.append('</svg>')
    return "\n".join(out) + "\n"


def _text(x: int, y: int, contenu: str, taille: int, couleur: str,
          weight: str = "normal", extra: str = "") -> str:
    poids = ' font-weight="bold"' if weight == "bold" else ""
    return ('<text x="%d" y="%d" font-size="%d" fill="%s"%s%s>%s</text>'
            % (x, y, taille, couleur, poids, extra, contenu))


def _render_header(colonnes: Sequence[str], largeurs: Sequence[int],
                   marge: int, haut: int, hauteur: int,
                   font_size: int) -> list[str]:
    parties = ['<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
               % (marge, haut, sum(largeurs), hauteur, _PALETTE["header_bg"])]
    x = marge
    for colonne, largeur in zip(colonnes, largeurs, strict=True):
        parties.append(_text(x + 12, haut + hauteur - 9,
                             svg_escape(colonne), font_size,
                             _PALETTE["accent"], weight="bold"))
        x += largeur
        if colonne != colonnes[-1]:
            parties.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
                           % (x, haut, x, haut + hauteur, _PALETTE["rule"]))
    return parties


def _render_body(lignes: Sequence[Mapping[str, Any]],
                 colonnes: Sequence[str], largeurs: Sequence[int],
                 marge: int, haut: int, row_height: int, font_size: int,
                 plafond: int, largeur_tableau: int) -> list[str]:
    parties: list[str] = []
    for index, ligne in enumerate(lignes):
        y = haut + index * row_height
        if index % 2:
            parties.append('<rect x="%d" y="%d" width="%d" height="%d" '
                           'fill="%s"/>' % (marge, y, largeur_tableau,
                                            row_height, _PALETTE["zebra"]))
        x = marge
        for colonne, largeur in zip(colonnes, largeurs, strict=True):
            brut = ligne.get(colonne)
            texte, coupe = _cell_text(brut, plafond)
            if texte:
                contenu = _text(x + 12, y + row_height - 6, svg_escape(texte),
                                font_size, _PALETTE["ink"])
                if coupe:
                    # L'infobulle porte la valeur ENTIÈRE : la coupe est un
                    # fait de rendu, jamais une perte de donnée.
                    contenu = contenu.replace(
                        "</text>", "<title>%s</title></text>"
                        % svg_escape(brut))
                parties.append(contenu)
            x += largeur
    return parties


def _footer_notes(total: int, rendues: int,
                  lignes: Sequence[Mapping[str, Any]],
                  colonnes: Sequence[str], plafond: int) -> list[str]:
    notes = []
    if rendues == total:
        notes.append("%d ligne(s), %d colonne(s)." % (total, len(colonnes)))
    else:
        notes.append(
            "%d ligne(s) rendues sur %d : le tableau est TRONQUÉ (max_rows)."
            % (rendues, total))
    coupees = _truncated_cells(lignes, colonnes, plafond)
    if coupees:
        notes.append(
            "%d cellule(s) coupées à %d caractères pour le rendu ; la valeur "
            "complète est en infobulle." % (coupees, plafond))
    return notes


def _truncated_cells(lignes: Sequence[Mapping[str, Any]],
                     colonnes: Sequence[str], plafond: int) -> int:
    if not plafond:
        return 0
    return sum(1 for ligne in lignes for colonne in colonnes
               if _cell_text(ligne.get(colonne), plafond)[1])


def write_table_svg(path: str, rows: Iterable[Mapping[str, Any]],
                    columns: Optional[Sequence[str]] = None,
                    title: Optional[str] = None,
                    subtitle: Optional[str] = None,
                    headers: Optional[Mapping[str, Any]] = None,
                    max_rows: Optional[int] = None,
                    max_cell_chars: int = 80) -> dict[str, Any]:
    """Écrit le relevé en SVG et rend un verdict JSON-safe.

    Le verdict porte ``{path, rows, total_rows, columns, truncated_rows,
    truncated_cells, bytes}`` : un appelant peut donc ASSERTER ce qui a été
    rendu au lieu de faire confiance au fichier. ``truncated_rows`` dit si le
    tableau est incomplet, ce qu'un simple compte de lignes ne dirait pas.

    Le fichier est écrit en UTF-8 avec des fins de ligne LF quelle que soit la
    plateforme : un artefact committé ne doit pas différer selon le poste qui
    l'a produit.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    document = render_table_svg(lignes, columns=colonnes, title=title,
                                subtitle=subtitle, headers=headers,
                                max_rows=max_rows,
                                max_cell_chars=max_cell_chars)
    cible = write_text(path, document, encoding="utf-8", newline="\n")
    borne = row_limit(max_rows)
    rendues = (len(lignes) if borne is None
               else min(len(lignes), max(0, borne)))
    plafond = max(0, as_optional_int(max_cell_chars, "max_cell_chars") or 0)
    return {
        "path": cible,
        "rows": rendues,
        "total_rows": len(lignes),
        "columns": list(colonnes),
        "headers": header_labels(colonnes, headers),
        "truncated_rows": rendues < len(lignes),
        "truncated_cells": _truncated_cells(lignes[:rendues], colonnes,
                                            plafond),
        "bytes": len(document.encode("utf-8")),
    }
