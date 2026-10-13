"""Planifier un job de fond par XBP : les gardes et l'en-tête, logique pure.
Socle du mixin ``SapApiLibrary._rfc_job_schedule`` (2026-10-12, backlog
§ 2.76 : le collecteur de workload, figé sur les deux images de
démonstration, a été replanifié par des scripts ponctuels ; le geste devient
une capacité).

La séquence XBP qui a marché sur A4H (754) et la 2023 (758), mandant 001 :
``BAPI_XBP_JOB_OPEN`` (le ``JOBCOUNT``), ``BAPI_XBP_JOB_ADD_ABAP_STEP``,
``BAPI_XBP_JOB_CLOSE``, puis ``BAPI_XBP_JOB_START_IMMEDIATELY`` pour un départ
immédiat, ou ``BAPI_XBP_JOB_HEADER_MODIFY`` pour une date de départ ou une
périodicité. Deux faits mesurés : la structure ``BP20HEAD`` porte
``SDLSTRTDT``, ``SDLSTRTTM``, ``PERIODIC`` et ``PRDHOURS``, et son masque
``BP20HMSK`` n'a QUE ``STARTCOND`` (le masque d'un champ ``PERIODIC`` est
refusé côté client, ``RFC_INVALID_PARAMETER``) ; les heures de départ sont en
heure SYSTÈME (``UTC`` sur le banc, ``TTZCU-TZONESYS``), pas celle de
l'utilisateur.

Trois gardes, toutes AVANT le premier appel : la liste blanche de noms
OBLIGATOIRE (une liste vide refuse tout, patron de `validate_job_deletion`),
un départ immédiat ou une date ISO explicite (un job périodique exige sa
date : « tout de suite, puis toutes les heures » n'a pas de module XBP), et
une périodicité en heures entières, au plus 99 (``PRDHOURS`` tient sur deux
caractères). Typed.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from .robot_args import as_name_list

#: Longueurs du dictionnaire : ``BTCJOB`` (32), ``BTCPROG`` (40), ``BTCVARIANT`` (14).
JOB_NAME_MAX, PROGRAM_MAX, VARIANT_MAX = 32, 40, 14
#: Statuts d'un run qui attend encore son départ : un second ne s'y ajoute pas.
PLANNED_STATUSES = ("P", "S")
IF_PLANNED = ("refuse", "keep")
IMMEDIATE = "immediate"

__all__ = ["JOB_NAME_MAX", "PROGRAM_MAX", "VARIANT_MAX", "PLANNED_STATUSES", "IF_PLANNED",
           "IMMEDIATE", "parse_start", "validate_job_schedule", "schedule_header",
           "planned_runs", "planned_refusal"]


def parse_start(start: Any) -> Optional[datetime]:
    """``None`` pour un départ immédiat, sinon la date et l'heure SYSTÈME
    lues en ISO (``2026-10-13 06:00`` ou ``2026-10-13T06:00:00``)."""
    text = str(start if start is not None else IMMEDIATE).strip()
    if not text or text.lower() == IMMEDIATE:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?", text)
    if not match:
        raise ValueError("start=%r : attendu %r ou une date ISO en heure système, par exemple "
                         "2026-10-13 06:00." % (start, IMMEDIATE))
    year, month, day, hour, minute, second = (int(g or 0) for g in match.groups())
    return datetime(year, month, day, hour, minute, second)


def validate_job_schedule(jobname: str, program: str, allowed_prefixes: Any, start: Any = IMMEDIATE,
                          period_hours: Any = 0, variant: str = "",
                          if_planned: str = "refuse") -> dict[str, Any]:
    """La garde AVANT tout appel : rend ``{jobname, program, variant, start,
    period_hours, if_planned, prefixes}`` normalisés, ou lève ``ValueError``
    en nommant ce qui manque."""
    prefixes = [p.upper() for p in as_name_list(allowed_prefixes, "allowed_prefixes")]
    if not prefixes:
        raise ValueError("Schedule Background Job refuse une liste blanche VIDE : allowed_prefixes est "
                         "obligatoire (préfixes ou noms des jobs que l'appelant a le droit de planifier).")
    name = str(jobname or "").strip().upper()
    if not name or len(name) > JOB_NAME_MAX:
        raise ValueError("nom de job %r : 1 à %d caractères." % (jobname, JOB_NAME_MAX))
    if not any(name.startswith(prefix) for prefix in prefixes):
        raise ValueError("Le job %r ne porte aucun préfixe de la liste blanche (%s) : planification "
                         "refusée avant tout appel." % (jobname, ", ".join(prefixes)))
    prog = str(program or "").strip().upper()
    if not prog or len(prog) > PROGRAM_MAX:
        raise ValueError("programme %r : 1 à %d caractères." % (program, PROGRAM_MAX))
    var = str(variant or "").strip().upper()
    if len(var) > VARIANT_MAX:
        raise ValueError("variante %r : au plus %d caractères." % (variant, VARIANT_MAX))
    try:
        hours = int(str(period_hours or 0).strip())
    except ValueError:
        raise ValueError("period_hours=%r : un nombre entier d'heures est attendu." % period_hours) from None
    if not 0 <= hours <= 99:
        raise ValueError("period_hours=%d : de 0 (job unique) à 99 heures." % hours)
    when = parse_start(start)
    if hours and when is None:
        raise ValueError("Un job périodique exige une date de départ (start=2026-10-13 06:00, heure "
                         "système) : aucun module XBP ne libère « tout de suite, puis toutes les N heures ».")
    mode = str(if_planned or "refuse").strip().lower()
    if mode not in IF_PLANNED:
        raise ValueError("if_planned=%r : attendu %s." % (if_planned, " ou ".join(IF_PLANNED)))
    return {"jobname": name, "program": prog, "variant": var, "start": when, "period_hours": hours,
            "if_planned": mode, "prefixes": prefixes}


def schedule_header(start: datetime, period_hours: int = 0) -> tuple[dict[str, str], dict[str, str]]:
    """L'en-tête ``BP20HEAD`` et le masque ``BP20HMSK`` de
    ``BAPI_XBP_JOB_HEADER_MODIFY`` : date de départ, et périodicité s'il y
    en a une. Le masque ne porte que ``STARTCOND`` (le seul champ qu'il a)."""
    header = {"SDLSTRTDT": start.strftime("%Y%m%d"), "SDLSTRTTM": start.strftime("%H%M%S")}
    if period_hours:
        header.update({"PERIODIC": "X", "PRDHOURS": "%02d" % int(period_hours)})
    return header, {"STARTCOND": "X"}


def planned_runs(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Les runs d'un nom qui attendent encore leur départ (``P``, ``S``)."""
    return [{"jobcount": str(r.get("JOBCOUNT", "")).strip(), "status": str(r.get("STATUS", "")).strip(),
             "scheduled_by": str(r.get("SDLUNAME", "")).strip()}
            for r in rows if str(r.get("STATUS", "")).strip() in PLANNED_STATUSES]


def planned_refusal(jobname: str, planned: list[dict[str, str]]) -> str:
    """Le refus nommé d'un doublon : un second run planifié du même nom
    tournerait deux fois (le collecteur de workload, par exemple)."""
    return ("Le job %s a déjà %d run(s) qui attend(ent) son départ (%s) : planification refusée pour ne "
            "pas le doubler ; if_planned=keep rend le run existant." % (
                jobname, len(planned), ", ".join("%s/%s par %s" % (p["jobcount"], p["status"],
                                                                    p["scheduled_by"] or "?") for p in planned)))
