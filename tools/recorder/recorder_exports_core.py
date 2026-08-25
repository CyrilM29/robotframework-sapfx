"""Exports du recorder bureau, SOCLE (prive) : modele des enregistrements.

Les primitives texte -> texte partagees par tous les formats d'export :
en-tete de suite rejouable (`build_record_header`), lecture/reecriture du
corps enregistre (`parse_recorded_body`/`replace_recorded_steps`,
`count_test_cases`), decoupage d'un step en cellules RF (`_split_step`),
slug de localisateur (`locator_slug`) et l'echappement RF des VALEURS
(`rf_escape_value`/`rf_unescape_value`, l'inverse exact applique au replay).

Extrait de ``recorder_exports.py`` (convention #13), qui reste la porte
d'entree et re-exporte tout.
"""
import re

DEFAULT_TEST_NAME = "Scénario enregistré"

_SUITE_SETTINGS = (
    "*** Settings ***\n"
    "Documentation       Enregistré par SAP GUI Recorder. Replay : SAP Logon ouvert,\n"
    "...                 session connectée (le Suite Setup s'y rattache).\n"
    "Library             SapEccLibrary\n"
    "\n"
    # Attach To Open Session (et non Connect To Session : celui-ci n'obtient que
    # le moteur, jamais la session : replay impossible ; découvert par le replay
    # live d'un export, 2026-07-19).
    "Suite Setup         Attach To Open Session\n"
    "\n")


def build_record_header(out_path, suite=False, test_name=DEFAULT_TEST_NAME,
                        resource_file=None):
    """En-tête du fichier d'enregistrement : corps nu (historique) ou suite
    complète (``--suite``) ; ``resource_file`` ajoute l'import Resource
    (export resource-first)."""
    header = "# Enregistré par SAP GUI Recorder : %s\n\n" % out_path
    if suite or resource_file:
        settings = _SUITE_SETTINGS
        if resource_file:
            settings = settings.replace(
                "Library             SapEccLibrary\n",
                "Library             SapEccLibrary\n"
                "Resource            %s\n" % resource_file)
        header += settings
    header += "*** Test Cases ***\n%s\n" % test_name
    return header


def parse_recorded_body(text):
    """Relit un fichier d'enregistrement (corps nu OU suite complète) et
    retourne ``(nom du test, [étapes])`` : les étapes sont les lignes indentées
    du premier test, commentaires inclus (``# screenshot: …``)."""
    name = None
    steps = []
    in_cases = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("*** test cases"):
            in_cases = True
            continue
        if not in_cases or not stripped:
            continue
        if stripped.startswith("***"):
            break
        if line[:1] in (" ", "\t"):
            if name is not None:
                steps.append(stripped)
        elif stripped.startswith("#"):
            continue
        elif name is None:
            name = stripped
        else:
            break                        # deuxième test : hors contrat du recorder
    return (name or DEFAULT_TEST_NAME), steps


def count_test_cases(text):
    """Nombre de tests d'un fichier d'enregistrement (lignes non indentées de la
    section ``*** Test Cases ***``).

    `parse_recorded_body` ne rend QUE le premier test (contrat du recorder) :
    un fichier multi-scénarios (export ``+test`` du recorder web, suite écrite
    à la main) serait rejoué à un tiers sans que rien ne le dise. Le compte
    permet au replay de l'annoncer au lieu de laisser croire qu'il a tout
    rejoué."""
    count = 0
    in_cases = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("*** test cases"):
            in_cases = True
            continue
        if not in_cases or not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("***"):
            break
        if line[:1] not in (" ", "\t"):
            count += 1
    return count


def replace_recorded_steps(text, steps):
    """Réécrit les étapes d'un fichier d'enregistrement en conservant tout
    l'en-tête (jusqu'à la ligne du nom de test incluse). Socle de l'édition de
    steps dans la GUI (« Enregistrer » du panneau)."""
    out = []
    in_cases = False
    for line in text.splitlines():
        stripped = line.strip()
        out.append(line)
        if stripped.lower().startswith("*** test cases"):
            in_cases = True
            continue
        if (in_cases and stripped and line[:1] not in (" ", "\t")
                and not stripped.startswith("#")):
            break                        # ligne du nom de test : l'en-tête s'arrête ici
    for step in steps:
        out.append("    " + step)
    return "\n".join(out) + "\n"


# Préfixes de type des ids SAP GUI (ctxtDATABROWSE-… -> DATABROWSE-…).
_LOC_PREFIX = re.compile(
    r"^(ctxt|txt|pwd|cmb|chk|rad|btn|lbl|tbl|cnt|sub|tabp|tabs|shellcont|shell|okcd)",
    re.IGNORECASE)


