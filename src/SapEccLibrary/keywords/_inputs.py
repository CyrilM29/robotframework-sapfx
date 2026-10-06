"""Mixin saisies : clic, texte, mot de passe, cases, boutons radio, touches.

Une partie de ce module dérive de robotframework-sapguilibrary 1.2.1
(Copyright Frank van der Kuur, Apache License 2.0, voir NOTICE), absorbée et
réécrite pour SAPFX le 2026-10-06 : `Click Element`, `Input Text`, `Input
Password`, `Select Checkbox`, `Unselect Checkbox`, `Select Radio Button` et
`Send Vkey` gardent leur nom et leur signature
(``tests/unit/test_upstream_compatibility.py``). Ce qui a changé :

* une écriture est RELUE (texte, case, radio) et l'écart échoue en nommant
  la valeur obtenue : l'amont écrivait sans relire, donc une saisie tronquée
  par la longueur du champ ou une case protégée passaient pour faites ;
* aucun mot de passe n'est journalisé, ni par `Input Password` ni par `Input
  Text` sur un champ masqué (l'amont écrivait la valeur en clair au niveau
  INFO), et les deux acceptent le type ``Secret`` de Robot Framework 7.4 ;
* un ``GuiShell`` n'est accepté que s'il porte vraiment du texte (sous-type
  ``TextEdit``) : sur un arbre ou une grille, l'affectation de ``.text`` ne
  faisait rien d'utile ;
* `Send Vkey` résout ses combinaisons par ``sapfx_common.vkeys`` (même
  table), et une combinaison inconnue propose les plus proches.

Aucune attente ``Busy`` n'est ajoutée à `Click Element` ni à `Send Vkey` :
la synchronisation reste à l'appelant (`Wait Until Busy Done`), c'est le
contrat connu de ces deux keywords.
"""
from typing import TYPE_CHECKING, Any

from pythoncom import com_error
from robot.api import logger
from robot.api.types import Secret

from sapfx_common.secrets import reveal_secret
from sapfx_common.vkeys import resolve_vkey

_TEXT_FIELDS = ("GuiTextField", "GuiCTextField", "GuiPasswordField", "GuiOkCodeField")
_TEXT_SHELL_SUBTYPES = ("TextEdit",)


class InputKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Chaque keyword agit sur l'écran ;
    les écritures sont relues avant de rendre la main."""

    if TYPE_CHECKING:
        # Contrat du composite (SapEccLibrary), déclaré pour mypy seulement :
        # `Input Password` est annoté (type Secret), donc son corps est vérifié.
        session: Any
        def _explicit_pause(self) -> None: ...

    def click_element(self, element_id):
        """Clique ``element_id`` : presse un bouton, sélectionne un onglet ou
        une entrée de menu. Pour une case, un bouton radio ou une combo,
        employer `Select Checkbox`, `Select Radio Button` ou `Select Combo Box
        Entry By Key`. La synchronisation reste à l'appelant.

        Exemple :
        | `Input Text`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
        | `Click Element`    wnd[0]/tbar[0]/btn[0]
        | `Wait Until Busy Done`
        | `Element Should Be Present`    wnd[0]/usr/txtMAX_SEL
        """
        element_type = self.get_element_type(element_id)
        element = self.session.findById(element_id)
        if element_type in ("GuiTab", "GuiMenu"):
            element.select()
        elif element_type == "GuiButton":
            element.press()
        else:
            self.take_screenshot()
            raise ValueError(
                "You cannot use 'click_element' on element type '%s', maybe use "
                "'select checkbox' instead?" % element_type)
        self._explicit_pause()

    def input_text(self, element_id, text):
        """Saisit ``text`` dans le champ ``element_id`` puis RELIT le champ :
        un écart (saisie tronquée par la longueur du champ, champ protégé)
        échoue en nommant la valeur obtenue. Champs pris en charge : texte,
        texte à aide F4, mot de passe, OK-code, et éditeur de texte
        (``GuiShell`` de sous-type ``TextEdit``).

        La valeur est journalisée, sauf sur un champ masqué ou quand ``text``
        est un ``Secret`` : préférer `Input Password` pour un mot de passe.

        Exemple :
        | `Input Text`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
        | ${table}=    `Get Value`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        | Should Be Equal    ${table}    T000
        """
        element_type = self._writable_text_type(element_id, "input text")
        secret = isinstance(text, Secret) or element_type == "GuiPasswordField"
        value = reveal_secret(text)
        self.session.findById(element_id).text = value
        if secret:
            logger.info("Typing hidden text into field '%s'." % element_id)
        else:
            logger.info("Typing text '%s' into text field '%s'." % (value, element_id))
            self._text_should_have_been_written(element_id, value)
        self._explicit_pause()

    def input_password(self, element_id, password: str | Secret):
        """Saisit un mot de passe dans le champ identifié, sans le journaliser
        et sans le relire (un champ masqué ne rend pas sa valeur).

        Accepte, en plus d'une chaîne, le type ``Secret`` de Robot Framework
        7.4 ; créez la variable typée dès la ligne de commande (``-v
        "SAP_PASSWORD: Secret:<motdepasse>"``) : sa valeur est alors masquée
        partout, y compris en niveau de log TRACE. Le secret n'est déballé
        qu'ici, juste avant la frontière COM.

        Exemple :
        | `Input Text`    wnd[0]/usr/txtRSYST-MANDT    001
        | `Input Text`    wnd[0]/usr/txtRSYST-BNAME    DEVELOPER
        | `Input Password`    wnd[0]/usr/pwdRSYST-BCODE    ${SAP_PASSWORD}
        | `Send Vkey`    0
        | ${transaction}=    `Get Current Transaction`
        | Should Be Equal    ${transaction}    SESSION_MANAGER
        """
        self._writable_text_type(element_id, "input password")
        self.session.findById(element_id).text = reveal_secret(password)
        logger.info("Typing password into text field '%s'." % element_id)
        self._explicit_pause()

    def select_checkbox(self, element_id):
        """Coche la case ``element_id`` (sans effet si elle l'est déjà) et
        RELIT son état : une case protégée qui reste décochée échoue.

        Exemple :
        | `Run Transaction`    SM37
        | `Select Checkbox`    wnd[0]/usr/chkBTCH2170-PRELIM
        | ${state}=    `Get Value`    wnd[0]/usr/chkBTCH2170-PRELIM
        | Should Be Equal    ${state}    checked
        """
        self._set_selected(element_id, "GuiCheckBox", "select checkbox", True)

    def unselect_checkbox(self, element_id):
        """Décoche la case ``element_id`` (sans effet si elle l'est déjà) et
        RELIT son état.

        Exemple :
        | `Run Transaction`    SM37
        | `Unselect Checkbox`    wnd[0]/usr/chkBTCH2170-ABORTED
        | ${state}=    `Get Value`    wnd[0]/usr/chkBTCH2170-ABORTED
        | Should Be Equal    ${state}    unchecked
        | `Select Checkbox`    wnd[0]/usr/chkBTCH2170-ABORTED
        """
        self._set_selected(element_id, "GuiCheckBox", "unselect checkbox", False)

    def select_radio_button(self, element_id):
        """Sélectionne le bouton radio ``element_id`` et RELIT son état.

        Exemple :
        | `Run Transaction`    SE38
        | `Select Radio Button`    wnd[0]/usr/radRS38M-FUNC_HEAD
        | ${state}=    `Get Value`    wnd[0]/usr/radRS38M-FUNC_HEAD
        | Should Be Equal    ${state}    checked
        """
        self._set_selected(element_id, "GuiRadioButton", "select radio button", True)

    def send_vkey(self, vkey_id, window=0):
        """Envoie une touche virtuelle SAP à la fenêtre ``wnd[window]`` (pas à
        un champ : pour saisir, `Input Text`). ``vkey_id`` est un numéro
        (``0`` = Entrée, ``3`` = F3, ``8`` = F8, ``12`` = F12...) ou une
        combinaison (``F8``, ``Ctrl+S``, ``Shift+F3``, ``Esc`` ; casse et
        espaces indifférents). Table complète : ``sapfx_common.vkeys``. Une
        combinaison inconnue échoue en proposant les plus proches. La
        synchronisation reste à l'appelant.

        Exemple :
        | `Input Text`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SCARR
        | `Send Vkey`    Enter
        | `Wait Until Busy Done`
        | `Send Vkey`    F8
        | `Wait Until Busy Done`
        | `Element Should Be Present`    wnd[0]/usr/cntlGRID1/shellcont/shell
        """
        number = resolve_vkey(vkey_id)
        try:
            self.session.findById("wnd[%s]" % window).sendVKey(number)
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot send Vkey to given window, is window wnd[%s] "
                             "actually open?" % window) from None
        self._explicit_pause()

    # -- relecture --------------------------------------------------------------

    def _writable_text_type(self, element_id, keyword_name):
        """Le type de ``element_id`` s'il accepte une saisie de texte, sinon
        ``ValueError`` (un shell qui n'est pas un éditeur de texte nomme son
        sous-type)."""
        element_type = self.get_element_type(element_id)
        if element_type in _TEXT_FIELDS:
            return element_type
        if element_type == "GuiShell":
            subtype = self._shell_subtype(element_id)
            if subtype in _TEXT_SHELL_SUBTYPES:
                return element_type
            self.take_screenshot()
            raise ValueError(
                "Cannot use keyword '%s' on GuiShell/%s '%s' : seul un éditeur de "
                "texte (TextEdit) reçoit une saisie." % (keyword_name, subtype or "?", element_id))
        self.take_screenshot()
        raise ValueError("Cannot use keyword '%s' for element type '%s'"
                         % (keyword_name, element_type))

    def _text_should_have_been_written(self, element_id, expected):
        """Relit ``element_id`` après une saisie ; un écart lève en nommant la
        valeur obtenue et, quand l'API la donne, la longueur maximale du
        champ. Les fins de ligne et les blancs de fin ne comptent pas (un
        éditeur normalise ses retours à la ligne)."""
        element = self.session.findById(element_id)
        actual = str(element.text or "")

        def normalized(text):
            return str(text).replace("\r\n", "\n").rstrip()

        if normalized(actual) == normalized(expected):
            return
        try:
            limit = " (longueur maximale du champ : %s)" % int(element.MaxLength)
        except (AttributeError, com_error, TypeError, ValueError):
            limit = ""
        self.take_screenshot()
        raise AssertionError(
            "Le champ '%s' porte '%s' après la saisie de '%s'%s : la valeur n'a pas "
            "été écrite telle quelle." % (element_id, actual, expected, limit))

    def _set_selected(self, element_id, expected_type, keyword_name, target):
        """Pose l'état ``selected`` d'une case ou d'un radio puis le RELIT sur
        l'élément ré-acquis (une case à code fonction peut reconstruire
        l'écran)."""
        element_type = self.get_element_type(element_id)
        if element_type != expected_type:
            self.take_screenshot()
            raise ValueError("Cannot use keyword '%s' for element type '%s'"
                             % (keyword_name, element_type))
        self.session.findById(element_id).selected = target
        self.wait_until_busy_done()
        try:
            reached = bool(self.session.findById(element_id).selected)
        except com_error:
            self.take_screenshot()
            raise AssertionError(
                "'%s' a disparu après '%s' : l'écran a changé, l'état atteint n'est "
                "plus vérifiable." % (element_id, keyword_name)) from None
        if reached != target:
            self.take_screenshot()
            raise AssertionError(
                "'%s' est resté %s après '%s' : élément protégé ou écran en affichage "
                "(voir Element Is Changeable)."
                % (element_id, "coché" if reached else "décoché", keyword_name))
        self._explicit_pause()
