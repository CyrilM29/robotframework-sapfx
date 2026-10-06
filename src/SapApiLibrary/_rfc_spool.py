"""Mixin du *spool* d'un job de fond par le canal RFC : du pas de job à la
demande de spool, puis au contenu, par deux voies XBP indépendantes.

Né de la fiche scénario 9 (A4H, 2026-10-01) : la bibliothèque savait
attendre un job et lire son journal, rien de ce qu'il IMPRIME. Les modules
qui le lisent à l'écran (``RSPO_RETURN_ABAP_SPOOLJOB``) ne sont pas
appelables à distance ; l'interface XBP, elle, l'est, et offre deux lectures
qui ne partagent ni leur clé ni leur format :

- `Read Job Spool` : par le pas de job (``BAPI_XBP_JOB_SPOOLLIST_READ``),
  lignes CADRÉES ;
- `Read Spool Request` : par le numéro de spool
  (``BAPI_XBP_GET_SPOOL_AS_DAT``), lignes TABULÉES.

`Get Job Spool Requests` fait le lien (``TBTCP-LISTIDENT`` puis ``TSP01``).
Un pas qui n'a rien imprimé n'a PAS de spool (``XM/E/063``), ce qui n'est
pas un spool vide : `Read Job Spool` lève alors une exception dédiée et
`Job Step Should Have No Spool` le constate par deux sources. Logique pure
dans ``sapfx_common.spool``. Typed.
"""
from __future__ import annotations

from typing import Any, Optional

from robot.api import logger

from sapfx_common import bapi_return, rfc_reads, spool
from sapfx_common.robot_args import as_optional_int

from ._rfc_jobs import RfcJobKeywords


