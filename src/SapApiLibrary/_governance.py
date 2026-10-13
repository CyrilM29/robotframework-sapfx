"""Mixin de gouvernance des canaux HTTP et RFC : `Set Api Policy`,
`Get Api Policy`, `Approve Next Api Write` et `Get Api Audit Trail` (backlog
§ 2.1, 2026-10-08).

La politique décide AVANT le geste, aux deux points de passage du canal :
chaque requête HTTP (une méthode autre que ``GET``/``HEAD``, sauf un
``$batch`` sans partie d'écriture, est une ÉCRITURE) et chaque appel RFC (un
module hors de la liste de LECTURE est une écriture : un appel RFC synchrone
valide en base à son retour). Un refus lève `SessionPolicyError` sans que
rien ne parte sur le réseau. Logique pure dans
``sapfx_common.session_policy``.

Depuis le 2026-10-09 (backlog § 2.1, point 1), une politique peut exiger
qu'un HUMAIN approuve (``approval=human``) : `Approve Next Api Write` est
alors refusé, et l'approbation vient de l'outil ``sapfx_approve_write`` de la
surcouche ``sapfx-mcp``. Une approbation peut être liée à une cible
(``target=POST /sap/opu/odata/sap/SEPMRA_SHOP/*``, ``target=BAPI_TRANSACTION_COMMIT``).

Typed.
"""
from __future__ import annotations

from typing import Any, Optional

from sapfx_common import approval_request
from sapfx_common.policy_gate import PolicyGate, gate_for
from sapfx_common.session_policy import load_policy_file, normalize_policy

from ._core import _ApiCore

LIBRARY = "SapApiLibrary"
APPROVE_KEYWORD = "Approve Next Api Write"


