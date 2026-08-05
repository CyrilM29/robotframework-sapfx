"""Mixin de perception d'écran : expose l'écran SAP GUI courant sous forme texte.

Sert deux usages :
* débogage de localisateurs (quels ids/champs existent à l'écran maintenant) ;
* alimentation d'un agent IA via le plugin rf-mcp (``integrations/robotmcp``), qui
  appelle ``Get Screen Signature`` pour *voir* l'écran avant d'agir.

La même idée de signature structurelle existe dans l'enregistreur desktop
(``tools/recorder/sapgui_recorder.py:screen_signature``) ; on la ré-implémente ici
en autonomie pour ne pas faire dépendre ``src/`` de ``tools/``. Les ids surfacés
sont **relatifs à la session** (``wnd[0]/usr/txt...``), donc directement collables
dans un test ou ``resources/``.
"""
import base64
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


# Codes de l'énumération GuiImageType de l'API SAP GUI Scripting. Le format
# RÉEL du buffer retourné est re-vérifié par magic bytes (_sniff_mime) : le
# MIME annoncé ne dépend jamais du seul code demandé.
_IMAGE_TYPE_CODES = {"bmp": 0, "jpeg": 1, "jpg": 1, "png": 2, "gif": 3}

_MAGIC_MIMES = (
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"BM", "image/bmp"),
    (b"GIF8", "image/gif"),
)


def _sniff_mime(data, fallback="image/png"):
    """MIME réel d'un buffer image par ses magic bytes (l'énumération
    GuiImageType a varié selon les versions, on ne lui fait pas confiance)."""
    for magic, mime in _MAGIC_MIMES:
        if data[:len(magic)] == magic:
            return mime
    return fallback


