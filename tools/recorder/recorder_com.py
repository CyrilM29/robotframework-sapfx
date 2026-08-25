"""Frontiere COM/win32 du recorder bureau : moteur, arbre, geometrie, capture.

Le socle partage des modes du recorder : acquisition du moteur de scripting
(ROT puis fabrique), parcours de l'arbre d'objets (`walk`/`collect`),
surlignage, elements de la FENETRE ACTIVE seulement
(`iter_active_window_elements`), geometrie ecran (`element_rect`,
`element_at`), capture GDI d'un rectangle et `hardcopy_screenshot`
(HardCopyToMemory prefere au GDI). Les imports win32/pythoncom vivent ICI,
gardes par le try/except qui autorise --help hors Windows ; les modules
voisins importent ``com_error`` et consorts d'ici.

Extrait de ``sapgui_recorder.py`` (convention #13), qui re-exporte tout pour
les consommateurs historiques (GUI, tests, suites).
"""
import re
import time

try:
    import win32com.client
    import pythoncom
    from pythoncom import com_error
    import win32api  # GetCursorPos pour le mode survol (--hover)
    import win32con  # SRCCOPY, pour la capture d'écran de --record --screenshots
    import win32gui  # bureau/DC, pour la capture d'écran de --record --screenshots
    import win32ui   # DC compatibles + BitBlt, pour la capture d'écran
except ImportError:  # autorise --help / l'import sur des machines de développement non-Windows
    win32com = None
    win32api = None
    win32con = None
    win32gui = None
    win32ui = None
    # `pythoncom` et `com_error` doivent exister EUX AUSSI : le module les cite
    # dans des dizaines de clauses ``except (AttributeError, com_error)``, et
    # une clause d'exception est évaluée au moment où l'erreur survient. Les
    # laisser indéfinis remplacerait l'erreur réelle par un NameError opaque.
    pythoncom = None
    com_error = OSError

# Prefixe de session d'un id absolu SAP GUI : ``/app/con[0]/ses[0]/``.
_SESSION_PREFIX = re.compile(r"^/app/con\[\d+\]/ses\[\d+\]/")


def active_window(session):
    """Fenetre active de la session (repli : la derniere), ou ``None``."""
    try:
        window = session.ActiveWindow
        if window is not None:
            return window
        windows = session.Children
        return windows.ElementAt(windows.Count - 1) if windows.Count else None
    except (AttributeError, com_error):
        return None


def _matches_filter(filter_text, eid, etype):
    """Vrai si ``filter_text`` (insensible à la casse) apparaît dans l'id ou le type,
    ou si aucun filtre n'est fourni. Même règle que le filtre du mode dump."""
    if not filter_text:
        return True
    needle = filter_text.lower()
    return needle in (eid or "").lower() or needle in (etype or "").lower()


def relative_id(full_id):
    """Retire le préfixe de session (``/app/con[i]/ses[j]/``) d'un id SAP GUI.

    ``walk`` part du nœud session et SAP GUI expose le ``.Id`` **absolu** de chaque
    descendant (``/app/con[0]/ses[0]/wnd[0]/usr/txt...``). Or ``SapEccLibrary`` résout
    via ``session.findById(id)``, donc **relativement à la session**
    (``wnd[0]/usr/txt...``) : la forme qu'utilisent tests et ``resources/``. On
    normalise pour que chaque id surfacé soit réellement collable. Un id déjà
    relatif (sans préfixe) est renvoyé tel quel."""
    return _SESSION_PREFIX.sub("", full_id or "")

# Type de contrôle SAP GUI -> (mot-clé SapEccLibrary, attend-il une valeur ?).
# Noms alignés sur les keywords réels de _vendor/sapgui_base.py.
_KEYWORD_BY_TYPE = {
    "GuiTextField":     ("Input Text", True),
    "GuiCTextField":    ("Input Text", True),
    "GuiPasswordField": ("Input Password", True),
    "GuiButton":        ("Click Element", False),
    "GuiCheckBox":      ("Select Checkbox", False),
    "GuiRadioButton":   ("Select Radio Button", False),
    "GuiComboBox":      ("Select From List By Label", True),
}


