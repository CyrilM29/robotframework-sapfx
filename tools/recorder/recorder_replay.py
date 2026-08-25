"""Replay et transpile VBS du recorder bureau, plus le pipeline d'exports.

`--replay` rejoue un enregistrement contre la session OUVERTE (`Attach To
Open Session`, arret au premier echec ; un step dont le keyword n'est pas
dans la bibliotheque FAIT ECHOUER le replay : le cas resource-first sortait
vert avec 0 step execute), `--transpile-vbs` convertit les enregistrements
ALT+F12 via la MEME machine a etats que le natif (BOM UTF-8/16, UTF-16 sans
BOM et ANSI decodes), et `run_record_exports` derive suite/resources/spec/
ISTQB/rapport d'un enregistrement brut jamais modifie.

Extrait de ``sapgui_recorder.py`` (convention #13).
"""
import codecs
import locale
import os
import re
import sys

# Module charge par CHEMIN (Robot `Library`, spec_from_file_location des
# tests) : son dossier n'est pas forcement sur sys.path, on l'y pose pour que
# les imports entre modules voisins du recorder fonctionnent partout.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from recorder_com import relative_id  # noqa: E402
from recorder_exports import (  # noqa: E402
    _split_step,
    count_test_cases,
    parse_recorded_body,
    report_screenshot_loader,
    rf_unescape_value,
    steps_to_istqb,
    steps_to_report,
    steps_to_resource_first,
    steps_to_spec,
)
from recorder_native import (  # noqa: E402
    flush_native_state,
    initial_native_state,
    process_change,
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


def _resource_first_hint(text):
    """Message d'aide quand le fichier soumis au replay est une suite
    **resource-first** : ses steps sont des keywords métier qui vivent dans le
    ``.resource`` importé, hors de portée de l'appel direct à la bibliothèque."""
    if not re.search(r"^Resource\s", text, re.MULTILINE):
        return ""
    return ("  Ce fichier importe un Resource : c'est une suite resource-first, "
            "dont les keywords métier ne sont pas ceux de SapEccLibrary. "
            "Rejoue-la avec `robot`, ou rejoue l'enregistrement brut.")


def run_replay(path, _lib_factory=None, _writer=print):
    """Point d'entrée de ``--replay`` : relit le fichier et rejoue. Retourne un
    code de sortie CLI (0 = **tout** a été rejoué).

    Un step dont le keyword n'existe pas dans SapEccLibrary est signalé ET
    fait ÉCHOUER le replay : sortir en 0 avec des steps ignorés serait vert et
    faux (cas vécu de la suite resource-first, dont 100 % des steps sont des
    keywords métier : « Replay OK : 0 step(s) exécuté(s) »)."""
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
    total_tests = count_test_cases(text)
    if total_tests > 1:
        # Le replay ne connaît que le premier test (contrat du recorder) : le
        # dire, plutôt que laisser un « Replay OK » couvrir les autres.
        _writer("Attention : %d tests dans %s, seul le PREMIER est rejoué."
                % (total_tests, path))
    _writer("Replay de %d step(s) depuis %s :" % (len(steps), path))
    executed, skipped, failed, message = replay_recorded_steps(steps, lib, writer=_writer)
    if failed is not None:
        _writer("ÉCHEC au step %d : %s" % (failed + 1, message))
        _writer("  %s" % steps[failed])
        return 1
    if skipped:
        _writer("ÉCHEC : %d step(s) sur %d n'ont aucun keyword dans "
                "SapEccLibrary et n'ont donc PAS été rejoués."
                % (skipped, len(steps)))
        hint = _resource_first_hint(text)
        if hint:
            _writer(hint)
        return 1
    _writer("Replay OK : %d step(s) exécuté(s)." % executed)
    return 0


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
