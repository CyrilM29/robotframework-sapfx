"""Mixin SE16 : l'ouverture et la lecture des ecrans du Data Browser.

Les primitives d'ECRAN de SE16, partagees par l'inventaire DDIC, la couche
resources et les campagnes (fin des trois copies divergentes) :

- `Reach Se16 Selection Screen` : SE16 jusqu'a l'ecran de selection d'une
  table, verdict structure ``reached``/``rejected``/``dialog``/``modal``,
  modales de generation absorbees (popup « choix des champs », dialogue de
  message SAPMSDYP detecte STRUCTURELLEMENT, jamais par son texte localise) ;
- `Fill Multiple Selection` : une liste de valeurs dans tout critere d'ecran
  de selection, dialogue standard SAPLALDB DEFILE fenetre par fenetre,
  position atteinte RELUE (scrollbar plafonnee = ecriture a l'index local
  decale, lecon ``window_plan`` de ``sapfx_common.table_control``) ;
- `Get Se16 Selection Criteria` : la carte ``{CHAMP: localisateur}`` DERIVEE
  de la perception semantique (les criteres ``I<n>`` sont positionnels et le
  choix des champs persiste par utilisateur : une carte ecrite a la main
  derive en silence) ;
- ``_read_se16_rows`` : le lecteur de resultat unique (grille ALV restreinte
  aux colonnes techniques, ecran de selection conserve = zero ligne, grille
  absente ailleurs = echec nommant `Use ALV Grid In Data Browser`).

Extrait de ``_ddic.py`` (convention #13) : la classification DD02L et
l'artefact d'inventaire restent la-bas et s'appuient sur ce mixin via la
composition dans :class:`SapEccLibrary`.
"""
from pythoncom import com_error
from robot.api import logger

from sapfx_common.cross_channel import selection_criteria
from sapfx_common.polling import poll_until
from sapfx_common.semantic import screen_affordances

# Ecrans standard pilotes par ce mixin. Le Data Browser et le dialogue de
# selection multiple sont des ecrans SAP standard, stables par version : leurs
# ids appartiennent a la bibliotheque (comme le popup F4 de `Pick F4 Value` ou
# les champs RSYST du login), la convention 1 ne vise que les tests.
_SE16_TABLE_FIELD = "wnd[0]/usr/ctxtDATABROWSE-TABLENAME"
_SE16_GRID = "wnd[0]/usr/cntlGRID1/shellcont/shell"
_SE16_MAX_HITS = "wnd[0]/usr/txtMAX_SEL"
_DD02L_MULTI_BUTTON = "wnd[0]/usr/btn%_I1_%_APP_%-VALU_PUSH"
_MULTI_TABLE = ("wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/"
                "ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE")
_MULTI_CELL = _MULTI_TABLE + "/ctxtRSCSEL_255-SLOW_I[1,{row}]"
_MULTI_ACCEPT = "wnd[1]/tbar[0]/btn[8]"
_DIALOG_TEXT = "wnd[1]/usr/txtMESSTXT{index}"


