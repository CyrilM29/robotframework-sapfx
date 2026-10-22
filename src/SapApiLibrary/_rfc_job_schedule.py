"""Mixin de la *planification* d'un job de fond par XBP (2026-10-12).

Le collecteur de workload (``RSCOLL00``), figé depuis 2017 sur les deux
images de démonstration, a été replanifié pour la cartographie des
interfaces (backlog § 2.76) par des scripts ponctuels : la séquence XBP qui
a marché devient `Schedule Background Job`, dans ce module à part plutôt que
dans ``_rfc_jobs.py`` (une capacité nouvelle a son module, convention n°13).

Le geste ÉCRIT sur le système : liste blanche de noms obligatoire, jamais le
mandant ``000``, pas de doublon d'un run qui attend son départ, et un job à
moitié créé (un appel refusé entre l'ouverture et la libération) est
supprimé avant de lever, parce qu'un run ``P`` orphelin ne part jamais et
encombre le journal. Sous une politique ``read_only`` les modules XBP
d'écriture sont refusés avant l'appel, comme toute écriture RFC.

Logique pure dans ``sapfx_common.job_schedule``. Typed.
"""
from __future__ import annotations

from typing import Any, Optional, Literal

from robot.api import logger

from sapfx_common.robot_args import NameListInput
from sapfx_common import bapi_return, job_schedule

from ._rfc_jobs import RfcJobKeywords

#: Ce que la relecture du run confronte à la demande.
SCHEDULE_FIELDS = ("JOBCOUNT", "STATUS", "SDLUNAME", "PERIODIC", "PRDHOURS", "SDLSTRTDT", "SDLSTRTTM")


