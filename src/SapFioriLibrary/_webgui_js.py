"""Sondes PURES du canal **WebGUI** (SAP GUI for HTML / ITS).

Un chapitre à part (convention #13) : ces sondes n'ont rien à voir avec le
bundle ``__SAPFX``, qui est le socle des pages UI5. Une page WebGUI n'a pas de
runtime UI5, et une simple observation ne doit RIEN instrumenter sur la cible,
donc aucune de ces lectures n'injecte quoi que ce soit.

Ce qu'elles partagent, et qui justifie de les tenir ensemble : le SID vit dans
l'attribut ``lsdata`` sous DEUX encodages selon la version de l'ITS (JSON
``"SID":"…"`` des fixtures et anciens ITS, littéral JS ``SID:'…'`` du WebGUI
live S/4 1909, découvert par l'exploration agent du 2026-07-18 : l'ancien
sélecteur JSON-seul ne matchait RIEN sur un vrai système), et un élément est
visible quand son ``offsetParent`` n'est pas nul.

``_ui5_js`` les ré-exporte : tout consommateur historique garde son import.
"""
from importlib import resources


def _read_js_template(name):
    """Charge un gabarit JS embarqué à côté de ce module (fins de ligne LF
    garanties par ``.gitattributes``). Une copie assumée de l'utilitaire de
    ``_ui5_js`` : l'importer de là créerait un cycle, puisque ce module-ci est
    celui que ``_ui5_js`` ré-exporte."""
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


# Présence et comptage. On itère sur `[lsdata]` plutôt que d'interpoler l'id
# dans un sélecteur CSS : les crochets des ids SAP GUI y exigeraient un
# échappement fragile.
WEBGUI_COUNT_PROBE_JS = (
    "(first, second) => { const w = (second === undefined) ? first : second; "
    "if (w === null || w === undefined || w === '') "
    "return document.querySelectorAll('[lsdata]').length; "
    "const tag = 'wnd[' + String(w) + ']'; "
    "const nodes = document.querySelectorAll('[lsdata]'); let n = 0; "
    "for (let i = 0; i < nodes.length; i++) { const e = nodes[i]; "
    "if ((e.getAttribute('lsdata') || '').indexOf(tag) === -1) continue; "
    "if (e.offsetParent === null) continue; n++; } "
    "return n; }")

# Barre de menus : les ids suivent la structure `wnd[N]/mbar/menu[i]` avec le
# suffixe de rendu `-BtnChoiceMenu`, et les items DIRECTS d'un menu ouvert
# n'ont plus aucun `/` après leur préfixe (relevés live 2026-07-18).
WEBGUI_MENUS_PROBE_JS = (
    "(first, second) => { const w = (second === undefined) ? first : second; "
    "const prefix = 'wnd[' + String((w === null || w === undefined || w === '') ? 0 : w) + ']/mbar/menu['; "
    "const out = []; const nodes = document.querySelectorAll('[id]'); "
    "for (let i = 0; i < nodes.length; i++) { const n = nodes[i]; const id = String(n.id || ''); "
    "if (id.indexOf(prefix) !== 0) continue; "
    "if (id.slice(-14) !== '-BtnChoiceMenu') continue; "
    "if (n.offsetParent === null) continue; out.push(id); } "
    "return out; }")

WEBGUI_MENU_ITEMS_PROBE_JS = (
    "(first, second) => { let base = String(((second === undefined) ? first : second) || ''); "
    "if (base.slice(-14) === '-BtnChoiceMenu') base = base.slice(0, -14); "
    "const prefix = base + '/menu['; "
    "const out = []; const nodes = document.querySelectorAll('[id]'); "
    "for (let i = 0; i < nodes.length; i++) { const n = nodes[i]; const id = String(n.id || ''); "
    "if (id.indexOf(prefix) !== 0) continue; "
    "if (id.slice(prefix.length).indexOf('/') !== -1) continue; "
    "if (n.offsetParent === null) continue; out.push(id); } "
    "return out; }")


# Textes BRUTS de la zone info système d'une session WebGUI. Les ids sont
# techniques et stables ; leur contenu mêle un libellé traduit et la valeur,
# que `sapfx_common.system_identity.webgui_identity` sépare par la FORME.
WEBGUI_IDENTITY_PROBE_JS = (
    "() => { const out = {}; "
    "const cles = ['SYSTEM', 'CLIENT', 'USER', 'TRANSACTION', 'DYNPRO']; "
    "for (let i = 0; i < cles.length; i++) { "
    "const e = document.getElementById("
    "'sysInfoAreaMenuItemSAPITS_MBAR_' + cles[i]); "
    "out[cles[i].toLowerCase()] = e ? "
    "String(e.innerText || e.textContent || '').replace(/\\s+/g, ' ').trim() "
    ": ''; } return out; }")

# Les deux sondes assez longues pour vivre dans leur propre gabarit : la
# lecture d'une grille ALV, et la perception d'un écran de sélection SE16
# (champs et libellés avec leur rectangle, appariés côté Python).
WEBGUI_GRID_PROBE_JS = _read_js_template("_webgui_grid.js.tpl").strip()
WEBGUI_SELECTION_PROBE_JS = _read_js_template("_webgui_selection.js.tpl").strip()
