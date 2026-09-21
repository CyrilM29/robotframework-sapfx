"""Écriture d'un relevé tabulaire en **classeur Excel** (.xlsx), logique pure.

Pendant de :mod:`sapfx_common.table_svg` : le SVG est une preuve qu'on colle
dans un rapport, le XLSX un relevé qu'un auditeur trie et filtre lui-même.

**Aucune dépendance nouvelle.** Un .xlsx est une archive ZIP de documents XML,
et ce module l'écrit avec la seule bibliothèque standard, comme le dépôt le
fait déjà pour le multipart OData. La raison n'est pas l'économie : une
dépendance de rendu se serait invitée dans le wheel des bibliothèques, donc
chez tous les utilisateurs, pour un besoin qui reste périphérique.

**Le piège que ce module ferme, et c'est sa vraie raison d'être.** Excel
retype ce qu'il lit : un mandant ``000`` devient ``0``, une valeur ``1/2``
devient une date, un identifiant long part en notation scientifique. Appliqué
à un relevé SAP, cela corrompt silencieusement ce que la campagne a mesuré, et
la corruption se voit à l'ouverture, pas à l'écriture. Toutes les cellules
sont donc écrites en TEXTE explicite (chaînes en ligne + format ``@``), sans
option pour faire autrement : un relevé d'audit n'est pas un tableur de
calcul, et ce que l'écran a rendu doit rester ce que le fichier porte.

Le classeur est **déterministe** : dates d'archive figées, aucune propriété de
document horodatée, ordre des parties stable. Deux écritures de la même donnée
produisent le même fichier à l'octet près, ce dont dépend toute comparaison
entre deux passages.

Typé, importable comme bibliothèque Robot
(``Library    sapfx_common.table_xlsx``).
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Iterable, Mapping, Optional, Sequence

from sapfx_common._tabular import cell_text, header_labels
from sapfx_common._tabular import normalize_rows, table_columns
from sapfx_common._tabular import xml_escape
from sapfx_common._tabular import row_limit, unique_header
from sapfx_common._tabular_io import write_bytes

__all__ = [
    "MAX_CELL_CHARS",
    "MAX_SHEET_NAME",
    "column_letter",
    "normalize_sheet_name",
    "build_xlsx",
    "write_table_xlsx",
    "read_table_xlsx",
]

#: Le plafond d'Excel pour le contenu d'une cellule. Au-delà, le fichier
#: s'ouvre mais la cellule est rejetée : mieux vaut couper en l'annonçant.
MAX_CELL_CHARS = 32767

#: Le plafond d'Excel pour un nom de feuille.
MAX_SHEET_NAME = 31

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_DOC = "application/vnd.openxmlformats-officedocument.spreadsheetml"
#: Date d'archive figée (le plancher du format ZIP) : c'est elle qui rend deux
#: écritures de la même donnée identiques à l'octet près.
_FIXED_DATE = (1980, 1, 1, 0, 0, 0)
_HEADER_STYLE = 1
_TEXT_STYLE = 0


def column_letter(index: int) -> str:
    """La lettre de colonne Excel d'un index à base 0 (``0`` -> ``A``).

    Au-delà de 26 colonnes la notation devient ``AA`` : un relevé large n'est
    pas un cas d'école, une grille SAP en porte couramment plus de trente.
    """
    if index < 0:
        raise ValueError("Un index de colonne ne peut pas être négatif.")
    lettres = ""
    reste = int(index) + 1
    while reste:
        reste, position = divmod(reste - 1, 26)
        lettres = chr(ord("A") + position) + lettres
    return lettres


def normalize_sheet_name(name: Optional[str]) -> str:
    """Un nom de feuille acceptable pour Excel, dérivé de celui demandé.

    Excel refuse cinq caractères et les noms de plus de 31 caractères, et sa
    façon de refuser est un fichier réputé corrompu à l'ouverture : le message
    ne nomme évidemment pas la feuille. La normalisation est donc silencieuse
    et documentée plutôt que bloquante, sauf pour un nom vide.
    """
    brut = str(name or "").strip()
    if not brut:
        return "Relevé"
    for interdit in "[]:*?/\\":
        brut = brut.replace(interdit, "-")
    brut = brut.strip("'")
    return (brut[:MAX_SHEET_NAME] or "Relevé")


def _cell(reference: str, valeur: Any, style: int) -> str:
    texte, _ = cell_text(valeur, MAX_CELL_CHARS)
    if not texte:
        # Une cellule vide sans contenu reste stylée : la colonne garde son
        # format texte, y compris là où la valeur arrivera plus tard.
        return '<c r="%s" s="%d"/>' % (reference, style)
    return ('<c r="%s" s="%d" t="inlineStr"><is><t xml:space="preserve">'
            '%s</t></is></c>' % (reference, style, xml_escape(texte)))


def _sheet_xml(rows: Sequence[Mapping[str, Any]], colonnes: Sequence[str],
               freeze_header: bool, largeurs: Sequence[int],
               entetes: Sequence[str]) -> str:
    derniere = column_letter(len(colonnes) - 1) if colonnes else "A"
    total_lignes = len(rows) + 1
    parties = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="%s" xmlns:r="%s">' % (_NS, _NS_R),
               '<dimension ref="A1:%s%d"/>' % (derniere, total_lignes)]
    if freeze_header:
        parties.append(
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" '
            'topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>')
    else:
        parties.append('<sheetViews><sheetView workbookViewId="0"/>'
                       '</sheetViews>')
    if colonnes:
        cols = "".join(
            '<col min="%d" max="%d" width="%d" customWidth="1"/>'
            % (i + 1, i + 1, largeur) for i, largeur in enumerate(largeurs))
        parties.append("<cols>%s</cols>" % cols)
    parties.append("<sheetData>")
    entete = "".join(_cell("%s1" % column_letter(i), libelle, _HEADER_STYLE)
                     for i, libelle in enumerate(entetes))
    parties.append('<row r="1">%s</row>' % entete)
    for index, ligne in enumerate(rows, start=2):
        cellules = "".join(
            _cell("%s%d" % (column_letter(i), index), ligne.get(colonne),
                  _TEXT_STYLE)
            for i, colonne in enumerate(colonnes))
        parties.append('<row r="%d">%s</row>' % (index, cellules))
    parties.append("</sheetData>")
    if colonnes:
        # Le filtre automatique porte sur l'en-tête : c'est ce qui fait la
        # différence entre un fichier qu'on lit et un fichier qu'on exploite.
        parties.append('<autoFilter ref="A1:%s%d"/>' % (derniere,
                                                        total_lignes))
    parties.append("</worksheet>")
    return "".join(parties)


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="%s">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="@"/></numFmts>'
        '<fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FF0B4F8A"/>'
        '<name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid">'
        '<fgColor rgb="FFF2F4F7"/><bgColor indexed="64"/>'
        '</patternFill></fill>'
        '</fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/>'
        '<diagonal/></border></borders>'
        '<cellStyleXfs count="1">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        '</cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" '
        'applyNumberFormat="1"/>'
        '<xf numFmtId="164" fontId="1" fillId="2" borderId="0" xfId="0" '
        'applyNumberFormat="1" applyFont="1" applyFill="1"/>'
        '</cellXfs>'
        '<cellStyles count="1">'
        '<cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>' % _NS)


def _workbook_xml(sheet_name: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="%s" xmlns:r="%s"><sheets>'
            '<sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>'
            % (_NS, _NS_R, xml_escape(sheet_name)))


def _content_types_xml() -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="%s">'
            '<Default Extension="rels" ContentType="application/'
            'vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="%s.sheet.'
            'main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType='
            '"%s.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="%s.styles+xml"/>'
            '</Types>' % (_CT, _DOC, _DOC, _DOC))


def _package_parts(rows: Sequence[Mapping[str, Any]],
                   colonnes: Sequence[str], sheet_name: str,
                   freeze_header: bool, largeurs: Sequence[int],
                   entetes: Sequence[str]) -> list[tuple[str, str]]:
    return [
        ("[Content_Types].xml", _content_types_xml()),
        ("_rels/.rels",
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%s/'
         'officeDocument" Target="xl/workbook.xml"/></Relationships>'
         % (_NS_PKG, _NS_R)),
        ("xl/workbook.xml", _workbook_xml(sheet_name)),
        ("xl/_rels/workbook.xml.rels",
         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="%s">'
         '<Relationship Id="rId1" Type="%s/worksheet" '
         'Target="worksheets/sheet1.xml"/>'
         '<Relationship Id="rId2" Type="%s/styles" Target="styles.xml"/>'
         '</Relationships>' % (_NS_PKG, _NS_R, _NS_R)),
        ("xl/styles.xml", _styles_xml()),
        ("xl/worksheets/sheet1.xml",
         _sheet_xml(rows, colonnes, freeze_header, largeurs, entetes)),
    ]


def _widths(rows: Sequence[Mapping[str, Any]], colonnes: Sequence[str],
            entetes: Sequence[str]) -> list[int]:
    """Largeur de colonne en caractères, bornée à ce qu'Excel accepte."""
    largeurs = []
    for colonne, entete in zip(colonnes, entetes, strict=True):
        plus_long = len(str(entete))
        for ligne in rows:
            plus_long = max(plus_long, len(cell_text(ligne.get(colonne))[0]))
        largeurs.append(max(8, min(120, plus_long + 2)))
    return largeurs


