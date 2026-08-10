"""SAP GUI Recorder : capture de localisateurs pour le client bureau (phase 2).

Cinq usages, du plus simple au plus interactif :

1. **Dump** (par défaut) : parcourt l'arbre d'objets SAP GUI en direct via l'API de
   scripting et liste chaque élément avec son id complet, son type et son texte.
   Cet id est exactement ce que l'on colle dans un mot-clé SapEccLibrary
   (``wnd[0]/usr/txtRSYST-BNAME``).
2. **Surlignage** (``--highlight ID``) : encadre un contrôle **en rouge à l'écran**
   via la méthode native ``Visualize`` de SAP GUI Scripting, pour vérifier
   visuellement à quoi correspond un id.
3. **Clic-à-capturer** (``--capture``) : surveille l'élément qui a le **focus** dans
   SAP GUI (``ActiveWindow.GuiFocus``) ; à chaque fois que tu cliques/tabules sur un
   champ, il enregistre son id, le surligne, et propose une **ligne de mot-clé prête
   à coller** (``Input Text``, ``Click Element``…). C'est le vrai enregistreur.
4. **Survol** (``--hover``) : encadre en continu le contrôle **sous le curseur** (et
   non celui qui a le focus) : associe la position souris (``win32api.GetCursorPos``)
   au plus petit rectangle écran (``ScreenLeft/Top/Width/Height``) qui la contient.
   Inspecteur live ; avec ``--out``, enregistre aussi chaque contrôle survolé.
5. **Enregistreur** (``--record``) : suit tes manipulations et transcrit le déroulé
   en une **séquence de keywords rejouable** (un corps ``*** Test Cases ***``). Modèle
   par aller-retour : entre deux écrans, diff des champs éditables -> ``Input Text``…
   puis l'action de soumission (``Run Transaction`` si OK-code saisi, sinon ``Send Vkey 0``).
   Avec ``--screenshots``, capture aussi (best-effort, bitmap) l'écran d'arrivée de
   chaque aller-retour, utile pour diagnostiquer visuellement un replay qui diverge.

Utilisation (avec SAP Logon Pad ouvert et une session en cours) :
    python sapgui_recorder.py                      # arbre complet -> terminal
    python sapgui_recorder.py --json               # dump JSON -> captures/dump_<horodatage>.json
    python sapgui_recorder.py --json out.json      # dump JSON -> captures/out.json
    python sapgui_recorder.py --filter txt         # ids/types contenant "txt"
    python sapgui_recorder.py --highlight wnd[0]/usr/ctxtDATABROWSE-TABLENAME
    python sapgui_recorder.py --capture            # focus : capture 1 locator (Ctrl+C)
    python sapgui_recorder.py --hover              # curseur : inspecteur (Ctrl+C)
    python sapgui_recorder.py --record             # enregistreur de déroulé (Ctrl+C)
    python sapgui_recorder.py --record --out scenario.robot
    python sapgui_recorder.py --record --semantic  # keywords humains (Fill Field By Label…),
                                                   # id technique en commentaire (moteur natif)

Politique de sauvegarde unifiée : tout artefact (dump JSON et captures) atterrit dans
``tools/recorder/captures/`` : horodaté si aucun nom n'est donné, sous ``captures/`` pour un
chemin relatif, et tel quel pour un chemin absolu. Le dump sans ``--json`` reste un
simple affichage terminal.

Prérequis : pywin32, et le scripting activé côté serveur et client.
"""
import argparse
import codecs
import datetime
import json
import locale
import os
import re
import sys
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

# Dossier de sauvegarde par défaut des captures interactives.
CAPTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

# Préfixe de session d'un id absolu SAP GUI : ``/app/con[0]/ses[0]/``.
_SESSION_PREFIX = re.compile(r"^/app/con\[\d+\]/ses\[\d+\]/")


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


# --- Clic-à-capturer (focus polling) -----------------------------------------

def active_focus(session):
    """Retourne l'élément focalisé de la fenêtre active d'une session, ou ``None``.

    ``GuiMainWindow.GuiFocus`` pointe le contrôle qui a le focus : c'est le socle
    fiable du clic-à-capturer (validé en live sur ABAP Platform A4H)."""
    try:
        window = session.ActiveWindow
        if window is None:
            return None
        return window.GuiFocus
    except (AttributeError, com_error):
        return None


def current_focus(engine):
    """Premier élément focalisé trouvé parmi toutes les sessions, ou ``None``."""
    for ci in range(engine.Children.Count):
        connection = engine.Children.ElementAt(ci)
        for si in range(connection.Children.Count):
            element = active_focus(connection.Children.ElementAt(si))
            if element is not None:
                return element
    return None


def suggest_keyword(etype, eid, etext=""):
    """Propose une ligne de mot-clé SapEccLibrary adaptée au type de contrôle."""
    if etype == "GuiOkCodeField":
        return "Run Transaction    <CODE>"
    entry = _KEYWORD_BY_TYPE.get(etype)
    if entry is None:
        return "# %s : pas de mot-clé direct    %s" % (etype, eid)
    name, needs_value = entry
    if needs_value:
        return "%s    %s    %s" % (name, eid, etext or "<valeur>")
    return "%s    %s" % (name, eid)


def format_capture_block(record):
    """Met en forme une capture (dict id/type/text) : ligne d'info + mot-clé suggéré."""
    text = (" = %r" % record["text"]) if record.get("text") else ""
    keyword = suggest_keyword(record["type"], record["id"], record.get("text", ""))
    return "[%s] %s%s\n    %s" % (record["type"], record["id"], text, keyword)


def _timestamped_path(prefix, ext, now=None):
    stamp = (now or datetime.datetime.now()).strftime("%Y%m%d_%H%M%S")
    return os.path.join(CAPTURES_DIR, "%s_%s.%s" % (prefix, stamp, ext))


def default_capture_path(now=None):
    """Chemin de capture par défaut : ``captures/capture_<horodatage>.txt``."""
    return _timestamped_path("capture", "txt", now)


def default_dump_path(now=None):
    """Chemin de dump JSON par défaut : ``captures/dump_<horodatage>.json``."""
    return _timestamped_path("dump", "json", now)


def resolve_save_path(path, default_factory):
    """Politique de sauvegarde unifiée : tout va dans ``captures/`` sauf chemin absolu.

    - ``None`` (option sans valeur)  -> ``default_factory()`` (horodaté dans captures/)
    - chemin **relatif**             -> sous ``captures/`` (artefact de travail)
    - chemin **absolu**              -> tel quel (l'utilisateur décide explicitement)

    Un chemin relatif qui contient des ``..`` menant hors de ``captures/`` (ex.
    ``--out ../../evil.txt``) est rejeté plutôt que silencieusement résolu en
    dehors du dossier : ce serait une sortie de ``captures/`` inattendue au vu
    du contrat ci-dessus."""
    if not path:
        return default_factory()
    if os.path.isabs(path):
        return path
    captures_root = os.path.normpath(CAPTURES_DIR)
    candidate = os.path.normpath(os.path.join(captures_root, path))
    if os.path.commonpath([captures_root, candidate]) != captures_root:
        raise ValueError(
            "Le chemin relatif %r sort de %s ; utilise un chemin absolu si "
            "c'est voulu." % (path, CAPTURES_DIR))
    return candidate