def locator_slug(eid):
    """Nom lisible dérivé d'un id SAP GUI : dernier segment, préfixe de type
    retiré, en MAJUSCULES_SOULIGNÉES (``wnd[0]/usr/ctxtDATABROWSE-TABLENAME``
    -> ``DATABROWSE_TABLENAME``). Jamais vide."""
    tail = (eid or "").rstrip("/").rsplit("/", 1)[-1]
    tail = _LOC_PREFIX.sub("", tail)
    slug = re.sub(r"[^0-9A-Za-z]+", "_", tail).strip("_").upper()
    return slug or "ELEMENT"


# Séparateur de cellules Robot Framework : une tabulation, ou DEUX espaces au
# moins. Les deux recorders écrivent quatre espaces, mais un déroulé ÉDITÉ
# (panneau de steps de la GUI, retouche à la main, fichier venu d'ailleurs) est
# du RF valide quelconque. Un `split("    ")` littéral rendait alors la ligne
# entière en UNE cellule (séparation à 2, 3 espaces ou tabulation) : keyword
# introuvable au replay ; ou des cellules à espace de tête (5 espaces et plus) :
# valeur silencieusement fausse.
_CELL_SEP = re.compile(r"\t+| {2,}")
# Un espace VOLONTAIRE dans une valeur est échappé ``\ `` par `rf_escape_value` :
# il est mis à l'abri du découpage (sentinelle) puis restitué, sans quoi une
# valeur à espaces multiples ou à espace final serait coupée par son propre
# échappement.
_SPACE_SENTINEL = "\x00"


def _split_step(step):
    """Cellules RF d'une étape (séparateur : tabulation, ou 2 espaces et plus),
    commentaire de fin mis à part : ``('Send Vkey    0    # F8')`` ->
    ``(['Send Vkey', '0'], '# F8')``."""
    protected = (step or "").replace("\\ ", _SPACE_SENTINEL)
    cells = [c.replace(_SPACE_SENTINEL, "\\ ")
             for c in _CELL_SEP.split(protected) if c != ""]
    comment_at = next((i for i, c in enumerate(cells) if c.startswith("#")), None)
    if comment_at is None:
        return cells, ""
    return cells[:comment_at], "    ".join(cells[comment_at:])


# --- échappement Robot Framework des VALEURS enregistrées ----------------------
# Une valeur lue dans SAP GUI (saisie, texte de champ assertionné) part telle
# quelle dans un .robot : sans échappement, ``${...}`` y serait résolu comme
# variable RF au replay, un run de 2+ espaces couperait la cellule, un ``#`` de
# tête ouvrirait un commentaire et ``mot=...`` deviendrait un argument nommé.
# Miroir exact du rfEscape/rfUnescape du recorder web (`_ui5_js.py`) ; le
# ``--replay`` applique l'inverse avant d'invoquer le keyword.

def rf_escape_value(value):
    """Échappe une valeur pour une cellule Robot Framework (``''`` ->
    ``${EMPTY}`` : vider un champ reste un step rejouable)."""
    if value is None or value == "":
        return "${EMPTY}"
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    s = re.sub(r"([$@&%])\{", r"\\\1{", s)
    s = re.sub(r" ( +)", lambda m: " " + m.group(1).replace(" ", "\\ "), s)
    if s.startswith(" ") or s.startswith("#"):
        s = "\\" + s
    if s.endswith(" "):
        # un nombre IMPAIR de backslashes devant l'espace final = déjà échappé
        trailing_bs = re.search(r"(\\*) $", s).group(1)
        if len(trailing_bs) % 2 == 0:
            s = s[:-1] + "\\ "
    s = re.sub(r"^([A-Za-z_][A-Za-z0-9_]*)=", r"\1\\=", s)
    return s


def rf_unescape_value(token):
    """Inverse exact de `rf_escape_value` (``${EMPTY}`` -> ``''``)."""
    if token == "${EMPTY}":
        return ""
    out = []
    i = 0
    while i < len(token):
        ch = token[i]
        if ch == "\\" and i + 1 < len(token):
            nxt = token[i + 1]
            out.append({"n": "\n", "r": "\r", "t": "\t"}.get(nxt, nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# Un document généré (rapport HTML, lignes brutes des plans spec/ISTQB) ne
# montre JAMAIS un secret : les arguments nommés sensibles d'une ligne
# (``password=…``/``passwd=…`` d'`Open Api Session`/`Open Rfc Connection`,
# ajoutés à la main dans un déroulé mixte) sont masqués dans la ligne
# affichée. Les exports EXÉCUTABLES (.robot/.resource) restent fidèles : les
# recorders eux-mêmes n'émettent jamais de mot de passe (placeholder).
_SECRET_ARG = re.compile(r"\b(password|passwd)=\S+", re.IGNORECASE)


def _mask_secret_args(step):
    return _SECRET_ARG.sub(lambda m: "%s=***" % m.group(1), step)
