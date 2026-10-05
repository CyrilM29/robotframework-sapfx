"""Mixin **barre de menus** : lister les entrées et en sélectionner une par
chemin (textes ou positions).

Un ``GuiMenu`` se sélectionne par ``Select()`` (ce que `Click Element` fait
déjà quand on connaît l'id positionnel ``wnd[0]/mbar/menu[4]/menu[11]``) ;
ce qui manquait est la résolution d'un CHEMIN lisible (``System > Status``)
ou de positions (``4 > 11``) vers cet id, avec l'ambiguïté remontée. Relevé
live le 2026-09-07 : « System > Status » ouvre le modal « System: Status ».
Le chemin de textes est une facilité de LISIBILITÉ tolérée dans un page
object (les textes sont localisés, convention 3) ; les positions sont
stables par transaction. Logique pure dans ``sapfx_common.menu_path``.
"""
from sapfx_common.menu_path import (
    describe_menu,
    menu_items_from_elements,
    resolve_menu_path,
)


class MenuKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def list_menu_items(self, window="wnd[0]"):
        """Les entrées de la barre de menus de ``window`` : liste de dicts
        ``{id, text, positions, path}`` dans l'ordre de perception (``path``
        = positions jointes par ``>``, rejouable par `Select Menu Item`)."""
        return describe_menu(menu_items_from_elements(self._screen_elements(), window))

    def resolve_menu_item(self, path, window="wnd[0]"):
        """L'id du ``GuiMenu`` désigné par ``path`` (``System > Status``,
        ``4 > 11``, ou mixte), résolu niveau par niveau sur la barre PERÇUE ;
        échec actionnable listant les entrées du niveau fautif."""
        items = menu_items_from_elements(self._screen_elements(), window)
        if not items:
            raise ValueError("Aucune entrée de menu perçue sous '%s/mbar'." % window)
        return resolve_menu_path(items, str(path)).id

    def select_menu_item(self, path, window="wnd[0]"):
        """Sélectionne l'entrée de menu désignée par ``path`` (`Resolve Menu
        Item` puis `Click Element`, qui appelle ``Select()`` sur un GuiMenu) et
        attend la fin de l'aller-retour. Retourne l'id sélectionné (à
        journaliser dans le page object : c'est lui qui est stable)."""
        element_id = self.resolve_menu_item(path, window)
        self.click_element(element_id)
        self.wait_until_busy_done()
        return element_id
