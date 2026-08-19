"""Mixin DDIC : découverte et classification des objets du dictionnaire ABAP.

Le Data Browser (SE16) sait afficher DD02L, la table des en-têtes du
dictionnaire, et c'est elle (pas l'ouverture SE16 de chaque objet) qui classe
un lot d'objets en un appel : ``TABCLASS`` en sortie de grille dit table
transparente, vue ou structure. Trois réalités d'écran relevées live (A4H,
2026-08-17) structurent ce mixin :

- ``TABCLASS`` n'est PAS un critère de sélection de DD02L (l'écran généré
  n'expose que les champs clés ``TABNAME``/``AS4LOCAL``/``AS4VERS``) : on
  sélectionne par NOM et on classe en sortie ;
- une liste de noms sans préfixe commun passe par la **sélection multiple**
  (dialogue standard ``SAPLALDB``, bouton ``%_I1_%_APP_%-VALU_PUSH``), remplie
  fenêtre visible par fenêtre visible : le table control du dialogue est
  DÉFILÉ entre deux fenêtres, et un défilement refusé est un échec
  actionnable, jamais des lignes réécrites en silence ;
- SE16 peut répondre par un DIALOGUE de message modal (SAPMSDYP,
  ``txtMESSTXT<n>``) à la génération d'un écran de sélection : détection
  STRUCTURELLE, verdict exposé par `Reach Se16 Selection Screen` (le keyword
  d'ouverture partagé avec la couche resources et les suites).

Deux garde-fous contre les campagnes « vertes mais fausses » : la lecture du
résultat DD02L distingue « aucune ligne » (écran de sélection conservé) de
« grille absente » (mode liste classique : échec nommant `Use ALV Grid In
Data Browser`), et un lot revenu vide déclenche une sonde CANARI
(``TABNAME=DD02L`` : la table se décrit elle-même) qui tranche entre absence
réelle et critères positionnels détournés par un choix de champs persistant.

La logique pure (barème de classification depuis le domaine relevé, entrée
d'objet, artefact déterministe, hash, comparaison) vit dans
``sapfx_common.ddic_inventory`` ; ici uniquement les E/S écran et fichier.
"""
import datetime
import json

from pythoncom import com_error
from robot.api import logger

from sapfx_common.ddic_inventory import (
    bounded_union,
    build_inventory,
    build_object_entry,
    classification_map,
    compare_inventories,
    comparison_hash,
    inventory_json,
    record_probe,
    render_comparison_report,
    sample_for_probe,
    validate_scope,
)
from sapfx_common.polling import poll_until

from ._diagnostics import _truthy

# Écrans standard pilotés par ce mixin. Le Data Browser et le dialogue de
# sélection multiple sont des écrans SAP standard, stables par version : leurs
# ids appartiennent à la bibliothèque (comme le popup F4 de `Pick F4 Value` ou
# les champs RSYST du login), la convention 1 ne vise que les tests.
_SE16_TABLE_FIELD = "wnd[0]/usr/ctxtDATABROWSE-TABLENAME"
_SE16_GRID = "wnd[0]/usr/cntlGRID1/shellcont/shell"
_SE16_MAX_HITS = "wnd[0]/usr/txtMAX_SEL"
_DD02L_TABNAME_LOW = "wnd[0]/usr/ctxtI1-LOW"
_DD02L_AS4LOCAL_LOW = "wnd[0]/usr/ctxtI2-LOW"
_DD02L_MULTI_BUTTON = "wnd[0]/usr/btn%_I1_%_APP_%-VALU_PUSH"
_MULTI_TABLE = ("wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/"
                "ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE")
_MULTI_CELL = _MULTI_TABLE + "/ctxtRSCSEL_255-SLOW_I[1,{row}]"
_MULTI_ACCEPT = "wnd[1]/tbar[0]/btn[8]"
_DIALOG_TEXT = "wnd[1]/usr/txtMESSTXT{index}"

#: Taille de lot par défaut, validée live (7 valeurs tiennent dans la fenêtre
#: visible du table control SAPLALDBSINGLE, A4H/GUI 8.00, 2026-08-17). Depuis
#: que `Fill Multiple Selection` défile le dialogue, un lot plus grand est
#: accepté : la valeur passée par l'appelant fait foi.
_DEFAULT_BATCH = 7

#: Colonnes DD02L consommées par la classification : la lecture de grille est
#: RESTREINTE à ces ids techniques (indépendants de la locale et du profil
#: d'affichage ALV, contrairement aux titres affichés).
_DD02L_COLUMNS = ("TABNAME", "TABCLASS", "AS4LOCAL", "AS4VERS")

