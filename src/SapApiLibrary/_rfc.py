"""Mixin RFC et BAPI (optionnel) : pyrfc si installe, erreur actionnable sinon.

`Open Rfc Connection` / `Call Rfc` (SAP NW RFC SDK requis, jamais de
dependance dure), le pattern **BAPI** au-dessus (`Call Bapi` juge par TYPE de
BAPIRET2, convention #3 ; `Commit/Rollback Bapi Transaction` ferment la LUW)
et `Wait For Background Job` (TBTCO via RFC_READ_TABLE, verdicts purs dans
``sapfx_common.rfc_tables``).

Extrait de ``SapApiLibrary.py`` (convention #13).
"""
from __future__ import annotations

import time
from typing import Any, Optional

from robot.utils import timestr_to_secs

from sapfx_common import bapi_return, rfc_tables
from sapfx_common.polling import poll_until
from sapfx_common.secrets import reveal_secret

from ._core import _ApiCore
from ._http import _as_bool


class RfcKeywords(_ApiCore):
    """Mixin de :class:`SapApiLibrary` : le canal RFC/BAPI optionnel."""

    def open_rfc_connection(self, alias: str = "default", **params: Any) -> str:
        """Ouvre une connexion RFC via `pyrfc` (``ashost=``, ``sysnr=``,
        ``client=``, ``user=``, ``passwd=``...). Échec explicite avec la marche
        à suivre si `pyrfc`/le SDK NW RFC ne sont pas installés : le RFC reste
        **optionnel**, rien d'autre dans la bibliothèque n'en dépend."""
        try:
            import pyrfc
        except ImportError:
            raise RuntimeError(
                "Call Rfc a besoin de pyrfc (et du SAP NW RFC SDK) : "
                "pip install pyrfc, voir https://github.com/SAP/PyRFC. "
                "Les keywords OData, eux, fonctionnent sans.")
        self._rfc_connections()[alias] = pyrfc.Connection(
            **{name: reveal_secret(value) for name, value in params.items()})
        return alias

    def call_rfc(self, function_name: str, alias: str = "default",
                 **params: Any) -> Any:
        """Appelle le module fonction ``function_name`` sur la connexion RFC
        ``alias`` (ouverte par `Open Rfc Connection`) et retourne le résultat
        (dict pyrfc)."""
        connection = self._rfc_connections().get(alias)
        if connection is None:
            raise RuntimeError(
                "Aucune connexion RFC '%s' : appeler Open Rfc Connection "
                "d'abord." % alias)
        return connection.call(function_name, **params)

    def call_bapi(self, function_name: str, alias: str = "default",
                  return_key: str = "RETURN", **params: Any) -> Any:
        """Appelle une **BAPI** et vérifie sa table ``RETURN`` (BAPIRET2) :
        un message de type ``E``/``A``/``X`` = échec listant les messages
        bloquants (décision par TYPE, jamais par texte localisé : convention
        n°3) et rappelant `Rollback Bapi Transaction`. Sinon retourne le
        résultat complet (dict pyrfc). Le pattern SAP de préparation de
        données robuste : `Call Bapi` puis `Commit Bapi Transaction`."""
        result = self.call_rfc(function_name, alias=alias, **params)
        messages = bapi_return.iter_bapi_messages(result, return_key)
        failing = bapi_return.failing_messages(messages)
        if failing:
            raise AssertionError(
                bapi_return.format_bapi_failure(function_name, failing))
        return result

    def commit_bapi_transaction(self, alias: str = "default",
                                wait: bool = True) -> Any:
        """``BAPI_TRANSACTION_COMMIT`` sur la connexion RFC ``alias`` :
        rend durables les écritures des BAPIs précédentes. ``wait=True``
        (défaut) attend la fin de la mise à jour (``WAIT='X'``) : le réglage
        sûr pour enchaîner une vérification. La table RETURN est vérifiée
        comme dans `Call Bapi`."""
        params = {"WAIT": "X"} if _as_bool(wait) else {}
        return self.call_bapi("BAPI_TRANSACTION_COMMIT", alias=alias, **params)

    def rollback_bapi_transaction(self, alias: str = "default") -> Any:
        """``BAPI_TRANSACTION_ROLLBACK`` sur la connexion RFC ``alias`` :
        annule la LUW en cours (le réflexe après un `Call Bapi` en échec, et
        un teardown sûr des préparations de données interrompues)."""
        return self.call_rfc("BAPI_TRANSACTION_ROLLBACK", alias=alias)

    def wait_for_background_job(self, jobname: str, alias: str = "default",
                                timeout: str = "10m", poll: str = "5s",
                                jobcount: Optional[str] = None) -> dict[str, Any]:
        """Attend la fin d'un **job de fond** (facturation, IDoc, génération
        de données…) en lisant la table ``TBTCO`` via ``RFC_READ_TABLE``
        (remote-enabled partout, aucun écran occupé). Succès quand plus aucun
        run du job n'est dans le pipeline (P/S/Y/R) et qu'au moins un est
        ``F`` (fini) : retourne ``{"state": "done", "statuses",
        "waited_seconds"}``. Un run annulé (``A``) = échec immédiat ; timeout
        = échec actionnable (statuts vus, suggestion ``jobcount=`` si
        plusieurs runs portent ce nom, journal SM37). Nécessite une connexion
        `Open Rfc Connection` sur ``alias``."""
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
        if verdict["state"] == "aborted":
            raise AssertionError(
                "Le job de fond '%s' a été annulé (statut A). %s Journal "
                "détaillé : SM37." % (jobname, verdict["detail"]))
        raise AssertionError(
            "Le job de fond '%s' n'a pas fini après %s : %s%s Préciser "
            "jobcount= si plusieurs runs portent ce nom ; journal : SM37."
            % (jobname, timeout, verdict["detail"],
               " Dernière erreur RFC : %s." % state["error"]
               if state["error"] else ""))

    def close_rfc_connection(self, alias: str = "default") -> None:
        """Ferme la connexion RFC ``alias`` (silencieux si absente)."""
        connection = self._rfc_connections().pop(alias, None)
        if connection is not None:
            connection.close()