def capture_loop(engine, out_path, do_highlight=True, poll_seconds=0.3,
                 filter_text=None, _max_iterations=None, _writer=print):
    """Mode interactif : enregistre chaque nouvel élément focalisé jusqu'à Ctrl+C.

    ``filter_text`` (option ``--filter``) restreint aux éléments dont l'id ou le type
    le contient. ``_max_iterations`` / ``_writer`` sont des points d'injection pour les
    tests : en production la boucle tourne indéfiniment et écrit sur stdout + fichier."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fh = open(out_path, "w", encoding="utf-8")
    fh.write("# Captures SAP GUI Spy : %s\n\n" % out_path)
    fh.flush()
    _writer("Mode capture : clique/tabule sur les champs dans SAP GUI.")
    _writer("Chaque élément focalisé est enregistré -> %s" % out_path)
    _writer("Ctrl+C pour arrêter.\n")
    last_id = None
    count = 0
    iterations = 0
    try:
        while _max_iterations is None or iterations < _max_iterations:
            iterations += 1
            element = current_focus(engine)
            if element is not None:
                eid = relative_id(_safe(element, "Id"))
                if eid and eid != last_id:
                    last_id = eid
                    etype = _safe(element, "Type")
                    if _matches_filter(filter_text, eid, etype):
                        record = {"id": eid, "type": etype,
                                  "text": _safe(element, "Text")}
                        block = format_capture_block(record)
                        count += 1
                        _writer(block)
                        fh.write(block + "\n\n")
                        fh.flush()
                        if do_highlight:
                            try:
                                element.Visualize(True)
                            except com_error:
                                pass
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        _writer("\nArrêt : %s élément(s) capturé(s) dans %s" % (count, out_path))
    finally:
        fh.close()
    return count


# --- Survol : encadrer l'élément SOUS LE CURSEUR -----------------------------

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


def hover_loop(engine, cursor_fn=None, poll_seconds=0.15, out_path=None,
               filter_text=None, _max_iterations=None, _writer=print):
    """Mode survol : encadre en rouge le contrôle sous le curseur, en continu.

    ``filter_text`` (option ``--filter``) restreint aux contrôles dont l'id ou le type
    le contient : les autres sont ignorés (ni cadre ni capture). ``cursor_fn`` (défaut
    ``win32api.GetCursorPos``) et ``_max_iterations`` sont des points d'injection pour
    les tests. Si ``out_path`` est fourni, chaque nouveau contrôle survolé est aussi
    enregistré (sinon : inspecteur live, sans fichier)."""
    if cursor_fn is None:
        if win32api is None:
            raise RuntimeError("win32api requis pour le mode survol (pywin32, Windows).")
        cursor_fn = win32api.GetCursorPos
    fh = None
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        fh = open(out_path, "w", encoding="utf-8")
        fh.write("# Survol SAP GUI Spy : %s\n\n" % out_path)
        fh.flush()
    _writer("Mode survol : déplace la souris sur SAP GUI ; le contrôle sous le curseur est encadré.")
    _writer("Ctrl+C pour arrêter." + (" Enregistrement -> %s" % out_path if out_path else ""))
    last_id = None
    current = None
    count = 0
    iterations = 0
    try:
        while _max_iterations is None or iterations < _max_iterations:
            iterations += 1
            x, y = cursor_fn()
            element = element_at(engine, x, y)
            eid = relative_id(_safe(element, "Id")) if element is not None else ""
            if eid and eid != last_id:
                etype = _safe(element, "Type")
                if current is not None:          # efface le cadre précédent
                    try:
                        current.Visualize(False)
                    except com_error:
                        pass
                    current = None
                last_id = eid
                if _matches_filter(filter_text, eid, etype):
                    current = element
                    try:
                        element.Visualize(True)
                    except com_error:
                        pass
                    record = {"id": eid, "type": etype,
                              "text": _safe(element, "Text")}
                    block = format_capture_block(record)
                    offset = offset_suggestion(etype, eid, element_rect(element), x, y)
                    if offset:
                        block += "\n    " + offset
                    _writer(block)
                    if fh is not None:
                        fh.write(block + "\n\n")
                        fh.flush()
                        count += 1
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        _writer("\nArrêt.")
    finally:
        if current is not None:                  # ne pas laisser de cadre orphelin
            try:
                current.Visualize(False)
            except com_error:
                pass
        if fh is not None:
            fh.close()
    return count


# --- Mode record : transcrit les manipulations en séquence rejouable -----------
#
# SAP est un système d'écrans à états : l'utilisateur remplit des champs (aucun
# aller-retour) puis SOUMET (aller-retour serveur). On exploite exactement ça :
# entre deux écrans, on diffe l'état des champs éditables et on émet les Input...
# correspondants, puis l'action de soumission (Run Transaction si un okcode a été
# saisi, sinon Send Vkey 0). La frontière d'aller-retour = changement d'écran
# (programme/transaction/numéro d'écran via session.Info) : robuste sans devoir
# intercepter session.Busy. La logique de décision est isolée dans process_poll
# (pure, testable hors SAP).

# Types de champs éditables dont on suit la valeur.
_EDITABLE_TYPES = ("GuiTextField", "GuiCTextField", "GuiPasswordField",
                   "GuiCheckBox", "GuiRadioButton", "GuiComboBox")


def first_session(engine):
    """Première session ouverte (con[0]/ses[0]) ou ``None``."""
    for ci in range(engine.Children.Count):
        connection = engine.Children.ElementAt(ci)
        for si in range(connection.Children.Count):
            return connection.Children.ElementAt(si)
    return None


def screen_key(session):
    """Identité de l'écran courant ``(programme, transaction, n° écran)`` via
    ``session.Info`` : son changement marque un aller-retour serveur."""
    try:
        info = session.Info
    except (AttributeError, com_error):
        return None
    return (_safe(info, "Program"), _safe(info, "Transaction"), _safe(info, "ScreenNumber"))


def okcode_value(session):
    """Valeur courante du champ OK-code (``wnd[0]/tbar[0]/okcd``), ou ``""``."""
    try:
        field = session.findById("wnd[0]/tbar[0]/okcd", False)
    except (AttributeError, com_error):
        return ""
    return _safe(field, "Text") or ""


def _field_value(element, etype):
    """Valeur enregistrable d'un champ éditable : texte, état coché, ou ``None``
    pour un mot de passe (illisible par scripting, pour des raisons de sécurité)."""
    if etype in ("GuiCheckBox", "GuiRadioButton"):
        val = _safe(element, "Selected")
        return bool(val) if val != "" else False
    if etype == "GuiPasswordField":
        return None
    return _safe(element, "Text")


def snapshot_fields(session):
    """État des champs éditables de la fenêtre active : ``{id: (type, valeur)}``,
    dans l'ordre d'affichage (ordre de parcours de l'arbre)."""
    out = {}
    window = active_window(session)
    if window is None:
        return out
    for element in _walk_objects(window):
        etype = _safe(element, "Type")
        if etype in _EDITABLE_TYPES:
            eid = relative_id(_safe(element, "Id"))
            if eid:
                out[eid] = (etype, _field_value(element, etype))
    return out


def active_window(session):
    """Fenêtre active de la session, ou ``None`` (défensif)."""
    try:
        return session.ActiveWindow
    except (AttributeError, com_error):
        return None


def _field_step(eid, etype, value):
    """Ligne de keyword pour un champ modifié, ou ``None`` si rien à émettre.
    Les valeurs libres sont échappées façon RF (`rf_escape_value`).

    `diff_to_steps` a déjà écarté les champs inchangés et les nouveaux champs
    vides : une valeur falsy ICI est donc une action délibérée (case décochée,
    champ vidé) et s'enregistre : ``Unselect Checkbox``, ``Input Text …
    ${EMPTY}``, au même contrat que le moteur natif. Seul le radio reste
    émis-si-True : son False est induit par le frère nouvellement coché."""
    if etype in ("GuiTextField", "GuiCTextField"):
        return "Input Text    %s    %s" % (eid, rf_escape_value(value))
    if etype == "GuiPasswordField":
        return "Input Password    %s    <password>" % eid
    if etype == "GuiCheckBox":
        return ("Select Checkbox    %s" if value else "Unselect Checkbox    %s") % eid
    if etype == "GuiRadioButton":
        return ("Select Radio Button    %s" % eid) if value else None
    if etype == "GuiComboBox":
        return ("Select From List By Label    %s    %s"
                % (eid, rf_escape_value(value))) if value else None
    return None


def diff_to_steps(prev, cur):
    """Lignes de keyword pour les champs dont la valeur a changé entre deux états,
    dans l'ordre d'affichage de ``cur``."""
    steps = []
    for eid, (etype, value) in cur.items():
        old = prev.get(eid)
        if old is not None and old[1] == value:
            continue
        if old is None and not value:
            continue                       # nouveau champ vide -> rien à enregistrer
        step = _field_step(eid, etype, value)
        if step:
            steps.append(step)
    return steps


def submit_step(okcd):
    """Action de soumission : ``Run Transaction`` si un OK-code a été saisi, sinon
    ``Send Vkey 0`` (Entrée, le bouton exact n'est pas déductible en polling)."""
    return ("Run Transaction    %s" % okcd) if okcd else "Send Vkey    0"


def screen_signature(session):
    """Signature structurelle de l'écran : ``(screen_key, tuple trié de TOUS les ids
    de contrôles de la fenêtre active)``.

    Le seul ``screen_key`` (programme/transaction/n° écran) ne suffit pas : *Exécuter*
    dans SE16 réaffiche le **même** dynpro en y ajoutant la grille ALV de résultat,
    sans changer le n° d'écran ni les champs de sélection. En prenant l'ensemble
    complet des ids de contrôles, l'apparition (ou disparition) du moindre contrôle
    marque l'aller-retour. La signature est stable pendant la saisie (les valeurs
    changent, pas les ids), donc ne déclenche pas de fausse frontière. Limite connue :
    un réaffichage strictement identique du même écran n'est pas détecté."""
    window = active_window(session)
    ids = []
    if window is not None:
        for element in _walk_objects(window):
            ids.append(relative_id(_safe(element, "Id")))
    return (screen_key(session), tuple(sorted(ids)))


def scan_active_window(session):
    """Équivalent à ``(screen_signature(session), snapshot_fields(session))``,
    mais en un **seul** parcours COM de la fenêtre active au lieu de deux.

    ``record_loop`` sonde à chaque cycle (0.4s par défaut) ; appeler
    séparément ``screen_signature`` puis ``snapshot_fields`` fait marcher deux
    fois l'arbre d'objets complet pour le même résultat. Cette fonction
    fusionne les deux parcours -- ``screen_signature``/``snapshot_fields``
    restent utilisables isolément (tests, autres appelants) et ne changent pas."""
    window = active_window(session)
    if window is None:
        return (screen_key(session), ()), {}
    ids = []
    fields = {}
    for element in _walk_objects(window):
        eid = relative_id(_safe(element, "Id"))
        ids.append(eid)                              # comme screen_signature : pas de filtre sur eid
        etype = _safe(element, "Type")
        if etype in _EDITABLE_TYPES and eid:          # comme snapshot_fields : eid non vide requis
            fields[eid] = (etype, _field_value(element, etype))
    return (screen_key(session), tuple(sorted(ids))), fields


def process_poll(state, cur_fp, cur_snapshot, cur_okcd):
    """Machine à états du recorder (pure). Retourne ``(nouvel_état, [lignes émises])``.

    ``cur_fp`` est la signature d'écran courante (cf. `screen_signature`). Tant qu'elle
    ne change pas, on accumule l'état des champs et le dernier OK-code non vide. Au
    changement de signature (aller-retour), on émet le diff des champs depuis l'entrée
    sur l'écran + l'action de soumission."""
    if not state.get("started"):
        return ({"started": True, "baseline": cur_snapshot,
                 "last_snapshot": cur_snapshot, "last_fp": cur_fp,
                 "last_okcd": cur_okcd}, [])
    if cur_fp != state["last_fp"]:
        steps = diff_to_steps(state["baseline"], state["last_snapshot"])
        steps.append(submit_step(state["last_okcd"]))
        return ({"started": True, "baseline": cur_snapshot,
                 "last_snapshot": cur_snapshot, "last_fp": cur_fp,
                 "last_okcd": cur_okcd}, steps)
    new_state = dict(state)
    new_state["last_snapshot"] = cur_snapshot
    new_state["last_okcd"] = cur_okcd or state["last_okcd"]   # garde le dernier non vide
    return (new_state, [])


def default_record_path(now=None):
    """Chemin par défaut de l'enregistrement : ``captures/record_<horodatage>.robot``."""
    return _timestamped_path("record", "robot", now)


# --- Exports post-enregistrement : extraits dans recorder_exports.py ----------
#
# La logique pure texte -> texte (suite, resource-first, spec, ISTQB, rapport
# HTML) vit dans ``recorder_exports.py`` à côté de ce fichier ; tout est
# ré-exporté ici pour les consommateurs historiques (GUI, tests, suites).
# Ce module étant chargé par CHEMIN (Robot `Library`, spec_from_file_location
# des tests), son dossier n'est pas forcément sur sys.path : on l'y pose.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from recorder_exports import (  # noqa: E402
    DEFAULT_TEST_NAME as DEFAULT_TEST_NAME,
    _ISTQB_GENERIC_EXPECTED as _ISTQB_GENERIC_EXPECTED,
    _ISTQB_TABLE_EXPECTED as _ISTQB_TABLE_EXPECTED,
    _LOC_PREFIX as _LOC_PREFIX,
    _REPORT_CSS as _REPORT_CSS,
    _REPORT_MIMES as _REPORT_MIMES,
    _RESOURCE_WRAPPERS as _RESOURCE_WRAPPERS,
    _SCREENSHOT_COMMENT as _SCREENSHOT_COMMENT,
    _SECRET_ARG as _SECRET_ARG,
    _SUITE_SETTINGS as _SUITE_SETTINGS,
    _esc as _esc,
    _humanize_channel_step as _humanize_channel_step,
    _humanize_step as _humanize_step,
    _istqb_slug as _istqb_slug,
    _istqb_step as _istqb_step,
    _istqb_yaml_lines as _istqb_yaml_lines,
    _mask_secret_args as _mask_secret_args,
    _md_cell as _md_cell,
    _report_shots as _report_shots,
    _split_step as _split_step,
    _strip_md_code as _strip_md_code,
    _yq as _yq,
    build_record_header as build_record_header,
    locator_slug as locator_slug,
    md_code as md_code,
    parse_recorded_body as parse_recorded_body,
    replace_recorded_steps as replace_recorded_steps,
    report_screenshot_loader as report_screenshot_loader,
    rf_escape_value as rf_escape_value,
    rf_unescape_value as rf_unescape_value,
    steps_to_istqb as steps_to_istqb,
    steps_to_report as steps_to_report,
    steps_to_resource_first as steps_to_resource_first,
    steps_to_spec as steps_to_spec,
)


