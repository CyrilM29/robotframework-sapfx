"""Effecteur **coordonnées** : agir là où l'API Scripting est aveugle.

Certaines zones de SAP GUI sont officiellement hors de portée du scripting :
l'intérieur des GuiShell opaques (listes modernes sans mode accessibilité),
GuiChart/GuiMap (record-only), le drag & drop (jamais scriptable — position
officielle SAP). La stratégie du projet y est **hybride, déterministe
d'abord** : l'API pour tout ce qu'elle voit (rapide, fiable), et en repli un
**clic matériel** aux coordonnées écran — le geste qu'un humain ferait.

Le partage des rôles avec un agent (rf-mcp) : l'agent obtient l'image
(`Get Screenshot As Base64`) et la géométrie de la zone aveugle
(`Get Element Screen Region`), décide *où* cliquer (c'est lui la « vision »),
puis appelle `Click Element At Offset` — l'effecteur reste déterministe,
journalisé, et exprimé relativement à un élément SAP (les offsets survivent à
un déplacement de fenêtre, contrairement à des coordonnées absolues).

Contraintes assumées d'un clic matériel : la fenêtre SAP doit être visible à
l'écran (l'effecteur la met au premier plan, best-effort) et le curseur bouge
réellement — c'est un outil de dernier recours, pas le chemin nominal (les
ids et libellés de ``resources/`` restent la règle, convention 1).
"""
from pythoncom import com_error
from robot.api import logger

_TRUTHY = ("1", "true", "yes", "on")

_BUTTON_EVENTS = {
    "left": (0x0002, 0x0004),     # MOUSEEVENTF_LEFTDOWN / LEFTUP
    "right": (0x0008, 0x0010),    # MOUSEEVENTF_RIGHTDOWN / RIGHTUP
    "double": (0x0002, 0x0004),   # double = deux séquences left
}


class PointerKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def get_element_screen_region(self, element_id):
        """Région **écran** (pixels physiques) d'un élément : dict ``left`` /
        ``top`` / ``width`` / ``height`` — les propriétés ``ScreenLeft`` /
        ``ScreenTop`` de l'API (position absolue à l'écran, pas relative à la
        fenêtre). C'est la moitié « perception » du repli coordonnées : un
        agent la croise avec la capture d'écran pour choisir un point dans une
        zone opaque."""
        try:
            element = self.session.findById(element_id)
            region = {"left": int(element.ScreenLeft),
                      "top": int(element.ScreenTop),
                      "width": int(element.Width),
                      "height": int(element.Height)}
        except (AttributeError, com_error) as err:
            raise AssertionError(
                "Impossible de lire la région écran de '%s' : %s"
                % (element_id, err))
        return region

    def click_element_at_offset(self, element_id, x_pct=0.5, y_pct=0.5,
                                button="left", focus=True):
        """Clic **matériel** à une position relative DANS un élément — le repli
        pour les zones que l'API ne scripte pas (intérieur d'un GuiShell,
        GuiChart, cibles de drag & drop).

        ``x_pct``/``y_pct`` : position dans l'élément, de 0.0 (bord gauche/haut)
        à 1.0 (bord droit/bas) — défaut le centre. ``button`` : ``left`` /
        ``right`` / ``double``. ``focus=True`` met d'abord la fenêtre SAP au
        premier plan (un clic matériel atterrit sur ce qui est VISIBLE à ces
        coordonnées). Retourne le point cliqué ``{"x": ..., "y": ...}`` —
        journalisé, jamais silencieux.

        Exemple (croiser avec la perception visuelle)::

            ${region}=    Get Element Screen Region    wnd[0]/usr/cntlGRID1/shellcont/shell
            Click Element At Offset    wnd[0]/usr/cntlGRID1/shellcont/shell    0.1    0.15
        """
        x_pct = float(x_pct)
        y_pct = float(y_pct)
        if not (0.0 <= x_pct <= 1.0 and 0.0 <= y_pct <= 1.0):
            raise ValueError(
                "Offsets hors de l'élément : x_pct=%s, y_pct=%s (attendu 0.0-1.0)."
                % (x_pct, y_pct))
        button = str(button).strip().lower()
        if button not in _BUTTON_EVENTS:
            raise ValueError("Bouton inconnu '%s' (left / right / double)." % button)
        region = self.get_element_screen_region(element_id)
        x = region["left"] + int(region["width"] * x_pct)
        y = region["top"] + int(region["height"] * y_pct)
        if str(focus).strip().lower() in _TRUTHY:
            self._focus_sap_window()
        self._send_hardware_click(x, y, button)
        logger.info("Clic matériel %s à (%d, %d) — %s @ (%.0f%%, %.0f%%)."
                    % (button, x, y, element_id, x_pct * 100, y_pct * 100))
        return {"x": x, "y": y}

    # -- plomberie (stubbable en test) -----------------------------------------

    def _focus_sap_window(self):
        """Fenêtre SAP active au premier plan — best-effort : un refus Windows
        (règles de focus) ne doit pas faire échouer le clic, l'utilisateur peut
        avoir mis la fenêtre devant lui-même."""
        try:
            import win32gui
            handle = int(self.session.ActiveWindow.Handle)
            win32gui.SetForegroundWindow(handle)
        except Exception as err:
            logger.info("Mise au premier plan impossible (%s) — le clic part "
                        "sur la fenêtre actuellement visible." % err)

    @staticmethod
    def _send_hardware_click(x, y, button):
        """Le geste : positionner le curseur puis émettre l'événement souris
        (win32api). Isolé pour rester stubbable hors Windows/CI."""
        import win32api
        down, up = _BUTTON_EVENTS[button]
        repeat = 2 if button == "double" else 1
        win32api.SetCursorPos((x, y))
        for _ in range(repeat):
            win32api.mouse_event(down, 0, 0, 0, 0)
            win32api.mouse_event(up, 0, 0, 0, 0)
