"""Sondes PURES du mode *Espaces et Pages* d'un launchpad et de l'histogramme
des types de contrôles rendus (fiche scénario 14, 2026-10-13).

Un chapitre à part (convention #13) : ``_ui5_js`` approche de sa limite.
Aucune sonde n'injecte le bundle ``__SAPFX`` : observer le mode d'un
launchpad ne doit rien instrumenter, même contrat que les sondes ushell
(``FLP_*_PROBE_JS``).

Mesuré sur ABAP Platform 2023 (SAPUI5 1.120.15) avant d'écrire une ligne : le
service ``Menu`` expose ``isMenuEnabled``, ``getMenuEntries``,
``getSpacesPagesHierarchy``, ``getDefaultSpace`` et ``getMyHomeSpace`` ; sur un
accueil classique ils rendent ``false``, ``[]``, ``{spaces: []}``, ``null``,
``null``. Les réponses arrivent en valeur, en promesse ou en jQuery Deferred
selon la méthode et la release : ``await`` accepte les trois (un Deferred est
un objet « thenable »).
"""

# L'état EFFECTIF du shell pour les espaces, lu au service `Menu`. Chaque
# méthode est lue séparément : une méthode absente ou qui lève est NOMMÉE dans
# `errors`, sa valeur restant `null`, jamais remplacée par une valeur
# plausible. Les espaces sont réduits à leurs identifiants et titres.
FLP_MENU_STATE_PROBE_JS = (
    "async () => { const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return { __no_container: true }; "
    "let m; try { m = await C.getServiceAsync('Menu'); } "
    "catch (e) { return { __no_service: String((e && e.message) || e || '') }; } "
    "if (!m) return { __no_service: 'service Menu vide' }; "
    "const errors = []; "
    "const call = async (name) => { if (typeof m[name] !== 'function') { errors.push(name + ' absent'); return null; } "
    "try { return await m[name](); } catch (e) { errors.push(name + ': ' + String((e && e.message) || e)); return null; } }; "
    "const ref = o => (o && typeof o === 'object') ? { id: String(o.id || ''), title: String(o.title || o.label || '') } : null; "
    "const enabled = await call('isMenuEnabled'); "
    "const entries = await call('getMenuEntries'); "
    "const hierarchy = await call('getSpacesPagesHierarchy'); "
    "const def = await call('getDefaultSpace'); "
    "const home = await call('getMyHomeSpace'); "
    "let showMyHome = null; try { const u = C.getUser(); "
    "if (u && typeof u.getShowMyHome === 'function') showMyHome = !!u.getShowMyHome(); } catch (e) {} "
    "const spaces = (hierarchy && Array.isArray(hierarchy.spaces)) ? hierarchy.spaces.map(s => ({ "
    "id: String((s && s.id) || ''), title: String((s && (s.title || s.label)) || ''), "
    "pages: ((s && s.pages) || []).map(p => ({ id: String((p && p.id) || ''), "
    "title: String((p && (p.title || p.label)) || '') })) })) : null; "
    "return { available: true, "
    "menu_enabled: (enabled === null || enabled === undefined) ? null : !!enabled, "
    "entries: Array.isArray(entries) ? entries.length : null, "
    "spaces: spaces, default_space: ref(def), my_home_space: ref(home), "
    "show_my_home: showMyHome, errors: errors }; }")

# Histogramme des types PLEINS des contrôles RENDUS (nœud DOM présent), sous un
# conteneur DOM optionnel et un préfixe d'espace de noms optionnel : tous les
# types rendus en un appel, sans supposer leurs noms. Un contrôle dont la
# lecture lève est COMPTÉ dans `errors` (le keyword échoue alors), jamais
# écarté en silence. Même chaîne de repli du registre que le bundle
# (module `ElementRegistry` en 2.x, `Element.registry` depuis 1.67, balayage
# `[data-sap-ui]` avant), recopiée puisque le bundle n'est pas injecté.
UI5_CONTROL_TYPES_PROBE_JS = (
    "(first, second) => { const raw = (second === undefined) ? first : second; "
    "const opts = JSON.parse(String(raw || '{}')); "
    "const s = window.sap; if (!(s && s.ui)) return { __no_runtime: true }; "
    "let scope = null; if (opts.container_id) { scope = document.getElementById(String(opts.container_id)); "
    "if (!scope) return { __no_container: String(opts.container_id) }; } "
    "const prefix = String(opts.namespace || ''); "
    "const each = fn => { let R = null; "
    "try { R = s.ui.require && s.ui.require('sap/ui/core/ElementRegistry'); } catch (e) {} "
    "if (R && typeof R.forEach === 'function') { R.forEach(fn); return; } "
    "let E = null; try { E = s.ui.require && s.ui.require('sap/ui/core/Element'); } catch (e) {} "
    "if (E && E.registry && typeof E.registry.forEach === 'function') { E.registry.forEach(fn); return; } "
    "const core = s.ui.getCore && s.ui.getCore(); if (!core) return; "
    "document.querySelectorAll('[data-sap-ui]').forEach(n => { const c = core.byId(n.id); if (c) fn(c, n.id); }); }; "
    "const types = {}; let total = 0; let errors = 0; "
    "each(c => { try { if (!c || typeof c.getMetadata !== 'function' || !c.getDomRef) return; "
    "const d = c.getDomRef(); if (!d) return; "
    "if (scope && (d === scope || !scope.contains(d))) return; "
    "const n = String(c.getMetadata().getName()); "
    "if (prefix && n.indexOf(prefix) !== 0) return; "
    "types[n] = (types[n] || 0) + 1; total += 1; } catch (e) { errors += 1; } }); "
    "return { types: types, total: total, errors: errors }; }")

# Fragment courant de la page : l'écran du shell sur lequel on lit l'accueil.
PAGE_HASH_PROBE_JS = "() => String(window.location.hash || '')"
