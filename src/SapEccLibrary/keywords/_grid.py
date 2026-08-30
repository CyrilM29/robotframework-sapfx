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
from sapfx_common.robot_args import as_name_list, as_optional_int

# Le remède joint à l'erreur de conversion de `max_rows` : l'incident vécu est
# une liste de colonnes passée en POSITION (donc dans le trou de max_rows).
_COLUMNS_HINT = "Une liste de colonnes se passe par columns=."


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
        Lève une exception si aucune colonne ne correspond : l'erreur liste les
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

        Le pendant en écriture de `Get Cell Value By Column Title` : évite d'avoir à
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
        d'existence : voir `Select Row By Column Value` pour la variante qui agit."""
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
        « la ligne dont ``anchor_title`` vaut ``anchor_value`` », l'adressage
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

    def read_full_grid(self, table_id, page_step=None, max_rows=None,
                       columns=None):
        """Comme `Read Grid` mais **fait défiler** la grille pour forcer le chargement
        différé de toutes les lignes avant de lire.

        SAP ne matérialise les lignes d'une ALV GridView qu'au fur et à mesure du
        défilement. On parcourt donc la grille par fenêtres de ``VisibleRowCount``
        (ou ``page_step`` si fourni) en repositionnant ``FirstVisibleRow``, puis on
        lit l'ensemble. ``max_rows`` plafonne le total lu (journalisé) ;
        ``columns`` restreint la lecture à des colonnes TECHNIQUES (voir
        `Read Grid`). Restaure la position de défilement initiale à la fin."""
        grid = self._grid(table_id)
        total = grid.RowCount
        max_rows = as_optional_int(max_rows, "max_rows", hint=_COLUMNS_HINT)
        if max_rows is not None:
            total = min(total, max_rows)
        page_step = as_optional_int(page_step, "page_step")
        step = page_step if page_step else int(getattr(grid, "VisibleRowCount", 0) or 0)
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
        return self.read_grid(table_id, max_rows=max_rows, columns=columns)

    def read_grid(self, table_id, max_rows=None, columns=None):
        """Lit une grille ALV dans une liste de dicts ``[{column_title: value, ...}]``.

        Seules les lignes actuellement chargées sont lues ; SAP charge les grilles
        en différé, donc pour les grandes tables faites défiler/paginer d'abord
        (voir `Scroll`) ou passez un plafond ``max_rows``. Le plafond est journalisé
        pour qu'une lecture tronquée ne soit jamais confondue avec une lecture complète.

        ``columns`` (liste d'ids TECHNIQUES, ``CARRID``… ; une valeur seule,
        une chaîne à virgules ``CARRID,CONNID`` ou une liste-littérale
        ``"['CARRID', 'CONNID']"`` sont acceptées : via rf-mcp tout argument
        arrive en chaîne, et un id technique ne contient pas de virgule)
        restreint la lecture à ces colonnes et fait des ids techniques
        les clés des dicts : indépendant de la locale ET du profil d'affichage
        ALV de l'utilisateur (les titres affichés n'égalent les ids techniques
        que quand le profil montre les noms de champs), et beaucoup moins
        d'appels COM quand la grille est large. Colonne inconnue = échec
        listant les colonnes disponibles. Sans ``columns``, les clés restent
        les titres affichés (comportement historique).
        """
        grid = self._grid(table_id)
        row_count = grid.RowCount
        max_rows = as_optional_int(max_rows, "max_rows", hint=_COLUMNS_HINT)
        if max_rows is not None and row_count > max_rows:
            logger.warn(
                "Grid '%s' has %s rows; reading only the first %s (max_rows)."
                % (table_id, row_count, max_rows)
            )
            row_count = max_rows
        wanted = as_name_list(columns, "columns")
        if wanted:
            available = [str(cid) for cid in grid.ColumnOrder]
            missing = [c for c in wanted if c not in available]
            if missing:
                self.take_screenshot()
                raise ValueError(
                    "Grid '%s' has no technical column(s) %s. Available: %s"
                    % (table_id, ", ".join(missing), ", ".join(available)))
            pairs = [(cid, cid) for cid in wanted]
        else:
            pairs = [(cid, grid.GetDisplayedColumnTitle(cid))
                     for cid in grid.ColumnOrder]
        rows = []
        for row in range(row_count):
            rows.append({key: grid.GetCellValue(row, cid) for cid, key in pairs})
        return rows

    def read_abap_list(self):
        """Lit la **liste ABAP classique** affichée (sortie SE38, SE16 sans ALV,
        protocoles…) : lignes de cellules texte ``[[cellule, ...], ...]``, de
        haut en bas, cellules de gauche à droite.

        Ces écrans n'ont AUCUN objet grille scriptable : l'écran n'est qu'une
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

    # Profondeur maximale explorée sous un conteneur avant d'abandonner.
    # Mesuré sur ABAP 2023 : la grille est à 2 niveaux sous le conteneur en
    # SE16, à 4 en SM50 (qui insère un panneau HTML et un second splitter).
    _MAX_CONTAINER_DEPTH = 6

    def _grid(self, table_id):
        self.element_should_be_present(table_id)
        grid = self.session.findById(table_id)
        if hasattr(grid, "ColumnOrder"):
            return grid
        # Le chemin visé ne porte pas la grille elle-même. Les releases
        # récentes enveloppent l'ALV dans un ou plusieurs GuiSplitterShell
        # (relevé live le 2026-08-23 sur ABAP 2023), et la profondeur varie
        # d'une transaction à l'autre : il n'existe donc pas de suffixe fixe
        # à concaténer au localisateur. On descend jusqu'au PREMIER GridView
        # réel, c'est-à-dire qu'on adresse l'identité du contrôle plutôt que
        # la mise en page de l'écran.
        found, found_id = self._grid_below(grid, table_id)
        if found is not None:
            # Jamais silencieux : la même règle que l'auto-réparation de
            # localisateurs. Un test qui passe grâce à une descente doit le
            # dire, sinon le localisateur périmé survit indéfiniment.
            logger.warn(
                "Grid '%s' n'est pas la grille elle-même mais un conteneur : "
                "grille trouvée à '%s' et utilisée. Les releases récentes "
                "enveloppent l'ALV dans des GuiSplitterShell, à une profondeur "
                "qui varie selon la transaction. Mettre le localisateur à jour "
                "si ce système devient la cible principale." % (table_id, found_id))
            return found
        self.take_screenshot()
        raise ValueError(
            "Element '%s' is not an ALV GridView (no ColumnOrder), and no "
            "GridView was found below it (%d niveaux explorés). Vérifier le "
            "localisateur avec Get Screen Signature : l'écran rend-il bien une "
            "grille ?" % (table_id, self._MAX_CONTAINER_DEPTH))

    def _resolved_grid_id(self, table_id):
        """Identifiant de la grille RÉELLE derrière ``table_id``.

        Rend l'identifiant INCHANGÉ dans les deux cas où il ne faut pas
        intervenir : le chemin porte déjà la grille (cas du 1909 et de toutes
        les suites vertes), ou rien qui ressemble à une grille n'existe en
        dessous (un GuiTableControl, par exemple). La primitive amont produit
        alors son propre message d'erreur, qui reste le plus juste.
        """
        try:
            element = self.session.findById(table_id)
        except Exception:                                  # noqa: BLE001
            return table_id
        if hasattr(element, "ColumnOrder"):
            return table_id
        found, found_id = self._grid_below(element, table_id)
        if found is None or not found_id or found_id == table_id:
            return table_id
        logger.warn(
            "Grid '%s' porte un conteneur : grille réelle '%s' utilisée."
            % (table_id, found_id))
        return found_id

    # Primitives de grille héritées du code vendorisé : elles appellent
    # `findById(table_id)` en direct, donc elles ne passent pas par `_grid`.
    # On ne modifie pas le fichier amont (convention 4) : on résout
    # l'identifiant ici, puis on délègue le comportement inchangé.

    def get_row_count(self, table_id):
        """Nombre de lignes d'une grille, y compris quand le localisateur vise
        le conteneur qui l'enveloppe (releases récentes)."""
        return super().get_row_count(self._resolved_grid_id(table_id))

    def get_cell_value(self, table_id, row_num, col_id):
        """Valeur d'une cellule, localisateur de conteneur toléré."""
        return super().get_cell_value(
            self._resolved_grid_id(table_id), row_num, col_id)

    def set_cell_value(self, table_id, row_num, col_id, text):
        """Écrit une cellule, localisateur de conteneur toléré."""
        return super().set_cell_value(
            self._resolved_grid_id(table_id), row_num, col_id, text)

    def click_toolbar_button(self, table_id, button_id):
        """Clique un bouton de la barre d'outils d'une grille, localisateur de
        conteneur toléré."""
        return super().click_toolbar_button(
            self._resolved_grid_id(table_id), button_id)

    def select_table_row(self, table_id, row_num):
        """Sélectionne une ligne. Sur un GuiTableControl l'identifiant est rendu
        inchangé, donc le comportement amont (qui gère les deux types) est
        strictement préservé."""
        return super().select_table_row(
            self._resolved_grid_id(table_id), row_num)

    @staticmethod
    def _children_of(node):
        """Enfants d'un conteneur COM, ou liste vide. Tolérant par dessein :
        un objet sans ``Children``, un accesseur absent ou un appel qui lève
        ne doivent pas faire échouer une simple exploration."""
        children = getattr(node, "Children", None)
        if children is None:
            return []
        try:
            count = int(children.Count)
        except Exception:                                  # noqa: BLE001
            return []
        items = []
        for index in range(count):
            for accessor in ("ElementAt", "Item"):
                method = getattr(children, accessor, None)
                if method is None:
                    continue
                try:
                    child = method(index)
                except Exception:                          # noqa: BLE001
                    continue
                if child is not None:
                    items.append(child)
                break
        return items

    def _grid_below(self, node, base_id):
        """Premier descendant portant ``ColumnOrder``, en parcours en largeur
        borné. Retourne ``(grille, identifiant)`` ou ``(None, None)``."""
        queue = [(node, 0)]
        while queue:
            current, depth = queue.pop(0)
            if depth >= self._MAX_CONTAINER_DEPTH:
                continue
            for child in self._children_of(current):
                if hasattr(child, "ColumnOrder"):
                    return child, str(getattr(child, "Id", "") or base_id)
                queue.append((child, depth + 1))
        return None, None
