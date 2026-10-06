"""Mixin vérifications de valeur : `Element Value Should Be` et `Contain`.

Ces deux keywords dérivent de robotframework-sapguilibrary 1.2.1 (Copyright
Frank van der Kuur, Apache License 2.0, voir NOTICE), absorbée et réécrite
pour SAPFX le 2026-10-06, nom et signature inchangés
(``tests/unit/test_upstream_compatibility.py``). Le recorder bureau les
génère (Ctrl+Alt+A). Ce qui a changé :

* une vérification ne modifie rien : l'amont posait le focus sur l'élément
  avant de le lire ;
* les erreurs disent leur nature : ``AssertionError`` pour un écart (avec
  la valeur attendue ET la valeur lue, y compris pour une case),
  ``ValueError`` pour une erreur d'usage (type d'élément non pris en charge,
  état de case autre que ``checked`` / ``unchecked``), là où l'amont mêlait
  ``Warning``, ``ValueError`` et ``AssertionError``.
"""

_TEXT_TYPES = ("GuiTextField", "GuiCTextField", "GuiComboBox", "GuiTitlebar",
               "GuiButton", "GuiLabel", "GuiStatusPane", "GuiStatusbar", "GuiTab")
_TOGGLE_TYPES = ("GuiCheckBox", "GuiRadioButton")
_TOGGLE_STATES = ("checked", "unchecked")


class ValueCheckKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule."""

    def element_value_should_be(self, element_id, expected_value, message=None):
        """Échoue si la valeur de ``element_id`` (voir `Get Value`) n'est pas
        exactement ``expected_value``. Pour une case ou un bouton radio,
        ``expected_value`` vaut ``checked`` ou ``unchecked`` (casse
        indifférente). ``message`` remplace le message d'écart.

        Exemple :
        | `Input Text`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
        | `Element Value Should Be`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000
        """
        element_type, actual = self._checkable_value(
            element_id, "element value should be", _TEXT_TYPES + _TOGGLE_TYPES)
        expected = str(expected_value)
        if element_type in _TOGGLE_TYPES:
            expected = expected.lower()
            if expected not in _TOGGLE_STATES:
                raise ValueError(
                    "Incorrect value '%s' for element type '%s', provide checked or "
                    "unchecked" % (expected_value, element_type))
        if actual != expected:
            self.take_screenshot()
            raise AssertionError(message or (
                "Element value of '%s' should be '%s', but was '%s'"
                % (element_id, expected, actual)))
        self._explicit_pause()

    def element_value_should_contain(self, element_id, expected_value, message=None):
        """Échoue si la valeur de ``element_id`` (voir `Get Value`) ne contient
        pas ``expected_value``. Réservé aux éléments à texte (champ, libellé,
        bouton, onglet, combo, barre de titre ou de statut). ``message``
        remplace le message d'écart.

        Exemple :
        | `Input Text`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    SCARR
        | `Element Value Should Contain`    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    CARR
        """
        _type, actual = self._checkable_value(
            element_id, "element value should contain", _TEXT_TYPES)
        if str(expected_value) not in actual:
            self.take_screenshot()
            raise AssertionError(message or (
                "Element value '%s' does not contain '%s', (but was '%s')"
                % (element_id, expected_value, actual)))
        self._explicit_pause()

    def _checkable_value(self, element_id, keyword_name, supported):
        """``(type, valeur)`` de ``element_id``, ou ``ValueError`` si le
        keyword ne sait pas vérifier ce type d'élément."""
        element_type = self.get_element_type(element_id)
        if element_type not in supported:
            self.take_screenshot()
            raise ValueError("Cannot use keyword '%s' for element type '%s'"
                             % (keyword_name, element_type))
        return element_type, str(self.get_value(element_id))