def build_xlsx(rows: Iterable[Mapping[str, Any]],
               columns: Optional[Sequence[str]] = None,
               sheet_name: str = "Relevé",
               headers: Optional[Mapping[str, Any]] = None,
               freeze_header: bool = True) -> bytes:
    """Construit le classeur EN MÉMOIRE et rend ses octets.

    Séparé de l'écriture pour que la construction reste testable sans toucher
    au disque, et pour qu'un appelant puisse remettre les octets ailleurs
    (une pièce jointe, un artefact) sans passer par un fichier temporaire.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    feuille = normalize_sheet_name(sheet_name)
    entetes = header_labels(colonnes, headers)
    largeurs = _widths(lignes, colonnes, entetes)
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in _package_parts(lignes, colonnes, feuille,
                                           freeze_header, largeurs, entetes):
            info = zipfile.ZipInfo(nom, date_time=_FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, contenu.encode("utf-8"))
    return tampon.getvalue()


def write_table_xlsx(path: str, rows: Iterable[Mapping[str, Any]],
                     columns: Optional[Sequence[str]] = None,
                     sheet_name: str = "Relevé",
                     headers: Optional[Mapping[str, Any]] = None,
                     max_rows: Optional[int] = None,
                     freeze_header: bool = True) -> dict[str, Any]:
    """Écrit le relevé en classeur Excel et rend un verdict JSON-safe.

    Le verdict porte ``{path, rows, total_rows, columns, sheet, truncated_rows,
    oversized_cells, bytes}`` : un appelant ASSERTE ce qui a été écrit au lieu
    de faire confiance au fichier. ``truncated_rows`` dit si le classeur est
    incomplet, et ``oversized_cells`` compte les cellules qu'Excel n'aurait pas
    acceptées entières, coupées ici plutôt que perdues à l'ouverture.

    Toutes les cellules sont du TEXTE : voir l'en-tête du module, c'est un
    choix et non une limite.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    total = len(lignes)
    borne = row_limit(max_rows)
    if borne is not None and borne >= 0:
        lignes = lignes[:borne]
    trop_longues = sum(1 for ligne in lignes for colonne in colonnes
                       if cell_text(ligne.get(colonne), MAX_CELL_CHARS)[1])
    octets = build_xlsx(lignes, colonnes, sheet_name=sheet_name,
                        headers=headers, freeze_header=freeze_header)
    cible = write_bytes(path, octets)
    return {
        "path": cible,
        "rows": len(lignes),
        "total_rows": total,
        "columns": list(colonnes),
        "headers": header_labels(colonnes, headers),
        "sheet": normalize_sheet_name(sheet_name),
        "truncated_rows": len(lignes) < total,
        "oversized_cells": trop_longues,
        "bytes": len(octets),
    }