class ApiGovernanceKeywords(_ApiCore):
    """Mixin de :class:`SapApiLibrary` : politique et audit des écritures."""

    def _gate(self) -> PolicyGate:
        return gate_for(self, LIBRARY, APPROVE_KEYWORD)

    def set_api_policy(self, mode: str = "full", read_functions: Any = None,
                       blocked_functions: Any = None,
                       policy_file: Optional[str] = None,
                       approval: Optional[str] = None) -> dict[str, Any]:
        """Fixe la politique des canaux HTTP et RFC et rend sa vue (comme
        `Get Api Policy`).

        ``mode`` : ``full`` (défaut : tout passe, les écritures sont
        journalisées), ``explore`` (chaque écriture exige
        `Approve Next Api Write` juste avant elle) ou ``read_only`` (toute
        écriture refusée, avant le réseau). Une ÉCRITURE est une requête HTTP
        autre que ``GET`` ou ``HEAD`` (un ``$batch`` ne compte que s'il porte une
        partie qui écrit), ou l'appel d'un module RFC hors de la liste de
        LECTURE : les modules qu'appellent les keywords de lecture de la
        bibliothèque (``read_functions_preset`` de `Get Api Policy`), plus
        ``read_functions`` (liste ou chaîne à virgules, ``*`` admis). Un
        appel RFC synchrone valide en base à son retour, donc seule une liste
        blanche tient ; elle est une DÉCLARATION, pas une preuve qu'un module
        n'écrit pas. ``blocked_functions`` ne passent jamais, quel que soit le
        mode. ``policy_file`` : un fichier JSON, à la place des autres
        arguments. ``approval`` : qui approuve une écriture en ``explore``,
        ``agent`` (`Approve Next Api Write` suffit) ou ``human`` (ce keyword
        est refusé, l'approbation vient de l'outil ``sapfx_approve_write`` de
        ``sapfx-mcp``) ; omis, il garde la valeur en vigueur.

        Une politique imposée par ``SAPFX_SESSION_POLICY`` est VERROUILLÉE :
        ce keyword peut la durcir, jamais la relâcher. Un garde-fou
        d'exploitation, PAS un contrôle de sécurité : la barrière reste
        l'autorisation SAP de l'utilisateur.

        Exemple :
        | ${policy}=    `Set Api Policy`    mode=read_only    read_functions=BAPI_FLIGHT_GETLIST
        | Should Be Equal    ${policy}[mode]    read_only
        | Run Keyword And Expect Error    REGEXP:.+refusée en mode read_only.+
        | ...    `Call Rfc`    BAPI_TRANSACTION_COMMIT    alias=a4h
        | `Set Api Policy`    mode=explore    approval=human
        | Run Keyword And Expect Error    REGEXP:.+sapfx_approve_write.+
        | ...    `Approve Next Api Write`    close the empty LUW
        """
        gate = self._gate()
        if policy_file:
            if read_functions not in (None, "") or blocked_functions not in (None, "") \
                    or approval not in (None, "") or mode != "full":
                raise ValueError("policy_file remplace les autres arguments : ne pas "
                                 "les combiner.")
            wanted = load_policy_file(str(policy_file))
        else:
            wanted = {"mode": mode,
                      "approval": approval if approval not in (None, "")
                      else gate.policy["approval"],
                      "transactions": gate.policy["transactions"],
                      "functions": {"read": read_functions, "blocked": blocked_functions}}
        return gate.set_policy(normalize_policy(wanted))

    def get_api_policy(self) -> dict[str, Any]:
        """La politique en vigueur sur les canaux HTTP et RFC : ``{"mode",
        "approval", "transactions", "functions", "hash", "locked",
        "read_functions_preset", "pending_approval"}``.

        Exemple :
        | ${policy}=    `Get Api Policy`
        | Should Contain    ${policy}[read_functions_preset]    RFC_READ_TABLE
        | Should Be Equal    ${policy}[pending_approval]    ${None}
        """
        return self._gate().describe()

    def approve_next_api_write(self, reason: str, target: str = "") -> None:
        """Approuve la PROCHAINE écriture HTTP ou RFC, en mode ``explore`` :
        consommée par ce geste, sa raison part dans le journal d'audit avec
        lui. Refusée en ``read_only`` ; sans objet en ``full`` ; refusée sous
        une politique ``approval=human``, où l'approbation vient d'un humain,
        par `Ask Human To Approve Next Api Write` (une boîte de dialogue sur le
        poste) ou par l'outil ``sapfx_approve_write`` de ``sapfx-mcp`` (une
        session d'agent).

        ``target`` lie l'approbation à une cible, motif où seul ``*`` est un
        joker, sans casse : une méthode et un chemin sans requête
        (``POST /sap/opu/odata/sap/SEPMRA_SHOP/*``) ou un nom de module
        (``BAPI_TRANSACTION_COMMIT``). Une écriture hors de la cible est
        refusée avant le réseau, et l'approbation tombe.

        Exemple :
        | `Set Api Policy`    mode=explore
        | `Approve Next Api Write`    close the empty LUW    target=BAPI_TRANSACTION_COMMIT
        | `Call Rfc`    BAPI_TRANSACTION_COMMIT    alias=a4h
        """
        self._gate().approve(reason, target=target)

    def ask_human_to_approve_next_api_write(self, reason: str,
                                            target: str = "") -> dict[str, str]:
        """Demande à un HUMAIN, par une boîte de dialogue sur le poste,
        d'approuver la prochaine écriture HTTP ou RFC, et ne l'approuve (au
        nom de ``human`` dans le journal d'audit) que s'il TAPE le mot
        ``approuver`` (un clic ne peut pas approuver ; toute autre saisie, ou
        Annuler, refuse) ; rend l'approbation ``{reason, approver, target}``.
        C'est la voie d'approbation d'une suite lancée par ``robot`` sous une
        politique ``approval=human``, où `Approve Next Api Write` est
        refusé ; dans une session d'agent, la même question passe par l'outil
        ``sapfx_approve_write`` de ``sapfx-mcp``.

        La boîte montre la raison, la cible couverte (``POST /chemin``, un
        module RFC, motif à ``*``), la politique, les sessions API et les
        connexions RFC ouvertes. Un refus, une fenêtre fermée ou un poste sans
        écran (une CI) échouent FERMÉ, la demande refusée étant journalisée ;
        en ``read_only`` rien n'est demandé, rien ne s'écrit.

        Exemple :
        | `Set Api Policy`    mode=explore    approval=human
        | ${approval}=    `Ask Human To Approve Next Api Write`    create one test travel    target=POST /sap/opu/odata4/*
        | Should Be Equal    ${approval}[approver]    human
        """
        context: dict[str, Any] = {"unread": {}}
        try:
            composed: Any = self              # keyword de la classe composée
            state = composed.list_api_sessions()
            context["api_sessions"] = [
                {key: entry.get(key) for key in ("alias", "base_url", "sap_client")}
                for entry in (state or {}).get("api_sessions", [])]
            context["rfc_connections"] = list((state or {}).get("rfc_connections", []))
        except Exception as exc:          # noqa: BLE001 (best-effort, nommé)
            context["unread"]["api_sessions"] = str(exc)
        return approval_request.ask_human_approval(
            self._gate(), "SapApiLibrary", reason, target, context,
            keyword="Ask Human To Approve Next Api Write")

    def get_api_audit_trail(self) -> list[dict[str, Any]]:
        """La trace d'audit des canaux HTTP et RFC depuis l'import : une entrée
        par décision qui compte (politique, approbation, écriture permise,
        approuvée ou refusée), ``{"timestamp", "library", "channel",
        "action", "target", "decision", "reason", "mode", "policy_hash",
        "approver", "test"}``, ``approver`` (``agent`` ou ``human``) sur une
        approbation et l'écriture qu'elle autorise. La cible est une méthode et un chemin sans requête, ou un
        nom de module : jamais un corps ni un paramètre. Avec
        ``SAPFX_AUDIT_LOG=<chemin>``, les mêmes entrées s'ajoutent à un
        fichier JSONL cumulatif.

        Exemple :
        | ${trail}=    `Get Api Audit Trail`
        | Should Be Equal    ${trail}[-1][target]    BAPI_TRANSACTION_COMMIT
        | Should Be Equal    ${trail}[-1][approver]    human
        """
        return self._gate().trail.snapshot()
