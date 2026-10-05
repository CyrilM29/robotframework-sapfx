"""Mixin **barre de statut** : l'IDENTITÉ d'un message, pas seulement son type.

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
from pythoncom import com_error

from sapfx_common.status_message import (
    format_identity_mismatch,
    identity_matches,
    message_identity,
)

_STATUSBAR = "wnd[0]/sbar"
_MAX_PARAMETERS = 4          # SAP porte quatre variables &1 à &4 dans un message


class StatusBarKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

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
        EXACT, là où `Get Status Message` ne donne que le type."""
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
        dit qu'aucun message n'est affiché. Retourne l'identité lue."""
        identity = self.get_status_message_identity()
        if not identity_matches(identity, message_class, message_number, message_type):
            self.take_screenshot()
            raise AssertionError(
                format_identity_mismatch(identity, message_class, message_number, message_type))
        return identity
