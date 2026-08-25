"""Mode record par SONDAGE du recorder bureau : diff d'ecran -> steps.

La transcription des manipulations par difference entre deux instantanes
(`snapshot_fields`/`diff_to_steps`/`process_poll` : la signature d'ecran
detecte la navigation, l'OK-code et Entree fusionnent en `Run Transaction`),
les assertions a chaud (Ctrl+Alt+A / Ctrl+Alt+V) et la boucle `record_loop`
(--engine poll, --screenshots via HardCopyToMemory).

Extrait de ``sapgui_recorder.py`` (convention #13).
"""
import os
import re
import sys
import time

# Module charge par CHEMIN (Robot `Library`, spec_from_file_location des
# tests) : son dossier n'est pas forcement sur sys.path, on l'y pose pour que
# les imports entre modules voisins du recorder fonctionnent partout.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from recorder_com import (  # noqa: E402
    _safe,
    _walk_objects,
    active_window,
    capture_rect_to_bmp,
    com_error,
    element_rect,
    hardcopy_screenshot,
    relative_id,
    win32api,
)
from recorder_capture import (  # noqa: E402
    _timestamped_path,
    active_focus,
    clear_stop_file,
    make_stop_checker,
)
from recorder_exports import build_record_header, rf_escape_value  # noqa: E402

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


def open_record_file(out_path, suite=False):
    """Ouvre le fichier de sortie du record avec l'en-tête partagé par les deux
    moteurs (polling et natif) : corps ``*** Test Cases ***`` nu, ou suite
    ``.robot`` complète et rejouable avec ``suite=True`` (``--suite``)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fh = open(out_path, "w", encoding="utf-8")
    fh.write(build_record_header(out_path, suite=suite))
    fh.flush()
    return fh


def record_loop(engine, out_path, poll_seconds=0.4, screenshot_dir=None,
                suite=False, stop_file=None, _max_iterations=None, _writer=print,
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

    ``stop_file`` (option ``--stop-file``) arrête la boucle proprement depuis
    l'extérieur (bouton « Arrêter » de la GUI) : le fichier est refermé et les
    dernières étapes écrites, ce qu'un processus tué ne permet pas.

    ``_max_iterations``/``_writer``/``_screenshot_fn`` sont des points
    d'injection pour les tests."""
    should_stop = make_stop_checker(stop_file)
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
        while (_max_iterations is None or iterations < _max_iterations) \
                and not should_stop():
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
        pass
    finally:
        # Message d'arrêt dans le `finally` : le Ctrl+C n'est plus le SEUL
        # chemin de sortie depuis l'arrêt par sentinelle (`stop_file`).
        clear_stop_file(stop_file)
        fh.close()
        _writer("\nArrêt : %s étape(s) enregistrée(s) dans %s" % (count, out_path))
    return count
