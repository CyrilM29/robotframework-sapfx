"""Keywords des **GuiTableControl** : les tables de dynpro classiques.

Un table control (saisie de postes, listes de champs SE11, transactions de
premiere generation) n'est pas une grille ALV : il ne materialise que ses
lignes VISIBLES et son ``RowCount`` annonce les lignes RESERVEES par l'ecran,
pas les lignes remplies (constate live sur SE11/SNWD_PD : 47 annoncees, 26
remplies). Ce mixin adresse les colonnes par leur titre visible comme le fait
`Read Grid` cote ALV, fait defiler par fenetres via la scrollbar verticale et
re-acquiert l'objet COM apres chaque defilement. La logique pure (titres
dedoublonnes, plan de defilement, position d'une ligne absolue) vit dans
``sapfx_common.table_control``.

Extrait de ``_grid.py`` (convention #13 : un fichier, un metier) : l'ALV et
les listes ABAP restent la-bas, les deux mixins se composent dans
:class:`SapEccLibrary`.
"""
from pythoncom import com_error
from robot.api import logger

from sapfx_common import table_control


class TableControlKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Opère sur les GuiTableControl
    (tables de dynpro classiques), par titre de colonne visible."""

    def read_table_control(self, table_id, max_rows=None):
        """Lit un **GuiTableControl** (table de dynpro classique : saisie de
        postes, listes de champs SE11…) en liste de dicts
        ``[{titre_de_colonne: texte}]``.

        Un table control ne matérialise que ses lignes VISIBLES : la lecture
        fait défiler la table par fenêtres via la scrollbar verticale et
        ré-acquiert l'objet COM après chaque défilement (un aller-retour
        serveur), le tout transparent pour le test. Colonnes sans titre
        nommées ``COL<n>``, titres en doublon suffixés ``(2)``… : rien n'est
        perdu en silence. ``max_rows`` plafonne la lecture (journalisé). La
        position de défilement initiale est restaurée à la fin.

        Piège vérifié live (SE11) : ``RowCount`` annonce les lignes
        **réservées** par l'écran (47), pas les lignes remplies (26) ; les
        lignes non matérialisées lèvent côté COM. Ce keyword retourne donc
        les lignes RÉELLEMENT remplies et s'arrête à la première ligne dont
        aucune cellule n'existe : jamais de lignes fantômes dans le résultat.
        Pour une grille **ALV**, utiliser `Read Grid` (l'erreur redirige)."""
        table = self._table_control(table_id)
        titles = table_control.unique_titles(self._table_column_titles(table))
        total = int(getattr(table, "RowCount", 0) or 0)
        if max_rows is not None and total > int(max_rows):
            logger.warn(
                "Table control '%s' reserves %s rows; reading at most %s "
                "(max_rows)." % (table_id, total, max_rows))
            total = int(max_rows)
        visible = int(getattr(table, "VisibleRowCount", 0) or 0)
        original = self._table_scroll_position(table)
        rows = []
        for position, first_local, count in table_control.window_plan(total, visible):
            table = self._scroll_table_to(table_id, position)
            exhausted = False
            for local in range(first_local, first_local + count):
                values = [self._cell_text(table, local, index)
                          for index, _ in enumerate(titles)]
                if all(value is None for value in values):
                    exhausted = True   # ligne réservée, jamais remplie : fin
                    break
                rows.append({title: (value or "")
                             for title, value in zip(titles, values, strict=True)})
            if exhausted:
                break
        self._scroll_table_to(table_id, original, best_effort=True)
        return rows

    def get_table_control_cell(self, table_id, row, column_title):
        """Texte de la cellule ``(ligne absolue, titre de colonne)`` d'un
        table control : ``row`` est l'index **absolu** 0-based, le défilement
        jusqu'à la fenêtre qui contient la ligne est automatique."""
        table = self._table_control(table_id)
        column = table_control.column_index_by_title(
            self._table_column_titles(table), column_title, table_id)
        position, local = table_control.window_for_row(
            int(row), int(getattr(table, "RowCount", 0) or 0),
            int(getattr(table, "VisibleRowCount", 0) or 0))
        table = self._scroll_table_to(table_id, position)
        text = self._cell_text(table, local, column)
        if text is None:
            self.take_screenshot()
            raise AssertionError(
                "La ligne %s de '%s' n'est pas remplie : RowCount annonce %s "
                "lignes RÉSERVÉES par l'écran, pas remplies (piège des table "
                "controls). Read Table Control retourne les lignes réellement "
                "remplies : compter dessus pour borner les indices."
                % (row, table_id, getattr(table, "RowCount", "?")))
        return text

    def set_table_control_cell(self, table_id, row, column_title, value):
        """Écrit ``value`` dans la cellule ``(ligne absolue, titre de
        colonne)`` d'un table control : la saisie des transactions classiques
        adressée comme l'ALV, par titre visible. Cellule non modifiable =
        échec actionnable nommant la colonne. Retourne l'id de la table."""
        table = self._table_control(table_id)
        column = table_control.column_index_by_title(
            self._table_column_titles(table), column_title, table_id)
        position, local = table_control.window_for_row(
            int(row), int(getattr(table, "RowCount", 0) or 0),
            int(getattr(table, "VisibleRowCount", 0) or 0))
        table = self._scroll_table_to(table_id, position)
        cell = table.GetCell(local, column)
        if not getattr(cell, "Changeable", True):
            self.take_screenshot()
            raise AssertionError(
                "La cellule (ligne %s, colonne '%s') de '%s' n'est pas "
                "modifiable (Changeable=False) : colonne d'affichage, ou "
                "écran en mode consultation." % (row, column_title, table_id))
        cell.Text = value
        return table_id

    def find_table_control_row(self, table_id, column_title, value,
                               ignore_case=False):
        """Index **absolu** (0-based) de la première ligne dont la colonne
        ``column_title`` vaut ``value``, ou ``-1`` si aucune (miroir de
        `Find Row By Column Value` côté ALV) : le défilement de recherche à
        travers toutes les fenêtres est automatique, et la recherche s'arrête
        à la fin des lignes réellement remplies (cf. `Read Table Control`)."""
        table = self._table_control(table_id)
        column = table_control.column_index_by_title(
            self._table_column_titles(table), column_title, table_id)
        total = int(getattr(table, "RowCount", 0) or 0)
        visible = int(getattr(table, "VisibleRowCount", 0) or 0)
        wanted = value.lower() if ignore_case else value
        for position, first_local, count in table_control.window_plan(total, visible):
            table = self._scroll_table_to(table_id, position)
            for local in range(first_local, first_local + count):
                cell = self._cell_text(table, local, column)
                if cell is None:
                    return -1   # fin des lignes remplies
                if (cell.lower() if ignore_case else cell) == wanted:
                    return position + local
        return -1

    def _table_control(self, table_id):
        self.element_should_be_present(table_id)
        table = self.session.findById(table_id)
        if hasattr(table, "ColumnOrder"):
            raise ValueError(
                "Element '%s' est une grille ALV (GuiGridView) : utiliser "
                "Read Grid / Get Cell Value By Column Title, pas les keywords "
                "Table Control." % table_id)
        if not hasattr(table, "GetCell") or not hasattr(table, "Columns"):
            self.take_screenshot()
            raise ValueError(
                "Element '%s' n'est pas un GuiTableControl (ni GetCell ni "
                "Columns)." % table_id)
        return table

    def _table_column_titles(self, table):
        """Titres BRUTS des colonnes (Title, repli Tooltip puis Name) : la
        normalisation (COL<n>, doublons) vit dans ``sapfx_common.table_control``."""
        columns = table.Columns
        titles = []
        for index in range(int(getattr(columns, "Count", 0) or 0)):
            column = columns.ElementAt(index)
            titles.append((getattr(column, "Title", "")
                           or getattr(column, "Tooltip", "")
                           or getattr(column, "Name", "") or "").strip())
        return titles

    @staticmethod
    def _cell_text(table, local_row, column):
        """Texte d'une cellule de table control, ou ``None`` si la cellule
        n'est pas MATÉRIALISÉE (``GetCell`` lève « invalid argument »).

        Constaté live (SE11/SNWD_PD) : ``RowCount`` annonce 47 lignes quand
        26 seulement sont remplies ; les lignes réservées n'ont aucune
        cellule. ``None`` distingue « cellule absente » (fin des données) de
        « cellule vide » (valeur légitime), ce dont dépendent l'arrêt de la
        lecture et l'échec actionnable de `Get Table Control Cell`."""
        try:
            return table.GetCell(local_row, column).Text
        except com_error:
            return None

    @staticmethod
    def _table_scroll_position(table):
        scrollbar = getattr(table, "VerticalScrollbar", None)
        if scrollbar is None:
            return 0
        return int(getattr(scrollbar, "Position", 0) or 0)

    def _scroll_table_to(self, table_id, position, best_effort=False):
        """Positionne la scrollbar verticale puis **ré-acquiert** l'objet
        table : le défilement d'un table control est un aller-retour serveur
        qui invalide l'objet COM. Position déjà atteinte = aucun aller-retour.
        ``best_effort`` (restauration de fin de lecture) avale une erreur COM."""
        table = self.session.findById(table_id)
        scrollbar = getattr(table, "VerticalScrollbar", None)
        if scrollbar is None:
            return table
        # La scrollbar plafonne à `total - visible` : une position au-delà
        # lève un com_error (constaté live sur SE11). `window_plan` borne déjà
        # ses positions ; cette borne est le garde-fou défensif pour les
        # tables de saisie dont RowCount inclut des lignes virtuelles.
        maximum = getattr(scrollbar, "Maximum", None)
        if maximum is not None:
            position = min(int(position), int(maximum))
        if int(getattr(scrollbar, "Position", 0) or 0) == int(position):
            return table
        try:
            scrollbar.Position = int(position)
            self.wait_until_busy_done()
        except com_error:
            if not best_effort:
                raise
            return table
        return self.session.findById(table_id)
