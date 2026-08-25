"""Export rapport HTML du recorder bureau : la documentation d'un deroule.

`steps_to_report` : rapport auto-contenu (phrase metier + ligne RF exacte
par step, keywords ECC/Fiori/API phrases pour les deroules mixtes, captures
``--screenshots`` incrustees en data-URI, ``password=`` masque ; concept
RoboSAPiens ``saveHtmlReport`` reimplemente par step, NOTICE). Jamais un
test : une documentation.

Extrait de ``recorder_exports.py`` (convention #13).
"""
import base64
import html
import os
import re

from recorder_exports_docs import _humanize_step, md_code
from recorder_exports_core import (
    _mask_secret_args,
    DEFAULT_TEST_NAME,
    _split_step,
    rf_unescape_value,
)



# --- Export rapport HTML : la documentation humaine d'un enregistrement -------
#
# 4e export (`--export-report`) : une page HTML AUTO-CONTENUE (CSS minimal
# inline, captures en data-URI : aucune dépendance, aucun réseau) qui documente
# le déroulé en langage métier, la ligne RF exacte en regard, et l'écran
# d'arrivée de chaque aller-retour quand ``--screenshots`` était actif.
# Concept observé chez RoboSAPiens (saveHtmlReport, NOTICE) ; réimplémenté sur
# notre modèle : par STEP (pas une capture par fenêtre), texte -> texte pur,
# lecture des captures injectable (testable hors SAP). Ce rapport est une
# documentation, jamais un artefact rejouable : l'enregistrement brut fait foi.

_REPORT_CSS = """\
body { font-family: system-ui, 'Segoe UI', sans-serif; margin: 2em auto;
       max-width: 62em; padding: 0 1em; color: #1d2d3e; }
h1 { font-size: 1.5em; border-bottom: 2px solid #0a6ed1; padding-bottom: .3em; }
p.meta { color: #556b82; font-size: .9em; }
ol.steps { padding-left: 1.6em; }
ol.steps > li { margin: .9em 0; }
p.human { margin: 0 0 .15em; }
p.raw { margin: 0; }
p.raw code, li.note code { background: #f5f6f7; border: 1px solid #d9d9d9;
       border-radius: 3px; padding: 1px 5px; font-size: .85em; color: #495a6e; }
li.note { list-style: none; margin-left: -1.6em; color: #6a6d70;
       font-style: italic; }
figure { margin: .5em 0 0; }
figure img { max-width: 100%; border: 1px solid #c8cdd2; border-radius: 3px; }
figcaption { color: #556b82; font-size: .8em; margin-top: .2em; }
p.missing { color: #aa0808; font-size: .85em; margin: .3em 0 0; }
"""

# Extensions de capture émises par le record (`hardcopy_screenshot` nomme le
# fichier d'après ses magic bytes, `capture_rect_to_bmp` écrit du .bmp).
_REPORT_MIMES = {".png": "image/png", ".bmp": "image/bmp", ".jpg": "image/jpeg",
                 ".jpeg": "image/jpeg", ".gif": "image/gif"}

def _esc(text):
    """Échappement HTML du CONTENU texte du rapport (jamais d'attribut
    alimenté par les données : ``quote=False`` garde les apostrophes
    françaises lisibles)."""
    return html.escape(text, quote=False)


_SCREENSHOT_COMMENT = re.compile(r"^#\s*screenshot:\s*(.+)$")


def report_screenshot_loader(record_dir):
    """Chargeur de captures par défaut de `steps_to_report` : chemin absolu tel
    quel, chemin relatif essayé depuis le répertoire courant PUIS depuis le
    dossier de l'enregistrement (les commentaires ``# screenshot:`` stockent le
    chemin tel que le record l'a construit). Retourne ``(mime, octets)`` ou
    ``None`` ; jamais d'exception : une capture illisible devient une mention
    honnête dans le rapport, pas un échec d'export."""
    def load(path):
        candidates = [path] if os.path.isabs(path) else \
            [path, os.path.join(record_dir, path)]
        for candidate in candidates:
            mime = _REPORT_MIMES.get(os.path.splitext(candidate)[1].lower())
            if mime is None or not os.path.isfile(candidate):
                continue
            try:
                with open(candidate, "rb") as fh:
                    return mime, fh.read()
            except OSError:
                return None
        return None
    return load


