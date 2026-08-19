"""Lanceur visuel léger du SAP GUI Recorder (`sapgui_recorder.py`).

Une petite fenêtre Tkinter (bibliothèque standard, aucune dépendance en plus de
pywin32) pour lancer le recorder bureau sans retenir la ligne de commande : on choisit
le **mode** (dump, JSON, capture, survol, record, surlignage) et les options, puis
« Lancer ». Les modes interactifs (capture/survol/record) tournent dans une **console
séparée** (sortie live + Ctrl+C natif) ; « Arrêter » termine le processus.

En mode record, le panneau « Étapes » suit le fichier de sortie EN DIRECT (les
steps émis apparaissent au fil de l'enregistrement) et permet de réordonner /
supprimer des étapes puis d'« Enregistrer » le fichier corrigé : la parité avec
le panneau du recorder web.

    python tools/recorder/recorder_gui.py

La logique pure de construction des arguments (`build_args`) et du panneau de
steps (`parse_recorded_body`/`replace_recorded_steps`, dans sapgui_recorder) est
isolée pour être testée hors SAP (convention #5) ; le câblage Tkinter, lui, ne
l'est pas.
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


# --------------------------------------------------------------------------- UI

def main():
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("SAP GUI Recorder")
    root.resizable(False, False)
    try:
        root.iconphoto(True, tk.PhotoImage(file=os.path.join(_DIR, "assets", "icon.png")))
    except Exception:
        pass   # icône absente ou Tk sans support PNG : purement cosmétique

    # --- bandeau identité : picto aicabra + titre, et poignée de déplacement --
    # La fenêtre se déplace déjà par sa barre de titre native ; le bandeau
    # devient une DEUXIÈME poignée (miroir de l'en-tête déplaçable du panneau
    # web) : utile au-dessus d'un SAP GUI plein écran où la barre native peut
    # sortir de l'écran. Le PNG est sous-échantillonné par ``subsample`` (Tk pur,
    # pas de Pillow à l'exécution) ; sans support PNG le bandeau reste textuel.
    banner = tk.Frame(root, bg="#0a6ed1", cursor="fleur")
    banner.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
    banner_img = None
    try:
        _raw = tk.PhotoImage(file=os.path.join(_DIR, "assets", "icon.png"))
        _factor = max(1, _raw.width() // 24)
        banner_img = _raw.subsample(_factor, _factor)
        tk.Label(banner, image=banner_img, bg="#0a6ed1").pack(side="left", padx=(8, 4), pady=3)
    except Exception:
        pass
    tk.Label(banner, text="SAPFX Recorder", fg="white", bg="#0a6ed1",
             font=("Segoe UI", 10, "bold")).pack(side="left", pady=3)
    tk.Label(banner, text="glisser pour déplacer", fg="#cfe3f7", bg="#0a6ed1",
             font=("Segoe UI", 8)).pack(side="right", padx=8)
    _drag = {"press_root": None, "press_win": None}

    def _banner_press(event):
        _drag["press_root"] = (event.x_root, event.y_root)
        _drag["press_win"] = (root.winfo_x(), root.winfo_y())

    def _banner_motion(event):
        if _drag["press_root"] is None:
            return
        x, y = banner_drag_position(_drag["press_root"], _drag["press_win"],
                                    (event.x_root, event.y_root))
        root.geometry("+%d+%d" % (x, y))

    def _banner_release(_event):
        _drag["press_root"] = None

    for w in [banner] + list(banner.winfo_children()):
        w.bind("<ButtonPress-1>", _banner_press)
        w.bind("<B1-Motion>", _banner_motion)
        w.bind("<ButtonRelease-1>", _banner_release)

    proc = {"p": None}   # processus en cours (modes interactifs)
    stop_state = {"path": None}          # sentinelle d'arrêt du lancement en cours
    # état du panneau de steps : fichier suivi, dernière mtime lue, édition en cours
    watch = {"path": None, "mtime": None, "dirty": False, "text": ""}

    mode_var = tk.StringVar(value=MODES[0][0])
    filter_var = tk.StringVar()
    out_var = tk.StringVar()
    hid_var = tk.StringVar()
    nohl_var = tk.BooleanVar(value=False)
    shots_var = tk.BooleanVar(value=False)
    engine_var = tk.StringVar(value="auto")
    sem_var = tk.BooleanVar(value=False)
    suite_var = tk.BooleanVar(value=True)   # défaut : .robot complet qui se lance tel quel
    expres_var = tk.BooleanVar(value=False)
    expspec_var = tk.BooleanVar(value=False)
    expreport_var = tk.BooleanVar(value=False)
    expistqb_var = tk.BooleanVar(value=False)

    pad = {"padx": 8, "pady": 3}

    # --- modes -------------------------------------------------------------
    frm_mode = ttk.LabelFrame(root, text="Mode")
    frm_mode.grid(row=1, column=0, sticky="ew", **pad)
    for i, (key, label, _desc) in enumerate(MODES):
        ttk.Radiobutton(frm_mode, text=label, value=key, variable=mode_var,
                        command=lambda: _on_mode_change()).grid(
            row=i, column=0, sticky="w", padx=6, pady=1)

    # --- options -----------------------------------------------------------
    frm_opt = ttk.LabelFrame(root, text="Options")
    frm_opt.grid(row=2, column=0, sticky="ew", **pad)
    ttk.Label(frm_opt, text="Filtre (id/type) :").grid(row=0, column=0, sticky="w", padx=6, pady=2)
    ent_filter = ttk.Entry(frm_opt, textvariable=filter_var, width=34)
    ent_filter.grid(row=0, column=1, padx=6, pady=2)
    ttk.Label(frm_opt, text="Fichier de sortie :").grid(row=1, column=0, sticky="w", padx=6, pady=2)
    ent_out = ttk.Entry(frm_opt, textvariable=out_var, width=34)
    ent_out.grid(row=1, column=1, padx=6, pady=2)
    ttk.Label(frm_opt, text="Id à surligner :").grid(row=2, column=0, sticky="w", padx=6, pady=2)
    ent_hid = ttk.Entry(frm_opt, textvariable=hid_var, width=34)
    ent_hid.grid(row=2, column=1, padx=6, pady=2)
    chk_nohl = ttk.Checkbutton(frm_opt, text="Ne pas surligner (capture)", variable=nohl_var)
    chk_nohl.grid(row=3, column=1, sticky="w", padx=6, pady=2)
    chk_shots = ttk.Checkbutton(frm_opt, text="Captures d'écran par étape (record)", variable=shots_var)
    chk_shots.grid(row=4, column=1, sticky="w", padx=6, pady=2)
    ttk.Label(frm_opt, text="Moteur (capture/record) :").grid(row=5, column=0, sticky="w", padx=6, pady=2)
    cmb_engine = ttk.Combobox(frm_opt, textvariable=engine_var, values=_ENGINES,
                              state="readonly", width=10)
    cmb_engine.grid(row=5, column=1, sticky="w", padx=6, pady=2)
    chk_sem = ttk.Checkbutton(
        frm_opt, text="Keywords humains par libellé (record natif)", variable=sem_var)
    chk_sem.grid(row=6, column=1, sticky="w", padx=6, pady=2)
    chk_suite = ttk.Checkbutton(
        frm_opt, text="Suite .robot complète (Settings + Setup ; décoché = fragment)",
        variable=suite_var)
    chk_suite.grid(row=7, column=1, sticky="w", padx=6, pady=2)
    chk_expres = ttk.Checkbutton(
        frm_opt, text="Export resource-first (.resource + suite)", variable=expres_var)
    chk_expres.grid(row=8, column=1, sticky="w", padx=6, pady=2)
    chk_expspec = ttk.Checkbutton(
        frm_opt, text="Export plan specs/ (.spec.md)", variable=expspec_var)
    chk_expspec.grid(row=9, column=1, sticky="w", padx=6, pady=2)
    chk_expreport = ttk.Checkbutton(
        frm_opt, text="Export rapport HTML (documentation)", variable=expreport_var)
    chk_expreport.grid(row=10, column=1, sticky="w", padx=6, pady=2)
    chk_expistqb = ttk.Checkbutton(
        frm_opt, text="Export plan ISTQB (.istqb.md)", variable=expistqb_var)
    chk_expistqb.grid(row=11, column=1, sticky="w", padx=6, pady=2)

    desc_var = tk.StringVar()
    ttk.Label(root, textvariable=desc_var, wraplength=360, foreground="#555").grid(
        row=3, column=0, sticky="w", **pad)
    status_var = tk.StringVar(value="Prêt. Ouvrez SAP Logon avec une session active.")
    # Ligne 6 et non 5 : la rangée de boutons occupe la 5 (`frm_btn` ci-dessous).
    # Deux widgets dans la MÊME cellule s'empilent sous Tk, et le frame créé en
    # dernier passait devant : le seul canal de retour de la fenêtre (« En
    # cours… », « Arrêté. », « Étapes enregistrées dans … ») était illisible.
    ttk.Label(root, textvariable=status_var, wraplength=360, foreground="#0a6ed1").grid(
        row=6, column=0, sticky="w", **pad)

    def _on_mode_change():
        mode = mode_var.get()
        desc = next(d for k, _l, d in MODES if k == mode)
        desc_var.set(desc)
        _set_state(ent_filter, mode in _USES_FILTER)
        _set_state(ent_out, mode in _USES_OUT)
        _set_state(ent_hid, mode in _USES_HIGHLIGHT_ID)
        _set_state(chk_nohl, mode in _USES_NO_HIGHLIGHT)
        _set_state(chk_shots, mode in _USES_SCREENSHOTS)
        _set_state(cmb_engine, mode in _USES_ENGINE, enabled_state="readonly")
        _set_state(chk_sem, mode in _USES_SEMANTIC)
        _set_state(chk_suite, mode in _USES_SUITE)
        _set_state(chk_expres, mode in _USES_EXPORTS)
        _set_state(chk_expspec, mode in _USES_EXPORTS)
        _set_state(chk_expreport, mode in _USES_EXPORTS)
        _set_state(chk_expistqb, mode in _USES_EXPORTS)

    def _set_state(widget, enabled, enabled_state="normal"):
        widget.configure(state=enabled_state if enabled else "disabled")

    # --- panneau de steps (mode record) ------------------------------------
    frm_steps = ttk.LabelFrame(root, text="Étapes enregistrées (record)")
    frm_steps.grid(row=4, column=0, sticky="ew", **pad)
    lst_steps = tk.Listbox(frm_steps, height=7, width=56, font=("Consolas", 9))
    lst_steps.grid(row=0, column=0, columnspan=5, sticky="ew", padx=6, pady=3)
    steps_state = {"steps": []}

    def _refresh_steps_list():
        lst_steps.delete(0, tk.END)
        for i, step in enumerate(steps_state["steps"], 1):
            lst_steps.insert(tk.END, "%d. %s" % (i, step))

    def _load_steps_from_file(force=False):
        path = watch["path"]
        if not path or not os.path.isfile(path):
            return
        try:
            mtime = os.path.getmtime(path)
            if not force and mtime == watch["mtime"]:
                return
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return
        watch["mtime"] = mtime
        watch["text"] = text
        _core = _recorder_core()
        _name, steps = _core.parse_recorded_body(text)
        steps_state["steps"] = steps
        watch["dirty"] = False
        _refresh_steps_list()

    def _tick():
        # suivi live : tant que l'utilisateur n'édite pas, on recharge le fichier
        if not watch["dirty"]:
            _load_steps_from_file()
        root.after(1000, _tick)

    def _selected_index():
        sel = lst_steps.curselection()
        return sel[0] if sel else None

    def on_step_move(delta):
        i = _selected_index()
        if i is None:
            return
        j = i + delta
        steps = steps_state["steps"]
        if j < 0 or j >= len(steps):
            return
        steps[i], steps[j] = steps[j], steps[i]
        watch["dirty"] = True
        _refresh_steps_list()
        lst_steps.selection_set(j)

    def on_step_delete():
        i = _selected_index()
        if i is None:
            return
        del steps_state["steps"][i]
        watch["dirty"] = True
        _refresh_steps_list()

    def on_steps_reload():
        _load_steps_from_file(force=True)

    def on_steps_save():
        path = watch["path"]
        if not path or not watch["text"]:
            return
        _core = _recorder_core()
        new_text = _core.replace_recorded_steps(watch["text"], steps_state["steps"])
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_text)
        except OSError as exc:                         # pragma: no cover - dépend de l'OS
            messagebox.showerror("Sauvegarde impossible", str(exc))
            return
        watch["dirty"] = False
        watch["mtime"] = None                          # forcera un rechargement propre
        status_var.set("Étapes enregistrées dans %s" % path)

    def on_step_edit(_event=None):
        # édition in-place (double-clic) : la parité avec le panneau du recorder web
        i = _selected_index()
        if i is None:
            return
        from tkinter import simpledialog
        new = simpledialog.askstring(
            "Éditer le step", "Step %d :" % (i + 1),
            initialvalue=steps_state["steps"][i], parent=root)
        if new is None:
            return
        new = new.strip()
        if not new:
            return
        steps_state["steps"][i] = new
        watch["dirty"] = True
        _refresh_steps_list()
        lst_steps.selection_set(i)

    def on_steps_replay():
        # le « play » de l'esprit Selenium IDE, côté client lourd : rejoue le
        # fichier contre la session SAP GUI ouverte (--replay, console séparée).
        path = watch["path"]
        if not path or not os.path.isfile(path):
            messagebox.showinfo("Rejouer", "Aucun fichier d'enregistrement à rejouer.")
            return
        if watch["dirty"]:
            on_steps_save()                            # rejouer CE qu'on voit à l'écran
        try:
            launch(["--replay", path])
        except Exception as exc:                       # pragma: no cover - dépend de l'OS
            messagebox.showerror("Échec du replay", str(exc))
            return
        status_var.set("Replay lancé (console séparée) : %s" % path)

    lst_steps.bind("<Double-Button-1>", on_step_edit)

    for col, (label, cmd) in enumerate((
            ("↑", lambda: on_step_move(-1)),
            ("↓", lambda: on_step_move(1)),
            ("✕", on_step_delete),
            ("Recharger", on_steps_reload),
            ("Enregistrer", on_steps_save),
            ("Rejouer", on_steps_replay))):
        ttk.Button(frm_steps, text=label, width=(3 if len(label) == 1 else 11),
                   command=cmd).grid(row=1, column=col, padx=3, pady=2)

    # --- actions -----------------------------------------------------------
    auto_out = {"name": None}   # dernier nom record auto-généré par la GUI

    def on_launch():
        mode = mode_var.get()
        if mode == "record":
            # nom généré CÔTÉ GUI (le panneau de steps sait quel fichier suivre),
            # RÉGÉNÉRÉ à chaque lancement tant que l'utilisateur ne l'a pas
            # remplacé : relancer un record n'écrase jamais le précédent.
            out, auto_out["name"] = resolve_record_out(out_var.get(), auto_out["name"])
            out_var.set(out)
        try:
            args = build_args(mode, filter_var.get(), out_var.get(),
                              hid_var.get(), nohl_var.get(), shots_var.get(),
                              engine_var.get(), sem_var.get(), suite_var.get(),
                              expres_var.get(), expspec_var.get(),
                              expreport_var.get(), expistqb_var.get())
        except ValueError as exc:
            messagebox.showerror("Option manquante", str(exc))
            return
        if proc["p"] is not None and proc["p"].poll() is None:
            on_stop()        # arrête une boucle précédente avant d'en lancer une autre
        if mode in _INTERACTIVE:
            # Sentinelle d'arrêt : la GUI est lancée par pythonw, elle n'a aucune
            # console d'où envoyer un Ctrl+C au recorder (console SÉPARÉE).
            stop_state["path"] = stop_file_path(out_var.get() or mode)
            args = args + ["--stop-file", stop_state["path"]]
        else:
            stop_state["path"] = None
        try:
            p = launch(args)
        except Exception as exc:                       # pragma: no cover - dépend de l'OS
            messagebox.showerror("Échec du lancement", str(exc))
            return
        proc["p"] = p if mode in _INTERACTIVE else None
        if mode == "record":
            watch.update(path=record_file_path(out_var.get().strip()),
                         mtime=None, dirty=False, text="")
            steps_state["steps"] = []
            _refresh_steps_list()
        # La sentinelle est un détail d'implémentation du bouton « Arrêter » :
        # elle n'encombre pas la ligne d'état, déjà étroite.
        shown = "sapgui_recorder.py " + " ".join(
            args[:args.index("--stop-file")] if "--stop-file" in args else args)
        status_var.set(("En cours (Ctrl+C dans la console pour arrêter) : " if mode in _INTERACTIVE
                        else "Lancé : ") + shown)

    def on_stop():
        p = proc["p"]
        path = stop_state["path"] or stop_file_path(out_var.get())
        outcome = request_stop(p, path)
        if outcome == "propre":
            status_var.set("Arrêté (teardown du recorder déroulé).")
        elif outcome == "forcé":
            status_var.set("Arrêt FORCÉ : le recorder n'a pas rendu la main ; "
                           "vérifiez le mode Record côté SAP GUI.")
        proc["p"] = None
        stop_state["path"] = None
        _load_steps_from_file(force=True)   # dernier état du fichier après l'arrêt

    def on_open_captures():
        os.makedirs(CAPTURES_DIR, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(CAPTURES_DIR)                 # pragma: no cover - Windows
        else:                                          # pragma: no cover
            status_var.set("Captures : %s" % CAPTURES_DIR)

    frm_btn = ttk.Frame(root)
    frm_btn.grid(row=5, column=0, sticky="ew", **pad)
    ttk.Button(frm_btn, text="Lancer", command=on_launch).grid(row=0, column=0, padx=4)
    ttk.Button(frm_btn, text="Arrêter", command=on_stop).grid(row=0, column=1, padx=4)
    ttk.Button(frm_btn, text="Dossier captures", command=on_open_captures).grid(row=0, column=2, padx=4)
    ttk.Button(frm_btn, text="Quitter", command=root.destroy).grid(row=0, column=3, padx=4)

    _on_mode_change()
    _tick()                              # suivi live du fichier record (panneau de steps)
    root.mainloop()


if __name__ == "__main__":
    main()
