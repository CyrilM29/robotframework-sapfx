"""Lecture de tables par ``RFC_READ_TABLE`` et suivi des jobs de fond.

``RFC_READ_TABLE`` est le cheval de trait historique des intégrations SAP :
présent partout, remote-enabled, il lit n'importe quelle table transparente
sans écran. Ce module porte la logique PURE : construction des paramètres
(``FIELDS``/``OPTIONS``, clauses limitées à 72 caractères par ligne),
parsing des lignes ``DATA`` retournées (séparateur), et la classification
des statuts de job de fond (table ``TBTCO``, domaine ``BTCSTATUS``) qui
fonde ``Wait For Background Job``. L'appel RFC lui-même vit dans
``SapApiLibrary`` (pyrfc optionnel).

Limite assumée du séparateur : une valeur qui CONTIENT le délimiteur
fausse le découpage de sa ligne ; choisir un délimiteur absent des données
(le ``|`` convient aux champs techniques : statuts, compteurs, noms).
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

#: Longueur maximale d'une clause OPTIONS de RFC_READ_TABLE (contrainte ABAP).
OPTIONS_LINE_LIMIT = 72

#: Statuts TBTCO (domaine BTCSTATUS) : lisibles par un humain ou un agent.
JOB_STATUS_LABELS = {
    "P": "scheduled",
    "S": "released",
    "Y": "ready",
    "R": "active",
    "F": "finished",
    "A": "cancelled",
}

#: Statuts « le job n'a pas fini » : on continue d'attendre.
PENDING_JOB_STATUSES = ("P", "S", "Y", "R")


def read_table_params(table: str, fields: Sequence[str],
                      options: Sequence[str] = (),
                      delimiter: str = "|",
                      rowcount: int = 0) -> dict[str, Any]:
    """Construit les paramètres d'un appel ``RFC_READ_TABLE`` : table, champs
    demandés, clauses de sélection (chacune <= 72 caractères, la contrainte
    ABAP : au-delà, découper la condition en plusieurs clauses ``AND``).
    ``rowcount=0`` = toutes les lignes."""
    for clause in options:
        if len(clause) > OPTIONS_LINE_LIMIT:
            raise ValueError(
                "Clause OPTIONS trop longue pour RFC_READ_TABLE (%d > %d "
                "caractères) : découper en plusieurs clauses AND. Clause : %r"
                % (len(clause), OPTIONS_LINE_LIMIT, clause))
    params: dict[str, Any] = {
        "QUERY_TABLE": table,
        "DELIMITER": delimiter,
        "FIELDS": [{"FIELDNAME": name} for name in fields],
        "OPTIONS": [{"TEXT": clause} for clause in options],
    }
    if int(rowcount):
        params["ROWCOUNT"] = int(rowcount)
    return params


def abap_quote(value: str) -> str:
    """Littéral ABAP entre quotes simples, quotes internes doublées
    (``O'Neil`` -> ``'O''Neil'``) : pour composer les clauses OPTIONS sans
    casser la syntaxe."""
    return "'%s'" % str(value).replace("'", "''")


def parse_read_table(result: Mapping[str, Any],
                     delimiter: str = "|") -> list[dict[str, str]]:
    """Transforme le résultat brut de ``RFC_READ_TABLE`` (tables ``FIELDS``
    et ``DATA``) en liste de dicts ``{champ: valeur}``, valeurs dépouillées
    des blancs de fin ABAP. Une ligne qui produit moins de colonnes que
    demandé est complétée par des chaînes vides (champ final vide non émis
    par le split)."""
    field_names = [str(entry.get("FIELDNAME", "")).strip()
                   for entry in result.get("FIELDS", [])]
    rows: list[dict[str, str]] = []
    for entry in result.get("DATA", []):
        raw = entry.get("WA", "") if isinstance(entry, Mapping) else str(entry)
        values = [value.strip() for value in str(raw).split(delimiter)]
        while len(values) < len(field_names):
            values.append("")
        # strict=False assumé : un délimiteur DANS une valeur produit des
        # colonnes excédentaires, ignorées (limite documentée en tête de module).
        rows.append(dict(zip(field_names, values, strict=False)))
    return rows


def summarize_job_statuses(rows: Sequence[Mapping[str, str]],
                           status_field: str = "STATUS") -> dict[str, int]:
    """Compte les occurrences de chaque statut de job dans les lignes lues
    (``{"F": 2, "R": 1}``)."""
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get(status_field, "")).strip().upper()
        if status:
            counts[status] = counts.get(status, 0) + 1
    return counts


def job_wait_verdict(counts: Mapping[str, int]) -> dict[str, Any]:
    """Verdict d'attente d'un job de fond depuis les statuts comptés :
    ``{"state": "missing"|"aborted"|"waiting"|"done", "detail": str}``.

    ``aborted`` prime (au moins un run annulé = échec à remonter), puis
    ``waiting`` (un run encore dans le pipeline P/S/Y/R), puis ``done``
    (au moins un ``F`` et plus rien en attente). ``missing`` = aucune ligne :
    le job n'existe pas (encore) sous ce nom."""
    if not counts:
        return {"state": "missing",
                "detail": "Aucun job trouvé sous ce nom (pas encore créé ?)."}
    described = ", ".join(
        "%s=%d (%s)" % (status, count, JOB_STATUS_LABELS.get(status, "?"))
        for status, count in sorted(counts.items()))
    if counts.get("A"):
        return {"state": "aborted",
                "detail": "Au moins un run annulé (statut A) : %s." % described}
    if any(counts.get(status) for status in PENDING_JOB_STATUSES):
        return {"state": "waiting",
                "detail": "Job encore dans le pipeline : %s." % described}
    if counts.get("F"):
        return {"state": "done", "detail": "Terminé : %s." % described}
    return {"state": "waiting",
            "detail": "Statuts inattendus, on continue d'attendre : %s." % described}