class RfcJobScheduleKeywords(RfcJobKeywords):
    """Mixin de :class:`SapApiLibrary` : planifier un job de fond."""

    def schedule_background_job(self, jobname: str, program: str, allowed_prefixes: NameListInput,
                                alias: str = "default", start: str = job_schedule.IMMEDIATE,
                                period_hours: int = 0, variant: str = "",
                                if_planned: Literal["refuse", "keep"] = "refuse",
                                step_user: Optional[str] = None,
                                external_user: Optional[str] = None) -> dict[str, Any]:
        """Planifie le job ``jobname`` d'une étape ABAP ``program`` (et
        ``variant``) par XBP et RELIT le run dans ``TBTCO`` ; rend
        ``{created, jobname, jobcount, status, start, period_hours, planned}``.

        ``start`` vaut ``immediate`` (départ tout de suite,
        ``BAPI_XBP_JOB_START_IMMEDIATELY``) ou une date ISO en heure SYSTÈME
        (``2026-10-13 06:00``, ``BAPI_XBP_JOB_HEADER_MODIFY``) ; un job
        périodique (``period_hours`` de 1 à 99) exige cette date. Gardes, toutes
        AVANT le premier appel : ``allowed_prefixes`` OBLIGATOIRE (une liste
        vide refuse tout) et le nom doit en porter un ; jamais le mandant
        ``000`` ; un run du même nom qui attend son départ (``P``, ``S``)
        refuse la planification (``if_planned=refuse``) ou est rendu tel quel
        (``if_planned=keep``, ``created`` faux : le geste devient idempotent).
        L'étape tourne sous ``step_user`` (défaut : l'utilisateur de la
        connexion). Un appel refusé après l'ouverture supprime le run
        commencé avant de lever. La relecture exige le run, un statut qui
        n'est plus ``P`` (planifié sans condition : il ne partirait jamais),
        et pour un départ daté la date, l'heure et la périodicité demandées.

        Exemple :
        | ${job}=    `Schedule Background Job`    SAPFX_SCHED_I172525    BTCTEST    SAPFX_SCHED_
        | ...    alias=a4h
        | Should Be True    ${job}[created]
        """
        guard = job_schedule.validate_job_schedule(jobname, program, allowed_prefixes, start,
                                                   period_hours, variant, if_planned)
        name = guard["jobname"]
        attributes = self.get_rfc_connection_attributes(alias)
        client = str(attributes.get("client", "")).strip()
        if not client or client == "000":
            raise ValueError("Schedule Background Job refuse le mandant %r : jamais le mandant 000, et "
                             "un mandant illisible ne se devine pas." % client)
        planned = job_schedule.planned_runs(self._job_rows(name, alias, SCHEDULE_FIELDS))
        if planned:
            if guard["if_planned"] == "keep":
                logger.info("Job %s déjà planifié (%s/%s) : rendu tel quel, rien créé."
                            % (name, planned[0]["jobcount"], planned[0]["status"]))
                return {"created": False, "jobname": name, "jobcount": planned[0]["jobcount"],
                        "status": planned[0]["status"], "start": "", "period_hours": guard["period_hours"],
                        "planned": planned}
            raise AssertionError(job_schedule.planned_refusal(name, planned))
        user = self._xbp_external_user(alias, external_user)
        step = str(step_user or attributes.get("user", "")).strip()
        with self._xbp_session(alias):
            opened, failing = self._call_xbp("BAPI_XBP_JOB_OPEN", alias, JOBNAME=name, EXTERNAL_USER_NAME=user)
            if failing:
                raise AssertionError(bapi_return.format_bapi_failure("BAPI_XBP_JOB_OPEN", failing))
            count = str(opened.get("JOBCOUNT", "")).strip()
            try:
                self._release_job(alias, name, count, user, step, guard)
            except Exception:
                self._abandon_job(alias, name, count, user)
                raise
        return self._schedule_readback(alias, name, count, guard)

    def _release_job(self, alias: str, name: str, count: str, user: str, step: str,
                     guard: dict[str, Any]) -> None:
        """Étape, clôture, puis départ immédiat ou daté : la séquence mesurée."""
        step_params: dict[str, Any] = {"JOBNAME": name, "JOBCOUNT": count, "EXTERNAL_USER_NAME": user,
                                       "ABAP_PROGRAM_NAME": guard["program"], "SAP_USER_NAME": step}
        if guard["variant"]:
            step_params["ABAP_VARIANT_NAME"] = guard["variant"]
        calls: list[tuple[str, dict[str, Any]]] = [
            ("BAPI_XBP_JOB_ADD_ABAP_STEP", step_params),
            ("BAPI_XBP_JOB_CLOSE", {"JOBNAME": name, "JOBCOUNT": count, "EXTERNAL_USER_NAME": user})]
        if guard["start"] is None:
            calls.append(("BAPI_XBP_JOB_START_IMMEDIATELY",
                          {"JOBNAME": name, "JOBCOUNT": count, "EXTERNAL_USER_NAME": user}))
        else:
            header, mask = job_schedule.schedule_header(guard["start"], guard["period_hours"])
            calls.append(("BAPI_XBP_JOB_HEADER_MODIFY", {"JOBNAME": name, "JOBCOUNT": count,
                                                         "EXTERNAL_USER_NAME": user, "JOB_HEADER": header,
                                                         "MASK": mask}))
        for function, params in calls:
            _, failing = self._call_xbp(function, alias, **params)
            if failing:
                raise AssertionError(bapi_return.format_bapi_failure(function, failing))

    def _abandon_job(self, alias: str, name: str, count: str, user: str) -> None:
        """Supprime le run commencé, best-effort : l'erreur d'origine prime."""
        try:
            _, failing = self._call_xbp("BAPI_XBP_JOB_DELETE", alias, JOBNAME=name, JOBCOUNT=count,
                                        EXTERNAL_USER_NAME=user)
            if failing:
                logger.warn("Run %s/%s commencé puis refusé, suppression refusée aussi : %s"
                            % (name, count, bapi_return.format_bapi_failure("BAPI_XBP_JOB_DELETE", failing)))
            else:
                logger.info("Run %s/%s commencé puis refusé : supprimé." % (name, count))
        except Exception as error:  # noqa: BLE001 - jamais au prix de l'erreur d'origine
            logger.warn("Run %s/%s commencé puis refusé, suppression impossible : %s" % (name, count, error))

    def _schedule_readback(self, alias: str, name: str, count: str, guard: dict[str, Any]) -> dict[str, Any]:
        """Relit le run et le confronte à la demande ; un écart lève en le nommant."""
        rows = self._job_rows(name, alias, SCHEDULE_FIELDS, count)
        if not rows:
            raise AssertionError("XBP a répondu sans erreur, mais le run %s/%s est absent de TBTCO : "
                                 "planification NON constatée." % (name, count))
        row = {k: str(v).strip() for k, v in rows[0].items()}
        gaps = []
        if row.get("STATUS") == "P":
            gaps.append("statut P (planifié sans condition de départ : il ne partirait jamais)")
        start = ""
        if guard["start"] is not None:
            header, _ = job_schedule.schedule_header(guard["start"], guard["period_hours"])
            start = guard["start"].strftime("%Y-%m-%d %H:%M:%S")
            for field in ("SDLSTRTDT", "SDLSTRTTM"):
                if row.get(field) != header[field]:
                    gaps.append("%s %s lu, %s demandé" % (field, row.get(field), header[field]))
            if guard["period_hours"] and (row.get("PERIODIC") != "X"
                                          or int(row.get("PRDHOURS") or 0) != guard["period_hours"]):
                gaps.append("périodicité %s/%s lue, %d heure(s) demandée(s)"
                            % (row.get("PERIODIC"), row.get("PRDHOURS"), guard["period_hours"]))
        if gaps:
            raise AssertionError("Run %s/%s relu dans TBTCO, mais il ne porte pas ce qui a été demandé : %s."
                                 % (name, count, "; ".join(gaps)))
        logger.info("Job %s/%s planifié (%s), relu dans TBTCO." % (name, count, row.get("STATUS")))
        return {"created": True, "jobname": name, "jobcount": count, "status": row.get("STATUS", ""),
                "start": start or job_schedule.IMMEDIATE, "period_hours": guard["period_hours"], "planned": []}
