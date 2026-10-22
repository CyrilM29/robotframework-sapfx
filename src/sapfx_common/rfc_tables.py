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

from sapfx_common import __version__ as _package_version
from robot.api.deco import keyword

#: Version de ce module quand Robot l'importe comme bibliothèque (Libdoc, journal) :
#: celle du paquet, jamais une seconde valeur à aligner à chaque release.
ROBOT_LIBRARY_VERSION = _package_version

#: Seules les fonctions décorées par ``@keyword`` deviennent des keywords :
#: Robot lit aussi ``__all__``, mais le chargeur de rf-mcp ne lit que ce
#: drapeau, et sans lui y publiait les fonctions importées d'ailleurs.
ROBOT_AUTO_KEYWORDS = False

#: Les keywords que ``Library    sapfx_common.rfc_tables`` expose.
__all__ = ["in_list_clauses"]

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
    ``rowcount=0`` = toutes les lignes.

    Exemple :
    | ${params}=    `Read Table Params`    T000    ${{ ['MANDT', 'MTEXT'] }}
    | Should Be Equal    ${params}[QUERY_TABLE]    T000
    | Should Be Equal    ${params}[FIELDS][0][FIELDNAME]    MANDT
    """
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
    (le dictionnaire ABAP ne connaît que la forme majuscule).

    Exemple :
    | ${fields}=    `As Field List`    mandt, mtext
    | Should Be Equal    ${fields}    ${{ ['MANDT', 'MTEXT'] }}
    """
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    return [str(item).strip().upper() for item in items if str(item).strip()]


