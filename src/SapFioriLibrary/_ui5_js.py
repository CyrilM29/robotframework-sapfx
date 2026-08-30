"""Bundle JavaScript en page pour la résolution et la capture de contrôles UI5.

Porté (et simplifié pour fonctionner comme un bundle injecté unique, sans fork de Playwright)
depuis **playwright-sap** par Arpit Sureka, https://github.com/ArpitSureka/playwright-sap
Sous licence Apache-2.0. Voir le fichier NOTICE du projet.

Techniques adoptées depuis ce projet :
  * un *arbre de contrôles* UI5 reflétant la hiérarchie des contrôles, permettant des localisateurs
    XPath hiérarchiques (`//Table//Button[@text='Create']`) : bien plus expressifs
    qu'un parcours à plat du registre ;
  * extraction des propriétés propres et héritées via les métadonnées du contrôle ;
  * un comparateur de propriétés robuste (sous-chaîne insensible à la casse, plus /regex/) ;
  * navigation depuis l'élément racine d'un contrôle jusqu'à l'élément interne interactif ;
  * une liste de propriétés autorisées ordonnée par priorité, utilisée par le Spy pour
    choisir un sélecteur stable.

Le bundle définit l'espace de noms `window.__SAPFX`, **versionné par le contenu** : une
réinstallation de la MÊME version ne fait rien (le cas courant, à chaque appel de keyword),
une version différente REMPLACE celle qui est en place. Sans ce numéro, une page gardait à
vie le premier bundle reçu, et une bibliothèque mise à jour en cours de session (hot-swap
rf-mcp) échouait en accusant le keyword appelé. `build_call()` enveloppe une
méthode de l'espace de noms dans une expression de fonction que `Evaluate JavaScript` du navigateur
peut exécuter. Le modèle de sélecteur Python pur réside dans `_ui5_runtime.py`.
"""

import hashlib
from importlib import resources

# Propriétés ordonnées par priorité à placer dans l'arbre / à utiliser comme sélecteur,
# portées depuis playwright-sap `allowedRolesAndProperties.ts`. Classées par utilité.
ALLOWED_PROPERTY_PRIORITY = [
    "text", "title", "viewName", "value", "src", "key",
    "icon", "number", "description", "headerText", "href", "label",
    "selectedKey", "placeholder", "target", "name", "header", "tooltip",
    "html", "htmlText", "alt", "subtitle", "info", "state", "valueStateText",
    "noDataText", "count", "status", "design", "type", "level", "intro",
]

# Propriétés portant de façon fiable un texte significatif pour l'utilisateur (idéales pour un sélecteur stable).
OBVIOUS_TEXT_PROPERTIES = [
    "text", "title", "value", "description", "headerText", "header", "htmlText",
    "noDataText",
]

# Types de contrôles adressables par type seul (sans propriété), par ex. pour nth().
ALLOW_WITHOUT_PROPERTIES = [
    "SearchField", "PullToRefresh", "Row", "ColumnListItem", "Column",
    "CustomListItem", "GridListItem", "StandardListItem", "Table", "List",
    "Page", "ToolbarSeparator",
]


def _js_string_array(items):
    return "[" + ",".join("'%s'" % i for i in items) + "]"


def _read_js_template(name):
    """Charge un gabarit JS embarqué dans le paquet (fichier ``.js.tpl`` à
    côté de ce module) : le JS garde coloration, diffs lisibles et outillage
    JS ; le Python n'héberge plus des milliers de lignes de chaîne. Fins de
    ligne LF garanties par ``.gitattributes`` (le gabarit du bundle est
    formaté ensuite par ``%`` : ses ``%s`` sont les deux listes autorisées)."""
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


# Picto aicabra (medaillon du projet, assets/logo.png redimensionne 28px) embarque
# en data-URI pour le panneau du recorder : le bundle reste auto-contenu (aucune
# requete reseau, CSP-safe ; si une CSP img-src stricte bloque le data:, l'onerror
# masque l'image, purement cosmetique). Regenere en place par gen_icons.py.
_AICABRA_ICON = (
    "data:image/png;base64,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"
    "AOp5q7AAAAAElFTkSuQmCC"
)


# Marqueur remplacé, APRÈS le formatage `%`, par l'empreinte du bundle : le
# calculer sur le gabarit formaté (marqueur encore en place) le rend déterministe,
# là où une empreinte du texte final serait circulaire.
_VERSION_TOKEN = "__SAPFX_BUNDLE_VERSION__"


