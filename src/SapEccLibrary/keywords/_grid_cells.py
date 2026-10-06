"""Mixin primitives de grille et de table : cellules, lignes, colonnes, barre
d'outils, défilement.

Une partie de ce module dérive de robotframework-sapguilibrary 1.2.1
(Copyright Frank van der Kuur, Apache License 2.0, voir NOTICE), absorbée et
réécrite pour SAPFX le 2026-10-06, noms et signatures inchangés
(``tests/unit/test_upstream_compatibility.py``). Ce qui a changé :

* le localisateur d'une grille ALV peut viser le CONTENEUR qui l'enveloppe
  (les releases récentes l'emballent dans des ``GuiSplitterShell``) : la
  grille réelle est résolue par `_resolved_grid_id` (mixin des grilles) ;
* `Set Cell Value` RELIT la cellule, comme `Input Text` relit un champ ;
* `Click Toolbar Button` ne capture plus l'écran sur le simple repli vers
  ``pressButton`` (une barre d'outils autonome), seulement sur un échec.

Les lectures ALV de haut niveau (`Read Grid`, par titre, par contenu) vivent
dans ``_grid.py`` ; les actions (double-clic, menu contextuel, tri) dans
``_grid_actions.py``.
"""
from pythoncom import com_error
from robot.api import logger


class GridCellKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`."""

    def get_row_count(self, table_id):
        """Nombre de lignes d'une grille, y compris quand le localisateur vise
        le conteneur qui l'enveloppe (releases récentes).

        Exemple :
        | ${count}=    `Get Row Count`    wnd[0]/usr/cntlGRID1/shellcont/shell
        | Should Be True    ${count} > 0
        """
        table_id = self._resolved_grid_id(table_id)
        self.element_should_be_present(table_id)
        return self.session.findById(table_id).rowCount

    def get_cell_value(self, table_id, row_num, col_id):
        """Valeur de la cellule (ligne ``row_num`` à partir de 0, colonne
        d'identifiant technique ``col_id``), localisateur de conteneur toléré.
        Colonne inconnue = échec.

        Exemple :
        | ${carrier}=    `Get Cell Value`    wnd[0]/usr/cntlGRID1/shellcont/shell    0    CARRID
        | Should Be Equal    ${carrier}    AA
        """
        table_id = self._resolved_grid_id(table_id)
        self.element_should_be_present(table_id)
        try:
            return self.session.findById(table_id).getCellValue(row_num, col_id)
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot find Column_id '%s'." % col_id) from None

    def set_cell_value(self, table_id, row_num, col_id, text):
        """Écrit ``text`` dans une cellule d'une grille modifiable puis RELIT
        la cellule : un écart échoue en nommant la valeur obtenue.
        Localisateur de conteneur toléré.

        Exemple :
        | `Set Cell Value`    wnd[1]/usr/cntlBCALV_GRID_DEMO_0100_CONT1/shellcont/shell    0    PRICE    999.00
        | ${price}=    `Get Cell Value`    wnd[1]/usr/cntlBCALV_GRID_DEMO_0100_CONT1/shellcont/shell    0    PRICE
        | Should Be Equal    ${price}    999.00
        """
        table_id = self._resolved_grid_id(table_id)
        self.element_should_be_present(table_id)
        grid = self.session.findById(table_id)
        try:
            grid.modifyCell(row_num, col_id, text)
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot type text '%s' into cell '%s', '%s'"
                             % (text, row_num, col_id)) from None
        logger.info("Typing text '%s' into cell '%s', '%s'" % (text, row_num, col_id))
        actual = str(self.session.findById(table_id).getCellValue(row_num, col_id) or "")
        if actual.rstrip() != str(text).rstrip():
            self.take_screenshot()
            raise AssertionError(
                "La cellule (%s, %s) de '%s' porte '%s' après la saisie de '%s' : "
                "cellule protégée ou grille en affichage." % (row_num, col_id, table_id,
                                                              actual, text))
        self._explicit_pause()

    def click_toolbar_button(self, table_id, button_id):
        """Clique le bouton ``button_id`` de la barre d'outils PROPRE d'une
        grille (``&FIND``, ``&SORT_ASC``...), ou d'une barre d'outils
        autonome. Localisateur de conteneur toléré.

        Exemple :
        | `Click Toolbar Button`    wnd[0]/usr/cntlBCALV_GRID_DEMO_0100_CONT1/shellcont/shell    &FIND
        | `Dismiss Modal Window`
        """
        table_id = self._resolved_grid_id(table_id)
        self.element_should_be_present(table_id)
        shell = self.session.findById(table_id)
        try:
            try:
                shell.pressToolbarButton(button_id)
            except AttributeError:
                shell.pressButton(button_id)     # barre d'outils autonome
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot find Button_id '%s'." % button_id) from None
        self._explicit_pause()

    def select_table_row(self, table_id, row_num):
        """Sélectionne une ligne entière (index à partir de 0) d'une grille ALV
        ou d'un table control (``GuiTableControl``, ligne ABSOLUE).

        Exemple :
        | `Select Table Row`    wnd[0]/usr/cntlGRID1/shellcont/shell    0
        | `Click Application Toolbar Button`    B_DETL
        | ${screen}=    `Get Current Screen`
        | Should Be Equal    ${screen}[program]    SAPLSLVC_SERVICES
        | `Dismiss Modal Window`
        """
        table_id = self._resolved_grid_id(table_id)
        element_type = self.get_element_type(table_id)
        table = self.session.findById(table_id)
        if element_type == "GuiTableControl":
            table.getAbsoluteRow(row_num).selected = -1
        else:
            try:
                table.selectedRows = row_num
            except com_error:
                self.take_screenshot()
                raise ValueError("Cannot use keyword 'select table row' for element "
                                 "type '%s'" % element_type) from None
        self._explicit_pause()

    def select_table_column(self, table_id, column_id):
        """Sélectionne une colonne entière d'une grille ALV par son identifiant
        technique ; colonne inconnue = échec.

        Exemple :
        | `Select Table Column`    wnd[0]/usr/cntlGRID1/shellcont/shell    CARRNAME
        | ${columns}=    `Get Grid Column Ids`    wnd[0]/usr/cntlGRID1/shellcont/shell
        | List Should Contain Value    ${columns}    CARRNAME
        """
        table_id = self._resolved_grid_id(table_id)
        self.element_should_be_present(table_id)
        try:
            self.session.findById(table_id).selectColumn(column_id)
        except com_error:
            self.take_screenshot()
            raise ValueError("Cannot find Column_id '%s'." % column_id) from None
        self._explicit_pause()

    def scroll(self, element_id, position):
        """Place la barre de défilement verticale de ``element_id`` (un table
        control, une zone d'écran défilante) sur la ligne ``position``. Une
        grille ALV défile par `Read Full Grid`.

        Exemple :
        | `Scroll`    wnd[0]/usr/tabsTAB_STRIP/tabpDEF/ssubTS_SCREEN:SAPLSD41:2201/tblSAPLSD41TC0    2
        | ${position}=    `Get Scroll Position`    wnd[0]/usr/tabsTAB_STRIP/tabpDEF/ssubTS_SCREEN:SAPLSD41:2201/tblSAPLSD41TC0
        | Should Be Equal As Integers    ${position}    2
        """
        self.element_should_be_present(element_id)
        self.session.findById(element_id).verticalScrollbar.position = position
        self._explicit_pause()

    def get_scroll_position(self, element_id):
        """Position de la barre de défilement verticale de ``element_id``.

        Exemple :
        | ${position}=    `Get Scroll Position`    wnd[0]/usr/tabsTAB_STRIP/tabpDEF/ssubTS_SCREEN:SAPLSD41:2201/tblSAPLSD41TC0
        | Should Be Equal As Integers    ${position}    0
        """
        self.element_should_be_present(element_id)
        return self.session.findById(element_id).verticalScrollbar.position