def as_clause_list(value: Any) -> list[str]:
    """Liste de clauses ``OPTIONS`` depuis une liste, une clause unique ou
    rien. Contrairement aux champs, une clause n'est jamais découpée : elle
    contient des espaces, des quotes et parfois des virgules, et c'est
    l'appelant qui décide où elle s'arrête (limite de 72 caractères par
    clause, vérifiée par `read_table_params`).

    Exemple :
    | ${clauses}=    `As Clause List`    JOBNAME LIKE 'SAPFX_JOB_20261001%'
    | Length Should Be    ${clauses}    1
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def abap_quote(value: str) -> str:
    """Littéral ABAP entre quotes simples, quotes internes doublées
    (``O'Neil`` -> ``'O''Neil'``) : pour composer les clauses OPTIONS sans
    casser la syntaxe.

    Exemple :
    | ${literal}=    `Abap Quote`    O'Neil
    | Should Be Equal    ${literal}    'O''Neil'
    """
    return "'%s'" % str(value).replace("'", "''")


@keyword
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

    Exemple :
    | @{tables}=    Create List    SWWWIHEAD    SWWUSERWI    SWFDEVENA    SWD_HEADER    SWETYPECOU
    | ${clauses}=    `In List Clauses`    TABNAME    ${tables}
    | Should Be Equal    ${clauses}[1]    OR TABNAME IN ('SWETYPECOU')
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
    par le split).

    Exemple :
    | ${params}=    Read Table Params    T000    ${{ ['MANDT', 'MTEXT'] }}
    | ${result}=    Call Rfc    RFC_READ_TABLE    alias=a4h    &{params}
    | ${rows}=    `Parse Read Table`    ${result}
    | Should Be Equal    ${rows}[1][MANDT]    001
    """
    field_names = [str(entry.get("FIELDNAME", "")).strip()
                   for entry in result.get("FIELDS", [])]
    rows: list[dict[str, str]] = []
    for entry in result.get("DATA", []):
        raw = entry.get("WA", "") if isinstance(entry, Mapping) else str(entry)
        # un champ caractère peut finir par des NUL (``QRFC_I_UNIT-TCODE`` écrit
        # par un client NW RFC : « NW RFC Library 753 » suivi de NUL, mesuré)
        values = [value.replace("\x00", "").strip() for value in str(raw).split(delimiter)]
        while len(values) < len(field_names):
            values.append("")
        # strict=False assumé : un délimiteur DANS une valeur produit des
        # colonnes excédentaires, ignorées (limite documentée en tête de module).
        rows.append(dict(zip(field_names, values, strict=False)))
    return rows


def truncated_raw_fields(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Les champs de type ``X`` (RAW) du résultat de ``RFC_READ_TABLE``, que
    le module rend TRONQUÉS en silence : il réserve ``LENGTH`` caractères à un
    champ de ``LENGTH`` octets, or un octet s'écrit en deux chiffres
    hexadécimaux. Mesuré sur A4H le 2026-09-28 : ``BUT000-PARTNER_GUID`` (RAW
    16) déclaré ``TYPE X`` / ``LENGTH 16`` et rendu sur 16 caractères, soit la
    moitié du GUID, IDENTIQUE pour deux partenaires différents. Rend
    ``[{"field", "bytes", "rendered_hex"}]``, vide si aucun champ RAW.

    Le critère est le ``TYPE`` que le module DÉCLARE dans ``FIELDS``, pas le
    ``INTTYPE`` du dictionnaire : DD03L range aussi INT1 et INT4 en ``X``
    (``USR02-UFLAG``, ``ICFVIRHOST-HOSTNUMBER``), que le module déclare ``b``
    et ``I`` et rend entiers (mesuré le même jour sur 754 et 758).

    Exemple :
    | ${params}=    Read Table Params    BUT000    ${{ ['PARTNER', 'PARTNER_GUID'] }}    rowcount=1
    | ${result}=    Call Rfc    RFC_READ_TABLE    alias=a4h    &{params}
    | ${raw}=    `Truncated Raw Fields`    ${result}
    | Should Be Equal    ${raw}[0][field]    PARTNER_GUID
    | Should Be Equal As Integers    ${raw}[0][bytes]    16
    """
    found = []
    for entry in result.get("FIELDS", []):
        if str(entry.get("TYPE", "")).strip().upper() != "X":
            continue
        try:
            length = int(str(entry.get("LENGTH", "0")).strip() or 0)
        except ValueError:
            length = 0
        found.append({"field": str(entry.get("FIELDNAME", "")).strip(),
                      "bytes": length, "rendered_hex": length})
    return found


#: Les types de ``FIELDS`` que le mode ``USE_ET_DATA_4_RETURN`` rend TELS QUELS :
#: texte, NUMC et RAW (en hexadécimal, sur toute sa longueur). Les autres (entier,
#: packé, date, heure) y sont mis en forme selon l'utilisateur, mesuré le
#: 2026-10-18 sur 754 : ``1.409.196.102`` pour un INT4, ``22.201``, un horodatage
#: à séparateurs.
ET_DATA_SAFE_TYPES = frozenset({"C", "N", "X"})
#: Les entiers (``I``, ``b``, ``s``, ``8``) y sont mis en forme mais se ramènent sans
#: ambiguïté à leurs chiffres et à leur signe (signe ABAP en fin : ``123-``).
ET_DATA_INTEGER_TYPES = frozenset({"I", "B", "S", "8"})


def _undelivered_fields(result: Mapping[str, Any], requested: Sequence[str]) -> list[str]:
    """Les champs DEMANDÉS que ``RFC_READ_TABLE`` n'a pas rendus, dans l'ordre
    de la demande. Le module OMET un champ qu'il ne sait pas livrer (mesuré le
    2026-10-19 sur ``ESH_ADM_PARAM-VALUE``, type chaîne court ``SSTR`` de
    ``INTTYPE`` ``g``, absent de la table ``FIELDS`` rendue) au lieu de refuser,
    si bien que les lignes n'en portent simplement pas la clé. Rien n'est
    comparé quand le module ne déclare aucun champ."""
    delivered = {str(entry.get("FIELDNAME", "")).strip().upper()
                 for entry in result.get("FIELDS", [])}
    if not delivered:
        return []
    return [name for name in requested if name.upper() not in delivered]


def _format_undelivered(table: str, fields: Sequence[str]) -> str:
    return ("Read Rfc Table : RFC_READ_TABLE n'a pas rendu le(s) champ(s) %s de %s. Le "
            "module OMET sans erreur un champ qu'il ne sait pas livrer (mesuré sur un "
            "champ de type chaîne court, SSTR : `ESH_ADM_PARAM-VALUE`), donc les lignes "
            "n'en portent pas la clé : une lecture par nom la prend pour une valeur "
            "absente ou vide, jamais pour une limite du canal. Lire ce champ par un "
            "autre canal (service OData, source ADT, écran), ou le retirer de la "
            "demande." % (", ".join(fields), table))


def _et_data_unsafe_fields(result: Mapping[str, Any]) -> list[str]:
    """Les champs du résultat qu'``ET_DATA`` mettrait en forme de façon
    irréversible (décimaux, dates, heures) : ``CHAMP (type)``."""
    return ["%s (%s)" % (str(entry.get("FIELDNAME", "")).strip(), str(entry.get("TYPE", "")).strip())
            for entry in result.get("FIELDS", [])
            if str(entry.get("TYPE", "")).strip().upper()
            not in ET_DATA_SAFE_TYPES | ET_DATA_INTEGER_TYPES]


def _plain_integer(text: str) -> str:
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return ""
    negative = text.strip().startswith("-") or text.strip().endswith("-")
    return str(-int(digits) if negative else int(digits))


def _parse_et_data(result: Mapping[str, Any], delimiter: str = "|") -> list[dict[str, str]]:
    """Les lignes du mode ``USE_ET_DATA_4_RETURN`` (table ``ET_DATA``, lignes de
    longueur variable) : même forme que `parse_read_table`, RAW en entier,
    entiers ramenés à leurs chiffres (``21.203`` -> ``21203``)."""
    fields = [(str(entry.get("FIELDNAME", "")).strip(), str(entry.get("TYPE", "")).strip().upper())
              for entry in result.get("FIELDS", [])]
    rows: list[dict[str, str]] = []
    for entry in result.get("ET_DATA", []) or []:
        raw = entry.get("LINE", "") if isinstance(entry, Mapping) else str(entry)
        values = [value.replace("\x00", "").strip() for value in str(raw).split(delimiter)]
        while len(values) < len(fields):
            values.append("")
        row = {}
        for (name, kind), value in zip(fields, values, strict=False):
            row[name] = _plain_integer(value) if kind in ET_DATA_INTEGER_TYPES else value
        rows.append(row)
    return rows


def format_truncated_raw(table: str, fields: Sequence[Mapping[str, Any]]) -> str:
    """Refus actionnable d'une lecture qui porterait un champ RAW tronqué.

    Exemple :
    | ${message}=    `Format Truncated Raw`    BUT000    ${raw}
    | Should Contain    ${message}    PARTNER_GUID (RAW 16
    """
    names = ", ".join("%s (RAW %d : %d chiffres hexadécimaux rendus sur %d)"
                      % (f["field"], f["bytes"], f["rendered_hex"], 2 * f["bytes"])
                      for f in fields)
    return ("Read Rfc Table refuse de rendre %s : RFC_READ_TABLE tronque un "
            "champ RAW à la moitié de sa valeur, sans le signaler : %s. Une "
            "valeur tronquée paraît plausible et peut être IDENTIQUE pour deux "
            "lignes différentes (mesuré sur deux GUID de partenaire), donc une "
            "jointure sur elle serait verte et fausse. Retirer ce champ de la "
            "projection et identifier la ligne par sa clé caractère ; un filtre "
            "OPTIONS sur la valeur complète (32 chiffres hexadécimaux) reste "
            "possible, et la valeur entière se lit par un autre canal (grille "
            "SE16, OData, BAPI)." % (table, names))


def summarize_job_statuses(rows: Sequence[Mapping[str, str]],
                           status_field: str = "STATUS") -> dict[str, int]:
    """Compte les occurrences de chaque statut de job dans les lignes lues
    (``{"F": 2, "R": 1}``).

    Exemple :
    | ${counts}=    `Summarize Job Statuses`    ${rows}
    | Dictionary Should Not Contain Key    ${counts}    A
    | Should Be True    ${counts}[F] > 0
    """
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
    agrège tout le journal et ne dit donc pas quel job porte quel cas.

    Exemple :
    | ${grouped}=    `Group Job Statuses`    ${rows}
    | Should Be Equal As Integers    ${grouped}[SAPFX_JOB_20261001_130542][F]    1
    """
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
    le job n'existe pas (encore) sous ce nom.

    Exemple :
    | ${grouped}=    Group Job Statuses    ${rows}
    | ${verdict}=    `Job Wait Verdict`    ${grouped}[SAPFX_JOB_20261001_130542]
    | Should Be Equal    ${verdict}[state]    done
    """
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
    """Le journal des jobs relu comme un *catalogue de cas d'attente* : pour
    chaque issue que `job_wait_verdict` peut rendre, les jobs de la cible qui
    la produiraient. C'est ce qui permet d'éprouver l'attente sur un système
    réel *sans rien y écrire* et sans graver de noms de jobs, qui sont ceux
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
    absent du journal n'y figure pas.

    Exemple :
    | ${grouped}=    Group Job Statuses    ${rows}
    | ${cases}=    `Job Wait Cases`    ${grouped}
    | Should Contain    ${cases}[done]    SAPFX_JOB_20261001_130542
    | Should Be Empty    ${cases}[aborted]
    """
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
