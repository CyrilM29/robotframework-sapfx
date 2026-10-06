"""Mixin de la *session XBP* partagée : l'interface officielle des
ordonnanceurs externes (``BAPI_XMI_LOGON`` / ``BAPI_XMI_LOGOFF``), ouverte
une fois autour d'une lecture ou d'une écriture de job.

Né de la fiche scénario 9 (A4H, 2026-10-01). Le logon XBP n'est pas
réentrant : sur une connexion RFC qui porte déjà une session XMI, un second
``BAPI_XMI_LOGON`` est refusé par ``XM/E/022``. `Get Job Log` ouvrait sa
propre session sans regarder, donc il échouait dès qu'une autre lecture XBP
était en cours sur la même connexion. Ici, un refus ``XM/E/022`` RÉUTILISE
la session existante et la laisse ouverte à son propriétaire, et
``BAPI_XMI_LOGOFF`` n'est appelé que pour une session ouverte par ce
gestionnaire, TOUJOURS (une session XMI orpheline reste ouverte côté
serveur).

Extrait en module à part (convention #13) : les lectures de preuves
(``_rfc_reads.py``), les jobs (``_rfc_jobs.py``) et le spool
(``_rfc_spool.py``) s'en servent tous.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from robot.api import logger

from sapfx_common import bapi_return
from sapfx_common.spool import XM_ALREADY_LOGGED_ON, XM_NOT_LOGGED_ON

from ._bapi import BapiKeywords

#: Paramètres d'annonce XBP (interface 3.0, celle de la cible mesurée).
_XMI_LOGON = {"EXTCOMPANY": "SAPFX", "EXTPRODUCT": "SAPFX",
              "INTERFACE": "XBP", "VERSION": "3.0"}


class XbpSessionMixin(BapiKeywords):
    """Mixin interne de :class:`SapApiLibrary` : la session XBP partagée."""

    def _xbp_external_user(self, alias: str, external_user: Optional[str]) -> str:
        """L'utilisateur externe annoncé à XBP : celui donné, sinon
        l'utilisateur de la connexion RFC."""
        if external_user:
            return str(external_user)
        return str(self.get_rfc_connection_attributes(alias).get("user", ""))

    @contextmanager
    def _xbp_session(self, alias: str = "default") -> Iterator[bool]:
        """Ouvre (ou réutilise) la session XBP de la connexion ``alias`` le
        temps du bloc ; rend ``True`` quand ce bloc l'a ouverte. Tout refus
        du logon autre que ``XM/E/022`` échoue en le nommant."""
        owned = self._xbp_logon(alias)
        if not owned:
            logger.info("Session XBP déjà ouverte sur la connexion %r "
                        "(%s) : réutilisée, laissée ouverte à son propriétaire."
                        % (alias, XM_ALREADY_LOGGED_ON))
        try:
            yield owned
        finally:
            if owned:
                try:
                    self.call_rfc("BAPI_XMI_LOGOFF", alias=alias, INTERFACE="XBP")
                except Exception as error:    # noqa: BLE001 (hygiène best-effort)
                    logger.warn("BAPI_XMI_LOGOFF a échoué sur %r : %s" % (alias, error))

    def _xbp_logon(self, alias: str) -> bool:
        """Ouvre la session XBP de ``alias`` ; ``False`` si elle l'était déjà
        (``XM/E/022``), tout autre refus lève en le nommant."""
        result = self.call_rfc("BAPI_XMI_LOGON", alias=alias, **_XMI_LOGON) or {}
        failing = bapi_return.failing_messages(
            bapi_return.iter_bapi_messages(result, "RETURN"))
        if not failing:
            return True
        if {bapi_return.message_identity(m) for m in failing} == {XM_ALREADY_LOGGED_ON}:
            return False
        raise AssertionError(bapi_return.format_bapi_failure("BAPI_XMI_LOGON", failing))

    def open_xbp_session(self, alias: str = "default") -> dict[str, Any]:
        """Ouvre la session *XBP* (``BAPI_XMI_LOGON``, interface 3.0) de la
        connexion RFC ``alias`` et rend ``{"opened": bool}`` : ``False`` quand
        elle était déjà ouverte (``XM/E/022``), sans erreur. Les keywords de
        jobs et de spool ouvrent et referment la leur seuls ; celui-ci sert à
        appeler soi-même un module XBP, et à éprouver une preuve de fermeture
        (`Xbp Session Should Be Closed`) sur une session laissée ouverte. À
        refermer par `Close Xbp Session`.

        Exemple :
        | ${xbp}=    `Open Xbp Session`    alias=a4h
        | Should Be True    ${xbp}[opened]
        """
        return {"opened": self._xbp_logon(alias)}

    def close_xbp_session(self, alias: str = "default") -> dict[str, Any]:
        """Referme la session XBP de ``alias`` (``BAPI_XMI_LOGOFF``) et rend
        ``{"closed": bool}`` : ``False`` quand aucune n'était ouverte
        (``XM/E/028``, mesuré), sans erreur ; tout autre refus lève.

        Exemple :
        | ${xbp}=    `Close Xbp Session`    alias=a4h
        | Should Be True    ${xbp}[closed]
        """
        result = self.call_rfc("BAPI_XMI_LOGOFF", alias=alias, INTERFACE="XBP") or {}
        failing = bapi_return.failing_messages(
            bapi_return.iter_bapi_messages(result, "RETURN"))
        if not failing:
            return {"closed": True}
        if {bapi_return.message_identity(m) for m in failing} == {XM_NOT_LOGGED_ON}:
            return {"closed": False}
        raise AssertionError(bapi_return.format_bapi_failure("BAPI_XMI_LOGOFF", failing))

    def get_xbp_session_state(self, alias: str = "default") -> dict[str, Any]:
        """Dit si une session XBP est OUVERTE sur la connexion RFC ``alias`` :
        ``{"open": bool, "evidence"}``, sans rien changer à l'état constaté.

        Aucun module ne lit cet état : la sonde tente un logon. Refusé par
        ``XM/E/022``, il prouve une session déjà ouverte (et rien n'est
        touché) ; accepté, il prouve qu'aucune ne l'était, et la session qu'il
        vient d'ouvrir est refermée aussitôt (mesuré sur A4H le 2026-10-01 :
        second logon ``XM/E/022``, logoff sans session ``XM/E/028``). Né de la
        revue ISTQB de la campagne du scénario 9 : la session XBP étant
        désormais partagée, le refus ``XM/E/022`` qui trahissait une session
        oubliée a disparu, et une fuite ne rougissait plus nulle part.

        Exemple :
        | ${xbp}=    `Get Xbp Session State`    alias=a4h
        | Should Not Be True    ${xbp}[open]
        """
        if self._xbp_logon(alias):
            self.close_xbp_session(alias)
            return {"open": False, "evidence": "logon accepté puis refermé"}
        return {"open": True, "evidence": XM_ALREADY_LOGGED_ON}

    def xbp_session_should_be_closed(self, alias: str = "default") -> dict[str, Any]:
        """Échoue si une session XBP est restée ouverte sur la connexion RFC
        ``alias`` (voir `Get Xbp Session State`) : la moitié XBP d'une preuve
        de fermeture, à poser AVANT de fermer la connexion RFC (une session
        XMI ne survit pas à sa connexion).

        Exemple :
        | `Xbp Session Should Be Closed`    alias=a4h
        """
        state = self.get_xbp_session_state(alias)
        if state["open"]:
            raise AssertionError(
                "Une session XBP est restée ouverte sur la connexion RFC %r (%s) : "
                "un keyword ou un appel direct ne l'a pas refermée (Close Xbp "
                "Session)." % (alias, state["evidence"]))
        return state

    def _call_xbp(self, function_name: str, alias: str,
                  **params: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Appelle un module XBP DANS une session ouverte et rend le résultat
        brut et ses messages bloquants, sans lever : l'appelant décide quels
        identifiants il nomme (``XM/E/063``, ``XM/E/065``) avant le refus
        générique."""
        result = self.call_rfc(function_name, alias=alias, **params) or {}
        failing = bapi_return.failing_messages(
            bapi_return.iter_bapi_messages(result, "RETURN"))
        return result, failing
