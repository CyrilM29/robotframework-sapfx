"""Lectures de PREUVES d'exploitation par le canal RFC, logique pure.

Le socle des quatre keywords « la famille que `Read Rfc Table` débloque »
(backlog 2.2) : documents de modification (CDHDR/CDPOS, l'assertion d'audit),
statuts d'IDoc (EDIDC/EDIDS), journaux applicatifs (BALHDR) et journal d'un
job de fond (chaîne XBP). Ici : construction de clauses, fusion des deux
projections CDPOS, barèmes de classification et normalisation JSON-safe.
Aucun réseau, aucun import `pyrfc` : le pilotage vit dans ``SapApiLibrary``.

Deux contraintes du canal, mesurées live (A4H, 2026-08-29) et encodées ici :

* **le tampon de RFC_READ_TABLE fait 512 octets par ligne** : une projection
  CDPOS portant ``VALUE_NEW`` ET ``VALUE_OLD`` (254 caractères chacun) sort
  en ``DATA_BUFFER_EXCEEDED`` (AD/E/559). D'où les DEUX projections (l'une
  avec la valeur nouvelle, l'autre avec l'ancienne) fusionnées sur la clé ;
* **un statut non cartographié n'est jamais un succès** : le barème IDoc
  suit le patron de ``rfc_tables.job_wait_verdict`` (catégorie ``unmapped``,
  le repli sûr).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from sapfx_common.rfc_tables import abap_quote

#: Clé d'une ligne CDPOS à l'intérieur d'un couple (classe, objet) : c'est
#: sur elle que les deux projections se recollent.
CHANGE_ITEM_KEY = ("CHANGENR", "TABNAME", "TABKEY", "FNAME", "CHNGIND")

#: Barème des statuts d'IDoc standard, par catégorie. Volontairement
#: restreint aux statuts documentés stables ; tout le reste est ``unmapped``
#: et ne devient JAMAIS un succès (le repli sûr, patron des jobs de fond).
IDOC_STATUS_CATEGORIES = {
    "success": ("03", "12", "16", "41", "53"),
    "error": ("02", "04", "05", "07", "11", "17", "23", "25", "26", "29",
              "34", "36", "37", "40", "51", "54", "56", "60", "61", "63",
              "65", "68"),
    "in_progress": ("01", "30", "31", "32", "33", "42", "50", "52", "62",
                    "64", "66", "69", "70", "71", "73", "75"),
}

#: Compteurs par sévérité de BALHDR (NUMC zéro-paddés, ``"000004"``), et le
#: nom parlant de chacun dans les totaux.
LOG_COUNTER_FIELDS = {
    "MSG_CNT_AL": "total", "MSG_CNT_A": "abort", "MSG_CNT_E": "error",
    "MSG_CNT_W": "warning", "MSG_CNT_I": "info", "MSG_CNT_S": "success",
}


def normalize_date(value: Any, argument: str) -> str:
    """Une date au format ABAP ``YYYYMMDD`` depuis ``YYYYMMDD`` ou
    ``YYYY-MM-DD`` ; toute autre forme échoue en nommant l'argument."""
    text = str(value).strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(
            "L'argument %s doit être une date YYYYMMDD ou YYYY-MM-DD, reçu %r."
            % (argument, value))
    return text


def build_options(pairs: Iterable[tuple[str, Any]]) -> list[str]:
    """Clauses ``OPTIONS`` de RFC_READ_TABLE depuis des couples
    (champ, valeur) : une clause ``EQ`` par couple, les suivantes préfixées
    ``AND``, valeurs citées façon ABAP. Les valeurs ``None`` sont ignorées
    (critère non fourni)."""
    clauses: list[str] = []
    for field, value in pairs:
        if value is None:
            continue
        clause = "%s EQ %s" % (field, abap_quote(str(value)))
        clauses.append(clause if not clauses else "AND " + clause)
    return clauses


def append_clause(clauses: list[str], clause: str) -> list[str]:
    """Ajoute une clause déjà écrite (comparateur libre : ``GE``, ``GT``…) en
    la préfixant ``AND`` si elle n'ouvre pas l'expression."""
    clauses.append(clause if not clauses else "AND " + clause)
    return clauses