def bundle_version(source):
    """Empreinte courte et stable d'un texte de bundle (12 hexa de SHA-256).

    Pourquoi une empreinte du CONTENU plutôt que la version du paquet : le
    bundle doit être remplacé dès qu'il change, y compris entre deux versions
    non publiées (travail en cours, hot-swap dans un serveur rf-mcp), et ne doit
    PAS être réinstallé quand il n'a pas bougé."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


# Le bundle injecté. Idempotent ET remplaçable : la garde en tête compare la
# VERSION installée dans la page à celle-ci. Le JS vit dans les gabarits
# _ui5_bundle_*.js.tpl (convention #13 : un chapitre par fichier, concaténés
# ICI dans l'ordre en un seul IIFE ; gabarit % : les deux %s sont les listes
# autorisées).
_BUNDLE_TEMPLATES = ("_ui5_bundle_core.js.tpl",
                     "_ui5_bundle_info.js.tpl",
                     "_ui5_bundle_shadow.js.tpl",
                     "_ui5_bundle_capture.js.tpl",
                     "_ui5_bundle_engines.js.tpl")
_BUNDLE_SOURCE = ("".join(_read_js_template(name) for name in _BUNDLE_TEMPLATES)
                  % (_js_string_array(ALLOWED_PROPERTY_PRIORITY),
                     _js_string_array(ALLOW_WITHOUT_PROPERTIES))).strip()
BUNDLE_VERSION = bundle_version(_BUNDLE_SOURCE)
BUNDLE = _BUNDLE_SOURCE.replace(_VERSION_TOKEN, BUNDLE_VERSION)


def build_call(method):
    """Retourne une expression de fonction qui (ré)installe le bundle puis appelle
    ``window.__SAPFX.<method>(arg)``. Commence par '(' : Playwright ne *lance* pas
    un littéral de fonction commençant par un espace.

    Double forme d'appel (même fonction) :
    * sans sélecteur Browser  -> Playwright appelle ``fn(arg)`` ;
    * avec sélecteur Browser (support iframe Work Zone/cFLP) -> Playwright
      appelle ``fn(element, arg)`` et exécute la fonction **dans le contexte de
      la frame de l'élément** : ``window`` y est la fenêtre de la frame, donc le
      bundle s'installe et résout dans l'app embarquée, pas dans le shell.
    On détecte la forme au nombre d'arguments réellement reçus."""
    return ("(first, second) => { const arg = (second === undefined) ? first : second; "
            "%s; return window.__SAPFX.%s(arg); }" % (BUNDLE, method))


RESOLVE_ROLE_JS = build_call("resolveByRole")
RESOLVE_VISIBLE_ROLE_JS = build_call("resolveVisibleByRole")
RESOLVE_XPATH_JS = build_call("resolveByXPath")
RESOLVE_WC_JS = build_call("resolveByWc")
RESOLVE_DOM_JS = build_call("resolveByDom")
PAGE_COMPOSITION_JS = build_call("pageComposition")
BEST_XPATH_JS = build_call("bestXpath")
READ_TABLE_JS = build_call("readTable")
READ_PROPERTY_JS = build_call("readProperty")
OPEN_POPUPS_JS = build_call("openPopups")
DIALOG_BUTTON_JS = build_call("dialogButton")
DUMP_TREE_JS = build_call("dumpTree")
IDLE_STATE_JS = build_call("idleState")
GET_MESSAGES_JS = build_call("getMessages")
CONTROL_INFO_JS = build_call("controlInfo")

# Sonde de runtime UI5 AUTONOME : la seule expression du module qui n'embarque
# PAS le bundle. Toute fonction bâtie par `build_call` (ré)installe `__SAPFX`,
# donc instrumente `fetch`/`XMLHttpRequest` et accroche `MessageToast` : c'est
# voulu quand on pilote, jamais quand on se contente de REGARDER (state provider
# rf-mcp appelé après chaque étape). Cette sonde est une lecture pure, et le
# prix à payer est qu'elle duplique la logique de `isUI5()` du bundle : garder
# les deux en phase (une classe `Element` chargée via AMD, sinon le Core hérité).
UI5_RUNTIME_PROBE_JS = (
    "() => { try { const E = window.sap && sap.ui && sap.ui.require && "
    "sap.ui.require('sap/ui/core/Element'); "
    "if (E && (typeof E.getElementById === 'function' || E.registry)) return true; } "
    "catch (e) {} "
    "const c = (window.sap && sap.ui && sap.ui.getCore) ? sap.ui.getCore() : null; "
    "return !!(c && typeof c.byId === 'function'); }")

