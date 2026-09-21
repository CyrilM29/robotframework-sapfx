"""Outillage de PRISE DE VUE d'une démo : voix off, placement de fenêtres et
assemblage du film.

Il n'y a rien de SAP ici, et c'est délibéré : ce module ne sait que filmer une
région de l'écran, poser une fenêtre dedans, dire un texte et recoller le tout.
La démo, elle, vit dans une suite Robot qui pilote le produit.

Trois partis pris, chacun payé par un défaut de la première tentative.

**Une seule capture continue, d'une région FIXE de l'écran.** La démo traverse
cinq applications (SAP GUI, l'explorateur, le bloc-notes, Excel, le navigateur).
Capturer chaque fenêtre par son titre obligerait à recoller des segments de
tailles différentes et à recaler autant de pistes de sous-titres. On capture
donc un rectangle fixe et on POSE chaque fenêtre dedans : le montage disparaît,
il ne reste qu'une timeline.

**Un fond opaque derrière tout.** Une capture de région montre ce qui s'y
trouve, y compris le bureau de la machine quand une fenêtre ne couvre pas tout
le rectangle. Le fond (`backdrop.py`) garantit qu'aucun élément du poste
n'entre dans l'image, ce qu'une capture par titre de fenêtre offrait
gratuitement et qu'il fallait donc rendre autrement.

**La voix est synthétisée AVANT la prise, jamais pendant.** Écrire les WAV en
amont donne leur durée exacte, donc le rythme du scénario (chaque réplique dure
ce qu'elle dure) et un mixage posé à l'horodatage en post-production. Parler
pendant la prise aurait mis la voix dans l'ambiance de la pièce et rendu le
film non rejouable.
"""

from __future__ import annotations

import os
import subprocess
import wave

# SSFMCreateForWrite : le mode d'ouverture d'un SpFileStream en écriture.
_SAPI_WRITE = 3
# Le bleu du bandeau de sous-titres, repris de la démo du recorder.
BANNER_COLOR = "0x0a3d62"


# --------------------------------------------------------------------------
# Voix off
# --------------------------------------------------------------------------
def synthesize_narration(script, out_dir, voice_hint="Zira", rate=-1):
    """Écrit un WAV par réplique et rend la carte ``{id: durée en secondes}``.

    ``script`` est une liste de dictionnaires ``{id, text, speech}``. C'est
    ``speech`` qui est DIT et ``text`` qui est LU dans le bandeau : une voix de
    synthèse prononce « SE16 » de façon imprévisible alors qu'elle prononce
    « S E sixteen » toujours pareil, et un sous-titre, lui, doit porter
    l'orthographe technique exacte. En l'absence de ``speech``, le sous-titre
    est dit tel quel.

    La voix est
    choisie par sous-chaîne de sa description (``Zira`` = la voix anglaise
    livrée avec Windows) : nommer une voix exactement la rendrait dépendante
    d'une installation précise, et un poste sans elle doit le DIRE plutôt que
    de parler français sur un commentaire anglais.

    ``rate`` suit l'échelle SAPI (-10 à 10). La valeur par défaut ralentit
    légèrement : à vitesse nominale, les sigles techniques (SE16, ALV, CSV)
    sortent hachés.
    """
    import win32com.client  # importé ici : ce module doit rester lisible hors Windows

    voice = win32com.client.Dispatch("SAPI.SpVoice")
    tokens = voice.GetVoices()
    chosen = None
    available = []
    for index in range(tokens.Count):
        token = tokens.Item(index)
        description = token.GetDescription()
        available.append(description)
        if voice_hint.lower() in description.lower():
            chosen = token
            break
    if chosen is None:
        raise RuntimeError(
            "Aucune voix ne correspond à '%s'. Voix installées : %s. "
            "Ajouter la voix anglaise dans Paramètres > Heure et langue > Voix."
            % (voice_hint, ", ".join(available))
        )
    voice.Voice = chosen
    voice.Rate = rate

    os.makedirs(out_dir, exist_ok=True)
    durations = {}
    for cue in script:
        path = os.path.join(out_dir, "%s.wav" % cue["id"])
        if os.path.exists(path):
            os.remove(path)
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(path, _SAPI_WRITE)
        voice.AudioOutputStream = stream
        voice.Speak(cue.get("speech") or cue["text"])
        voice.AudioOutputStream = None
        stream.Close()
        durations[cue["id"]] = wav_duration(path)
    return durations


def wav_duration(path):
    """Durée d'un WAV en secondes, lue dans son en-tête."""
    with wave.open(path) as handle:
        return handle.getnframes() / float(handle.getframerate())


