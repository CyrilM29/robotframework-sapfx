"""Écriture d'un relevé tabulaire en **CSV**, logique pure.

Troisième format de restitution à côté de :mod:`sapfx_common.table_svg` (une
preuve qu'on colle dans un rapport) et :mod:`sapfx_common.table_xlsx` (un
relevé qu'on trie). Le CSV est celui qu'une autre chaîne d'outils consomme :
un script, un tableur, un moteur d'analyse.

Il passe pour le format trivial des trois. Il est le seul à porter quatre
pièges dont chacun produit un fichier parfaitement lisible et faux.

1. **L'encodage.** Un CSV en UTF-8 sans marque d'ordre d'octets est ouvert en
   codage local par Excel, qui massacre alors tout accent. La marque est donc
   écrite par défaut (``utf-8-sig``) : les lecteurs standard la gèrent, et
   c'est le seul réglage qui ne casse rien nulle part. Le dépôt a déjà payé
   ce piège dans l'autre sens, une référence de sentinelle éditée sous Windows
   ayant fait rougir une lecture stricte sur son propre décodage.
2. **Le séparateur.** Le défaut est la virgule, qui est la norme (RFC 4180) et
   ce que lisent les outils. Un Excel configuré en français attend le
   point-virgule et rend sinon une colonne unique : ``delimiter=;`` est là
   pour ce cas, et c'est un choix d'usage, pas une correction.
3. **L'injection de formule.** Une valeur qui commence par ``=``, ``+``, ``-``
   ou ``@`` est interprétée comme une FORMULE à l'ouverture. C'est un vecteur
   d'exécution connu, et un relevé de paramètres SAP en porte réellement (une
   valeur négative commence par un tiret). Ce module ne neutralise RIEN par
   défaut, parce qu'altérer une valeur en silence est exactement ce que les
   trois formats refusent ; il COMPTE les cellules concernées dans son verdict
   et n'agit que si ``neutralize_formulas`` le demande, auquel cas le verdict
   dit combien de valeurs ont été préfixées.
4. **Les fins de ligne.** Fixées à CRLF (RFC 4180), donc identiques quelle que
   soit la plateforme : deux écritures de la même donnée produisent le même
   fichier, comme pour les deux autres formats.

Typé, sans dépendance : importable comme bibliothèque Robot
(``Library    sapfx_common.table_csv``).
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable, Mapping, Optional, Sequence

from sapfx_common._tabular import cell_text, header_labels
from sapfx_common._tabular import normalize_rows, table_columns
from sapfx_common._tabular import row_limit, unique_header
from sapfx_common._tabular_io import write_text

__all__ = [
    "FORMULA_PREFIXES",
    "looks_like_formula",
    "formula_risk_cells",
    "render_table_csv",
    "write_table_csv",
    "read_table_csv",
]

#: Les amorces qu'un tableur interprète comme une formule. Le tiret en fait
#: partie, ce qui rend le sujet concret : une valeur négative est un cas
#: ordinaire d'un relevé de paramètres, pas une curiosité.
FORMULA_PREFIXES = ("=", "+", "-", "@")

_LINE_TERMINATOR = "\r\n"


def looks_like_formula(value: Any) -> bool:
    """Dit si une valeur serait interprétée comme une formule à l'ouverture.

    Le critère est le premier caractère, tabulation et retour chariot de tête
    compris, car un tableur les ignore avant de décider.
    """
    texte = ("" if value is None else str(value)).lstrip("\t\r\n ")
    return texte.startswith(FORMULA_PREFIXES)


def formula_risk_cells(rows: Iterable[Mapping[str, Any]],
                       columns: Optional[Sequence[str]] = None) -> int:
    """Combien de cellules du relevé seraient lues comme des formules.

    Rendre ce compte sans rien changer est le coeur du contrat : l'appelant
    apprend le risque et décide, là où une neutralisation par défaut aurait
    modifié la donnée mesurée sans le dire.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    return sum(1 for ligne in lignes for colonne in colonnes
               if looks_like_formula(ligne.get(colonne)))


def _neutralize(texte: str) -> str:
    """Préfixe une apostrophe, la convention que les tableurs comprennent."""
    return "'" + texte if looks_like_formula(texte) else texte