# Lecture de la configuration ushell (`window['sap-ushell-config']`), AUTONOME
# pour la même raison que la sonde de runtime : une observation ne doit rien
# modifier, or toute fonction bâtie par `build_call` (ré)installe le bundle et
# instrumente `fetch`/XHR. La configuration est LA source locale-indépendante
# d'un launchpad (elle déclare services, renderer et réglages AVANT tout
# rendu : relevé live 2026-08-26, un site Work Zone y annonce ses 24 services
# et son délai d'expiration de session). Sérialisation JSON-safe : fonctions
# écartées, cycles coupés (`<cycle>`), l'appelant Python borne la taille.
# Signature (first, second) : même double forme d'appel que `build_call`
# (Browser passe l'élément résolu en premier quand un sélecteur de frame est
# fourni), sans le bundle.
USHELL_CONFIG_PROBE_JS = (
    "(first, second) => { const path = (second === undefined) ? first : second; "
    "const cfg = window['sap-ushell-config']; "
    "if (!cfg) return { __no_config: true }; "
    "let target = cfg; "
    "if (path) { const parts = String(path).split('.'); "
    "for (let i = 0; i < parts.length; i++) { "
    "if (target === null || target === undefined || typeof target !== 'object') "
    "{ target = undefined; break; } "
    "target = target[parts[i]]; } } "
    "if (target === undefined) return { __missing_path: String(path), "
    "__known_keys: Object.keys(cfg || {}).slice(0, 40) }; "
    "const seen = new WeakSet(); "
    "const text = JSON.stringify(target, (k, v) => { "
    "if (typeof v === 'function') return undefined; "
    "if (v && typeof v === 'object') { "
    "if (seen.has(v)) return '<cycle>'; seen.add(v); } "
    "return v; }); "
    "return text === undefined ? null : JSON.parse(text); }")

# --- Sondes launchpad (ushell), page et WebGUI : AUTONOMES -------------------
# Toutes ces sondes sont des lectures PURES sans bundle, pour la même raison
# que UI5_RUNTIME_PROBE_JS : une observation ne doit rien modifier dans la
# page. Elles sont nées dans des page objects (JS inline dupliqué entre
# resources/page_objects/abap_flp.resource et workzone_*.resource) et ont été
# promues ici au titre de la convention #12. Les services ushell répondent en
# promesse (`getServiceAsync`) : le Evaluate JavaScript de Browser attend la
# promesse retournée ; l'adaptateur ABAP livre certains résultats en
# `progress` (jQuery Deferred), les sondes acceptent les deux formes. Même
# double forme d'appel (first, second) que `build_call` pour les sondes à
# argument (portée de frame : Browser passe l'élément résolu en premier).

FLP_CONTAINER_PROBE_JS = (
    "() => !!(window.sap && sap.ushell && sap.ushell.Container)")

FLP_USER_PROBE_JS = (
    "() => { const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getUser !== 'function') return { __no_container: true }; "
    "const u = C.getUser(); "
    "return { id: String(u && u.getId ? u.getId() : ''), "
    "language: String(u && u.getLanguage ? u.getLanguage() : ''), "
    "theme: String(u && u.getTheme ? u.getTheme() : '') }; }")

FLP_SERVICE_PROBE_JS = (
    "async (first, second) => { const name = (second === undefined) ? first : second; "
    "const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return false; "
    "try { const s = await C.getServiceAsync(String(name)); return !!s; } "
    "catch (e) { return false; } }")

FLP_APPS_PROBE_JS = (
    "async () => { const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return { __no_container: true }; "
    "let s; try { s = await C.getServiceAsync('SearchableContent'); } "
    "catch (e) { return { __no_service: String((e && e.message) || e || '') }; } "
    "if (!s || typeof s.getApps !== 'function') return { __no_service: 'SearchableContent sans getApps' }; "
    "const apps = await s.getApps(); "
    "return (apps || []).map(a => { const v = ((a && a.visualizations) || [])[0] || {}; "
    "const url = String(v.targetURL || ''); "
    "return { title: String((a && (a.label || a.title)) || v.title || ''), "
    "viz_title: String(v.title || ''), "
    "intent: url.replace(/^#/, '').split('?')[0], target_url: url }; }); }")