class RfcSpoolKeywords(RfcJobKeywords):
    """Mixin de :class:`SapApiLibrary` : le spool d'un job, lu par RFC."""

    def get_job_spool_requests(self, jobname: str, jobcount: str,
                               alias: str = "default") -> list[dict[str, Any]]:
        """Les pas d'un run de job et leur spool : une entrée par pas
        ``{step, program, variant, user, spool_id, owner, client,
        created_at, title}``, triée par pas.

        ``spool_id`` vaut ``None`` (jamais ``0``) pour un pas qui n'a rien
        imprimé ; les champs de la demande (``TSP01``) restent alors vides.
        ``created_at`` est ``TSP01-RQCRETIME`` en ``AAAAMMJJhhmmss``, heure
        SYSTÈME (SP01 affiche l'heure du fuseau de l'utilisateur : ne jamais
        comparer les deux). ``title`` est le titre que montre SP01
        (``LIST1S SHOWCOLO_DEV`` : programme tronqué à huit caractères), un
        indice, jamais une preuve : le programme est ``program``
        (``TBTCP-PROGNAME``). Un numéro de spool non nul ABSENT de ``TSP01``
        (demande supprimée par une réorganisation) ÉCHOUE en le disant, au
        lieu de passer pour « pas de spool ».

        Exemple :
        | ${run}=    `Get Background Job Run`    SAPFX_JOB_20261001_130542    alias=a4h
        | ${steps}=    `Get Job Spool Requests`    ${run}[jobname]    ${run}[jobcount]    alias=a4h
        | Should Be Equal    ${steps}[0][program]    SHOWCOLO
        """
        options = rfc_reads.build_options([("JOBNAME", str(jobname)),
                                           ("JOBCOUNT", str(jobcount))])
        steps = self.read_rfc_table("TBTCP", list(spool.STEP_FIELDS),
                                    alias=alias, options=options)
        if not steps:
            raise AssertionError(
                "Aucun pas pour le job %s/%s dans TBTCP : run inexistant "
                "(vérifier le JOBCOUNT par Get Background Job Run)."
                % (jobname, jobcount))
        entries = []
        for step in sorted(steps, key=lambda row: int(str(row.get("STEPCOUNT", "0")).strip() or 0)):
            spool_id = spool.spool_id_of(step.get("LISTIDENT"))
            spool_row = None
            if spool_id is not None:
                rows = self.read_rfc_table(
                    "TSP01", list(spool.SPOOL_FIELDS), alias=alias,
                    options=["RQIDENT EQ %d" % spool_id])
                if not rows:
                    raise AssertionError(spool.missing_spool_message(
                        str(jobname), str(jobcount), step))
                spool_row = rows[0]
            entries.append(spool.describe_step_spool(step, spool_row))
        return entries

    def read_job_spool(self, jobname: str, jobcount: str, step: Any = 1,
                       alias: str = "default",
                       external_user: Optional[str] = None) -> dict[str, Any]:
        """Lit le spool d'UN pas de job par ``BAPI_XBP_JOB_SPOOLLIST_READ``
        (session XBP partagée) : ``{lines, line_count, non_blank_lines}``,
        lignes CADRÉES telles que la liste s'imprime, blancs de fin retirés,
        lignes vides conservées.

        Un pas sans spool lève ``JobStepWithoutSpoolError`` en nommant
        ``XM/E/063`` : jamais une liste vide, parce qu'un rapport qui n'a rien
        produit n'est pas un rapport qui n'avait rien à dire. Un pas ABSENT
        du job lève ``JobStepNotFoundError`` en nommant ``XM/E/220`` et les
        pas existants. ``step`` est converti en entier ici (pyrfc refuse une
        chaîne pour ``STEP_NUMBER``, et via rf-mcp tout arrive en chaîne).

        Exemple :
        | ${run}=    `Get Background Job Run`    SAPFX_JOB_20261001_130542    alias=a4h
        | ${spool}=    `Read Job Spool`    ${run}[jobname]    ${run}[jobcount]    step=1    alias=a4h
        | Should Be True    ${spool}[non_blank_lines] > 0
        """
        step_number = as_optional_int(step, "step") or 1
        user = self._xbp_external_user(alias, external_user)
        with self._xbp_session(alias):
            result, failing = self._call_xbp(
                "BAPI_XBP_JOB_SPOOLLIST_READ", alias, JOBNAME=str(jobname),
                JOBCOUNT=str(jobcount), STEP_NUMBER=step_number,
                EXTERNAL_USER_NAME=user)
        identities = {bapi_return.message_identity(m) for m in failing}
        if spool.XM_NO_SPOOL_FOR_STEP in identities:
            raise spool.JobStepWithoutSpoolError(
                "Le pas %d du job %s/%s n'a produit AUCUN spool (%s) : ce n'est "
                "pas un spool vide, le programme n'a rien imprimé."
                % (step_number, jobname, jobcount, spool.XM_NO_SPOOL_FOR_STEP))
        if spool.XM_STEP_NOT_IN_JOB in identities:
            steps = [str(row.get("STEPCOUNT", "")).strip() for row in self.read_rfc_table(
                "TBTCP", ["STEPCOUNT"], alias=alias, options=rfc_reads.build_options(
                    [("JOBNAME", str(jobname)), ("JOBCOUNT", str(jobcount))]))]
            raise spool.JobStepNotFoundError(
                "Le job %s/%s n'a pas de pas %d (%s) ; pas existants : %s."
                % (jobname, jobcount, step_number, spool.XM_STEP_NOT_IN_JOB,
                   ", ".join(sorted(steps, key=lambda v: int(v or 0))) or "aucun"))
        if failing:
            raise AssertionError(bapi_return.format_bapi_failure(
                "BAPI_XBP_JOB_SPOOLLIST_READ", failing, rollback_hint=False))
        lines = spool.normalize_spool_lines(result.get("SPOOL_LIST"))
        return spool.spool_summary(lines)

    def get_spool_request_attributes(self, spool_id: Any, alias: str = "default",
                                     external_user: Optional[str] = None
                                     ) -> dict[str, Any]:
        """Les attributs d'une demande de spool par
        ``BAPI_XBP_GET_SPOOL_ATTRIBUTES`` (session XBP partagée) : ``{spool_id,
        client, owner, title, pages, created_at, device, doc_type, size,
        language}``. ``pages`` est le nombre de pages DÉCLARÉ (``SPOPAGES``),
        le total auquel une lecture se confronte pour se dire complète (mesuré
        le 2026-10-01 : 20 pages, comme la colonne Pages de SP01 ;
        ``TSP01-RQAPPRULE`` porte aussi 20 mais son libellé de dictionnaire
        est « Number of add protection rule », il n'est donc pas une source).
        Un numéro inexistant lève ``InvalidSpoolRequestError`` (``XM/E/065``).

        Exemple :
        | ${attributes}=    `Get Spool Request Attributes`    ${steps}[0][spool_id]    alias=a4h
        | Should Be Equal As Integers    ${attributes}[pages]    1
        """
        number = spool.spool_id_argument(spool_id)
        user = self._xbp_external_user(alias, external_user)
        with self._xbp_session(alias):
            result, failing = self._call_xbp(
                "BAPI_XBP_GET_SPOOL_ATTRIBUTES", alias, SPOOL_REQUEST=number,
                EXTERNAL_USER_NAME=user)
        self._raise_spool_refusal(number, failing, "BAPI_XBP_GET_SPOOL_ATTRIBUTES")
        return spool.describe_spool_attributes(result.get("SPOOL_ATTR") or {})

    def _raise_spool_refusal(self, number: int, failing: list[dict[str, Any]],
                             function_name: str, declared: int = 0) -> None:
        identities = {bapi_return.message_identity(m) for m in failing}
        if spool.XM_INVALID_SPOOL in identities:
            raise spool.InvalidSpoolRequestError(
                "Le spool %d n'existe pas (%s)." % (number, spool.XM_INVALID_SPOOL))
        if spool.XM_PAGE_OUT_OF_RANGE in identities:
            raise spool.SpoolPageOutOfRangeError(
                "La plage demandée du spool %d commence après sa dernière page "
                "(%s) ; pages déclarées : %s." % (number, spool.XM_PAGE_OUT_OF_RANGE,
                                                  declared or "?"))
        if failing:
            raise AssertionError(bapi_return.format_bapi_failure(
                function_name, failing, rollback_hint=False))

    def read_spool_request(self, spool_id: Any, first_page: Any = 1,
                           last_page: Any = 0, alias: str = "default",
                           external_user: Optional[str] = None,
                           verify_complete: Any = False
                           ) -> dict[str, Any]:
        """Lit une demande de spool par son NUMÉRO, par
        ``BAPI_XBP_GET_SPOOL_AS_DAT`` (session XBP partagée) : ``{spool_id,
        lines, line_count, non_blank_lines, cells}``, ``lines`` TABULÉES
        (cadres rendus vides) et ``cells`` le découpage de chaque ligne non
        vide par tabulation. ``last_page=0`` lit jusqu'à la fin.

        La seconde voie, indépendante de `Read Job Spool` : autre module,
        autre clé (le numéro, pas le pas de job), autre format. Un numéro
        inexistant lève ``InvalidSpoolRequestError`` en nommant
        ``XM/E/065``. Numéro et pages convertis en entiers ici (pyrfc refuse
        une chaîne).

        Depuis la revue ISTQB du 2026-10-01, la lecture se confronte au nombre
        de pages DÉCLARÉ (`Get Spool Request Attributes`) et rend aussi
        ``declared_pages``, ``first_page``, ``last_page`` (effective) et
        ``complete`` (la plage DEMANDÉE va de la page 1 à la dernière
        déclarée). ``verify_complete=True`` exige cette plage ET la preuve que
        le CONTENU rendu est entier : la dernière page déclarée, relue seule,
        doit être non vide et terminer exactement la lecture (``content_verified``
        rendu à ``True``) ; une réponse amputée de sa fin échoue (revue
        indépendante du 2026-10-01 : le drapeau seul jugeait la demande). Une
        plage inversée est refusée AVANT l'appel (XBP rendait sans refus les
        pages 5 à 20 d'une plage « 5 à 3 »), comme une plage qui DÉBORDE la
        dernière page (ramenée sinon en silence) ; une plage qui commence après
        la dernière page lève ``SpoolPageOutOfRangeError`` (``XM/E/273``).

        Exemple :
        | ${spool}=    `Read Spool Request`    ${steps}[0][spool_id]    alias=a4h    verify_complete=True
        | Should Be True    ${spool}[complete]
        """
        number = spool.spool_id_argument(spool_id)
        first = as_optional_int(first_page, "first_page")
        first = 1 if first is None else first
        last = as_optional_int(last_page, "last_page") or 0
        spool.validate_page_range(first, last)
        user = self._xbp_external_user(alias, external_user)
        verify = str(verify_complete).strip().lower() in ("1", "true", "yes", "on")
        with self._xbp_session(alias):
            declared = self.get_spool_request_attributes(number, alias, user)["pages"]
            spool.check_page_range_against_declared(first, last, declared)
            result, failing = self._call_xbp(
                "BAPI_XBP_GET_SPOOL_AS_DAT", alias, SPOOL_REQUEST=number,
                FIRST_PAGE=first, LAST_PAGE=last, EXTERNAL_USER_NAME=user)
            self._raise_spool_refusal(number, failing, "BAPI_XBP_GET_SPOOL_AS_DAT", declared)
            lines = spool.normalize_spool_lines(result.get("SPOOL_LIST"))
            summary = spool.spool_summary(lines)
            summary.update(spool_id=number, cells=spool.split_dat_cells(lines))
            summary.update(spool.page_coverage(first, last, declared))
            summary["content_verified"] = None
            if verify:
                if not summary["complete"]:
                    raise AssertionError(
                        "Lecture du spool %d NON complète : pages %d à %d sur %d "
                        "déclarées." % (number, first, summary["last_page"], declared))
                tail_result, tail_failing = self._call_xbp(
                    "BAPI_XBP_GET_SPOOL_AS_DAT", alias, SPOOL_REQUEST=number,
                    FIRST_PAGE=declared, LAST_PAGE=declared, EXTERNAL_USER_NAME=user)
                self._raise_spool_refusal(number, tail_failing,
                                          "BAPI_XBP_GET_SPOOL_AS_DAT", declared)
                tail = spool.normalize_spool_lines(tail_result.get("SPOOL_LIST"))
                if not spool.last_page_is_suffix(lines, tail):
                    raise AssertionError(
                        "Lecture du spool %d NON complète : la page %d relue seule "
                        "(%d lignes) ne termine pas la lecture entière (%d lignes), "
                        "la réponse a été amputée." % (number, declared, len(tail),
                                                       len(lines)))
                summary["content_verified"] = True
        return summary

    def job_step_should_have_no_spool(self, jobname: str, jobcount: str,
                                      step: Any = 1, alias: str = "default",
                                      external_user: Optional[str] = None
                                      ) -> dict[str, Any]:
        """Vérifie qu'un pas de job n'a produit AUCUN spool, par DEUX sources :
        ``TBTCP-LISTIDENT`` est nul ET XBP refuse la lecture par
        ``XM/E/063``. Rend ``{step, program, message_id}``. Échoue si le pas
        porte un spool, si le pas n'existe pas, ou si XBP rend des lignes (ou
        refuse autrement).

        Exemple :
        | ${run}=    `Get Background Job Run`    SAPFX_JOB_20261001_131002    alias=a4h
        | `Job Step Should Have No Spool`    ${run}[jobname]    ${run}[jobcount]    step=1    alias=a4h
        """
        step_number = as_optional_int(step, "step") or 1
        entries = self.get_job_spool_requests(jobname, jobcount, alias)
        entry = next((e for e in entries if e["step"] == step_number), None)
        if entry is None:
            raise AssertionError("Le job %s/%s n'a pas de pas %d (pas : %s)."
                                 % (jobname, jobcount, step_number,
                                    [e["step"] for e in entries]))
        if entry["spool_id"] is not None:
            raise AssertionError("Le pas %d du job %s/%s porte le spool %d."
                                 % (step_number, jobname, jobcount, entry["spool_id"]))
        try:
            content = self.read_job_spool(jobname, jobcount, step_number,
                                          alias, external_user)
        except spool.JobStepWithoutSpoolError:
            return {"step": step_number, "program": entry["program"],
                    "message_id": spool.XM_NO_SPOOL_FOR_STEP}
        raise AssertionError(
            "TBTCP ne porte aucun spool pour le pas %d du job %s/%s, mais XBP "
            "en a rendu %d lignes : les deux sources se contredisent."
            % (step_number, jobname, jobcount, content["line_count"]))

    def spool_request_should_not_exist(self, spool_id: Any,
                                       alias: str = "default",
                                       external_user: Optional[str] = None
                                       ) -> dict[str, Any]:
        """Vérifie qu'un numéro de spool n'existe pas, par DEUX sources :
        absent de ``TSP01`` ET refusé par XBP avec ``XM/E/065``. Rend
        ``{spool_id, message_id}``.

        Exemple :
        | `Spool Request Should Not Exist`    999999999    alias=a4h
        """
        number = spool.spool_id_argument(spool_id)
        if self.read_rfc_table("TSP01", ["RQIDENT"], alias=alias,
                               options=["RQIDENT EQ %d" % number]):
            raise AssertionError("Le spool %d existe dans TSP01." % number)
        try:
            self.read_spool_request(number, alias=alias, external_user=external_user)
        except spool.InvalidSpoolRequestError:
            return {"spool_id": number, "message_id": spool.XM_INVALID_SPOOL}
        raise AssertionError("Le spool %d est absent de TSP01 mais XBP l'a lu : "
                             "les deux sources se contredisent." % number)

    def lines_should_contain_in_order(self, lines: Any, *markers: Any,
                                      same_line: Any = False) -> list[dict[str, Any]]:
        """Vérifie que ``markers`` apparaissent DANS L'ORDRE dans ``lines`` et
        rend leurs positions ``[{marker, line, column}]``. ``lines`` accepte
        le résultat de `Read Job Spool` ou `Read Spool Request` (dict portant
        ``lines``), une liste de chaînes, de listes de cellules (`Read Abap
        List`) ou de dicts (`Read Abap List Rows`). Les marqueurs sont des
        sous-chaînes EXACTES : des constantes techniques, jamais du texte
        localisé. Chaque marqueur doit être sur une ligne STRICTEMENT plus
        basse que le précédent (une ligne unique portant tous les noms ne
        passe pas) ; ``same_line=True`` lève cette exigence. L'échec dit
        lequel manque, et s'il est ABSENT ou présent mais dans le DÉSORDRE.

        Exemple :
        | ${spool}=    `Read Job Spool`    ${run}[jobname]    ${run}[jobcount]    alias=a4h
        | `Lines Should Contain In Order`    ${spool}[lines]    COL_BACKGROUND    COL_HEADING    COL_NORMAL
        """
        source = lines.get("lines", []) if isinstance(lines, dict) else lines
        wanted: list[str] = []
        for marker in markers:
            if isinstance(marker, (list, tuple)):
                wanted.extend(str(m) for m in marker)
            else:
                wanted.append(str(marker))
        if not wanted:
            raise ValueError("Lines Should Contain In Order : aucun marqueur donné.")
        texts = spool.lines_text(source)
        result = spool.find_in_order(texts, wanted,
                                     same_line=str(same_line).strip().lower()
                                     in ("1", "true", "yes", "on"))
        if result["missing"]:
            raise AssertionError(spool.format_order_failure(result, len(texts)))
        logger.info("%d marqueurs trouvés dans l'ordre sur %d lignes."
                    % (len(wanted), len(texts)))
        return result["found"]
