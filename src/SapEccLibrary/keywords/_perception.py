"""Mixin de perception d'écran : expose l'écran SAP GUI courant sous forme texte.

Sert deux usages :
* débogage de localisateurs (quels ids/champs existent à l'écran maintenant) ;
* alimentation d'un agent IA via le plugin rf-mcp (``integrations/robotmcp``), qui
  appelle ``Get Screen Signature`` pour *voir* l'écran avant d'agir.

La même idée de signature structurelle existe dans l'enregistreur desktop
(``tools/recorder/recorder_poll.py:screen_signature``) ; on la ré-implémente ici
en autonomie pour ne pas faire dépendre ``src/`` de ``tools/``. Les ids surfacés
sont **relatifs à la session** (``wnd[0]/usr/txt...``), donc directement collables
dans un test ou ``resources/``.
"""
import re
from dataclasses import replace as _dc_replace

from pythoncom import com_error
from robot.api import logger

from sapfx_common.object_tree import (OBJECT_TREE_PROPERTIES, ScreenElement,
                                      flatten_object_tree)
from sapfx_common.perception_diff import diff_perception

# Préfixe de session SAP GUI (``/app/con[0]/ses[0]/``) à retirer des ids absolus.
_SESSION_PREFIX = re.compile(r"^/app/con\[\d+\]/ses\[\d+\]/")

# Types de champ éditables qu'un agent voudra cibler en priorité.
_EDITABLE_TYPES = ("GuiTextField", "GuiCTextField", "GuiPasswordField",
                   "GuiCheckBox", "GuiRadioButton", "GuiComboBox")

_TRUTHY = ("1", "true", "yes", "on")


def _safe(node, attr):
    try:
        return getattr(node, attr)
    except (AttributeError, com_error):
        return ""


def _safe_int(node, attr):
    try:
        value = getattr(node, attr)
    except (AttributeError, com_error):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _relative_id(full_id):
    """Retire le préfixe de session d'un id SAP GUI absolu (collable tel quel)."""
    return _SESSION_PREFIX.sub("", full_id or "")


def _replace_id(element, new_id):
    return _dc_replace(element, id=new_id)



def _walk(node):
    """Génère ``node`` puis tous ses descendants (parcours en profondeur)."""
    yield node
    try:
        children = getattr(node, "Children", None)
    except (AttributeError, com_error):
        return
    if children is None:
        return
    try:
        count = children.Count
    except (AttributeError, com_error):
        return
    for index in range(count):
        try:
            child = children.ElementAt(index)
        except com_error:
            continue
        yield from _walk(child)



class PerceptionKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Lecture seule : ne modifie aucun écran."""

    def _screen_elements(self):
        """Contrôles de la fenêtre active en liste de :class:`ScreenElement`
        (ids **relatifs à la session**, ordre du document).

        Chemin rapide : ``session.GetObjectTree``, un seul appel COM pour tout
        le sous-arbre, avec texte, éditabilité et géométrie (voir
        ``sapfx_common.object_tree``). Repli : la marche COM historique nœud par
        nœud. Une ``AttributeError`` (API absente de cette version de SAP GUI)
        est mémorisée sur l'instance pour ne pas retenter à chaque perception ;
        une ``com_error``/JSON invalide (transitoire) replie ponctuellement et
        sera retentée à l'appel suivant. Défensif : fenêtre indisponible ->
        liste vide (jamais d'exception COM brute)."""
        try:
            window = self.session.ActiveWindow
        except (AttributeError, com_error):
            window = None
        if window is None:
            return []
        if not getattr(self, "_object_tree_unsupported", False):
            try:
                payload = self.session.GetObjectTree(
                    _safe(window, "Id"), list(OBJECT_TREE_PROPERTIES))
                elements = flatten_object_tree(payload)
            except AttributeError:
                self._object_tree_unsupported = True
            except (com_error, ValueError, TypeError):
                pass   # transitoire : repli sur la marche, on retentera
            else:
                relative = [
                    _replace_id(el, _relative_id(el.id))
                    for el in elements if _relative_id(el.id)
                ]
                if relative:
                    return relative
        return [
            ScreenElement(
                id=eid,
                type=_safe(element, "Type"),
                text=_safe(element, "Text") or "",
                tooltip=_safe(element, "Tooltip") or "",
                changeable=bool(_safe(element, "Changeable")),
                left=_safe_int(element, "ScreenLeft"),
                top=_safe_int(element, "ScreenTop"),
                width=_safe_int(element, "Width"),
                height=_safe_int(element, "Height"),
            )
            for element in _walk(window)
            for eid in [_relative_id(_safe(element, "Id"))]
            if eid
        ]

    def _screen_header(self):
        """Ligne d'identité de l'écran actif (``# screen P/T/N``), partagée
        par la signature, la carte numérotée et le contrôle de fraîcheur des
        références. Défensif : ``# screen ?`` si la session est illisible."""
        try:
            info = self.session.Info
            return "# screen %s/%s/%s" % (
                _safe(info, "Program"), _safe(info, "Transaction"),
                _safe(info, "ScreenNumber"))
        except (AttributeError, com_error):
            return "# screen ?"

    def get_screen_signature(self, mode="full", include_geometry=False,
                             pair_renames=False):
        """Retourne une vue texte de l'écran SAP GUI actif, ligne par ligne.

        Première ligne : ``# screen <Program>/<Transaction>/<ScreenNumber>``.
        Puis une ligne par contrôle : ``<id relatif>\\t<Type>\\t<texte>``. Les champs
        éditables (saisie, cases, radios, listes) sont préfixés ``* `` pour qu'un
        agent les repère immédiatement.

        ``mode=diff`` retourne le **différentiel** depuis l'appel précédent de ce
        keyword sur cette instance (lignes ``- `` disparues / ``+ `` apparues,
        inchangé résumé en ``= N unchanged line(s)``) : après une action, c'est
        « ce qui a changé » qui intéresse l'agent, pour une fraction des tokens.
        Le premier appel en diff retourne la vue complète (rien à comparer).
        L'écran est TOUJOURS relu en entier (jamais de cache d'état) ; seul le
        rendu diffère. ``pair_renames=True`` (avec ``mode=diff``) active le
        **diff intelligent** : les lignes disparues/apparues dont les ids se
        ressemblent (scoring de ``sapfx_common.healing``) sont appariées en
        ``~ ancien -> nouveau`` : un sous-écran renuméroté se lit comme un
        renommage, pas comme deux blocs de lignes.

        ``mode=semantic`` retourne la vue **formulaire** de l'écran : une ligne
        par cible actionnable (champ modifiable ou bouton/onglet) portant son
        localisateur humain *vérifié* (émis seulement s'il re-résout vers ce
        seul élément, sinon ``?``), l'id technique, le type et la valeur
        courante : ``* Table Name\\twnd[0]/usr/ctxtDATABROWSE-TABLENAME\\t
        GuiCTextField\\t= T000``. C'est la perception la plus directement
        actionnable pour un agent (chaque ligne se rejoue en ``Fill Field By
        Label``/``Click Button By Label``, ou par id) et la moins chère en
        tokens. Cette vue ne participe pas à la mémoire du ``mode=diff``.

        ``include_geometry=True`` ajoute une 4e colonne ``@gauche,haut LxH``
        (coordonnées écran) aux contrôles qui en ont, utile pour situer un
        champ ou déboguer un localisateur par libellé. Le format par défaut à
        3 colonnes reste inchangé (contrat du filtrage rf-mcp).

        La lecture passe par le chemin rapide ``GetObjectTree`` quand l'API est
        disponible (un appel COM au lieu d'un par contrôle), avec repli
        automatique sur la marche COM historique : voir ``_screen_elements``.

        Lecture seule et indépendant de la locale (on n'expose que types et ids,
        pas de message localisé). C'est le keyword de perception consommé par le
        plugin rf-mcp pour que l'agent *voie* l'écran avant d'agir."""
        header = self._screen_header()

        mode_normalized = str(mode).strip().lower()
        elements = self._screen_elements()
        if mode_normalized == "semantic":
            from sapfx_common.semantic import screen_affordances
            return "\n".join([header] + screen_affordances(elements))

        with_geometry = str(include_geometry).strip().lower() in _TRUTHY
        lines = [header]
        for element in elements:
            mark = "* " if element.type in _EDITABLE_TYPES else "  "
            line = "%s%s\t%s\t%s" % (mark, element.id, element.type,
                                     (element.text or "").strip())
            if with_geometry and element.left is not None and element.top is not None:
                line += "\t@%d,%d %sx%s" % (
                    element.left, element.top,
                    element.width if element.width is not None else "?",
                    element.height if element.height is not None else "?")
            lines.append(line)
        signature = "\n".join(lines)

        previous = getattr(self, "_last_screen_signature", None)
        self._last_screen_signature = signature
        if mode_normalized == "diff":
            return diff_perception(
                previous, signature,
                pair_renames=str(pair_renames).strip().lower() in _TRUTHY)
        return signature

    # -- carte numérotée + action par référence (@N) ---------------------------
    # Boucle perception -> action resserrée pour un agent, dans l'esprit du
    # ``map`` / ``@e1`` de Vibium : la carte numérote les cibles actionnables,
    # l'agent agit ensuite par le numéro, plus court et moins sujet aux
    # erreurs de recopie qu'un id SAP complet. Les références sont éphémères
    # (dernière perception de l'instance) et re-vérifiées avant chaque action.

    def _register_screen_refs(self, refs, header):
        """Mémorise la table ``numéro -> id`` de la dernière perception
        numérotée (carte OU screenshot annoté, la dernière gagne), avec
        l'identité d'écran du moment pour le contrôle de fraîcheur."""
        self._screen_refs = dict(refs)
        self._screen_refs_header = header

    def get_screen_map(self):
        """Retourne la **carte numérotée** de l'écran SAP actif : une ligne
        par cible actionnable, ``@N`` suivi de la ligne d'affordance de
        ``mode=semantic`` (libellé humain vérifié, id, type, valeur) ::

            # screen SAPLSE16/SE16/0102
            @1\t* Table Name\twnd[0]/usr/ctxtDATABROWSE-TABLENAME\tGuiCTextField\t= T000
            @2\t  Number of Entries\twnd[0]/tbar[1]/btn[31]\tGuiButton

        Chaque numéro devient une **référence éphémère** utilisable par
        `Resolve Screen Ref`, `Click Screen Ref` et `Fill Screen Ref` : l'agent
        lit la carte puis agit par ``@N`` sans recopier l'id (la résolution
        re-vérifie l'écran avant d'agir). Même numérotation que la légende de
        `Get Annotated Screenshot` quand tous les éléments ont une géométrie.
        Lecture seule ; les références vivent sur l'instance (dernière
        perception numérotée)."""
        from sapfx_common.semantic import actionable_targets, screen_affordances
        header = self._screen_header()
        elements = self._screen_elements()
        # screen_affordances émet une ligne par cible de actionable_targets,
        # dans le même ordre : le zip est le contrat, pas une coïncidence.
        targets = actionable_targets(elements)
        lines = screen_affordances(elements)
        refs = {}
        numbered = [header]
        for index, (target, line) in enumerate(
                zip(targets, lines, strict=True), start=1):
            refs[str(index)] = target.id
            numbered.append("@%d\t%s" % (index, line))
        self._register_screen_refs(refs, header)
        return "\n".join(numbered)

    def resolve_screen_ref(self, ref):
        """Résout une référence ``@N`` de la dernière perception numérotée
        (`Get Screen Map` ou `Get Annotated Screenshot`) en **id d'élément**,
        jamais en silence : échec actionnable si aucune perception n'a été
        faite, si la référence est inconnue, si l'écran a changé depuis la
        perception, ou si l'élément a disparu (dans ces deux derniers cas le
        remède est nommé : re-percevoir). Accepte ``3`` ou ``@3``. Retourne
        l'id (chaîne, MCP-safe)."""
        refs = getattr(self, "_screen_refs", None)
        if not refs:
            raise AssertionError(
                "Aucune perception numérotée mémorisée : appeler d'abord "
                "Get Screen Map (ou Get Annotated Screenshot) pour relever "
                "les références @N de l'écran.")
        number = str(ref).strip().lstrip("@")
        if number not in refs:
            raise AssertionError(
                "Référence @%s inconnue : la dernière perception numérotée "
                "expose @1..@%d (relever la carte à jour avec Get Screen Map)."
                % (number, len(refs)))
        element_id = refs[number]
        registered = getattr(self, "_screen_refs_header", None)
        current = self._screen_header()
        if registered and current != registered:
            raise AssertionError(
                "L'écran a changé depuis la perception numérotée (%r -> %r), "
                "les références @N sont périmées : re-percevoir avec "
                "Get Screen Map avant d'agir par référence."
                % (registered, current))
        try:
            self.session.findById(element_id)
        except (AttributeError, com_error):
            raise AssertionError(
                "La cible @%s (%s) n'existe plus à l'écran : re-percevoir "
                "avec Get Screen Map avant d'agir par référence."
                % (number, element_id))
        return element_id

    def click_screen_ref(self, ref):
        """Clique la cible ``@N`` de la dernière perception numérotée : la
        référence est résolue en id (`Resolve Screen Ref` : fraîcheur et
        présence re-vérifiées), puis le clic passe par le keyword
        **déterministe** `Click Element`. Retourne l'id cliqué (journalisé :
        la trace reste rejouable par id dans une suite)."""
        element_id = self.resolve_screen_ref(ref)
        logger.info("Click Screen Ref @%s -> %s"
                    % (str(ref).strip().lstrip("@"), element_id))
        self.click_element(element_id)
        return element_id

    def fill_screen_ref(self, ref, text):
        """Saisit ``text`` dans la cible ``@N`` de la dernière perception
        numérotée : résolution `Resolve Screen Ref` puis `Input Text`
        déterministe. Retourne l'id rempli. La valeur saisie n'est jamais
        utilisée comme localisateur (même règle que le recorder sémantique)."""
        element_id = self.resolve_screen_ref(ref)
        logger.info("Fill Screen Ref @%s -> %s"
                    % (str(ref).strip().lstrip("@"), element_id))
        self.input_text(element_id, text)
        return element_id

    def get_open_windows(self):
        """Retourne la pile de **fenêtres ouvertes** de la session : une liste de
        dicts JSON-safe ``{id, type, title, modal}`` dans l'ordre de la session
        (``wnd[0]`` d'abord ; ``modal`` vaut ``True`` pour les ``GuiModalWindow``).

        C'est le garde-fou du piège constaté live sur SESSION_MANAGER :
        ``Run Transaction`` peut rapporter un succès (``Info.Transaction`` porte
        déjà le tcode) alors qu'un **modal d'erreur est resté affiché** et
        neutralise le champ OK-code. Vérifier ``modal`` ici (ou ``modal_open``
        dans l'état applicatif rf-mcp, qui appelle ce keyword) avant d'enchaîner.
        Lecture seule, indépendant de la locale (le titre est du contexte humain,
        jamais une ancre d'assertion). Défensif : fenêtre illisible ignorée,
        session indisponible -> liste vide."""
        windows = []
        try:
            children = self.session.Children
            count = children.Count
        except (AttributeError, com_error):
            return windows
        for index in range(count):
            try:
                window = children.ElementAt(index)
            except (AttributeError, com_error):
                continue
            window_id = _relative_id(_safe(window, "Id"))
            if not window_id:
                continue
            window_type = _safe(window, "Type") or ""
            windows.append({
                "id": window_id,
                "type": window_type,
                "title": (_safe(window, "Text") or "").strip(),
                "modal": window_type == "GuiModalWindow",
            })
        return windows
