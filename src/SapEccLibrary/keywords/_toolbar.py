"""Mixin **barres d'outils de la fenêtre** : inventorier la barre d'application
(``wnd[0]/tbar[1]``) et la barre système (``tbar[0]``), et y cliquer un bouton
en échouant avec l'inventaire.

Trois messages d'échec de la bibliothèque renvoyaient déjà vers « la barre
d'application » (`Click Toolbar Button`, `Sort Grid By Column`, le contexte
d'une grille SE16 sans barre propre) sans pouvoir la LISTER : `List Grid
Toolbar Buttons` est réservé aux grilles et le dit. Mesuré le 2026-09-08 sur
ABAP 2023 : la barre d'application de l'écran de sélection SE16 porte cinq
boutons que la perception voit (``btn[8]``, ``btn[2]``, ``btn[14]``,
``btn[18]``, ``btn[31]`` « Number of Entries »). L'inventaire vient du même
parcours structuré que la perception ; l'icône (``IconName``, locale-safe) est
lue par contrôle, best-effort.
"""
from pythoncom import com_error

APPLICATION_TOOLBAR = "wnd[0]/tbar[1]"
SYSTEM_TOOLBAR = "wnd[0]/tbar[0]"


class ToolbarKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def _toolbar_icon(self, button_id):
        try:
            return str(getattr(self.session.findById(button_id, False), "IconName", "") or "")
        except (AttributeError, com_error):
            return ""

    def list_toolbar_buttons(self, toolbar_id=APPLICATION_TOOLBAR):
        """Les boutons d'une barre d'outils de la fenêtre (défaut : la barre
        d'APPLICATION ``wnd[0]/tbar[1]`` ; ``wnd[0]/tbar[0]`` = barre système) :
        liste de dicts ``{id, text, tooltip, icon}`` dans l'ordre d'affichage,
        ``icon`` étant le nom d'icône SAP (``ICON_EXECUTE``...), l'ancre
        locale-safe là où ``tooltip`` est localisé. Barre sans bouton perçu =
        liste vide (un écran peut n'en avoir aucun)."""
        prefix = toolbar_id.rstrip("/") + "/"
        buttons = []
        for element in self._screen_elements():
            if element.type == "GuiButton" and element.id.startswith(prefix):
                buttons.append({"id": element.id, "text": (element.text or "").strip(),
                                "tooltip": (element.tooltip or "").strip(),
                                "icon": self._toolbar_icon(element.id)})
        return buttons

    def click_application_toolbar_button(self, button, toolbar_id=APPLICATION_TOOLBAR):
        """Clique le bouton ``button`` de la barre d'application : son id complet
        (``wnd[0]/tbar[1]/btn[31]``), son segment (``btn[31]``) ou son nom
        d'icône (``ICON_COUNT``, locale-safe). Bouton absent = échec listant
        l'inventaire réel (id, icône, tooltip), jamais un « Cannot find » nu.
        Attend la fin de l'aller-retour ; retourne l'id cliqué."""
        buttons = self.list_toolbar_buttons(toolbar_id)
        wanted = str(button).strip()
        for candidate in buttons:
            if wanted in (candidate["id"], candidate["id"].rsplit("/", 1)[-1]) or (
                    wanted and wanted.upper() == candidate["icon"].upper()):
                self.click_element(candidate["id"])
                self.wait_until_busy_done()
                return candidate["id"]
        self.take_screenshot()
        available = ", ".join("%s (%s%s)" % (b["id"].rsplit("/", 1)[-1], b["icon"] or "sans icône",
                                            ", " + b["tooltip"] if b["tooltip"] else "")
                              for b in buttons) or "aucun bouton perçu"
        raise ValueError(
            "Aucun bouton %r dans la barre '%s'. Boutons : %s" % (button, toolbar_id, available))