FLP_CATALOGS_PROBE_JS = (
    "async (first, second) => { const mode = (second === undefined) ? first : second; "
    "const withTiles = mode !== 'no_tiles'; "
    "const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return { __no_container: true }; "
    "let s; try { s = await C.getServiceAsync('LaunchPage'); } "
    "catch (e) { return { __no_service: String((e && e.message) || e || '') }; } "
    "const cats = await new Promise((res, rej) => { const out = []; "
    "s.getCatalogs().done(a => res(out.length ? out : (a || []))).fail(rej).progress(c => out.push(c)); }); "
    "const r = []; "
    "for (const c of cats) { const entry = { id: String(s.getCatalogId(c)), tiles: [] }; "
    "if (withTiles) { const tiles = await new Promise((res, rej) => s.getCatalogTiles(c).done(res).fail(rej)); "
    "for (const tile of (tiles || [])) { const url = String(s.getCatalogTileTargetURL(tile) || ''); "
    "entry.tiles.push({ intent: url.replace(/^#/, '').split('?')[0], target_url: url }); } } "
    "r.push(entry); } "
    "return r; }")

FLP_GROUPS_PROBE_JS = (
    "async () => { const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return { __no_container: true }; "
    "let s; try { s = await C.getServiceAsync('LaunchPage'); } "
    "catch (e) { return { __no_service: String((e && e.message) || e || '') }; } "
    "const groupes = await new Promise((res, rej) => { const out = []; "
    "s.getGroups().done(a => res(out.length ? out : (a || []))).fail(rej).progress(g => out.push(g)); }); "
    "return groupes.map(g => ({ id: String(s.getGroupId(g)), "
    "tile_count: (s.getGroupTiles(g) || []).length })); }")

FLP_INTENT_SUPPORT_PROBE_JS = (
    "async (first, second) => { const raw = (second === undefined) ? first : second; "
    "const intents = JSON.parse(String(raw || '[]')).map(String); "
    "const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return { __no_container: true }; "
    "let s; try { s = await C.getServiceAsync('CrossApplicationNavigation'); } "
    "catch (e) { return { __no_service: String((e && e.message) || e || '') }; } "
    "const hashes = intents.map(i => '#' + i); "
    "const r = await new Promise((res, rej) => s.isIntentSupported(hashes).done(res).fail(rej)); "
    "return intents.map(i => ({ intent: i, "
    "supported: !!(r['#' + i] && r['#' + i].supported) })); }")

# Le moteur UI5 est-il INACTIF (pas seulement chargé) : runtime présent (Core
# hérité OU module Element, UI5 2.x supprimant `sap.ui.getCore()`), aucune
# mise à jour d'UI en attente (`getUIDirty` quand le Core l'expose), aucun
# indicateur d'occupation visible. Le prédicat de `Wait For UI5 Ready` (couche
# resources et exports du recorder), promu ici (convention #12) : lecture pure,
# sans bundle, à la différence de `Wait For Ui5 Idle` qui instrumente le réseau.
UI5_READY_PROBE_JS = (
    "() => { const s = window.sap; if (!(s && s.ui)) return false; "
    "let E = null; "
    "try { E = s.ui.require && s.ui.require('sap/ui/core/Element'); } catch (e) {} "
    "const c = s.ui.getCore ? s.ui.getCore() : null; "
    "if (!c && !E) return false; "
    "if (c && typeof c.getUIDirty === 'function' && c.getUIDirty()) return false; "
    "const b = document.querySelectorAll('.sapUiLocalBusyIndicator, .sapMBusyDialog, #sapUiBusyIndicator'); "
    "for (let i = 0; i < b.length; i++) { if (b[i].offsetParent !== null) return false; } "
    "return true; }")