def merge_change_items(new_rows: Iterable[Mapping[str, str]],
                       old_rows: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    """Fusionne les DEUX projections CDPOS (valeur nouvelle, valeur ancienne)
    sur la clé de poste : le contournement du tampon de 512 octets de
    RFC_READ_TABLE. Une ligne présente d'un seul côté garde l'autre valeur
    vide plutôt que de disparaître."""
    def key(row: Mapping[str, str]) -> tuple[str, ...]:
        return tuple(str(row.get(name, "")) for name in CHANGE_ITEM_KEY)

    olds = {key(row): str(row.get("VALUE_OLD", "")) for row in old_rows}
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for row in new_rows:
        k = key(row)
        seen.add(k)
        item = {name: str(row.get(name, "")) for name in CHANGE_ITEM_KEY}
        item["VALUE_NEW"] = str(row.get("VALUE_NEW", ""))
        item["VALUE_OLD"] = olds.get(k, "")
        merged.append(item)
    for k, value_old in olds.items():
        if k not in seen:
            item = dict(zip(CHANGE_ITEM_KEY, k, strict=True))
            item["VALUE_NEW"] = ""
            item["VALUE_OLD"] = value_old
            merged.append(item)
    return merged


def attach_change_items(headers: Iterable[Mapping[str, str]],
                        items: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    """Accroche à chaque en-tête CDHDR ses postes CDPOS (clé ``CHANGENR``).
    Les postes d'un numéro de modification absent des en-têtes (filtrés par
    date ou par plafond côté en-têtes) sont laissés de côté : la jointure se
    fait côté Python, jamais en devinant côté serveur."""
    grouped: dict[str, list[dict[str, str]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("CHANGENR", "")), []).append(dict(item))
    documents: list[dict[str, Any]] = []
    for header in headers:
        document: dict[str, Any] = dict(header)
        document["items"] = grouped.get(str(header.get("CHANGENR", "")), [])
        documents.append(document)
    return documents


def classify_idoc_status(status: Any) -> str:
    """Catégorie d'un statut d'IDoc : ``success`` / ``error`` /
    ``in_progress`` / ``unmapped``. Le statut est un CODE numérique stable
    (convention n°3 : jamais le texte localisé de TEDS1), et un statut
    inconnu du barème reste ``unmapped``, jamais un succès."""
    code = str(status).strip().zfill(2) if str(status).strip() else ""
    for category, codes in IDOC_STATUS_CATEGORIES.items():
        if code in codes:
            return category
    return "unmapped"


def summarize_idoc_statuses(rows: Iterable[Mapping[str, str]]) -> dict[str, int]:
    """Décompte des IDocs par catégorie de statut (catégories toujours toutes
    présentes, à zéro s'il le faut : un décompte absent ne se distingue pas
    d'un zéro chez le lecteur)."""
    counts = {name: 0 for name in (*IDOC_STATUS_CATEGORIES, "unmapped")}
    for row in rows:
        counts[classify_idoc_status(row.get("STATUS", ""))] += 1
    return counts


def normalize_log_header(row: Mapping[str, str]) -> dict[str, Any]:
    """Un en-tête BALHDR aux compteurs convertis en entiers (les NUMC
    ``"000004"`` deviennent ``4``), sous leurs noms parlants ; les autres
    champs traversent en chaînes."""
    header: dict[str, Any] = {}
    for name, value in row.items():
        label = LOG_COUNTER_FIELDS.get(str(name))
        if label is not None:
            text = str(value).strip()
            header[label] = int(text) if text.isdigit() else 0
        else:
            header[str(name)] = str(value)
    return header


def summarize_log_headers(headers: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Totaux par sévérité d'une liste d'en-têtes déjà normalisés par
    `normalize_log_header` : la matière de l'assertion locale-safe (des
    COMPTES par type, jamais des textes, que BALDAT garde compressés)."""
    totals = {label: 0 for label in LOG_COUNTER_FIELDS.values()}
    for header in headers:
        for label in totals:
            value = header.get(label, 0)
            totals[label] += int(value) if str(value).strip().isdigit() else 0
    return totals


def normalize_job_log_lines(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Lignes du journal d'un job (table ``JOB_PROTOCOL`` de la chaîne XBP)
    ramenées à des dicts JSON-safe de chaînes : identifiant de message
    (``MSGID``/``MSGNO``, le critère stable), horodatage, texte pour le seul
    lecteur. Les champs vides sont conservés : une ligne de journal sans
    identifiant existe (texte libre) et ne doit pas disparaître."""
    return [{str(name): str(value).rstrip() for name, value in row.items()}
            for row in rows]
