"""Lecture de tables par ``RFC_READ_TABLE`` et suivi des jobs de fond.

``RFC_READ_TABLE`` est le cheval de trait historique des intégrations SAP :
présent partout, remote-enabled, il lit n'importe quelle table transparente
sans écran. Ce module porte la logique PURE : construction des paramètres
(``FIELDS``/``OPTIONS``, clauses limitées à 72 caractères par ligne),
parsing des lignes ``DATA`` retournées (séparateur), et la classification
des statuts de job de fond (table ``TBTCO``, domaine ``BTCSTATUS``) qui
fonde ``Wait For Background Job``, y compris le regroupement par job et le
catalogue des cas d'attente que la cible porte déjà (``job_wait_cases``),
la voie qui permet d'éprouver l'attente sans créer ni annuler un job.
L'appel RFC lui-même vit dans ``SapApiLibrary`` (pyrfc optionnel).

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


def as_field_list(value: Any) -> list[str]:
    """Liste de noms de champs depuis ce qu'une suite Robot peut fournir : une
    liste, ou une chaîne séparée par des virgules (``"CARRID,CARRNAME"``). Les
    entrées vides sont ignorées, les noms sont dépouillés et mis en capitales
    (le dictionnaire ABAP ne connaît que la forme majuscule)."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    return [str(item).strip().upper() for item in items if str(item).strip()]


def as_clause_list(value: Any) -> list[str]:
    """Liste de clauses ``OPTIONS`` depuis une liste, une clause unique ou
    rien. Contrairement aux champs, une clause n'est jamais découpée : elle
    contient des espaces, des quotes et parfois des virgules, et c'est
    l'appelant qui décide où elle s'arrête (limite de 72 caractères par
    clause, vérifiée par `read_table_params`)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def abap_quote(value: str) -> str:
    """Littéral ABAP entre quotes simples, quotes internes doublées
    (``O'Neil`` -> ``'O''Neil'``) : pour composer les clauses OPTIONS sans
    casser la syntaxe."""
    return "'%s'" % str(value).replace("'", "''")


def in_list_clauses(field: str, values: Sequence[str],
                    limit: int = OPTIONS_LINE_LIMIT) -> list[str]:
    """Découpe un ``<CHAMP> IN (...)`` en autant de clauses que la limite de
    ligne l'impose, les suivantes préfixées ``OR``.

    Le module ABAP borne CHAQUE ligne de ``OPTIONS`` à 72 caractères, mais une
    liste de valeurs n'a pas de raison de tenir sur une ligne, et surtout
    l'appelant qui fournit la liste n'est pas celui qui compose la clause : lui
    demander de la découper est impossible. Sans ce découpage, un keyword qui
    accepte une liste surchargeable marche jusqu'à une valeur de trop, puis
    refuse avec un message qui parle d'une clause que l'appelant n'a jamais
    écrite (mesuré : la liste des six comptes standards SAP occupe 69
    caractères, un septième la porte à 82).

    Les valeurs sont citées par `abap_quote`, donc une quote interne ne casse
    pas la syntaxe. Une valeur si longue qu'elle ne tient dans aucune ligne est
    refusée en le disant, plutôt que tronquée en silence.
    """
    name = str(field).strip()
    if not name:
        raise ValueError("in_list_clauses : le nom de champ est vide.")
    items = [abap_quote(v) for v in values if str(v).strip()]
    if not items:
        raise ValueError(
            f"in_list_clauses : aucune valeur pour '{name}', or une clause "
            f"IN vide sélectionnerait TOUT au lieu de rien.")
    clauses: list[str] = []
    current: list[str] = []
    prefix = f"{name} IN ("
    for item in items:
        head = prefix if not clauses and not current else f"OR {name} IN ("
        if not current:
            candidate = f"{head}{item})"
        else:
            candidate = f"{head}{','.join(current)},{item})"
        if len(candidate) <= limit:
            current.append(item)
            continue
        if not current:
            raise ValueError(
                f"in_list_clauses : la valeur {item} seule dépasse la limite "
                f"de {limit} caractères d'une clause OPTIONS.")
        clauses.append(f"{head if clauses else prefix}{','.join(current)})")
        current = [item]
    if current:
        head = prefix if not clauses else f"OR {name} IN ("
        clauses.append(f"{head}{','.join(current)})")
    return clauses


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


def group_job_statuses(rows: Sequence[Mapping[str, str]],
                       job_field: str = "JOBNAME",
                       status_field: str = "STATUS") -> dict[str, dict[str, int]]:
    """Le journal des jobs regroupé PAR job : ``{"RDDIMPDP": {"F": 300,
    "S": 1}}``. C'est la lecture qui manque à `summarize_job_statuses`, qui
    agrège tout le journal et ne dit donc pas quel job porte quel cas."""
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        name = str(row.get(job_field, "")).strip()
        status = str(row.get(status_field, "")).strip().upper()
        if not name or not status:
            continue
        counts = grouped.setdefault(name, {})
        counts[status] = counts.get(status, 0) + 1
    return grouped


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


def job_wait_cases(grouped: Mapping[str, Mapping[str, int]]) -> dict[str, list[str]]:
    """Le journal des jobs relu comme un **catalogue de cas d'attente** : pour
    chaque issue que `job_wait_verdict` peut rendre, les jobs de la cible qui
    la produiraient. C'est ce qui permet d'éprouver l'attente sur un système
    réel **sans rien y écrire** et sans graver de noms de jobs, qui sont ceux
    d'une image donnée et n'existeront pas ailleurs.

    Clés : ``done``, ``aborted``, ``aborted_with_finished``, ``pipeline``,
    ``unmapped``. Listes triées, donc un choix reproductible d'un run à
    l'autre.

    Deux clés méritent leur existence. ``aborted_with_finished`` est le
    sous-ensemble des jobs annulés qui portent AUSSI des runs terminés : c'est
    lui, et lui seul, qui prouve qu'un ``A`` prime sur des dizaines de ``F``
    (un run annulé est un fait à remonter, jamais une statistique à moyenner).
    Et ``unmapped`` sépare, dans le ``waiting`` du verdict, les jobs encore
    dans le pipeline de ceux dont AUCUN statut n'est cartographié ici : le
    second cas est celui du repli sûr, où l'attente continue au lieu de
    conclure au succès. ``missing`` n'a pas de clé, par définition : un job
    absent du journal n'y figure pas."""
    cases: dict[str, list[str]] = {
        "done": [], "aborted": [], "aborted_with_finished": [],
        "pipeline": [], "unmapped": []}
    for name in sorted(grouped):
        counts = grouped[name]
        state = job_wait_verdict(counts)["state"]
        if state == "aborted":
            cases["aborted"].append(name)
            if counts.get("F"):
                cases["aborted_with_finished"].append(name)
        elif state == "done":
            cases["done"].append(name)
        elif state == "waiting":
            pending = any(counts.get(status) for status in PENDING_JOB_STATUSES)
            cases["pipeline" if pending else "unmapped"].append(name)
    return cases