def get_scripting_engine():
    """Retourne le GuiApplication connecté via la Running Object Table.

    Reproduit la logique de connexion de SapEccLibrary afin que les ids capturés
    correspondent exactement à ce que la bibliothèque résoudra à l'exécution."""
    if win32com is None:
        raise RuntimeError("pywin32 is required (Windows only).")
    try:
        rot = pythoncom.GetRunningObjectTable()
        enum = rot.EnumRunning()
        while True:
            monikers = enum.Next()
            if not monikers:
                break
            ctx = pythoncom.CreateBindCtx(0)
            name = monikers[0].GetDisplayName(ctx, None)
            if name.endswith("SAPGUI"):
                obj = rot.GetObject(monikers[0])
                sapgui = win32com.client.Dispatch(obj.QueryInterface(pythoncom.IID_IDispatch))
                return sapgui.GetScriptingEngine
    except com_error as exc:
        # Erreur COM transitoire (COM non initialisé sur ce thread, RPC en échec...) :
        # remonter en RuntimeError pour passer par le chemin d'erreur convivial de
        # main() ("Erreur : ...") plutôt qu'un traceback COM brut.
        raise RuntimeError("Could not query the Running Object Table: %s" % exc) from exc
    raise RuntimeError("No running SAPGUI engine found. Is SAP Logon Pad open?")


def walk(node, depth=0):
    """Génère ``(depth, id, type, text)`` pour ``node`` et tous ses descendants.

    Tous les nœuds n'exposent pas ``Children``/``Text`` ; la lecture est
    défensive car le modèle objet varie selon le type de contrôle (un GuiButton
    n'a pas d'enfants, un GuiShell peut en avoir beaucoup)."""
    node_id = _safe(node, "Id")
    node_type = _safe(node, "Type")
    node_text = _safe(node, "Text")
    yield depth, node_id, node_type, node_text
    children = getattr(node, "Children", None)
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
        yield from walk(child, depth + 1)


def _safe(node, attr):
    try:
        return getattr(node, attr)
    except (AttributeError, com_error):
        return ""


def collect(engine):
    """Retourne une liste plate de dictionnaires d'éléments pour toutes les connexions/sessions ouvertes."""
    elements = []
    for ci in range(engine.Children.Count):
        connection = engine.Children.ElementAt(ci)
        for si in range(connection.Children.Count):
            session = connection.Children.ElementAt(si)
            for depth, eid, etype, etext in walk(session):
                elements.append({"depth": depth, "id": relative_id(eid),
                                 "type": etype, "text": etext})
    return elements


# --- Surlignage (Visualize) --------------------------------------------------

def find_element(engine, element_id):
    """Cherche un élément par id dans toutes les sessions ouvertes ; ``None`` si absent.

    ``findById(id, False)`` renvoie ``None`` au lieu de lever quand l'id est
    introuvable : on parcourt les sessions car l'id pourrait viser n'importe laquelle."""
    for ci in range(engine.Children.Count):
        connection = engine.Children.ElementAt(ci)
        for si in range(connection.Children.Count):
            session = connection.Children.ElementAt(si)
            try:
                element = session.findById(element_id, False)
            except (AttributeError, com_error):
                element = None
            if element:
                return element
    return None


def highlight(engine, element_id, seconds=3.0):
    """Encadre l'élément en rouge via ``Visualize(True)`` quelques secondes. ``False`` si introuvable."""
    element = find_element(engine, element_id)
    if element is None:
        return False
    element.Visualize(True)
    time.sleep(seconds)
    try:
        element.Visualize(False)
    except com_error:
        pass
    return True


def _walk_objects(node):
    """Génère les objets élément (pas seulement leurs ids) de ``node`` et descendants."""
    yield node
    children = getattr(node, "Children", None)
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
        yield from _walk_objects(child)


def iter_active_window_elements(engine):
    """Comme `iter_elements`, mais restreint à la **fenêtre active de chaque
    session** (``session.ActiveWindow``) plutôt qu'à tout l'arbre de la session.

    Une session peut porter plusieurs fenêtres (modales/popups résiduelles non
    fermées proprement) ; sans ce filtre, un contrôle appartenant à une fenêtre
    non visible pouvait l'emporter dans `element_at` sur le contrôle réellement
    sous le curseur. On n'a pas de notion de z-order/premier-plan **entre
    sessions** via l'API Scripting (pas de hWnd fiable exposé), donc ceci
    reste une approximation par session, mais élimine le cas le plus fréquent
    (fenêtres résiduelles au sein d'une même session)."""
    for ci in range(engine.Children.Count):
        connection = engine.Children.ElementAt(ci)
        for si in range(connection.Children.Count):
            session = connection.Children.ElementAt(si)
            window = active_window(session)
            if window is not None:
                yield from _walk_objects(window)


