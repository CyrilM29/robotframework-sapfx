"""Mixin de l'ATTENTE d'un statut d'IDoc et du lien sortant/entrant :
`Wait For Idoc Status` et `Get Idoc Counterpart`.

L'attente est le point où un test d'intégration asynchrone ment le plus
facilement : il prend un statut d'erreur pour un statut « en cours » et attend
jusqu'au délai, ou il prend un statut hors barème pour un succès.
`Wait For Idoc Status` juge par CODE (jamais le texte localisé), échoue tout de suite
sur un statut d'erreur en nommant le code réel, et dit à quel geste manquant
tient un délai dépassé. Verdicts et messages purs dans
``sapfx_common.idoc_status``, sur le patron de `Wait For Background Job`.

`Get Idoc Counterpart` relie un IDoc sortant à l'IDoc ENTRANT que son
bouclage tRFC a créé (ou l'inverse) par le TID de la transaction, jamais par
proximité d'horodatage.

Typed.
"""
from __future__ import annotations

import time
from typing import Any

from robot.utils import timestr_to_secs

from sapfx_common import idoc, idoc_status
from sapfx_common.polling import poll_until

from ._http import _as_bool
from ._rfc_idoc import RfcIdocKeywords


class RfcIdocWaitKeywords(RfcIdocKeywords):
    """Mixin de :class:`SapApiLibrary` : attendre un statut, relier deux IDocs."""

    def wait_for_idoc_status(self, docnum: Any, expected: Any = "success",
                             timeout: str = "30s", poll: str = "1s",
                             alias: str = "default",
                             raise_on_failure: Any = True) -> dict[str, Any]:
        """Attend qu'un IDoc atteigne un statut TERMINAL, en sondant ``EDIDC``
        (jamais de pause fixe), et rend ``{"docnum", "status", "category",
        "state", "reached", "waited_seconds", "history"}``.

        ``expected`` : ``success`` (la catégorie du barème : 03, 12, 16, 41,
        53) ou des codes précis (``53``, ``"03,12"``). ``state`` vaut
        ``reached``, ``error``, ``unmapped``, ``missing`` ou ``timeout``.

        * un statut d'ERREUR échoue TOUT DE SUITE en nommant le code réel, le
          dernier enregistrement (origine, identifiant de message, paramètres)
          et jamais « encore en cours » ;
        * un statut HORS barème n'est jamais un succès et n'est pas attendu
          indéfiniment : échec qui nomme le code ;
        * un délai dépassé nomme le dernier statut ET ce qui le fait
          normalement avancer (30 : rien ne l'a expédié, WE14 ; 64 : BD87...).

        Avec ``raise_on_failure=${False}`` le même dictionnaire est rendu sans
        lever : le cas négatif s'asserte alors sur ``status``, ``category`` et
        ``state``, pas sur un message. L'historique porte, par enregistrement,
        le statut, l'origine, le message par identifiant, ses paramètres et le
        TID.

        Exemple :
        | ${inbound}=    `Wait For Idoc Status`    6    expected=53    timeout=30s    alias=a4h
        | Should Be Equal    ${inbound}[state]    reached
        """
        number = idoc.normalize_docnum(docnum)
        idoc_status.parse_expected(expected)
        seconds = timestr_to_secs(timeout)
        step = max(0.1, timestr_to_secs(poll))
        started = time.monotonic()
        state: dict[str, Any] = {
            "verdict": {"state": "missing", "status": "", "category": "unmapped"},
            "error": None}

        def probe() -> bool:
            try:
                rows = self.read_rfc_table(
                    "EDIDC", ["DOCNUM", "STATUS"], alias=alias,
                    options=["DOCNUM EQ '%s'" % number])
            except Exception as err:
                state["error"] = str(err)
                return False
            state["error"] = None
            state["verdict"] = idoc_status.wait_verdict(
                rows[0].get("STATUS", "") if rows else "", expected)
            return state["verdict"]["state"] != "waiting"

        poll_until(probe, seconds, step)
        verdict = state["verdict"]
        waited = round(time.monotonic() - started, 2)
        history = self._idoc_history(number, alias)
        outcome = verdict["state"]
        if outcome == "waiting" or (state["error"] and outcome == "missing"):
            outcome = "timeout"
        result: dict[str, Any] = {
            "docnum": number, "status": verdict["status"],
            "category": verdict["category"], "state": outcome,
            "reached": outcome == "reached", "waited_seconds": waited,
            "history": history}
        if outcome == "reached" or not _as_bool(raise_on_failure):
            return result
        if outcome == "timeout":
            message = idoc_status.format_wait_timeout(
                number, timeout, verdict, history, expected)
            if state["error"]:
                message += " Dernière erreur RFC : %s." % state["error"]
            raise AssertionError(message)
        raise AssertionError(
            idoc_status.format_wait_failure(number, verdict, history, expected))

    def get_idoc_counterpart(self, docnum: Any, timeout: str = "30s",
                             poll: str = "1s",
                             alias: str = "default") -> dict[str, Any]:
        """Retrouve l'IDoc LIÉ à ``docnum`` : le numéro de l'autre IDoc dont un
        enregistrement de statut porte le même TID tRFC (``EDIDS-TID``).
        Rend ``{"docnum", "tid", "counterpart", "counterpart_direction",
        "counterpart_status"}``.

        Sur A4H, le statut 03 d'un sortant et le premier statut de l'entrant
        que son bouclage crée portent le MÊME TID (deux chaînes sur deux) ;
        aucune heuristique d'horodatage n'est utilisée, deux envois dans la
        même seconde ne se départageraient pas. L'entrant naît dans la seconde
        du 03 : l'attente jusqu'à ``timeout`` couvre ce délai.

        Échecs actionnables : IDoc sans TID (il n'a pas été expédié, son
        statut est nommé), aucun entrant après le délai (tRFC, moniteur
        SM58), plusieurs candidats (listés).

        Exemple :
        | ${link}=    `Get Idoc Counterpart`    5    alias=a4h
        | Should Be Equal    ${link}[counterpart_status]    53
        """
        number = idoc.normalize_docnum(docnum)
        history = self._idoc_history(number, alias)
        tids = idoc_status.tids_of(history)
        if not tids:
            current = self.read_rfc_table(
                "EDIDC", ["STATUS"], alias=alias, options=["DOCNUM EQ '%s'" % number])
            raise AssertionError(
                "L'IDoc %s n'a aucun TID dans son historique (statut %s) : il "
                "n'a pas été expédié, donc aucun IDoc lié n'existe encore."
                % (number, current[0]["STATUS"] if current else "inexistant"))
        found: dict[str, Any] = {"by_tid": {}}

        def probe() -> bool:
            # TOUS les TID à chaque sondage : un IDoc retransmis en porte
            # plusieurs, et s'arrêter au premier ignorerait en silence
            # l'entrant du second.
            by_tid: dict[str, list[str]] = {}
            for tid in tids:
                rows = self.read_rfc_table(
                    "EDIDS", ["DOCNUM", "COUNTR", "STATUS"], alias=alias,
                    options=["TID EQ '%s'" % tid])
                candidates = idoc_status.counterpart_candidates(number, rows)
                if candidates:
                    by_tid[tid] = candidates
            found["by_tid"] = by_tid
            return bool(by_tid)

        poll_until(probe, timestr_to_secs(timeout), max(0.1, timestr_to_secs(poll)))
        by_tid = found["by_tid"]
        if not by_tid:
            raise AssertionError(
                "Aucun IDoc lié à %s (TID %s) après %s : l'envoi tRFC n'a pas "
                "créé son vis-à-vis (moniteur SM58, destination du port)."
                % (number, ", ".join(tids), timeout))
        candidates = sorted({other for others in by_tid.values() for other in others})
        if len(candidates) > 1:
            raise AssertionError(
                "Plusieurs IDocs sont liés à %s (%s) : %s. Départager par le "
                "type de message ou la direction."
                % (number, "; ".join("TID %s -> %s" % (tid, ", ".join(others))
                                     for tid, others in sorted(by_tid.items())),
                   ", ".join(candidates)))
        found["tid"] = next(iter(sorted(by_tid)))
        other = candidates[0]
        row = self.read_rfc_table(
            "EDIDC", ["DOCNUM", "STATUS", "DIRECT"], alias=alias,
            options=["DOCNUM EQ '%s'" % other])
        return {"docnum": number, "tid": found["tid"], "counterpart": other,
                "counterpart_direction": row[0]["DIRECT"] if row else "",
                "counterpart_status": row[0]["STATUS"] if row else ""}

    def _idoc_history(self, docnum: str, alias: str) -> list[dict[str, str]]:
        """L'historique ``EDIDS`` d'un IDoc, dans l'ordre des compteurs."""
        rows = self.read_rfc_table(
            "EDIDS", list(idoc_status.HISTORY_FIELDS), alias=alias,
            options=["DOCNUM EQ '%s'" % docnum])
        return sorted(rows, key=lambda row: str(row.get("COUNTR", "")))
