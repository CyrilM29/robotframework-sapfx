"""Exports post-enregistrement du recorder bureau : suite, resource-first,
spec, ISTQB, rapport HTML.

Extrait de ``sapgui_recorder.py`` (module devenu monolithique) : tout ici est
PUR (texte -> texte), sans COM ni session SAP, et testé hors SAP dans
``tests/unit/test_recorder_exports.py``. ``sapgui_recorder`` ré-exporte ces
noms : les consommateurs historiques (GUI, tests, suites Robot) ne changent
pas.
"""
import base64
import html
import os
import re
import unicodedata

# --- Exports post-enregistrement : suite complète, resource-first, spec --------
#
# Le déroulé brut (corps *** Test Cases *** aux ids techniques) est un BROUILLON.
# Trois exports le rapprochent d'un test maintenable, sans rien perdre :
#   * ``--suite``            : fichier .robot COMPLET (Settings + Suite Setup),
#     rejouable tel quel contre la session SAP GUI déjà ouverte ;
#   * ``--export-resources`` : la paire resource-first, un ``.resource`` où
#     chaque id devient une variable ``${LOC_…}`` enveloppée dans un keyword
#     métier, et la suite n'appelle plus QUE ces keywords (convention n°1 du
#     projet : aucun id brut dans les tests, et c'est la couche resources que
#     sap-healer sait réparer) ;
#   * ``--export-spec``      : un plan Markdown au format ``specs/`` (étapes en
#     langage métier, ids relégués en notes factuelles) : l'enregistrement
#     devient l'ENTRÉE du cycle plan → generate → heal au lieu d'un test figé.
# Tout est pur (texte -> texte) et testé hors SAP.

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


# keyword -> (gabarit de nom, arguments métier, gabarit de corps). ``%s`` = la
# variable ``${LOC_…}`` ; les arguments métier reçoivent les valeurs de l'étape.
_RESOURCE_WRAPPERS = {
    "Input Text": ("Saisir {slug}", ["${valeur}"],
                   "Input Text    {loc}    ${valeur}"),
    "Input Password": ("Saisir Mot De Passe {slug}", ["${mot_de_passe}"],
                       "Input Password    {loc}    ${mot_de_passe}"),
    "Click Element": ("Cliquer {slug}", [], "Click Element    {loc}"),
    "Select Checkbox": ("Cocher {slug}", [], "Select Checkbox    {loc}"),
    "Unselect Checkbox": ("Décocher {slug}", [], "Unselect Checkbox    {loc}"),
    "Select Radio Button": ("Sélectionner {slug}", [],
                            "Select Radio Button    {loc}"),
    "Select From List By Label": ("Choisir {slug}", ["${libelle}"],
                                  "Select From List By Label    {loc}    ${libelle}"),
    "Element Value Should Be": ("Vérifier {slug}", ["${valeur_attendue}"],
                                "Element Value Should Be    {loc}    ${valeur_attendue}"),
    "Element Should Be Present": ("Vérifier Présence {slug}", [],
                                  "Element Should Be Present    {loc}"),
}


