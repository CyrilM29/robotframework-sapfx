"""Keywords pratiques pour les tables ALV GridView.

L'upstream expose déjà les opérations primitives sur les grilles (`Get Cell Value`,
`Set Cell Value`, `Get Row Count`, `Select Table Row`, `Click Toolbar Button`).
Toutes nécessitent de connaître l'*identifiant technique* de la colonne (ex. ``"MATNR"``),
habituellement obtenu via l'enregistreur Scripting Tracker.

Ce mixin ajoute la couche ergonomique par-dessus : résoudre les colonnes par leur
*titre visible*, et lire une grille entière dans une liste de dicts compatible
Robot pour que les tests puissent faire des assertions sur les données plutôt que
sur les coordonnées de cellules.
"""
from pythoncom import com_error
from robot.api import logger

from sapfx_common.abap_list import reconstruct_rows


class GridKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Opère sur les objets shell GuiGridView
    (plus `Read Abap List` pour les sorties liste classiques, sans objet grille)."""

    def get_grid_column_ids(self, table_id):
        """Retourne la liste des identifiants techniques des colonnes d'une grille ALV, dans l'ordre d'affichage."""
        grid = self._grid(table_id)
        return [col for col in grid.ColumnOrder]

    def get_column_id_by_title(self, table_id, title):
        """Résout un ``title`` de colonne visible en son identifiant technique.

        La correspondance est insensible à la casse et ignore les espaces en bordure.
        Lève une exception si aucune colonne ne correspond — l'erreur liste les
        titres disponibles pour faciliter le débogage des localisateurs.
        """
        grid = self._grid(table_id)
        wanted = title.strip().lower()
        available = {}
        for col_id in grid.ColumnOrder:
            col_title = grid.GetDisplayedColumnTitle(col_id)
            available[col_id] = col_title
            if col_title.strip().lower() == wanted:
                return col_id
        self.take_screenshot()
        raise ValueError(
            "No column titled '%s' in grid '%s'. Available: %s"
            % (title, table_id, available)
        )

    def get_cell_value_by_column_title(self, table_id, row_num, title):
        """Comme `Get Cell Value` mais adresse la colonne par son titre visible."""
        col_id = self.get_column_id_by_title(table_id, title)
        return self.get_cell_value(table_id, row_num, col_id)

    def set_cell_value_by_column_title(self, table_id, row_num, title, text):
        """Comme `Set Cell Value` mais adresse la colonne par son titre visible.

        Le pendant en écriture de `Get Cell Value By Column Title` — évite d'avoir à
        connaître l'identifiant technique de colonne dans le test."""
        col_id = self.get_column_id_by_title(table_id, title)
        self.set_cell_value(table_id, row_num, col_id, text)

    def find_row_by_column_value(self, table_id, title, value, ignore_case=False):
        """Retourne l'index (base 0) de la **première** ligne dont la cellule de la
        colonne ``title`` vaut ``value``, ou ``-1`` si aucune.

        Ne lit que les lignes actuellement chargées (cf. `Read Grid`) ; pour une
        grande table, appeler `Read Full Grid` au préalable ou paginer. La
        comparaison est exacte par défaut ; ``ignore_case`` la rend insensible à la
        casse. Retourne ``-1`` plutôt que de lever, pour permettre un test
        d'existence — voir `Select Row By Column Value` pour la variante qui agit."""
        grid = self._grid(table_id)
        col_id = self.get_column_id_by_title(table_id, title)
        wanted = value.lower() if ignore_case else value
        for row in range(grid.RowCount):
            cell = grid.GetCellValue(row, col_id)
            if (cell.lower() if ignore_case else cell) == wanted:
                return row
        return -1

    def select_row_by_column_value(self, table_id, title, value, ignore_case=False):
        """Sélectionne la première ligne dont la colonne ``title`` vaut ``value``.

        Lève si aucune ligne ne correspond (l'erreur nomme la colonne et la valeur).
        Retourne l'index de la ligne sélectionnée pour permettre l'enchaînement."""
        row = self.find_row_by_column_value(table_id, title, value, ignore_case)
        if row < 0:
            self.take_screenshot()
            raise ValueError(
                "No row in grid '%s' has '%s' = '%s'." % (table_id, title, value)
            )
        self.select_table_row(table_id, row)
        return row

    def get_cell_value_by_row_content(self, table_id, anchor_title, anchor_value,
                                      target_title, ignore_case=False):
        """Lit la cellule ``target_title`` de la ligne repérée par son **contenu** :
        « la ligne dont ``anchor_title`` vaut ``anchor_value`` » — l'adressage
        ``contenu @ colonne`` (à la RoboSAPiens) appliqué à l'ALV. Aucun index de
        ligne dans le test : l'adressage survit au tri, au filtre et aux insertions.

        Lève si aucune ligne ne porte cette valeur (mêmes limites de chargement
        différé que `Find Row By Column Value`). Usage type::

            ${prix}=    Get Cell Value By Row Content    ${GRID}    Carrier    LH    Price
        """
        row = self.find_row_by_column_value(table_id, anchor_title, anchor_value,
                                            ignore_case)
        if row < 0:
            self.take_screenshot()
            raise ValueError(
                "No row in grid '%s' has '%s' = '%s'."
                % (table_id, anchor_title, anchor_value)
            )
        return self.get_cell_value_by_column_title(table_id, row, target_title)

    def read_full_grid(self, table_id, page_step=None, max_rows=None):
        """Comme `Read Grid` mais **fait défiler** la grille pour forcer le chargement
        différé de toutes les lignes avant de lire.

        SAP ne matérialise les lignes d'une ALV GridView qu'au fur et à mesure du
        défilement. On parcourt donc la grille par fenêtres de ``VisibleRowCount``
        (ou ``page_step`` si fourni) en repositionnant ``FirstVisibleRow``, puis on
        lit l'ensemble. ``max_rows`` plafonne le total lu (journalisé). Restaure la
        position de défilement initiale à la fin."""
        grid = self._grid(table_id)
        total = grid.RowCount
        if max_rows is not None:
            total = min(total, int(max_rows))
        step = int(page_step) if page_step else int(getattr(grid, "VisibleRowCount", 0) or 0)
        if step <= 0:
            step = total or 1
        original = getattr(grid, "FirstVisibleRow", 0)
        first = 0
        while first < total:
            grid.FirstVisibleRow = first      # déclenche le chargement de la fenêtre
            first += step
        try:
            grid.FirstVisibleRow = original
        except com_error:
            pass
        return self.read_grid(table_id, max_rows=max_rows)

    def read_grid(self, table_id, max_rows=None):
        """Lit une grille ALV dans une liste de dicts ``[{column_title: value, ...}]``.

        Seules les lignes actuellement chargées sont lues ; SAP charge les grilles
        en différé, donc pour les grandes tables faites défiler/paginer d'abord
        (voir `Scroll`) ou passez un plafond ``max_rows``. Le plafond est journalisé
        pour qu'une lecture tronquée ne soit jamais confondue avec une lecture complète.
        """
        grid = self._grid(table_id)
        row_count = grid.RowCount
        if max_rows is not None and row_count > int(max_rows):
            logger.warn(
                "Grid '%s' has %s rows; reading only the first %s (max_rows)."
                % (table_id, row_count, max_rows)
            )
            row_count = int(max_rows)
        columns = [(cid, grid.GetDisplayedColumnTitle(cid)) for cid in grid.ColumnOrder]
        rows = []
        for row in range(row_count):
            rows.append({title: grid.GetCellValue(row, cid) for cid, title in columns})
        return rows

    def read_abap_list(self):
        """Lit la **liste ABAP classique** affichée (sortie SE38, SE16 sans ALV,
        protocoles…) : lignes de cellules texte ``[[cellule, ...], ...]``, de
        haut en bas, cellules de gauche à droite.

        Ces écrans n'ont AUCUN objet grille scriptable — l'écran n'est qu'une
        nuée de ``GuiLabel`` : la structure est reconstruite par géométrie
        (``sapfx_common.abap_list``, via le même parcours structuré que la
        perception). Complémentaire de `Read Grid` (ALV) : plus besoin de
        forcer `Use ALV Grid In Data Browser` pour une simple assertion de
        contenu.

        **Prérequis vérifié live (A4H, SAP GUI 8.00)** : sans le **mode
        accessibilité** SAP GUI (Options → Interaction Design → Accessibility),
        les écrans de liste modernes sont rendus dans un contrôle *shell*
        opaque qui n'expose AUCUN label. L'échec le signale explicitement (même
        diagnostic que `Get List Rendering Status` / `Abap List Should Be
        Readable`, à appeler en préflight pour échouer plus tôt). Lecture seule."""
        rows = reconstruct_rows(self._screen_elements())
        if not rows:
            # Même diagnostic (et même message) que le préflight : une seule
            # source de vérité pour « pourquoi cette liste est illisible ».
            self.abap_list_should_be_readable()
            self.take_screenshot()
            raise AssertionError(
                "Aucune liste ABAP détectée sur l'écran actif : des labels sont "
                "présents mais aucun n'est positionné (géométrie indisponible).")
        return rows

    # -- helpers (méthodes internes) ------------------------------------------

    def _grid(self, table_id):
        self.element_should_be_present(table_id)
        grid = self.session.findById(table_id)
        if not hasattr(grid, "ColumnOrder"):
            self.take_screenshot()
            raise ValueError(
                "Element '%s' is not an ALV GridView (no ColumnOrder)." % table_id
            )
        return grid