def render_table_csv(rows: Iterable[Mapping[str, Any]],
                     columns: Optional[Sequence[str]] = None,
                     delimiter: str = ",",
                     headers: Optional[Mapping[str, Any]] = None,
                     max_rows: Optional[int] = None,
                     neutralize_formulas: bool = False) -> str:
    """Rend le relevé en texte CSV.

    L'en-tête porte les colonnes, dans l'ordre demandé. Les valeurs sont
    écrites telles quelles, guillemets posés par le module standard là où le
    délimiteur, un guillemet ou un espace l'exigent.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    borne = row_limit(max_rows)
    if borne is not None:
        lignes = lignes[:borne]
    separateur = str(delimiter or ",")
    if len(separateur) != 1:
        raise ValueError(
            "Le séparateur doit être UN caractère, reçu %r. Le point-virgule "
            "est l'usage d'un Excel configuré en français, la virgule la "
            "norme RFC 4180." % separateur)
    tampon = io.StringIO()
    graveur = csv.writer(tampon, delimiter=separateur,
                         lineterminator=_LINE_TERMINATOR,
                         quoting=csv.QUOTE_MINIMAL)
    graveur.writerow(header_labels(colonnes, headers))
    for ligne in lignes:
        valeurs = [cell_text(ligne.get(colonne))[0] for colonne in colonnes]
        if neutralize_formulas:
            valeurs = [_neutralize(v) for v in valeurs]
        graveur.writerow(valeurs)
    return tampon.getvalue()


def write_table_csv(path: str, rows: Iterable[Mapping[str, Any]],
                    columns: Optional[Sequence[str]] = None,
                    delimiter: str = ",",
                    headers: Optional[Mapping[str, Any]] = None,
                    max_rows: Optional[int] = None,
                    neutralize_formulas: bool = False,
                    byte_order_mark: bool = True) -> dict[str, Any]:
    """Écrit le relevé en CSV et rend un verdict JSON-safe.

    Le verdict porte ``{path, rows, total_rows, columns, delimiter, encoding,
    truncated_rows, formula_cells, neutralized_cells, bytes}``. ``formula_cells``
    est le compte des valeurs qu'un tableur lirait comme des formules, RENDU
    même quand rien n'est neutralisé : c'est ce qui permet à un appelant de
    décider en connaissance de cause plutôt que de l'ignorer.

    ``byte_order_mark`` écrit la marque d'ordre d'octets UTF-8 (défaut), sans
    laquelle Excel rend les accents en codage local. La retirer donne un
    fichier UTF-8 nu, plus propre pour une chaîne d'outils qui sait déjà quoi
    lire.
    """
    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    total = len(lignes)
    borne = row_limit(max_rows)
    retenues = lignes if borne is None else lignes[:borne]
    a_risque = formula_risk_cells(retenues, colonnes)
    document = render_table_csv(retenues, columns=colonnes,
                                delimiter=delimiter, headers=headers,
                                neutralize_formulas=neutralize_formulas)
    encodage = "utf-8-sig" if byte_order_mark else "utf-8"
    cible = write_text(path, document, encoding=encodage, newline="")
    return {
        "path": cible,
        "rows": len(retenues),
        "total_rows": total,
        "columns": list(colonnes),
        "headers": header_labels(colonnes, headers),
        "delimiter": str(delimiter or ","),
        "encoding": encodage,
        "truncated_rows": len(retenues) < total,
        "formula_cells": a_risque,
        "neutralized_cells": a_risque if neutralize_formulas else 0,
        "bytes": len(document.encode(encodage)),
    }


def read_table_csv(path: str, delimiter: Optional[str] = None
                   ) -> list[dict[str, Any]]:
    """Relit un CSV et rend son relevé, en-tête en clés.

    Le pendant de :func:`write_table_csv`, pour que l'écrit soit CONFRONTÉ au
    relevé d'origine : un fichier qui existe n'est pas un fichier juste.

    La lecture se fait en ``utf-8-sig``, qui accepte le fichier avec ET sans
    marque d'ordre d'octets ; sans cela, une marque laissée en tête collerait
    à la première colonne et le nom de celle-ci ne correspondrait plus à rien,
    échec d'autant plus désagréable qu'il est invisible à l'oeil.

    Sans ``delimiter``, le séparateur est DÉDUIT de la ligne d'en-tête : un
    CSV reçu ne dit pas lequel il emploie, et supposer la virgule rend une
    unique colonne dont le nom est toute la ligne.
    """
    with open(str(path), "r", encoding="utf-8-sig", newline="") as flux:
        contenu = flux.read()
    if not contenu.strip():
        return []
    separateur = str(delimiter) if delimiter else _sniff_delimiter(contenu)
    lecteur = csv.reader(io.StringIO(contenu), delimiter=separateur)
    lignes = [ligne for ligne in lecteur]
    if not lignes:
        return []
    entete = lignes[0]
    unique_header(entete, "CSV %s" % path)
    return [{entete[i]: (ligne[i] if i < len(ligne) else "")
             for i in range(len(entete))} for ligne in lignes[1:]]


def _sniff_delimiter(contenu: str) -> str:
    """Le séparateur le plus présent dans la ligne d'en-tête.

    Volontairement grossier et borné aux trois séparateurs répandus : une
    déduction élaborée se tromperait sur des données, là où l'en-tête d'un
    relevé ne porte que des noms de colonnes.
    """
    premiere = contenu.splitlines()[0] if contenu.splitlines() else ""
    comptes = {sep: premiere.count(sep) for sep in (",", ";", "\t")}
    meilleur = max(comptes, key=lambda sep: comptes[sep])
    return meilleur if comptes[meilleur] else ","