# Phrases métier des keywords **Fiori/UI5** et **API** pour le rapport : le
# rapport documente aussi des déroulés mixtes cross-canal (une suite éditée à
# la main peut mêler écran ECC, contrôles UI5 et recoupement OData) ; l'export
# spec, lui, reste borné au contrat ECC du recorder desktop. Le sélecteur/
# chemin est rendu tel quel (la ligne exacte est de toute façon en regard).
def _humanize_channel_step(cells):
    """Phrase métier française pour un keyword Fiori/UI5 ou API, ou ``None``."""
    kw = cells[0] if cells else ""

    def rest(start, stop=None):
        return md_code("    ".join(cells[start:stop]) or "?")

    if kw in ("Click Ui5 Control", "Click Wc Control", "Click Dom Element") \
            and len(cells) >= 2:
        return "Cliquer le contrôle %s" % rest(1)
    if kw in ("Fill Ui5 Input", "Fill Wc Input", "Fill Dom Input") and len(cells) >= 3:
        return "Saisir %s dans le contrôle %s" % (
            md_code(rf_unescape_value(cells[1])), rest(2))
    if kw == "Click Sid" and len(cells) >= 2:
        return "Cliquer l'élément WebGUI %s" % rest(1)
    if kw == "Fill Sid Input" and len(cells) >= 3:
        return "Saisir %s dans l'élément WebGUI %s" % (
            md_code(rf_unescape_value(cells[2])), rest(1, 2))
    if kw == "Ui5 Text Should Be" and len(cells) >= 3:
        return "Vérifier que %s affiche %s" % (
            rest(2), md_code(rf_unescape_value(cells[1])))
    if kw.endswith("Should Be Visible") and len(cells) >= 2:
        return "Vérifier la présence de %s" % rest(1)
    if kw in ("Wait For UI5 Ready", "Wait For Load State"):
        return "Attendre la fin du chargement"
    if kw == "Keyboard Key" and len(cells) >= 2:
        return "Envoyer la touche %s" % md_code(cells[-1])
    if kw in ("Open App By Intent", "Open Fiori App") and len(cells) >= 2:
        return "Ouvrir l'app Fiori %s" % md_code(cells[1])
    if kw == "Log In Via Identity Provider":
        return "Se connecter via le fournisseur d'identité"
    if kw == "Open Api Session" and len(cells) >= 2:
        return "Ouvrir la session API %s" % md_code(cells[1])
    if kw == "Get Odata Entities" and len(cells) >= 2:
        return "Lire les entités OData %s" % md_code(cells[1])
    if kw == "Get Odata Count" and len(cells) >= 2:
        return "Compter les entités OData %s" % md_code(cells[1])
    if kw == "Post Odata" and len(cells) >= 2:
        return "Envoyer (POST OData, protocole CSRF) vers %s" % md_code(cells[1])
    if kw == "Open Rfc Connection":
        return "Ouvrir la connexion RFC"
    if kw == "Call Rfc" and len(cells) >= 2:
        return "Appeler le module RFC %s" % md_code(cells[1])
    if kw == "List Api Sessions":
        return "Lister les sessions API"
    return None

def steps_to_report(steps, test_name=DEFAULT_TEST_NAME, source="",
                    screenshot_loader=None):
    """Transforme un déroulé brut en **rapport HTML de documentation**
    auto-contenu (chaîne). Chaque étape porte sa phrase métier (celle de
    l'export spec, étendue aux keywords Fiori/UI5 et API pour les déroulés
    mixtes) ET la ligne RF exacte : le rapport n'invente rien ; les
    commentaires ``# screenshot: <chemin>`` deviennent l'« écran d'arrivée »
    de l'étape précédente, image inline en data-URI via ``screenshot_loader``
    (``chemin -> (mime, octets) | None`` ; ``None`` = pas d'images)."""
    entries = []                         # {kind, human, raw, shots: [(chemin, données|None)]}
    for step in steps:
        shot = _SCREENSHOT_COMMENT.match(step)
        if shot:
            path = shot.group(1).strip()
            loaded = screenshot_loader(path) if screenshot_loader else None
            if not entries:              # capture avant tout step : état initial
                entries.append({"kind": "note", "human": "État initial",
                                "raw": None, "shots": []})
            entries[-1]["shots"].append((path, loaded))
            continue
        cells, comment = _split_step(step)
        if not cells:                    # commentaire du record (# non mappé…)
            entries.append({"kind": "note", "human": None, "raw": step, "shots": []})
            continue
        human = _humanize_step(cells, comment) or _humanize_channel_step(cells)
        entries.append({"kind": "step", "human": human,
                        "raw": _mask_secret_args(step), "shots": []})
    step_count = sum(1 for e in entries if e["kind"] == "step")

    out = ["<!doctype html>",
           '<html lang="fr">',
           "<head>",
           '<meta charset="utf-8">',
           "<title>%s</title>" % _esc(test_name),
           "<style>%s</style>" % _REPORT_CSS,
           "</head>",
           "<body>",
           "<h1>%s</h1>" % _esc(test_name),
           '<p class="meta">Rapport généré par le SAP GUI Recorder%s, '
           "%d étape(s). Documentation du déroulé enregistré : "
           "l'enregistrement brut fait foi, ce rapport n'est pas un test.</p>"
           % ((" depuis %s" % _esc(source)) if source else "", step_count),
           '<ol class="steps">']
    for entry in entries:
        if entry["kind"] == "note":
            out.append('<li class="note">%s%s</li>' % (
                _esc(entry["human"]) if entry["human"] else "",
                ("<code>%s</code>" % _esc(entry["raw"])) if entry["raw"] else ""))
            out.extend(_report_shots(entry["shots"]))
            continue
        out.append("<li>")
        if entry["human"]:
            out.append('<p class="human">%s</p>' % _esc(_strip_md_code(entry["human"])))
        out.append('<p class="raw"><code>%s</code></p>' % _esc(entry["raw"]))
        out.extend(_report_shots(entry["shots"]))
        out.append("</li>")
    out += ["</ol>", "</body>", "</html>"]
    return "\n".join(out) + "\n"


def _report_shots(shots):
    """Fragments HTML des captures d'une étape : image inline (data-URI) quand
    le chargeur l'a lue, mention honnête sinon : jamais de silence."""
    frags = []
    for path, loaded in shots:
        if loaded:
            mime, data = loaded
            frags.append('<figure><img src="data:%s;base64,%s" '
                         'alt="Écran d\'arrivée"><figcaption>Écran d\'arrivée '
                         ": %s</figcaption></figure>"
                         % (mime, base64.b64encode(data).decode("ascii"),
                            _esc(path)))
        else:
            frags.append('<p class="missing">Capture introuvable ou illisible : '
                         "<code>%s</code></p>" % _esc(path))
    return frags


def _strip_md_code(text):
    """Retire les code spans Markdown d'une phrase de `_humanize_step` (écrite
    pour l'export spec) : en HTML les backticks seraient du bruit, la valeur
    reste : ``Saisir `T000` dans…`` -> ``Saisir T000 dans…``."""
    return re.sub(r"(`+)( ?)(.*?)\2\1", r"\3", text)