# Thème : ce que le runtime a DEMANDÉ, et ce que le document porte réellement.
# Les deux ne coïncident pas toujours, et c'est précisément ce que la sonde sert
# à voir : il existe une fenêtre transitoire, juste après un changement, où la
# classe de thème a été retirée sans que la nouvelle soit posée (mesuré live sur
# le Demo Kit OpenUI5 le 2026-08-30). Le thème demandé se lit sur le module
# `sap/ui/core/Theming` (la voie actuelle) avec repli sur la configuration du
# Core hérité, que UI5 2.x supprime. Même contrat que les autres sondes : lecture
# PURE, sans injection du bundle, une observation ne doit rien modifier.
UI5_THEME_PROBE_JS = (
    "() => { const s = window.sap; let requested = ''; "
    "try { const T = s && s.ui && s.ui.require "
    "? s.ui.require('sap/ui/core/Theming') : null; "
    "if (T && typeof T.getTheme === 'function') requested = String(T.getTheme() || ''); } "
    "catch (e) {} "
    "if (!requested) { try { const c = s && s.ui && s.ui.getCore ? s.ui.getCore() : null; "
    "const cfg = c && c.getConfiguration ? c.getConfiguration() : null; "
    "if (cfg && typeof cfg.getTheme === 'function') requested = String(cfg.getTheme() || ''); } "
    "catch (e) {} } "
    "return { requested: requested, "
    "classes: String(document.documentElement.className || '') }; }")

IFRAMES_PROBE_JS = (
    "() => Array.from(document.querySelectorAll('iframe'))"
    ".map(f => ({ id: String(f.id || ''), src: String(f.src || '') }))")

PAGE_LANGUAGES_PROBE_JS = (
    "() => ({ document: String(document.documentElement.lang || ''), "
    "navigator: String(navigator.language || '') })")

# WebGUI (SAP GUI for HTML) : présence et menus. Le témoin de présence est le
# nombre d'éléments porteurs de `lsdata` (l'attribut où vit le SID) ; les ids
# de la barre de menus suivent la structure `wnd[N]/mbar/menu[i]` avec le
# suffixe de rendu `-BtnChoiceMenu`, et les items DIRECTS d'un menu ouvert
# n'ont plus aucun `/` après leur préfixe (relevés live 2026-07-18). Un
# élément est visible quand son `offsetParent` n'est pas null. On itère sur
# `[id]` plutôt que d'interpoler l'id dans un sélecteur CSS : les crochets des
# ids SAP GUI y exigeraient un échappement fragile.
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


def sid_xpath(sid):
    """Sélecteur navigateur pour un élément SAP WebGUI par son ``SID`` stable.

    Les éléments WebGUI (SAP GUI for HTML) portent un attribut ``lsdata`` où le ``SID``
    (``wnd[0]/usr/...``, le même espace d'ids que le scripting SAP GUI) apparaît sous DEUX
    encodages constatés : JSON ``"SID":"…"`` (fixtures, anciens ITS) ou littéral JS ``SID:'…'``
    (clé non citée, guillemets simples : le WebGUI live S/4 1909, découvert par l'exploration
    agent du 2026-07-18 : l'ancien sélecteur JSON-seul ne matchait RIEN sur un vrai système).
    On compare donc avec deux ``contains()`` XPath, un par encodage. ``sid`` ne doit jamais
    contenir de guillemet (les ids SAP GUI n'en ont jamais) : un guillemet casserait le
    littéral XPath et pourrait rediriger le sélecteur vers un élément arbitraire de la page,
    donc on le rejette plutôt que de l'interpoler tel quel."""
    if "'" in sid or '"' in sid:
        raise ValueError("Invalid SAP GUI SID (must not contain a quote character): %r" % sid)
    return ("xpath=//*[contains(@lsdata, '\"SID\":\"%s\"')"
            " or contains(@lsdata, \"SID:'%s'\")]" % (sid, sid))


# Extrait Spy DevTools autonome, généré depuis le même BUNDLE afin que la logique de capture
# ne diverge jamais du résolveur de la bibliothèque. `tools/recorder_web/recorder_snippet.js`
# est cette chaîne avec un commentaire d'en-tête ; `tests/unit/test_sid_and_spy.py` vérifie que
# le fichier reste synchronisé.
# Même règle que le bundle (convention #13) : le listener du Spy vit dans les
# gabarits _ui5_spy_*.js.tpl, un chapitre par fichier (panneau, exports,
# replay/import, record), concaténés ici dans l'ordre en un seul IIFE.
_SPY_TEMPLATES = ("_ui5_spy_core.js.tpl",
                  "_ui5_spy_exports.js.tpl",
                  "_ui5_spy_replay.js.tpl",
                  "_ui5_spy_record.js.tpl")
