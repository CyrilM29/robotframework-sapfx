"""L'approbation d'une écriture par un HUMAIN : ce qu'on lui montre, comment
on lui pose la question, et ce que sa réponse décide (backlog § 2.1,
2026-10-09).

Deux canaux posent la même question avec le même texte : l'outil
``sapfx_approve_write`` de la surcouche ``sapfx-mcp`` (une élicitation MCP,
pour une session d'agent) et les keywords `Ask Human To Approve Next Write`
(SapEccLibrary) et `Ask Human To Approve Next Api Write` (SapApiLibrary),
qui ouvrent une boîte de dialogue sur le POSTE par la bibliothèque
``Dialogs`` de Robot Framework, pour une suite lancée par ``robot`` devant
un humain. Sur le poste, l'humain TAPE le mot ``approuver`` : un clic ne
peut pas approuver par erreur (décision du 2026-10-09, après un premier run
où le choix dans une liste dépendait de l'endroit où tombait le clic). Sans eux, une politique ``approval=human`` livrée dans les
paquets PyPI n'avait aucun moyen d'approuver hors de la surcouche, privée.

La demande MONTRE ce qui va être approuvé : la raison, la CIBLE couverte
(motif à ``*`` ; sur l'écran, sans cible, la transaction affichée, ``SE16
*``), la politique (mode, empreinte) et ce qui a pu être lu de la session
(système, mandant, utilisateur, écran ; sessions API et connexions RFC).
Seule la réponse ``approuver`` (tapée sur le poste) enregistre une
approbation, au nom de ``human`` ; un refus, une fenêtre fermée ou un poste SANS ÉCRAN (une CI, une
session sans affichage) échouent FERMÉ, et la demande refusée est
journalisée. Ce n'est pas un contrôle de sécurité : c'est ce qui rend la
décision humaine possible, visible et tracée. Typed.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from .session_policy import SessionPolicyError

APPROVE = "approuver"
REFUSE = "refuser"
CHOICES = [APPROVE, REFUSE]

#: Au-delà, la demande est coupée (un dialogue affiche un texte, pas un rapport).
MAX_MESSAGE_CHARS = 1800

#: Pose la question (message, choix) et rend le choix ; lève si personne ne répond.
Ask = Callable[[str, list[str]], str]


def default_target(library: str, target: str, context: Mapping[str, Any]) -> str:
    """La cible effectivement approuvée : celle donnée, sinon, sur l'écran,
    la transaction affichée (``SE16 *``), sinon aucune (toute écriture)."""
    wanted = str(target or "").strip()
    if wanted:
        return wanted
    transaction = str((context.get("screen") or {}).get("transaction") or "").strip()
    if library == "SapEccLibrary" and transaction:
        return "%s *" % transaction.upper()
    return ""


def build_message(library: str, policy: Mapping[str, Any], reason: str, target: str,
                  context: Mapping[str, Any], requester: str = "l'agent",
                  typed: bool = False) -> str:
    """Le texte montré à l'humain : ce qui va être approuvé, où, et pourquoi.
    ``typed`` : la réponse se TAPE (poste) au lieu de se choisir (client MCP)."""
    lines = [
        "SAPFX demande l'approbation d'UNE écriture.",
        "",
        "Raison donnée par %s : %s" % (requester, reason),
        "Cible couverte : %s" % (target or "toute écriture (aucune cible donnée)"),
        "Canal : %s, politique %s (empreinte %s)"
        % (library, policy.get("mode", "?"), str(policy.get("hash", ""))[:12]),
    ]
    sap = context.get("session") or {}
    if sap:
        lines.append("Système : %s, mandant %s, utilisateur %s"
                     % (sap.get("system", "?"), sap.get("client", "?"), sap.get("user", "?")))
    screen = context.get("screen") or {}
    if screen:
        lines.append("Écran : transaction %s, programme %s, dynpro %s"
                     % (screen.get("transaction", "?"), screen.get("program", "?"),
                        screen.get("screen_number", "?")))
    for alias in context.get("api_sessions") or []:
        lines.append("Session API %s : %s, mandant %s"
                     % (alias.get("alias", "?"), alias.get("base_url", "?"),
                        alias.get("sap_client") or "-"))
    for name in context.get("rfc_connections") or []:
        lines.append("Connexion RFC : %s" % name)
    for key, problem in sorted((context.get("unread") or {}).items()):
        lines.append("Non lu (%s) : %s" % (key, problem))
    answer = ("Taper « %s » pour approuver ; toute autre saisie, ou Annuler, refuse."
              % APPROVE if typed else "Choisir « %s » ou « %s »." % (APPROVE, REFUSE))
    lines += ["", "Le geste sera refusé s'il ne correspond pas à la cible. " + answer]
    text = "\n".join(lines)
    if len(text) > MAX_MESSAGE_CHARS:
        text = text[:MAX_MESSAGE_CHARS - 20].rstrip() + "\n[... coupé]"
    return text


def ask_on_workstation(message: str, choices: list[str]) -> str:
    """Pose la question dans une boîte de dialogue du poste (bibliothèque
    ``Dialogs`` de Robot) et rend ce que l'humain a TAPÉ : approuver est un
    geste délibéré, qu'un clic mal placé ne peut pas produire (``choices``
    reste dans la signature, commune avec l'élicitation). Lève quand personne
    ne peut répondre : Annuler ou fenêtre fermée (``RuntimeError``), pas
    d'écran ni de Tk (``ImportError``, ``TclError``)."""
    from robot.libraries.Dialogs import get_value_from_user

    return str(get_value_from_user(message))


def ask_human_approval(gate: Any, library: str, reason: str, target: str,
                       context: Mapping[str, Any], ask: Optional[Ask] = None,
                       keyword: str = "") -> dict[str, str]:
    """Demande à un humain d'approuver la prochaine écriture et, sur
    ``approuver`` seulement, l'enregistre dans la garde ``gate`` au nom de
    ``human`` ; rend l'approbation (``{reason, approver, target}``). En
    ``read_only`` la garde refuse sans qu'aucune question soit posée. Toute
    autre issue échoue fermé, la demande refusée étant journalisée."""
    text = str(reason or "").strip()
    approved_target = default_target(library, target, context)
    if not text or gate.policy["mode"] == "read_only":
        gate.approve(text, approver="human", target=approved_target)   # lève, journalisé
    message = build_message(library, gate.describe(), text, approved_target, context,
                            requester="la suite", typed=True)
    try:
        answer = str((ask or ask_on_workstation)(message, list(CHOICES))).strip().lower()
    except Exception as exc:                       # noqa: BLE001 (échec fermé, nommé)
        why = "aucun humain n'a pu répondre (%s : %s)" % (type(exc).__name__, exc)
        gate.record_approval_refusal(text, why, approver="human", target=approved_target)
        raise SessionPolicyError(
            "Approbation non accordée : %s. `%s` ouvre une boîte de dialogue sur le "
            "poste et exige un humain devant un écran ; dans une session d'agent, "
            "l'outil `sapfx_approve_write` de sapfx-mcp pose la question par le "
            "client MCP." % (why, keyword or "Ask Human To Approve Next Write")) from exc
    if answer != APPROVE:
        why = "l'humain a répondu %r" % answer
        gate.record_approval_refusal(text, why, approver="human", target=approved_target)
        raise SessionPolicyError("Approbation refusée par l'humain (réponse %r) : la "
                                 "prochaine écriture reste interdite." % answer)
    gate.approve(text, approver="human", target=approved_target)
    return dict(gate.pending_approval() or {})
