"""Écriture d'un relevé tabulaire en **JSON** et en **JSON Lines**, pure.

Le format des trois précédents qui vise une MACHINE. Le SVG se regarde, le
classeur se trie, le CSV se charge tant bien que mal ; celui-ci se lit par un
script Python ou R et par les outils décisionnels, sans convention à deviner.

**Pourquoi deux formes.** Le tableau JSON (``[{...}, {...}]``) est celui qu'on
ouvre, qu'on relit et qu'on compare. Le JSON Lines (un objet par ligne) est
celui des gros volumes : il se lit en flux sans charger le fichier entier, se
concatène, se découpe, et c'est ce que lisent nativement ``pandas``
(``read_json(lines=True)``), DuckDB, Spark et la plupart des chaînes
décisionnelles. Un relevé de paramètres tient en mémoire ; l'inventaire d'un
système, non, et c'est le cas que cette forme couvre.

**Trois propriétés délibérées.**

1. **Tout est du texte**, comme dans les autres formats. Deviner des types
   ferait de ``000`` un zéro et de ``0012`` un douze, or ce sont des valeurs
   SAP : un mandant, un identifiant. Le consommateur retype s'il le veut, en
   sachant ce qu'il fait.
2. **L'ordre des colonnes est PRÉSERVÉ** dans chaque objet, ce qui n'est pas
   gratuit : un dictionnaire JSON n'a pas d'ordre garanti par la norme, mais
   les lecteurs le respectent, et un relevé relu doit ressembler à l'écran
   dont il vient. L'en-tête est aussi rendu à part par le verdict.
3. **Le fichier est déterministe** : indentation fixe, aucune date injectée,
   fins de ligne LF. Deux extractions de la même donnée produisent le même
   fichier, donc un écart entre deux fichiers signale un écart du SYSTÈME.

Typé, sans dépendance : importable comme bibliothèque Robot
(``Library    sapfx_common.table_json``).
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional, Sequence

from sapfx_common._tabular import cell_text, header_labels
from sapfx_common._tabular import normalize_rows, table_columns
from sapfx_common._tabular import row_limit
from sapfx_common._tabular_io import write_text
from sapfx_common.robot_args import as_optional_int

__all__ = [
    "table_records",
    "render_table_json",
    "write_table_json",
    "read_table_json",
]


def table_records(rows: Iterable[Mapping[str, Any]],
                  columns: Optional[Sequence[str]] = None,
                  max_rows: Optional[int] = None,
                  headers: Optional[Mapping[str, Any]] = None
                  ) -> list[dict[str, str]]:
    """Le relevé réduit aux colonnes voulues, toutes valeurs en texte.

    La brique commune aux deux formes : ce qui part dans le fichier est ce que
    cette fonction rend, donc un appelant peut l'ASSERTER avant écriture.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    borne = row_limit(max_rows)
    retenues = lignes if borne is None else lignes[:borne]
    # `require_unique` : ici l'en-tête devient une CLÉ, donc deux colonnes au
    # même libellé en feraient disparaître une d'un fichier d'apparence
    # complète. Le refus est préférable au silence.
    cles = header_labels(colonnes, headers, require_unique=True)
    return [{cle: cell_text(ligne.get(colonne))[0]
             for colonne, cle in zip(colonnes, cles, strict=True)}
            for ligne in retenues]


def render_table_json(rows: Iterable[Mapping[str, Any]],
                      columns: Optional[Sequence[str]] = None,
                      max_rows: Optional[int] = None,
                      headers: Optional[Mapping[str, Any]] = None,
                      lines: bool = False, indent: int = 2) -> str:
    """Rend le relevé en texte JSON.

    ``lines=True`` produit du JSON Lines (un objet compact par ligne), la
    forme des gros volumes et des lectures en flux ; sinon un tableau indenté,
    la forme qu'on ouvre et qu'on relit.
    """
    fiches = table_records(rows, columns, max_rows, headers)
    if lines:
        return "".join(
            json.dumps(fiche, ensure_ascii=False, separators=(",", ":")) + "\n"
            for fiche in fiches)
    profondeur = as_optional_int(indent, "indent")
    return json.dumps(fiches, ensure_ascii=False,
                      indent=profondeur if profondeur else None) + "\n"


def write_table_json(path: str, rows: Iterable[Mapping[str, Any]],
                     columns: Optional[Sequence[str]] = None,
                     max_rows: Optional[int] = None,
                     headers: Optional[Mapping[str, Any]] = None,
                     lines: bool = False, indent: int = 2) -> dict[str, Any]:
    """Écrit le relevé en JSON (ou JSON Lines) et rend un verdict JSON-safe.

    Le verdict porte ``{path, rows, total_rows, columns, format,
    truncated_rows, bytes}``. ``format`` vaut ``json`` ou ``jsonl`` : le
    consommateur n'a pas à deviner d'après l'extension, et deux chaînes
    d'outils différentes n'attendent pas la même chose.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    document = render_table_json(lignes, columns=colonnes, max_rows=max_rows,
                                 headers=headers, lines=lines, indent=indent)
    borne = row_limit(max_rows)
    rendues = (len(lignes) if borne is None
               else min(len(lignes), borne))
    cible = write_text(path, document, encoding="utf-8", newline="\n")
    return {
        "path": cible,
        "rows": rendues,
        "total_rows": len(lignes),
        "columns": list(colonnes),
        "headers": header_labels(colonnes, headers, require_unique=True),
        "format": "jsonl" if lines else "json",
        "truncated_rows": rendues < len(lignes),
        "bytes": len(document.encode("utf-8")),
    }


def read_table_json(path: str) -> list[dict[str, Any]]:
    """Relit un JSON ou un JSON Lines et rend son relevé.

    La forme est DÉDUITE du contenu et non de l'extension : un fichier reçu
    porte souvent ``.json`` en étant du JSON Lines, et supposer la mauvaise
    forme échoue sur une erreur de syntaxe qui accuse la donnée alors que
    c'est la lecture qui se trompe.

    La lecture se fait en ``utf-8-sig`` : un fichier réenregistré sous Windows
    porte volontiers une marque d'ordre d'octets, et une lecture stricte
    échouerait sur son propre décodage plutôt que sur le contenu, leçon déjà
    payée par la sentinelle de posture de sécurité.
    """
    with open(str(path), "r", encoding="utf-8-sig") as flux:
        contenu = flux.read()
    if not contenu.strip():
        return []
    if contenu.lstrip().startswith("["):
        charge = json.loads(contenu)
        return [dict(fiche) for fiche in charge]
    return [dict(json.loads(ligne)) for ligne in contenu.splitlines()
            if ligne.strip()]
