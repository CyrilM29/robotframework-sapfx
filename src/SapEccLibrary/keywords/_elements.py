"""Mixin éléments : présence, type, valeur et focus d'un élément d'écran.

Une partie de ce module dérive de robotframework-sapguilibrary 1.2.1
(Copyright Frank van der Kuur, Apache License 2.0, voir NOTICE), absorbée et
réécrite pour SAPFX le 2026-10-06 : `Get Element Type`, `Element Should Be
Present`, `Get Value`, `Set Focus`, `Get Element Location`, `Get Window
Title` et `Maximize Window` gardent leur nom et leur signature (promesse de
compatibilité, ``tests/unit/test_upstream_compatibility.py``). Ce qui a
changé, et pourquoi :

* une absence nomme l'écran RÉEL (`# screen ...`), parce qu'un id manquant
  ne distingue pas un localisateur périmé d'un écran qui n'est pas celui
  qu'on croit ;
* `Get Value` ne prend plus le focus : une lecture ne modifie rien. Elle
  refuse le ProgID d'un shell, valeur plausible qui n'a rien lu ;
* un type d'élément non pris en charge lève ``ValueError`` (erreur
  d'usage) au lieu d'un ``Warning``.

`Element Is Changeable` et ses deux assertions vivent ici aussi : ce sont
des lectures d'état d'un élément, au même titre que sa valeur.
"""
from pythoncom import com_error

from sapfx_common.tree_nodes import is_progid

# Le keyword qui sait lire un shell, nommé quand `Get Value` refuse son ProgID.
_SHELL_READERS = {
    "GridView": "Lire la grille avec Read Grid / Get Cell Value.",
    "Tree": "Lire l'arbre avec Read Tree Nodes / Get Selected Tree Node.",
    "Calendar": "Choisir une date avec Pick Calendar Date.",
    "AbapEditor": "Le source d'un éditeur ABAP est hors de l'API Scripting : "
                  "aucune lecture possible (Click Element At Offset pour agir).",
    "HTMLViewer": "Le contenu d'un HTMLViewer est hors de l'API Scripting.",
    "Picture": "Une image n'a pas de valeur lisible.",
    "Toolbar": "Lister les boutons avec List Grid Toolbar Buttons sur la grille "
               "porteuse, ou Get Screen Signature.",
}
_SHELL_READERS_DEFAULT = ("Percevoir le contrôle avec Get Screen Signature "
                          "(colonne type GuiShell/<SubType>).")

# Types dont la valeur est le texte affiché.
_TEXT_TYPES = ("GuiTextField", "GuiCTextField", "GuiLabel", "GuiTitlebar",
               "GuiStatusbar", "GuiStatusPane", "GuiButton", "GuiTab", "GuiShell")


class ElementKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lectures d'élément ; seuls
    `Set Focus` et `Maximize Window` agissent sur l'écran."""

    def get_element_type(self, element_id):
        """Retourne le type SAP de ``element_id`` (``GuiButton``, ``GuiTab``...).

        Un élément absent échoue en nommant l'écran courant. C'est le chemin
        par lequel passe `Click Element`, qui résout le type avant d'agir :
        sans cet enrichissement, un clic sur un écran inattendu ne rapporte
        que l'id manquant.

        Exemple :
        | ${type}=    `Get Element Type`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        | Should Be Equal    ${type}    GuiCTextField
        """
        try:
            return self.session.findById(element_id).type
        except com_error:
            self.take_screenshot()
            raise ValueError(self._absence_message(
                "Cannot find element with id '%s'" % element_id)) from None

    def element_should_be_present(self, element_id, message=None):
        """Échoue si ``element_id`` est absent de l'écran courant.

        Le message d'échec nomme l'écran réel (voir `Get Element Type`). Un
        ``message`` explicite fourni par l'appelant est respecté tel quel :
        c'est sa phrase, pas la nôtre.

        Exemple :
        | `Element Should Be Present`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        """
        try:
            self.session.findById(element_id)
        except com_error:
            self.take_screenshot()
            if message is not None:
                raise ValueError(message) from None
            raise ValueError(self._absence_message(
                "Cannot find Element '%s'." % element_id)) from None

    def get_value(self, element_id):
        """Retourne la valeur de ``element_id``, selon son type : le texte d'un
        champ, d'un libellé, d'un bouton, d'un onglet, d'une barre de titre ou
        de statut ; ``checked`` / ``unchecked`` pour une case ou un bouton
        radio ; le libellé de l'entrée choisie pour une combo (blancs de fin
        retirés, `Get Combo Box Key` rend la clé).

        Une lecture ne prend pas le focus (l'amont le faisait, effet de bord
        retiré le 2026-10-06). Un ``GuiShell`` dont le ``Text`` est le ProgID
        du contrôle (``SAP.TableTreeControl.1``, ``SAPGUI.AbapEditor.1``) est
        REFUSÉ en nommant le keyword qui sait le lire : relevé le 2026-09-07,
        c'est une valeur plausible qui n'a rien lu. Un shell dont le texte est
        une vraie donnée (un ``TextEdit``) reste lu tel quel. Type non pris en
        charge = ``ValueError``.

        Exemple :
        | `Input Text`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
        | ${table}=    `Get Value`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        | Should Be Equal    ${table}    T000
        """
        element_type = self.get_element_type(element_id)
        element = self.session.findById(element_id)
        if element_type in ("GuiCheckBox", "GuiRadioButton"):
            return "checked" if element.selected else "unchecked"
        if element_type == "GuiComboBox":
            return str(element.text or "").strip()
        if element_type not in _TEXT_TYPES:
            self.take_screenshot()
            raise ValueError("Cannot get value for element type '%s'" % element_type)
        value = element.text
        if element_type == "GuiShell" and isinstance(value, str) and is_progid(value):
            subtype = self._shell_subtype(element_id)
            raise ValueError(
                "Get Value sur '%s' rendrait le ProgID '%s' du contrôle, pas une "
                "donnée d'écran (GuiShell%s). %s"
                % (element_id, value.strip(), "/%s" % subtype if subtype else "",
                   _SHELL_READERS.get(subtype, _SHELL_READERS_DEFAULT)))
        return value

    def _shell_subtype(self, element_id):
        """Sous-type d'un shell (``Tree``, ``GridView``...), ou ``""``."""
        try:
            return str(self.session.findById(element_id).SubType or "").strip()
        except (AttributeError, com_error):
            return ""

    def set_focus(self, element_id):
        """Place le focus sur ``element_id`` (sans effet sur un volet de la
        barre de statut, qui ne le prend pas).

        Exemple :
        | `Set Focus`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        | ${type}=    `Get Element Type`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        | Should Be Equal    ${type}    GuiCTextField
        """
        if self.get_element_type(element_id) != "GuiStatusPane":
            self.session.findById(element_id).setFocus()
        self._explicit_pause()

    def get_element_location(self, element_id):
        """Position ÉCRAN de ``element_id`` : le couple ``(gauche, haut)`` en
        pixels physiques (``ScreenLeft`` / ``ScreenTop``). `Get Element Screen
        Region` rend aussi la largeur et la hauteur.

        Exemple :
        | ${left}    ${top}=    `Get Element Location`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        | Should Be True    ${left} > 0 and ${top} > 0
        """
        self.element_should_be_present(element_id)
        element = self.session.findById(element_id)
        return element.screenLeft, element.screenTop

    def get_window_title(self, locator):
        """Titre de la fenêtre ``locator`` (``wnd[0]``, ``wnd[1]``...). Le titre
        est traduit : pour une assertion, préférer `Get Current Screen` ou
        `Get Current Transaction`.

        Exemple :
        | `Open System Status`
        | ${title}=    `Get Window Title`    wnd[1]
        | Should Not Be Empty    ${title}
        | `Dismiss Modal Window`
        """
        try:
            return self.session.findById(locator).text
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot find window with locator '%s'" % locator) from None

    def maximize_window(self, window=0):
        """Agrandit la fenêtre ``wnd[window]`` (défaut : la principale).

        Exemple :
        | `Maximize Window`
        | `Element Should Be Present`    wnd[0]/usr
        """
        try:
            self.session.findById("wnd[%s]" % window).maximize()
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot maximize window wnd[%s], is the window actually "
                             "open?" % window) from None
        self._explicit_pause()

    def element_is_changeable(self, element_id):
        """``True`` si ``element_id`` est MODIFIABLE (propriété ``Changeable``
        de l'API Scripting), ``False`` sinon. Sur un bouton, elle dit s'il est
        actif. Lève si l'élément est absent, avec l'écran réel nommé (même
        message que `Element Should Be Present`), et si la propriété est
        ILLISIBLE (voir plus bas).

        C'est le témoin locale-safe du MODE d'une transaction à bascule
        Affichage/Modification (BP, SU01, ...) : le titre de la fenêtre
        (« Display Organization » / « Change Organization ») est traduit, et
        la bascule (F6) est un interrupteur, donc la presser sans savoir où
        l'on part peut ramener en affichage. Relevé le 2026-09-28 sur la
        transaction BP, qui rouvre le dernier partenaire dans son DERNIER
        mode. Une propriété illisible n'est jamais lue comme « non
        modifiable » : l'échec le dit.

        Exemple :
        | ${editable}=    `Element Is Changeable`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        | Should Be True    ${editable}
        """
        self.element_should_be_present(element_id)
        element = self.session.findById(element_id)
        try:
            changeable = element.Changeable
        except Exception as exc:   # noqa: BLE001 : re-levé en nommant l'élément
            raise AssertionError(
                "La modifiabilité de '%s' (%s) est illisible : %s. Rien ne peut "
                "en être conclu, ni affichage ni modification."
                % (element_id, getattr(element, "Type", "type inconnu"), exc)) from exc
        return bool(changeable)

    def element_should_be_changeable(self, element_id, message=None):
        """Échoue si ``element_id`` n'est pas modifiable (voir `Element Is
        Changeable`) : l'écran est en affichage, ou le champ est protégé.
        ``message`` remplace le message par défaut.

        Exemple :
        | `Element Should Be Changeable`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME
        """
        if not self.element_is_changeable(element_id):
            self.take_screenshot()
            raise AssertionError(message or (
                "L'élément '%s' n'est pas modifiable (Changeable=False) : écran en "
                "affichage, ou champ protégé.\n%s"
                % (element_id, self._absence_message("").strip())))

    def element_should_not_be_changeable(self, element_id, message=None):
        """Échoue si ``element_id`` est modifiable (voir `Element Is
        Changeable`) : la garde qu'un écran est bien en AFFICHAGE avant d'y
        lire une valeur qu'une saisie accidentelle ne doit pas toucher.

        Exemple :
        | `Open System Status`
        | `Element Should Not Be Changeable`    wnd[1]/usr/txtSYST-MANDT
        | `Dismiss Modal Window`
        """
        if self.element_is_changeable(element_id):
            self.take_screenshot()
            raise AssertionError(message or (
                "L'élément '%s' est modifiable (Changeable=True) alors qu'il ne "
                "devait pas l'être : l'écran est en modification ou en création.\n%s"
                % (element_id, self._absence_message("").strip())))

    def _absence_message(self, message):
        """Suffixe un message d'élément absent par l'IDENTITÉ de l'écran actif.

        « Cannot find element with id 'wnd[0]/tbar[1]/btn[31]' » ne
        distingue pas les trois causes possibles : localisateur périmé,
        élément pas encore matérialisé, ou écran qui n'est pas celui
        qu'on croit. La troisième est la plus fréquente en ECC (une
        transaction qui refuse une saisie reste sur l'écran précédent) et
        c'est la seule que l'id seul ne peut pas révéler. Une ligne
        ``# screen <Programme>/<Transaction>/<Numéro>`` tranche
        immédiatement, pour un humain comme pour un agent.

        Mesuré le 2026-08-17 : le même `Click Element` avait réussi
        vingt étapes plus tôt dans la session, puis échoué sur la table
        suivante ; sans l'écran, le diagnostic généré a conclu à un
        problème de synchronisation et a été rejeté par le juge.

        Best-effort : le calcul ne masque jamais l'erreur d'origine, et le
        mixin de perception peut être absent (usage isolé en tests
        unitaires).
        """
        header = getattr(self, "_screen_header", None)
        if header is None:
            return message
        try:
            return "%s\n%s" % (message, header())
        except Exception:                       # noqa: BLE001 (best-effort)
            return message