# --- Transpile VBS : consommer les enregistrements ALT+F12 de SAP GUI ---------
#
# Le « Script Recording and Playback » intégré à SAP GUI (ALT+F12) produit du
# VBScript (`session.findById("…").text = "…"`, `.press`, `.sendVKey 0`…) que
# les key users SAP pratiquent depuis toujours. `--transpile-vbs FILE` convertit
# ces enregistrements en steps SapEccLibrary via la MÊME machine à états que le
# record natif (`process_change` : fusion OK-code+Entrée, menus contextuels
# appariés, cellules de grille suivies) : les exports --suite /
# --export-resources / --export-spec s'appliquent ensuite normalement.

_VBS_CALL = re.compile(r'^\s*session\.findById\("([^"]+)"\)\.(\w+)(.*)$')

# Le VBS ne porte pas le type de contrôle : on l'infère du préfixe de l'id,
# suffisant pour les aiguillages de map_change_command (radio/checkbox/okcd…).
_VBS_TYPE_PREFIXES = (
    ("okcd", "GuiOkCodeField"), ("rad", "GuiRadioButton"), ("chk", "GuiCheckBox"),
    ("pwd", "GuiPasswordField"), ("cmb", "GuiComboBox"), ("tabp", "GuiTab"),
    ("btn", "GuiButton"), ("ctxt", "GuiCTextField"), ("txt", "GuiTextField"),
)


def _vbs_guess_type(eid):
    tail = (eid or "").rsplit("/", 1)[-1].lower()
    if "/menu" in (eid or ""):
        return "GuiMenu"
    for prefix, gui_type in _VBS_TYPE_PREFIXES:
        if tail.startswith(prefix):
            return gui_type
    return "GuiShell" if "shell" in tail else ""


def _vbs_literal(token):
    token = token.strip()
    if len(token) >= 2 and token.startswith('"') and token.endswith('"'):
        return token[1:-1].replace('""', '"')
    return token


def _split_vbs_args(argstr):
    """Coupe une liste d'arguments VBS sur les virgules HORS littéraux chaîne."""
    out, cur, in_str = [], "", False
    for ch in argstr:
        if ch == '"':
            in_str = not in_str
            cur += ch
        elif ch == "," and not in_str:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [a.strip() for a in out if a.strip()]


