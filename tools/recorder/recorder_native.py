"""Moteur record NATIF, moitie PURE : commandes -> keywords, mode semantique.

Le mapping des evenements ``Change`` de l'API (`map_change_command` :
boutons/grilles/arbres/menus captures avec la commande exacte), la machine a
etats (`process_change` : OK-code + Entree fusionnes en `Run Transaction`),
la table des vkeys lisibles, le mode --semantic (`semanticize_step` : keyword
humain seulement quand le libelle re-resout de facon unique via
`describe_element`) et `recording_disabled` (profil serveur).

Extrait de ``sapgui_recorder.py`` (convention #13). La boucle evenementielle
vit dans ``recorder_native_loop.py``.
"""
import os
import re
import sys

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
    com_error,
    relative_id,
)
from recorder_exports import rf_escape_value  # noqa: E402

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
