"""Mixin *arbres SAP GUI* (``GuiShell`` de sous-type ``Tree``) : lire, développer,
sélectionner par clé, par texte ou par chemin.

Le menu SAP Easy Access, l'IMG de SPRO, l'Object Navigator (SE80), SM59 et
SICF sont des arbres ; la bibliothèque n'avait qu'un `Select Node` hérité qui
exige la clé opaque (et échouait par intermittence) et aucune lecture. Les
chemins API vérifiés live le 2026-09-07 (A4H, SAP GUI 8.00) : ``GetAllNodeKeys``,
``GetNodeTextByKey``, ``SelectNode``, ``ExpandNode``, ``IsFolder``,
``GetNodeChildrenCount``, ``GetSubNodesCol``, ``SelectedNode``, et pour un
arbre à colonnes (``GetTreeType() = 2``, l'IMG) ``GetColumnNames`` +
``GetItemText(clé, colonne)`` là où ``GetNodeTextByKey`` rend une chaîne vide.
Les clés sont rendues TELLES QUELLES (complétées à gauche sur un arbre à
colonnes : ``'01  1      1'``). Logique pure dans ``sapfx_common.tree_nodes``.
Tous les retours sont JSON-safe (rf-mcp).
"""
from pythoncom import com_error
from robot.api import logger

from sapfx_common.com_safety import shell_subtype
from sapfx_common.object_tree import LEAF_SHELL_SUBTYPES
from sapfx_common.tree_nodes import (
    TreeNode,
    find_nodes_by_column,
    find_nodes_by_text,
    format_candidates,
    split_path,
    unique_match,
)

_TRUTHY = ("1", "true", "yes", "on")

# Types d'item d'un arbre à colonnes (``GuiTree.GetItemType``).
_ITEM_TYPES = {0: "hiérarchie", 1: "image", 2: "texte", 3: "case", 4: "bouton", 5: "lien"}
_LINK_ITEM = 5


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUTHY


def _collection(obj):
    """Une collection COM (``Count`` + ``Item`` / ``ElementAt``/appel) en liste."""
    if obj is None:
        return []
    try:
        count = int(obj.Count)
    except (AttributeError, TypeError, ValueError):
        return list(obj)
    items = []
    for index in range(count):
        for accessor in ("Item", "ElementAt"):
            method = getattr(obj, accessor, None)
            if method is not None:
                items.append(method(index))
                break
        else:
            items.append(obj(index))
    return items