def decode_vbs_source(data, ansi_encoding=None):
    """Décode les octets d'un enregistrement VBS sans parier sur UN encodage.

    Les ``.vbs`` rencontrés en pratique : UTF-8 (avec ou sans BOM), UTF-16
    LE/BE avec BOM (Bloc-notes « Unicode », ``Out-File`` PowerShell 5.1), ou
    la page de code ANSI du poste (SAP GUI ALT+F12, éditeurs anciens : cp1252
    en Europe de l'Ouest). Forcer l'UTF-8 corrompait silencieusement les deux
    derniers cas : les octets NUL de l'UTF-16 étant du UTF-8 *valide*, la
    transpilation rendait 0 step sans la moindre exception.

    Ordre de décision : BOM explicite > présence d'octets NUL (UTF-16 sans
    BOM, endianness déduite de leur position) > essai UTF-8 strict > repli
    ANSI (``mbcs`` sous Windows, encodage préféré du système ailleurs).
    ``ansi_encoding`` force ce repli (tests, poste à page de code atypique).
    Les replis décodent en ``errors="replace"`` : la fonction n'échoue jamais,
    fidèle au contrat du transpileur : rien d'actionnable perdu en silence."""
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig", errors="replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace")   # le codec lit le BOM
    if b"\x00" in data:
        # Du VBScript ANSI/UTF-8 ne contient jamais d'octet NUL : c'est de
        # l'UTF-16 sans BOM. Sur du texte majoritairement ASCII, les NUL
        # occupent l'octet de poids fort : les positions impaires en LE.
        little = data[1::2].count(0) >= data[0::2].count(0)
        return data.decode("utf-16-le" if little else "utf-16-be",
                           errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        if ansi_encoding is None:
            ansi_encoding = ("mbcs" if sys.platform == "win32"
                             else locale.getpreferredencoding(False))
        return data.decode(ansi_encoding, errors="replace")


def transpile_vbs(text):
    """Transcrit un enregistrement VBS ALT+F12 en steps SapEccLibrary (liste de
    lignes RF). Le boilerplate (`If Not IsObject…`, `Set session = …`,
    commentaires) est ignoré ; les commandes sans keyword restent des
    commentaires ``# non mappé`` : rien d'actionnable n'est perdu."""
    state = initial_native_state()
    steps = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("'"):
            continue
        match = _VBS_CALL.match(line)
        if not match:
            continue
        eid = relative_id(match.group(1))
        member, rest = match.group(2), (match.group(3) or "").strip()
        if rest.startswith("="):
            parts = ["SP", member, _vbs_literal(rest[1:])]
        else:
            if rest.startswith("(") and rest.endswith(")"):
                rest = rest[1:-1]
            parts = ["M", member] + [_vbs_literal(a) for a in _split_vbs_args(rest)]
        state, lines = process_change(state, eid, _vbs_guess_type(eid), tuple(parts))
        steps.extend(lines)
    steps.extend(flush_native_state(state))
    return steps


# --- Replay : rejouer un enregistrement contre la session ouverte -------------
#
# Le « play » de l'esprit Selenium IDE, côté client lourd : `--replay FILE`
# relit un enregistrement (corps nu ou suite complète), rattache SapEccLibrary
# à la session SAP GUI déjà ouverte (`Attach To Open Session`) et exécute les
# steps un à un : arrêt au premier échec, step fautif nommé. La GUI l'expose
# par le bouton « Rejouer » du panneau de steps.

def replay_recorded_steps(steps, lib, writer=print):
    """Rejoue des steps (lignes RF) contre une bibliothèque déjà rattachée :
    keyword -> méthode (normalisation Robot), commentaires ignorés, keywords
    inconnus signalés mais non bloquants. Retourne
    ``(exécutés, ignorés, index d'échec ou None, message)``."""
    executed = 0
    skipped = 0
    for index, step in enumerate(steps):
        cells, _comment = _split_step(step)
        if not cells:
            continue                     # ligne de commentaire (screenshot, marqueur…)
        method = getattr(lib, cells[0].lower().replace(" ", "_"), None)
        if method is None:
            skipped += 1
            writer("  ? step %d ignoré (keyword hors bibliothèque) : %s"
                   % (index + 1, step))
            continue
        writer("  > %s" % step)
        try:
            # les valeurs sont échappées façon RF dans le fichier : l'inverse
            # exact avant l'appel (les ids SAP ne portent jamais de backslash)
            method(*[rf_unescape_value(c) for c in cells[1:]])
        except Exception as exc:
            return executed, skipped, index, "%s" % exc
        executed += 1
    return executed, skipped, None, ""


def _default_replay_lib():
    """SapEccLibrary rattachée à la session ouverte : import depuis ``src/`` du
    dépôt si présent (sinon l'environnement installé, cas du pack déployé).

    ``screenshots_on_error=False`` : la CLI n'a pas de log Robot où incruster
    une capture, et hors contexte RF le handler ``take_screenshot`` remplace
    l'erreur réelle du step par « Cannot access execution context » (constaté
    live 2026-07-21 : l'échec du replay devenait indiagnosticable)."""
    src = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
    if os.path.isdir(src) and src not in sys.path:
        sys.path.insert(0, src)
    from SapEccLibrary import SapEccLibrary
    lib = SapEccLibrary(screenshots_on_error=False)
    lib.attach_to_open_session()
    return lib


def run_replay(path, _lib_factory=None, _writer=print):
    """Point d'entrée de ``--replay`` : relit le fichier et rejoue. Retourne un
    code de sortie CLI (0 = tout rejoué)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        _writer("Erreur : %s" % exc)
        return 1
    _name, steps = parse_recorded_body(text)
    if not steps:
        _writer("Aucun step à rejouer dans %s" % path)
        return 1
    factory = _lib_factory or _default_replay_lib
    try:
        lib = factory()
    except Exception as exc:
        _writer("Erreur : impossible de rattacher SapEccLibrary (%s)" % exc)
        return 1
    _writer("Replay de %d step(s) depuis %s :" % (len(steps), path))
    executed, skipped, failed, message = replay_recorded_steps(steps, lib, writer=_writer)
    if failed is not None:
        _writer("ÉCHEC au step %d : %s" % (failed + 1, message))
        _writer("  %s" % steps[failed])
        return 1
    _writer("Replay OK : %d step(s) exécuté(s), %d ignoré(s)." % (executed, skipped))
    return 0


# --- Assertions à chaud (mode record) : Ctrl+Alt+A / Ctrl+Alt+V ---------------
#
# Un enregistrement sans assertion n'est qu'un script de navigation. Pendant le
# record (les deux moteurs), deux raccourcis GLOBAUX insèrent des vérifications
# dans le déroulé, sans quitter SAP GUI :
#   * Ctrl+Alt+A -> assertion de VALEUR sur l'élément focalisé
#     (``Element Value Should Be``, ou présence si l'élément n'a pas de texte ;
#     jamais la valeur d'un champ mot de passe) ;
#   * Ctrl+Alt+V -> assertion VISUELLE de l'écran (``Screen Should Match
#     Baseline`` : baseline créée au premier replay, cf. _perception.py).
# Détection par GetAsyncKeyState (pywin32, déjà requis) avec front montant :
# un appui = une assertion. Logique pure injectable pour les tests.

_HOTKEY_CODES = {
    # VK_CONTROL, VK_MENU (Alt), puis la lettre.
    "value": (0x11, 0x12, 0x41),    # Ctrl+Alt+A
    "visual": (0x11, 0x12, 0x56),   # Ctrl+Alt+V
}


def make_hotkey_poller(key_state_fn=None):
    """Retourne ``poll()`` -> ``'value'`` / ``'visual'`` / ``None`` (front
    montant : ne déclenche qu'à l'APPUI, pas tant que la combinaison reste
    tenue). Sans pywin32 (``key_state_fn`` absent), poller inerte."""
    if key_state_fn is None:
        if win32api is None:
            return lambda: None
        key_state_fn = win32api.GetAsyncKeyState
    held = {action: False for action in _HOTKEY_CODES}

    def poll():
        fired = None
        for action, codes in _HOTKEY_CODES.items():
            down = all(key_state_fn(code) & 0x8000 for code in codes)
            if down and not held[action] and fired is None:
                fired = action
            held[action] = down
        return fired
    return poll


def assertion_step_for_element(eid, etype, text):
    """Ligne d'assertion pour l'élément focalisé : valeur si un texte est
    lisible (jamais pour un mot de passe), présence sinon. ``None`` sans id.
    Texte échappé façon RF (un texte SAP peut porter runs d'espaces, ``#``…)."""
    if not eid:
        return None
    if etype == "GuiPasswordField" or not text:
        return "Element Should Be Present    %s" % eid
    return "Element Value Should Be    %s    %s" % (eid, rf_escape_value(text))


def visual_assertion_step(base_name, index):
    """Ligne d'assertion visuelle numérotée (baseline snapshot à committer)."""
    safe = re.sub(r"[^0-9A-Za-z_-]+", "_", base_name or "record").strip("_") or "record"
    return "Screen Should Match Baseline    %s_etape_%02d" % (safe, index)


def hotkey_assertion_lines(action, session, base_name, visual_counter):
    """Traduit un déclenchement de raccourci en lignes d'étape. Retourne
    ``(lignes, nouveau compteur visuel)`` ; jamais d'exception (COM défensif)."""
    if action == "visual":
        counter = visual_counter + 1
        return [visual_assertion_step(base_name, counter)], counter
    if action == "value":
        element = active_focus(session)
        if element is None:
            return [], visual_counter
        line = assertion_step_for_element(
            relative_id(_safe(element, "Id")), _safe(element, "Type"),
            _safe(element, "Text"))
        return ([line] if line else []), visual_counter
    return [], visual_counter


# --- Zones opaques (GuiShell/GuiChart) : suggestion de clic par offset --------

_OPAQUE_TYPES = ("GuiShell", "GuiChart")


def offset_suggestion(etype, eid, rect, x, y):
    """Pour un élément OPAQUE au scripting (intérieur d'un GuiShell, GuiChart),
    propose la ligne du repli coordonnées ``Click Element At Offset`` avec la
    position RELATIVE du curseur (pourcentages 0..1, 2 décimales) : le geste
    matériel documenté de ``_pointer.py``. ``None`` pour les types scriptables
    ou sans géométrie exploitable."""
    if etype not in _OPAQUE_TYPES or not eid or rect is None:
        return None
    if not rect_contains(rect, x, y):
        return None                     # curseur hors de l'élément (ex. FocusChanged clavier)
    left, top, width, height = rect
    x_pct = (x - left) / float(width)
    y_pct = (y - top) / float(height)
    return ("Click Element At Offset    %s    %.2f    %.2f"
            "    # zone opaque : geste matériel" % (eid, x_pct, y_pct))


# --- Mode record NATIF : événements Session.Record + Change --------------------
#
# L'API SAP GUI Scripting expose un mode Record natif (le mécanisme derrière
# ALT+F12) : ``GuiSession.Record = True`` fait émettre par SAP GUI lui-même,
# via l'événement ``Change(session, component, commandArray)``, la commande
# exacte exécutée : ``["SP", propriété, valeur]`` (set-property) ou
# ``["M", méthode, args...]`` (appel de méthode), juste avant chaque
# aller-retour serveur (doc officielle « SAP GUI Scripting API », GuiSession).
# Contrairement au diff de polling ci-dessus, il capte nativement les clics de
# boutons/toolbar, la grille ALV, les arbres, les onglets et menus, avec le
# bouton EXACT pressé (fini le ``Send Vkey 0`` par défaut).
#
# Limites officielles à connaître : le F4 devient modal et le drag & drop est
# désactivé pendant l'enregistrement ; et AUCUN événement n'est émis si le
# profil serveur ``sapgui/user_scripting_disable_recording`` est actif
# (``session.Info.ScriptingModeRecordingDisabled``), d'où le repli
# automatique sur le mode polling (``--engine auto``, défaut).
#
# La traduction événement -> keyword est isolée dans des fonctions pures
# (normalize_command / map_change_command / process_change), testables hors SAP.

# Propriétés « bruit de navigation » : elles n'ont pas d'effet métier propre et
# encombreraient le déroulé (position de curseur, scroll, cellule courante...).
_NOISE_PROPERTIES = frozenset((
    "caretposition", "currentcellrow", "currentcellcolumn", "firstvisiblerow",
    "verticalscrollposition", "horizontalscrollposition", "currentcell",
))

_TRUE_STRINGS = ("true", "1", "-1", "vrai", "x")

# Noms lisibles des vkeys courants (table officielle SAP GUI Scripting) : le
# déroulé enregistré dit « # F8 » au lieu de laisser deviner le code 8.
_VKEY_NAMES = {
    0: "Enter", 1: "F1", 2: "F2", 3: "F3", 4: "F4", 5: "F5", 6: "F6",
    7: "F7", 8: "F8", 9: "F9", 10: "F10", 11: "Ctrl+S", 12: "F12",
    82: "PageUp", 83: "PageDown",
}

# Résolveur DYNAMIQUE optionnel des noms de vkeys : l'API scripting les connaît
# déjà tous (``GuiSession.GetVKeyDescription``, usage observé chez RoboSAPiens,
# qui a remplacé sa table manuelle par cet appel). Branché par le moteur record
# natif quand une session live est là ; la table statique reste prioritaire
# (sorties stables, testables hors SAP), le résolveur couvre le reste
# (Shift+F5, Ctrl+F1…).
_VKEY_RESOLVER = {"fn": None}


def set_vkey_resolver(fn):
    """Branche (``fn = code -> description``) ou débranche (``None``) la
    résolution dynamique des noms de vkeys. Retourne le résolveur précédent,
    à restaurer en teardown, comme les réglages de timeout des bibliothèques."""
    previous = _VKEY_RESOLVER["fn"]
    _VKEY_RESOLVER["fn"] = fn
    return previous


def _vkey_comment(vkey):
    """Suffixe de commentaire `` # Enter``/`` # F8`` pour un code vkey connu
    (table statique d'abord, résolveur de session ensuite)."""
    try:
        code = int(str(vkey).strip())
    except (TypeError, ValueError):
        return ""
    name = _VKEY_NAMES.get(code)
    if name is None and _VKEY_RESOLVER["fn"] is not None:
        try:
            name = " ".join(str(_VKEY_RESOLVER["fn"](code) or "").split()) or None
        except Exception:                # COM en échec = pas de nom, jamais un crash
            name = None
    return ("    # %s" % name) if name else ""


def normalize_command(command):
    """Aplati un ``CommandArray`` COM en liste de chaînes ``[type, nom, args...]``.

    Le variant livré par l'événement Change peut arriver comme tableau plat
    (``('SP', 'text', 'SE16')``) ou enveloppé dans un tableau externe
    (``(('SP', 'text', 'SE16'),)``) selon le marshaling ; on déballe une
    éventuelle enveloppe à un seul élément puis on stringifie chaque partie."""
    if command is None:
        return []
    parts = list(command) if isinstance(command, (list, tuple)) else [command]
    while len(parts) == 1 and isinstance(parts[0], (list, tuple)):
        parts = list(parts[0])
    return [("" if p is None else str(p)) for p in parts]


def _is_true(value):
    return str(value).strip().lower() in _TRUE_STRINGS


def map_change_command(eid, etype, parts, context=None):
    """Traduit un événement Change (id relatif, type, commande normalisée) en ligne
    de keyword SapEccLibrary, ou ``None`` (bruit à ignorer), ou une ligne de
    commentaire ``# non mappé : ...`` si aucun keyword ne correspond (l'information
    n'est jamais perdue : le commentaire contient l'appel exact à rejouer).

    ``context`` (fourni par `process_change`) porte l'état inter-événements que
    certaines commandes de grille exigent : ``cell`` = {'row','col'} (dernières
    SP currentCellRow/Column vues sur cet élément), ``ctx_button`` = bouton d'un
    ``pressToolbarContextButton`` en attente de son ``selectContextMenuItem``."""
    context = context or {}
    if len(parts) < 2:
        return None
    kind, name = parts[0].upper(), parts[1]
    args = parts[2:]
    lname = name.lower()
    if kind == "SP":
        if lname == "selectedrows":
            rows = args[0] if args else ""
            if rows.isdigit():
                return "Select Table Row    %s    %s" % (eid, rows)
            return ("# grille %s : sélection de lignes '%s', une ligne simple = "
                    "Select Table Row    %s    <n>" % (eid, rows, eid))
        if lname in _NOISE_PROPERTIES:
            return None
        if lname == "text":
            if etype == "GuiPasswordField":
                # Jamais de mot de passe en clair dans un déroulé (l'API elle-même
                # ne l'enregistre pas : placeholder, à remplacer au replay).
                return "Input Password    %s    <password>" % eid
            # Valeur échappée façon RF (${...}, runs d'espaces, # de tête…) ;
            # vider un champ devient ${EMPTY} : un step rejouable, pas une
            # cellule manquante.
            return "Input Text    %s    %s" % (eid, rf_escape_value(args[0] if args else ""))
        if lname == "selected":
            checked = _is_true(args[0]) if args else True
            if etype == "GuiRadioButton":
                return ("Select Radio Button    %s" % eid) if checked else None
            if etype == "GuiCheckBox":
                return ("Select Checkbox    %s" if checked else "Unselect Checkbox    %s") % eid
        if lname == "key" and etype == "GuiComboBox":
            # La base ne sélectionne que par libellé ; on garde la clé exacte en
            # commentaire pour que l'utilisateur (ou l'agent) la convertisse.
            return ("# Combo par clé, remplacer par : Select From List By Label    %s"
                    "    <libellé de la clé '%s'>" % (eid, args[0] if args else ""))
    elif kind == "M":
        if lname in ("setfocus",):
            return None
        if lname == "press":
            return "Click Element    %s" % eid
        if lname == "select" and etype in ("GuiTab", "GuiMenu", "GuiRadioButton"):
            if etype == "GuiRadioButton":
                return "Select Radio Button    %s" % eid
            return "Click Element    %s" % eid          # click_element fait .select()
        if lname == "sendvkey":
            vkey = args[0] if args else "0"
            match = re.match(r"wnd\[(\d+)\]", eid or "")
            window = match.group(1) if match else "0"
            if window == "0":
                return "Send Vkey    %s%s" % (vkey, _vkey_comment(vkey))
            return "Send Vkey    %s    %s%s" % (vkey, window, _vkey_comment(vkey))
        if lname == "presstoolbarbutton" and args:
            return "Click Toolbar Button    %s    %s" % (eid, args[0])
        if lname == "selectcontextmenuitem" and args:
            button = context.get("ctx_button")
            if button:
                return "Select Context Menu Item    %s    %s    %s" % (eid, button, args[0])
            return ("# menu contextuel %s : fcode '%s' sans bouton apparié ; "
                    "Select Context Menu Item    %s    <bouton>    %s"
                    % (eid, args[0], eid, args[0]))
        if lname == "selectnode" and args:
            return "Select Node    %s    %s" % (eid, args[0])
        if lname == "expandnode" and args:
            # select_node(expand=True) sélectionne ET déplie : le replay fidèle.
            return "Select Node    %s    %s    True" % (eid, args[0])
        if lname in ("doubleclickcurrentcell", "clickcurrentcell"):
            cell = context.get("cell") or {}
            row, col = cell.get("row", "?"), cell.get("col", "?")
            action = "double-clic" if lname.startswith("double") else "clic"
            return ("# grille %s : %s cellule ligne %s, colonne %s, lecture : "
                    "Get Cell Value    %s    %s    %s" % (eid, action, row, col,
                                                          eid, row, col))
    # Méthode/propriété sans keyword direct (arbres : doubleClickNode... ;
    # graphes...) : trace exacte, replayable à la main.
    return "# non mappé : %s  %s  %s %s(%s)" % (eid, etype, kind, name, ", ".join(args))


def initial_native_state():
    """État initial de `process_change` (machine à états pure du record natif)."""
    return {"pending_tcode": None}


def _is_enter_on_main_window(line):
    """Vrai si ``line`` est un ``Send Vkey 0`` sur la fenêtre principale (le
    commentaire lisible `` # Enter`` éventuel est ignoré, une fenêtre explicite
    non-0 ne compte pas)."""
    cells = [c for c in (line or "").split("    ") if c and not c.startswith("#")]
    return cells == ["Send Vkey", "0"]


def process_change(state, eid, etype, command):
    """Machine à états du record natif (pure). Retourne ``(nouvel_état, [lignes])``.

    Presque tout est du 1-événement -> 1-ligne via `map_change_command` ; les
    subtilités inter-événements :

    * OK-code : la saisie d'un tcode (SP text sur ``.../okcd``) suivie d'Entrée
      (M sendVKey 0) doit devenir UNE ligne ``Run Transaction`` (le keyword
      envoie lui-même le vkey 0 : émettre les deux rejouerait Entrée deux
      fois). Un OK-code suivi d'autre chose est émis comme ``Input Text``.
    * Grilles : les SP ``currentCellRow``/``currentCellColumn`` (bruit seuls)
      sont MÉMORISÉS par élément : un ``doubleClickCurrentCell`` ultérieur
      connaît ainsi sa cellule ; ``pressToolbarContextButton`` est retenu
      jusqu'au ``selectContextMenuItem`` qui suit -> UNE ligne
      ``Select Context Menu Item`` (le keyword de la base fait les deux)."""
    parts = normalize_command(command)
    if len(parts) >= 2 and parts[0].upper() == "SP" and parts[1].lower() == "text" \
            and (etype == "GuiOkCodeField" or (eid or "").endswith("/okcd")):
        return dict(state, pending_tcode=parts[2] if len(parts) > 2 else ""), []
    if len(parts) >= 3 and parts[0].upper() == "SP" \
            and parts[1].lower() in ("currentcellrow", "currentcellcolumn"):
        cells = dict(state.get("cells") or {})
        cell = dict(cells.get(eid) or {})
        cell["row" if parts[1].lower() == "currentcellrow" else "col"] = parts[2]
        cells[eid] = cell
        return dict(state, cells=cells), []
    if len(parts) >= 3 and parts[0].upper() == "M" \
            and parts[1].lower() == "presstoolbarcontextbutton":
        return dict(state, ctx_button=(eid, parts[2])), []
    ctx = {"cell": (state.get("cells") or {}).get(eid)}
    pending_ctx = state.get("ctx_button")
    if pending_ctx and pending_ctx[0] == eid:
        ctx["ctx_button"] = pending_ctx[1]
    line = map_change_command(eid, etype, parts, context=ctx)
    lines = []
    pending = state.get("pending_tcode")
    if pending is not None:
        if _is_enter_on_main_window(line):
            return dict(state, pending_tcode=None), ["Run Transaction    %s" % pending]
        lines.append("Input Text    wnd[0]/tbar[0]/okcd    %s" % pending)
    if line:
        lines.append(line)
    return dict(state, pending_tcode=None, ctx_button=None), lines


def flush_native_state(state):
    """Lignes finales à émettre à l'arrêt de l'enregistrement (OK-code en attente
    dont l'Entrée n'a pas encore été observée : on le rejoue en Run Transaction)."""
    pending = state.get("pending_tcode")
    return ["Run Transaction    %s" % pending] if pending else []


def recording_disabled(session):
    """Vrai si le profil serveur interdit les événements d'enregistrement
    (``sapgui/user_scripting_disable_recording`` ->
    ``session.Info.ScriptingModeRecordingDisabled``) : le mode natif ne recevra
    jamais de Change, il faut replier sur le polling."""
    try:
        return bool(session.Info.ScriptingModeRecordingDisabled)
    except (AttributeError, com_error):
        return False


# --- Mode sémantique (--semantic) : keywords « humains » au lieu d'ids -------
#
# Idée portée de RoboSAPiens (imbus, Apache-2.0, NOTICE) : au moment de
# l'événement, l'écran est encore là : on peut calculer le LIBELLÉ qui désigne
# l'élément (géométrie label -> champ) et émettre `Fill Field By Label   Table
# Name   T000` au lieu de l'id technique, directement au niveau d'abstraction
# de resources/ (convention n°1). Différence assumée : le libellé n'est retenu
# que s'il RE-RÉSOUT de façon unique vers le même élément
# (sapfx_common.semantic.describe_element) ; sinon la ligne technique est
# gardée telle quelle, jamais de perte d'information. Requiert le paquet
# sapfx_common (installé avec les wheels du pack / present dans src/ au repo) ;
# sans lui, --semantic se désactive avec un avertissement.

def _elem_int(node, attr):
    try:
        return int(getattr(node, attr))
    except (AttributeError, com_error, TypeError, ValueError):
        return None


def screen_elements(session):
    """Contrôles de la fenêtre active en ``ScreenElement`` (géométrie incluse),
    ids relatifs : le socle du mode ``--semantic``. Chemin rapide
    ``GetObjectTree`` (un appel COM), repli marche COM. ``[]`` si sapfx_common
    n'est pas importable ou la fenêtre indisponible."""
    try:
        from sapfx_common.object_tree import (OBJECT_TREE_PROPERTIES,
                                              ScreenElement, flatten_object_tree)
    except ImportError:
        return []
    window = active_window(session)
    if window is None:
        return []
    try:
        payload = session.GetObjectTree(_safe(window, "Id"),
                                        list(OBJECT_TREE_PROPERTIES))
        flat = flatten_object_tree(payload)
    except Exception:
        flat = []
    if flat:
        import dataclasses
        return [dataclasses.replace(el, id=relative_id(el.id))
                for el in flat if relative_id(el.id)]
    out = []
    for element in _walk_objects(window):
        rid = relative_id(_safe(element, "Id"))
        if not rid:
            continue
        out.append(ScreenElement(
            id=rid, type=_safe(element, "Type"),
            text=_safe(element, "Text") or "",
            tooltip=_safe(element, "Tooltip") or "",
            changeable=bool(_safe(element, "Changeable")),
            left=_elem_int(element, "ScreenLeft"),
            top=_elem_int(element, "ScreenTop"),
            width=_elem_int(element, "Width"),
            height=_elem_int(element, "Height")))
    return out


def semanticize_step(line, elements):
    """Réécrit une ligne technique en keyword « humain » quand un libellé
    re-résout de façon unique vers le même élément (``describe_element``) ;
    l'id technique reste en commentaire de fin de ligne (traçabilité +
    diagnostic). Ligne rendue inchangée sinon : jamais de perte d'information.

    Pur (aucun COM) : ``elements`` est l'instantané ``screen_elements`` pris au
    moment de l'événement, quand l'écran d'origine est encore affiché."""
    if not elements:
        return line
    try:
        from sapfx_common.semantic import describe_element
    except ImportError:
        return line
    cells = line.split("    ")
    keyword = cells[0]
    if keyword == "Input Text" and len(cells) >= 3 and not cells[1].endswith("/okcd"):
        label = describe_element(elements, cells[1])
        if label:
            return "Fill Field By Label    %s    %s    # id: %s" % (
                label, "    ".join(cells[2:]), cells[1])
    elif keyword == "Click Element" and len(cells) >= 2:
        label = describe_element(elements, cells[1])
        if label:
            return "Click Button By Label    %s    # id: %s" % (label, cells[1])
    elif keyword in ("Select Checkbox", "Unselect Checkbox",
                     "Select Radio Button") and len(cells) >= 2:
        label = describe_element(elements, cells[1])
        if label:
            return "%s    # libellé : %s" % (line, label)
    return line


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


# IID du dispinterface ``ISapSessionEvents`` et dispids de ses événements,
# contrat COM de sapfewse (stable par définition : un IID ne change jamais),
# vérifiés contre la typelib live de SAP GUI 8.00.
SESSION_EVENTS_IID = "{67A71FA4-9381-4061-B3BB-74A545C75874}"
_SESSION_EVENT_DISPIDS = {1280: "OnChange", 1281: "OnHit", 1286: "OnFocusChanged"}


class SessionEventConnection:
    """Poignée d'abonnement aux événements de session : ``close()`` désabonne
    (idempotent, jamais d'exception, utilisé dans les teardowns)."""

    def __init__(self, connection_point, cookie):
        self._cp = connection_point
        self._cookie = cookie

    def close(self):
        if self._cp is not None:
            try:
                self._cp.Unadvise(self._cookie)
            except Exception:
                pass
            self._cp = None


def advise_session_events(session, on_change=None, on_hit=None,
                          on_focus_changed=None):
    """Branche des handlers Python sur les événements COM de GuiSession,
    SANS makepy. Retourne une :class:`SessionEventConnection` ; lève si la
    liaison échoue (l'appelant replie alors sur le polling).

    ``DispatchWithEvents`` est inutilisable sur la typelib sapfewse : sa
    génération makepy plante (AssertionError dans genpy, pywin32 issue #2433,
    reproduit sur pywin32 311 / SAP GUI 8.00). On se connecte donc au point de
    connexion manuellement, avec le hack canonique de la démo officielle
    ``win32com/demos/connect.py`` : le sink répond au QueryInterface pour l'IID
    du dispinterface en retournant sa propre passerelle IDispatch (légal : un
    dispinterface EST un IDispatch au niveau vtable). Validé live contre un
    A4H : les actions scriptées comme manuelles émettent bien les Change.

    Handlers (tous optionnels) : ``on_change(component, command_array)``,
    ``on_hit(component)``, ``on_focus_changed(component)`` : les composants sont
    livrés déjà enveloppés (attributs ``.Id``/``.Type`` accessibles). Un handler
    ne doit jamais déclencher d'aller-retour serveur (boucle infinie, doc
    officielle) ; toute exception y est étouffée (le pont COM ne doit pas casser)."""
    import pywintypes
    import win32com.server.util
    from win32com.server.policy import EventHandlerPolicy

    events_iid = pywintypes.IID(SESSION_EVENTS_IID)

    def _wrap_component(raw):
        try:
            return win32com.client.Dispatch(raw)
        except Exception:
            return raw               # déjà enveloppé (EventHandlerPolicy) ou None

    class _Sink:
        _public_methods_ = []
        _dispid_to_func_ = dict(_SESSION_EVENT_DISPIDS)

        def _query_interface_(self, iid):
            if iid == events_iid:
                return win32com.server.util.wrap(self, usePolicy=EventHandlerPolicy)

        # Signatures officielles : Change(session, component, commandArray),
        # Hit(session, component, innerObject), FocusChanged(session, component).
        # On indexe depuis la FIN (le marshaling peut omettre la session).
        def OnChange(self, *args):
            try:
                if on_change is not None and len(args) >= 2:
                    on_change(_wrap_component(args[-2]), args[-1])
            except Exception:
                pass

        def OnHit(self, *args):
            try:
                if on_hit is not None and len(args) >= 2:
                    on_hit(_wrap_component(args[-2]))
            except Exception:
                pass

        def OnFocusChanged(self, *args):
            try:
                if on_focus_changed is not None and args:
                    on_focus_changed(_wrap_component(args[-1]))
            except Exception:
                pass

    punk = win32com.server.util.wrap(_Sink(), usePolicy=EventHandlerPolicy)
    container = session._oleobj_.QueryInterface(
        pythoncom.IID_IConnectionPointContainer)
    connection_point = container.FindConnectionPoint(events_iid)
    return SessionEventConnection(connection_point, connection_point.Advise(punk))


def record_loop_native(engine, out_path, poll_seconds=0.1, semantic=False,
                       suite=False, _writer=print, _max_iterations=None,
                       _advise=None, _pump=None, _sleep=time.sleep,
                       _elements_fn=None, _key_state_fn=None):
    """Mode enregistreur NATIF : transcrit les événements Change en keywords.

    ``semantic=True`` (``--semantic``) : chaque ligne est réécrite en keyword
    « humain » (`Fill Field By Label`, `Click Button By Label`) quand le
    libellé calculé au moment de l'événement re-résout de façon unique vers le
    même élément : l'id technique reste en commentaire (voir
    `semanticize_step`). Le déroulé émis parle alors le langage de
    ``resources/`` (convention n°1) au lieu d'ids à retravailler.

    Retourne le nombre d'étapes écrites, ou ``None`` si le mode natif est
    indisponible (événements interdits par le profil serveur, liaison COM aux
    événements impossible) : l'appelant replie alors sur `record_loop` (polling).
    ``_advise``/``_pump``/``_max_iterations``/``_sleep``/``_elements_fn`` sont
    des points d'injection pour les tests hors SAP."""
    session = first_session(engine)
    if session is None:
        _writer("Aucune session SAP ouverte.")
        return 0
    if recording_disabled(session):
        _writer("Événements d'enregistrement désactivés par le serveur "
                "(sapgui/user_scripting_disable_recording) : repli sur le polling.")
        return None
    if _advise is None:
        if win32com is None:
            return None
        _advise = advise_session_events
    if _pump is None:
        _pump = pythoncom.PumpWaitingMessages

    counters = {"steps": 0, "visual": 0}
    state = {"st": initial_native_state()}
    fh = open_record_file(out_path, suite=suite)

    def emit(line):
        text = "    " + line
        _writer(text)
        fh.write(text + "\n")
        fh.flush()
        counters["steps"] += 1

    elements_fn = _elements_fn or screen_elements

    def on_change(component, command):
        eid = relative_id(_safe(component, "Id"))
        etype = _safe(component, "Type")
        state["st"], lines = process_change(state["st"], eid, etype, command)
        if lines and semantic:
            # l'écran d'origine est encore affiché au moment de l'événement :
            # c'est LE moment où le libellé de l'élément est calculable.
            elements = elements_fn(session)
            lines = [semanticize_step(line, elements) for line in lines]
        for line in lines:
            emit(line)

    try:
        connection = _advise(session, on_change=on_change)
    except Exception as exc:
        fh.close()
        _writer("Liaison aux événements COM impossible (%s) : repli sur le polling." % exc)
        return None

    try:
        session.Record = True
    except (AttributeError, com_error) as exc:
        connection.close()
        fh.close()
        _writer("Impossible d'activer Session.Record (%s) : repli sur le polling." % exc)
        return None

    _writer("Mode record NATIF : effectue tes actions dans SAP GUI ; chaque commande "
            "est transcrite à l'aller-retour serveur.")
    _writer("Assertions : Ctrl+Alt+A = valeur du champ focalisé, "
            "Ctrl+Alt+V = empreinte visuelle de l'écran.")
    _writer("Séquence -> %s   (Ctrl+C pour arrêter)\n" % out_path)
    # Noms de vkeys au-delà de la table statique : l'API de la session les
    # connaît tous (GetVKeyDescription) : branché le temps de l'enregistrement.
    previous_resolver = set_vkey_resolver(
        lambda code: session.GetVKeyDescription(code))
    hotkeys = make_hotkey_poller(_key_state_fn)
    assert_base = os.path.splitext(os.path.basename(out_path))[0]
    iterations = 0
    try:
        while _max_iterations is None or iterations < _max_iterations:
            iterations += 1
            _pump()                     # boucle STA : livre les événements en attente
            action = hotkeys()
            if action:
                lines, counters["visual"] = hotkey_assertion_lines(
                    action, session, assert_base, counters["visual"])
                for line in lines:
                    emit(line)
            _sleep(poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        for line in flush_native_state(state["st"]):
            emit(line)
        set_vkey_resolver(previous_resolver)
        try:
            session.Record = False
        except (AttributeError, com_error):
            pass
        connection.close()
        fh.close()
        _writer("\nArrêt : %s étape(s) enregistrée(s) dans %s"
                % (counters["steps"], out_path))
    return counters["steps"]


def open_record_file(out_path, suite=False):
    """Ouvre le fichier de sortie du record avec l'en-tête partagé par les deux
    moteurs (polling et natif) : corps ``*** Test Cases ***`` nu, ou suite
    ``.robot`` complète et rejouable avec ``suite=True`` (``--suite``)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fh = open(out_path, "w", encoding="utf-8")
    fh.write(build_record_header(out_path, suite=suite))
    fh.flush()
    return fh


# --- Mode capture NATIF : hit-test (elementVisualizationMode + événement Hit) --
#
# L'API expose aussi un « hit test mode » : ``session.elementVisualizationMode =
# True`` fait surligner par SAP GUI le contrôle sous le curseur et émet un
# événement ``Hit(session, component, innerObject)`` quand l'utilisateur CLIQUE
# un élément : le vrai clic-à-capturer officiel, supérieur au polling du focus
# (il voit aussi les éléments non focusables : labels, cellules, toolbars).
# On écoute aussi ``FocusChanged`` en complément (navigation clavier).

def capture_loop_native(engine, out_path, poll_seconds=0.1, filter_text=None,
                        _writer=print, _max_iterations=None,
                        _advise=None, _pump=None, _sleep=time.sleep,
                        _cursor_fn=None):
    """Mode capture NATIF : enregistre chaque élément cliqué (Hit) ou focalisé
    (FocusChanged) via les événements de l'API, sans polling.

    Retourne le nombre de captures, ou ``None`` si le mode natif est indisponible
    (l'appelant replie sur `capture_loop`)."""
    session = first_session(engine)
    if session is None:
        _writer("Aucune session SAP ouverte.")
        return 0
    if recording_disabled(session):
        _writer("Événements désactivés par le serveur : repli sur le polling du focus.")
        return None
    if _advise is None:
        if win32com is None:
            return None
        _advise = advise_session_events
    if _pump is None:
        _pump = pythoncom.PumpWaitingMessages

    seen = {"last": None, "count": 0}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fh = open(out_path, "w", encoding="utf-8")
    fh.write("# Captures SAP GUI Spy (hit-test natif) : %s\n\n" % out_path)
    fh.flush()

    cursor_fn = _cursor_fn
    if cursor_fn is None and win32api is not None:
        cursor_fn = win32api.GetCursorPos

    def on_component(component):
        eid = relative_id(_safe(component, "Id"))
        if not eid or eid == seen["last"]:
            return
        seen["last"] = eid
        etype = _safe(component, "Type")
        if not _matches_filter(filter_text, eid, etype):
            return
        record = {"id": eid, "type": etype, "text": _safe(component, "Text")}
        block = format_capture_block(record)
        if cursor_fn is not None:
            # Zone opaque cliquée (Hit) : propose aussi le repli coordonnées ;
            # la position du curseur AU CLIC donne l'offset relatif exact.
            try:
                x, y = cursor_fn()
                offset = offset_suggestion(etype, eid, element_rect(component), x, y)
            except Exception:
                offset = None
            if offset:
                block += "\n    " + offset
        seen["count"] += 1
        _writer(block)
        fh.write(block + "\n\n")
        fh.flush()

    try:
        connection = _advise(session, on_hit=on_component,
                             on_focus_changed=on_component)
    except Exception as exc:
        fh.close()
        _writer("Liaison aux événements COM impossible (%s) : repli sur le polling." % exc)
        return None

    hit_mode = True
    try:
        session.elementVisualizationMode = True
    except (AttributeError, com_error):
        hit_mode = False          # FocusChanged seul reste utile (pas bloquant)

    _writer("Mode capture NATIF : %s dans SAP GUI."
            % ("clique un élément (surligné par SAP GUI) ou tabule"
               if hit_mode else "tabule sur les champs (hit-test indisponible)"))
    _writer("Chaque élément est enregistré -> %s   (Ctrl+C pour arrêter)\n" % out_path)
    iterations = 0
    try:
        while _max_iterations is None or iterations < _max_iterations:
            iterations += 1
            _pump()
            _sleep(poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        if hit_mode:
            try:
                session.elementVisualizationMode = False
            except (AttributeError, com_error):
                pass
        connection.close()
        fh.close()
        _writer("\nArrêt : %s élément(s) capturé(s) dans %s" % (seen["count"], out_path))
    return seen["count"]


def record_loop(engine, out_path, poll_seconds=0.4, screenshot_dir=None,
                suite=False, _max_iterations=None, _writer=print,
                _screenshot_fn=None, _key_state_fn=None):
    """Mode enregistreur : transcrit les manipulations en séquence de keywords.

    Sonde l'écran et l'état des champs (``scan_active_window``, un seul parcours
    COM par cycle) ; à chaque aller-retour serveur, écrit les Input.../Select...
    puis l'action de soumission, formant un corps de test ``*** Test Cases ***``
    rejouable.

    ``screenshot_dir``, si fourni, active une capture d'écran best-effort de
    l'écran d'arrivée à chaque aller-retour détecté (référencée par un
    commentaire ``# screenshot: <fichier>`` dans le fichier de sortie), utile
    pour diagnostiquer visuellement un replay qui diverge plus tard. Une
    capture échouée (API/version SAP GUI, bureau verrouillé...) est
    silencieusement ignorée : n'interrompt jamais l'enregistrement.

    ``_max_iterations``/``_writer``/``_screenshot_fn`` sont des points
    d'injection pour les tests."""
    session = first_session(engine)
    if session is None:
        _writer("Aucune session SAP ouverte.")
        return 0
    if screenshot_dir:
        os.makedirs(screenshot_dir, exist_ok=True)
    screenshot_fn = _screenshot_fn or capture_rect_to_bmp
    fh = open_record_file(out_path, suite=suite)
    _writer("Mode record : effectue tes actions dans SAP GUI ; chaque aller-retour est transcrit.")
    _writer("Assertions : Ctrl+Alt+A = valeur du champ focalisé, "
            "Ctrl+Alt+V = empreinte visuelle de l'écran.")
    _writer("Séquence -> %s   (Ctrl+C pour arrêter)\n" % out_path)
    hotkeys = make_hotkey_poller(_key_state_fn)
    assert_base = os.path.splitext(os.path.basename(out_path))[0]
    visual_count = 0
    state = {"started": False}
    count = 0
    shot_count = 0
    iterations = 0
    try:
        while _max_iterations is None or iterations < _max_iterations:
            iterations += 1
            sig, fields = scan_active_window(session)
            state, steps = process_poll(state, sig, fields, okcode_value(session))
            if steps and screenshot_dir:
                shot_count += 1
                base = os.path.join(screenshot_dir, "step_%03d" % shot_count)
                shot_path = None
                if _screenshot_fn is None:
                    # voie API d'abord (HardCopyToMemory : fenêtre fidèle même
                    # recouverte) ; GDI en repli seulement.
                    shot_path = hardcopy_screenshot(session, base)
                if shot_path is None:
                    window = active_window(session)
                    rect = element_rect(window) if window is not None else None
                    if rect is not None and screenshot_fn(rect, base + ".bmp"):
                        shot_path = base + ".bmp"
                if shot_path:
                    line = "    # screenshot: %s" % shot_path
                    _writer(line)
                    fh.write(line + "\n")
            action = hotkeys()
            if action:
                lines, visual_count = hotkey_assertion_lines(
                    action, session, assert_base, visual_count)
                steps = list(steps) + lines
            for step in steps:
                line = "    " + step
                _writer(line)
                fh.write(line + "\n")
                fh.flush()
                count += 1
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        _writer("\nArrêt : %s étape(s) enregistrée(s) dans %s" % (count, out_path))
    finally:
        fh.close()
    return count


def run_record_exports(out_path, export_resources=False, export_spec=False,
                       export_report=False, export_istqb=False, _writer=print):
    """Post-traitement d'un enregistrement (``--export-resources`` /
    ``--export-spec`` / ``--export-report`` / ``--export-istqb``) : relit le
    fichier de sortie et écrit les artefacts dérivés À CÔTÉ : l'enregistrement
    brut n'est jamais modifié."""
    if not (export_resources or export_spec or export_report or export_istqb):
        return
    try:
        with open(out_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        _writer("Exports impossibles (%s)" % exc)
        return
    test_name, steps = parse_recorded_body(text)
    base, _ext = os.path.splitext(out_path)
    if export_resources:
        resource_file = os.path.basename(base) + "_keywords.resource"
        resource_text, suite_text = steps_to_resource_first(
            steps, test_name, resource_file)
        resource_path = base + "_keywords.resource"
        suite_path = base + "_resource_first.robot"
        with open(resource_path, "w", encoding="utf-8") as fh:
            fh.write(resource_text)
        with open(suite_path, "w", encoding="utf-8") as fh:
            fh.write(suite_text)
        _writer("Export resource-first : %s + %s" % (resource_path, suite_path))
    if export_spec:
        spec_path = base + ".spec.md"
        with open(spec_path, "w", encoding="utf-8") as fh:
            fh.write(steps_to_spec(steps, test_name))
        _writer("Export spec : %s" % spec_path)
    if export_report:
        report_path = base + "_report.html"
        loader = report_screenshot_loader(os.path.dirname(os.path.abspath(out_path)))
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(steps_to_report(steps, test_name,
                                     source=os.path.basename(out_path),
                                     screenshot_loader=loader))
        _writer("Export rapport HTML : %s" % report_path)
    if export_istqb:
        istqb_path = base + ".istqb.md"
        with open(istqb_path, "w", encoding="utf-8") as fh:
            fh.write(steps_to_istqb(steps, test_name,
                                    source=os.path.basename(out_path)))
        _writer("Export plan ISTQB : %s" % istqb_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Dump / surligne / capture / enregistre l'arbre d'objets SAP GUI en direct.")
    parser.add_argument("--json", metavar="FILE", nargs="?", const="", default=None,
                        help="écrit le dump JSON (sans valeur -> captures/dump_<horodatage>.json ; "
                             "chemin relatif -> sous captures/ ; chemin absolu -> tel quel)")
    parser.add_argument("--filter", metavar="TEXT",
                        help="ne retient que les éléments dont l'id ou le type contient TEXT "
                             "(insensible à la casse), s'applique au dump, à --capture et à --hover")
    # Modes mutuellement exclusifs : combiner --capture/--hover/--record/--highlight
    # n'a pas de sens (chacun boucle ou quitte immédiatement) ; sans ce groupe, un
    # tel mélange était honoré silencieusement par ordre de priorité fixe dans
    # main() ci-dessous, sans avertir l'utilisateur.
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--highlight", metavar="ID",
                            help="encadre l'élément ID en rouge à l'écran (Visualize) puis quitte")
    mode_group.add_argument("--capture", action="store_true",
                            help="mode interactif : enregistre chaque élément focalisé (Ctrl+C pour arrêter)")
    mode_group.add_argument("--hover", action="store_true",
                            help="mode survol : encadre le contrôle SOUS LE CURSEUR en continu "
                                 "(avec --out, enregistre aussi ; Ctrl+C pour arrêter)")
    mode_group.add_argument("--record", action="store_true",
                            help="mode enregistreur : transcrit tes manipulations en une séquence de "
                                 "keywords rejouable (diff par aller-retour ; Ctrl+C pour arrêter)")
    mode_group.add_argument("--replay", metavar="FILE",
                            help="rejoue un enregistrement (corps ou suite) contre la session SAP GUI "
                                 "déjà ouverte (Attach To Open Session), arrêt au premier échec, "
                                 "step fautif nommé")
    mode_group.add_argument("--transpile-vbs", metavar="FILE",
                            help="convertit un enregistrement VBS du recorder ALT+F12 intégré à "
                                 "SAP GUI en steps SapEccLibrary (mêmes fusions que le moteur "
                                 "natif ; --suite/--export-resources/--export-spec s'appliquent) ; "
                                 "ne requiert AUCUNE session SAP")
    parser.add_argument("--out", metavar="FILE",
                        help="destination des captures (défaut : captures/capture_<horodatage>.txt ; "
                             "chemin relatif -> sous captures/ ; chemin absolu -> tel quel)")
    parser.add_argument("--engine", choices=("auto", "native", "poll"), default="auto",
                        help="moteur de --record/--capture : 'native' = événements de l'API "
                             "(Session.Record + Change ; hit-test pour --capture), capte boutons, "
                             "grilles, arbres ; 'poll' = sondage (diff d'écran / focus) ; "
                             "'auto' (défaut) essaie native puis replie sur poll")
    parser.add_argument("--no-highlight", action="store_true",
                        help="en mode capture, ne pas surligner les éléments enregistrés")
    parser.add_argument("--screenshots", action="store_true",
                        help="en mode record, capture (best-effort ; HardCopyToMemory, repli "
                             "bitmap GDI) l'écran d'arrivée de chaque aller-retour, sous "
                             "<out>_shots/ ; sans effet hors --record")
    parser.add_argument("--semantic", action="store_true",
                        help="en mode record NATIF, émet des keywords « humains » (Fill Field "
                             "By Label, Click Button By Label ; libellé vérifié re-résolvant "
                             "vers le même élément, id technique en commentaire) au lieu des "
                             "ids ; requiert le paquet sapfx_common ; sans effet en polling")
    # Forme du fichier d'enregistrement : depuis 2026-08-05 le DÉFAUT est la
    # suite complète (Settings + Library SapEccLibrary + Suite Setup Attach To
    # Open Session) : un fichier .robot produit doit se lancer tel quel (un
    # corps nu échouait en « keyword introuvable », constaté au test live).
    shape_group = parser.add_mutually_exclusive_group()
    shape_group.add_argument("--suite", action="store_true",
                             help="(défaut depuis 2026-08-05) en mode record, écrit un fichier "
                                  ".robot COMPLET et rejouable (Settings + Library + Suite Setup "
                                  "Attach To Open Session) ; drapeau conservé pour compatibilité")
    shape_group.add_argument("--body-only", action="store_true",
                             help="en mode record, n'écrit que le corps *** Test Cases *** "
                                  "(l'ancienne forme fragment, à coller dans une suite existante ; "
                                  "sans Library, ce fichier ne se lance pas tel quel)")
    parser.add_argument("--export-resources", action="store_true",
                        help="après l'enregistrement, génère la paire resource-first : "
                             "<out>_keywords.resource (variables ${LOC_…} + keywords métier) "
                             "et <out>_resource_first.robot (suite sans aucun id brut, "
                             "convention n°1) ; l'enregistrement brut reste intact")
    parser.add_argument("--export-spec", action="store_true",
                        help="après l'enregistrement, génère aussi <out>.spec.md : un plan "
                             "Markdown au format specs/ (étapes en langage métier, ids en "
                             "notes) : l'entrée du cycle sap-planner/sap-generator")
    parser.add_argument("--export-report", action="store_true",
                        help="après l'enregistrement, génère aussi <out>_report.html : un "
                             "rapport HTML auto-contenu documentant le déroulé (phrases "
                             "métier + lignes exactes + captures inline si --screenshots) "
                             ": documentation, pas un test")
    parser.add_argument("--export-istqb", action="store_true",
                        help="après l'enregistrement, génère aussi <out>.istqb.md : un "
                             "plan de test + cas de test ISTQB (tableau Action/Données/"
                             "Résultat attendu + bloc replay YAML aux actions normalisées, "
                             "rejouable par une IA quel que soit le framework)")
    args = parser.parse_args(argv)

    def _resolved(path, factory):
        """resolve_save_path, mais imprime une erreur conviviale plutôt que de
        laisser remonter un ValueError brut jusqu'à l'utilisateur de la CLI."""
        try:
            return resolve_save_path(path, factory)
        except ValueError as exc:
            print("Erreur : %s" % exc, file=sys.stderr)
            return None

    # Forme effective du fichier : suite complète par défaut (--body-only =
    # l'ancien fragment ; --suite reste accepté, redondant depuis 2026-08-05).
    suite_mode = not args.body_only

    # --transpile-vbs et --replay ne passent pas par get_scripting_engine :
    # le premier n'a besoin d'AUCUNE session SAP, le second se rattache lui-même.
    if args.transpile_vbs:
        out_path = _resolved(args.out, default_record_path)
        if out_path is None:
            return 1
        try:
            with open(args.transpile_vbs, "rb") as fh:
                steps = transpile_vbs(decode_vbs_source(fh.read()))
        except OSError as exc:
            print("Erreur : %s" % exc, file=sys.stderr)
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(build_record_header(out_path, suite=suite_mode))
            for step in steps:
                fh.write("    " + step + "\n")
        print("Transpilé %d step(s) depuis %s -> %s"
              % (len(steps), args.transpile_vbs, out_path))
        run_record_exports(out_path, export_resources=args.export_resources,
                           export_spec=args.export_spec,
                           export_report=args.export_report,
                           export_istqb=args.export_istqb)
        return 0

    if args.replay:
        return run_replay(args.replay)

    try:
        engine = get_scripting_engine()
    except RuntimeError as exc:
        print("Erreur : %s" % exc, file=sys.stderr)
        return 1

    if args.highlight:
        if highlight(engine, args.highlight):
            print("Surligné : %s" % args.highlight)
            return 0
        print("Erreur : élément introuvable -> %s" % args.highlight, file=sys.stderr)
        return 1

    if args.capture:
        out_path = _resolved(args.out, default_capture_path)
        if out_path is None:
            return 1
        captured = None
        if args.engine in ("auto", "native"):
            try:
                captured = capture_loop_native(engine, out_path, filter_text=args.filter)
            except KeyboardInterrupt:
                raise
            except Exception as exc:      # défaillance COM imprévue -> repli, jamais un crash
                print("Mode natif en échec (%s) : repli sur le polling." % exc,
                      file=sys.stderr)
                captured = None
            if captured is None and args.engine == "native":
                print("Erreur : mode capture natif indisponible (voir message ci-dessus).",
                      file=sys.stderr)
                return 1
        if captured is None:
            capture_loop(engine, out_path, do_highlight=not args.no_highlight,
                         filter_text=args.filter)
        return 0

    if args.hover:
        out_path = _resolved(args.out, default_capture_path) if args.out else None
        if args.out and out_path is None:
            return 1
        hover_loop(engine, out_path=out_path, filter_text=args.filter)
        return 0

    if args.record:
        out_path = _resolved(args.out, default_record_path)
        if out_path is None:
            return 1
        screenshot_dir = None
        if args.screenshots:
            base, _ext = os.path.splitext(out_path)
            screenshot_dir = base + "_shots"
        recorded = None
        # --screenshots capture l'écran d'arrivée de chaque aller-retour, un
        # concept du moteur polling (frontière = diff de signature) : en auto,
        # sa présence privilégie donc le polling ; --engine native l'ignore.
        use_native = (args.engine == "native"
                      or (args.engine == "auto" and not args.screenshots))
        if use_native:
            try:
                recorded = record_loop_native(engine, out_path, semantic=args.semantic,
                                              suite=suite_mode)
            except KeyboardInterrupt:
                raise
            except Exception as exc:      # défaillance COM imprévue -> repli, jamais un crash
                print("Mode natif en échec (%s) : repli sur le polling." % exc,
                      file=sys.stderr)
                recorded = None
            if recorded is None and args.engine == "native":
                print("Erreur : mode record natif indisponible (voir message ci-dessus).",
                      file=sys.stderr)
                return 1
        if recorded is None:
            if args.semantic:
                print("--semantic requiert le moteur natif : déroulé en ids techniques.",
                      file=sys.stderr)
            record_loop(engine, out_path, screenshot_dir=screenshot_dir, suite=suite_mode)
        run_record_exports(out_path, export_resources=args.export_resources,
                           export_spec=args.export_spec,
                           export_report=args.export_report,
                           export_istqb=args.export_istqb)
        return 0

    elements = collect(engine)

    if args.filter:
        needle = args.filter.lower()
        elements = [e for e in elements
                    if needle in e["id"].lower() or needle in e["type"].lower()]

    if args.json is not None:
        out_path = _resolved(args.json or None, default_dump_path)
        if out_path is None:
            return 1
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(elements, fh, indent=2, ensure_ascii=False)
        print("Wrote %s elements to %s" % (len(elements), out_path))
    else:
        for e in elements:
            indent = "  " * e["depth"]
            text = (" = %r" % e["text"]) if e["text"] else ""
            print("%s[%s] %s%s" % (indent, e["type"], e["id"], text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