# --------------------------------------------------------------------------
# Placement des fenêtres filmées
# --------------------------------------------------------------------------
def place_window(title_part, x, y, width, height, timeout=20.0):
    """Amène au premier plan la fenêtre dont le titre CONTIENT ``title_part`` et
    la pose exactement dans le rectangle filmé.

    Rend le titre réellement retenu, pour que l'appelant puisse le journaliser :
    une démo qui filme la mauvaise fenêtre produit une vidéo parfaitement nette
    de quelque chose d'autre.

    L'attente est active parce qu'une application lancée par la démo (Excel, le
    navigateur) n'a pas sa fenêtre à l'instant où le processus démarre.
    """
    import time

    import win32con
    import win32gui

    deadline = time.monotonic() + float(timeout)
    needle = title_part.lower()

    # L'accumulateur passe par le second paramètre que `EnumWindows` transmet
    # au rappel, plutôt que par une fermeture sur une variable de boucle : la
    # fonction est ainsi définie UNE fois, hors de l'attente active.
    def collect(hwnd, found):
        if not win32gui.IsWindowVisible(hwnd):
            return
        text = win32gui.GetWindowText(hwnd)
        if text and needle in text.lower():
            found.append((hwnd, text))

    while True:
        matches = []
        win32gui.EnumWindows(collect, matches)
        if matches:
            hwnd, text = matches[0]
            # Une fenêtre agrandie ignore MoveWindow : on la restaure d'abord.
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.MoveWindow(hwnd, int(x), int(y), int(width), int(height), True)
            _force_foreground(hwnd)
            time.sleep(0.4)
            return text
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "Aucune fenêtre visible dont le titre contient '%s' après %ss. "
                "La démo filmerait le fond au lieu de l'application."
                % (title_part, timeout)
            )
        time.sleep(0.3)


def _force_foreground(hwnd):
    """Met la fenêtre au premier plan malgré le verrou de focus de Windows.

    `SetForegroundWindow` ÉCHOUE quand le processus appelant ne détient pas le
    focus, ce qui est le cas courant ici : la démo pilote des applications
    qu'elle vient de lancer. Le repli minimise puis restaure, ce que Windows
    accepte toujours, et la fenêtre remonte.
    """
    import win32con
    import win32gui

    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)


def file_url(path):
    """Transforme un chemin local en URL ``file:///``.

    Ce keyword existe pour une raison de FRONTIÈRE, pas de complexité : écrit
    en Robot, le même calcul passe par une expression contenant des antislashs,
    que Robot échappe avant de la remettre à Python, et l'expression finit en
    chaîne non terminée. Le calcul appartient donc au module.
    """
    return "file:///" + os.path.abspath(path).replace("\\", "/")


def resolve_app(executable):
    """Chemin complet d'une application installée, lu dans la base de registre.

    Windows publie sous ``App Paths`` l'emplacement des applications installées
    (Excel, les navigateurs). Le lire évite d'écrire un chemin de POSTE dans un
    fichier du dépôt, et donne un refus clair là où l'application manque, au
    lieu d'un processus qui ne démarre pas.
    """
    import winreg

    key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\%s" % executable
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, key) as handle:
                path = winreg.QueryValueEx(handle, None)[0]
        except OSError:
            continue
        if path and os.path.exists(path):
            return path
    raise RuntimeError(
        "%s n'est pas installé sur ce poste (rien sous App Paths). "
        "La démo ne peut pas montrer ce format ouvert." % executable
    )


def send_keys(keys, settle=0.6):
    """Envoie une séquence de touches à la fenêtre ACTIVE.

    Sert aux gestes qu'aucune API ne donne proprement sur une application
    tierce : passer l'explorateur en affichage détaillé, ou sauter à la
    dernière cellule d'un classeur pour MONTRER qu'il porte bien ses cinq
    mille lignes. La fenêtre visée doit avoir été mise au premier plan juste
    avant (voir `place_window`), sans quoi les touches partiraient ailleurs.
    """
    import time

    import win32com.client

    win32com.client.Dispatch("WScript.Shell").SendKeys(keys)
    time.sleep(float(settle))


def close_windows(*title_parts):
    """Demande la fermeture de chaque fenêtre dont le titre contient un motif.

    Best effort et sans exception : c'est un keyword de teardown, et une fenêtre
    déjà fermée n'est pas une anomalie.
    """
    import win32con
    import win32gui

    # Le motif cherché ET la liste des titres fermés voyagent par le second
    # paramètre du rappel, donc le rappel ne capture aucune variable de boucle.
    def collect(hwnd, state):
        lowered, closed = state
        if not win32gui.IsWindowVisible(hwnd):
            return
        text = win32gui.GetWindowText(hwnd)
        if text and lowered in text.lower():
            closed.append(text)
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

    closed = []
    for needle in title_parts:
        try:
            win32gui.EnumWindows(collect, (needle.lower(), closed))
        except Exception:
            pass
    return closed


