"""Mixin **fenêtres modales** : refermer un popup quelle que soit sa forme.

Relevé live sur A4H (SAP GUI 8.00) : plusieurs dialogues modaux REFUSENT
``sendVKey`` (les SPOP de confirmation dès 2026-07, le popup « Details » d'une
grille SE16 le 2026-09-07 : ``com_error`` « Cannot send Vkey to given window »
alors que ``wnd[1]`` est bien ouverte). Un ``Send Vkey 12 window=1`` n'est
donc pas une fermeture fiable, et une suite qui s'y fie laisse un modal
ouvert qui neutralise l'écran principal. Ce mixin essaie les voies dans
l'ordre (touche, bouton Annuler de la barre du modal, bouton SPOP) et VÉRIFIE
que la fenêtre a disparu ; sinon il échoue en listant les boutons réels du
modal, jamais en silence.
"""
from pythoncom import com_error

# Boutons de fermeture d'un modal, du plus neutre au plus spécifique :
# barre d'outils du modal (btn[12] = Annuler/F12, btn[0] = Entrée) puis les
# boutons SPOP des dialogues de confirmation (OPTION2 = Non/Annuler,
# OPTION1 = Oui/Continuer).
_CANCEL_BUTTONS = ("tbar[0]/btn[12]", "usr/btnSPOP-OPTION2", "usr/btnSPOP-OPTION_CAN")
_CONFIRM_BUTTONS = ("tbar[0]/btn[0]", "usr/btnSPOP-OPTION1")


class WindowKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def _window_open(self, window):
        try:
            return self.session.findById("wnd[%s]" % window, False) is not None
        except (AttributeError, com_error):
            return False

    def _is_informational_modal(self, window):
        """Vrai si ``wnd[window]`` n'offre ni bouton Annuler (``tbar[0]/btn[12]``)
        ni question SPOP (``usr/btnSPOP-OPTION1``) mais bien un ``tbar[0]/btn[0]`` :
        une fenêtre d'information, dont la seule fermeture est ce bouton.

        Limite assumée : le test est STRUCTUREL (présence de trois ids), pas
        sémantique. Un dialogue qui porterait sa question dans des boutons de
        zone utilisateur hors SPOP (``usr/btnXXX``) et un ``btn[0]`` qui
        ENGAGE quelque chose passerait pour informatif ; `Dismiss Modal Window`
        ne presse ce ``btn[0]`` qu'en dernier recours, après la touche et les
        boutons d'annulation, et jamais en mode ``confirm``. Devant un tel
        dialogue, fermer par `Click Popup Button` sur le bouton voulu."""
        def present(suffix):
            try:
                return self.session.findById("wnd[%s]/%s" % (window, suffix), False) is not None
            except (AttributeError, com_error):
                return False
        return (present("tbar[0]/btn[0]") and not present("tbar[0]/btn[12]")
                and not present("usr/btnSPOP-OPTION1"))

    def get_modal_buttons(self, window=1):
        """Les boutons de la fenêtre ``wnd[window]`` : liste de dicts
        ``{id, text, tooltip}`` (barre d'outils et boutons de la zone
        utilisateur), la matière d'un échec de fermeture actionnable."""
        prefix = "wnd[%s]/" % window
        buttons = []
        for element in self._screen_elements():
            if element.type == "GuiButton" and element.id.startswith(prefix):
                buttons.append({"id": element.id, "text": (element.text or "").strip(),
                                "tooltip": (element.tooltip or "").strip()})
        return buttons

    def dismiss_modal_window(self, window=1, confirm=False):
        """Referme la fenêtre modale ``wnd[window]`` et VÉRIFIE qu'elle a
        disparu. Voies essayées dans l'ordre : la touche (F12, ou Entrée si
        ``confirm``), puis le bouton de la barre du modal (Annuler, ou
        Continuer), puis le bouton SPOP (Non, ou Oui). Certains dialogues SAP
        refusent ``sendVKey`` (SPOP, « Details » d'une grille SE16) : c'est
        pour eux que les replis existent. Aucune fenêtre ouverte = ne fait
        rien et retourne ``False`` ; fenêtre toujours ouverte après toutes
        les voies = échec listant ses boutons. Retourne ``True`` quand une
        fenêtre a été refermée."""
        if not self._window_open(window):
            return False
        vkey = 0 if _as_bool(confirm) else 12
        buttons = _CONFIRM_BUTTONS if _as_bool(confirm) else _CANCEL_BUTTONS
        attempts = []
        try:
            self.session.findById("wnd[%s]" % window).sendVKey(vkey)
            attempts.append("vkey %d" % vkey)
        except com_error:
            attempts.append("vkey %d refusé" % vkey)
        self.wait_until_busy_done()
        if not self._window_open(window):
            return True
        for suffix in buttons:
            element_id = "wnd[%s]/%s" % (window, suffix)
            try:
                button = self.session.findById(element_id, False)
            except (AttributeError, com_error):
                button = None
            if button is None:
                continue
            try:
                button.press()
                attempts.append(element_id)
            except (AttributeError, com_error):
                attempts.append("%s refusé" % element_id)
                continue
            self.wait_until_busy_done()
            if not self._window_open(window):
                return True
        if not _as_bool(confirm) and self._is_informational_modal(window):
            # Un modal SANS bouton Annuler ni question SPOP (le « Details »
            # d'une grille SE16 : seuls « Close window (Enter) » et « Find »,
            # relevé live 2026-09-07) n'a rien à annuler : son btn[0] est sa
            # seule fermeture, et la presser n'engage rien.
            try:
                self.session.findById("wnd[%s]/tbar[0]/btn[0]" % window).press()
                attempts.append("wnd[%s]/tbar[0]/btn[0] (modal informatif)" % window)
            except (AttributeError, com_error):
                attempts.append("wnd[%s]/tbar[0]/btn[0] refusé" % window)
            self.wait_until_busy_done()
            if not self._window_open(window):
                return True
        self.take_screenshot()
        available = ", ".join("%s (%s)" % (b["id"], b["text"] or b["tooltip"])
                              for b in self.get_modal_buttons(window)) or "aucun"
        raise AssertionError(
            "La fenêtre wnd[%s] est restée ouverte après %s. Boutons du modal : %s "
            "(cliquer le bon par Click Element, ou Click Popup Button)."
            % (window, ", ".join(attempts), available))


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")
