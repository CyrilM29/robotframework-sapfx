"""Mixin *barre de statut* : l'IDENTITÉ d'un message, pas seulement son type.

`Get Status Message` (module principal) rend le type et le texte localisé ;
ce mixin lit ce que ``wnd[0]/sbar`` expose en plus (mesuré le 2026-09-08 sur
ABAP 2023) : ``MessageId`` (la classe de message ABAP, complétée à droite sur
20 caractères), ``MessageNumber`` et ``MessageParameter(index)`` (une MÉTHODE,
les variables ``&`` du message). Deux refus différents du même écran, tous
deux de type ``E``, deviennent ainsi discernables sans un mot de texte
localisé (``MO/E/402`` contre ``MO/E/410``) : la convention #3 côté SAP GUI,
au même grain que `Rfc Should Fail With Message Id` côté RFC. Logique pure
dans ``sapfx_common.status_message``.
"""
from typing import TYPE_CHECKING, Any

from pythoncom import com_error

from sapfx_common import touch_log
from sapfx_common.robot_args import OptionalNameListInput, as_name_list
from sapfx_common.transaction_code import TransactionCodeInput
from sapfx_common.status_message import (
    format_identity_mismatch,
    identity_matches,
    message_identity,
)

_STATUSBAR = "wnd[0]/sbar"
_MAX_PARAMETERS = 4          # SAP porte quatre variables &1 à &4 dans un message


class StatusBarKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    if TYPE_CHECKING:
        # Contrat du composite (SapEccLibrary), déclaré pour mypy seulement :
        # `Transaction Start Should Be Refused` est annoté (type NameList),
        # donc son corps est vérifié.
        session: Any
        def _has_nav_prefix(self, transaction: str) -> bool: ...
        def _screen_identity_or_none(self) -> Any: ...
        def _modal_open(self) -> Any: ...
        def send_vkey(self, vkey_id: Any, window: int = 0) -> None: ...
        def wait_until_busy_done(self, timeout: Any = None) -> None: ...
        def take_screenshot(self, screenshot_name: str = ...) -> Any: ...

    def _statusbar_parameters(self, status):
        method = getattr(status, "MessageParameter", None)
        if method is None:
            return []
        parameters = []
        for index in range(_MAX_PARAMETERS):
            try:
                parameters.append(str(method(index) or ""))
            except (AttributeError, com_error, TypeError, ValueError):
                break
        return parameters

    def get_status_message_identity(self):
        """L'IDENTITÉ du message de la barre de statut : dict JSON-safe
        ``{type, class, number, identity, text, parameters}`` où ``identity``
        vaut ``MO/E/402`` (classe/type/numéro, la forme du canal RFC) et reste
        VIDE quand aucun message n'est affiché. ``class`` est la classe de
        message ABAP (``MessageId``, padding de champ retiré : ``MO``),
        ``number`` son numéro, ``parameters`` les variables ``&`` ; ``text``
        n'est là que pour le lecteur. C'est l'ancre locale-safe d'un refus
        EXACT, là où `Get Status Message` ne donne que le type.

        Exemple :
        | ${message}=    `Get Status Message Identity`
        | Should Be Equal    ${message}[identity]    MO/E/402
        | Should Be Equal    ${message}[parameters][0]    ZZ_NO_SUCH_TABLE
        """
        status = self.session.findById(_STATUSBAR)
        return message_identity(
            getattr(status, "MessageType", ""), getattr(status, "MessageId", ""),
            getattr(status, "MessageNumber", ""), getattr(status, "Text", ""),
            self._statusbar_parameters(status))

    def status_message_should_be(self, message_class, message_number, message_type=None):
        """Échoue si la barre de statut ne porte pas le message de classe
        ``message_class`` et de numéro ``message_number`` (et du type
        ``message_type`` quand il est donné) : ``Status Message Should Be    MO
        402    E``. L'échec nomme l'attendu, l'identité lue et son texte, ou
        dit qu'aucun message n'est affiché. Retourne l'identité lue.

        Exemple :
        | `Input Text`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    ZZ_NO_SUCH_TABLE
        | `Send Vkey`    0
        | `Status Message Should Be`    MO    402    E
        """
        identity = self.get_status_message_identity()
        if not identity_matches(identity, message_class, message_number, message_type):
            self.take_screenshot()
            raise AssertionError(
                format_identity_mismatch(identity, message_class, message_number, message_type))
        return identity

    def transaction_start_should_be_refused(
            self, transaction: TransactionCodeInput,
            accepted_identities: OptionalNameListInput = None):
        """Lance ``transaction`` et échoue sauf si son LANCEMENT est refusé :
        la transaction active n'est pas celle demandée et la barre de statut
        porte un message de type ``E`` ou ``A``. Rend l'identité du refus
        (celle de `Get Status Message Identity`) complétée de l'écran où la
        session est restée (``program``, ``screen_number``, ``transaction``).

        C'est le constat d'un refus d'autorisation au lancement (``S_TCODE``
        absent), là où `Run Transaction` échoue en capturant l'écran : un refus
        ATTENDU ne doit ni passer par une erreur rattrapée dans la suite, ni
        produire une capture dans un run vert. Une transaction qui démarre
        échoue en le disant ; un refus de type ``S`` ou ``W`` aussi (une
        transaction inexistante répond en ``S``, ce n'est pas un refus de
        droits).

        La session doit être restée sur son écran de départ, sans dialogue
        ouvert : une transaction qui démarre puis redirige ailleurs avec un
        message ``E`` n'est pas un refus de lancement.

        Limite connue : un message identique resté d'un essai précédent sur le
        même écran ne se distingue pas d'un refus neuf ; le paramètre du
        message (le code de transaction) est à confronter par l'appelant.

        ``accepted_identities`` (liste ou chaîne à virgules) restreint les
        identités admises. Le même refus en porte deux selon l'écran de départ,
        mesuré le 2026-10-07 sur la 758 : ``S#/E/077`` depuis l'accueil SAP
        Easy Access, ``00/E/172`` depuis l'écran vide ``S000``.

        Exemple :
        | ${refusal}=    `Transaction Start Should Be Refused`    SEPM_SO
        | ...    accepted_identities=S#/E/077,00/E/172
        | Should Be Equal    ${refusal}[parameters][0]    SEPM_SO
        """
        code = str(transaction).strip()
        okcode = code if self._has_nav_prefix(code) else "/n" + code
        expected = code[2:] if self._has_nav_prefix(code) and len(code) > 2 else code
        before = self._screen_identity_or_none()
        if before is None:
            raise AssertionError(
                "The SAP session is unreadable before starting '%s': a refusal "
                "could not be told from a session that is gone." % code)
        touch_log.record_transaction("SapEccLibrary", code)
        self.session.findById("wnd[0]/tbar[0]/okcd").text = okcode
        self.send_vkey(0)
        self.wait_until_busy_done()
        info = self.session.Info
        screen = {"program": str(info.Program), "screen_number": str(info.ScreenNumber),
                  "transaction": str(info.Transaction)}
        if screen["transaction"].upper().lstrip("/") == expected.upper().lstrip("/"):
            self.take_screenshot()
            raise AssertionError(
                "Transaction '%s' STARTED (%s/%s): a refusal was expected."
                % (expected, screen["program"], screen["screen_number"]))
        after = (screen["program"], screen["screen_number"], screen["transaction"])
        if after != before or self._modal_open():
            # Un refus de lancement laisse la session sur son écran de départ,
            # sans dialogue ; une transaction qui démarre puis redirige ailleurs
            # avec un message E n'est pas un refus de droits.
            self.take_screenshot()
            raise AssertionError(
                "Transaction '%s' did not start, but the session left its starting "
                "screen (%s -> %s%s): not a plain refusal at start."
                % (expected, "/".join(before) if before else "?", "/".join(after),
                   ", a dialog is open" if self._modal_open() else ""))
        identity = self.get_status_message_identity()
        if identity["type"] not in ("E", "A"):
            self.take_screenshot()
            raise AssertionError(
                "Transaction '%s' did not start, but the status bar carries no "
                "error (%s): not a refusal of rights. A transaction that does "
                "not exist answers with type S." % (expected, identity["identity"] or "no message"))
        accepted = [name.upper() for name in as_name_list(accepted_identities, "accepted_identities")]
        if accepted and identity["identity"].upper() not in accepted:
            self.take_screenshot()
            raise AssertionError(
                "Transaction '%s' was refused with %s (%s), not with one of %s."
                % (expected, identity["identity"], identity["text"], ", ".join(accepted)))
        result = dict(identity)
        result.update(screen)
        return result