def steps_to_resource_first(steps, test_name=DEFAULT_TEST_NAME,
                            resource_file="record_keywords.resource"):
    """Transforme un déroulé brut en paire **resource-first** :
    ``(texte du .resource, texte de la suite .robot)``.

    Chaque action à id connu devient un keyword métier (``Saisir
    DATABROWSE_TABLENAME``) adossé à une variable ``${LOC_…}`` dans le
    resource ; la suite n'appelle plus que ces keywords. Les lignes déjà
    métier (``Run Transaction``, ``Send Vkey``, keywords sémantiques,
    baselines visuelles, commentaires) passent inchangées : jamais de perte
    d'information."""
    variables = {}          # eid -> nom de variable
    var_order = []
    keywords = {}           # nom -> (args, [lignes de corps])
    kw_order = []
    slug_owner = {}         # slug -> eid (détection de collision)
    test_lines = []

    def var_for(eid):
        if eid in variables:
            return variables[eid]
        slug = locator_slug(eid)
        if slug_owner.get(slug, eid) != eid:      # même slug, autre id : suffixe
            n = 2
            while slug_owner.get("%s_%d" % (slug, n), eid) != eid:
                n += 1
            slug = "%s_%d" % (slug, n)
        slug_owner[slug] = eid
        name = "${LOC_%s}" % slug
        variables[eid] = name
        var_order.append(eid)
        return name

    def add_keyword(name, args, body_lines):
        if name in keywords:
            if keywords[name] == (tuple(args), tuple(body_lines)):
                return name              # même keyword déjà émis : réutilisé
            n = 2
            while ("%s %d" % (name, n)) in keywords:
                n += 1
            name = "%s %d" % (name, n)
        keywords[name] = (tuple(args), tuple(body_lines))
        kw_order.append(name)
        return name

    for step in steps:
        cells, comment = _split_step(step)
        id_hint = re.match(r"^# id: (.+)$", comment) if comment else None
        wrapper = _RESOURCE_WRAPPERS.get(cells[0]) if cells else None
        if cells and id_hint and cells[0] == "Fill Field By Label" and len(cells) >= 3:
            # Ligne sémantique du record natif --semantic : libellé ET id connus.
            # Le keyword généré naît AUTO-RÉPARABLE : résolution nominale par id,
            # réparation scorée + ancre de libellé sinon (jamais silencieuse).
            loc = var_for(id_hint.group(1))
            slug = loc[len("${LOC_"):-1]
            kw_name = add_keyword(
                "Saisir %s" % slug, ["${valeur}"],
                ["${cible}=    Resolve Element With Healing    %s    label=%s"
                 % (loc, cells[1]),
                 "Input Text    ${cible}    ${valeur}"])
            test_lines.append(kw_name + "    " + "    ".join(cells[2:]))
        elif cells and id_hint and cells[0] == "Click Button By Label" and len(cells) >= 2:
            loc = var_for(id_hint.group(1))
            slug = loc[len("${LOC_"):-1]
            kw_name = add_keyword(
                "Cliquer %s" % slug, [],
                ["${cible}=    Resolve Element With Healing    %s    label=%s"
                 % (loc, cells[1]),
                 "Click Element    ${cible}"])
            test_lines.append(kw_name)
        elif wrapper and len(cells) >= 2 and cells[1].startswith("wnd["):
            name_tpl, kw_args, body_tpl = wrapper
            eid = cells[1]
            loc = var_for(eid)
            slug = loc[len("${LOC_"):-1]
            body = body_tpl.replace("{loc}", loc)
            kw_name = add_keyword(name_tpl.format(slug=slug), kw_args, [body])
            call = [kw_name] + cells[2:2 + len(kw_args)]
            test_lines.append("    ".join(call) + (("    " + comment) if comment else ""))
        elif cells and cells[0] == "Click Toolbar Button" and len(cells) >= 3 \
                and cells[1].startswith("wnd["):
            loc = var_for(cells[1])
            btn_slug = locator_slug(cells[2])
            kw_name = add_keyword(
                "Cliquer Bouton %s" % btn_slug, [],
                ["Click Toolbar Button    %s    %s" % (loc, cells[2])])
            test_lines.append(kw_name + (("    " + comment) if comment else ""))
        elif cells and cells[0] == "Select Context Menu Item" and len(cells) >= 4 \
                and cells[1].startswith("wnd["):
            loc = var_for(cells[1])
            kw_name = add_keyword(
                "Choisir Menu %s" % locator_slug(cells[3]), [],
                ["Select Context Menu Item    %s    %s    %s"
                 % (loc, cells[2], cells[3])])
            test_lines.append(kw_name + (("    " + comment) if comment else ""))
        else:
            test_lines.append(step)      # déjà métier / commentaire / inconnu

    resource = ["*** Settings ***",
                "Documentation       Keywords générés par le SAP GUI Recorder : brouillon",
                "...                 à renommer/factoriser dans resources/ (site_keywords).",
                "Library             SapEccLibrary",
                ""]
    if var_order:
        resource.append("*** Variables ***")
        for eid in var_order:
            resource.append("%s    %s" % (variables[eid], eid))
        resource.append("")
    resource.append("*** Keywords ***")
    for kw_name in kw_order:
        args, body = keywords[kw_name]
        resource.append(kw_name)
        if args:
            resource.append("    [Arguments]    " + "    ".join(args))
        for line in body:
            resource.append("    " + line)
        resource.append("")

    suite = build_record_header("(export resource-first)", suite=True,
                                test_name=test_name, resource_file=resource_file)
    suite = suite.split("\n", 2)[2]      # retire la ligne de commentaire + vide
    suite_lines = [suite.rstrip("\n")] + ["    " + line for line in test_lines]
    return "\n".join(resource).rstrip("\n") + "\n", "\n".join(suite_lines) + "\n"