class TreeKeywords:
    """Mixin ajouté à :class:`SapEccLibrary`. Suppose ``self.session`` connectée."""

    # Même profondeur de descente que le résolveur de grille : les releases
    # récentes enveloppent les contrôles dans des GuiSplitterShell.
    _MAX_CONTAINER_DEPTH = 6

    @staticmethod
    def _is_tree(obj):
        """Vrai pour un arbre réel : ``GuiShell`` de sous-type ``Tree`` ; sans
        sous-type exposé (doublure), la présence de ``GetAllNodeKeys`` décide."""
        subtype = shell_subtype(obj)
        if subtype:
            return subtype == "Tree"
        return hasattr(obj, "GetAllNodeKeys")

    def _tree(self, tree_id):
        """Le contrôle-arbre derrière ``tree_id``, ou un échec ACTIONNABLE.

        Même contrat que le résolveur de grille (mesuré le 2026-09-08 sur SPRO :
        visé sur le conteneur de l'arbre, ce lecteur laissait fuir un
        ``AttributeError: <unknown>.GetAllNodeKeys`` qui ne disait ni ce qui
        était visé ni quoi faire) : un shell d'un autre sous-type est refusé
        en nommant son lecteur ; un conteneur est DESCENDU jusqu'au premier
        arbre, en WARNING jamais silencieux ; rien en dessous = échec nommant
        la profondeur explorée et `Get Screen Signature`."""
        self.element_should_be_present(tree_id)
        element = self.session.findById(tree_id)
        if self._is_tree(element):
            return element
        subtype = shell_subtype(element)
        if subtype in LEAF_SHELL_SUBTYPES:
            self.take_screenshot()
            raise ValueError(
                "Element '%s' n'est pas un arbre (GuiShell/%s) : %s. Percevoir avec "
                "Get Screen Signature (colonne type GuiShell/<SubType>)."
                % (tree_id, subtype,
                   {"GridView": "une grille ALV, lire par Read Grid",
                    "Calendar": "un calendrier, Pick Calendar Date"}.get(
                       subtype, "un contrôle sans lecteur d'arbre")))
        found, found_id = self._tree_below(element, tree_id)
        if found is not None:
            logger.warn(
                "Tree '%s' n'est pas l'arbre lui-même mais un conteneur : arbre "
                "trouvé à '%s' et utilisé. Mettre le localisateur à jour si ce "
                "système devient la cible principale." % (tree_id, found_id))
            return found
        self.take_screenshot()
        raise ValueError(
            "Element '%s' n'est pas un arbre (GuiShell/Tree) et aucun arbre n'a été "
            "trouvé en dessous (%d niveaux explorés). Vérifier le localisateur avec "
            "Get Screen Signature : l'écran rend-il bien un arbre ?"
            % (tree_id, self._MAX_CONTAINER_DEPTH))

    def _tree_below(self, node, base_id):
        """Premier descendant qui est un arbre, en parcours en largeur borné."""
        queue = [(node, 0)]
        while queue:
            current, depth = queue.pop(0)
            if depth >= self._MAX_CONTAINER_DEPTH:
                continue
            for child in self._children_of(current):
                if self._is_tree(child):
                    return child, str(getattr(child, "Id", "") or base_id)
                queue.append((child, depth + 1))
        return None, None

    def _tree_columns(self, tree):
        try:
            return [str(c) for c in _collection(tree.GetColumnNames())]
        except (AttributeError, com_error, TypeError):
            return []

    def _node(self, tree, key, columns):
        text = ""
        try:
            text = str(tree.GetNodeTextByKey(key) or "")
        except (AttributeError, com_error):
            pass
        values = {}
        for column in columns:
            try:
                values[column] = str(tree.GetItemText(key, column) or "")
            except (AttributeError, com_error):
                values[column] = ""
        if not text and columns:
            # arbre à colonnes : le texte vit dans la colonne TEXT (IMG) ou
            # dans la première colonne non vide.
            text = values.get("TEXT") or next((v for v in values.values() if v), "")
        folder = False
        try:
            folder = bool(tree.IsFolder(key))
        except (AttributeError, com_error):
            pass
        children = None
        try:
            children = int(tree.GetNodeChildrenCount(key))
        except (AttributeError, com_error, TypeError, ValueError):
            pass
        level = None
        try:
            level = int(tree.GetNodeLevel(key))
        except (AttributeError, com_error, TypeError, ValueError):
            pass
        return TreeNode(key=str(key), text=text.strip(), level=level,
                        folder=folder, children=children, columns=values)

    def _all_nodes(self, tree, max_nodes):
        keys = _collection(tree.GetAllNodeKeys())
        limit = int(max_nodes)
        if len(keys) > limit:
            raise AssertionError(
                "L'arbre porte %d nœuds rendus, plafond max_nodes=%d atteint : "
                "relever le plafond ou lire par nœud (Read Tree Children)."
                % (len(keys), limit))
        columns = self._tree_columns(tree)
        return [self._node(tree, key, columns) for key in keys]

    def read_tree_nodes(self, tree_id, max_nodes=500):
        """Lit les nœuds RENDUS d'un arbre : liste de dicts ``{key, text,
        level, folder, children, columns}`` dans l'ordre de l'arbre (les
        nœuds d'un dossier replié n'existent pas encore : `Expand Tree Node`
        d'abord). ``key`` est la clé opaque telle quelle (la repasser
        intacte, padding compris) ; ``columns`` porte les colonnes d'un arbre
        de type 2. Plafond ATTEINT = échec (jamais une liste tronquée en
        silence).

        Exemple :
        | ${nodes}=    `Read Tree Nodes`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell
        | Should Be Equal    ${nodes}[0][text]    Favorites
        """
        tree = self._tree(tree_id)
        return [node.as_dict() for node in self._all_nodes(tree, max_nodes)]

    def read_tree_children(self, tree_id, key):
        """Les enfants DIRECTS du nœud ``key`` (``GetSubNodesCol``), même
        forme que `Read Tree Nodes` ; liste vide pour une feuille.

        Exemple :
        | ${key}=    `Get Tree Node Key By Text`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    Custom Code Analysis
        | ${children}=    `Read Tree Children`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    ${key}
        | Should Be Equal    ${children}[0][text]    SYCM - Custom Code Management
        """
        tree = self._tree(tree_id)
        try:
            keys = _collection(tree.GetSubNodesCol(key))
        except (AttributeError, com_error) as exc:
            raise ValueError("Nœud %r introuvable dans '%s' (%s)." % (key, tree_id, exc))
        columns = self._tree_columns(tree)
        return [self._node(tree, k, columns).as_dict() for k in keys]

    def get_selected_tree_node(self, tree_id):
        """La clé du nœud sélectionné (``SelectedNode``), ``""`` si aucun.

        Exemple :
        | ${key}=    `Select Tree Node By Text`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    SE38 - ABAP Editor
        | ${selected}=    `Get Selected Tree Node`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell
        | Should Be Equal    ${selected}    ${key}
        """
        return str(self._tree(tree_id).SelectedNode or "")

    def select_tree_node(self, tree_id, key, expand=False):
        """Sélectionne le nœud ``key`` par ``SelectNode`` (la voie qui passe
        sur tous les nœuds relevés, là où l'affectation de ``selectedNode`` du
        keyword hérité échouait par intermittence), le développe si
        ``expand``, et VÉRIFIE la sélection en relisant ``SelectedNode``.
        Échec actionnable nommant la clé et les nœuds disponibles.

        Mesuré le 2026-10-06 sur l'accueil SAP Easy Access (A4H) : sur un
        arbre fraîchement affiché, ``SelectNode`` reste SANS EFFET
        (sélection et focus inchangés, même répété, précédé d'un
        ``SetFocus`` ou d'un ``TopNode`` réaffecté) tant qu'aucun
        ``ExpandNode`` n'a éveillé le contrôle ; l'éveil vaut pour
        l'instance du contrôle, qu'un retour à l'accueil par
        ``SESSION_MANAGER`` recrée endormie. Quand la sélection n'a pas
        pris, le keyword développe donc le parent du nœud (le nœud lui-même
        pour une racine), geste sans effet visible sur un dossier déjà
        ouvert, puis sélectionne à nouveau : cette seconde lecture fait
        foi.

        Exemple :
        | `Select Tree Node`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    0000000050
        | ${selected}=    `Get Selected Tree Node`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell
        | Should Be Equal    ${selected}    0000000050
        """
        tree = self._tree(tree_id)
        wanted = str(key)
        try:
            selected = self._select_and_read(tree, wanted)
            if selected != wanted and self._wake_tree(tree, wanted):
                selected = self._select_and_read(tree, wanted)
            if _as_bool(expand):
                tree.ExpandNode(wanted)
        except com_error as exc:
            self.take_screenshot()
            raise ValueError(
                "Impossible de sélectionner le nœud %r de '%s' (%s). Nœuds "
                "rendus :\n%s" % (wanted, tree_id, exc,
                                  format_candidates(self._all_nodes(tree, 500))))
        if selected != wanted:
            self.take_screenshot()
            raise AssertionError(
                "Le nœud %r de '%s' n'est pas sélectionné après SelectNode "
                "(sélection relue : %r)." % (wanted, tree_id, selected))
        return selected

    def _select_and_read(self, tree, key):
        tree.SelectNode(key)
        self.wait_until_busy_done()
        return str(tree.SelectedNode or "")

    def _wake_tree(self, tree, key):
        """Développe le parent de ``key`` (``key`` lui-même pour une
        racine) : le geste qui rend ``SelectNode`` effectif sur un arbre que
        rien n'a encore touché. Faux si le développement est refusé (une
        racine sans enfant : rien à réessayer)."""
        try:
            parent = str(tree.GetParent(key) or "")
        except (AttributeError, com_error):
            parent = ""
        try:
            tree.ExpandNode(parent or key)
        except (AttributeError, com_error):
            return False
        self.wait_until_busy_done()
        return True

    def expand_tree_node(self, tree_id, key):
        """Développe le nœud ``key`` (``ExpandNode``) et retourne ses enfants
        (`Read Tree Children`) : le geste « ouvrir un dossier et voir ce qu'il
        contient » en un keyword.

        Exemple :
        | ${children}=    `Expand Tree Node`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    Favo
        | Should Not Be Empty    ${children}
        """
        tree = self._tree(tree_id)
        try:
            tree.ExpandNode(str(key))
        except com_error as exc:
            raise ValueError("Impossible de développer le nœud %r de '%s' (%s)."
                             % (key, tree_id, exc))
        self.wait_until_busy_done()
        return self.read_tree_children(tree_id, key)

    def get_tree_node_key_by_text(self, tree_id, text, exact=False):
        """La clé du SEUL nœud rendu dont le texte correspond (préfixe
        insensible à la casse, ``exact=True`` pour l'égalité). Ambiguïté
        remontée avec les candidats, jamais tranchée.

        Exemple :
        | ${key}=    `Get Tree Node Key By Text`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    Administrator Tools
        | Should Be Equal    ${key}    0000000048
        """
        tree = self._tree(tree_id)
        node = unique_match(self._all_nodes(tree, 2000), str(text), _as_bool(exact),
                            "dans l'arbre '%s'" % tree_id)
        return node.key

    def select_tree_node_by_text(self, tree_id, text, exact=False, expand=False):
        """`Get Tree Node Key By Text` puis `Select Tree Node` : retourne la clé.

        Exemple :
        | ${key}=    `Select Tree Node By Text`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    SE80
        | Should Be Equal    ${key}    0000000049
        """
        key = self.get_tree_node_key_by_text(tree_id, text, exact)
        return self.select_tree_node(tree_id, key, expand)

    def select_tree_node_by_path(self, tree_id, path, exact=False, expand=True):
        """Descend un CHEMIN de textes (``Favorites > URL - ABAP Samples``,
        séparateur ``>``) niveau par niveau : à chaque niveau, l'enfant dont le
        texte correspond est sélectionné (et développé si ``expand``, pour que
        le niveau suivant existe). Retourne la clé du nœud final. Le premier
        niveau se cherche parmi les nœuds sans parent rendu (les racines).

        Exemple :
        | ${key}=    `Select Tree Node By Path`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    User Menu > Administrator Tools > SE38
        | Should Be Equal    ${key}    0000000050
        """
        tree = self._tree(tree_id)
        segments = split_path(path)
        if not segments:
            raise ValueError("Chemin d'arbre vide : attendu 'Racine > Dossier > Nœud'.")
        columns = self._tree_columns(tree)
        nodes = self._all_nodes(tree, 2000)
        candidates = [n for n in nodes if n.level in (None, 0, 1)] or nodes
        current = None
        for depth, segment in enumerate(segments, start=1):
            node = unique_match(candidates, segment, _as_bool(exact),
                                "au niveau %d du chemin %r dans '%s'"
                                % (depth, path, tree_id))
            current = node
            if depth < len(segments):
                if _as_bool(expand):
                    try:
                        tree.ExpandNode(node.key)
                    except com_error:
                        pass
                    self.wait_until_busy_done()
                try:
                    keys = _collection(tree.GetSubNodesCol(node.key))
                except (AttributeError, com_error):
                    keys = []
                candidates = [self._node(tree, k, columns) for k in keys]
        assert current is not None
        return self.select_tree_node(tree_id, current.key)

    def double_click_tree_node(self, tree_id, key):
        """Double-clique le nœud ``key`` (``DoubleClickNode`` : l'action
        d'ouverture, celle d'un double-clic utilisateur sur une transaction du
        menu SAP).

        Exemple :
        | `Double Click Tree Node`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    0000000050
        | ${transaction}=    `Get Current Transaction`
        | Should Be Equal    ${transaction}    SE38
        """
        tree = self._tree(tree_id)
        try:
            tree.DoubleClickNode(str(key))
        except com_error as exc:
            raise ValueError("Impossible de double-cliquer le nœud %r de '%s' (%s)."
                             % (key, tree_id, exc))
        self.wait_until_busy_done()

    def select_node(self, tree_id, node_id, expand=False):
        """Le `Select Node` de robotframework-sapguilibrary, même signature :
        passe par ``SelectNode`` (jamais l'affectation de ``selectedNode``, qui
        échouait par intermittence avec une ``AttributeError`` COM non
        actionnable), et vérifie la sélection. Voir `Select Tree Node`.

        Exemple :
        | `Select Node`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    0000000049
        | ${selected}=    `Get Selected Tree Node`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell
        | Should Be Equal    ${selected}    0000000049
        """
        self.select_tree_node(tree_id, node_id, expand)

    def select_node_link(self, tree_id, link_id1, link_id2):
        """Sélectionne puis clique le LIEN de l'item (``link_id1``, clé du
        nœud ; ``link_id2``, nom de la colonne) d'un arbre à colonnes
        ``tree_id`` (``SelectItem`` puis ``ClickLink``). Absorbé de
        robotframework-sapguilibrary le 2026-10-06 (Apache License 2.0, voir
        NOTICE).

        L'item doit être un lien (type d'item 5 de l'API) : un autre item est
        REFUSÉ en nommant son type. Sur un texte, ``ClickLink`` ne fait rien
        et ne lève rien, donc le keyword de l'amont passait sans effet
        (relevé le 2026-10-06 sur BD87, dont les colonnes sont du texte).
        Les liens de l'IMG de SPRO (documentation, notes de version) en sont,
        avec des clés complétées d'espaces : la clé se lit par `Get Tree Node
        Key By Text`.

        Exemple :
        | ${key}=    `Get Tree Node Key By Text`    wnd[0]/usr/cntlTREE_CONTROL_CONTAINER/shellcont/shell    SAP Customizing Implementation Guide
        | `Select Node Link`    wnd[0]/usr/cntlTREE_CONTROL_CONTAINER/shellcont/shell    ${key}    1
        | `Wait Until Element Present`    wnd[0]/shellcont/shell/shellcont[1]/shell
        """
        self.element_should_be_present(tree_id)
        tree = self.session.findById(tree_id)
        try:
            kind = tree.GetItemType(link_id1, link_id2)
        except (AttributeError, com_error):
            kind = None
        if kind != _LINK_ITEM:
            self.take_screenshot()
            raise ValueError(
                "L'item (%r, %r) de '%s' n'est pas un lien (%s) : Select Node Link "
                "n'aurait rien fait. Pour un nœud : Select Tree Node ou Double Click "
                "Tree Node." % (link_id1, link_id2, tree_id,
                                "type d'item %s, %s" % (kind, _ITEM_TYPES.get(kind, "inconnu"))
                                if kind is not None else
                                "nœud ou colonne introuvable, ou arbre sans colonnes"))
        tree.selectItem(link_id1, link_id2)
        tree.clickLink(link_id1, link_id2)
        self._explicit_pause()

    def find_tree_nodes_by_column(self, tree_id, column, value, exact=True):
        """TOUS les nœuds rendus dont la COLONNE ``column`` vaut ``value``
        (liste de dicts, comme `Read Tree Nodes`). Les moniteurs de statut
        (BD87) ont des clés de nœud POSITIONNELLES (``N1``, ``N2``...) et un
        texte de nœud localisé : le code de statut est dans une colonne
        (``Column2``), donc c'est elle qu'on interroge. Une colonne absente
        échoue en listant les colonnes de l'arbre.

        Exemple :
        | ${posted}=    `Find Tree Nodes By Column`    wnd[0]/usr/cntlTREE_CONTAINER/shellcont/shell    Column2    53
        | Length Should Be    ${posted}    1
        | Should Be Equal    ${posted}[0][key]    N7
        """
        tree = self._tree(tree_id)
        try:
            found = find_nodes_by_column(
                self._all_nodes(tree, 2000), column, str(value), _as_bool(exact))
        except ValueError as err:
            raise AssertionError(str(err)) from err
        return [n.as_dict() for n in found]

    def find_tree_nodes(self, tree_id, text, exact=False):
        """TOUS les nœuds rendus dont le texte correspond (liste de dicts) :
        la sonde qui précède un choix quand un texte se répète.

        Exemple :
        | ${nodes}=    `Find Tree Nodes`    wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell    SEPM_REF_APPS_DG
        | Length Should Be    ${nodes}    2
        """
        tree = self._tree(tree_id)
        return [n.as_dict() for n in find_nodes_by_text(
            self._all_nodes(tree, 2000), str(text), _as_bool(exact))]
