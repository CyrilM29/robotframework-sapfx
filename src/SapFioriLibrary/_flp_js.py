"""Sondes PURES des **tuiles** d'un launchpad : compteurs rendus, configuration
et symboles numériques de la page (fiche scénario 7, 2026-09-29).

Un chapitre à part (convention #13) : ``_ui5_js`` approche de sa limite, et
ces trois lectures forment un tout, celui qu'exige la question « le chiffre
d'une tuile est-il juste ». Aucune n'injecte le bundle ``__SAPFX`` : observer
une tuile ne doit rien instrumenter, même contrat que les sondes ushell
(``FLP_*_PROBE_JS``) et que ``UI5_RUNTIME_PROBE_JS``.

Mesuré sur les deux launchpads ABAP du banc avant d'écrire une ligne :

* le registre porte un ``sap.ushell.ui.launchpad.Tile`` par tuile rendue, sur
  1.71 comme sur 1.120 ; sa propriété ``target`` porte l'intent en 1.71 et
  vaut ``''`` en 1.120, où l'ancre HTML de la tuile le porte (``href`` se
  terminant par ``#SemanticObject-action``) ;
* le compteur est la propriété ``value`` d'un ``sap.m.NumericContent`` rendu
  DANS le nœud de la tuile (relation de containment, pas d'agrégation lisible
  en 1.120) ;
* le service ``LaunchPage`` rend, pour chaque tuile d'un groupe, son instance
  de chip, dont le paramètre ``tileConfiguration`` est une chaîne JSON portant
  ``service_url`` et ``navigation_target_url`` ; ``getTileTarget`` y rend une
  chaîne VIDE sur l'adaptateur ABAP, d'où la lecture de la configuration.

Les parcours de registre suivent la même chaîne de repli que le bundle
(module ``ElementRegistry`` en 2.x, ``Element.registry`` depuis 1.67, balayage
``[data-sap-ui]`` avant), recopiée ici puisque le bundle n'est pas injecté.
"""

# Les compteurs de TOUTES les tuiles rendues : une entrée par tuile,
# `{tile_id, intent, contents: [{value, scale, rendered}]}`. Le filtrage par
# intent se fait côté Python (`sapfx_common.flp_tiles`), ce qui rend la liste
# des tuiles vues disponible pour un échec qui dit ce qui existe.
FLP_TILE_COUNTERS_PROBE_JS = (
    "() => { const s = window.sap; if (!(s && s.ui)) return null; "
    "const each = fn => { let R = null; "
    "try { R = s.ui.require && s.ui.require('sap/ui/core/ElementRegistry'); } catch (e) {} "
    "if (R && typeof R.forEach === 'function') { R.forEach(fn); return; } "
    "let E = null; try { E = s.ui.require && s.ui.require('sap/ui/core/Element'); } catch (e) {} "
    "if (E && E.registry && typeof E.registry.forEach === 'function') { E.registry.forEach(fn); return; } "
    "const core = s.ui.getCore && s.ui.getCore(); if (!core) return; "
    "document.querySelectorAll('[data-sap-ui]').forEach(n => { const c = core.byId(n.id); if (c) fn(c, n.id); }); }; "
    "const tiles = [], numeric = []; "
    "each(c => { if (!c || typeof c.getMetadata !== 'function' || !c.getDomRef || !c.getDomRef()) return; "
    "const n = c.getMetadata().getName(); "
    "if (n === 'sap.ushell.ui.launchpad.Tile') tiles.push(c); "
    "else if (n === 'sap.m.NumericContent') numeric.push(c); }); "
    "return tiles.map(t => { const dom = t.getDomRef(); "
    "let target = ''; try { target = String((t.getTarget && t.getTarget()) || ''); } catch (e) {} "
    "let href = ''; const a = dom.querySelector('a[href]'); if (a) href = String(a.getAttribute('href') || ''); "
    "const contents = numeric.filter(nc => dom.contains(nc.getDomRef())).map(nc => ({ "
    "value: String(nc.getValue ? (nc.getValue() == null ? '' : nc.getValue()) : ''), "
    "scale: String(nc.getScale ? (nc.getScale() || '') : ''), "
    "rendered: String(nc.getDomRef().innerText || nc.getDomRef().textContent || '') })); "
    "let debug = ''; try { debug = String((t.getDebugInfo && t.getDebugInfo()) || ''); } catch (e) {} "
    "return { tile_id: String(t.getId()), intent: target || href, target: target, "
    "href: href, debug: debug, contents: contents }; }); }")