class Se16Keywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : pilote les
    écrans de consultation du Data Browser (SE16), jamais une donnée métier.
    Suppose ``self.session`` posé par les keywords de connexion."""

    def reach_se16_selection_screen(self, table, timeout=None):
        """SE16 jusqu'à l'écran de sélection de ``table``, verdict structuré.

        Ouvre SE16, saisit le nom, valide (Entrée) et absorbe les modales de
        génération : popup « choix des champs de sélection » des tables larges
        (> 40 champs, première case cochée : le choix persiste par
        utilisateur) et DIALOGUE de message modal (programme ``SAPMSDYP``,
        lignes ``txtMESSTXT<n>``, texte relevé pour le journal puis Entrée).
        La détection des dialogues est STRUCTURELLE, jamais un texte localisé.

        Retourne un dict JSON-safe : ``reached`` (booléen), ``verdict``
        (``reached`` | ``rejected`` | ``dialog`` | ``modal``),
        ``message_type`` (type du message de statut, ``E``…),
        ``status_text`` et ``dialog_text`` (textes localisés, pour le journal
        et les messages d'échec seulement, jamais une assertion).

        - ``rejected`` : message de statut de type ``E`` (structure, include
          ou table inconnue) ;
        - ``dialog`` : dialogue de message refermé mais écran de sélection
          jamais atteint (sondé brièvement : pas d'attente pleine durée) ;
        - ``modal`` : modale inconnue laissée EN PLACE (ni ``MESSTXT`` ni
          case à cocher), à percevoir avec `Get Screen Signature`.

        Sans modale, l'attente de l'écran utilise ``timeout`` (défaut : le
        timeout de la bibliothèque) : l'écran de sélection d'une table est
        GÉNÉRÉ au premier accès et la fin du « busy » ne garantit pas qu'il
        est là (vécu SAPLANE, 2026-08-17).
        """
        self.run_transaction("SE16")
        self.wait_until_busy_done()
        self.input_text(_SE16_TABLE_FIELD, str(table).strip().upper())
        self.send_vkey(0)
        self.wait_until_busy_done()
        message_type, status_text = self.get_status_message()
        state = {"reached": False, "verdict": "reached",
                 "message_type": str(message_type or ""),
                 "status_text": str(status_text or ""), "dialog_text": ""}
        if message_type == "E":
            state["verdict"] = "rejected"
            return state
        dialog_parts = []
        for _ in range(3):   # au plus : choix des champs + dialogue + marge
            if self.session.findById("wnd[1]", False) is None:
                break
            text = self._read_message_dialog_text()
            if text is not None:
                if text:
                    dialog_parts.append(text)
                logger.info("Dialogue de message SE16 refermé (texte relevé "
                            "pour le journal) : %s" % text)
                self.send_vkey(0, window=1)
                self.wait_until_busy_done()
                continue
            checkbox = self._first_popup_checkbox()
            if checkbox is not None:
                self.select_checkbox(checkbox)
                self.send_vkey(0, window=1)
                self.wait_until_busy_done()
                continue
            state["verdict"] = "modal"
            state["dialog_text"] = " ".join(dialog_parts)
            return state
        state["dialog_text"] = " ".join(dialog_parts)
        if dialog_parts:
            # Après un dialogue refermé, l'écran est soit déjà derrière
            # (sous-seconde), soit ne viendra jamais : sonde brève, jamais le
            # timeout plein (30 s de sondage mort par objet rejeté, sinon).
            if not self._probe_selection_screen(timeout or "5s"):
                state["verdict"] = "dialog"
                return state
        else:
            self.wait_until_element_present(_SE16_MAX_HITS, timeout=timeout)
        state["reached"] = True
        return state

    def fill_multiple_selection(self, values, button_id=_DD02L_MULTI_BUTTON):
        """Charge une LISTE de valeurs dans la sélection multiple d'un critère.

        Ouvre le dialogue standard « Multiple Selection » par son bouton
        (``${button_id}``, celui à droite du champ ; défaut : premier critère
        ``I1``), remplit une valeur par ligne de l'onglet « Select Single
        Values », puis reprend (F8) et vérifie le retour à l'écran de
        sélection (aucune modale résiduelle).

        Au-delà de la fenêtre VISIBLE du table control, le dialogue est
        DÉFILÉ fenêtre par fenêtre (scrollbar verticale, objet ré-acquis
        après chaque défilement, position RELUE : jamais des lignes réécrites
        en silence). Comme pour tout GuiTableControl, la scrollbar PLAFONNE
        (``sapfx_common.table_control.window_plan``) : la dernière fenêtre
        chevauche alors la précédente et s'écrit à un index local DÉCALÉ, ce
        que le décalage relu permet de faire au lieu d'échouer. Un défilement
        qui ne couvre toujours pas les valeurs restantes reste un échec
        actionnable invitant à traiter par lots. ``values`` accepte une liste
        Robot ; une chaîne seule est refusée (elle serait itérée caractère par
        caractère). La sélection chargée n'étant pas rémanente entre deux
        passages SE16, les lots successifs ne se contaminent pas.
        """
        if isinstance(values, str):
            raise AssertionError(
                "fill_multiple_selection: 'values' must be a LIST of values, "
                "got the string %r. In Robot, build it with Create List (a "
                "lone string would be iterated character by character)."
                % values)
        values = [str(v).strip() for v in values if str(v).strip()]
        if not values:
            raise AssertionError("fill_multiple_selection: no value provided.")
        self.click_element(button_id)
        self.wait_until_busy_done()
        self.wait_until_element_present(_MULTI_TABLE)
        table = self.session.findById(_MULTI_TABLE)
        capacity = int(getattr(table, "VisibleRowCount", 0) or 0) or 1
        for start in range(0, len(values), capacity):
            window = values[start:start + capacity]
            offset = 0
            if start:
                offset = self._scroll_multi_selection(
                    start, capacity, len(values), len(window))
            for local, value in enumerate(window):
                self.input_text(_MULTI_CELL.format(row=offset + local), value)
        self.click_element(_MULTI_ACCEPT)
        self.wait_until_busy_done()
        if self.session.findById("wnd[1]", False) is not None:
            raise AssertionError(
                "fill_multiple_selection: a modal window is still open after "
                "taking over the selection; perceive it with "
                "Get Screen Signature before retrying.")

    def get_se16_selection_criteria(self):
        """Carte ``{CHAMP: localisateur}`` de l'écran de sélection SE16 COURANT.

        Les critères d'un écran de sélection SE16 sont POSITIONNELS
        (``I1-LOW``, ``I2-LOW``…) et leur ordre dépend du choix des champs de
        sélection, qui persiste par utilisateur : un dictionnaire écrit à la
        main dérive en silence. Ce keyword le DÉRIVE de la perception
        sémantique de l'écran, où chaque critère porte son nom technique de
        champ (donc indépendant de la langue, convention 3).

        Retourne un dict JSON-safe, vide jamais : un écran sans aucun critère
        reconnaissable est un échec actionnable (l'écran de sélection n'est
        probablement pas ouvert). Lecture seule, aucune saisie.
        """
        criteria = selection_criteria(screen_affordances(self._screen_elements()))
        if not criteria:
            raise AssertionError(
                "get_se16_selection_criteria: no technical selection criterion "
                "found on the current screen. Open a SE16 selection screen "
                "first (Reach Se16 Selection Screen), and perceive the screen "
                "with Get Screen Signature if it is already open.")
        return criteria

    def _read_se16_rows(self, max_rows, columns, timeout=None,
                        context="read_se16_rows"):
        """Résultat SE16 après exécution (F8) : lignes de la grille ALV par
        colonnes TECHNIQUES, ou liste vide quand AUCUNE ligne ne répond (SE16
        reste alors sur l'écran de sélection, sans message d'erreur). Toute
        autre issue est un échec actionnable, jamais « zéro ligne » : la fin
        du « busy » ne garantit pas l'écran (l'issue est SONDÉE), et une
        grille absente hors écran de sélection signifie le plus souvent un
        Data Browser resté en mode liste classique.

        ``context`` nomme le keyword appelant dans les échecs : une seule copie
        de cette logique sert la classification DD02L et le contrat de champs
        DD03L."""
        def outcome():
            if self.session.findById(_SE16_GRID, False) is not None:
                return "grid"
            if self.session.findById(_SE16_MAX_HITS, False) is not None:
                return "selection"
            return None

        state = outcome()
        if state is None:
            seconds = (self._timeout_secs(timeout)
                       if hasattr(self, "_timeout_secs") else 10.0)
            step = float(getattr(self, "poll_interval", 0.2) or 0.2)
            state = poll_until(outcome, seconds, step=step)
        if state == "grid":
            return self.read_full_grid(_SE16_GRID, max_rows=max_rows,
                                       columns=list(columns))
        if state == "selection":
            message_type, message_text = self.get_status_message()
            if message_type == "E":
                raise AssertionError(
                    "%s: SE16 refused the selection (status type E): %s."
                    % (context, message_text))
            return []
        self.take_screenshot()
        raise AssertionError(
            "%s: after execution neither the ALV grid nor "
            "the selection screen is present: the Data Browser is likely in "
            "classic list mode (no scriptable grid object). Run 'Use ALV "
            "Grid In Data Browser' once (persistent per user), or perceive "
            "the screen with Get Screen Signature." % context)

    def _scroll_multi_selection(self, position, capacity, total, needed):
        """Fait défiler le table control du dialogue jusqu'à la ligne absolue
        ``position`` et retourne l'index LOCAL où commencer à écrire.

        La position atteinte est RELUE, jamais supposée. Comme toute scrollbar
        de GuiTableControl, celle-ci PLAFONNE (leçon ``window_plan`` de
        ``sapfx_common.table_control``, relevée live sur SE11) : la dernière
        fenêtre chevauche alors la précédente, et les ``needed`` valeurs
        restantes s'écrivent à partir de l'index local ``position - atteinte``,
        qui les remet en face des bonnes lignes. Un défilement qui laisse ces
        valeurs hors de la fenêtre visible (dialogue verrouillé, décalage
        négatif) reste un échec actionnable : rejouer les mêmes lignes
        visibles corromprait la sélection en silence."""
        table = self.session.findById(_MULTI_TABLE)
        scrollbar = getattr(table, "VerticalScrollbar", None)
        error = None
        offset = 0
        if scrollbar is None:
            error = "the dialog table has no vertical scrollbar"
        else:
            try:
                scrollbar.Position = self._scroll_target(scrollbar, position)
                self.wait_until_busy_done()
                table = self.session.findById(_MULTI_TABLE)
                actual = int(getattr(
                    getattr(table, "VerticalScrollbar", None),
                    "Position", -1))
                offset = int(position) - actual
                if offset < 0 or offset + int(needed) > int(capacity):
                    error = ("the dialog refused to scroll to row %s "
                             "(stayed at %s)" % (position, actual))
                elif offset:
                    logger.info(
                        "Sélection multiple : défilement plafonné à la ligne "
                        "%s (demandée : %s), les %s valeur(s) restantes "
                        "s'écrivent à partir de l'index local %s de la "
                        "fenêtre." % (actual, position, needed, offset))
            except com_error as failure:
                error = "scrolling raised %s" % failure
        if error:
            self.send_vkey(12, window=1)
            raise AssertionError(
                "fill_multiple_selection: %s values need scrolling beyond "
                "the visible window (%s rows) but %s. Split the list into "
                "batches of at most %s." % (total, capacity, error, capacity))
        return offset

    @staticmethod
    def _scroll_target(scrollbar, position):
        """Position de défilement à DEMANDER : bornée au ``Maximum`` de la
        scrollbar quand il est exposé. Demander au-delà lève un ``com_error``
        « invalid argument » sur un vrai table control (constaté live sur
        SE11) : le plafond se demande, il ne se découvre pas par l'exception."""
        maximum = getattr(scrollbar, "Maximum", None)
        try:
            if maximum is not None:
                return min(int(position), int(maximum))
        except (TypeError, ValueError):
            pass
        return int(position)

    def _probe_selection_screen(self, timeout):
        """Présence de l'écran de sélection SE16 (sonde bornée, sans échec)."""
        try:
            self.wait_until_element_present(_SE16_MAX_HITS, timeout=timeout)
        except AssertionError:
            return False
        return True

    def _read_message_dialog_text(self):
        """Texte d'un DIALOGUE DE MESSAGE modal (``txtMESSTXT<n>``), ou
        ``None`` quand ``wnd[1]`` n'est pas un dialogue de message. La
        détection est structurelle ; le texte n'alimente que le journal."""
        if self.session.findById(_DIALOG_TEXT.format(index=1), False) is None:
            return None
        parts = []
        for index in range(1, 10):
            element = self.session.findById(
                _DIALOG_TEXT.format(index=index), False)
            if element is None:
                break
            text = str(getattr(element, "Text", "") or "").strip()
            if text:
                parts.append(text)
        return " ".join(parts)

    def _first_popup_checkbox(self):
        """Id (relatif à la session) de la première case à cocher de
        ``wnd[1]``, ou ``None``. Parcours ``Count``/``ElementAt`` : jamais
        d'itération Python directe sur une collection COM (motif du dépôt),
        et jamais d'id absolu ``/app/...`` repassé à ``findById``."""
        usr = self.session.findById("wnd[1]/usr", False)
        children = getattr(usr, "Children", None) if usr is not None else None
        for index in range(int(getattr(children, "Count", 0) or 0)):
            child = children.ElementAt(index)
            if getattr(child, "Type", "") == "GuiCheckBox":
                raw = str(getattr(child, "Id", "") or "")
                marker = raw.find("wnd[")
                return raw[marker:] if marker >= 0 else raw
        return None
