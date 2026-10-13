"""Mixin de gouvernance du canal écran : `Set Session Policy`,
`Get Session Policy`, `Approve Next Write` et `Get Audit Trail` (backlog
§ 2.1, 2026-10-08).

La politique décide AVANT le geste : le lancement d'une transaction
(`Run Transaction`) et le geste d'enregistrement (touche 11, ``Ctrl+S``, et
le bouton ``tbar[0]/btn[11]`` par `Click Element` et tout ce qui passe par
lui). Un refus lève `SessionPolicyError` sans que rien n'ait été envoyé à
SAP. Logique pure dans ``sapfx_common.session_policy``, garde et trace dans
``sapfx_common.policy_gate`` et ``sapfx_common.audit_log``.

Depuis le 2026-10-09 (backlog § 2.1, point 1), une politique peut exiger
qu'un HUMAIN approuve (``approval=human``) : `Approve Next Write` est alors
refusé, et l'approbation vient de l'outil ``sapfx_approve_write`` de la
surcouche ``sapfx-mcp``, qui pose la question à l'humain. Une approbation peut
être liée à une cible (``target=SE16 *``) : la cible d'un enregistrement porte
la transaction de l'écran.
"""
from sapfx_common import approval_request
from sapfx_common.policy_gate import gate_for
from sapfx_common.session_policy import is_save_gesture, load_policy_file, normalize_policy

LIBRARY = "SapEccLibrary"
APPROVE_KEYWORD = "Approve Next Write"


def _screen_transaction(library) -> str:
    """La transaction de l'écran, lue sans geste (``session.Info``), vide si
    illisible : elle nomme la cible d'un enregistrement, jamais au prix de
    l'erreur du geste lui-même."""
    try:
        return str(library.session.Info.Transaction or "").strip()
    except Exception:                       # noqa: BLE001 (best-effort)
        return ""


def check_save_gesture(library, vkey=None, element_id=None) -> None:
    """Interroge la politique avant un geste d'enregistrement de l'écran
    (``Click Element``, ``Send Vkey``) ; rien n'est lu pour un autre geste."""
    if is_save_gesture(vkey=vkey, element_id=element_id):
        gate_for(library, LIBRARY, APPROVE_KEYWORD).check_save_gesture(
            vkey=vkey, element_id=element_id, transaction=_screen_transaction(library))


class GovernanceKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`."""

    def _gate(self):
        return gate_for(self, LIBRARY, APPROVE_KEYWORD)

    def set_session_policy(self, mode="full", allowed_transactions=None,
                           blocked_transactions=None, policy_file=None, approval=None):
        """Fixe la politique de session du canal écran et rend sa vue (comme
        `Get Session Policy`).

        ``mode`` : ``full`` (défaut : tout passe, les écritures sont
        journalisées), ``explore`` (chaque écriture exige `Approve Next Write`
        juste avant elle) ou ``read_only`` (toute écriture refusée). Une
        ÉCRITURE, sur ce canal, est le geste d'enregistrement : touche 11
        (``Ctrl+S``) et bouton ``tbar[0]/btn[11]``. Un bouton qui valide sans
        lui (une suppression qui écrit aussitôt) n'est PAS reconnu :
        ``blocked_transactions`` est le second garde, et l'autorisation SAP de
        l'utilisateur le vrai.

        ``allowed_transactions`` / ``blocked_transactions`` : listes (ou
        chaînes à virgules) de codes de transaction, ``*`` admis
        (``SM3*``), valables dans tous les modes ; une transaction bloquée
        l'est toujours, une liste permise non vide n'admet qu'elle. Les
        OK-codes système (``/n``, ``/nex``...) passent toujours.
        ``policy_file`` : un fichier JSON (``{"mode", "approval",
        "transactions": {"allowed", "blocked"}, "functions": {"read",
        "blocked"}}``), à la place des autres arguments.

        ``approval`` : qui approuve une écriture en ``explore``. ``agent``
        (défaut d'une politique neuve) : `Approve Next Write` suffit. ``human`` :
        ce keyword est refusé, et l'approbation vient de l'outil
        ``sapfx_approve_write`` de la surcouche ``sapfx-mcp``, qui pose la
        question à un humain par le client MCP. Omis, il garde la valeur en
        vigueur.

        Une politique imposée par la variable d'environnement
        ``SAPFX_SESSION_POLICY`` est VERROUILLÉE : ce keyword peut la durcir,
        jamais la relâcher (refus nommé, journalisé). C'est un garde-fou
        d'exploitation, PAS un contrôle de sécurité : qui tient le poste peut
        le contourner, la barrière reste l'autorisation SAP.

        Exemple :
        | ${policy}=    `Set Session Policy`    mode=read_only    blocked_transactions=SE38,SA38
        | Should Be Equal    ${policy}[mode]    read_only
        | Run Keyword And Expect Error    REGEXP:.+bloquée par la politique.+    `Run Transaction`    SE38
        | ${policy}=    `Set Session Policy`    mode=explore    approval=human
        | Run Keyword And Expect Error    REGEXP:.+sapfx_approve_write.+
        | ...    `Approve Next Write`    open the variant attributes of SE16 without saving
        """
        gate = self._gate()
        if policy_file:
            if any(value not in (None, "") for value in (allowed_transactions,
                                                       blocked_transactions, approval)) \
                    or mode != "full":
                raise ValueError("policy_file remplace les autres arguments : ne pas "
                                 "les combiner.")
            wanted = load_policy_file(str(policy_file))
        else:
            wanted = {"mode": mode,
                      "approval": approval if approval not in (None, "")
                      else gate.policy["approval"],
                      "transactions": {"allowed": allowed_transactions,
                                       "blocked": blocked_transactions},
                      "functions": gate.policy["functions"]}
        return gate.set_policy(normalize_policy(wanted))

    def get_session_policy(self):
        """La politique de session en vigueur : ``{"mode", "approval",
        "transactions", "functions", "hash", "locked", "read_functions_preset",
        "pending_approval"}``. ``hash`` est l'empreinte SHA-256 de la forme
        canonique (elle accompagne chaque entrée de `Get Audit Trail`),
        ``locked`` vrai quand elle vient de ``SAPFX_SESSION_POLICY``,
        ``pending_approval`` l'approbation qui attend son geste
        (``{reason, approver, target}``) ou ``None``.

        Exemple :
        | ${policy}=    `Get Session Policy`
        | Should Be Equal    ${policy}[mode]    full
        | Should Be Equal    ${policy}[pending_approval]    ${None}
        """
        return self._gate().describe()

    def approve_next_write(self, reason, target=""):
        """Approuve le PROCHAIN geste d'écriture du canal écran, en mode
        ``explore`` : l'approbation est consommée par ce geste, et sa raison
        part dans le journal d'audit avec lui. Sans approbation, une écriture
        en ``explore`` est refusée en nommant ce keyword. Refusée en
        ``read_only``, où rien ne s'écrit ; sans objet en ``full``. Refusée
        aussi sous une politique ``approval=human`` : l'approbation vient
        alors d'un humain, par `Ask Human To Approve Next Write` (une boîte de
        dialogue sur le poste) ou par l'outil ``sapfx_approve_write`` de
        ``sapfx-mcp`` (une session d'agent).

        ``target`` lie l'approbation à une cible, motif où seul ``*`` est un
        joker, sans casse : la cible d'un enregistrement est la transaction de
        l'écran suivie du geste (``SE16 vkey 11``,
        ``SE16 wnd[0]/tbar[0]/btn[11]``), donc ``SE16 *`` couvre un
        enregistrement dans SE16 et rien d'autre. Un geste hors de la cible
        est refusé, et l'approbation tombe.

        Exemple :
        | `Set Session Policy`    mode=explore
        | `Approve Next Write`    open the variant attributes of SE16 without saving    target=SE16 *
        | `Send Vkey`    Ctrl+S
        """
        self._gate().approve(reason, target=target)

    def ask_human_to_approve_next_write(self, reason, target=""):
        """Demande à un HUMAIN, par une boîte de dialogue sur le poste,
        d'approuver le prochain geste d'écriture du canal écran, et ne
        l'approuve (au nom de ``human`` dans le journal d'audit) que s'il TAPE
        le mot ``approuver`` (un clic ne peut pas approuver ; toute autre
        saisie, ou Annuler, refuse) ; rend l'approbation ``{reason, approver,
        target}``. C'est la voie d'approbation d'une suite lancée par
        ``robot`` sous une politique ``approval=human``, où `Approve Next
        Write` est refusé ; dans une session d'agent, la même question passe
        par l'outil ``sapfx_approve_write`` de ``sapfx-mcp``.

        La boîte montre la raison, la cible couverte, la politique et ce qui
        se lit de la session (système, mandant, utilisateur, écran). Sans
        ``target``, l'approbation est liée à la transaction affichée
        (``SE16 *``). Un refus, une fenêtre fermée ou un poste sans écran (une
        CI) échouent FERMÉ, la demande refusée étant journalisée ; en
        ``read_only`` rien n'est demandé, rien ne s'écrit.

        Exemple :
        | `Set Session Policy`    mode=explore    approval=human
        | ${approval}=    `Ask Human To Approve Next Write`    save the variant attributes of SE16    target=SE16 *
        | Should Be Equal    ${approval}[approver]    human
        """
        context = {"unread": {}}
        try:
            context["screen"] = dict(self.get_current_screen())
        except Exception as exc:          # noqa: BLE001 (best-effort, nommé)
            context["unread"]["screen"] = str(exc)
        try:
            active = [e for e in self.list_sap_sessions() if e.get("active")]
            if active:
                context["session"] = {key: active[0].get(key, "?")
                                      for key in ("system", "client", "user")}
        except Exception as exc:          # noqa: BLE001
            context["unread"]["session"] = str(exc)
        return approval_request.ask_human_approval(
            self._gate(), "SapEccLibrary", reason, target, context,
            keyword="Ask Human To Approve Next Write")

    def get_audit_trail(self):
        """La trace d'audit de cette bibliothèque depuis l'import (portée de la
        suite) : une entrée par décision qui compte (politique chargée ou
        changée, approbation, transaction lancée, écriture permise, approuvée
        ou refusée), ``{"timestamp", "library", "channel", "action",
        "target", "decision", "reason", "mode", "policy_hash", "approver",
        "test"}``, ``approver`` (``agent`` ou ``human``) sur une approbation et
        l'écriture qu'elle autorise. Jamais une valeur saisie. Avec ``SAPFX_AUDIT_LOG=<chemin>``, les
        mêmes entrées s'ajoutent à un fichier JSONL cumulatif.

        Exemple :
        | `Approve Next Write`    open the variant attributes of SE16 without saving    target=SE16 *
        | `Send Vkey`    Ctrl+S
        | ${trail}=    `Get Audit Trail`
        | Should Be Equal    ${trail}[-1][target]    SE16 vkey 11
        | Should Be Equal    ${trail}[-1][approver]    agent
        """
        return self._gate().trail.snapshot()
