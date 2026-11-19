"""Mixin *fenêtres modales* : refermer un popup quelle que soit sa forme.

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
from typing import TYPE_CHECKING, Any

from pythoncom import com_error
from robot.api import logger

from sapfx_common.status_message import normalize_message_class, normalize_message_number

# Boutons de fermeture d'un modal, du plus neutre au plus spécifique :
# barre d'outils du modal (btn[12] = Annuler/F12, btn[0] = Entrée) puis les
# boutons SPOP des dialogues de confirmation (OPTION2 = Non/Annuler,
# OPTION1 = Oui/Continuer), puis ceux de ``POPUP_TO_CONFIRM`` (dynpro
# ``SAPLSPO1/600`` : BUTTON_2 = la seconde réponse, Non, BUTTON_1 = la
# première, Oui). Mesuré le 2026-11-02 sur a4h et abap2023 (avertissement
# d'OBBS, sans bouton Annuler) : F12 y est refusé par ``00/S/255`` et aucun
# bouton SPOP n'existe, le dialogue restait ouvert.
_CANCEL_BUTTONS = ("tbar[0]/btn[12]", "usr/btnSPOP-OPTION2", "usr/btnSPOP-OPTION_CAN",
                   "usr/btnBUTTON_2")
_CONFIRM_BUTTONS = ("tbar[0]/btn[0]", "usr/btnSPOP-OPTION1", "usr/btnBUTTON_1")

# « Function code cannot be selected » : la fonction du bouton pressé est
# EXCLUE du statut GUI du dialogue. Mesuré le 2026-10-06 sur A4H : après un
# dialogue qui portait un Annuler (la sélection multiple SAPLALDB), le
# ``btn[12]`` survit MASQUÉ dans la barre du modal suivant (« Details » d'une
# grille SE16) : ``findById`` le trouve, l'arbre affiché non, et le presser
# ne rend que ce message.
_EXCLUDED_FUNCTION = ("00", "255")


# Profondeur maximale de pile de modaux sondée (SAP GUI en ouvre rarement
# plus de trois ; au-delà, la session est de toute façon à reprendre).
_MAX_MODAL_DEPTH = 9

# Le dialogue de message générique de SAP (programme SAPMSDYP, dynpro 10) :
# son champ d'icône porte le TYPE du message, ``M_INFO`` pour une information
# (relevé le 2026-10-21 sur a4h, dialogue d'expiration de licence après la
# connexion). Le type se lit à l'icône, jamais au texte, traduit.
_MESSAGE_DIALOG_PROGRAM = "SAPMSDYP"
_INFORMATION_ICON = "M_INFO"
_MESSAGE_TEXT_FIELDS = 9
# Liste classique en modal : la forme du dialogue « Copyright » de la connexion.
_LIST_PROGRAM = "SAPMSSY0"
_LIST_SCREEN = "120"


class WindowKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    if TYPE_CHECKING:
        # Contrat du composite (SapEccLibrary), pour mypy seulement : les
        # keywords annotés (type GuiElementId) font vérifier leurs corps.
        session: Any
        def take_screenshot(self, *args: Any, **kwargs: Any) -> Any: ...
        def wait_until_busy_done(self, *args: Any, **kwargs: Any) -> Any: ...

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

    def _is_informational_modal(self, window, excluded=()):
        """Vrai si ``wnd[window]`` n'offre ni bouton Annuler (``tbar[0]/btn[12]``)
        ni question SPOP (``usr/btnSPOP-OPTION1``) mais bien un ``tbar[0]/btn[0]`` :
        une fenêtre d'information, dont la seule fermeture est ce bouton.

        Limite assumée : le test est STRUCTUREL (présence de trois ids), pas
        sémantique. Un dialogue qui porterait sa question dans des boutons de
        zone utilisateur hors SPOP (``usr/btnXXX``) et un ``btn[0]`` qui
        ENGAGE quelque chose passerait pour informatif ; `Dismiss Modal Window`
        ne presse ce ``btn[0]`` qu'en dernier recours, après la touche et les
        boutons d'annulation, et jamais en mode ``confirm``. Devant un tel
        dialogue, fermer par `Click Popup Button` sur le bouton voulu.

        ``excluded`` : boutons dont la pression a rendu ``00/S/255`` (fonction
        exclue du statut GUI), tenus pour absents : un Annuler masqué que
        ``findById`` trouve encore n'est pas un Annuler.

        Un bouton de la barre ``tbar[0]`` ne compte aussi que s'il est parmi
        ses ENFANTS, c'est-à-dire affiché. Mesuré le 2026-11-03 sur a4h
        (fenêtre « aucun IDoc » de WE02, ``SAPMSDYP/10``, icône ``M_INFO``) :
        la barre n'affiche que Continuer et Aide, mais ``findById`` y trouve
        un ``btn[12]`` masqué, géométrie et info-bulle « Cancel » comprises,
        absent des enfants de la barre ; il faisait prendre l'information
        pour un dialogue annulable. Des enfants illisibles laissent la seule
        réponse de ``findById``."""
        def present(suffix):
            if suffix in excluded:
                return False
            try:
                found = self.session.findById("wnd[%s]/%s" % (window, suffix), False) is not None
            except (AttributeError, com_error):
                return False
            if found and suffix.startswith("tbar[0]/"):
                displayed = self._displayed_toolbar_buttons(window)
                if displayed is not None:
                    return "wnd[%s]/%s" % (window, suffix) in displayed
            return found
        return (present("tbar[0]/btn[0]") and not present("tbar[0]/btn[12]")
                and not present("usr/btnSPOP-OPTION1"))

    def _displayed_toolbar_buttons(self, window):
        """Les boutons AFFICHÉS de la barre ``wnd[window]/tbar[0]``, en ids
        relatifs (``wnd[1]/tbar[0]/btn[0]``), lus dans ses enfants ; ``None``
        quand la barre ou ses enfants sont illisibles."""
        marker = "wnd[%s]/tbar[0]/" % window
        try:
            children = self.session.findById("wnd[%s]/tbar[0]" % window).Children
            ids = [str(children.ElementAt(index).Id) for index in range(children.Count)]
        except (AttributeError, com_error, TypeError):
            return None
        return {marker + child_id.split(marker, 1)[1] for child_id in ids if marker in child_id}

    def _function_was_excluded(self):
        """Vrai si la barre de statut porte ``00/S/255`` : la dernière
        fonction demandée est exclue du statut GUI de l'écran."""
        try:
            status = self.session.findById("wnd[0]/sbar")
            identity = (normalize_message_class(getattr(status, "MessageId", "")),
                        normalize_message_number(getattr(status, "MessageNumber", "")))
        except (AttributeError, com_error):
            return False
        return identity == _EXCLUDED_FUNCTION

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
        (``window=1`` sous un ``wnd[2]``).

        Exemple :
        | ${buttons}=    `Get Modal Buttons`
        | Should Be Equal    ${buttons}[0][id]    wnd[1]/tbar[0]/btn[0]
        """
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

    def dismiss_modal_window(self, window=None, confirm: bool = False):
        """Referme la fenêtre modale ``wnd[window]`` (omis : le modal le PLUS
        HAUT de la pile, celui qui a la main) et VÉRIFIE qu'elle a
        disparu. Voies essayées dans l'ordre : la touche (F12, ou Entrée si
        ``confirm``), puis le bouton de la barre du modal (Annuler, ou
        Continuer), puis le bouton SPOP (Non, ou Oui). Certains dialogues SAP
        refusent ``sendVKey`` (SPOP, « Details » d'une grille SE16) : c'est
        pour eux que les replis existent. Aucune fenêtre ouverte = ne fait
        rien et retourne ``False`` ; fenêtre toujours ouverte après toutes
        les voies = échec listant ses boutons. Retourne ``True`` quand une
        fenêtre a été refermée.

        Avec ``confirm``, un dialogue ``POPUP_TO_CONFIRM`` (``SAPLSPO1/600``,
        boutons ``BUTTON_1`` à ``BUTTON_3``) est confirmé par ``BUTTON_1``, sa
        première réponse, AVANT toute touche : Entrée y presse le bouton par
        défaut, que l'appelant du dialogue choisit et qui vaut « No » sur
        l'avertissement d'OBBS. Le bouton pressé est journalisé.

        Exemple :
        | `Open System Status`
        | ${closed}=    `Dismiss Modal Window`
        | Should Be True    ${closed}
        """
        window = self._modal_window_argument(window)
        if window is None or not self._window_open(window):
            return False
        if _as_bool(confirm) and self._press_first_answer(window):
            return True
        vkey = 0 if _as_bool(confirm) else 12
        buttons = _CONFIRM_BUTTONS if _as_bool(confirm) else _CANCEL_BUTTONS
        attempts = []
        excluded = set()
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
            if self._function_was_excluded():
                excluded.add(suffix)
                attempts[-1] = "%s exclu (00/S/255)" % element_id
        if not _as_bool(confirm) and self._is_informational_modal(window, excluded):
            # Un modal SANS bouton Annuler ni question SPOP (le « Details »
            # d'une grille SE16 : seuls « Close window (Enter) » et « Find »,
            # relevé live 2026-09-07) n'a rien à annuler : son btn[0] est sa
            # seule fermeture, et la presser n'engage rien. Un Annuler masqué
            # que SAP refuse par 00/S/255 ne change rien à ce constat.
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

    def _press_first_answer(self, window):
        """Confirme un ``POPUP_TO_CONFIRM`` (``SAPLSPO1/600``) par son bouton
        ``BUTTON_1``, la première réponse, sans passer par Entrée : Entrée y
        presse le bouton PAR DÉFAUT, que l'appelant du dialogue choisit
        (l'avertissement d'OBBS a « No » par défaut, mesuré le 2026-11-02).
        Rend ``True`` quand le dialogue s'est refermé, ``False`` quand il n'a
        pas ce bouton (les autres voies prennent alors le relais). Un bouton
        présent qui ne referme pas le dialogue fait échouer : se rabattre sur
        Entrée risquerait de répondre « No »."""
        element_id = "wnd[%s]/usr/btnBUTTON_1" % window
        try:
            button = self.session.findById(element_id, False)
        except (AttributeError, com_error):
            button = None
        if button is None:
            return False
        try:
            button.press()
            outcome = "pressé"
        except (AttributeError, com_error) as error:
            outcome = "refusé (%s)" % error
        self.wait_until_busy_done()
        if not self._window_open(window):
            logger.info("Dialogue wnd[%s] confirmé par sa première réponse (%s)."
                        % (window, element_id))
            return True
        self._fail_if_covered(window, [element_id])
        self.take_screenshot()
        raise AssertionError(
            "La fenêtre wnd[%s] est restée ouverte : sa première réponse %s a été %s, et "
            "Entrée n'est pas tentée (elle presse le bouton par défaut, qui peut être "
            "« No »). Boutons du modal : %s."
            % (window, element_id, outcome,
               ", ".join("%s (%s)" % (b["id"], b["text"] or b["tooltip"])
                         for b in self.get_modal_buttons(window)) or "aucun"))

    def _information_dialog(self, window):
        """``{text, icon}`` si ``wnd[window]`` est un dialogue d'INFORMATION, sous
        l'une de ses deux formes (message SAPMSDYP, liste d'information de la
        connexion), sinon ``None``."""
        return self._message_information(window) or self._information_list(window)

    def _information_list(self, window):
        """``{text, icon}`` si ``wnd[window]`` est une LISTE d'information en
        modal : programme ``SAPMSSY0``, dynpro ``120``, zone utilisateur faite
        de libellés seulement, aucune question ni Annuler mais un ``btn[0]``.
        C'est le dialogue « Copyright » que la connexion affiche quand sa langue
        change d'une connexion à l'autre (mesuré le 2026-11-17 sur a4h, en
        anglais après l'allemand et l'inverse, jamais deux fois de suite dans la
        même langue) ; son titre, traduit, n'est jamais lu. ``icon`` est vide."""
        try:
            program = (self.session.Info.Program or "").strip().upper()
            screen = str(self.session.Info.ScreenNumber or "").strip().lstrip("0")
            children = self.session.findById("wnd[%s]/usr" % window).Children
            items = [children.ElementAt(index) for index in range(int(children.Count))]
        except (AttributeError, TypeError, ValueError, com_error):
            return None
        if program != _LIST_PROGRAM or screen != _LIST_SCREEN or not items:
            return None
        if any(str(getattr(item, "Type", "") or "") != "GuiLabel" for item in items):
            return None
        if not self._is_informational_modal(window):
            return None
        texts = [str(getattr(item, "Text", "") or "").strip() for item in items]
        return {"text": " ".join(text for text in texts if text), "icon": ""}

    def _message_information(self, window):
        """``{text, icon}`` si ``wnd[window]`` est le dialogue de message SAPMSDYP
        d'une INFORMATION (icône ``M_INFO``, ``usr/txtMESSTXT1`` présent, aucune
        question ni Annuler), sinon ``None``."""
        try:
            program = (self.session.Info.Program or "").strip().upper()
            icon = (self.session.findById("wnd[%s]/usr/txtIK1" % window).IconName or "").strip()
            first = self.session.findById("wnd[%s]/usr/txtMESSTXT1" % window)
        except (AttributeError, com_error):
            return None
        if (program != _MESSAGE_DIALOG_PROGRAM or icon != _INFORMATION_ICON
                or not self._is_informational_modal(window)):
            return None
        lines = [(first.Text or "").strip()]
        for index in range(2, _MESSAGE_TEXT_FIELDS + 1):
            field = self.session.findById("wnd[%s]/usr/txtMESSTXT%d" % (window, index), False)
            if field is None:
                break
            lines.append((field.Text or "").strip())
        return {"text": " ".join(line for line in lines if line), "icon": icon}

    def dismiss_information_dialogs(self, max_dialogs: int = 5) -> list[dict[str, str]]:
        """Referme les dialogues d'INFORMATION ouverts au-dessus de l'écran (la
        connexion en laisse) et rend ce qu'ils disaient, pour le journal : une
        liste ``[{text, icon}]``, vide quand il n'y en avait aucun.

        Un dialogue d'information est le dialogue de message générique de SAP
        (programme ``SAPMSDYP``) dont l'icône vaut ``M_INFO`` et dont la barre
        n'offre ni Annuler ni question : il est reconnu à sa STRUCTURE et à
        son icône, jamais à son texte, traduit. Mesuré le 2026-10-21 sur a4h :
        « License expiration date: 04.11.2026 (in 14 days) » suit chaque
        connexion SAP GUI et bloque `Open System Status` tant qu'il est
        ouvert. Seconde forme reconnue : la LISTE d'information en modal
        (programme ``SAPMSSY0``, dynpro ``120``, libellés seulement, un seul
        bouton Continuer), le dialogue « Copyright » que la connexion affiche
        quand sa langue change d'une connexion à l'autre (mesuré le 2026-11-17
        sur a4h) ; avant ce correctif, il restait ouvert et `Open System
        Status` refusait ensuite. Tout autre modal reste en place (message d'erreur ou
        d'avertissement, question, connexion multiple, changement de mot de
        passe) : le keyword s'arrête au premier qui n'est pas une information.
        Un bouton de la barre ne compte que s'il y est AFFICHÉ : la fenêtre
        « aucun IDoc » de WE02 (a4h, 2026-11-03) n'affiche que Continuer et
        Aide mais garde un Annuler masqué ; avant ce correctif, le keyword la
        laissait ouverte.
        Un dialogue que son bouton ne referme pas échoue en le nommant, comme
        plus de ``max_dialogs`` à la suite.

        Exemple :
        | ${closed}=    `Dismiss Information Dialogs`
        | Log Many    @{closed}
        | ${modal}=    `Element Is Present`    wnd[1]
        | Should Not Be True    ${modal}
        """
        closed: list[dict[str, str]] = []
        for _ in range(int(max_dialogs)):
            window = self._topmost_modal_window()
            if window is None:
                return closed
            dialog = self._information_dialog(window)
            if dialog is None:
                return closed
            self.session.findById("wnd[%s]/tbar[0]/btn[0]" % window).press()
            self.wait_until_busy_done()
            if self._window_open(window) and self._information_dialog(window) == dialog:
                self.take_screenshot()
                raise AssertionError(
                    "Le dialogue d'information wnd[%s] (« %s ») est resté ouvert après "
                    "son bouton Continuer." % (window, dialog["text"]))
            closed.append(dialog)
        if self._topmost_modal_window() is not None and self._information_dialog(
                self._topmost_modal_window()) is not None:
            raise AssertionError(
                "Plus de %s dialogues d'information à la suite : %s. La session est à "
                "reprendre." % (max_dialogs, "; ".join(d["text"] for d in closed)))
        return closed


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")
