"""Exports documentaires du recorder bureau : plan specs/ et plan ISTQB.

`steps_to_spec` (plan Markdown au format ``specs/``, brouillon pour
sap-generator, code spans CommonMark via `md_code`) et `steps_to_istqb`
(plan de test + cas de test ISO 29119-3 : tableau Action / Donnees /
Resultat attendu + bloc ``replay`` YAML normalise, localisateur en hint ;
les rubriques de jugement restent « a completer », redigees par sap-istqb).

Extrait de ``recorder_exports.py`` (convention #13).
"""
import re
import unicodedata

from recorder_exports_core import (
    DEFAULT_TEST_NAME,
    _mask_secret_args,
    _split_step,
    locator_slug,
    rf_unescape_value,
)



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