# Déclenche le RAFRAÎCHISSEMENT d'une tuile des groupes (désignée par son
# identifiant d'instance, lu par `Get Flp Tile Configuration`) par le service
# LaunchPage, et rend l'instant du déclenchement sur l'horloge du minutage des
# ressources (`timeOrigin + now()`, la MÊME que celle des réponses : `Date.now()`
# peut en diverger). Mesuré sur 1.71 : `refreshTile` relance la requête du
# service (réponse 33 ms plus tard) SANS repasser la valeur par `...` : la
# preuve de fraîcheur est donc la réponse, lue par
# `PAGE_RESOURCE_RESPONSES_PROBE_JS`.
FLP_TILE_REFRESH_PROBE_JS = (
    "async (first, second) => { const raw = (second === undefined) ? first : second; "
    "const voulu = String(JSON.parse(String(raw || '{}')).tile_instance_id || ''); "
    "const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return { __no_container: true }; "
    "let s; try { s = await C.getServiceAsync('LaunchPage'); } "
    "catch (e) { return { __no_service: String((e && e.message) || e || '') }; } "
    "if (typeof s.refreshTile !== 'function') return { __no_refresh: true }; "
    "const groupes = await new Promise((res, rej) => { const out = []; "
    "s.getGroups().done(a => res(out.length ? out : (a || []))).fail(rej).progress(g => out.push(g)); }); "
    "let cible = null; groupes.forEach(g => (s.getGroupTiles(g) || []).forEach(t => { "
    "let id = ''; try { id = String(s.getTileId(t) || ''); } catch (e) {} if (id === voulu) cible = t; })); "
    "if (!cible) return { __not_found: voulu }; "
    "const vus = []; let obs = null; try { obs = new PerformanceObserver(l => "
    "l.getEntries().forEach(e => vus.push(e))); obs.observe({ type: 'resource' }); } "
    "catch (e) { obs = null; } "
    "const ancien = window.__SAPFX_TILE_REFRESH__; if (ancien && ancien.obs) { "
    "try { ancien.obs.disconnect(); } catch (e) {} } "
    "window.__SAPFX_TILE_REFRESH__ = { vus: vus, obs: obs }; "
    "const t0 = performance.timeOrigin + performance.now(); s.refreshTile(cible); "
    "return { triggered_at: t0, observer: !!obs }; }")

# Requêtes dont le CHEMIN est celui demandé (casse ignorée, requête ignorée) :
# `{start, end, status, transfer, body}`, instants sur l'horloge `timeOrigin`,
# statut HTTP tel que le navigateur l'expose (`responseStatus`, 200 et 404
# mesurés ; `null` quand il ne l'expose pas), octets transférés et taille du
# corps décodé (0 quand le navigateur ne les expose pas : réponse d'une autre
# origine sans `Timing-Allow-Origin`). Lues dans ce que l'observateur posé par
# `FLP_TILE_REFRESH_PROBE_JS` a vu (il ne dépend pas du tampon du minutage,
# 250 entrées par défaut, au-delà duquel les nouvelles entrées sont PERDUES),
# plus le tampon lui-même, doublons retirés. Lecture pure.
PAGE_RESOURCE_RESPONSES_PROBE_JS = (
    "(first, second) => { const raw = (second === undefined) ? first : second; "
    "const voulu = String(raw || '').toLowerCase(); if (!voulu || !window.performance) return []; "
    "const suivi = window.__SAPFX_TILE_REFRESH__; "
    "const toutes = ((suivi && suivi.vus) || []).concat(performance.getEntriesByType('resource')); "
    "const out = [], vues = new Set(); toutes.forEach(e => { let p = ''; "
    "try { p = decodeURIComponent(new URL(e.name, location.href).pathname); } catch (x) { return; } "
    "const cle = e.name + '|' + e.startTime; if (vues.has(cle)) return; vues.add(cle); "
    "if (p.toLowerCase() === voulu && e.responseEnd > 0) out.push({ "
    "start: performance.timeOrigin + e.startTime, end: performance.timeOrigin + e.responseEnd, "
    "status: (typeof e.responseStatus === 'number') ? e.responseStatus : null, "
    "transfer: (typeof e.transferSize === 'number') ? e.transferSize : null, "
    "body: (typeof e.decodedBodySize === 'number') ? e.decodedBodySize : null }); }); return out; }")

