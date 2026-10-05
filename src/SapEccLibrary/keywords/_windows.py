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

Depuis le 2026-10-01 (fiche scénario 9), les deux keywords visent par défaut
le modal le PLUS HAUT de la pile. Mesuré sur SM36 : une étape au programme
inexistant ouvre un dialogue d'erreur ``wnd[2]`` AU-DESSUS du dialogue
d'étape ``wnd[1]`` ; le défaut historique ``window=1`` envoyait F12 au
dialogue d'étape (qui se refermait en abandonnant la saisie) et laissait
l'erreur ouverte, et `Get Modal Buttons` rendait ``[]`` pour ``wnd[1]``, qui
porte pourtant quatre boutons, parce que la perception ne parcourait que la
fenêtre ACTIVE. Avec un seul modal ouvert, rien ne change.
"""
from pythoncom import com_error

# Boutons de fermeture d'un modal, du plus neutre au plus spécifique :
# barre d'outils du modal (btn[12] = Annuler/F12, btn[0] = Entrée) puis les
# boutons SPOP des dialogues de confirmation (OPTION2 = Non/Annuler,
# OPTION1 = Oui/Continuer).
_CANCEL_BUTTONS = ("tbar[0]/btn[12]", "usr/btnSPOP-OPTION2", "usr/btnSPOP-OPTION_CAN")
_CONFIRM_BUTTONS = ("tbar[0]/btn[0]", "usr/btnSPOP-OPTION1")


# Profondeur maximale de pile de modaux sondée (SAP GUI en ouvre rarement
# plus de trois ; au-delà, la session est de toute façon à reprendre).
_MAX_MODAL_DEPTH = 9


class WindowKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def _topmost_modal_window(self):
        """Indice du modal le plus haut (``2`` pour ``wnd[2]``), ou ``None``
        sans modal. La pile SAP GUI est contiguë : on monte tant que la
        fenêtre suivante existe."""
        top = None
        for index in range(1, _MAX_MODAL_DEPTH + 1):
            if not self._window_open(index):
                break
            top = index
        return top

    def _modal_window_argument(self, window):
        """``window`` explicite (indice ``1``, ``"2"``), ou le modal le plus
        haut quand il vaut ``None``/vide/``top``."""
        if window is None or str(window).strip().lower() in ("", "none", "top"):
            return self._topmost_modal_window()
        return int(str(window).strip())

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

    def _fail_if_covered(self, window, attempts):
        """Échoue si un modal s'est ouvert AU-DESSUS de ``wnd[window]`` pendant
        la tentative de fermeture : un refus de saisie ou une confirmation
        (mesuré sur SM36 : Annuler le dialogue d'étape qui porte un programme
        inexistant rouvre le dialogue d'erreur). Continuer à presser des
        boutons sur une fenêtre recouverte n'aurait aucun effet, et l'échec
        générique « restée ouverte » cacherait la vraie cause."""
        top = self._topmost_modal_window()
        if top is None or top <= int(window):
            return
        try:
            title = (self.session.findById("wnd[%s]" % top).Text or "").strip()
        except (AttributeError, com_error):
            title = ""
        self.take_screenshot()
        raise AssertionError(
            "La fermeture de wnd[%s] (%s) a ouvert un modal AU-DESSUS : wnd[%s]%s. "
            "Le traiter d'abord (Get Modal Buttons, puis Dismiss Modal Window sans "
            "argument, qui vise le plus haut), puis corriger ce que wnd[%s] refuse."
            % (window, ", ".join(attempts), top,
               " « %s »" % title if title else "", window))

    def get_modal_buttons(self, window=None):
        """Les boutons de la fenêtre ``wnd[window]`` : liste de dicts
        ``{id, text, tooltip}`` (barre d'outils et boutons de la zone
        utilisateur), la matière d'un échec de fermeture actionnable.
        ``window`` omis = le modal le PLUS HAUT de la pile (aucun modal :
        ``[]``) ; un modal recouvert par un autre se lit en le nommant
        (``window=1`` sous un ``wnd[2]``)."""
        window = self._modal_window_argument(window)
        if window is None:
            return []
        prefix = "wnd[%s]/" % window
        buttons = []
        for element in self._screen_elements(window):
            if element.type == "GuiButton" and element.id.startswith(prefix):
                buttons.append({"id": element.id, "text": (element.text or "").strip(),
                                "tooltip": (element.tooltip or "").strip()})
        return buttons

    def dismiss_modal_window(self, window=None, confirm=False):
        """Referme la fenêtre modale ``wnd[window]`` (omis : le modal le PLUS
        HAUT de la pile, celui qui a la main) et VÉRIFIE qu'elle a
        disparu. Voies essayées dans l'ordre : la touche (F12, ou Entrée si
        ``confirm``), puis le bouton de la barre du modal (Annuler, ou
        Continuer), puis le bouton SPOP (Non, ou Oui). Certains dialogues SAP
        refusent ``sendVKey`` (SPOP, « Details » d'une grille SE16) : c'est
        pour eux que les replis existent. Aucune fenêtre ouverte = ne fait
        rien et retourne ``False`` ; fenêtre toujours ouverte après toutes
        les voies = échec listant ses boutons. Retourne ``True`` quand une
        fenêtre a été refermée."""
        window = self._modal_window_argument(window)
        if window is None or not self._window_open(window):
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
        self._fail_if_covered(window, attempts)
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
            self._fail_if_covered(window, attempts)
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
