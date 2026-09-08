"""Mixin **onglets** (``GuiTabStrip`` / ``GuiTab``) : lister, lire l'onglet actif,
en choisir un par CLÉ technique ou par libellé.

Avant ce mixin, une suite cliquait un id d'onglet gravé ; or le jeu d'onglets
DIVERGE d'une release à l'autre (SU01 : douze onglets sur ABAP 2023, onze sur
la 754, ``tabpUSAT`` nouveau, mesuré le 2026-09-08) et rien ne relisait
l'onglet actif. Chemins API vérifiés live : ``GuiTabStrip.SelectedTab`` (objet
COM, ``Id`` absolu), ``GuiTab.Select()``, ``GuiTab.Text`` (localisé). La liste
des onglets vient de la perception (le même parcours structuré que tout le
reste), la CLÉ technique est le suffixe ``tabp<CLÉ>`` de l'id ; la sélection
est VÉRIFIÉE en relisant l'onglet actif. Logique pure dans
``sapfx_common.tab_strip``.
"""
from pythoncom import com_error

from sapfx_common.tab_strip import (
    describe_tabs,
    find_tab_by_key,
    find_tabs_by_label,
    format_tabs,
    relative_id,
)

_TRUTHY = ("1", "true", "yes", "on")


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


class TabStripKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def _tabstrip(self, tabstrip_id):
        element_type = self.get_element_type(tabstrip_id)
        if element_type != "GuiTabStrip":
            self.take_screenshot()
            raise ValueError(
                "Element '%s' est un %s, pas un GuiTabStrip." % (tabstrip_id, element_type))
        return self.session.findById(tabstrip_id)

    def _selected_tab_id(self, strip):
        try:
            selected = strip.SelectedTab
            return relative_id(getattr(selected, "Id", "") if selected is not None else "")
        except (AttributeError, com_error):
            return ""

    def list_tabs(self, tabstrip_id):
        """Les onglets du tabstrip ``tabstrip_id`` : liste de dicts
        ``{id, key, text, selected}`` dans l'ordre d'affichage, ``key`` étant la
        clé TECHNIQUE (``LOGO`` pour ``tabpLOGO``, locale-safe) et ``text`` le
        libellé localisé ; ``selected`` marque l'onglet actif (``SelectedTab``
        relu). Tabstrip sans onglet perçu = échec."""
        strip = self._tabstrip(tabstrip_id)
        tabs = describe_tabs(self._screen_elements(), tabstrip_id, self._selected_tab_id(strip))
        if not tabs:
            self.take_screenshot()
            raise ValueError(
                "Aucun onglet perçu sous '%s' : percevoir avec Get Screen Signature."
                % tabstrip_id)
        return tabs

    def get_selected_tab(self, tabstrip_id):
        """L'onglet ACTIF du tabstrip (dict ``{id, key, text, selected}``) ;
        échec nommant les onglets si aucun n'est marqué actif."""
        tabs = self.list_tabs(tabstrip_id)
        selected = [tab for tab in tabs if tab["selected"]]
        if len(selected) != 1:
            self.take_screenshot()
            raise AssertionError(
                "Le tabstrip '%s' ne désigne pas UN onglet actif (%d) : %s"
                % (tabstrip_id, len(selected), format_tabs(tabs)))
        return selected[0]

    def _activate(self, tabstrip_id, tab):
        self.session.findById(tab["id"]).Select()
        self.wait_until_busy_done()
        active = self.get_selected_tab(tabstrip_id)
        if active["key"] != tab["key"]:
            self.take_screenshot()
            raise AssertionError(
                "L'onglet '%s' n'est pas devenu actif (actif : '%s'). Onglets : %s"
                % (tab["key"], active["key"], format_tabs(self.list_tabs(tabstrip_id))))
        return active

    def select_tab(self, tabstrip_id, key):
        """Active l'onglet de CLÉ technique ``key`` (``LOGO``, ``DEFA``... le
        suffixe ``tabp<CLÉ>`` de son id, insensible à la casse) et VÉRIFIE
        qu'il est devenu l'onglet actif. Clé absente = échec listant les
        onglets réels (clé, libellé, actif). Retourne l'onglet actif."""
        tabs = self.list_tabs(tabstrip_id)
        tab = find_tab_by_key(tabs, key)
        if tab is None:
            self.take_screenshot()
            raise ValueError(
                "Aucun onglet de clé %r sous '%s'. Onglets : %s"
                % (key, tabstrip_id, format_tabs(tabs)))
        return self._activate(tabstrip_id, tab)

    def select_tab_by_label(self, tabstrip_id, label, exact=False):
        """Active l'onglet dont le LIBELLÉ correspond (préfixe insensible à la
        casse, ``exact=True`` pour l'égalité) et vérifie la sélection. Le
        libellé est LOCALISÉ : c'est un choix de lisibilité pour un page
        object, jamais une ancre de suite ; préférer `Select Tab` par clé.
        Ambiguïté remontée avec les candidats, jamais tranchée en silence."""
        tabs = self.list_tabs(tabstrip_id)
        matches = find_tabs_by_label(tabs, label, exact=_as_bool(exact))
        if len(matches) != 1:
            self.take_screenshot()
            if not matches:
                raise ValueError(
                    "Aucun onglet au libellé %r sous '%s' (libellé LOCALISÉ : préférer "
                    "Select Tab par clé). Onglets : %s" % (label, tabstrip_id, format_tabs(tabs)))
            raise ValueError(
                "Libellé %r ambigu sous '%s' : %s" % (label, tabstrip_id, format_tabs(matches)))
        return self._activate(tabstrip_id, matches[0])