#: Sonde canari des critères positionnels : DD02L se décrit elle-même, la
#: ligne DOIT revenir quand ``ctxtI1-LOW`` est bien TABNAME.
_CANARY_TABLE = "DD02L"

#: Marge de lignes DD02L par objet demandé (versions ``AS4LOCAL``/``AS4VERS``
#: multiples comprises) : borne MAX_SEL et plafond de lecture d'un lot. Un
#: plafond ATTEINT est un échec actionnable, jamais une troncature muette.
_ROWS_PER_OBJECT = 10


class DdicKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : aucune donnée
    métier n'est modifiée, seuls des écrans de consultation sont pilotés.
    Suppose ``self.session`` posé par les keywords de connexion."""

    _truthy = staticmethod(_truthy)

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

    def get_ddic_classification_map(self, domain_values, extra=None):
        """Barème de classification restreint au domaine RELEVÉ sur la cible.

        ``domain_values`` est la liste des valeurs du domaine ``TABCLASS`` lue
        live (p.ex. via ``Read Domain Values`` de la couche resources) ; seules
        les valeurs présentes sur la cible ET appuyées par une observation
        entrent au barème, le reste se classera ``unknown``. ``extra`` :
        surcharge site explicite ``valeur=classe`` (classe cible inconnue =
        échec actionnable). Retourne un dict JSON-safe.
        """
        try:
            return classification_map(domain_values, extra)
        except ValueError as error:
            raise AssertionError(
                f"get_ddic_classification_map: {error}") from error

    def validate_ddic_scope(self, packages=None, prefixes=None,
                            max_objects=100, batch_size=_DEFAULT_BATCH,
                            object_types=None):
        """Valide et normalise le périmètre d'une campagne d'inventaire.

        Refuse une sélection vide (ni package ni préfixe) et toute limite
        absente ou non positive : la campagne n'a pas de mode illimité
        implicite. ``object_types`` : types d'objets TADIR interrogés
        (``TABL`` et ``VIEW`` par défaut), consignés dans le périmètre parce
        qu'ils conditionnent toute comparaison entre cibles. ``packages``,
        ``prefixes`` et ``object_types`` acceptent une liste OU une valeur
        seule (une variable ``-v`` Robot est un scalaire). Retourne le
        périmètre normalisé (dict JSON-safe), à consigner dans l'artefact.
        """
        try:
            return validate_scope(packages, prefixes, max_objects, batch_size,
                                  object_types)
        except ValueError as error:
            raise AssertionError(f"validate_ddic_scope: {error}") from error

    def classify_ddic_objects(self, names, class_map, batch_size=_DEFAULT_BATCH,
                              active_only=True, timeout=None):
        """Classe une liste d'objets DDIC via DD02L, par lots de sélection multiple.

        Pour chaque lot : SE16 sur ``DD02L``, sélection multiple de ``TABNAME``
        chargée avec les noms du lot (``AS4LOCAL=A`` si ``active_only``, la
        version active seulement), exécution (F8), lecture de la grille
        RESTREINTE aux colonnes techniques consommées et classification par
        ``class_map`` (le barème relevé sur la cible, voir
        `Get Ddic Classification Map`). Retourne ``{nom: entrée}`` JSON-safe :
        valeurs brutes conservées, objet inconnu de DD02L signalé
        (``present=False``, classe ``unknown``), jamais assimilé à une table
        vide. Lecture seule.

        Garde-fous « jamais faux en silence » : une grille absente qui n'est
        pas un écran de sélection est un échec nommant `Use ALV Grid In Data
        Browser` (mode liste classique) ; un plafond de lecture atteint est un
        échec (troncature jamais muette) ; un lot revenu VIDE déclenche une
        sonde canari (``TABNAME=DD02L``) qui distingue l'absence réelle d'un
        écran de sélection dont les critères positionnels ne sont plus
        ``TABNAME``/``AS4LOCAL`` (le choix des champs persiste par
        utilisateur).
        """
        if isinstance(names, str):
            raise AssertionError(
                "classify_ddic_objects: 'names' must be a LIST of object "
                "names, got the string %r. In Robot, build it with Create "
                "List (a lone string would be iterated character by "
                "character)." % names)
        names = [str(n).strip().upper() for n in names if str(n).strip()]
        try:
            batch_size = int(str(batch_size).strip())
        except (TypeError, ValueError):
            batch_size = 0
        if batch_size < 1:
            raise AssertionError(
                "classify_ddic_objects: batch_size must be a strictly "
                "positive integer.")
        rows_by_name = {}
        for start in range(0, len(names), batch_size):
            batch = names[start:start + batch_size]
            rows = self._classify_batch(batch, active_only, timeout)
            if not rows:
                self._verify_dd02l_criteria(active_only, timeout)
            for row in rows:
                rows_by_name[str(row.get("TABNAME", "")).strip().upper()] = row
        return {name: build_object_entry(name, class_map,
                                         dd02l_row=rows_by_name.get(name))
                for name in names}

    def sample_ddic_objects_for_probe(self, entries, per_class=2,
                                      classes=None):
        """Échantillon déterministe et borné pour la sonde SE16.

        Les ``per_class`` premiers noms (tri technique) de chaque classe
        demandée (par défaut ``table``, ``view``, ``non_consultable_ddic``) :
        jamais tous les objets, jamais un choix dépendant de l'ordre
        d'arrivée. ``entries`` accepte le dict retourné par `Classify Ddic
        Objects` ou une liste d'entrées ; ``classes`` accepte une liste ou
        une valeur seule. Retourne la liste des noms à sonder.
        """
        if isinstance(entries, dict):
            entries = list(entries.values())
        if classes is None:
            return sample_for_probe(entries, per_class=int(per_class))
        if isinstance(classes, str):
            classes = [classes]
        return sample_for_probe(entries, per_class=int(per_class),
                                classes=list(classes))

    def merge_ddic_name_lists(self, groups, max_objects):
        """Union déterministe et bornée de plusieurs listes de noms d'objets.

        Dédoublonne, trie par nom technique, applique la borne
        ``max_objects``. Retourne ``[noms, truncated]`` : ``truncated`` vaut
        vrai quand la borne a retiré des objets, jamais un succès silencieux.
        """
        names, truncated = bounded_union(groups, int(max_objects))
        return [names, truncated]

    def record_ddic_probe(self, entry, status, message_type="", detail="",
                          entry_count=None):
        """Consigne le résultat technique d'une sonde SE16 dans une entrée.

        ``status`` : ``selection_screen_reached``, ``rejected``,
        ``authorization_blocked``, ``runtime_error`` ou ``not_probed`` ;
        ``message_type`` est le TYPE de message (``E``…), jamais un texte
        localisé. Retourne l'entrée mise à jour (JSON-safe).
        """
        try:
            return record_probe(entry, status, message_type, detail,
                                entry_count)
        except ValueError as error:
            raise AssertionError(f"record_ddic_probe: {error}") from error

    def write_ddic_inventory_artifact(self, path, target_id, scope, entries,
                                      truncated=False):
        """Écrit l'artefact JSON déterministe d'une cible et retourne sa preuve.

        Assemble l'inventaire (objets triés, résumé recalculé, horodatage UTC
        posé ici, à la frontière), l'écrit en UTF-8/LF à ``${path}`` et
        retourne ``{path, sha256, summary}`` : le hash exclut l'horodatage,
        deux campagnes lisant les mêmes données produisent donc le même hash.
        ``entries`` accepte le dict retourné par `Classify Ddic Objects` ou une
        liste d'entrées.
        """
        if isinstance(entries, dict):
            entries = list(entries.values())
        observed = datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds")
        inventory = build_inventory(target_id, scope, entries, observed,
                                    truncated=self._truthy(truncated))
        digest = comparison_hash(inventory)
        with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(inventory_json(inventory))
        logger.info(f"DDIC inventory written to {path} (sha256 {digest}).")
        return {"path": str(path), "sha256": digest,
                "summary": inventory["summary"]}

    def compare_ddic_inventory_artifacts(self, path_a, path_b):
        """Compare deux artefacts écrits par `Write Ddic Inventory Artifact`.

        Charge les deux fichiers JSON, vérifie la comparabilité (même schéma ;
        périmètres différents = comparaison marquée non probante, jamais des
        écarts trompeurs), journalise le rapport Markdown et retourne le dict
        de comparaison JSON-safe (``only_in_a``/``only_in_b``, reclassements,
        consultabilité SE16 changée, écarts de volumétrie). Hors ligne : ne
        touche jamais l'écran.
        """
        with open(str(path_a), encoding="utf-8") as handle:
            inventory_a = json.load(handle)
        with open(str(path_b), encoding="utf-8") as handle:
            inventory_b = json.load(handle)
        try:
            comparison = compare_inventories(inventory_a, inventory_b)
        except ValueError as error:
            raise AssertionError(
                f"compare_ddic_inventory_artifacts: {error}") from error
        logger.info(render_comparison_report(comparison))
        return comparison

    # ------------------------------------------------------------------ interne

    def _classify_batch(self, batch, active_only, timeout):
        """Un passage SE16/DD02L pour UN lot : sélection, exécution, lecture
        ciblée. Retourne les lignes DD02L du lot (éventuellement vides)."""
        self._open_dd02l_selection(timeout)
        if self._truthy(active_only):
            self.input_text(_DD02L_AS4LOCAL_LOW, "A")
        cap = max(len(batch) * _ROWS_PER_OBJECT, 20)
        self.input_text(_SE16_MAX_HITS, str(cap))
        if len(batch) == 1:
            self.input_text(_DD02L_TABNAME_LOW, batch[0])
        else:
            self.input_text(_DD02L_TABNAME_LOW, "")
            self.fill_multiple_selection(batch)
        self.send_vkey(8)
        self.wait_until_busy_done()
        rows = self._read_dd02l_results(cap, timeout)
        if len(rows) >= cap:
            raise AssertionError(
                "classify_ddic_objects: the DD02L read hit its row cap "
                "(%s rows for %s names): later objects of the batch would be "
                "silently mis-flagged as absent. Lower batch_size (or keep "
                "active_only=True) so every DD02L row of the batch fits."
                % (cap, len(batch)))
        return rows

    def _open_dd02l_selection(self, timeout=None):
        """SE16 jusqu'à l'écran de sélection de DD02L, échec actionnable sur
        tout verdict autre que ``reached``."""
        state = self.reach_se16_selection_screen(_CANARY_TABLE, timeout)
        if state["reached"]:
            return
        if state["verdict"] == "rejected":
            raise AssertionError(
                "SE16 rejected DD02L (status type E): %s. "
                "Check SE16/DDIC display authorizations."
                % state["status_text"])
        detail = state["dialog_text"] or (
            "unknown modal window left open; perceive it with "
            "Get Screen Signature")
        raise AssertionError(
            "SE16 did not reach the DD02L selection screen (verdict "
            "'%s'): %s" % (state["verdict"], detail))

    def _read_dd02l_results(self, max_rows, timeout=None):
        """Résultat SE16 après exécution (F8) : lignes de la grille ALV par
        colonnes TECHNIQUES, ou liste vide quand AUCUNE ligne ne répond (SE16
        reste alors sur l'écran de sélection, sans message d'erreur). Toute
        autre issue est un échec actionnable, jamais « zéro ligne » : la fin
        du « busy » ne garantit pas l'écran (l'issue est SONDÉE), et une
        grille absente hors écran de sélection signifie le plus souvent un
        Data Browser resté en mode liste classique."""
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
                                       columns=list(_DD02L_COLUMNS))
        if state == "selection":
            message_type, message_text = self.get_status_message()
            if message_type == "E":
                raise AssertionError(
                    "classify_ddic_objects: SE16 refused the DD02L selection "
                    "(status type E): %s." % message_text)
            return []
        self.take_screenshot()
        raise AssertionError(
            "classify_ddic_objects: after execution neither the ALV grid nor "
            "the selection screen is present: the Data Browser is likely in "
            "classic list mode (no scriptable grid object). Run 'Use ALV "
            "Grid In Data Browser' once (persistent per user), or perceive "
            "the screen with Get Screen Signature.")

    def _verify_dd02l_criteria(self, active_only, timeout=None):
        """Sonde canari des critères positionnels de l'écran DD02L.

        Un lot sans AUCUNE ligne a deux explications : les objets sont
        vraiment absents de DD02L, ou les critères positionnels ``I1``/``I2``
        ne sont plus ``TABNAME``/``AS4LOCAL`` (le choix des champs de
        sélection PERSISTE par utilisateur et déplace les ``I<n>``). La sonde
        tranche : ``TABNAME=DD02L`` (mêmes critères que le lot) doit ramener
        la ligne de DD02L elle-même. Vérifiée une fois par instance, et
        seulement quand un lot revient vide : aucun coût sur le chemin
        nominal."""
        if getattr(self, "_dd02l_criteria_ok", False):
            return
        self._open_dd02l_selection(timeout)
        if self._truthy(active_only):
            self.input_text(_DD02L_AS4LOCAL_LOW, "A")
        self.input_text(_SE16_MAX_HITS, "20")
        self.input_text(_DD02L_TABNAME_LOW, _CANARY_TABLE)
        self.send_vkey(8)
        self.wait_until_busy_done()
        rows = self._read_dd02l_results(20, timeout)
        found = {str(r.get("TABNAME", "")).strip().upper() for r in rows}
        if _CANARY_TABLE not in found:
            self.take_screenshot()
            raise AssertionError(
                "classify_ddic_objects: the canary probe (TABNAME=%s) "
                "returned no row: the positional criteria of the DD02L "
                "selection screen do not map to TABNAME/AS4LOCAL (the SE16 "
                "field choice persists per user and shifts the I<n> fields). "
                "Reset the field selection for DD02L in SE16 (Settings > "
                "Fields for Selection) so the key fields come first, then "
                "rerun." % _CANARY_TABLE)
        self._dd02l_criteria_ok = True

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
