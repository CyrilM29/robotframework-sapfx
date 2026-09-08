"""Mixin **actions de grille ALV** : double-clic de cellule, menu contextuel par
code fonction, inventaire de la barre d'outils, tri.

Relevé live le 2026-09-07 (SE16 sur T000, SAP GUI 8.00) : le `Doubleclick
Element` hérité appelle ``doubleClickItem`` (l'API des ARBRES) sur une grille
et échoue par ``AttributeError`` ; `Select Context Menu Item` hérité refuse
une grille par son type (il cherche ``nodeContextMenu``/``pressContextButton``)
; `Click Toolbar Button` échoue sur un code absent sans dire ce qui existe.
Les chemins API vérifiés : ``SetCurrentCell`` + ``DoubleClickCurrentCell``
(ouvre le modal « Details » de SE16), ``ContextMenu()`` puis
``CurrentContextMenu`` (entrées ``&LOCAL&COPY``, ``&OPTIMIZE``, ``&FIND``,
``&FILTER``, ``&XXL`` : codes fonction STABLES, textes localisés) puis
``SelectContextMenuItem(code)``, ``ToolbarButtonCount`` +
``GetToolbarButtonId/Tooltip/Type``. Le tri n'est PAS dans le menu contextuel
de SE16 (mesuré : ``&SORT_DSC`` y est un argument invalide) : `Sort Grid By
Column` passe par la barre de la grille quand elle en a une, sinon échoue en
listant ce qui existe, jamais en silence.
"""
from pythoncom import com_error

_TRUTHY = ("1", "true", "yes", "on")
_SORT_CODES = {False: ("&SORT_UP", "&SORT_ASC"), True: ("&SORT_DOWN", "&SORT_DSC")}


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


class GridActionKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`, au-dessus de ``GridKeywords``
    (dont il réutilise ``_grid`` : localisateur de conteneur toléré)."""

    def double_click_grid_cell(self, table_id, row_num, column):
        """Double-clique la cellule (``row_num`` 0-based, ``column`` = id
        technique de colonne) d'une grille ALV : ``SetCurrentCell`` puis
        ``DoubleClickCurrentCell``, le geste qui ouvre le détail d'une ligne
        (modal « Details » de SE16, navigation dans un rapport ALV). Attend la
        fin de l'aller-retour."""
        grid = self._grid(table_id)
        try:
            grid.SetCurrentCell(int(row_num), column)
            grid.DoubleClickCurrentCell()
        except com_error as exc:
            self.take_screenshot()
            raise ValueError(
                "Double-clic impossible sur la cellule (%s, %r) de '%s' (%s) : "
                "colonnes disponibles %s" % (row_num, column, table_id, exc,
                                             list(grid.ColumnOrder)))
        self.wait_until_busy_done()

    def doubleclick_element(self, element_id, item_id, column_id):
        """Surcharge du keyword hérité : sur une GRILLE (``ColumnOrder``), le
        double-clic passe par `Double Click Grid Cell` (l'hérité appelait
        ``doubleClickItem``, l'API des arbres, et échouait par
        ``AttributeError``) ; sur tout autre shell, comportement hérité."""
        try:
            element = self.session.findById(element_id)
        except com_error:
            element = None
        if element is not None and hasattr(element, "ColumnOrder"):
            return self.double_click_grid_cell(element_id, item_id, column_id)
        return super().doubleclick_element(element_id, item_id, column_id)

    def list_grid_context_menu(self, table_id):
        """Ouvre le menu contextuel d'une grille et le REFERME (touche
        Échap par ``Escape`` non nécessaire : le menu se ferme au prochain
        appel), retourne ses entrées ``{code, text, level}`` : le code fonction
        (``&FILTER``) est la donnée stable, le texte est localisé."""
        grid = self._grid(table_id)
        try:
            grid.ContextMenu()
            menu = grid.CurrentContextMenu
        except (AttributeError, com_error) as exc:
            raise ValueError("Menu contextuel indisponible sur '%s' (%s)." % (table_id, exc))
        items = []

        def walk(node, level):
            children = node.Children
            for index in range(children.Count):
                child = children.Item(index)
                code = str(getattr(child, "Name", "") or "").strip()
                text = str(getattr(child, "Text", "") or "").strip()
                if code or text:
                    items.append({"code": code, "text": text, "level": level})
                try:
                    if child.Children.Count and level < 3:
                        walk(child, level + 1)
                except (AttributeError, com_error):
                    pass
        walk(menu, 0)
        return items

    def select_grid_context_menu_item(self, table_id, code):
        """Ouvre le menu contextuel de la grille et choisit l'entrée de code
        fonction ``code`` (``&FILTER``, ``&FIND``, ``&XXL``...) par
        ``SelectContextMenuItem`` ; code absent = échec listant les codes du
        menu réel. Attend la fin de l'aller-retour."""
        items = self.list_grid_context_menu(table_id)
        codes = [item["code"] for item in items if item["code"]]
        wanted = str(code).strip()
        if wanted not in codes:
            self.take_screenshot()
            raise ValueError(
                "Aucune entrée de code %r dans le menu contextuel de '%s'. "
                "Codes disponibles : %s" % (wanted, table_id, ", ".join(codes)))
        grid = self._grid(table_id)
        grid.SelectContextMenuItem(wanted)
        self.wait_until_busy_done()

    def select_context_menu_item(self, element_id, menu_or_button_id, item_id):
        """Surcharge du keyword hérité : sur une GRILLE, passe par `Select Grid
        Context Menu Item` (l'hérité refusait le type ``GuiShell``) ; sur un
        arbre ou une barre, comportement hérité."""
        try:
            element = self.session.findById(element_id)
        except com_error:
            element = None
        if element is not None and hasattr(element, "ColumnOrder"):
            return self.select_grid_context_menu_item(element_id, item_id)
        return super().select_context_menu_item(element_id, menu_or_button_id, item_id)

    def list_grid_toolbar_buttons(self, table_id):
        """Les boutons de la barre d'outils PROPRE d'une grille : liste de
        dicts ``{id, tooltip, type}``. Vide quand la grille n'a pas de barre
        (SE16 : les fonctions vivent dans la barre d'application)."""
        grid = self._grid(table_id)
        buttons = []
        try:
            count = int(grid.ToolbarButtonCount)
        except (AttributeError, com_error, TypeError, ValueError):
            return buttons
        for index in range(count):
            try:
                buttons.append({
                    "id": str(grid.GetToolbarButtonId(index) or "").strip(),
                    "tooltip": str(grid.GetToolbarButtonTooltip(index) or "").strip(),
                    "type": str(grid.GetToolbarButtonType(index) or "").strip(),
                })
            except (AttributeError, com_error):
                continue
        return buttons

    def click_toolbar_button(self, table_id, button_id):
        """Surcharge : même comportement hérité, mais un bouton ABSENT échoue
        en listant les boutons de la barre de la grille (vide = la grille n'a
        pas de barre propre : les fonctions vivent dans la barre d'application,
        `Click Button By Label` par tooltip)."""
        try:
            return super().click_toolbar_button(table_id, button_id)
        except ValueError as exc:
            buttons = self.list_grid_toolbar_buttons(table_id)
            if buttons:
                available = ", ".join("%s (%s)" % (b["id"], b["tooltip"])
                                      for b in buttons if b["id"])
                hint = "Boutons de la barre de la grille : %s." % available
            else:
                # La barre d'application est LISTÉE, pas seulement nommée
                # (depuis le 2026-09-08 : List Toolbar Buttons).
                try:
                    app_buttons = self.list_toolbar_buttons()
                except Exception:                              # noqa: BLE001
                    app_buttons = []
                inventory = ", ".join(
                    "%s (%s)" % (b["id"].rsplit("/", 1)[-1], b["icon"] or b["tooltip"] or "?")
                    for b in app_buttons) or "aucun bouton perçu"
                hint = ("La grille n'a pas de barre d'outils propre : ses "
                        "fonctions vivent dans la barre d'application, qui porte "
                        "%s (Click Application Toolbar Button par id ou icône, "
                        "Click Button By Label par tooltip, ou le menu contextuel : "
                        "List Grid Context Menu)." % inventory)
            raise ValueError("%s %s" % (exc, hint)) from exc

    def sort_grid_by_column(self, table_id, column, descending=False):
        """Trie la grille sur la colonne ``column`` (id technique) : sélection
        de la colonne puis bouton de tri de la barre de la grille
        (``&SORT_UP``/``&SORT_DOWN``), à défaut entrée de tri du menu
        contextuel. Grille sans l'un ni l'autre (SE16 : le tri vit dans la
        barre d'application) = échec nommant les voies disponibles, jamais un
        tri silencieusement absent."""
        grid = self._grid(table_id)
        grid.SelectColumn(column)
        desc = _as_bool(descending)
        buttons = {b["id"] for b in self.list_grid_toolbar_buttons(table_id)}
        for code in _SORT_CODES[desc]:
            if code in buttons:
                grid.PressToolbarButton(code)
                self.wait_until_busy_done()
                return code
        codes = {item["code"] for item in self.list_grid_context_menu(table_id)}
        for code in _SORT_CODES[desc]:
            if code in codes:
                grid.SelectContextMenuItem(code)
                self.wait_until_busy_done()
                return code
        self.take_screenshot()
        raise ValueError(
            "Aucune fonction de tri sur la grille '%s' (barre : %s ; menu "
            "contextuel : %s) : sur cet écran le tri vit dans la barre "
            "d'application (Click Button By Label sur le tooltip de tri, colonne "
            "sélectionnée)." % (table_id, sorted(buttons) or "vide", sorted(codes)))
