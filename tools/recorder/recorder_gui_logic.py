"""Logique PURE du lanceur GUI du recorder (testable hors ecran).

Construction de la ligne de commande (`build_args` : modes, moteur,
exports), chemins d'enregistrement et d'arret (`record_file_path`,
`resolve_record_out`, `stop_file_path`, `request_stop` : la sentinelle
--stop-file qui rend l'arret externe aussi propre qu'un Ctrl+C),
`console_python` (pythonw -> python -> py) et la table des MODES.

Extrait de ``recorder_gui.py`` (convention #13) : le cablage Tkinter reste
la-bas, hors perimetre de couverture (pas d'ecran en CI).
"""
import datetime
import importlib.util
import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(_DIR, "sapgui_recorder.py")
CAPTURES_DIR = os.path.join(_DIR, "captures")


def _recorder_core():
    """Le module `sapgui_recorder` (helpers purs du panneau de steps), importé
    par nom si possible, sinon chargé par chemin (GUI lancée hors du dossier)."""
    try:
        import sapgui_recorder
        return sapgui_recorder
    except ImportError:
        spec = importlib.util.spec_from_file_location("sapgui_recorder", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def default_record_name(now=None):
    """Nom de fichier record par défaut, généré CÔTÉ GUI pour connaître (et
    suivre) le fichier de sortie : la CLI horodaterait elle-même sinon, et le
    panneau de steps n'aurait rien à suivre."""
    stamp = (now or datetime.datetime.now()).strftime("%Y%m%d_%H%M%S")
    return "record_%s.robot" % stamp


def record_file_path(out):
    """Chemin complet du fichier de sortie record tel que la CLI le résoudra
    (relatif -> sous captures/, absolu -> tel quel)."""
    if os.path.isabs(out):
        return out
    return os.path.join(CAPTURES_DIR, out)


def resolve_record_out(current, previous_auto, now=None):
    """Nom de sortie d'un lancement record : un nom SAISI par l'utilisateur est
    respecté tel quel (écraser est alors son choix explicite) ; un champ vide ou
    resté sur le nom auto-généré du lancement précédent reçoit un NOUVEAU nom
    horodaté : relancer un record ne tronque jamais silencieusement
    l'enregistrement précédent. Retourne ``(nom, nom_auto_mémorisé)``."""
    current = (current or "").strip()
    if current and current != previous_auto:
        return current, previous_auto
    fresh = default_record_name(now)
    return fresh, fresh

def stop_file_path(out_name, now=None):
    """Chemin de la sentinelle d'arrêt d'un lancement interactif.

    Dérivé du fichier de sortie quand il y en a un (record), horodaté sinon
    (capture et survol peuvent tourner sans fichier). Toujours sous
    ``captures/`` : c'est un artefact de travail, et le recorder l'efface
    lui-même en fin de boucle."""
    base = os.path.basename((out_name or "").strip())
    if not base:
        base = (now or datetime.datetime.now()).strftime("%Y%m%d_%H%M%S")
    return os.path.join(CAPTURES_DIR, base + ".stop")


def request_stop(proc, stop_path, timeout=5.0):
    """Arrête un recorder interactif SANS le tuer d'abord : pose la sentinelle
    (le processus sort de sa boucle et déroule son teardown : ``Session.Record``
    remis à False, événements désabonnés, dernières étapes écrites), et ne
    recourt à ``terminate()`` que s'il ne rend pas la main.

    ``terminate()`` seul sautait tout ce teardown, ce qui perdait l'OK-code en
    attente et laissait le mode Record actif côté SAP GUI (F4 modal, drag & drop
    désactivé pour l'utilisateur). Retourne ``'propre'``, ``'forcé'`` ou
    ``'déjà arrêté'``."""
    if proc is None or proc.poll() is not None:
        return "déjà arrêté"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(stop_path)), exist_ok=True)
        with open(stop_path, "w", encoding="utf-8") as fh:
            fh.write("stop\n")
    except OSError:
        proc.terminate()                  # sentinelle impossible : dernier recours
        return "forcé"
    try:
        proc.wait(timeout=timeout)
        return "propre"
    except subprocess.TimeoutExpired:
        proc.terminate()
        return "forcé"


def banner_drag_position(press_root, press_win, motion_root):
    """Nouvelle origine de la fenêtre pendant un glisser du bandeau.

    Logique pure du déplacement : ``press_root`` est la position (x, y) de la
    souris À L'ENFONCEMENT (coordonnées écran), ``press_win`` l'origine de la
    fenêtre au même instant, ``motion_root`` la position courante de la souris.
    La fenêtre suit le delta souris : même contrat que le drag de l'en-tête du
    panneau du recorder web.
    """
    return (press_win[0] + motion_root[0] - press_root[0],
            press_win[1] + motion_root[1] - press_root[1])


