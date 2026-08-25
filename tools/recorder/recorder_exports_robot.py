"""Export resource-first du recorder bureau : la paire .resource + .robot.

`steps_to_resource_first` : variables ``${LOC_...}`` + keywords metier dans
la resource, suite SANS aucun id brut (convention #1), steps `--semantic`
rendus AUTO-REPARABLES (`Resolve Element With Healing ... label=...`).

Extrait de ``recorder_exports.py`` (convention #13).
"""
import re

from recorder_exports_core import (
    DEFAULT_TEST_NAME,
    _split_step,
    build_record_header,
    locator_slug,
)



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
