"""Écriture d'un relevé tabulaire en **Parquet**, canal OPTIONNEL.

Le format colonnaire des gros volumes : compressé, typé, lu nativement par
pandas, R (``arrow``), DuckDB, Spark et les outils décisionnels. C'est le bon
format quand le relevé n'est plus un tableau qu'on regarde mais une table
qu'on interroge.

**Pourquoi il est optionnel, et pourquoi c'est assumé.** Parquet n'est pas un
format qu'on écrit à la main : ses métadonnées sont du Thrift binaire, et un
écrivain maison non confronté à un vrai lecteur produirait des fichiers
plausibles que rien ne relirait. Les trois autres formats de restitution du
dépôt sont en bibliothèque standard précisément parce qu'ils le PEUVENT ;
celui-ci délègue à ``pyarrow``, qui n'entre pas dans les dépendances des
bibliothèques (extra ``parquet``). C'est le même arbitrage que ``pyrfc`` pour
le canal RFC et ``Pillow`` pour les assertions visuelles : une capacité réelle,
absente par défaut, qui se DÉCLARE indisponible au lieu d'échouer obscurément.

**Ce que ce module ajoute au simple appel de pyarrow**, et c'est sa raison
d'être : le même contrat de colonnes que les trois autres formats, le même
verdict JSON-safe, un statut qu'on peut sonder AVANT d'écrire (sur le patron
de :mod:`sapfx_common.rfc_channel`), et surtout le typage IMPOSÉ en chaîne.
Laissé libre, un écrivain Parquet infère les types, et l'inférence transforme
un mandant ``000`` en entier ``0`` et une valeur ``1.10`` en flottant : c'est
la corruption silencieuse que les trois autres formats refusent déjà, et elle
serait ici irréversible puisque le fichier porterait le type.

Typé : importable comme bibliothèque Robot
(``Library    sapfx_common.table_parquet``).
"""
from __future__ import annotations

import importlib.util
from typing import Any, Iterable, Mapping, Optional, Sequence

from sapfx_common._tabular import cell_text, header_labels
from sapfx_common._tabular import normalize_rows, table_columns
from sapfx_common._tabular import row_limit
from sapfx_common._tabular_io import locked_target, prepare_target

__all__ = [
    "PARQUET_EXTRA_HINT",
    "parquet_channel_status",
    "parquet_is_available",
    "write_table_parquet",
    "read_table_parquet",
]

PARQUET_EXTRA_HINT = (
    "Installer le binding : `pip install pyarrow` (ou l'extra "
    "`robotframework-sapfx[parquet]`). Les trois autres formats de "
    "restitution (CSV, JSON/JSON Lines, XLSX) n'ont AUCUNE dépendance et "
    "couvrent la même donnée : JSON Lines est la solution de repli pour une "
    "chaîne décisionnelle.")


def parquet_channel_status() -> dict[str, Any]:
    """Dit si le canal Parquet est utilisable, et sinon POURQUOI.

    Rend ``{available, reason, remedy, version}``. Sonder plutôt que tenter
    permet à une suite de se SAUTER proprement au lieu de rougir là où rien
    n'est cassé, exactement comme le canal RFC : un format optionnel absent
    n'est pas un défaut du système testé.
    """
    if importlib.util.find_spec("pyarrow") is None:
        return {
            "available": False,
            "reason": "binding_absent",
            "remedy": PARQUET_EXTRA_HINT,
            "version": None,
        }
    try:
        import pyarrow  # noqa: F401
        import pyarrow.parquet  # noqa: F401
    except Exception as cause:  # pragma: no cover - dépend du poste
        # Un paquet présent mais inutilisable (installation partielle,
        # bibliothèque native manquante) : la distinction compte, les deux
        # remèdes ne sont pas les mêmes, leçon du binding pyrfc qui avalait
        # son propre échec de chargement natif.
        return {
            "available": False,
            "reason": "binding_broken",
            "remedy": "pyarrow est installé mais ne se charge pas (%s). %s"
                      % (cause, PARQUET_EXTRA_HINT),
            "version": None,
        }
    import pyarrow

    return {
        "available": True,
        "reason": "",
        "remedy": "",
        "version": str(pyarrow.__version__),
    }


def parquet_is_available() -> bool:
    """Le prédicat, pour une garde de suite. N'échoue jamais."""
    return bool(parquet_channel_status()["available"])


def _require_parquet() -> Any:
    statut = parquet_channel_status()
    if not statut["available"]:
        raise RuntimeError(
            "Canal Parquet indisponible (%s). %s"
            % (statut["reason"], statut["remedy"]))
    import pyarrow.parquet as pq

    return pq


def write_table_parquet(path: str, rows: Iterable[Mapping[str, Any]],
                        columns: Optional[Sequence[str]] = None,
                        headers: Optional[Mapping[str, Any]] = None,
                        max_rows: Optional[int] = None,
                        compression: str = "snappy") -> dict[str, Any]:
    """Écrit le relevé en Parquet et rend un verdict JSON-safe.

    Toutes les colonnes sont de type chaîne, imposé et non inféré : voir
    l'en-tête du module, c'est ce qui empêche le fichier de porter un type
    faux pour toujours.

    Le verdict porte ``{path, rows, total_rows, columns, compression,
    truncated_rows, bytes, writer}``. ``writer`` nomme la version qui a écrit :
    un fichier illisible ailleurs se diagnostique d'abord par là.
    """
    pq = _require_parquet()
    import pyarrow as pa

    lignes = normalize_rows(rows)
    colonnes = table_columns(lignes, columns)
    borne = row_limit(max_rows)
    retenues = lignes if borne is None else lignes[:borne]
    # Comme pour le JSON, un nom de colonne est ici une CLÉ : deux libellés
    # identiques feraient disparaître une colonne du fichier.
    cles = header_labels(colonnes, headers, require_unique=True)
    donnees = {cle: [cell_text(ligne.get(colonne))[0] for ligne in retenues]
               for colonne, cle in zip(colonnes, cles, strict=True)}
    table = pa.table(donnees, schema=pa.schema(
        [(cle, pa.string()) for cle in cles]))
    cible = prepare_target(path)
    try:
        pq.write_table(table, cible, compression=str(compression or "none"))
    except PermissionError as cause:
        # Le même message que les quatre autres formats : sous Windows un
        # fichier ouvert dans un tableur est verrouillé, et le refus nu envoie
        # chercher un problème de droits qui n'existe pas.
        raise locked_target(cible, cause) from None
    import os

    return {
        "path": cible,
        "rows": len(retenues),
        "total_rows": len(lignes),
        "columns": list(colonnes),
        "headers": header_labels(colonnes, headers, require_unique=True),
        "compression": str(compression or "none"),
        "truncated_rows": len(retenues) < len(lignes),
        "bytes": os.path.getsize(cible),
        "writer": "pyarrow %s" % parquet_channel_status()["version"],
    }


def read_table_parquet(path: str) -> list[dict[str, Any]]:
    """Relit un Parquet et rend son relevé, pour confronter l'écrit à
    l'origine comme pour les autres formats.

    Les valeurs reviennent en texte : le fichier a été écrit en chaînes, et
    rendre autre chose ici masquerait une écriture qui aurait, elle, dérivé.
    """
    pq = _require_parquet()
    table = pq.read_table(str(path))
    fiches = table.to_pylist()
    return [{cle: ("" if valeur is None else str(valeur))
             for cle, valeur in fiche.items()} for fiche in fiches]