def element_rect(element):
    """Rectangle écran ``(left, top, width, height)`` d'un contrôle, ou ``None``.

    ``ScreenLeft/ScreenTop/Width/Height`` sont en pixels écran (même repère que
    ``win32api.GetCursorPos``). ``None`` si absent ou dégénéré (menus, etc.)."""
    try:
        left = int(element.ScreenLeft)
        top = int(element.ScreenTop)
        width = int(element.Width)
        height = int(element.Height)
    except (AttributeError, com_error, ValueError, TypeError):
        return None
    if width <= 0 or height <= 0:
        return None
    return (left, top, width, height)


def capture_rect_to_bmp(rect, out_path):
    """Capture la région écran ``rect`` = ``(left, top, width, height)`` en bitmap
    à ``out_path``. Best-effort : ne lève **jamais**, retourne ``True``/``False``.

    N'a besoin d'aucun handle de fenêtre SAP spécifique (l'API SAP GUI Scripting
    n'en expose pas de façon fiable) : capture directement les pixels du bureau à
    ces coordonnées écran, obtenues via `element_rect` (``ScreenLeft/ScreenTop/
    Width/Height``, déjà utilisées et fiables pour ``--hover``). Recette GDI
    standard (``BitBlt`` depuis le DC du bureau) via pywin32, déjà une dépendance
    du projet : pas de nouvelle dépendance (Pillow, etc.)."""
    if win32gui is None or win32ui is None or win32con is None:
        return False
    left, top, width, height = rect
    hwin = hwindc = srcdc = memdc = bmp = None
    try:
        hwin = win32gui.GetDesktopWindow()
        hwindc = win32gui.GetWindowDC(hwin)
        srcdc = win32ui.CreateDCFromHandle(hwindc)
        memdc = srcdc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(srcdc, width, height)
        memdc.SelectObject(bmp)
        memdc.BitBlt((0, 0), (width, height), srcdc, (left, top), win32con.SRCCOPY)
        bmp.SaveBitmapFile(memdc, out_path)
        return True
    except Exception:
        # Best-effort : bureau verrouillé, session RDP sans affichage, version de
        # Windows/pywin32 inattendue... rien ne doit interrompre l'enregistrement.
        return False
    finally:
        if bmp is not None:
            try:
                win32gui.DeleteObject(bmp.GetHandle())
            except Exception:
                pass
        if memdc is not None:
            memdc.DeleteDC()
        if srcdc is not None:
            srcdc.DeleteDC()
        if hwin is not None and hwindc is not None:
            win32gui.ReleaseDC(hwin, hwindc)


def rect_contains(rect, x, y):
    """Le point écran (x, y) est-il dans le rectangle ``(left, top, width, height)`` ?"""
    left, top, width, height = rect
    return left <= x < left + width and top <= y < top + height


def element_at(engine, x, y):
    """Contrôle le plus **spécifique** (plus petite aire) sous le point écran (x, y).

    Les conteneurs (fenêtre, zone /usr) contiennent aussi le point ; on retient
    l'aire minimale pour viser la feuille interactive plutôt que son parent.
    Ne regarde que les fenêtres *actives* de chaque session
    (`iter_active_window_elements`) : une fenêtre résiduelle non visible ne
    doit jamais l'emporter sur le contrôle réellement sous le curseur."""
    best = None
    best_area = None
    for element in iter_active_window_elements(engine):
        rect = element_rect(element)
        if rect is not None and rect_contains(rect, x, y):
            area = rect[2] * rect[3]
            if best_area is None or area < best_area:
                best, best_area = element, area
    return best


def hardcopy_screenshot(session, out_base):
    """Capture la fenêtre active via ``HardCopyToMemory`` (API scripting :
    image fidèle de la fenêtre, même partiellement recouverte, supérieure au
    BitBlt du bureau) et l'écrit sous ``out_base`` + extension du format RÉEL
    (magic bytes). Retourne le chemin écrit, ou ``None`` si l'API est absente /
    la fenêtre indisponible (l'appelant replie sur la capture GDI)."""
    window = active_window(session)
    if window is None:
        return None
    try:
        raw = window.HardCopyToMemory(2)          # 2 = PNG demandé (GuiImageType)
    except Exception:
        return None
    if isinstance(raw, (bytes, bytearray, memoryview)):
        data = bytes(raw)
    else:
        try:
            data = bytes(b & 0xFF for b in raw)
        except TypeError:
            return None
    if not data:
        return None
    ext = ".png"
    if data[:2] == b"BM":
        ext = ".bmp"
    elif data[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif data[:4] == b"GIF8":
        ext = ".gif"
    path = out_base + ext
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError:
        return None
    return path