# (clé, libellé affiché, description courte). L'ordre = l'ordre des boutons radio.
MODES = [
    ("dump", "Dump : arbre d'objets (terminal)",
     "Liste tout l'arbre de contrôles SAP GUI dans la console. Astuce : filtre."),
    ("json", "Dump JSON (fichier)",
     "Écrit l'arbre en JSON sous captures/ (ou le fichier de sortie indiqué)."),
    ("capture", "Capture : clic = 1 locator",
     "Enregistre chaque contrôle focalisé + une ligne de keyword prête à coller."),
    ("hover", "Survol : inspecteur live",
     "Encadre le contrôle sous le curseur en continu (avec sortie : enregistre aussi)."),
    ("record", "Record : enregistrer un déroulé",
     "Transcrit vos manipulations en un corps *** Test Cases *** rejouable."),
    ("highlight", "Surligner un id à l'écran",
     "Encadre en rouge l'élément dont vous saisissez l'id, puis quitte."),
]

# Pour activer/désactiver les champs selon le mode.
_USES_FILTER = {"dump", "json", "capture", "hover"}
_USES_OUT = {"json", "capture", "hover", "record"}
_USES_HIGHLIGHT_ID = {"highlight"}
_USES_NO_HIGHLIGHT = {"capture"}
_USES_SCREENSHOTS = {"record"}
_USES_ENGINE = {"capture", "record"}
_USES_SEMANTIC = {"record"}
_USES_SUITE = {"record"}
_USES_EXPORTS = {"record"}
_ENGINES = ("auto", "native", "poll")
_INTERACTIVE = {"capture", "hover", "record"}   # boucles à arrêter via « Arrêter »


def build_args(mode, filter_text="", out="", highlight_id="", no_highlight=False,
               screenshots=False, engine="auto", semantic=False, suite=True,
               export_resources=False, export_spec=False, export_report=False,
               export_istqb=False):
    """Construit la liste d'arguments CLI de ``sapgui_recorder.py`` pour ``mode``.

    Reflète exactement l'interface de la CLI : ``--json`` prend le fichier en
    positionnel, ``--out`` sert capture/survol/record, ``--filter`` sert
    dump/json/capture/survol, ``--screenshots``/``--semantic``/
    ``--export-resources``/``--export-spec``/``--export-report``/
    ``--export-istqb`` ne s'appliquent qu'au record, ``--engine`` à
    capture/record (omis quand il vaut ``auto``, le défaut de la CLI). La
    suite complète est le DÉFAUT de la CLI depuis 2026-08-05 (aucun drapeau
    émis) ; ``suite=False`` en mode record émet ``--body-only`` (l'ancien
    fragment sans Library, qui ne se lance pas tel quel). Lève si un id manque
    pour le surlignage."""
    filter_text = (filter_text or "").strip()
    out = (out or "").strip()
    highlight_id = (highlight_id or "").strip()
    if engine not in _ENGINES:
        raise ValueError("Moteur inconnu : %r (choix : %s)" % (engine, "/".join(_ENGINES)))

    if mode == "dump":
        args = []
    elif mode == "json":
        args = ["--json"] + ([out] if out else [])
    elif mode == "highlight":
        if not highlight_id:
            raise ValueError("Le mode « Surligner » exige un id d'élément.")
        args = ["--highlight", highlight_id]
    elif mode == "capture":
        args = ["--capture"] + (["--no-highlight"] if no_highlight else [])
    elif mode == "hover":
        args = ["--hover"]
    elif mode == "record":
        args = (["--record"] + (["--screenshots"] if screenshots else [])
                + (["--semantic"] if semantic else [])
                + ([] if suite else ["--body-only"])
                + (["--export-resources"] if export_resources else [])
                + (["--export-spec"] if export_spec else [])
                + (["--export-report"] if export_report else [])
                + (["--export-istqb"] if export_istqb else []))
    else:
        raise ValueError("Mode inconnu : %r" % (mode,))

    if engine != "auto" and mode in _USES_ENGINE:
        args += ["--engine", engine]
    if filter_text and mode in _USES_FILTER:
        args += ["--filter", filter_text]
    if out and mode in ("capture", "hover", "record"):   # json: fichier déjà positionnel
        args += ["--out", out]
    return args


def console_python():
    """Chemin d'un interpréteur *console* (jamais ``pythonw.exe``).

    ``recorder.cmd`` lance cette GUI via ``pythonw`` pour éviter une console
    parasite derrière la fenêtre Tkinter, mais ``pythonw.exe`` est un binaire à
    sous-système GUI qui n'a **aucun** flux stdio, même dans une nouvelle console
    (``CREATE_NEW_CONSOLE``) : le premier ``print()`` du recorder y échoue. Si
    ``sys.executable`` pointe vers ``pythonw.exe``, on bascule sur le
    ``python.exe`` du même dossier pour le processus enfant, qui lui a une
    console utilisable."""
    exe = sys.executable
    if os.path.basename(exe).lower() == "pythonw.exe":
        candidate = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(candidate):
            return candidate
    return exe


def launch(args):
    """Lance ``sapgui_recorder.py args`` dans une console séparée ; retourne le Popen.

    Sous Windows, ``CREATE_NEW_CONSOLE`` ouvre une fenêtre où la sortie live s'affiche
    et où Ctrl+C arrête proprement les boucles interactives."""
    cmd = [console_python(), SCRIPT_PATH] + list(args)
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
    return subprocess.Popen(cmd, creationflags=creationflags)