_SPY_LISTENER = "".join(_read_js_template(name) for name in _SPY_TEMPLATES).strip()

_SPY_HEADER = """\
/*
 * Recorder de localisation UI5 / WebGUI : survolez pour surligner, cliquez pour capturer,
 * ou « rec » pour enregistrer un déroulé d'actions rejouable.
 *
 * Deux façons de l'exécuter sur n'importe quelle page Fiori / SAPUI5 / OpenUI5 (ou une page
 * SAP WebGUI classique pour la capture SID) :
 *   1. collez ce fichier entier dans la console DevTools, ou
 *   2. chargez l'extension navigateur dans tools/recorder_web/extension et cliquez sur son icône.
 *
 * Mode capture (au clic) : lignes prêtes à coller, copiées dans le presse-papiers :
 *   Resolve Ui5 Control    controlType=...    properties={...}
 *   Resolve Ui5 By Xpath    //PlusCourt/Unique/Chemin
 *   Resolve Sid    wnd[0]/usr/...        (éléments WebGUI classiques uniquement)
 *   Resolve Wc Control    tag=...    text=...   (pages UI5 Web Components, hors registre UI5)
 *   Resolve Dom Element    role=...    name=...   (zones non-SAP : React/Angular/vanilla)
 * Mode record (bouton « rec ») : suit vos manipulations en steps ordonnés
 *   (Click/Fill sur les 5 moteurs role/xpath/sid/wc/dom ; clic droit = menu d'assertions
 *   visible/texte, Alt+clic = raccourci ; Entrée capturée en Keyboard Key ; nav -> Wait For
 *   UI5 Ready quand le runtime UI5 est là, Wait For Load State sinon ; re-saisie du même
 *   champ et attentes consécutives compactées).
 *   Steps éditables (déplacer/supprimer/ÉDITER au double-clic), nommables, persistés
 *   (sessionStorage : survivent à un rechargement de page). « play » REJOUE le déroulé
 *   dans la page (mêmes moteurs de résolution, repli xpath essayé, arrêt sur le premier
 *   échec, validation avant export). « +test » démarre un nouveau scénario (marqueur ;
 *   chaque export produit alors plusieurs *** Test Cases ***). Les steps UI5 naissent
 *   avec leur repli xpath en commentaire : l'export resource-first les convertit en
 *   Resolve Ui5 With Fallback (auto-réparables au replay). « export » ouvre un menu :
 *   .robot COMPLET (Settings + New Browser/New Page + steps, keyword Wait For UI5 Ready
 *   embarqué), paire resource-first (.resource keywords métier + .robot sans
 *   localisateur, convention n°1), plan specs/ (.spec.md, l'entrée du cycle
 *   plan -> generate -> heal), rapport HTML auto-contenu (documentation du déroulé :
 *   phrase métier + ligne exacte par step, jamais un test), et IMPORT d'un .robot
 *   exporté (le cycle d'édition se
 *   referme). Un panneau ne peut pas instrumenter une iframe cross-origin :
 *   avertissement affiché, l'extension (allFrames) injecte un panneau par frame.
 *
 * GÉNÉRÉ depuis src/SapFioriLibrary/_ui5_js.py (BUNDLE + écouteur recorder) afin que la
 * logique de capture ne diverge jamais du résolveur de la bibliothèque. Ne pas éditer
 * manuellement : exécuter `python -m SapFioriLibrary.regen_recorder`. Techniques portées depuis
 * playwright-sap (Apache-2.0) ; voir le NOTICE du projet.
 *
 * Le survol met en surbrillance le contrôle ; Échap ou window.__ui5SpyStop() arrête.
 */
"""


def spy_snippet():
    """Retourne le programme Spy autonome complet (en-tête + bundle + écouteur de survol/clic).
    Utilisé à la fois comme extrait à coller dans DevTools et comme script de contenu injecté
    par l'extension."""
    # Le picto aicabra (data-URI) est injecté par token : le gabarit du
    # listener est brut (ses '%' sont littéraux), aucun formatage %s dedans.
    listener = _SPY_LISTENER.replace("__AICABRA_ICON__", _AICABRA_ICON)
    return "%s\n%s\n%s\n" % (_SPY_HEADER, BUNDLE, listener)
