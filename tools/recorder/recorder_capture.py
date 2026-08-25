"""Modes capture (clic-a-capturer) et survol du recorder bureau.

Le sondage de focus (`current_focus`), la suggestion de keyword, les chemins
de sauvegarde par defaut (rediriges par ``CAPTURES_DIR``), l'arret propre
externe (`make_stop_checker` : sentinelle --stop-file sondee par les boucles
interactives), les deux boucles `capture_loop` (focus polling) et
`hover_loop` (l'element SOUS le curseur, fenetre active seulement), et la
suggestion `Click Element At Offset` des zones opaques (GuiShell/GuiChart).

Extrait de ``sapgui_recorder.py`` (convention #13).
"""
import datetime
import os
import sys
import time

# Module charge par CHEMIN (Robot `Library`, spec_from_file_location des
# tests) : son dossier n'est pas forcement sur sys.path, on l'y pose pour que
# les imports entre modules voisins du recorder fonctionnent partout.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from recorder_com import (  # noqa: E402
    _matches_filter,
    _safe,
    com_error,
    element_at,
    element_rect,
    rect_contains,
    relative_id,
    win32api,
)

# Dossier de sauvegarde par defaut des captures interactives.
CAPTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

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
    # Windows : ``E:fichier`` porte un lecteur SANS être absolu (il vise le
    # répertoire courant DE ce lecteur). Un ``join`` sous captures/ le laisse
    # tel quel et `commonpath` lève alors un ValueError « mix absolute and
    # relative » que la CLI affichait en message de traversée de chemin,
    # trompeur. On le refuse pour ce qu'il est.
    if os.path.splitdrive(path)[0]:
        raise ValueError(
            "Le chemin %r est relatif à un lecteur (forme ``X:fichier``) : "
            "donne un chemin absolu, ou un chemin relatif sous %s."
            % (path, CAPTURES_DIR))
    captures_root = os.path.normpath(CAPTURES_DIR)
    candidate = os.path.normpath(os.path.join(captures_root, path))
    try:
        inside = os.path.commonpath([captures_root, candidate]) == captures_root
    except ValueError:                   # lecteurs différents, formes mixtes
        inside = False
    if not inside:
        raise ValueError(
            "Le chemin relatif %r sort de %s ; utilise un chemin absolu si "
            "c'est voulu." % (path, CAPTURES_DIR))
    return candidate


# --- Arrêt propre demandé de l'extérieur (--stop-file) ------------------------
#
# Les boucles interactives s'arrêtent nominalement par Ctrl+C dans leur propre
# console. La GUI, elle, n'a aucune console à laquelle envoyer ce signal (elle
# lance le recorder dans une console SÉPARÉE) : elle ne pouvait que TUER le
# processus, ce qui saute le ``finally`` des boucles, donc l'OK-code resté en
# attente (`flush_native_state`), le ``session.Record = False`` et le
# désabonnement des événements. Une sentinelle fichier, sondée au rythme de la
# boucle, rend l'arrêt EXTERNE aussi propre que le Ctrl+C.

def make_stop_checker(stop_file):
    """Retourne ``should_stop()`` -> booléen, vrai dès que ``stop_file``
    apparaît ; sonde inerte (toujours fausse) sans chemin.

    Une sentinelle RESTÉE d'un run précédent est retirée à l'armement : sinon
    elle arrêterait l'enregistrement suivant dès sa première itération."""
    if not stop_file:
        return lambda: False
    try:
        os.remove(stop_file)
    except OSError:
        pass
    return lambda: os.path.exists(stop_file)


def clear_stop_file(stop_file):
    """Retire la sentinelle d'arrêt en fin de boucle (best-effort : son absence
    n'est jamais une erreur, la boucle est déjà terminée)."""
    if stop_file:
        try:
            os.remove(stop_file)
        except OSError:
            pass


def capture_loop(engine, out_path, do_highlight=True, poll_seconds=0.3,
                 filter_text=None, stop_file=None, _max_iterations=None,
                 _writer=print):
    """Mode interactif : enregistre chaque nouvel élément focalisé jusqu'à Ctrl+C.

    ``filter_text`` (option ``--filter``) restreint aux éléments dont l'id ou le type
    le contient. ``stop_file`` (option ``--stop-file``) est la sentinelle d'arrêt
    externe. ``_max_iterations`` / ``_writer`` sont des points d'injection pour les
    tests : en production la boucle tourne indéfiniment et écrit sur stdout + fichier."""
    should_stop = make_stop_checker(stop_file)
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
        while (_max_iterations is None or iterations < _max_iterations) \
                and not should_stop():
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
        pass
    finally:
        # Message d'arrêt dans le `finally` : la sortie par sentinelle
        # (`stop_file`) doit rendre compte comme le Ctrl+C.
        clear_stop_file(stop_file)
        fh.close()
        _writer("\nArrêt : %s élément(s) capturé(s) dans %s" % (count, out_path))
    return count


def hover_loop(engine, cursor_fn=None, poll_seconds=0.15, out_path=None,
               filter_text=None, stop_file=None, _max_iterations=None,
               _writer=print):
    """Mode survol : encadre en rouge le contrôle sous le curseur, en continu.

    ``filter_text`` (option ``--filter``) restreint aux contrôles dont l'id ou le type
    le contient : les autres sont ignorés (ni cadre ni capture). ``cursor_fn`` (défaut
    ``win32api.GetCursorPos``) et ``_max_iterations`` sont des points d'injection pour
    les tests. ``stop_file`` (option ``--stop-file``) est la sentinelle d'arrêt
    externe. Si ``out_path`` est fourni, chaque nouveau contrôle survolé est aussi
    enregistré (sinon : inspecteur live, sans fichier)."""
    should_stop = make_stop_checker(stop_file)
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
        while (_max_iterations is None or iterations < _max_iterations) \
                and not should_stop():
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
        pass
    finally:
        clear_stop_file(stop_file)
        if current is not None:                  # ne pas laisser de cadre orphelin
            try:
                current.Visualize(False)
            except com_error:
                pass
        if fh is not None:
            fh.close()
        _writer("\nArrêt.")
    return count


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