def md_code(text):
    """Code span Markdown qui reste littéral QUEL QUE SOIT le contenu (règle
    CommonMark) : la clôture est une série de backticks plus longue que toute
    série interne, et un espace de bourrage isole un contenu qui commence ou
    finit par un backtick. Protège les plans générés des métacaractères
    Markdown dans les données enregistrées : ``*LH*`` (joker SAP typique en
    écran de sélection) rendrait « LH » en italique entre simples guillemets."""
    text = str(text)
    longest = max((len(run) for run in re.findall("`+", text)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if not text or text[:1] == "`" or text[-1:] == "`" else ""
    return fence + pad + text + pad + fence


def _humanize_step(cells, comment):
    """Phrase métier française pour une étape connue, ou ``None`` (étape à
    laisser en brut). Aucun id SAP dedans (contrat ``specs/``) ; les valeurs
    sont DÉSÉCHAPPÉES pour l'affichage (le plan est en langage humain), et
    toute donnée interpolée passe en code span `md_code` (style de l'exemple
    de référence ``specs/``, et un ``*``/``_`` saisi ne met pas le plan en
    italique)."""
    kw = cells[0] if cells else ""
    if kw == "Input Text" and len(cells) >= 3:
        return "Saisir %s dans le champ %s" % (
            md_code(rf_unescape_value(cells[2])), md_code(locator_slug(cells[1])))
    if kw == "Input Password" and len(cells) >= 2:
        return ("Saisir le mot de passe dans %s (valeur à fournir au replay)"
                % md_code(locator_slug(cells[1])))
    if kw == "Click Element" and len(cells) >= 2:
        return "Cliquer %s" % md_code(locator_slug(cells[1]))
    if kw == "Click Toolbar Button" and len(cells) >= 3:
        return "Cliquer le bouton %s de la barre d'outils" % md_code(locator_slug(cells[2]))
    if kw == "Select Checkbox" and len(cells) >= 2:
        return "Cocher %s" % md_code(locator_slug(cells[1]))
    if kw == "Unselect Checkbox" and len(cells) >= 2:
        return "Décocher %s" % md_code(locator_slug(cells[1]))
    if kw == "Select Radio Button" and len(cells) >= 2:
        return "Sélectionner %s" % md_code(locator_slug(cells[1]))
    if kw == "Select From List By Label" and len(cells) >= 3:
        return "Choisir %s dans la liste %s" % (
            md_code(rf_unescape_value(cells[2])), md_code(locator_slug(cells[1])))
    if kw == "Run Transaction" and len(cells) >= 2:
        return "Lancer la transaction %s" % md_code(cells[1])
    if kw == "Send Vkey" and len(cells) >= 2:
        key = comment.lstrip("# ").strip() if comment else ""
        if cells[1] == "0" and not key:
            key = "Entrée"
        return "Envoyer la touche %s" % md_code(key or ("vkey %s" % cells[1]))
    if kw == "Element Value Should Be" and len(cells) >= 3:
        return "Vérifier que %s vaut %s" % (
            md_code(locator_slug(cells[1])), md_code(rf_unescape_value(cells[2])))
    if kw == "Element Should Be Present" and len(cells) >= 2:
        return "Vérifier la présence de %s" % md_code(locator_slug(cells[1]))
    if kw == "Screen Should Match Baseline" and len(cells) >= 2:
        return "Vérifier l'empreinte visuelle de l'écran (baseline %s)" % md_code(cells[1])
    if kw == "Fill Field By Label" and len(cells) >= 3:
        return "Saisir %s dans le champ %s" % (md_code(cells[2]), md_code(cells[1]))
    if kw == "Click Button By Label" and len(cells) >= 2:
        return "Cliquer le bouton %s" % md_code(cells[1])
    if kw == "Select Context Menu Item" and len(cells) >= 4:
        return "Choisir %s dans le menu contextuel" % md_code(cells[3])
    if kw == "Select Node" and len(cells) >= 3:
        return "Sélectionner le nœud %s de l'arbre" % md_code(cells[2])
    if kw == "Select Table Row" and len(cells) >= 3:
        return "Sélectionner la ligne %s de la grille" % md_code(cells[2])
    return None


def steps_to_spec(steps, test_name=DEFAULT_TEST_NAME,
                  system="session SAP GUI locale (à préciser)"):
    """Transforme un déroulé brut en **plan Markdown** au format ``specs/`` :
    étapes en langage métier (aucun id SAP, convention du répertoire), ids
    relevés relégués en « Points de vigilance » comme notes factuelles pour le
    sap-generator. Le plan est marqué BROUILLON : à retravailler (résultats
    attendus, données) avant génération."""
    etapes = []
    ids_seen = {}                        # id -> n° de la 1re étape qui le porte
    raw_steps = []
    for step in steps:
        if step.startswith("#"):
            continue                     # screenshots & commentaires : hors plan
        cells, comment = _split_step(step)
        human = _humanize_step(cells, comment)
        for cell in cells[1:]:
            if cell.startswith("wnd[") and cell not in ids_seen:
                ids_seen[cell] = len(etapes) + 1
        if human is None:
            # Étape inconnue : la ligne exacte ne va dans les étapes QUE si elle
            # ne porte aucun id (contrat specs/ : pas d'id dans les étapes) ;
            # sinon elle vit en « Points de vigilance », intégralement.
            if any(c.startswith("wnd[") for c in cells[1:]):
                raw_steps.append((_mask_secret_args(step), len(etapes) + 1))
                human = ("Étape technique à traduire "
                         "(ligne exacte en « Points de vigilance »)")
            else:
                human = "Étape brute à traduire : %s" % md_code(
                    _mask_secret_args(step))
        etapes.append(human)
    lines = ["# %s" % test_name,
             "",
             "> **Brouillon généré par le SAP GUI Recorder** : à retravailler",
             "> (résultats attendus, données) avant passage au sap-generator.",
             "",
             "- **Canal** : ECC (SAP GUI)",
             "- **Système / URL** : %s" % system,
             "- **Préconditions** : session SAP GUI ouverte et connectée.",
             "",
             "## Données observées",
             "",
             "- Valeurs saisies pendant l'enregistrement : voir les étapes.",
             "",
             "## Scénarios",
             "",
             "### 1. %s" % test_name,
             "- **Étapes** :"]
    for i, etape in enumerate(etapes, 1):
        lines.append("  %d. %s" % (i, etape))
    lines += ["- **Résultat attendu** : à compléter (assertions indépendantes de la locale).",
              "- **Keywords métier manquants** : à créer par le sap-generator.",
              "",
              "## Points de vigilance",
              ""]
    if ids_seen:
        lines.append("Ids relevés pendant l'enregistrement (notes factuelles "
                     "pour le générateur) :")
        lines.append("")
        for eid, num in ids_seen.items():
            lines.append("- %s (étape %d)" % (md_code(eid), num))
    else:
        lines.append("- (aucun id technique relevé)")
    if raw_steps:
        lines.append("")
        lines.append("Étapes techniques non traduites (lignes exactes, à "
                     "réécrire en langage métier) :")
        lines.append("")
        for raw, num in raw_steps:
            lines.append("- étape %d : %s" % (num, md_code(raw)))
    return "\n".join(lines) + "\n"


# --- Export ISTQB : plan de test + cas de test, humain ET rejouable -----------
#
# 5e export (`--export-istqb`) : UN document Markdown couvrant les deux niveaux
# ISTQB (plan de test : objectif, périmètre, critères d'entrée/sortie, risques ;
# cas de test : tableau Action / Données / Résultat attendu), plus un bloc
# `replay` YAML par cas de test : actions NORMALISÉES indépendantes du framework
# d'exécution (fill/click/press_key/assert_value…), cible en langage humain,
# localisateur technique relevé relégué en simple indice `hint`. Lisible par un
# humain, rejouable par une IA avec n'importe quel framework de test. Le
# recorder n'invente rien : les résultats attendus des actions restent
# « à préciser », seules les assertions posées à chaud (Ctrl+Alt+A/V) portent un
# attendu réel. L'agent sap-istqb produit le même format, en version rédigée.

# Résultat attendu affiché dans le tableau humain, par action normalisée ; les
# actions absentes de la table reçoivent le générique (clics, sélections). Les
# formulations restent indépendantes de la locale (type de message, jamais un
# texte localisé), conformément à la convention n°3.
_ISTQB_GENERIC_EXPECTED = ("L'action s'exécute sans message d'erreur "
                           "(type de message E) ; à préciser")
_ISTQB_TABLE_EXPECTED = {
    "run_transaction": "L'écran attendu s'affiche (à préciser)",
    "fill": "La valeur est acceptée",
    "fill_secret": "La valeur est acceptée",
    "press_key": "L'écran suivant s'affiche (à préciser)",
    "assert_value": "Valeur conforme (assertion indépendante de la locale)",
    "assert_present": "L'élément est présent",
    "assert_visual": "L'écran correspond à la baseline enregistrée",
    "raw": "à préciser",
}


def _istqb_slug(name):
    """Slug kebab-case d'un nom de test pour l'identifiant du plan, accents
    translittérés (``Scénario enregistré`` -> ``scenario-enregistre``, attrapé
    au premier test live : le slug naïf mangeait les lettres accentuées).
    Jamais vide."""
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^0-9A-Za-z]+", "-", text).strip("-").lower()
    return slug or "enregistrement"


def _yq(text):
    """Scalaire YAML à guillemets simples (le seul échappement : doubler les
    guillemets simples internes) : sûr quel que soit le contenu enregistré."""
    return "'" + str(text).replace("'", "''") + "'"


def _md_cell(text):
    """Contenu d'une cellule de tableau Markdown : les ``|`` sont échappés
    (même à l'intérieur d'un code span, un pipe nu couperait la ligne)."""
    return str(text).replace("|", "\\|")


def _istqb_step(cells, comment):
    """Étape normalisée du bloc replay (``action``/``target``/``value``/
    ``expected``/``hint``/``note``) pour un keyword ECC connu, ou ``None``
    (étape à laisser en brut). ``expected`` n'est posé QUE sur les assertions
    (l'attendu machine) : le recorder n'invente pas de résultat attendu."""
    kw = cells[0] if cells else ""

    def slug(eid):
        return locator_slug(eid).lower()

    def gui_hint(eid):
        return {"engine": "sapgui-id", "locator": eid}

    if kw == "Run Transaction" and len(cells) >= 2:
        return {"action": "run_transaction", "value": cells[1]}
    if kw == "Input Text" and len(cells) >= 3:
        return {"action": "fill", "target": "champ %s" % slug(cells[1]),
                "value": rf_unescape_value(cells[2]), "hint": gui_hint(cells[1])}
    if kw == "Input Password" and len(cells) >= 2:
        return {"action": "fill_secret", "target": "champ %s" % slug(cells[1]),
                "note": "mot de passe à fournir au replay, jamais enregistré",
                "hint": gui_hint(cells[1])}
    if kw == "Click Element" and len(cells) >= 2:
        return {"action": "click", "target": slug(cells[1]),
                "hint": gui_hint(cells[1])}
    if kw == "Click Toolbar Button" and len(cells) >= 3:
        return {"action": "click",
                "target": "bouton %s de la barre d'outils" % slug(cells[2]),
                "hint": gui_hint(cells[2])}
    if kw == "Select Checkbox" and len(cells) >= 2:
        return {"action": "check", "target": slug(cells[1]),
                "hint": gui_hint(cells[1])}
    if kw == "Unselect Checkbox" and len(cells) >= 2:
        return {"action": "uncheck", "target": slug(cells[1]),
                "hint": gui_hint(cells[1])}
    if kw == "Select Radio Button" and len(cells) >= 2:
        return {"action": "select_radio", "target": slug(cells[1]),
                "hint": gui_hint(cells[1])}
    if kw == "Select From List By Label" and len(cells) >= 3:
        return {"action": "select", "target": "liste %s" % slug(cells[1]),
                "value": rf_unescape_value(cells[2]), "hint": gui_hint(cells[1])}
    if kw == "Send Vkey" and len(cells) >= 2:
        key = comment.lstrip("# ").strip() if comment else ""
        if cells[1] == "0" and not key:
            key = "Entrée"
        return {"action": "press_key", "value": key or ("vkey %s" % cells[1])}
    if kw == "Element Value Should Be" and len(cells) >= 3:
        return {"action": "assert_value", "target": "champ %s" % slug(cells[1]),
                "expected": rf_unescape_value(cells[2]), "hint": gui_hint(cells[1])}
    if kw == "Element Should Be Present" and len(cells) >= 2:
        return {"action": "assert_present", "target": slug(cells[1]),
                "hint": gui_hint(cells[1])}
    if kw == "Screen Should Match Baseline" and len(cells) >= 2:
        return {"action": "assert_visual", "value": cells[1]}
    if kw == "Fill Field By Label" and len(cells) >= 3:
        hint = {"engine": "sapgui-label", "locator": cells[1]}
        matched = re.match(r"#\s*id:\s*(\S+)", comment or "")
        if matched:                      # l'id technique du mode --semantic
            hint = {"engine": "sapgui-id", "locator": matched.group(1)}
        return {"action": "fill", "target": "champ « %s »" % cells[1],
                "value": rf_unescape_value(cells[2]), "hint": hint}
    if kw == "Click Button By Label" and len(cells) >= 2:
        return {"action": "click", "target": "bouton « %s »" % cells[1],
                "hint": {"engine": "sapgui-label", "locator": cells[1]}}
    if kw == "Select Context Menu Item" and len(cells) >= 4:
        return {"action": "select_menu_item", "target": slug(cells[1]),
                "value": cells[3], "hint": gui_hint(cells[1])}
    if kw == "Select Node" and len(cells) >= 3:
        return {"action": "select_node", "target": slug(cells[1]),
                "value": cells[2], "hint": gui_hint(cells[1])}
    if kw == "Select Table Row" and len(cells) >= 3:
        return {"action": "select_row", "target": slug(cells[1]),
                "value": cells[2], "hint": gui_hint(cells[1])}
    return None


def _istqb_yaml_lines(struct):
    """Lignes YAML d'une étape du bloc replay (indentation de liste incluse)."""
    lines = ["  - action: %s" % struct["action"]]
    for key in ("target", "value", "expected", "line", "note"):
        if struct.get(key) is not None:
            lines.append("    %s: %s" % (key, _yq(struct[key])))
    hint = struct.get("hint")
    if hint:
        lines.append("    hint: {engine: %s, locator: %s}"
                     % (_yq(hint["engine"]), _yq(hint["locator"])))
    return lines


def steps_to_istqb(steps, test_name=DEFAULT_TEST_NAME,
                   system="session SAP GUI locale (à préciser)", source=""):
    """Transforme un déroulé brut en **plan de test + cas de test ISTQB**
    (chaîne Markdown) : sections plan (objectif, préconditions, critères,
    risques), un cas de test avec tableau Action / Données / Résultat attendu,
    et son bloc ``replay`` YAML aux actions normalisées (rejouable par une IA
    quel que soit le framework). Les mentions « à compléter/préciser » restent
    apparentes : le recorder documente l'observé, il n'invente rien."""
    rows = []                            # (phrase humaine, données, attendu)
    structs = []
    values = []
    for step in steps:
        if step.startswith("#"):
            continue                     # screenshots & commentaires : hors plan
        cells, comment = _split_step(step)
        if not cells:
            continue
        struct = _istqb_step(cells, comment)
        if struct is None:
            masked = _mask_secret_args(step)
            struct = {"action": "raw", "line": masked,
                      "note": "étape non traduite : ligne Robot Framework exacte"}
            human = "Étape non traduite : %s" % md_code(masked)
        else:
            human = _humanize_step(cells, comment) or struct["action"]
        action = struct["action"]
        if action in ("fill", "select") and struct.get("value"):
            values.append(struct["value"])
        data = struct.get("value") or \
            (struct.get("expected") if action.startswith("assert") else "") or ""
        if action == "press_key":
            data = ""                    # la touche est l'action, pas une donnée
        rows.append((human, md_code(data) if data else "",
                     _ISTQB_TABLE_EXPECTED.get(action, _ISTQB_GENERIC_EXPECTED)))
        structs.append(struct)
    origin = md_code(source) if source else "enregistrement local"
    lines = ["# Plan de test ISTQB : %s" % test_name,
             "",
             "> Généré par le SAP GUI Recorder depuis %s." % origin,
             "> Document de conception de test (ISTQB / ISO 29119-3) : lisible",
             "> par un humain, rejouable par une IA via le bloc `replay` de",
             "> chaque cas de test, indépendant du framework d'exécution. Les",
             "> mentions « à compléter / à préciser » sont à renseigner avant",
             "> usage formel (l'agent sap-istqb peut rédiger ce document).",
             "",
             "- **Identifiant** : TP-%s" % _istqb_slug(test_name),
             "- **Canal** : ECC (SAP GUI)",
             "- **Système** : %s" % system,
             "- **Références** : %s" % origin,
             "",
             "## 1. Objectif et périmètre",
             "",
             "- **Objectif** : à compléter (constaté : déroulé enregistré ci-dessous).",
             "- **Éléments à tester** : à compléter.",
             "- **Hors périmètre** : à compléter.",
             "",
             "## 2. Préconditions et données de test",
             "",
             "- Session SAP GUI ouverte et connectée.",
             "- Valeurs observées pendant l'enregistrement : %s."
             % (", ".join(md_code(v) for v in values) if values else "aucune"),
             "",
             "## 3. Critères d'entrée / de sortie",
             "",
             "- **Entrée** : système accessible, préconditions satisfaites.",
             "- **Sortie** : tous les cas de test exécutés, résultats attendus confirmés.",
             "",
             "## 4. Cas de test",
             "",
             "### TC-01 : %s" % test_name,
             "",
             "- **Priorité** : à compléter",
             "",
             "| # | Action | Données | Résultat attendu |",
             "|---|--------|---------|------------------|"]
    for i, (human, data, expected) in enumerate(rows, 1):
        lines.append("| %d | %s | %s | %s |"
                     % (i, _md_cell(human), _md_cell(data), _md_cell(expected)))
    lines += ["",
              "- **Postconditions** : à compléter.",
              "",
              "Bloc rejouable (actions normalisées ; les `hint` sont les",
              "localisateurs relevés au moment de l'enregistrement,",
              "susceptibles de dériver) :",
              "",
              "```yaml",
              "test_case: TC-01",
              "title: %s" % _yq(test_name),
              "channel: sap-gui",
              "steps:"]
    for struct in structs:
        lines.extend(_istqb_yaml_lines(struct))
    lines += ["```",
              "",
              "## 5. Traçabilité",
              "",
              "| Cas de test | Source | Exigence / spec |",
              "|---|---|---|",
              "| TC-01 | %s, étapes 1 à %d | à relier |"
              % (_md_cell(origin), len(rows)),
              "",
              "## 6. Risques et points de vigilance",
              "",
              "- Les localisateurs des `hint` datent de l'enregistrement : les",
              "  re-vérifier en cas de dérive de l'écran (healing, sentinelle).",
              "- Ne jamais rejouer avec des attentes fixes (time.sleep) : attendre",
              "  les conditions d'écran (fin du sablier, élément présent)."]
    return "\n".join(lines) + "\n"


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


# Un document généré (rapport HTML, lignes brutes des plans spec/ISTQB) ne
# montre JAMAIS un secret : les arguments nommés sensibles d'une ligne
# (``password=…``/``passwd=…`` d'`Open Api Session`/`Open Rfc Connection`,
# ajoutés à la main dans un déroulé mixte) sont masqués dans la ligne
# affichée. Les exports EXÉCUTABLES (.robot/.resource) restent fidèles : les
# recorders eux-mêmes n'émettent jamais de mot de passe (placeholder).
_SECRET_ARG = re.compile(r"\b(password|passwd)=\S+", re.IGNORECASE)


def _mask_secret_args(step):
    return _SECRET_ARG.sub(lambda m: "%s=***" % m.group(1), step)


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