def _as_bytes(raw):
    """Buffer COM -> bytes : l'API retourne selon les versions un ``bytes``
    direct ou un SAFEARRAY (tuple d'entiers, parfois signés)."""
    if isinstance(raw, (bytes, bytearray, memoryview)):
        return bytes(raw)
    return bytes(b & 0xFF for b in raw)


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

    def get_screenshot_as_base64(self, image_format="png"):
        """Capture la fenêtre SAP active **en mémoire** et retourne l'image en
        base64 (chaîne sûre à travers la frontière rf-mcp, rien n'est écrit
        sur disque).

        Passe par ``ActiveWindow.HardCopyToMemory`` (API scripting : capture
        fidèle de la fenêtre, y compris hors focus, contrairement à une
        capture GDI de l'écran). ``image_format`` : ``png`` (défaut), ``jpeg``,
        ``bmp``, ``gif``. Le format réellement retourné est re-vérifié par
        magic bytes, pas supposé.

        Complète `Get Screen Signature` (texte) d'un canal **visuel** : un
        agent (ou un rapport) peut joindre la preuve d'écran ; voir
        `Log Screenshot` pour l'ancrer dans le log Robot. Échec explicite si
        l'API est absente (SAP GUI ancien) : `Take Screenshot` (fichier) reste
        le repli."""
        fmt = str(image_format).strip().lower()
        type_code = _IMAGE_TYPE_CODES.get(fmt, _IMAGE_TYPE_CODES["png"])
        try:
            raw = self.session.ActiveWindow.HardCopyToMemory(type_code)
        except (AttributeError, com_error) as exc:
            raise AssertionError(
                "HardCopyToMemory indisponible sur cette session (SAP GUI trop "
                "ancien ?). Utiliser Take Screenshot (fichier) en repli : %s" % exc)
        return base64.b64encode(_as_bytes(raw)).decode("ascii")

    def log_screenshot(self, message=""):
        """Capture la fenêtre SAP active et l'**incruste dans le log Robot**
        (image inline en data-URI : le ``log.html`` reste autoporteur, aucune
        pièce jointe à archiver à côté). ``message`` : texte optionnel affiché
        au-dessus de l'image. Retourne le MIME réellement incrusté."""
        b64 = self.get_screenshot_as_base64()
        mime = _sniff_mime(base64.b64decode(b64))
        html = '<img src="data:%s;base64,%s" style="max-width:100%%;">' % (mime, b64)
        if message:
            html = "%s<br>%s" % (message, html)
        logger.info(html, html=True)
        return mime

    # -- screenshot annoté (Set-of-Mark : boîtes numérotées + légende) ---------

    def get_annotated_screenshot(self, include_types=None):
        """Capture la fenêtre SAP active et y **dessine les cibles
        actionnables** : une boîte numérotée par champ modifiable /
        bouton / onglet, plus une légende ``numéro -> id``. Retourne un dict
        MCP-safe : ``image`` (PNG annoté en base64), ``mime``, ``legend``.

        C'est le pont entre la perception visuelle et l'effecteur : un agent
        (ou un humain) qui regarde l'image n'a plus à *deviner* des
        coordonnées : il lit le numéro, la légende lui donne l'id, et l'id
        alimente un keyword déterministe (`Click Element`, ou `Click Element
        At Offset` pour l'intérieur d'une zone opaque). Le patron
        « Set-of-Mark » des agents à vision, appliqué à SAP GUI.

        ``include_types`` (liste ou chaîne d'IDs de types séparés par des
        virgules, ex. ``GuiShell,GuiCustomControl``) remplace la sélection par
        défaut, utile pour n'annoter que les zones opaques. Seuls les
        éléments avec géométrie sont annotés. Nécessite Pillow (extra
        ``visual``).

        La légende est aussi enregistrée comme table de **références ``@N``**
        (voir `Get Screen Map`) : le numéro lu sur l'image se rejoue
        directement via `Click Screen Ref` / `Fill Screen Ref`."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        elements = self._screen_elements()
        if include_types:
            if isinstance(include_types, str):
                wanted = {part.strip() for part in include_types.split(",")
                          if part.strip()}
            else:
                wanted = {str(part).strip() for part in include_types}
            targets = [el for el in elements if el.type in wanted]
        else:
            from sapfx_common.semantic import actionable_targets
            targets = actionable_targets(elements)
        ox, oy = self._window_origin()
        boxes = []
        legend = {}
        for element in targets:
            # géométrie complète ET positive exigée : le vrai SAP GUI remonte
            # des largeurs négatives sur certains contrôles (constaté live A4H)
            if (element.left is None or element.top is None
                    or not element.width or element.width < 0
                    or not element.height or element.height < 0):
                continue
            number = str(len(boxes) + 1)
            boxes.append((number, element.left - ox, element.top - oy,
                          element.width, element.height))
            legend[number] = element.id
        annotated = self._draw_annotations(png, boxes)
        # La légende devient aussi la table de références @N : le numéro lu
        # sur l'image est directement actionnable via Click/Fill Screen Ref.
        self._register_screen_refs(legend, self._screen_header())
        return {"image": base64.b64encode(annotated).decode("ascii"),
                "mime": "image/png", "legend": legend}

    def log_annotated_screenshot(self, message="", include_types=None):
        """Capture annotée (voir `Get Annotated Screenshot`) **incrustée dans
        le log Robot** avec sa légende ``numéro -> id`` en tableau, le
        débogage de localisateurs d'un coup d'œil : chaque cible actionnable
        est numérotée sur l'image, son id copiable juste en dessous.
        Retourne la légende (dict)."""
        shot = self.get_annotated_screenshot(include_types)
        html = ('<img src="data:%s;base64,%s" style="max-width:100%%;">'
                % (shot["mime"], shot["image"]))
        if shot["legend"]:
            rows = "".join(
                "<tr><td>%s</td><td><code>%s</code></td></tr>" % (num, eid)
                for num, eid in shot["legend"].items())
            html += ('<table border="1" cellpadding="2">'
                     "<tr><th>n°</th><th>id</th></tr>%s</table>" % rows)
        if message:
            html = "%s<br>%s" % (message, html)
        logger.info(html, html=True)
        return shot["legend"]

    # -- assertion visuelle (hash perceptuel) ---------------------------------

    def get_screen_perceptual_hash(self, hash_size=8, mask_elements=None):
        """Capture la fenêtre SAP active et retourne son **hash perceptuel**
        (dHash hexadécimal, ``hash_size²`` bits, voir
        ``sapfx_common.visual_hash``).

        Le canal *pixels* de la perception : couvre précisément ce que l'API
        Scripting ne voit pas (GuiShell des listes modernes sans mode
        accessibilité, GuiChart/GuiMap officiellement record-only). Deux écrans
        visuellement identiques donnent le même hash ; un petit écart local, une
        distance de Hamming faible (`Screen Should Match Baseline` fait
        l'assertion).

        ``mask_elements`` **neutralise les zones légitimement volatiles** avant
        hachage (remplies de gris neutre) : ``auto`` masque la barre de statut
        et la barre de titre (l'horloge, le titre localisé : les sources
        classiques de faux positifs des snapshots), ou une liste d'ids séparés
        par des virgules pour masquer des régions choisies. Un id absent de
        l'écran est journalisé et ignoré (le masque est déclaratif, pas une
        assertion).

        Nécessite Pillow (``pip install Pillow``, extra ``visual`` du paquet)
        pour décoder le PNG ; l'algorithme lui-même est pur et testé hors SAP."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        pixels = self._decode_image_to_gray(png)
        regions = self._mask_regions_for(mask_elements)
        if regions:
            from sapfx_common.visual_hash import mask_regions
            pixels = mask_regions(pixels, regions)
        from sapfx_common.visual_hash import dhash_hex
        return dhash_hex(pixels, int(hash_size))

    def get_element_perceptual_hash(self, element_id, hash_size=8):
        """Hash perceptuel de la **région d'UN élément** (dHash hexadécimal),
        l'assertion visuelle ciblée là où elle a le plus de valeur : la grille
        dHash couvre l'élément seul au lieu de l'écran entier, donc un
        changement DANS un GuiShell opaque ou un GuiChart pèse sur tous les
        bits au lieu d'être dilué dans l'écran (sur une grille typique, la
        sensibilité gagne un facteur ~50).

        La région vient de `Get Element Screen Region` (le même relevé que
        l'effecteur coordonnées), convertie dans le repère de la capture de
        fenêtre. Échec explicite si l'élément n'existe pas ou sort de la
        capture. Voir `Element Should Match Baseline` pour l'assertion
        snapshot."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        pixels = self._decode_image_to_gray(png)
        region = self._element_image_region(element_id)
        from sapfx_common.visual_hash import crop_pixels, dhash_hex
        return dhash_hex(crop_pixels(pixels, region), int(hash_size))

    def get_screen_tile_hashes(self, tiles_x=4, tiles_y=4, hash_size=8):
        """Empreintes perceptuelles **par tuile** : la fenêtre est découpée en
        grille ``tiles_x × tiles_y`` (défaut 4×4) et chaque tuile reçoit son
        propre dHash. Retourne la liste des hex, ligne par ligne.

        Là où le hash global dilue un changement local dans l'écran entier, la
        grille le **localise** : comparer deux passages tuile à tuile
        (``sapfx_common.visual_hash.tiled_hamming``) dit *où* l'écran a bougé.
        C'est le canal fin de la sentinelle (`Check Screen Against Watch`
        l'utilise automatiquement) ; exposé ici pour les diagnostics manuels."""
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        pixels = self._decode_image_to_gray(png)
        from sapfx_common.visual_hash import tiled_dhash
        return tiled_dhash(pixels, int(tiles_x), int(tiles_y), int(hash_size))

    def screen_should_match_baseline(self, name, threshold=5,
                                     baseline_directory="visual_baselines",
                                     hash_size=8, mask_elements=None):
        """Assertion de **non-régression visuelle** de la fenêtre SAP active,
        sémantique *snapshot testing* :

        * premier passage (aucune baseline ``<name>.png``) : la capture devient
          la baseline. WARNING journalisé, le test passe (à committer si le
          rendu fait référence) ;
        * passages suivants : distance de Hamming entre le hash perceptuel de
          l'écran et celui recalculé depuis la baseline ; ``<= threshold``
          (défaut 5 sur 64 bits) = succès, sinon échec **auto-corrigible** :
          distance mesurée, chemins de la baseline et de la capture
          ``<name>.actual.png`` sauvegardée à côté pour comparaison, et le
          remède (supprimer la baseline si le changement est voulu).

        ``mask_elements`` (``auto`` ou ids séparés par des virgules) neutralise
        les zones volatiles AVANT hachage, identiquement pour la baseline et la
        capture : voir `Get Screen Perceptual Hash`. C'est le remède nominal à
        une baseline qui échoue à cause de l'horloge de la barre de statut.

        ``baseline_directory`` est relatif au répertoire courant du run (le
        committer avec la suite). Le hash est **recalculé depuis le PNG** de la
        baseline à chaque assertion : changer ``hash_size`` (ou le masque)
        reste honnête. Retourne la distance mesurée (0 pour une baseline
        nouvellement créée)."""
        from sapfx_common.visual_baseline import match_baseline
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        regions = self._mask_regions_for(mask_elements)
        decode = self._decode_image_to_gray
        if regions:
            from sapfx_common.visual_hash import mask_regions
            base_decode = decode

            def decode(image_bytes):
                return mask_regions(base_decode(image_bytes), regions)
        outcome = match_baseline(name, png, decode,
                                 str(baseline_directory), int(threshold),
                                 int(hash_size), what="L'écran")
        self._log_baseline_outcome(outcome, int(threshold))
        return outcome.distance

    def element_should_match_baseline(self, name, element_id, threshold=5,
                                      baseline_directory="visual_baselines",
                                      hash_size=8):
        """Assertion de non-régression visuelle de la **région d'UN élément** :
        même sémantique snapshot que `Screen Should Match Baseline`, mais la
        baseline est le PNG *recadré* sur l'élément : l'assertion est immune à
        tout ce qui change ailleurs sur l'écran (horloge, messages, autres
        champs) et les 64 bits du hash couvrent la seule zone qui compte.

        C'est l'assertion nominale pour les zones que l'API Scripting ne lit
        pas : la grille rendue dans un GuiShell opaque, un GuiChart, une image.
        Exemple::

            Element Should Match Baseline    grille-resultats
            ...    wnd[0]/usr/cntlGRID1/shellcont/shell

        Retourne la distance mesurée (0 pour une baseline nouvellement créée).
        Échec auto-corrigible avec ``<name>.actual.png`` sauvé à côté."""
        from sapfx_common.visual_baseline import match_baseline
        png = base64.b64decode(self.get_screenshot_as_base64("png"))
        region = self._element_image_region(element_id)
        cropped = self._crop_image(png, region)
        outcome = match_baseline(name, cropped, self._decode_image_to_gray,
                                 str(baseline_directory), int(threshold),
                                 int(hash_size),
                                 what="L'élément %s" % element_id)
        self._log_baseline_outcome(outcome, int(threshold))
        return outcome.distance

    @staticmethod
    def _log_baseline_outcome(outcome, threshold):
        """Journalisation commune des deux assertions snapshot (création en
        WARNING, un PNG à committer ; conformité en info)."""
        if outcome.created:
            logger.warn(
                "Baseline visuelle créée (%s), premier passage : committer "
                "ce PNG s'il fait référence." % outcome.baseline_path)
        else:
            logger.info("Conforme à la baseline (distance %d <= %d)."
                        % (outcome.distance, threshold))

    def _window_origin(self):
        """Origine écran de la fenêtre active, pour convertir une géométrie
        absolue (ScreenLeft/ScreenTop) dans le repère de la capture
        ``HardCopyToMemory`` (qui photographie la fenêtre, pas l'écran).
        Best-effort : (0, 0) si illisible."""
        try:
            window = self.session.ActiveWindow
            return int(window.ScreenLeft), int(window.ScreenTop)
        except (AttributeError, com_error, TypeError, ValueError):
            return 0, 0

    def _element_image_region(self, element_id):
        """Région d'un élément dans le repère de la capture de fenêtre :
        ``(left, top, width, height)``, le relevé écran de `Get Element
        Screen Region` (mixin pointeur), translaté de l'origine de la fenêtre."""
        rect = self.get_element_screen_region(element_id)
        ox, oy = self._window_origin()
        return (rect["left"] - ox, rect["top"] - oy,
                rect["width"], rect["height"])

    # Zones volatiles par défaut du masque ``auto`` : barre de statut (heure,
    # messages) et barre de titre (titre localisé) de la fenêtre principale.
    _AUTO_MASK_IDS = ("wnd[0]/sbar", "wnd[0]/titl")

    def _mask_regions_for(self, mask_elements):
        """Traduit ``mask_elements`` (None / ``auto`` / ids séparés par des
        virgules / liste) en régions du repère capture. Un id absent est
        journalisé et ignoré : le masque décrit des zones à neutraliser, il
        n'affirme pas leur présence."""
        if not mask_elements:
            return []
        if isinstance(mask_elements, str):
            ids = [part.strip() for part in mask_elements.split(",")
                   if part.strip()]
        else:
            ids = [str(part).strip() for part in mask_elements if str(part).strip()]
        if len(ids) == 1 and ids[0].lower() == "auto":
            ids = list(self._AUTO_MASK_IDS)
        ox, oy = self._window_origin()
        regions = []
        for element_id in ids:
            try:
                rect = self.get_element_screen_region(element_id)
            except AssertionError:
                logger.info("Masque visuel : élément '%s' absent de l'écran, "
                            "ignoré." % element_id)
                continue
            regions.append((rect["left"] - ox, rect["top"] - oy,
                            rect["width"], rect["height"]))
        return regions

    # -- sentinelle de dérive (surveillance sans tests) ------------------------

    def check_screen_against_watch(self, name, directory="screen_watch",
                                   fail_on_drift=False, visual_threshold=5,
                                   tiles_x=4, tiles_y=4):
        """**Sentinelle** : compare l'écran SAP actif à sa référence mémorisée,
        la détection de dérive SANS test scripté (voir
        ``sapfx_common.screen_watch``).

        Première visite de ``name`` : la perception structurée (et les
        empreintes visuelles, hash global + grille de tuiles, si Pillow est
        présent) devient la référence dans ``directory`` : WARNING journalisé,
        statut ``baseline-created``. Ensuite, TROIS canaux :

        * **structurel** : diff *intelligent* ligne à ligne (les ids qui se
          ressemblent sont appariés en ``~ ancien -> nouveau`` par le scoring
          de healing : un sous-écran renuméroté se lit comme un renommage) ;
        * **visuel global** : distance de Hamming du hash plein écran ;
        * **visuel localisé** : comparaison tuile à tuile (grille ``tiles_x ×
          tiles_y``, défaut 4×4) : une dérive locale trop diluée pour le hash
          global est rattrapée par SA tuile, nommée avec sa position, son
          rectangle et les éléments qui la recouvrent.

        Toute dérive est **nommée** et la perception courante sauvée en
        ``<name>.actual.*`` à côté de la référence. ``fail_on_drift=True``
        transforme la dérive en échec (sentinelle-assertion) ; par défaut la
        sentinelle **rapporte** et retourne le verdict (dict : ``status``,
        ``structural_diff``, ``visual_distance``, ``visual_tiles``) ; c'est au
        run de veille d'agréger.

        La référence est faite pour être committée : la supprimer revalide
        l'écran au passage suivant (même sémantique snapshot que
        `Screen Should Match Baseline`, ici sur TOUS les canaux)."""
        import os
        from sapfx_common.screen_watch import (WatchOutcome, apply_tile_verdict,
                                               compare_watch)
        from sapfx_common.visual_baseline import validate_snapshot_name
        safe = validate_snapshot_name(name, kind="surveillance")
        signature = self.get_screen_signature()
        visual = self._try_perceptual_hash()
        directory = os.path.abspath(str(directory))
        signature_path = os.path.join(directory, "%s.signature.txt" % safe)
        hash_path = os.path.join(directory, "%s.dhash.txt" % safe)
        tiles_path = os.path.join(directory, "%s.tiles.txt" % safe)
        if not os.path.exists(signature_path):
            tiles = self._try_tile_capture(int(tiles_x), int(tiles_y))
            os.makedirs(directory, exist_ok=True)
            with open(signature_path, "w", encoding="utf-8") as fh:
                fh.write(signature)
            if visual:
                with open(hash_path, "w", encoding="utf-8") as fh:
                    fh.write(visual)
            if tiles:
                tile_hashes, width, height = tiles
                with open(tiles_path, "w", encoding="utf-8") as fh:
                    fh.write("%d %d %d %d %d\n%s" % (
                        int(tiles_x), int(tiles_y), 8, width, height,
                        " ".join(tile_hashes)))
            logger.warn("Sentinelle : référence '%s' créée (%s), première "
                        "visite, à committer si l'écran fait référence."
                        % (safe, signature_path))
            outcome = WatchOutcome(name=safe, status="baseline-created")
            return self._watch_outcome_dict(outcome)
        with open(signature_path, "r", encoding="utf-8") as fh:
            baseline_signature = fh.read()
        baseline_hash = None
        if os.path.exists(hash_path):
            with open(hash_path, "r", encoding="utf-8") as fh:
                baseline_hash = fh.read().strip()
        outcome = compare_watch(safe, baseline_signature, signature,
                                baseline_hash, visual,
                                int(visual_threshold))
        tile_report = self._tile_drift_report(tiles_path, int(visual_threshold))
        outcome = apply_tile_verdict(outcome, tile_report)
        if outcome.drifted:
            actual_path = os.path.join(directory, "%s.actual.signature.txt" % safe)
            with open(actual_path, "w", encoding="utf-8") as fh:
                fh.write(signature)
            details = "\n".join(part for part in (
                outcome.structural_diff,
                ("distance visuelle %d bits" % outcome.visual_distance)
                if outcome.visual_distance is not None else None,
                outcome.visual_tiles) if part)
            message = ("Sentinelle : l'écran '%s' a DÉRIVÉ de sa référence.\n"
                       "%s\nPerception courante sauvée : %s"
                       % (safe, details, actual_path))
            if str(fail_on_drift).strip().lower() in _TRUTHY:
                self.take_screenshot()
                raise AssertionError(message)
            logger.warn(message)
        else:
            logger.info("Sentinelle : écran '%s' inchangé." % safe)
        return self._watch_outcome_dict(outcome)

    def _try_perceptual_hash(self):
        """Empreinte visuelle **best-effort** : la sentinelle reste utilisable
        sans Pillow (canal structurel seul) et sur les SAP GUI sans
        HardCopyToMemory."""
        try:
            return self.get_screen_perceptual_hash()
        except Exception:
            return None

    def _try_tile_capture(self, tiles_x, tiles_y, hash_size=8):
        """Grille de tuiles **best-effort** : ``(hashes, largeur, hauteur)`` ou
        ``None``, même politique que ``_try_perceptual_hash`` (le canal tuiles
        est un raffinement, jamais une condition de fonctionnement)."""
        try:
            png = base64.b64decode(self.get_screenshot_as_base64("png"))
            pixels = self._decode_image_to_gray(png)
            from sapfx_common.visual_hash import tiled_dhash
            hashes = tiled_dhash(pixels, tiles_x, tiles_y, hash_size)
            return hashes, (len(pixels[0]) if pixels else 0), len(pixels)
        except Exception:
            return None

    def _tile_drift_report(self, tiles_path, visual_threshold):
        """Compare l'écran courant à la grille de tuiles de la référence, avec
        le découpage ET le hash_size **de la référence** (un changement de
        configuration ne fabrique jamais une fausse dérive). Retourne le
        rapport localisé (tuiles au-delà du seuil + éléments recouvrants) ou
        ``None``, best-effort intégral."""
        import os
        if not os.path.exists(tiles_path):
            return None
        try:
            with open(tiles_path, "r", encoding="utf-8") as fh:
                header, hashes_line = fh.read().splitlines()[:2]
            btx, bty, bhash_size = (int(v) for v in header.split()[:3])
            baseline_tiles = hashes_line.split()
        except (ValueError, IndexError):
            return None
        current = self._try_tile_capture(btx, bty, bhash_size)
        if current is None:
            return None
        current_tiles, width, height = current
        if len(current_tiles) != len(baseline_tiles):
            return None
        from sapfx_common.screen_watch import locate_tile_drift
        from sapfx_common.visual_hash import tiled_hamming
        try:
            distances = tiled_hamming(baseline_tiles, current_tiles)
        except ValueError:
            return None
        if max(distances, default=0) <= visual_threshold:
            return None
        ox, oy = self._window_origin()
        elements = [
            (el.id, el.left - ox, el.top - oy, el.width, el.height)
            for el in self._screen_elements()
            if el.left is not None and el.top is not None
            and el.width and el.height
        ]
        return locate_tile_drift(distances, btx, bty, width, height,
                                 visual_threshold, elements) or None

    @staticmethod
    def _watch_outcome_dict(outcome):
        """Le verdict en dict de chaînes/entiers : MCP-safe, lisible en Robot."""
        return {"name": outcome.name, "status": outcome.status,
                "structural_diff": outcome.structural_diff,
                "visual_distance": outcome.visual_distance,
                "visual_tiles": outcome.visual_tiles}

    # -- frontières image (Pillow, stubbables en test) --------------------------

    @staticmethod
    def _decode_image_to_gray(image_bytes):
        """PNG/JPEG/BMP → matrice de gris (frontière image, stubbable en test).
        Impl partagée avec le canal Fiori dans
        ``sapfx_common.visual_baseline``, où Pillow est importé seulement à
        l'appel : l'assertion visuelle est opt-in (extra ``visual``), le reste
        de la bibliothèque n'en dépend jamais."""
        from sapfx_common.visual_baseline import decode_image_to_gray
        return decode_image_to_gray(image_bytes)

    @staticmethod
    def _crop_image(image_bytes, region):
        """Recadre un PNG sur ``region`` (left, top, width, height, repère
        capture) et retourne le PNG recadré. Frontière Pillow, stubbable.
        Lève ``ValueError`` si l'intersection avec la capture est vide."""
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError(
                "L'assertion visuelle a besoin de Pillow pour recadrer la "
                "capture : pip install Pillow (extra 'visual' du paquet "
                "robotframework-sapfx).")
        import io
        image = Image.open(io.BytesIO(image_bytes))
        x0 = max(int(region[0]), 0)
        y0 = max(int(region[1]), 0)
        x1 = min(int(region[0]) + int(region[2]), image.size[0])
        y1 = min(int(region[1]) + int(region[3]), image.size[1])
        if x1 <= x0 or y1 <= y0:
            raise ValueError(
                "Région (%s, %s, %sx%s) hors de la capture %dx%d : l'élément "
                "est-il visible dans la fenêtre ?" %
                (region[0], region[1], region[2], region[3],
                 image.size[0], image.size[1]))
        out = io.BytesIO()
        image.crop((x0, y0, x1, y1)).save(out, format="PNG")
        return out.getvalue()

    @staticmethod
    def _draw_annotations(image_bytes, boxes):
        """Dessine les boîtes numérotées (``(étiquette, left, top, width,
        height)``, repère capture) sur un PNG et retourne le PNG annoté.
        Frontière Pillow, stubbable en test."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            raise RuntimeError(
                "Le screenshot annoté a besoin de Pillow : pip install Pillow "
                "(extra 'visual' du paquet robotframework-sapfx).")
        import io
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(image)
        for label, left, top, width, height in boxes:
            draw.rectangle([left, top, left + width, top + height],
                           outline=(220, 30, 30), width=2)
            tag_width = 7 * len(label) + 6
            tag_top = max(top - 13, 0)
            draw.rectangle([left, tag_top, left + tag_width, tag_top + 13],
                           fill=(220, 30, 30))
            draw.text((left + 3, tag_top + 1), label, fill=(255, 255, 255))
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()
