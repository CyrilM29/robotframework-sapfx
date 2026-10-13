"""La garde de politique d'une instance de bibliothèque : politique en
vigueur, verrou d'environnement, approbation en attente et trace d'audit,
au-dessus des décisions pures de ``session_policy`` (backlog § 2.1,
2026-10-08).

Chaque bibliothèque en tient une (``SapEccLibrary`` pour l'écran,
``SapApiLibrary`` pour HTTP et RFC) et l'interroge AVANT le geste : un refus
lève `SessionPolicyError` sans que rien n'ait été envoyé à SAP. Sans
politique déclarée ni variable ``SAPFX_SESSION_POLICY``, le mode est ``full``
et rien ne change, sinon que les écritures sont journalisées.

Typed.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from sapfx_common import session_policy
from sapfx_common.audit_log import AuditTrail, strip_query
from sapfx_common.session_policy import SessionPolicyError


class PolicyGate:
    """Politique, approbation et trace d'une instance de bibliothèque."""

    def __init__(self, library: str, approve_keyword: str) -> None:
        self.library = library
        self.approve_keyword = approve_keyword
        self.trail = AuditTrail(library)
        self.locked = False
        self.approval: Optional[dict[str, str]] = None
        self._policy: Optional[dict[str, Any]] = None

    # -- politique ---------------------------------------------------------------------

    @property
    def policy(self) -> dict[str, Any]:
        if self._policy is None:
            imposed = session_policy.environment_policy()
            if imposed is None:
                self._policy = session_policy.normalize_policy({})
            else:
                self._policy, self.locked = imposed, True
                self._record("policy", "load", "environment", "allow",
                             "politique imposée par %s" % session_policy.ENV_VAR)
        return self._policy

    def describe(self) -> dict[str, Any]:
        view = session_policy.describe_policy(self.policy, self.locked)
        view["pending_approval"] = self.pending_approval()
        return view

    def set_policy(self, wanted: Mapping[str, Any]) -> dict[str, Any]:
        """Adopte ``wanted`` ; refusé, et journalisé, s'il relâche une
        politique verrouillée par l'environnement."""
        candidate = session_policy.normalize_policy(wanted)
        # Charger la politique AVANT de lire le verrou : sur une garde neuve,
        # c'est ce chargement qui pose ``locked`` (sinon un premier
        # `Set Session Policy` relâchait une politique d'environnement).
        current = self.policy
        if self.locked:
            refusals = session_policy.tightening_refusals(current, candidate)
            if refusals:
                reason = ("la politique imposée par %s ne se relâche pas (%s)"
                          % (session_policy.ENV_VAR, "; ".join(refusals)))
                self._record("policy", "set", "keyword", "deny", reason)
                raise SessionPolicyError("Politique refusée : %s." % reason)
        previous = current
        self._policy = candidate
        self.approval = None
        self._record("policy", "set", "keyword", "allow", "mode %s -> %s, empreinte %s"
                     % (previous["mode"], candidate["mode"],
                        session_policy.policy_hash(candidate)[:12]))
        return self.describe()

    def approve(self, reason: str, approver: str = "agent", target: str = "") -> None:
        """Approuve le PROCHAIN geste d'écriture (mode ``explore``).

        ``approver`` dit qui approuve : ``agent`` (le keyword d'approbation)
        ou ``human`` (l'outil ``sapfx_approve_write`` de la surcouche, après la
        réponse d'un humain). Sous une politique ``approval=human``, une
        approbation ``agent`` est refusée. ``target`` lie l'approbation à une
        cible (motif à ``*``, :func:`session_policy.target_matches`) : un geste
        dont la cible ne lui correspond pas est refusé et l'approbation
        tombe."""
        text = str(reason or "").strip()
        if not text:
            raise SessionPolicyError(
                "Une approbation porte sa raison : `%s` attend un texte qui dit "
                "pourquoi l'écriture qui suit est voulue." % self.approve_keyword)
        who = str(approver or "agent").strip().lower()
        if who not in session_policy.APPROVERS:
            raise ValueError("approver %r inconnu (attendus : %s)."
                             % (approver, ", ".join(session_policy.APPROVERS)))
        pattern = str(target or "").strip()
        label = pattern or "next write"
        mode = self.policy["mode"]
        if mode == "read_only":
            self._record("approval", "approve", label, "deny",
                         "aucune approbation ne permet d'écrire en read_only", who)
            raise SessionPolicyError(
                "Approbation refusée : en mode read_only aucune écriture n'est "
                "permise, approuvée ou non.")
        if self.policy["approval"] == "human" and who != "human":
            self._record("approval", "approve", label, "deny",
                         "la politique exige l'approbation d'un humain (approval=human)",
                         who)
            raise SessionPolicyError(
                "Approbation refusée : la politique exige qu'un HUMAIN approuve "
                "(approval=human), et `%s` est à la portée d'un agent. Demander "
                "l'approbation par `Ask Human To %s` (une boîte de dialogue sur le "
                "poste, pour une suite lancée par robot devant un écran) ou, dans une "
                "session d'agent, par l'outil `sapfx_approve_write` de sapfx-mcp, qui "
                "pose la question par le client MCP."
                % (self.approve_keyword, self.approve_keyword))
        self.approval = {"reason": text, "approver": who, "target": pattern}
        self._record("approval", "approve", label, "allow", text, who)

    def record_approval_refusal(self, reason: str, why: str, approver: str = "human",
                                target: str = "") -> None:
        """Journalise une approbation DEMANDÉE et non accordée (un humain qui
        refuse, un client MCP qui ne sait pas poser la question) : rien n'est
        approuvé, et une approbation en attente tombe."""
        self.approval = None
        self._record("approval", "approve", str(target or "").strip() or "next write",
                     "deny", "%s : %s" % (why, str(reason or "").strip()), approver)

    def pending_approval(self) -> Optional[dict[str, str]]:
        """L'approbation en attente (``{reason, approver, target}``) ou
        ``None``."""
        return dict(self.approval) if self.approval else None

    # -- décisions ----------------------------------------------------------------------

    def check_transaction(self, okcode: str) -> None:
        verdict, reason = session_policy.decide_transaction(self.policy, okcode)
        code = session_policy.bare_transaction(okcode)
        if code in session_policy.SYSTEM_OK_CODES:
            return
        self._record("gui", "start_transaction", code, verdict, reason)
        if verdict == "deny":
            raise SessionPolicyError("Transaction refusée par la politique de session : "
                                     "%s." % reason)

    def check_write(self, channel: str, action: str, target: str) -> None:
        pending = self.approval
        if (pending is not None and self.policy["mode"] == "explore"
                and not session_policy.target_matches(pending["target"], target)):
            self.approval = None
            reason = ("l'approbation couvrait %s, le geste vise %s : approbation annulée"
                      % (pending["target"], target))
            self._record(channel, action, target, "deny", reason, pending["approver"])
            raise SessionPolicyError(
                "Écriture refusée (%s) : %s. Approuver ce geste-là, avec sa cible, "
                "avant de le refaire." % (target, reason))
        verdict, reason = session_policy.decide_write(self.policy, pending is not None)
        approver = ""
        if verdict == "allow" and pending is not None:
            reason = "%s : %s" % (reason, pending["reason"])
            approver = pending["approver"]
            self.approval = None
        self._record(channel, action, target, verdict, reason, approver)
        if verdict == "confirm":
            raise SessionPolicyError(
                "Écriture refusée faute d'approbation (%s, mode explore) : appeler "
                "`%s` avec la raison de ce geste juste avant lui." % (target,
                                                                      self.approve_keyword))
        if verdict == "deny":
            raise SessionPolicyError("Écriture refusée par la politique de session "
                                     "(%s) : %s." % (target, reason))

    def check_save_gesture(self, vkey: Optional[int] = None,
                           element_id: Optional[str] = None,
                           transaction: str = "") -> None:
        """Le geste d'enregistrement de l'écran ; ``transaction`` (celle de
        l'écran, lue par l'appelant) préfixe la cible, ce qui permet de lier
        une approbation à une transaction (``SE16 *``)."""
        if session_policy.is_save_gesture(vkey=vkey, element_id=element_id):
            gesture = element_id if element_id else "vkey %s" % vkey
            code = str(transaction or "").strip().upper()
            target = "%s %s" % (code, gesture) if code else str(gesture)
            self.check_write("gui", "save", target)

    def check_http(self, method: str, path: str, body: Any = None) -> None:
        if session_policy.is_write_request(method, path, body):
            self.check_write("http", "write", "%s %s" % (str(method).upper(),
                                                         strip_query(path)))

    def check_rfc(self, function: str) -> None:
        name = str(function or "").strip().upper()
        if session_policy.function_blocked(self.policy, name):
            reason = "module %s bloqué par la politique" % name
            self._record("rfc", "call", name, "deny", reason)
            raise SessionPolicyError("Appel RFC refusé par la politique de session : "
                                     "%s." % reason)
        if session_policy.is_write_function(self.policy, name):
            self.check_write("rfc", "call", name)

    def _record(self, channel: str, action: str, target: str, decision: str,
                reason: str, approver: str = "") -> None:
        policy = self._policy or session_policy.normalize_policy({})
        self.trail.record(channel, action, target, decision, reason, policy["mode"],
                          session_policy.policy_hash(policy), approver)


def gate_for(owner: Any, library: str, approve_keyword: str) -> PolicyGate:
    """La garde de ``owner`` (une instance de bibliothèque), créée au premier
    besoin : les mixins qui l'interrogent n'ont pas à savoir qui l'a posée."""
    gate = getattr(owner, "_sapfx_policy_gate", None)
    if gate is None:
        gate = PolicyGate(library, approve_keyword)
        owner._sapfx_policy_gate = gate
    return gate
