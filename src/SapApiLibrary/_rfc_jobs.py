"""Mixin des *jobs de fond* au-delà de l'attente : retrouver le run d'un
nom unique, constater son état d'un coup, supprimer un job non démarré.

Né de la fiche scénario 9 (A4H, 2026-10-01), où un job planifié par SM36
devait être attendu puis suivi jusqu'à son spool. `Wait For Background Job`
existait ; manquaient les trois gestes qui l'entourent :

- `Get Background Job Run` : SM36 ne rend jamais le ``JOBCOUNT`` (le message
  ``BT/S/112`` porte le nom et un statut en texte localisé), donc le run se
  retrouve dans ``TBTCO`` par son nom, et seul un nom UNIQUE suffit : zéro
  run comme plusieurs échouent en nommant ce qui est vu ;
- `Get Background Job Status` / `Background Job State Should Be` : le constat
  ponctuel, sans attente ni exception, où ``pipeline`` (``P`` / ``S`` / ``Y``/
  ``R``) et ``unmapped`` (statut hors carte comme ``Z``) restent distincts ;
- `Delete Background Job` : un job laissé en ``S`` part tout seul plus tard,
  un job en ``P`` ne part jamais. Liste blanche de préfixes OBLIGATOIRE,
  statuts non démarrés seulement, absence RELUE dans ``TBTCO``.

`Wait For Background Job`, `Get Background Job Status Model` et
`Find Background Job Cases` vivent ici depuis le 2026-10-06 (extraits de
``_rfc.py``, convention n°13) : l'attente rejoint les gestes qui l'entourent.

Logique pure dans ``sapfx_common.background_jobs``. Typed.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from robot.api import logger
from robot.utils import timestr_to_secs

from sapfx_common import background_jobs, bapi_return, rfc_reads, rfc_tables
from sapfx_common.polling import poll_until
from sapfx_common.background_jobs import JOB_RUN_FIELDS

from ._rfc_idoc_wait import RfcIdocWaitKeywords


class RfcJobKeywords(RfcIdocWaitKeywords):
    """Mixin de :class:`SapApiLibrary` : un job de fond désigné et jugé."""

    def _job_rows(self, jobname: str, alias: str, fields: Any,
                  jobcount: Optional[str] = None) -> list[dict[str, str]]:
        options = rfc_reads.build_options([("JOBNAME", str(jobname)),
                                           ("JOBCOUNT", jobcount or None)])
        return self.read_rfc_table("TBTCO", list(fields), alias=alias,
                                   options=options)

    def get_background_job_run(self, jobname: str, alias: str = "default",
                               owner: Optional[str] = None,
                               scheduled_after: Optional[str] = None
                               ) -> dict[str, Any]:
        """Le run UNIQUE d'un job de fond, lu dans ``TBTCO`` par son nom :
        ``{jobname, jobcount, status, status_label, scheduled_by, client,
        job_class, scheduled_at, started_at, ended_at}`` (horodatages
        techniques ``AAAAMMJJhhmmss``, heure SYSTÈME, vides quand l'étape n'a
        pas eu lieu).

        C'est la voie du ``JOBCOUNT`` d'un job planifié à l'écran : SM36 ne
        l'affiche nulle part et son message de sauvegarde (``BT/S/112``) ne le
        porte pas. ``owner`` (utilisateur qui l'a planifié) et
        ``scheduled_after`` (``AAAAMMJJhhmmss`` ou ``AAAA-MM-JJ hh:mm:ss``,
        heure système) restreignent la recherche. Zéro run ou plusieurs runs
        ÉCHOUENT en listant les runs vus : un nom réutilisé ferait lire le run
        d'une autre exécution, et rien dans ce run ne le trahirait.

        Exemple :
        | ${run}=    `Get Background Job Run`    SAPFX_JOB_20261001_130542    alias=a4h
        | Should Be Equal    ${run}[status]    F
        """
        rows = self._job_rows(jobname, alias, JOB_RUN_FIELDS)
        return background_jobs.select_job_run(
            rows, str(jobname), owner=owner, scheduled_after=scheduled_after)

    def get_background_job_status(self, jobname: str,
                                  jobcount: Optional[str] = None,
                                  alias: str = "default") -> dict[str, Any]:
        """Constate l'état d'un job en UNE lecture de ``TBTCO``, sans attendre
        et sans jamais lever sur un état : ``{state, detail, statuses,
        runs}``, ``state`` valant ``done``, ``aborted``, ``pipeline``,
        ``unmapped`` ou ``missing``.

        Le complément de `Wait For Background Job`, qui ne sait qu'attendre
        puis réussir ou échouer : ici un job en attente de démarrage
        (``pipeline``) et un job au statut que la bibliothèque ne cartographie
        pas (``unmapped``, le ``Z`` de 105 runs mesurés sur A4H) restent
        distincts, et aucun des deux n'est jamais ``done``. ``jobcount``
        désigne un run précis ; sans lui, tous les runs du nom comptent.

        Exemple :
        | ${status}=    `Get Background Job Status`    SAPFX_JOB_20261001_130542    alias=a4h
        | Should Be Equal    ${status}[state]    done
        """
        rows = self._job_rows(jobname, alias, ("JOBCOUNT", "STATUS"), jobcount)
        report = background_jobs.job_status_report(rows)
        logger.info("Job %s%s : %s" % (jobname, "/%s" % jobcount if jobcount else "",
                                       report["detail"]))
        return report

    def background_job_state_should_be(self, jobname: str, state: str,
                                       jobcount: Optional[str] = None,
                                       alias: str = "default") -> dict[str, Any]:
        """Vérifie que le job est dans l'état ``state`` (``done``,
        ``aborted``, ``pipeline``, ``unmapped`` ou ``missing``) au moment de
        la lecture et rend le constat de `Get Background Job Status`. Un état
        attendu inconnu est refusé AVANT la lecture, en listant les cinq.

        Exemple :
        | `Background Job State Should Be`    SAPFX_JOB_20261001_130542    done    alias=a4h
        """
        expected = background_jobs.expected_job_state(state)
        report = self.get_background_job_status(jobname, jobcount, alias)
        if report["state"] != expected:
            raise AssertionError(
                "Le job %s%s est %r, pas %r : %s"
                % (jobname, "/%s" % jobcount if jobcount else "",
                   report["state"], expected, report["detail"]))
        return report

    def delete_background_job(self, jobname: str, jobcount: str,
                              allowed_prefixes: Any, alias: str = "default",
                              allowed_statuses: Any = None,
                              external_user: Optional[str] = None,
                              owner: Optional[str] = None
                              ) -> dict[str, Any]:
        """Supprime UN run de job de fond NON DÉMARRÉ par
        ``BAPI_XBP_JOB_DELETE`` et RELIT son absence dans ``TBTCO`` ; rend
        ``{deleted, jobname, jobcount, previous_status}``.

        Gardes, toutes AVANT l'appel de suppression : ``allowed_prefixes``
        OBLIGATOIRE (liste ou chaîne à virgules ; une liste vide refuse tout)
        et le nom doit en porter un ; le run doit être dans
        ``allowed_statuses`` (défaut ``P,S`` : planifié ou libéré, jamais
        démarré ; ``R`` refusé quoi qu'on passe) ; il doit avoir été
        planifié par ``owner`` (défaut : l'utilisateur de la connexion RFC)
        dans le mandant de la connexion, parce que la liste blanche ne tient
        que par le nommage et qu'un job d'autrui peut porter le même préfixe ;
        un ``jobcount`` vide est refusé (il désignerait tous les runs du nom).
        Un run déjà absent rend
        ``deleted=False`` sans rien appeler : le geste est idempotent, donc
        sûr dans un teardown. Pourquoi supprimer : un job libéré (``S``) à
        date future part tout seul plus tard, un job planifié sans condition
        (``P``) ne part jamais et reste dans le journal.

        Exemple :
        | ${run}=    `Get Background Job Run`    SAPFX_JOB_20261001_150000    alias=a4h
        | ${deletion}=    `Delete Background Job`    ${run}[jobname]    ${run}[jobcount]    SAPFX_JOB_
        | ...    alias=a4h
        """
        guard = background_jobs.validate_job_deletion(
            jobname, allowed_prefixes, allowed_statuses)
        if not str(jobcount or "").strip():
            raise ValueError("Delete Background Job exige un jobcount : vide, il "
                             "désignerait TOUS les runs du nom %r." % jobname)
        attributes = self.get_rfc_connection_attributes(alias)
        expected_owner = str(owner or attributes.get("user", "")).strip()
        expected_client = str(attributes.get("client", "")).strip()
        if not expected_owner or not expected_client:
            # Une garde qui se saute faute de valeur attendue ne garde rien
            # (contre-revue indépendante du 2026-10-01).
            raise ValueError(
                "Delete Background Job ne sait pas qui doit avoir planifié le run "
                "(utilisateur %r) ni dans quel mandant (%r) : attributs de la "
                "connexion RFC %r illisibles ; passer owner= ou rouvrir la "
                "connexion." % (expected_owner, expected_client, alias))
        rows = self._job_rows(jobname, alias, JOB_RUN_FIELDS, str(jobcount))
        if not rows:
            logger.info("Job %s/%s déjà absent de TBTCO : rien à supprimer."
                        % (jobname, jobcount))
            return {"deleted": False, "jobname": str(jobname),
                    "jobcount": str(jobcount), "previous_status": ""}
        run = background_jobs.describe_job_run(rows[0])
        refusal = background_jobs.deletion_refusal(
            run, guard["statuses"], owner=expected_owner, client=expected_client)
        if refusal:
            raise AssertionError(refusal)
        user = self._xbp_external_user(alias, external_user)
        with self._xbp_session(alias):
            _, failing = self._call_xbp(
                "BAPI_XBP_JOB_DELETE", alias, JOBNAME=str(jobname),
                JOBCOUNT=str(jobcount), EXTERNAL_USER_NAME=user)
        if failing:
            raise AssertionError(
                bapi_return.format_bapi_failure("BAPI_XBP_JOB_DELETE", failing))
        if self._job_rows(jobname, alias, ("JOBCOUNT",), str(jobcount)):
            raise AssertionError(
                "BAPI_XBP_JOB_DELETE a répondu sans erreur, mais le run %s/%s "
                "est toujours dans TBTCO : suppression NON constatée."
                % (jobname, jobcount))
        logger.info("Job %s/%s (%s) supprimé, absence relue dans TBTCO."
                    % (jobname, jobcount, run["status"]))
        return {"deleted": True, "jobname": str(jobname),
                "jobcount": str(jobcount), "previous_status": run["status"]}

    def wait_for_background_job(self, jobname: str, alias: str = "default",
                                timeout: str = "10m", poll: str = "5s",
                                jobcount: Optional[str] = None) -> dict[str, Any]:
        """Attend la fin d'un *job de fond* (facturation, IDoc, génération
        de données…) en lisant la table ``TBTCO`` via ``RFC_READ_TABLE``
        (remote-enabled partout, aucun écran occupé). Succès quand plus aucun
        run du job n'est dans le pipeline (P/S/Y/R) et qu'au moins un est
        ``F`` (fini) : retourne ``{"state": "done", "statuses",
        "waited_seconds"}``. Un run annulé (``A``) = échec immédiat ; timeout
        = échec actionnable (statuts vus, suggestion ``jobcount=`` si
        plusieurs runs portent ce nom, journal SM37). Nécessite une connexion
        `Open Rfc Connection` sur ``alias``.

        Exemple :
        | ${run}=    `Get Background Job Run`    SAPFX_JOB_20261001_130542    alias=a4h
        | ${outcome}=    `Wait For Background Job`    ${run}[jobname]    alias=a4h
        | ...    timeout=2m    poll=5s    jobcount=${run}[jobcount]
        | Should Be Equal    ${outcome}[state]    done
        """
        if self._rfc_connections().get(alias) is None:
            raise RuntimeError(
                "Aucune connexion RFC '%s' : appeler Open Rfc Connection "
                "d'abord (Wait For Background Job lit TBTCO via "
                "RFC_READ_TABLE)." % alias)
        secs = timestr_to_secs(timeout)
        step = timestr_to_secs(poll)
        options = ["JOBNAME EQ %s" % rfc_tables.abap_quote(jobname)]
        if jobcount:
            options.append("AND JOBCOUNT EQ %s" % rfc_tables.abap_quote(jobcount))
        params = rfc_tables.read_table_params("TBTCO", ["STATUS"], options)
        started = time.monotonic()
        state: dict[str, Any] = {
            "verdict": {"state": "missing", "detail": "aucune sonde encore"},
            "counts": {}, "error": None}

        def probe() -> bool:
            try:
                result = self.call_rfc("RFC_READ_TABLE", alias=alias, **params)
            except Exception as err:
                state["error"] = str(err)
                return False
            rows = rfc_tables.parse_read_table(result)
            counts = rfc_tables.summarize_job_statuses(rows)
            state["verdict"] = rfc_tables.job_wait_verdict(counts)
            state["counts"] = counts
            state["error"] = None
            return state["verdict"]["state"] in ("done", "aborted")

        poll_until(probe, secs, max(0.1, step))
        verdict = state["verdict"]
        waited = round(time.monotonic() - started, 2)
        if verdict["state"] == "done":
            return {"state": "done", "statuses": state["counts"],
                    "waited_seconds": waited}
        # La marque `issue=<état>` est STABLE (les cinq états de
        # `Get Background Job Status`, jamais traduits) : une suite juge
        # l'issue sur elle, pas sur la prose (revue ISTQB du 2026-10-01, qui a
        # relevé qu'une attente rangeant P en « hors carte » passait).
        issue = background_jobs.job_state(state["counts"])["state"]
        if verdict["state"] == "aborted":
            raise AssertionError(
                "Le job de fond '%s' a été annulé (statut A, issue=aborted). %s "
                "Journal détaillé : SM37." % (jobname, verdict["detail"]))
        raise AssertionError(
            "Le job de fond '%s' n'a pas fini après %s (issue=%s) : %s%s Préciser "
            "jobcount= si plusieurs runs portent ce nom ; journal : SM37."
            % (jobname, timeout, issue, verdict["detail"],
               " Dernière erreur RFC : %s." % state["error"]
               if state["error"] else ""))

    def get_background_job_status_model(self) -> dict[str, Any]:
        """Ce que cette bibliothèque *cartographie* des statuts de job de
        fond : ``{"labels": {"F": "finished", "A": "cancelled"…}, "pending":
        ["P", "S", "Y", "R"]}``, c'est-à-dire exactement ce qui fonde le
        verdict de `Wait For Background Job`.

        Sert à lire un décompte de statuts sans deviner, et surtout à établir
        qu'un statut rencontré n'est PAS cartographié ici. Le domaine
        ``BTCSTATUS`` est un ``CHAR1`` sans liste de valeurs dans le
        dictionnaire : ce que cette table ne contient pas ne s'invente pas, et
        l'attente le traite en continuant d'attendre plutôt qu'en concluant au
        succès.

        Exemple :
        | ${model}=    `Get Background Job Status Model`
        | Should Be Equal    ${model}[labels][F]    finished
        """
        return {"labels": dict(rfc_tables.JOB_STATUS_LABELS),
                "pending": list(rfc_tables.PENDING_JOB_STATUSES)}

    def find_background_job_cases(self, alias: str = "default",
                                  rowcount: int = 0) -> dict[str, Any]:
        """Lit le journal des jobs (``TBTCO``) et le rend comme un *catalogue
        de cas d'attente* : quels jobs de CETTE cible produiraient chacune des
        issues de `Wait For Background Job`.

        Retourne ``{"rows", "statuses", "jobs", "cases"}`` : le nombre de runs
        lus, le décompte global par statut, le décompte par job, et les jobs
        classés par cas (``done``, ``aborted``, ``aborted_with_finished``,
        ``pipeline``, ``unmapped``).

        La perception qui manquait à l'attente : elle permet d'éprouver toutes
        ses issues en *lecture seule*, sur les jobs d'exploitation que le
        système porte déjà, sans créer ni annuler quoi que ce soit, et sans
        graver dans une suite des noms de jobs qui sont ceux d'une image donnée.

        ``rowcount`` borne la lecture, et vaut 0 (tout le journal) à dessein :
        un plafond ne tronque pas seulement le résultat, il *fausse la
        classification*. Mesuré sur une cible réelle, les 200 premières lignes
        d'un journal qui en portait 4719 étaient toutes ``F`` et faisaient
        conclure que le système ne portait que des jobs terminés.

        Exemple :
        | ${catalogue}=    `Find Background Job Cases`    alias=a4h
        | Log    ${catalogue}[cases]
        """
        rows = self.read_rfc_table("TBTCO", ["JOBNAME", "STATUS"], alias=alias,
                                   rowcount=int(rowcount))
        grouped = rfc_tables.group_job_statuses(rows)
        return {"rows": len(rows),
                "statuses": rfc_tables.summarize_job_statuses(rows),
                "jobs": grouped,
                "cases": rfc_tables.job_wait_cases(grouped)}