# --------------------------------------------------------------------------
# Sous-titres
# --------------------------------------------------------------------------
def build_srt(cues, path, offset=0.0, tail=3.0):
    """Écrit la piste de sous-titres depuis les répliques horodatées.

    Chaque réplique s'affiche de son horodatage jusqu'au suivant, jamais moins
    longtemps que sa propre voix : sans ce plancher, deux répliques rapprochées
    feraient disparaître le texte pendant que la phrase est encore dite.
    """
    lines = []
    total = len(cues)
    for index, cue in enumerate(cues):
        start = float(cue["t"]) + offset
        spoken_end = start + float(cue.get("duration", 0.0))
        if index + 1 < total:
            end = float(cues[index + 1]["t"]) + offset
        else:
            end = spoken_end + tail
        end = max(end, spoken_end)
        text = cue["text"].strip()
        lines.append(
            "%d\n%s --> %s\n%s\n"
            % (index + 1, _timestamp(start), _timestamp(end), _wrap(text))
        )
    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def clock():
    """L'horloge de la prise, en secondes.

    Monotone et jamais l'heure du mur : une resynchronisation d'horloge pendant
    une prise de plusieurs minutes décalerait toute la piste de sous-titres et
    la voix avec elle (même raison que dans `sapfx_common.polling`).
    """
    import time

    return time.monotonic()


def shift_cues(cues, offset):
    """Recale toutes les répliques d'un même décalage, mesuré sur le film.

    La capture démarre AVANT l'origine du scénario (amorçage de gdigrab, puis
    temporisation), donc le film est plus long que le déroulé : sans ce
    recalage, sous-titres et voix devancent l'image de quelques secondes. Le
    décalage est MESURÉ (durée du film moins durée du scénario), jamais supposé.
    """
    shifted = []
    for cue in cues:
        copy = dict(cue)
        copy["t"] = float(cue["t"]) + float(offset)
        shifted.append(copy)
    return shifted


def _timestamp(seconds):
    seconds = max(0.0, float(seconds))
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:  # l'arrondi peut franchir la seconde
        whole += 1
        millis = 0
    return "%02d:%02d:%02d,%03d" % (whole // 3600, (whole // 60) % 60, whole % 60, millis)


def _wrap(text, width=96):
    """Replie une réplique sur au plus deux lignes lisibles dans le bandeau."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Assemblage
# --------------------------------------------------------------------------
def assemble_video(ffmpeg, raw, srt, cues, wav_dir, out, banner=190, font_size=15):
    """Recolle le film : bandeau, sous-titres incrustés et voix off mixée.

    La voix off est POSÉE à l'horodatage de chaque réplique (`adelay`) puis
    mélangée en une piste unique (`amix`). C'est ce qui rend le son solidaire du
    scénario : il n'a pas été enregistré pendant la prise, il est reconstruit
    depuis les mêmes horodatages que les sous-titres, donc les deux ne peuvent
    pas diverger.

    ``apad`` prolonge le silence après la dernière réplique et ``-shortest``
    coupe sur la fin de l'IMAGE : sans les deux, le film s'arrêterait à la
    dernière phrase ou la piste sonore serait tronquée.
    """
    inputs = ["-i", raw]
    filters = []
    labels = []
    for index, cue in enumerate(cues):
        wav = os.path.join(wav_dir, "%s.wav" % cue["id"])
        if not os.path.exists(wav):
            continue
        inputs += ["-i", wav]
        stream = len(labels) + 1  # l'entrée 0 est l'image
        delay = int(max(0.0, float(cue["t"]) + float(cue.get("offset", 0.0))) * 1000)
        label = "a%d" % index
        filters.append("[%d:a]adelay=%d:all=1[%s]" % (stream, delay, label))
        labels.append(label)

    # Le SRT est désigné par son NOM NU et ffmpeg lancé dans le dossier : un
    # chemin Windows dans un filtre exige d'échapper « \ » ET « : », source
    # d'erreurs sans rapport avec le montage.
    style = (
        "FontName=Segoe UI,FontSize=%d,PrimaryColour=&H00FFFFFF&,"
        "Outline=0,Shadow=0,Alignment=1,MarginL=40,MarginV=18" % font_size
    )
    video_chain = "[0:v]pad=iw:ih+%d:0:0:color=%s,subtitles=%s:force_style='%s'[v]" % (
        banner,
        BANNER_COLOR,
        os.path.basename(srt),
        style,
    )
    filters.append(video_chain)

    if labels:
        filters.append(
            "%samix=inputs=%d:normalize=0,apad[aout]"
            % ("".join("[%s]" % name for name in labels), len(labels))
        )
        mapping = ["-map", "[v]", "-map", "[aout]", "-c:a", "aac", "-b:a", "128k"]
    else:
        mapping = ["-map", "[v]"]

    command = (
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        + inputs
        + ["-filter_complex", ";".join(filters)]
        + mapping
        + [
            "-c:v", "libx264", "-preset", "slow", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", "30",
            "-shortest", os.path.basename(out),
        ]
    )
    result = subprocess.run(
        command, cwd=os.path.dirname(os.path.abspath(out)),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "ffmpeg a refusé le montage (code %s) : %s"
            % (result.returncode, (result.stderr or result.stdout)[-2000:])
        )
    return os.path.getsize(out)


def probe_duration(ffmpeg, path):
    """Durée réelle d'un fichier vidéo, mesurée et non supposée."""
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("ffprobe n'a pas pu mesurer %s : %s" % (path, result.stderr))
    return float(result.stdout.strip())
