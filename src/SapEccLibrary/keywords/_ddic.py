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
Les primitives d'ÉCRAN SE16 (`Reach Se16 Selection Screen`,
`Fill Multiple Selection`, `Get Se16 Selection Criteria`, lecteur de
résultat) vivent dans le mixin voisin ``_se16.py`` et sont atteintes par la
composition.
"""
import datetime
import json

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

from ._diagnostics import _truthy
from ._se16 import _SE16_MAX_HITS

# Criteres positionnels de l'ecran DD02L (les champs cles viennent en tete
# tant que le choix des champs de selection n'a pas ete modifie ; la sonde
# canari `_verify_dd02l_criteria` tranche quand un lot revient vide).
_DD02L_TABNAME_LOW = "wnd[0]/usr/ctxtI1-LOW"
_DD02L_AS4LOCAL_LOW = "wnd[0]/usr/ctxtI2-LOW"

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

#: Table des champs du dictionnaire, source du contrat de champs.
_DD03L_TABLE = "DD03L"

#: Colonnes DD03L consommées par le contrat de champs : même règle que pour
#: DD02L, la lecture est RESTREINTE aux ids techniques (indépendants de la
#: locale et du profil d'affichage ALV). Relevé live : la grille en expose 31,
#: neuf suffisent à décrire un champ.
_DD03L_COLUMNS = ("FIELDNAME", "POSITION", "KEYFLAG", "ROLLNAME", "DATATYPE",
                  "LENG", "DECIMALS", "DOMNAME", "CHECKTABLE")

#: Marge de lignes DD02L par objet demandé (versions ``AS4LOCAL``/``AS4VERS``
#: multiples comprises) : borne MAX_SEL et plafond de lecture d'un lot. Un
#: plafond ATTEINT est un échec actionnable, jamais une troncature muette.
_ROWS_PER_OBJECT = 10


class DdicKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : aucune donnée
    métier n'est modifiée, seuls des écrans de consultation sont pilotés.
    Suppose ``self.session`` posé par les keywords de connexion."""

    _truthy = staticmethod(_truthy)

    def read_ddic_table_fields(self, table, active_only=True, max_fields=200,
                               timeout=None):
        """Champs d'une table du dictionnaire (DD03L), en liste de dicts.

        Ouvre DD03L dans le Data Browser, filtre sur ``TABNAME`` (et
        ``AS4LOCAL=A``, la version active, quand ``active_only``), exécute et
        lit la grille RESTREINTE aux colonnes techniques consommées
        (``FIELDNAME``, ``POSITION``, ``KEYFLAG``, ``ROLLNAME``, ``DATATYPE``,
        ``LENG``, ``DECIMALS``, ``DOMNAME``, ``CHECKTABLE``). Les lignes sont
        rendues triées par position : la lecture est déterministe et
        indépendante de l'ordre d'affichage.

        Les critères sont résolus par NOM via `Get Se16 Selection Criteria`,
        jamais par position : c'est ce qui rend le keyword insensible au choix
        des champs de sélection persistant par utilisateur, sans avoir besoin
        de la sonde canari que la classification DD02L doit, elle, exécuter.

        Mêmes garde-fous « jamais vert et faux » que `Classify Ddic Objects` :
        un plafond de lecture ATTEINT est un échec (une troncature ne doit
        jamais être muette), une grille absente hors écran de sélection nomme
        `Use ALV Grid In Data Browser`, et un résultat VIDE est un échec (la
        table est inconnue de DD03L) au lieu d'un contrat de champs vide qui
        passerait pour une table sans champ. Lecture seule.
        """
        name = str(table).strip().upper()
        if not name:
            raise AssertionError("read_ddic_table_fields: no table name given.")
        try:
            cap = int(str(max_fields).strip())
        except (TypeError, ValueError):
            cap = 0
        if cap < 1:
            raise AssertionError(
                "read_ddic_table_fields: max_fields must be a strictly "
                "positive integer.")
        state = self.reach_se16_selection_screen(_DD03L_TABLE, timeout)
        if not state["reached"]:
            raise AssertionError(
                "read_ddic_table_fields: SE16 did not reach the %s selection "
                "screen (verdict '%s'): %s. Check SE16/DDIC display "
                "authorizations." % (_DD03L_TABLE, state["verdict"],
                                     state["status_text"]
                                     or state["dialog_text"]))
        criteria = self.get_se16_selection_criteria()
        self.input_text(self._dd03l_criterion(criteria, "TABNAME"), name)
        if self._truthy(active_only):
            self.input_text(self._dd03l_criterion(criteria, "AS4LOCAL"), "A")
        self.input_text(_SE16_MAX_HITS, str(cap))
        self.send_vkey(8)
        self.wait_until_busy_done()
        rows = self._read_se16_rows(cap, list(_DD03L_COLUMNS), timeout,
                                    "read_ddic_table_fields")
        if len(rows) >= cap:
            raise AssertionError(
                "read_ddic_table_fields: the DD03L read hit its row cap (%s "
                "rows for '%s'): the field contract would be silently "
                "truncated. Raise max_fields." % (cap, name))
        if not rows:
            raise AssertionError(
                "read_ddic_table_fields: DD03L returned no field for '%s'. "
                "The object is unknown to the dictionary (or has no active "
                "version): classify it with Classify Ddic Objects before "
                "asking for its field contract." % name)
        return sorted(rows, key=lambda row: (str(row.get("POSITION", "")),
                                             str(row.get("FIELDNAME", ""))))

    @staticmethod
    def _dd03l_criterion(criteria, field):
        """Localisateur d'un critère DD03L attendu, échec listant les critères
        réellement présents sinon (jamais une saisie à l'aveugle dans un champ
        positionnel qui aurait bougé)."""
        locator = criteria.get(field)
        if locator is None:
            raise AssertionError(
                "read_ddic_table_fields: the DD03L selection screen exposes no "
                "'%s' criterion; present criteria: %s. Reset the field "
                "selection for DD03L in SE16 (Settings > Fields for Selection) "
                "so the key fields are available."
                % (field, ", ".join(sorted(criteria))))
        return locator

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
        """Résultat SE16 d'un lot DD02L, colonnes techniques de classification."""
        return self._read_se16_rows(max_rows, list(_DD02L_COLUMNS), timeout,
                                    "classify_ddic_objects")

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