def _cell_position(reference: str) -> int:
    """L'index de colonne (base 0) d'une référence ``B7``.

    Une cellule VIDE n'est pas écrite par tous les producteurs : sans lire la
    référence, une ligne à trous décalerait toutes ses valeurs d'une colonne,
    et le relevé relu serait faux tout en restant plausible.
    """
    lettres = "".join(c for c in str(reference) if c.isalpha()).upper()
    index = 0
    for caractere in lettres:
        index = index * 26 + (ord(caractere) - ord("A") + 1)
    return max(0, index - 1)


def read_table_xlsx(path: str) -> list[dict[str, Any]]:
    """Relit un classeur et rend son relevé, en-tête en clés.

    Le pendant de :func:`write_table_xlsx`, sur le patron des artefacts JSON
    du dépôt : ce qui a été écrit doit pouvoir être CONFRONTÉ au relevé
    d'origine, sinon la seule preuve qu'un fichier est correct est qu'il
    existe.

    Lit les chaînes en ligne (ce que ce module écrit), la table de chaînes
    partagées (ce qu'Excel écrit en réenregistrant le fichier) et les valeurs
    brutes. Tout est rendu en texte : une comparaison avec un relevé d'écran
    se fait entre chaînes, et retyper à la lecture réintroduirait exactement le
    piège que l'écriture ferme.
    """
    with zipfile.ZipFile(str(path)) as archive:
        partagees: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            racine = _parse(archive.read("xl/sharedStrings.xml"))
            partagees = ["".join(n.text or "" for n in item.iter()
                                 if n.tag.endswith("}t"))
                         for item in racine if item.tag.endswith("}si")]
        feuille = _parse(archive.read("xl/worksheets/sheet1.xml"))
    donnees = [n for n in feuille if n.tag.endswith("}sheetData")]
    lignes: list[list[str]] = []
    for row in (donnees[0] if donnees else []):
        cellules: dict[int, str] = {}
        for cellule in row:
            index = _cell_position(cellule.get("r", "A1"))
            cellules[index] = _cell_value(cellule, partagees)
        largeur = max(cellules) + 1 if cellules else 0
        lignes.append([cellules.get(i, "") for i in range(largeur)])
    if not lignes:
        return []
    entete = list(lignes[0])
    unique_header(entete, "Classeur %s" % path)
    return [{entete[i]: (ligne[i] if i < len(ligne) else "")
             for i in range(len(entete))} for ligne in lignes[1:]]


def _parse(octets: bytes) -> ET.Element:
    return ET.fromstring(octets)


def _cell_value(cellule: ET.Element, partagees: Sequence[str]) -> str:
    type_cellule = cellule.get("t")
    if type_cellule == "inlineStr":
        return "".join(n.text or "" for n in cellule.iter()
                       if n.tag.endswith("}t"))
    brut = "".join(n.text or "" for n in cellule if n.tag.endswith("}v"))
    if type_cellule == "s" and brut.isdigit():
        position = int(brut)
        return partagees[position] if position < len(partagees) else ""
    return brut