# Retire l'observateur posé par le rafraîchissement : la page est rendue dans
# l'état où on l'a trouvée.
FLP_TILE_REFRESH_CLEANUP_JS = (
    "() => { const suivi = window.__SAPFX_TILE_REFRESH__; if (suivi && suivi.obs) { "
    "try { suivi.obs.disconnect(); } catch (e) {} } "
    "try { delete window.__SAPFX_TILE_REFRESH__; } catch (e) {} return true; }")

# La configuration des tuiles des groupes, par le service LaunchPage : une
# entrée par tuile, `{group_id, tile_instance_id, chip_id, base_chip_id, title,
# configuration}` où `configuration` est la chaîne JSON brute (décodée côté
# Python, qui sait refuser une configuration illisible).
FLP_TILE_CONFIGURATION_PROBE_JS = (
    "async () => { const C = window.sap && sap.ushell && sap.ushell.Container; "
    "if (!C || typeof C.getServiceAsync !== 'function') return { __no_container: true }; "
    "let s; try { s = await C.getServiceAsync('LaunchPage'); } "
    "catch (e) { return { __no_service: String((e && e.message) || e || '') }; } "
    "const groupes = await new Promise((res, rej) => { const out = []; "
    "s.getGroups().done(a => res(out.length ? out : (a || []))).fail(rej).progress(g => out.push(g)); }); "
    "const out = []; groupes.forEach(g => (s.getGroupTiles(g) || []).forEach(t => { "
    "const r = { group_id: String(s.getGroupId(g)), tile_instance_id: '', chip_id: '', "
    "base_chip_id: '', title: '', configuration: '' }; "
    "try { r.tile_instance_id = String(s.getTileId(t) || ''); } catch (e) {} "
    "try { r.title = String(s.getTileTitle(t) || ''); } catch (e) {} "
    "try { r.configuration = String((t.getConfigurationParameter && "
    "t.getConfigurationParameter('tileConfiguration')) || ''); } catch (e) {} "
    "try { const c = t.getChip && t.getChip(); if (c) { r.chip_id = String(c.getId() || ''); "
    "r.base_chip_id = String((c.getBaseChipId && c.getBaseChipId()) || ''); } } catch (e) {} "
    "out.push(r); })); return out; }")

# Les symboles numériques EFFECTIFS de la page : un nombre connu formaté par le
# formateur de la page (celui de la tuile), dont `sapfx_common.flp_tiles.
# number_symbols` déduit groupement et décimale. Mesuré sur les deux
# launchpads : `1.234.567,5` (notation décimale de l'utilisateur vide).
# Le module est CHARGÉ s'il ne l'est pas encore (requête asynchrone) : la
# lecture synchrone ne le trouvait que si la page l'avait déjà demandé, vrai
# sur le launchpad du banc, faux sur une page qui n'a pas encore formaté de
# nombre (relevé par la fixture de la revue du 2026-09-29).
PAGE_NUMBER_SAMPLE_PROBE_JS = (
    "async () => { const s = window.sap; if (!(s && s.ui)) return ''; let NF = null; "
    "try { NF = s.ui.require && s.ui.require('sap/ui/core/format/NumberFormat'); } catch (e) {} "
    "if (!NF && s.ui.require) { NF = await new Promise(res => { try { "
    "s.ui.require(['sap/ui/core/format/NumberFormat'], m => res(m), () => res(null)); } "
    "catch (e) { res(null); } }); } "
    "if (!NF && s.ui.core && s.ui.core.format) NF = s.ui.core.format.NumberFormat; "
    "if (!NF) return ''; try { return String(NF.getFloatInstance({ groupingEnabled: true, "
    "minFractionDigits: 1, maxFractionDigits: 1 }).format(1234567.5)); } catch (e) { return ''; } }")
