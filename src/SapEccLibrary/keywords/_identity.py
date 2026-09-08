"""Mixin **identité du système** : release, kernel et composants lus à l'écran.

Le miroir SAP GUI de `Read System Identity` du canal RFC. Le modal « System:
Status » (programme ``SAPLSHSY``, dynpro ``700``) est le seul endroit où un
écran SAP GUI dit à quel système on parle : mandant, utilisateur, serveur
d'application (``hôte_SID_instance``), base de données ; son bouton « Other
Kernel Information » (dynpro ``701``) donne la release et le patch du kernel ;
son bouton « Details » ouvre « Installed Software », dont la grille des
composants porte ``SAP_BASIS`` et sa release. Relevé live le 2026-09-07 sur
A4H (SAP GUI 8.00) : tous ces champs ont des ids TECHNIQUES, et le menu
« System » est l'AVANT-DERNIER menu de la barre sur les six écrans sondés
(SESSION_MANAGER, SE16, SU01, SM37, SE38, SE11). L'entrée « Status... », elle,
est l'AVANT-DERNIÈRE du menu System, « Log Off » fermant la liste : c'est
l'ancre qui tient sur DEUX releases (754 : 13 entrées, Status en 11 ; 758 :
12 entrées, Status en 10, l'entrée « List » ayant disparu), là où l'indice 11
gravé le 2026-09-07 cliquait « Log Off » sur la 758 (mesuré le 2026-09-08 par
le registre de capacités de la seconde release). L'entrée est donc RÉSOLUE
avant d'être cliquée, doit ouvrir un dialogue (points de suspension, une
convention non localisée), et le dialogue atteint est VÉRIFIÉ structurellement
(champ ``txtSYST-MANDT`` présent) ; sinon l'échec nomme la voie manuelle.
Logique pure dans ``sapfx_common.system_identity`` et
``sapfx_common.menu_path``.
"""
from pythoncom import com_error
from robot.api import logger

from sapfx_common.menu_path import dialog_entry_before_last, menu_items_from_elements
from sapfx_common.system_identity import (
    ANCHOR_KEYS,
    COMPONENT_COLUMNS,
    KERNEL_FIELDS,
    STATUS_FIELDS,
    build_identity,
    describe_identity,
    expected_mismatches,
)

_STATUS_ANCHOR = "usr/txtSYST-MANDT"     # présent sur le seul dynpro SAPLSHSY/700
_KERNEL_BUTTON = "tbar[0]/btn[17]"       # « Other Kernel Information » (Shift+F5)
_KERNEL_ANCHOR = "usr/txtKINFOSTRUC-KERNEL_RELEASE"
_DETAILS_BUTTON = "usr/btnPRELINFO"      # « Details » -> « Installed Software »
_COMPONENTS_GRID = ("usr/tabsVERSDETAILS/tabpCOMP_VERS/"
                    "ssubDETAIL_SUBSCREEN:SAPLOCS_UI_CONTROLS:0301/"
                    "cntlSCV_CU_CONTROL/shellcont/shell")
_TRUTHY = ("1", "true", "yes", "on")


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


class SystemIdentityKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    def _element(self, element_id):
        try:
            return self.session.findById(element_id, False)
        except (AttributeError, com_error):
            return None

    def _read_fields(self, window, fields):
        """``{suffixe: texte}`` des champs de ``wnd[window]/usr/`` présents."""
        values = {}
        for suffix in fields:
            element = self._element("wnd[%s]/usr/%s" % (window, suffix))
            if element is not None:
                try:
                    values[suffix] = str(getattr(element, "Text", "") or "")
                except (AttributeError, com_error):
                    continue
        return values

    def open_system_status(self):
        """Ouvre le modal « System: Status » PAR POSITION RÉSOLUE : le menu
        System est l'avant-dernier de la barre et « Status... » l'AVANT-DERNIÈRE
        entrée de ce menu (« Log Off » ferme la liste), une ancre mesurée sur
        deux releases (754 : entrée 11 sur 13 ; 758 : entrée 10 sur 12). Rien
        n'est gravé : l'entrée candidate doit en plus ouvrir un dialogue
        (points de suspension, non localisés), sinon REFUS avant tout clic
        (l'indice 11 gravé cliquait « Log Off » sur la 758). Le dialogue
        atteint est VÉRIFIÉ structurellement (champ ``txtSYST-MANDT`` sur
        ``wnd[1]``). Un modal déjà ouvert = refus (le refermer par `Dismiss
        Modal Window`) ; dialogue inattendu = refermé puis échec nommant la
        voie manuelle (`Select Menu Item` avec le chemin de textes de la langue
        de session). Retourne l'id de l'entrée de menu CLIQUÉE (par exemple
        ``wnd[0]/mbar/menu[5]/menu[10]`` sur SE16 de la release 758), la trace
        de la résolution qu'un test peut confronter à un relevé indépendant du
        menu ; le dialogue lui-même est ``wnd[1]``."""
        if self._element("wnd[1]") is not None:
            raise AssertionError(
                "Un modal (wnd[1]) est déjà ouvert : le refermer d'abord "
                "(Dismiss Modal Window) avant d'ouvrir System > Status.")
        items = menu_items_from_elements(self._screen_elements(), "wnd[0]")
        tops = sorted((item for item in items if item.depth == 1),
                      key=lambda item: item.positions[0])
        if len(tops) < 2:
            raise AssertionError(
                "La barre de menus de wnd[0] porte %d menu(s) : impossible d'y "
                "trouver le menu System (attendu avant-dernier)." % len(tops))
        system_menu = tops[-2]
        entries = [item for item in items
                   if item.depth == 2 and item.positions[0] == system_menu.positions[0]]
        candidate, reason = dialog_entry_before_last(entries)
        if candidate is None:
            raise AssertionError(
                "Le menu '%s' (%s) ne porte pas d'entrée « Status » résolvable : %s. "
                "Entrées perçues : %s. Ouvrir le statut par Select Menu Item avec le "
                "chemin de textes de la langue de session (« System > Status » en EN)."
                % (system_menu.text or system_menu.id, system_menu.id, reason,
                   ", ".join("%d=%s" % (e.positions[-1], e.text)
                             for e in sorted(entries, key=lambda e: e.positions[-1]))))
        target = candidate.id
        self.click_element(target)
        self.wait_until_busy_done()
        if self._element("wnd[1]/%s" % _STATUS_ANCHOR) is None:
            opened = self._element("wnd[1]") is not None
            if opened:
                self.dismiss_modal_window(1)
            self.take_screenshot()
            raise AssertionError(
                "L'entrée %s n'a pas ouvert le dialogue « System: Status » (%s) : "
                "cette barre de menus ne suit pas la disposition standard. Ouvrir "
                "le statut par Select Menu Item avec le chemin de textes de la "
                "langue de session." % (target, "un autre modal s'est ouvert et a "
                                        "été refermé" if opened else "aucun modal"))
        return target

    def _read_kernel(self, window, unread):
        button = self._element("wnd[%s]/%s" % (window, _KERNEL_BUTTON))
        if button is None:
            unread.append("kernel : bouton « Other Kernel Information » absent")
            return None
        try:
            button.press()
        except (AttributeError, com_error) as exc:
            unread.append("kernel : bouton refusé (%s)" % exc)
            return None
        self.wait_until_busy_done()
        popup = window + 1
        if self._element("wnd[%s]/%s" % (popup, _KERNEL_ANCHOR)) is None:
            unread.append("kernel : le popup « Kernel information » n'est pas apparu")
            if self._element("wnd[%s]" % popup) is not None:
                self.dismiss_modal_window(popup)
            return None
        fields = self._read_fields(popup, KERNEL_FIELDS)
        self.dismiss_modal_window(popup)
        return fields

    def _read_components(self, window, unread):
        button = self._element("wnd[%s]/%s" % (window, _DETAILS_BUTTON))
        if button is None:
            unread.append("composants : bouton « Details » absent")
            return None
        try:
            button.press()
        except (AttributeError, com_error) as exc:
            unread.append("composants : bouton refusé (%s)" % exc)
            return None
        self.wait_until_busy_done()
        popup = window + 1
        grid_id = "wnd[%s]/%s" % (popup, _COMPONENTS_GRID)
        if self._element(grid_id) is None:
            unread.append("composants : la grille « Installed Software » n'est pas apparue")
            if self._element("wnd[%s]" % popup) is not None:
                self.dismiss_modal_window(popup)
            return None
        try:
            rows = self.read_grid(grid_id, columns=list(COMPONENT_COLUMNS))
        finally:
            self.dismiss_modal_window(popup)
        return rows

    def get_system_identity(self, kernel=True, components=True):
        """Lit l'IDENTITÉ du système joint dans « System > Status » et la rend
        en dict JSON-safe : ``system_id``, ``client``, ``user``, ``language``,
        ``server_name`` (``hôte_SID_instance``, décomposé en
        ``application_host`` / ``instance_number``), ``product_version_text``,
        ``installation_name``, base de données, puis, sauf ``kernel=False``,
        ``kernel_release`` / ``kernel_patch_level`` / ``supported_sap_releases``
        / ``ip_address`` (volatile), et, sauf ``components=False``, la liste
        ``components`` avec ``basis_release`` / ``basis_sp_level`` (la ligne
        ``SAP_BASIS`` : LA release ABAP, ce qui distingue deux systèmes qui
        partagent un SID et un hôte, relevé live 2026-08-28). ``anchor`` isole
        les clés comparables ; ``unread`` nomme les sections qui n'ont PAS pu
        être lues, ``missing_fields`` les champs qu'un dialogue lu n'affichait
        pas (une autre release peut en omettre), jamais remplacés par une
        valeur plausible. Tous les modals ouverts sont refermés et leur
        disparition vérifiée."""
        self.open_system_status()
        window = 1
        unread = []
        status = self._read_fields(window, STATUS_FIELDS)
        kernel_fields = self._read_kernel(window, unread) if _as_bool(kernel) else None
        rows = self._read_components(window, unread) if _as_bool(components) else None
        self.dismiss_modal_window(window)
        if self._element("wnd[%s]" % window) is not None:
            self.take_screenshot()
            raise AssertionError(
                "Le dialogue « System: Status » est resté ouvert après lecture.")
        try:
            session_system = str(self.session.Info.SystemName or "")
        except (AttributeError, com_error):
            session_system = ""
        identity = build_identity(status, kernel_fields, rows, session_system, unread)
        logger.info("Identité du système : %s" % describe_identity(identity))
        return identity

    def system_identity_should_be(self, identity=None, **expected):
        """Échoue si l'identité (``identity`` = le dict de `Get System
        Identity`, relu sur l'écran quand absent) diverge des valeurs attendues
        sur des clés d'ANCRE (``basis_release=754    kernel_release=777``
        ``client=001``...) : chaque écart est listé avec la valeur réelle, une
        clé absente de l'identité est un écart. Les clés volatiles (adresse IP,
        transaction) sont refusées : elles ne prouvent rien."""
        if not expected:
            raise ValueError(
                "Aucune attente : passer des clés d'ancre (%s)." % ", ".join(ANCHOR_KEYS))
        volatile = [key for key in expected if key not in ANCHOR_KEYS]
        if volatile:
            raise ValueError(
                "Clé(s) hors ancre refusée(s) : %s (clés comparables : %s)."
                % (", ".join(volatile), ", ".join(ANCHOR_KEYS)))
        if identity is None:
            identity = self.get_system_identity()
        mismatches = expected_mismatches(identity, expected)
        if mismatches:
            self.take_screenshot()
            raise AssertionError(
                "Identité du système différente de l'attendu : %s. Système lu : %s"
                % ("; ".join("%s attendu %r, lu %r" % (m["key"], m["expected"], m["actual"])
                             for m in mismatches),
                   describe_identity(identity)))
        return identity
