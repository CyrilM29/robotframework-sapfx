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

(() => {
  if (window.__SAPFX) return;
  const ALLOWED = ['text','title','viewName','value','src','key','icon','number','description','headerText','href','label','selectedKey','placeholder','target','name','header','tooltip','html','htmlText','alt','subtitle','info','state','valueStateText','noDataText','count','status','design','type','level','intro'];
  const ALLOW_WITHOUT = ['SearchField','PullToRefresh','Row','ColumnListItem','Column','CustomListItem','GridListItem','StandardListItem','Table','List','Page','ToolbarSeparator'];

  // Classe Element via le module AMD (chemin moderne, non déprécié sur UI5 >= 1.118)
  // si déjà chargé ; sinon null et on retombe sur le Core hérité. Element est un module
  // de base toujours présent, donc sap.ui.require(string) le rend de façon synchrone.
  function elementClass() {
    try { const E = window.sap && sap.ui && sap.ui.require && sap.ui.require('sap/ui/core/Element'); if (E) return E; }
    catch (e) {}
    return null;
  }
  function core() { return (window.sap && sap.ui && sap.ui.getCore) ? sap.ui.getCore() : null; }
  function isUI5() {
    const E = elementClass();
    if (E && (typeof E.getElementById === 'function' || E.registry)) return true;
    const c = core();
    return !!(c && typeof c.byId === 'function');
  }
  function byId(id) {
    if (!id) return null;
    const E = elementClass();
    if (E && typeof E.getElementById === 'function') return E.getElementById(id);
    const c = core(); if (!c) return null;
    return (typeof c.getElementById === 'function') ? c.getElementById(id) : c.byId(id);
  }

  // Itère sur tous les contrôles, quel que soit l'âge du runtime UI5 :
  //  1. module 'sap/ui/core/ElementRegistry' (UI5 2.x : Element.registry supprimé) ;
  //  2. Element.registry via le module ou l'espace global (UI5 1.67+) ;
  //  3. balayage DOM [data-sap-ui] + byId (UI5 < 1.67, ex. launchpads 1.44/1.52),
  //     ne voit que les contrôles RENDUS, ce qui suffit : resolveByRole ne retourne
  //     de toute façon que les contrôles ayant un getDomRef().
  function registryForEach(fn) {
    try {
      const R = window.sap && sap.ui && sap.ui.require && sap.ui.require('sap/ui/core/ElementRegistry');
      if (R && typeof R.forEach === 'function') { R.forEach(fn); return true; }
    } catch (e) {}
    const E = elementClass();
    const reg = (E && E.registry) || (window.sap && sap.ui && sap.ui.core && sap.ui.core.Element && sap.ui.core.Element.registry);
    if (reg && typeof reg.forEach === 'function') { reg.forEach(fn); return true; }
    if (!isUI5()) return false;
    const seen = {};
    const nodes = document.querySelectorAll('[data-sap-ui]');
    for (let i = 0; i < nodes.length; i++) {
      const id = nodes[i].id;
      if (!id || seen[id]) continue;
      seen[id] = true;
      const c = byId(id);
      if (c) { try { fn(c, id); } catch (e) {} }
    }
    return true;
  }
  function shortType(full) { return full ? full.split('.').pop() : ''; }

  // ---- Repos réseau/busy (Wait For Ui5 Idle) --------------------------------
  // XHR et fetch instrumentés à l'INSTALLATION du bundle (la garde __SAPFX
  // protège du double-wrap) : on ne compte que les requêtes lancées après
  // l'injection, exactement le besoin du keyword (agir, puis attendre que la
  // page ait fini de parler au serveur). Indépendant du runtime UI5 : les
  // pages WC/hybrides en profitent aussi.
  const NET = { pending: 0, last: Date.now() };
  function netDone() { NET.pending = NET.pending > 0 ? NET.pending - 1 : 0; NET.last = Date.now(); }
  try {
    const xhrSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
      NET.pending += 1; NET.last = Date.now();
      try { this.addEventListener('loadend', netDone); } catch (e) { netDone(); }
      return xhrSend.apply(this, arguments);
    };
  } catch (e) {}
  try {
    if (window.fetch) {
      const realFetch = window.fetch;
      window.fetch = function () {
        NET.pending += 1; NET.last = Date.now();
        const p = realFetch.apply(this, arguments);
        try { p.then(netDone, netDone); } catch (e) { netDone(); }
        return p;
      };
    }
  } catch (e) {}
  function busyVisible() {
    try {
      const nodes = document.querySelectorAll(
        '.sapUiLocalBusyIndicator, .sapUiBusy, .sapMBusyDialog, .sapMBusyIndicator');
      for (let i = 0; i < nodes.length; i++) {
        const r = nodes[i].getBoundingClientRect();
        if (r.width || r.height) return true;
      }
    } catch (e) {}
    return false;
  }
  function idleState() {
    const busy = busyVisible();
    if (busy || NET.pending > 0) NET.last = Date.now();
    return { pending: NET.pending, busy: busy, quiet_ms: Date.now() - NET.last };
  }

  // ---- Messages UI5 (MessageManager/Messaging) et MessageToast ---------------
  // Les toasts sont éphémères à l'écran : un hook posé sur sap.m.MessageToast à
  // l'injection garde les 20 derniers (texte + horodatage). Best-effort : un
  // toast émis AVANT l'injection est perdu, jamais une erreur.
  const TOASTS = [];
  try {
    if (window.sap && sap.ui && sap.ui.require) {
      sap.ui.require(['sap/m/MessageToast'], function (MT) {
        try {
          if (!MT || MT.__sapfxToastHook) return;
          const realShow = MT.show;
          MT.show = function (message) {
            try {
              TOASTS.push({ text: String(message), time: Date.now() });
              if (TOASTS.length > 20) TOASTS.shift();
            } catch (e) {}
            return realShow.apply(this, arguments);
          };
          MT.__sapfxToastHook = true;
        } catch (e) {}
      });
    }
  } catch (e) {}
  function messageModel() {
    try {
      const M = window.sap && sap.ui && sap.ui.require && sap.ui.require('sap/ui/core/Messaging');
      if (M && typeof M.getMessageModel === 'function') return M.getMessageModel();
    } catch (e) {}
    try {
      const c = core();
      if (c && typeof c.getMessageManager === 'function') return c.getMessageManager().getMessageModel();
    } catch (e) {}
    return null;
  }
  function getMessages() {
    if (!isUI5()) return null;
    const out = { messages: [], toasts: TOASTS.slice() };
    try {
      const model = messageModel();
      const data = (model && model.getData()) || [];
      for (let i = 0; i < data.length; i++) {
        const m = data[i];
        try {
          out.messages.push({
            type: String((m.getType ? m.getType() : m.type) || ''),
            message: String((m.getMessage ? m.getMessage() : m.message) || ''),
            target: String((m.getTargets ? (m.getTargets()[0] || '')
                            : (m.getTarget ? m.getTarget() : (m.target || ''))) || ''),
            description: String((m.getDescription ? m.getDescription() : (m.description || '')) || '')
          });
        } catch (e) {}
      }
    } catch (e) {}
    return out;
  }

  // Littéral de chaîne XPath 1.0 correctement échappé. XPath 1.0 (document.evaluate)
  // n'offre AUCUN échappement de guillemet dans un littéral : on bascule de quote, et
  // si la valeur contient les deux types, on construit un concat(). Évite qu'un texte
  // comme "L'utilisateur" produise un prédicat cassé ([@text='Lutilisateur']).
  function xpathLiteral(s) {
    s = String(s);
    if (s.indexOf("'") === -1) return "'" + s + "'";
    if (s.indexOf('"') === -1) return '"' + s + '"';
    return "concat('" + s.replace(/'/g, "',\"'\",'") + "')";
  }

  // Propriétés propres et héritées via les métadonnées du contrôle.
  function props(control) {
    const out = {};
    try {
      const md = control.getMetadata();
      const all = md.getAllProperties ? md.getAllProperties() : md.getProperties();
      Object.keys(all).forEach((k) => {
        try { const v = control.getProperty(k); if (v !== undefined && v !== null) out[k] = v; }
        catch (e) {}
      });
    } catch (e) {}
    return out;
  }

  // Correspondance par sous-chaîne insensible à la casse ; supporte /pattern/flags pour une valeur de propriété.
  // La forme regex doit être EXPLICITE et bien formée : `/motif/drapeaux` avec des drapeaux
  // valides ([a-z]*) et un motif compilable. Sinon (ex. une valeur de chemin '/sap/bc/' ou
  // '/Orders'), on retombe sur la sous-chaîne, au lieu de la traiter à tort comme une regex.
  // Bornes défensives contre un pattern/haystack forgé (properties=/pattern/flags
  // vient d'un argument de test, potentiellement fourni par un agent MCP) : un
  // regex à quantificateurs imbriqués peut bloquer le thread JS (ReDoS). On ne
  // détecte pas les patterns pathologiques eux-mêmes (analyse statique hors de
  // portée ici), mais borner la longueur du pattern et de la chaîne testée borne
  // aussi le pire cas de backtracking catastrophique.
  const MATCH_PROPS_MAX_PATTERN_LENGTH = 200;
  const MATCH_PROPS_MAX_HAYSTACK_LENGTH = 500;

  // Comparaison d'UNE valeur (sous-chaîne insensible à la casse, ou /regex/flags
  // explicite et bien formée), partagée par le moteur role (propriétés de
  // contrôle) et le moteur Web Components (attributs/propriétés d'hôte).
  function valueMatches(haystack, want) {
    const w = String(want);
    const h = String(haystack).slice(0, MATCH_PROPS_MAX_HAYSTACK_LENGTH);
    const rx = /^\/(.+)\/([a-z]*)$/.exec(w);
    let re = null;
    if (rx && rx[1].length <= MATCH_PROPS_MAX_PATTERN_LENGTH) {
      try { re = new RegExp(rx[1], rx[2]); } catch (e) { re = null; }
    }
    if (re) return re.test(h);        // regex : la valeur BRUTE, \s et \n compris
    // Sous-chaîne : les DEUX côtés sont normalisés en espaces. Une cellule Robot
    // ne peut pas porter 2+ espaces ni un saut de ligne, donc un sélecteur
    // enregistré est toujours normalisé ; sans cette normalisation côté
    // résolution, une propriété contenant « Total:\n  42 » ne pourrait JAMAIS
    // être matchée par le sélecteur que le recorder vient d'émettre (les
    // moteurs wc et dom normalisent déjà leur cible, le moteur role non).
    return wsCollapse(h).toLowerCase().includes(wsCollapse(w).toLowerCase());
  }

  // Normalisation des espaces (runs -> un espace). Les textes et noms
  // accessibles lus dans le DOM gardent leurs retours à la ligne d'indentation
  // (`<button>Add\n  item</button>`), alors que la valeur ENREGISTRÉE est
  // normalisée (une cellule RF ne peut pas porter 2+ espaces) : sans repli
  // commun côté résolution, un nom multi-nœuds ne re-résoudrait jamais.
  function wsCollapse(s) {
    return String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  }

  function matchProps(control, want) {
    const have = props(control);
    for (const k in want) {
      if (!(k in have)) return false;
      if (!valueMatches(have[k], want[k])) return false;
    }
    return true;
  }

  function matchBinding(control, bp) {
    try {
      const prop = bp.propertyPath || bp.property;
      const info = prop && control.getBindingInfo ? control.getBindingInfo(prop) : null;
      const path = info && (info.path || (info.parts && info.parts[0] && info.parts[0].path));
      if (!path) return false;
      return !bp.path || path.indexOf(bp.path) !== -1;
    } catch (e) { return false; }
  }

  // Construit un XMLDocument reflétant la hiérarchie des contrôles UI5. Balise = type court du contrôle ;
  // attributs = id, controlType, et les propriétés primitives autorisées : ainsi les prédicats
  // XPath comme [@text='Create'] fonctionnent nativement via document.evaluate.
  function buildTree() {
    const doc = document.implementation.createDocument(null, 'UI5Tree', null);
    function walk(node) {
      const kids = [];
      let child = node.firstElementChild;
      while (child) { kids.push.apply(kids, walk(child)); child = child.nextElementSibling; }
      const control = node.id ? byId(node.id) : null;
      if (node.getAttribute && node.getAttribute('data-sap-ui') && control) {
        const full = control.getMetadata().getName();
        const el = doc.createElement(shortType(full) || 'Control');
        el.setAttribute('id', control.getId());
        el.setAttribute('controlType', full);
        const p = props(control);
        ALLOWED.forEach((name) => {
          if (name in p && typeof p[name] !== 'object') {
            let v = String(p[name]);
            if (v.length > 200) v = v.slice(0, 200);
            try { el.setAttribute(name, v); } catch (e) {}
          }
        });
        kids.forEach((k) => el.appendChild(k));
        return [el];
      }
      return kids;
    }
    walk(document.body).forEach((n) => doc.documentElement.appendChild(n));
    return doc;
  }

  // Résout un XPath UI5 vers les ids de contrôles (ceux actuellement rendus avec un id DOM).
  function resolveByXPath(xpathStr) {
    if (!isUI5()) return null;
    const doc = buildTree();
    const ids = [];
    const res = doc.evaluate(xpathStr, doc, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    for (let i = 0; i < res.snapshotLength; i++) {
      const n = res.snapshotItem(i);
      const id = n && n.getAttribute ? n.getAttribute('id') : null;
      if (id && byId(id) && byId(id).getDomRef && byId(id).getDomRef()) ids.push(id);
    }
    return ids;
  }

  // Résout un sélecteur rôle/propriété vers les ids de contrôles via le registre
  // (avec repli DOM pour les runtimes sans registre, voir registryForEach).
  // `idSuffix` matche la FIN de l'id du contrôle : c'est le motif des ids stables
  // Fiori Elements (« <AppId>::<PageId>--fe::table::<Entity>::LineItem::Table »),
  // dont seul le suffixe `fe::…` est déterministe : le préfixe varie par app/route.
  function resolveByRole(selJson) {
    if (!isUI5()) return null;
    const sel = JSON.parse(selJson);
    const shortWant = sel.controlType ? shortType(sel.controlType) : null;
    const ids = [];
    registryForEach((c) => {
      try {
        if (sel.id && c.getId() !== sel.id) return;
        if (sel.idSuffix && String(c.getId()).slice(-String(sel.idSuffix).length) !== String(sel.idSuffix)) return;
        if (sel.controlType) {
          const full = c.getMetadata().getName();
          if (full !== sel.controlType && shortType(full) !== shortWant) return;
        }
        if (sel.viewId && c.getId().indexOf(sel.viewId) === -1) return;
        if (sel.properties && !matchProps(c, sel.properties)) return;
        if (sel.bindingPath && !matchBinding(c, sel.bindingPath)) return;
        const d = c.getDomRef();
        if (d && d.id) ids.push(d.id);
      } catch (e) {}
    });
    return ids;
  }

  // Spy : trouve le contrôle UI5 le plus proche propriétaire d'un nœud DOM et propose un sélecteur stable.
  function closestControl(node) {
    let cur = node;
    while (cur) {
      if (cur.id) {
        const c = byId(cur.id);
        if (c && c.getDomRef && c.getDomRef() && c.getDomRef().contains(node)) return c;
      }
      cur = cur.parentElement;
    }
    return null;
  }
  // Suffixe d'id STABLE d'un id Fiori Elements : la partie à partir de 'fe::'
  // (« <AppId>::<PageId>--fe::table::… » -> « fe::table::… »). Le préfixe
  // app/route varie ; le suffixe est déterministe (doc officielle FE V4).
  function feIdSuffix(id) {
    const idx = String(id).indexOf('fe::');
    return idx === -1 ? null : String(id).slice(idx);
  }
  function capture(node) {
    if (!isUI5()) return null;
    const c = closestControl(node);
    if (!c) return null;
    const full = c.getMetadata().getName();
    const sh = shortType(full);
    const p = props(c);
    const xShort = bestXpath(c.getId());
    // Id Fiori Elements ? Son suffixe 'fe::…' est le sélecteur LE PLUS stable
    // (avant même les propriétés, qui portent souvent du texte localisé).
    const fe = feIdSuffix(c.getId());
    const txt = controlText(c);           // texte visible : assertions de valeur du recorder
    if (fe) {
      return { role: { idSuffix: fe }, xpath: '//' + sh, xpathShort: xShort, text: txt };
    }
    let role = { controlType: full };
    let xprop = '//' + sh;
    for (let i = 0; i < ALLOWED.length; i++) {
      const name = ALLOWED[i];
      if (name in p && typeof p[name] !== 'object' && String(p[name]) !== '') {
        const val = String(p[name]);
        role = { controlType: full, properties: {} };
        role.properties[name] = val;
        xprop = '//' + sh + '[@' + name + '=' + xpathLiteral(val) + ']';
        return { role: role, xpath: xprop, xpathShort: xShort, text: txt };
      }
    }
    if (ALLOW_WITHOUT.indexOf(sh) === -1) {
      console.warn('[UI5 Recorder] no stable property matched for ' + sh +
        ' (' + c.getId() + ') -- falling back to a dynamic control id, likely fragile.');
      role = { id: c.getId() };
      xprop = '//' + sh + '[@id=' + xpathLiteral(c.getId()) + ']';
    }
    return { role: role, xpath: xprop, xpathShort: xShort, text: txt };
  }

  // ---- Lecture de table UI5 (parité avec Read Grid côté ECC) ----------------
  // Extrait le texte significatif d'un contrôle cellule, quel que soit son type.
  function controlText(c) {
    if (!c) return '';
    try {
      if (typeof c.getText === 'function' && c.getText()) return String(c.getText());
      if (typeof c.getTitle === 'function' && c.getTitle()) return String(c.getTitle());
      if (typeof c.getValue === 'function' && c.getValue() !== undefined && c.getValue() !== null && c.getValue() !== '')
        return String(c.getValue());
      if (typeof c.getNumber === 'function' && c.getNumber()) return String(c.getNumber());
      if (typeof c.getSelected === 'function') return c.getSelected() ? 'true' : 'false';
    } catch (e) {}
    try { const dom = c.getDomRef && c.getDomRef(); if (dom) return (dom.textContent || '').trim(); }
    catch (e) {}
    return '';
  }
  // Lit une table sap.m.Table (getItems/getCells) ou sap.ui.table.Table (getRows, lignes
  // VISIBLES seulement, virtualisation) vers une liste d'objets {en-tête: valeur}.
  function readTable(controlId) {
    if (!isUI5()) return null;
    const t = byId(controlId);
    if (!t) return null;
    const cols = (typeof t.getColumns === 'function') ? t.getColumns() : [];
    const headers = cols.map((col, i) => {
      let h = '';
      try {
        if (typeof col.getHeader === 'function') h = controlText(col.getHeader());
        if (!h && typeof col.getLabel === 'function') h = controlText(col.getLabel());
      } catch (e) {}
      return h || ('col' + i);
    });
    let items = [];
    if (typeof t.getItems === 'function') items = t.getItems();
    else if (typeof t.getRows === 'function') items = t.getRows();
    const out = [];
    items.forEach((row) => {
      if (typeof row.getCells !== 'function') return;   // ignore les en-têtes de groupe
      const cells = row.getCells();
      const obj = {};
      cells.forEach((cell, i) => { obj[headers[i] || ('col' + i)] = controlText(cell); });
      out.push(obj);
    });
    return out;
  }

  // ---- XPath structurel le plus court et unique sur l'arbre de contrôles ----
  // Porté depuis playwright-sap UI5Xpath.ts (getShortestXPath) : construit le chemin
  // positionnel complet, puis retourne le '//suffixe' le plus court qui résout encore
  // exactement vers le nœud cible.
  function findNodeById(doc, id) {
    const r = doc.evaluate('//*[@id=' + xpathLiteral(id) + ']',
        doc, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
    return r.singleNodeValue;
  }
  function positionalPath(node) {
    const parts = [];
    let cur = node;
    while (cur && cur.nodeType === 1 && cur.nodeName !== 'UI5Tree') {
      let idx = 1, sib = cur.previousElementSibling;
      while (sib) { if (sib.nodeName === cur.nodeName) idx++; sib = sib.previousElementSibling; }
      parts.unshift(cur.nodeName + '[' + idx + ']');
      cur = cur.parentElement;
    }
    return parts;
  }
  function bestXpath(controlId) {
    if (!isUI5()) return null;
    const doc = buildTree();
    const node = findNodeById(doc, controlId);
    if (!node) return null;
    const parts = positionalPath(node);
    for (let i = parts.length - 1; i >= 0; i--) {
      const cand = '//' + parts.slice(i).join('/');
      const res = doc.evaluate(cand, doc, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
      if (res.snapshotLength === 1 && res.snapshotItem(0) === node) return cand;
    }
    return '//' + parts.join('/');
  }

  // ---- Support du 'sid' SAP WebGUI (SAP GUI for HTML) -----------------------
  // Les éléments ABAP classiques WebGUI portent un attribut `lsdata` où le "SID" stable
  // (ex. wnd[0]/usr/ctxtVBAK-VBELN, l'id de scripting SAP GUI) apparaît sous DEUX
  // encodages : JSON `"SID":"…"` (fixtures, anciens ITS) ou littéral JS `SID:'…'`
  // (clé non citée, guillemets simples : le WebGUI live S/4 1909, constaté 2026-07-18).
  // Porté depuis playwright-sap sidSelectorGenerator.ts (regex au lieu d'eval).
  // Décodage d'entités HTML SANS innerHTML : même sur un <textarea> détaché,
  // un lsdata hostile pourrait sortir du RCDATA par </textarea> et créer des
  // nœuds à gestionnaire inline. Entités numériques + les nommées usuelles :
  // largement assez pour un attribut lsdata.
  const NAMED_ENTITIES = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'",
                          nbsp: '\u00a0'};
  function decodeEntities(raw) {
    return raw.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, function (all, ent) {
      if (ent.charAt(0) === '#') {
        const cp = (ent.charAt(1) === 'x' || ent.charAt(1) === 'X')
          ? parseInt(ent.slice(2), 16) : parseInt(ent.slice(1), 10);
        return isNaN(cp) ? all : String.fromCodePoint(cp);
      }
      return Object.prototype.hasOwnProperty.call(NAMED_ENTITIES, ent)
        ? NAMED_ENTITIES[ent] : all;
    });
  }
  function sidFromElement(el) {
    if (!el || !el.getAttribute) return undefined;
    const raw = el.getAttribute('lsdata');
    if (!raw) return undefined;
    const m = decodeEntities(raw).match(/["']?SID["']?\s*:\s*["']([^"']+)["']/);
    return m ? m[1] : undefined;
  }
  function captureSid(node) {
    let cur = (node.nodeType === 1) ? node : node.parentElement;
    let count = 0;
    while (cur && count < 5) {
      if (cur.id && cur.id.indexOf('helpbutton') !== -1) break;
      if (cur.hasAttribute && cur.hasAttribute('lsdata')) {
        const s = sidFromElement(cur);
        if (s) return { sid: s };
        break;
      }
      count++; cur = cur.parentElement;
    }
    const start = (node.nodeType === 1) ? node : node.parentElement;
    const queue = start ? [{ n: start, d: 0 }] : [];
    while (queue.length) {
      const it = queue.shift();
      if (!it || it.d > 2) break;
      if (it.n.id && it.n.id.indexOf('helpbutton') !== -1) continue;
      for (let i = 0; i < it.n.children.length; i++) {
        const ch = it.n.children[i];
        if (ch.hasAttribute('lsdata')) {
          const s = sidFromElement(ch);
          if (s) return { sid: s };
        }
        queue.push({ n: ch, d: it.d + 1 });
      }
    }
    return null;
  }

  // ---- Accessibilité : rôle implicite + nom accessible ----------------------
  // Les zones web génériques (React/Angular/vanilla) et les UI5 Web Components
  // s'adressent au plus près de l'INTENTION utilisateur via l'arbre
  // d'accessibilité : le rôle ARIA (explicite OU implicite, la sémantique
  // HTML native, sous-ensemble pragmatique de HTML-AAM) et le nom accessible
  // (calcul accname SIMPLIFIÉ, dans l'ordre de précédence de la spec W3C).
  // Consommés par les clés `role=`/`name=` des moteurs dom et wc, jamais
  // requis : les clés structurelles (css/tag/id) restent disponibles.
  const IMPLICIT_ROLES = {
    button: 'button', textarea: 'textbox', img: 'img', nav: 'navigation',
    main: 'main', form: 'form', search: 'search', header: 'banner',
    footer: 'contentinfo', aside: 'complementary', article: 'article',
    section: 'region', dialog: 'dialog', table: 'table', ul: 'list',
    ol: 'list', li: 'listitem', option: 'option', progress: 'progressbar',
    output: 'status', summary: 'button', hr: 'separator', select: 'combobox',
  };
  const INPUT_ROLES = {
    checkbox: 'checkbox', radio: 'radio', button: 'button', submit: 'button',
    reset: 'button', image: 'button', range: 'slider', number: 'spinbutton',
    search: 'searchbox',
  };
  function ariaRole(el) {
    const explicit = String(el.getAttribute('role') || '').trim().split(/\s+/)[0];
    if (explicit) return explicit.toLowerCase();
    const tag = el.tagName.toLowerCase();
    if (tag === 'a' || tag === 'area') return el.hasAttribute('href') ? 'link' : '';
    if (tag === 'input') {
      const t = String(el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'hidden') return '';
      return INPUT_ROLES[t] || 'textbox';
    }
    if (tag === 'select') return (el.multiple || Number(el.size) > 1) ? 'listbox' : 'combobox';
    if (/^h[1-6]$/.test(tag)) return 'heading';
    return IMPLICIT_ROLES[tag] || '';
  }
  function refsText(el, attr) {
    const refs = String(el.getAttribute(attr) || '').trim();
    if (!refs) return '';
    const parts = [];
    const ids = refs.split(/\s+/);
    for (let i = 0; i < ids.length; i++) {
      const ref = document.getElementById(ids[i]);
      if (ref) { const t = (ref.textContent || '').trim(); if (t) parts.push(t); }
    }
    return parts.join(' ');
  }
  function accName(el) {
    const labelledby = refsText(el, 'aria-labelledby');
    if (labelledby) return labelledby;
    const ariaLabel = String(el.getAttribute('aria-label') || '').trim();
    if (ariaLabel) return ariaLabel;
    // Convention UI5 Web Components : accessible-name (attribut) / accessibleName (propriété).
    let wcName = el.getAttribute('accessible-name');
    if (!wcName && ('accessibleName' in el) && typeof el.accessibleName !== 'object') {
      wcName = el.accessibleName;
    }
    if (wcName && String(wcName).trim()) return String(wcName).trim();
    // <label for=…> / <label> englobant : .labels pour les champs de formulaire
    // natifs, requête label[for] pour les autres (custom elements à id).
    if (el.labels && el.labels.length) {
      const t = (el.labels[0].textContent || '').trim();
      if (t) return t;
    }
    if (el.id && el.id.indexOf('"') === -1) {
      const lab = document.querySelector('label[for="' + el.id + '"]');
      if (lab) { const t = (lab.textContent || '').trim(); if (t) return t; }
    }
    const tag = el.tagName.toLowerCase();
    if ((tag === 'img' || tag === 'area')) {
      const alt = String(el.getAttribute('alt') || '').trim();
      if (alt) return alt;
    }
    if (tag === 'input') {
      const t = String(el.getAttribute('type') || '').toLowerCase();
      // != null et non-vide, pas truthy : un bouton de pavé numérique value="0" a un nom
      if ((t === 'button' || t === 'submit' || t === 'reset') &&
          el.value !== undefined && el.value !== null && String(el.value) !== '') {
        return String(el.value).trim();
      }
    }
    const text = (el.textContent || '').trim();
    if (text) return text.slice(0, 300);
    const title = String(el.getAttribute('title') || '').trim();
    if (title) return title;
    return String(el.getAttribute('placeholder') || '').trim();
  }

  // ---- Moteur Web Components (UI5 Web Components, pages hors registre UI5) --
  // Les pages « pur Web Components » (home SuccessFactors, apps ui5-webcomponents)
  // rendent des custom elements <ui5-button>… SANS runtime UI5 classique : le
  // registre est vide, resolveByRole/resolveByXPath sont aveugles. On scanne le
  // light DOM du document, le contenu applicatif (slots) y reste ; seuls les
  // internals des composants vivent dans leurs shadow roots (ouverts : le CSS de
  // Playwright les perce pour le clic/la saisie). Le scoping UI5 WC peut suffixer
  // les tags (ui5-button-abc123) : un type court 'Button' matche les deux formes.
  const WC_PREFIXES = ['ui5-'];
  function wcKebab(name) {
    return String(name).replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
  }
  function wcTagMatches(tag, wanted) {
    const want = wcKebab(wanted);
    if (want.indexOf('-') !== -1) {           // tag complet donné (ui5-button)
      return tag === want || tag.lastIndexOf(want + '-', 0) === 0;
    }
    for (let i = 0; i < WC_PREFIXES.length; i++) {   // type court (Button, TabContainer)
      const full = WC_PREFIXES[i] + want;
      if (tag === full || tag.lastIndexOf(full + '-', 0) === 0) return true;
    }
    return false;
  }
  function wcVisible(el) {
    const r = el.getBoundingClientRect();
    return !!(r.width || r.height);
  }
  // Chemin CSS light-DOM ancré au plus proche ancêtre à id (sinon body) : les
  // hôtes WC n'ont souvent PAS d'id, contrairement aux contrôles UI5 classiques,
  // on ne peut pas retourner un simple [id=…]. Les ids contenant un guillemet
  // (littéral CSS cassé) sont ignorés comme ancre.
  function wcCssPath(el) {
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.body) {
      if (cur.id && cur.id.indexOf('"') === -1) {
        parts.unshift('[id="' + cur.id + '"]');
        return parts.join(' > ');
      }
      let idx = 1, sib = cur.previousElementSibling;
      while (sib) { if (sib.tagName === cur.tagName) idx++; sib = sib.previousElementSibling; }
      parts.unshift(cur.tagName.toLowerCase() + ':nth-of-type(' + idx + ')');
      cur = cur.parentElement;
    }
    parts.unshift('body');
    return parts.join(' > ');
  }
  function wcMatches(el, sel) {
    const tag = el.tagName.toLowerCase();
    if (tag.indexOf('-') === -1) return false;         // pas un custom element
    if (sel.tag) {
      if (!wcTagMatches(tag, sel.tag)) return false;
    } else {
      let known = false;                                // sans tag : préfixes connus seulement
      for (let i = 0; i < WC_PREFIXES.length; i++) {
        if (tag.lastIndexOf(WC_PREFIXES[i], 0) === 0) { known = true; break; }
      }
      if (!known) return false;
    }
    if (sel.id && el.id !== sel.id) return false;
    if (sel.idSuffix && String(el.id).slice(-String(sel.idSuffix).length) !== String(sel.idSuffix)) return false;
    if (sel.text && !valueMatches(wsCollapse(el.textContent), sel.text)) return false;
    if (sel.name && !valueMatches(wsCollapse(accName(el)), sel.name)) return false;
    if (sel.properties) {
      for (const k in sel.properties) {
        let have = el.getAttribute ? el.getAttribute(k) : null;
        if (have === null && (k in el) && typeof el[k] !== 'object' && typeof el[k] !== 'function') {
          have = el[k];                                 // propriété JS non reflétée en attribut
        }
        if (have === null || have === undefined) return false;
        if (!valueMatches(have, sel.properties[k])) return false;
      }
    }
    return true;
  }
  // Résout un sélecteur WC vers des CHEMINS CSS light-DOM (pas des ids : voir
  // wcCssPath). Ne retourne que les hôtes rendus (rect non nul).
  function resolveByWc(selJson) {
    const sel = JSON.parse(selJson);
    const out = [];
    const nodes = document.querySelectorAll('*');
    for (let i = 0; i < nodes.length; i++) {
      const el = nodes[i];
      if (!wcMatches(el, sel)) continue;
      if (!wcVisible(el)) continue;
      out.push(wcCssPath(el));
    }
    return out;
  }
  // Recorder : l'hôte custom element ui5-* propriétaire le plus proche du nœud.
  function closestWcElement(node) {
    let cur = (node && node.nodeType === 1) ? node : (node ? node.parentElement : null);
    while (cur) {
      const tag = cur.tagName ? cur.tagName.toLowerCase() : '';
      if (tag.indexOf('-') !== -1) {
        for (let i = 0; i < WC_PREFIXES.length; i++) {
          if (tag.lastIndexOf(WC_PREFIXES[i], 0) === 0) return cur;
        }
      }
      cur = cur.parentElement;
    }
    return null;
  }
  // Capture sérialisable pour le recorder ({tag, text}), jamais l'élément DOM.
  // Texte NORMALISÉ (wsCollapse) : un textContent multi-nœuds porterait des
  // retours à la ligne, invalides dans une cellule RF, introuvables au replay.
  function captureWc(node) {
    const el = closestWcElement(node);
    if (!el) return null;
    const rec = { tag: el.tagName.toLowerCase() };
    const txt = wsCollapse(el.textContent).slice(0, 80);
    if (txt) rec.text = txt;
    return rec;
  }

  // Recorder : cible INTERACTIVE du moteur dom la plus proche (rôle ARIA calculé
  // parmi les rôles actionnables) : le repli du recorder pour les zones non-SAP
  // d'une page hybride. On refuse les conteneurs passifs (body, div nu) : un
  // clic hors de tout élément interactif ne doit produire AUCUN step (bruit).
  const INTERACTIVE_ROLES = { button: 1, link: 1, textbox: 1, searchbox: 1,
    checkbox: 1, radio: 1, combobox: 1, listbox: 1, option: 1, menuitem: 1,
    tab: 1, switch: 1, slider: 1, spinbutton: 1 };
  function interactiveDomTarget(node) {
    let cur = (node && node.nodeType === 1) ? node : (node ? node.parentElement : null);
    while (cur && cur !== document.body) {
      const role = ariaRole(cur);
      if (role && INTERACTIVE_ROLES[role]) return cur;
      cur = cur.parentElement;
    }
    return null;
  }
  // Capture sérialisable du moteur dom ({role, name, css}) : rôle + nom
  // accessible quand ils existent (le localisateur « intention utilisateur »),
  // chemin CSS light-DOM ancré sinon, jamais l'élément DOM lui-même.
  function captureDom(node) {
    const el = interactiveDomTarget(node);
    if (!el) return null;
    const rec = { css: wcCssPath(el) };
    const role = ariaRole(el);
    if (role) rec.role = role;
    const name = accName(el);
    if (name) rec.name = String(name).replace(/\s+/g, ' ').trim().slice(0, 80);
    return rec;
  }

  // ---- Moteur DOM générique (5e moteur : zones NON-SAP d'une page hybride) --
  // Un widget React/Angular/vanilla incrusté dans un shell Fiori (portlet
  // Work Zone, iframe custom, aide embarquée…) n'est adressable par AUCUN
  // moteur SAP : ni registre UI5, ni hôte ui5-*, ni lsdata WebGUI. Ce moteur
  // générique (CSS de base + texte + rôle ARIA explicite OU implicite +
  // nom accessible + attributs, mêmes règles de matching valueMatches que
  // role/wc) fait entrer ces zones dans la même
  // grammaire, chaîne de fallback et télémétrie de healing comprises, au
  // lieu de retomber sur des sélecteurs Browser bruts hors bibliothèque.
  // Retourne des CHEMINS CSS light-DOM (wcCssPath), comme le moteur wc.
  function resolveByDom(selJson) {
    const sel = JSON.parse(selJson);
    let nodes;
    try { nodes = document.querySelectorAll(sel.css || '*'); }
    catch (e) { return []; }   // CSS invalide : aucune correspondance (l'échec du keyword mentionne cette cause)
    const out = [];
    for (let i = 0; i < nodes.length; i++) {
      const el = nodes[i];
      if (sel.tag && el.tagName.toLowerCase() !== String(sel.tag).toLowerCase()) continue;
      if (sel.id && el.id !== sel.id) continue;
      if (sel.idSuffix && String(el.id).slice(-String(sel.idSuffix).length) !== String(sel.idSuffix)) continue;
      if (sel.role && ariaRole(el) !== String(sel.role).toLowerCase()) continue;
      if (sel.text && !valueMatches(wsCollapse(el.textContent), sel.text)) continue;
      if (sel.name && !valueMatches(wsCollapse(accName(el)), sel.name)) continue;
      if (sel.properties) {
        let ok = true;
        for (const k in sel.properties) {
          const have = el.getAttribute ? el.getAttribute(k) : null;
          if (have === null || have === undefined || !valueMatches(have, sel.properties[k])) { ok = false; break; }
        }
        if (!ok) continue;
      }
      if (!wcVisible(el)) continue;
      out.push(wcCssPath(el));
    }
    return out;
  }

  // ---- Sonde de composition (perception des pages HYBRIDES) -----------------
  // Décrit quelles technologies adressables cohabitent dans le document
  // courant : runtime UI5 classique (moteurs role/xpath), hôtes UI5 Web
  // Components (wc), éléments WebGUI lsdata (sid), indices de frameworks web
  // génériques (dom), et les iframes à sonder séparément (chacune avec un
  // sélecteur Browser réutilisable). Lecture seule, ne lève jamais : chaque
  // sous-sonde est isolée pour qu'une page exotique dégrade en champs vides.
  function frameworkHints() {
    const hints = [];
    try { if (document.querySelector('[data-reactroot],[data-reactid]')) hints.push('react'); } catch (e) {}
    try { if (document.querySelector('[ng-version]')) hints.push('angular'); } catch (e) {}
    try { if (document.querySelector('[data-v-app],[data-server-rendered]')) hints.push('vue'); } catch (e) {}
    return hints;
  }
  function frameSelector(el) {
    if (el.id && el.id.indexOf('"') === -1) return 'iframe[id="' + el.id + '"]';
    const name = el.getAttribute && el.getAttribute('name');
    if (name && name.indexOf('"') === -1) return 'iframe[name="' + name + '"]';
    return wcCssPath(el);   // repli : chemin CSS positionnel ancré à l'id le plus proche
  }
  function pageComposition() {
    const out = { url: String(location.href).slice(0, 300), title: String(document.title || '').slice(0, 120),
                  ui5_runtime: false, ui5_version: null, ui5_controls: 0,
                  wc_hosts: 0, webgui_elements: 0,
                  frameworks: frameworkHints(), frames: [] };
    if (isUI5()) {
      out.ui5_runtime = true;
      // sap.ui.version est SUPPRIMÉ en UI5 2.x : purement informatif, jamais requis.
      try { if (window.sap && sap.ui && sap.ui.version) out.ui5_version = String(sap.ui.version); } catch (e) {}
      let n = 0;
      try { registryForEach(function () { n++; }); } catch (e) {}
      out.ui5_controls = n;
    }
    try {
      const all = document.querySelectorAll('*');
      let wc = 0;
      for (let i = 0; i < all.length; i++) {
        const tag = all[i].tagName.toLowerCase();
        if (tag.indexOf('-') === -1) continue;
        for (let j = 0; j < WC_PREFIXES.length; j++) {
          if (tag.lastIndexOf(WC_PREFIXES[j], 0) === 0) { wc++; break; }
        }
      }
      out.wc_hosts = wc;
    } catch (e) {}
    try { out.webgui_elements = document.querySelectorAll('[lsdata]').length; } catch (e) {}
    try {
      const iframes = document.querySelectorAll('iframe');
      for (let i = 0; i < iframes.length; i++) {
        const el = iframes[i];
        const r = el.getBoundingClientRect();
        out.frames.push({ selector: frameSelector(el),
                          src: String(el.getAttribute('src') || '').slice(0, 200),
                          visible: !!(r.width || r.height) });
      }
    } catch (e) {}
    return out;
  }

  // ---- Informations de survol pour la superposition du Spy ------------------
  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, width: r.width, height: r.height };
  }
  // Pour le nœud DOM sous le curseur, retourne {rect, label} du contrôle propriétaire
  // (UI5) ou de l'élément WebGUI `lsdata` le plus proche, ou null si aucun ne s'applique.
  function highlightInfo(node) {
    if (!node || node.nodeType !== 1) node = node ? node.parentElement : null;
    if (!node) return null;
    if (isUI5()) {
      const c = closestControl(node);
      if (c && c.getDomRef && c.getDomRef()) {
        const sh = shortType(c.getMetadata().getName());
        const p = props(c);
        let label = sh;
        for (let i = 0; i < ALLOWED.length; i++) {
          const n = ALLOWED[i];
          if (n in p && typeof p[n] !== 'object' && String(p[n]) !== '') {
            label = sh + " \u00b7 " + n + "='" + String(p[n]).slice(0, 40) + "'";
            break;
          }
        }
        return { rect: rectOf(c.getDomRef()), label: label };
      }
    }
    const sid = captureSid(node);
    if (sid && sid.sid) {
      let cur = node;
      while (cur) {
        if (cur.hasAttribute && cur.hasAttribute('lsdata'))
          return { rect: rectOf(cur), label: 'SID ' + sid.sid };
        cur = cur.parentElement;
      }
    }
    // Page sans registre UI5 ni lsdata : hôte Web Component ui5-* le plus proche.
    const wcEl = closestWcElement(node);
    if (wcEl) {
      const t = (wcEl.textContent || '').trim().slice(0, 40);
      return { rect: rectOf(wcEl),
               label: 'WC ' + wcEl.tagName.toLowerCase() + (t ? " \u00b7 '" + t + "'" : '') };
    }
    // Zone non-SAP (widget React/Angular/vanilla) : cible interactive du moteur dom.
    const domEl = interactiveDomTarget(node);
    if (domEl) {
      const role = ariaRole(domEl);
      const name = accName(domEl);
      return { rect: rectOf(domEl),
               label: 'DOM ' + (role || domEl.tagName.toLowerCase()) +
                 (name ? " \u00b7 '" + String(name).slice(0, 40) + "'" : '') };
    }
    return null;
  }

  // Sérialise l'arbre de contrôles UI5 en chaîne XML (perception pour un agent IA :
  // il y lit types/ids/propriétés et en déduit un sélecteur role/xpath stable).
  // Renvoie null tant qu'AUCUN contrôle n'est monté, pour que le polling côté lib
  // attende le rendu asynchrone au lieu de retourner un arbre vide.
  function dumpTree() {
    if (!isUI5()) return null;
    try {
      const doc = buildTree();
      if (!doc.documentElement || !doc.documentElement.firstElementChild) return null;
      return new XMLSerializer().serializeToString(doc);
    } catch (e) { return null; }
  }

  window.__SAPFX = { isUI5: isUI5, resolveByXPath: resolveByXPath,
                     resolveByRole: resolveByRole, resolveByWc: resolveByWc,
                     resolveByDom: resolveByDom, pageComposition: pageComposition,
                     capture: capture, captureWc: captureWc, captureDom: captureDom,
                     bestXpath: bestXpath, readTable: readTable, dumpTree: dumpTree,
                     idleState: idleState, getMessages: getMessages,
                     captureSid: captureSid, highlightInfo: highlightInfo };
})();
(function () {
  if (!window.__SAPFX) { console.error('[UI5 Recorder] __SAPFX bundle missing.'); return; }
  if (window.__ui5SpyStop) { console.info('[UI5 Recorder] already running.'); return; }

  // Texte de sélecteur destiné à une cellule RF SIMPLE (text= wc, name= dom).
  // Les blancs sont normalisés (une cellule ne porte ni saut de ligne ni run de
  // 2+ espaces ; les moteurs normalisent leur cible de la même façon) et une
  // amorce de variable RF est échappée (\${…}, littéral après relecture par
  // Robot). Le backslash reste le SEUL caractère non transmissible (Robot le
  // consomme à la relecture) : on garde alors le plus long segment sans
  // backslash. L'apostrophe, elle, passe intacte : elle n'a jamais gêné une
  // cellule RF, seulement le littéral Python des properties (voir pyQuoted).
  function safeMatchText(value) {
    var s = cleanCell(value);
    if (!s) return null;
    if (s.indexOf('\\') !== -1) {
      var parts = s.split('\\');
      var best = '';
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i].trim();
        if (p.length > best.length) best = p;
      }
      s = best;
    }
    s = s.replace(/([$@&%])\{/g, '\\$1{');
    return s || null;
  }
  // Valeur d'un littéral Python (properties={'k': <ici>}), relu par
  // ast.literal_eval APRÈS le déséchappement Robot. Le guillemet est choisi
  // pour ne pas entrer en conflit avec le contenu (« Editor's Choice » part
  // entre guillemets doubles) : aucune troncature sur l'apostrophe, qui était
  // la cause n°1 de sélecteurs raccourcis donc ambigus. Retourne le littéral
  // complet (guillemets compris), ou null si le contenu porte les DEUX sortes
  // de guillemets (cas résiduel : l'appelant dégrade son sélecteur).
  function pyQuoted(value) {
    var s = safeMatchText(value);
    if (s === null) return null;
    if (s.indexOf("'") === -1) return "'" + s + "'";
    if (s.indexOf('"') === -1) return '"' + s + '"';
    return null;
  }
  // Un xpath part dans une cellule RF (ligne Resolve ou indice « # xpath: ») :
  // saut de ligne, run de 2+ espaces, amorce de variable RF ou backslash
  // (consommé par Robot à la relecture) le casseraient ; on l'omet plutôt que
  // d'émettre une ligne corrompue, et l'omission est ANNONCÉE par l'appelant.
  function rfSafeCell(text) {
    return !/[\r\n\\]| {2,}|[$@&%]\{/.test(String(text));
  }
  // Arguments de sélecteur (id ou controlType + properties), communs aux lignes
  // Resolve (inspecteur) et Click/Fill (recorder).
  function roleArgs(r) {
    if (r.id) return 'id=' + r.id;
    if (r.idSuffix) return 'idSuffix=' + r.idSuffix;   // id stable Fiori Elements (fe::…)
    if (r.properties) {
      var k = Object.keys(r.properties)[0];
      var v = pyQuoted(r.properties[k]);
      if (v !== null) return "controlType=" + r.controlType + "    properties={'" + k + "': " + v + "}";
    }
    // Dégradation en type SEUL : le replay prendra le PREMIER contrôle de ce
    // type. On l'annonce dans la ligne plutôt que de laisser croire à un
    // sélecteur discriminant (un clic rejoué ailleurs, en silence, est pire
    // qu'un step visiblement à compléter).
    return 'controlType=' + r.controlType
      + '    # sélecteur non discriminant : la propriété enregistrée n\'est pas'
      + ' transmissible telle quelle, préciser le contrôle avant de rejouer';
  }
  function roleLine(cap) { return 'Resolve Ui5 Control    ' + roleArgs(cap.role); }
  function clickLine(cap) { return 'Click Ui5 Control    ' + roleArgs(cap.role); }
  function fillLine(cap, value) { return 'Fill Ui5 Input    ' + value + '    ' + roleArgs(cap.role); }
  // Chaque step UI5 enregistré naît avec son REPLI xpath en commentaire RF :
  // l'export resource-first le convertit en Resolve Ui5 With Fallback (le step
  // s'auto-répare dès le premier replay), et le replay in-page l'essaie quand
  // le sélecteur primaire ne résout plus (esprit « fallback locators » de
  // Selenium IDE, sur nos moteurs sémantiques).
  function withXpathHint(line, cap) {
    if (!cap || !cap.xpathShort) return line;
    if (rfSafeCell(cap.xpathShort)) return line + '    # xpath: ' + cap.xpathShort;
    // Repli xpath IMPOSSIBLE à transmettre en cellule RF : le step ne naîtra
    // pas auto-réparable. On le DIT (l'omission muette laissait croire à un
    // step qui se répare, jusqu'au jour où le sélecteur primaire dérive). Le
    // préfixe diffère de « # xpath: » à dessein : l'export resource-first ne
    // doit PAS prendre cette phrase pour un localisateur de repli.
    return line + '    # xpath indisponible : non transmissible en cellule'
      + ' Robot, ce step n\'a pas de repli auto-réparable';
  }
  function xpathLine(cap) {
    var x = cap.xpathShort || cap.xpath;
    return (x && rfSafeCell(x)) ? 'Resolve Ui5 By Xpath    ' + x : '';
  }
  // Web Component (page hors registre UI5) : arguments du moteur wc.
  function wcArgs(wc) {
    var t = wc.text ? safeMatchText(wc.text) : null;
    return 'tag=' + wc.tag + (t ? '    text=' + t : '');
  }
  // Zone non-SAP : arguments du moteur dom (rôle + nom accessible de préférence,
  // chemin CSS light-DOM sinon). Espaces normalisés : un run de 4 espaces dans un
  // nom accessible couperait la ligne RF en cellules.
  function cleanCell(v) { return String(v == null ? '' : v).replace(/\s+/g, ' ').trim(); }
  // --- échappement Robot Framework des VALEURS enregistrées ------------------
  // Une valeur saisie (ou un texte de page assertionné) part telle quelle dans
  // un .robot : sans échappement, ${...} y serait résolu comme variable RF à
  // l'exécution (« Variable not found »), un run de 2+ espaces couperait la
  // cellule, un '#' de tête ouvrirait un commentaire, et une valeur « mot=... »
  // deviendrait un argument nommé. rfUnescape est l'inverse exact : le replay
  // in-page l'applique avant d'utiliser la valeur.
  function rfEscape(value, isValue) {
    if (value === undefined || value === null || value === '') return '${EMPTY}';
    var s = String(value);
    s = s.replace(/\\/g, '\\\\');
    s = s.replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t');
    s = s.replace(/([$@&%])\{/g, '\\$1{');   // texte enregistré = littéral, jamais une variable RF vivante
    s = s.replace(/ ( +)/g, function (m, extra) {
      return ' ' + extra.replace(/ /g, '\\ ');               // 'a  b' -> 'a \ b'
    });
    if (s.charAt(0) === ' ') s = '\\' + s;
    if (s.charAt(0) === '#') s = '\\' + s;
    if (s.charAt(s.length - 1) === ' ') {
      // un nombre IMPAIR de backslashes devant l'espace final = déjà échappé
      var bs = /\\*(?= $)/.exec(s)[0].length;
      if (bs % 2 === 0) s = s.slice(0, -1) + '\\ ';
    }
    if (isValue) s = s.replace(/^([A-Za-z_][A-Za-z0-9_]*)=/, '$1\\=');
    return s;
  }
  function rfUnescape(token) {
    if (token === '${EMPTY}') return '';
    var out = '';
    for (var i = 0; i < token.length; i++) {
      var ch = token.charAt(i);
      if (ch === '\\' && i + 1 < token.length) {
        var next = token.charAt(i + 1);
        if (next === 'n') { out += '\n'; i++; continue; }
        if (next === 'r') { out += '\r'; i++; continue; }
        if (next === 't') { out += '\t'; i++; continue; }
        out += next; i++; continue;      // \\  \<espace>  \#  \$ et tout autre échappement
      }
      out += ch;
    }
    return out;
  }
  function domArgs(d) {
    var n = d.name ? safeMatchText(d.name) : null;
    if (d.role && n) return 'role=' + d.role + '    name=' + n;
    if (d.role) return 'role=' + d.role + '    css=' + d.css;
    return 'css=' + d.css;
  }
  function allLines(rec) {
    var out = [];
    if (rec.cap) { out.push(roleLine(rec.cap)); var x = xpathLine(rec.cap); if (x) out.push(x); }
    if (rec.sid) out.push('Resolve Sid    ' + rec.sid);
    if (rec.wc) out.push('Resolve Wc Control    ' + wcArgs(rec.wc));
    if (rec.dom) out.push('Resolve Dom Element    ' + domArgs(rec.dom));
    return out.join('\n');
  }
  function copy(text, btn) {
    function flash(label) {
      if (!btn) return;
      if (btn.__ui5CopyLabel === undefined) btn.__ui5CopyLabel = btn.textContent;
      btn.textContent = label;
      setTimeout(function () { btn.textContent = btn.__ui5CopyLabel; }, 700);
    }
    // Repli des contextes SANS presse-papier asynchrone : une origine non
    // sécurisée (WebGUI intranet servi en http) n'a PAS navigator.clipboard,
    // et writeText rejette en asynchrone (document sans focus, iframe
    // cross-origin sous permissions policy...). Textarea temporaire parenté
    // AU PANNEAU (inOurUI, comme l'ancre de download) + execCommand('copy') :
    // le bouton affiche le résultat RÉEL, jamais « copied » quand rien n'a
    // été copié (l'ancien code le prétendait quand clipboard était absent).
    function legacyCopy() {
      var ok = false;
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed'; ta.style.opacity = '0';
        panel.appendChild(ta);
        ta.select();
        ok = !!(document.execCommand && document.execCommand('copy'));
        ta.remove();
      } catch (e) { ok = false; }
      flash(ok ? 'copied' : 'copy failed');
    }
    try {
      if (navigator.clipboard) {
        var p = navigator.clipboard.writeText(text);
        if (p && typeof p.then === 'function') {
          p.then(function () { flash('copied'); }, legacyCopy);
          return;
        }
      }
      legacyCopy();
    } catch (e) { legacyCopy(); }
  }

  // --- superposition de survol (pointer-events none afin de ne jamais intercepter la souris) ---
  var box = document.createElement('div');
  box.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;' +
    'border:2px solid #0a6ed1;background:rgba(10,110,209,0.10);border-radius:2px;' +
    'display:none;transition:all .03s linear;';
  var chip = document.createElement('div');
  chip.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;' +
    'background:#0a6ed1;color:#fff;font:12px/1.4 monospace;padding:2px 6px;' +
    'border-radius:3px;white-space:nowrap;display:none;max-width:80vw;overflow:hidden;' +
    'text-overflow:ellipsis;';
  document.documentElement.appendChild(box);
  document.documentElement.appendChild(chip);

  // --- persistance du déroulé (sessionStorage : survit aux rechargements) ----
  var STORE_KEY = '__ui5RecorderSteps';
  var NAME_KEY = '__ui5RecorderName';
  var REC_KEY = '__ui5RecorderRecording';
  // Une ÉCRITURE sessionStorage qui échoue (quota plein, stockage bloqué par
  // la politique du site) perdrait steps et état de record en silence au
  // prochain rechargement : prévenir UNE fois dans la console, sans jamais
  // bloquer l'enregistrement. Les lectures, elles, retombent sur les défauts.
  var storageWarned = false;
  function warnStorage(e) {
    if (storageWarned) return;
    storageWarned = true;
    try {
      console.warn('[SAPFX recorder] sessionStorage en \u00e9chec (' +
        (e && e.message ? e.message : e) +
        ') : le d\u00e9roul\u00e9 ne survivra pas \u00e0 un rechargement.');
    } catch (e2) {}
  }
  function loadSteps() { try { var s = sessionStorage.getItem(STORE_KEY); return s ? JSON.parse(s) : []; } catch (e) { return []; } }
  function saveSteps() { try { sessionStorage.setItem(STORE_KEY, JSON.stringify(steps)); } catch (e) { warnStorage(e); } }
  function loadName() { try { return sessionStorage.getItem(NAME_KEY) || 'Scenario enregistre'; } catch (e) { return 'Scenario enregistre'; } }
  // L'ÉTAT d'enregistrement survit aussi à la navigation : après un reload +
  // ré-injection (snippet recollé ou raccourci extension), l'enregistrement
  // reprend tout seul au lieu de perdre silencieusement les interactions,
  // une navigation cross-app du launchpad recharge la page entière.
  function saveRecording() { try { sessionStorage.setItem(REC_KEY, recording ? '1' : ''); } catch (e) { warnStorage(e); } }
  function loadRecording() { try { return sessionStorage.getItem(REC_KEY) === '1'; } catch (e) { return false; } }
  // L'URL de DÉBUT d'enregistrement (portée de rf-web-recorder) : les exports
  // amorcent New Page sur la page où le déroulé a COMMENCÉ, pas sur celle du
  // moment de l'export (constaté live : un record login -> dashboard exporté
  // depuis le dashboard rejouait au mauvais endroit). Posée au démarrage du
  // record et jamais écrasée ensuite : la reprise post-navigation repasse par
  // setRecording(true) avec l'URL d'arrivée, qui ne doit pas gagner. Purgée
  // par clear, restaurée par l'import d'un .robot (round-trip).
  var URL_KEY = '__ui5RecorderStartUrl';
  function rememberUrl() {
    try {
      if (!sessionStorage.getItem(URL_KEY)) sessionStorage.setItem(URL_KEY, location.href);
    } catch (e) { warnStorage(e); }
  }
  function startUrl() {
    try { return sessionStorage.getItem(URL_KEY) || location.href; } catch (e) { return location.href; }
  }

  // --- panneau intégré listant les sélecteurs capturés -----------------------
  var captures = [];
  var steps = loadSteps();   // restauré après un rechargement de page (persistance)
  var recording = false;
  var panel = document.createElement('div');
  panel.id = '__ui5SpyPanel';
  // 470px : à 380 l'en-tête débordait ses 7 boutons, et `overflow:hidden` rognait
  // « stop » : bouton réellement inatteignable à la souris (vu à l'image sur une
  // app Fiori Elements). Largeur + titre qui s'ellipse = en-tête sur UNE ligne.
  panel.style.cssText = 'position:fixed;z-index:2147483647;right:12px;bottom:12px;' +
    'width:470px;max-height:55vh;display:flex;flex-direction:column;background:#fff;' +
    'border:1px solid #b3b3b3;border-radius:6px;box-shadow:0 4px 16px rgba(0,0,0,.25);' +
    'font:12px/1.45 -apple-system,Segoe UI,sans-serif;color:#222;overflow:hidden;';
  var head = document.createElement('div');
  head.style.cssText = 'display:flex;align-items:center;gap:6px;padding:8px 10px;' +
    'background:#0a6ed1;color:#fff;font-weight:600;cursor:move;';   // cursor:move -> déplaçable
  head.title = 'SAPFX Recorder : glisser l\'en-t\u00eate pour d\u00e9placer le panneau';
  // Picto aicabra (identité du projet) : data-URI embarqué, jamais de requête
  // réseau. onerror = repli silencieux si une CSP img-src stricte bloque le
  // data: (purement décoratif). Le curseur move sur l'image renforce l'indice
  // « ce panneau se déplace » (constaté utile : le drag existait mais restait
  // invisible tant qu'on ne survolait pas l'en-tête).
  var logo = document.createElement('img');
  logo.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABwAAAAcCAYAAAByDd+UAAAJNklEQVR42oWWa3BcZRnH/++57tlbtnvNbrK5t2kKbSlUoFhaKzdbxqEiKSMqzqDIINNBwCID1RBRGGaozuhQVIbLDI4jCS0IpdIWrAx84No20GwuTdKkabLJ3s+ePWfP/fUDhqkI8v/4Ps/8f8/zfHn/wBeIUkoopexn3oKU0hWqql4qy/IGSmkPpbQBIJ/2DAwMsJRS8kW+n1sYGBhgd+zY4fwH0jQ1MbF9fHxsW1WurHZcGrMsy+NYJlzAcG27wLJMJhSO/OPC9WtebG/vmf6sx/8FUkpZQohDKQ1Pnhp/4PiHH/xQ8HgaGpMp+LxeOI4Nx3HAEALTsqEqMoqFAnK5HCpyRY3HY89ce+XWh5JdXbnPg/4X8OjRo9yWLVtsSukVrx189c9aTeno6FyOlrY2++RHH5NarcZU5TIikQh57933EA4vo/6AH5JHdL0+L83l8lxhcRF1Q59tbW+/9Qe3/PhQX18f19/fb/8PcAmmKMpNf9+/77lwJMJsvHyT/cH777N1TSXDwxk4toNUKolUUxKjI6NgGQZVRYZhGCgVilixciUVPaIzPzfPyeUyUk3pH91z331PnQsl5967lC9d99KLgy91dHW6zU1peuCVA2xbWyump2ew8fKNiCfiMOoaKnIFHMuC4zlk57OYm5vD6akpyJUyBNGDdRde5E5OTCC/mGPikegNux9+eF9vby87ODjoEEopQwihlNL2Z57804nmdLN/2bIIHRsbY3RdRyQcwRVXXonhzDD27XsBoyOjUDUNlLpgGILlXV249NJLEAmHceLEEAgBWJaFququYRiQyxWtva1t3f39/ZN9fX2EGxwcJAzDuIN/++vjgiAEPIJoD5/8mKMUWL/+K4hFo9h17y7s3/8iGhsTCEciSDUmwbMszmTz+PDYMI4c+ScuuGANrrn6atSUKoYzI/BKEhOLNdpypeqfPn1mLwG5GgAhADA8NLTpyJHDb55//nnOwuIC6zoO0ukWxOIJ/HbPY6AALtmwEdSxYJo6GIaFrptwHAqOcVGsapiZGEdNKWPdRRejVCygUCxAED2IhGPO4nyWjccSX/vdE394kwGAt956+3a/30ep69LxsVNQlBpSTSns/sVujJ6awo033oSTQ8dRq1ZBCA+vtwGu42J+7gxOjoxg4tQIulf2YPpsDq+8egDBhhAIWNimhUq5RDlBpIVi8TYAYCuVyrI3Dh/eEwo1+KemJommaaS7ewWGhzMYHNyPG67fgbGxETQlYuAECaLHh2i8Eapq4PXXj0I3dDRGozBMB5LHA8PQ4ToUDcEginIZDAgReIGomhr/5vbrnmQOvvzyOk1T43BdWigUiVKtQhRFHDx4CGt6VqFUyCPRmIKsU1BWRGtXJ1rSzVi95nxctmED5ufymJmeg5cnkOUyQg1hZBey4DgeHkGEVleJZRkUQCI7m13LzZ45s4IhDLLZrFtTVTYaDiO3kMPk5BRWrerBwsI80i1NOH58CN09q3B2dhbxWBzxaATvvvM2elZ0IruYx2IuD5dS+AISRJ6FazsQRB4MA/A871qOzVLX7GZqihyv1zU4jgvHcWAYBhayWRBCUK4qqGkmsosl6DUFtK6hI90COBZmZybQ1d6JdDKFaCyBUkUGB4pkLAqvJIIXBFDbRbVahUtdsIQAlMbZjRsu26Tr+hZV02i+kGe8Xh8ch2DmzAwSiTiIY4EwBMWyjEAggPHxcQgeBt/Yug1+XwMYQYAvGESlmIeq1lCSFbguRTKZhC/gQzKRhEeUqKbVGIFj/8W5lOSVWh3BYACt6VYABKZpwu/3Y2b6NBKxRtTkKiyzjrHxUQg8DwB4/vn9oAC6zluDBupCVWQ4LiAQFpFoDMuWBaEoKly4EMCCZQWIPm+BkwRuzKjXUbZdxh8IAI4DTuSxLByGXFMhSl6IXhEgNhLxNNZffAmW93SjOZVCNBrDYj6Hvgd+Dt4jISgxUA0DzU0peETxk1NyPAr5IsNyLCINkVFmzYoVx1mWWdR1gxRyOZpdnIVR1xEOhCAKHCzbAsvwaE2ncTY7g7HxUdQ1FXK1jDcOH8JDv7wfoDbWre5BsSSDJRTtHS2wqYPZs2eh1zVqOw7xePjF1V1txwgA3Pr9W54ry5XvchxxKLU5lmURCkZQqshQdQvE1ZFsaoZcqSCbnYNpmgAoCAii8SRWruzG6YkJzC3ksKN3O1Yu78Q7778HpaYi6A/Y5YrM+v3ev/z60cdu5gAgFo0+rtaq3zNMm/AeFoZpQlFriEXDIOUyjg1l8PHIKASBgyjwYFgeqqrAdhzIShXHTxwDw/G49+6fYv36tchkMtDUOpLxOCzLJqLAk2BD4AkAIEvfxm0337KvWMxfz4uCLfm8nCSJgMtCEHhomoKFfBE1VQXHEAiCAMuyIFdrYDkOLa0tuHbrVTivZzmGT2YwMXkalYqMzvZ2ez6b5bw+70u7f/Wbbw0M9LLcqlWrKADSmEjv1OrqpqoiR31+v0vAMlVNBjQGTckUmprT0A0DdV2DJAqIRmIwbIqOjhZ0trdCqSoYH51ATdWg1evoWdntzsycZb2+QKm1uXknpZQ8+OCDn6SrpS3vvuOOq7Jz869phkESiYQry2XWpS44XkBnZwdCoQZ4JS9CoRD8XgmCwMMwTRSLRRRyBRiWhYsuXItCoeRMTk4xkuSFz9ewdefP7jq0xGABIJPJ0N7eXvapZ5+duGbz1zMOdbaXKyU+HI3aHtFDCAFpTCYwn80im81ifn4eokdEqVzB8aEhGIYJ13URi8WobprO9MwZjhcEOx6Pfef2O+98ua+vj9u7d68DAJ/mzkwmQ/s2b+Ye2ffCyW1XbT3KCdxX1ZoSJwCJRiK2JEm0Uq4QSikCAT+RBBGJeJwSAJIkuR5JcqvVKlssFhiPKI76PL4bfnLXPa99YYha0tLqO3fuDLLUub8my7cRhoRYnodHFMHzPIKhEHiWA88ysCwLpmPDsR1Q0GLAJ/1xZHL20aefflr50pi4pL6+Pqa/v98FgF27dqUcXfu2aZrbHMtaazlWmBdE0SN6YNt23St5ipIkfcRzzIGape5/5JHfL37W40uBS7WBgQHm3Amf3LMnLOt63NSVBp6TkIhEiuV8Pndnf3/1nGG5/v5+BwD9PNd/Ay62shAOp5q7AAAAAElFTkSuQmCC';
  logo.alt = 'aicabra';
  logo.style.cssText = 'width:20px;height:20px;border-radius:50%;flex:0 0 auto;' +
    'cursor:move;background:#fff;';
  logo.onerror = function () { logo.style.display = 'none'; };
  var dot = document.createElement('span');   // indicateur d'enregistrement (rouge clignotant)
  dot.style.cssText = 'width:9px;height:9px;border-radius:50%;background:#ff3b30;display:none;' +
    'flex:0 0 auto;box-shadow:0 0 4px #ff3b30;';
  // min-width:0 + ellipsis : sans quoi un titre long (« Recording : 12 step(s) »)
  // pousse les boutons hors du panneau au lieu de se tronquer lui-même.
  var title = document.createElement('span');
  title.style.cssText = 'flex:1 1 auto;min-width:0;white-space:nowrap;' +
    'overflow:hidden;text-overflow:ellipsis;';
  var btnCollapse = document.createElement('button');
  var btnRec = document.createElement('button');
  var btnPlay = document.createElement('button');
  var btnNewTest = document.createElement('button');
  var btnExport = document.createElement('button');
  var btnClear = document.createElement('button');
  var btnClose = document.createElement('button');
  [btnCollapse, btnRec, btnPlay, btnNewTest, btnExport, btnClear, btnClose].forEach(function (b) {
    b.style.cssText = 'border:1px solid #fff;background:transparent;color:#fff;' +
      'border-radius:4px;cursor:pointer;font:11px monospace;padding:2px 7px;' +
      'flex:0 0 auto;white-space:nowrap;';   // jamais compressés ni repliés
  });
  btnCollapse.textContent = '\u25be';   // ▾ (déplié)
  btnRec.textContent = 'rec'; btnPlay.textContent = 'play';
  btnNewTest.textContent = '+test'; btnExport.textContent = 'export';
  btnClear.textContent = 'clear'; btnClose.textContent = 'stop';
  head.appendChild(logo); head.appendChild(dot); head.appendChild(title); head.appendChild(btnCollapse);
  head.appendChild(btnRec); head.appendChild(btnPlay); head.appendChild(btnNewTest);
  head.appendChild(btnExport); head.appendChild(btnClear); head.appendChild(btnClose);
  var nameRow = document.createElement('div');
  nameRow.style.cssText = 'display:flex;align-items:center;gap:6px;padding:4px 10px;border-bottom:1px solid #eee;';
  var nameLbl = document.createElement('span'); nameLbl.textContent = 'Test:'; nameLbl.style.color = '#666';
  var nameInput = document.createElement('input');
  nameInput.type = 'text'; nameInput.value = loadName();
  nameInput.style.cssText = 'flex:1;font:11px monospace;border:1px solid #ccc;border-radius:3px;padding:2px 5px;';
  nameInput.addEventListener('input', function () { try { sessionStorage.setItem(NAME_KEY, nameInput.value); } catch (e) { warnStorage(e); } });
  nameRow.appendChild(nameLbl); nameRow.appendChild(nameInput);
  var list = document.createElement('div');
  list.style.cssText = 'overflow:auto;padding:6px;';
  var hint = document.createElement('div');
  hint.style.cssText = 'padding:6px 10px;color:#666;border-top:1px solid #eee;';
  hint.textContent = 'Hover + click to capture. rec to record, play to replay in-page. Right-click / Alt+click = assert. Esc to stop.';
  // Frames cross-origin : ce panneau ne peut PAS les instrumenter (le snippet
  // collé en console ne voit que sa frame). L'extension, elle, injecte en
  // allFrames : un panneau séparé apparaît DANS chaque frame accessible.
  var frameWarn = document.createElement('div');
  frameWarn.style.cssText = 'padding:4px 10px;color:#a15c00;background:#fff8ec;' +
    'border-top:1px solid #f0e0c0;display:none;';
  function crossOriginFrameCount() {
    var n = 0;
    try {
      var frames = document.querySelectorAll('iframe');
      for (var i = 0; i < frames.length; i++) {
        try { if (!frames[i].contentDocument) n++; } catch (e) { n++; }
      }
    } catch (e) {}
    return n;
  }
  function updateFrameWarn() {
    var n = (window.top === window.self) ? crossOriginFrameCount() : 0;
    if (n) {
      frameWarn.textContent = '\u26a0 ' + n + ' iframe(s) cross-origin non instrument\u00e9e(s) ' +
        'par ce panneau : utiliser l\'extension (allFrames : un panneau par frame).';
      frameWarn.style.display = '';
    } else { frameWarn.style.display = 'none'; }
  }
  panel.appendChild(head); panel.appendChild(nameRow); panel.appendChild(list);
  panel.appendChild(frameWarn); panel.appendChild(hint);
  document.documentElement.appendChild(panel);

  // animation du point d'enregistrement
  var styleEl = document.createElement('style');
  styleEl.textContent = '@keyframes __ui5RecBlink{50%{opacity:.25}}';
  document.documentElement.appendChild(styleEl);

  // repli du panneau (n'affiche plus que l'en-tête)
  var collapsed = false;
  function setCollapsed(c) {
    collapsed = c;
    nameRow.style.display = c ? 'none' : '';
    list.style.display = c ? 'none' : '';
    hint.style.display = c ? 'none' : '';
    if (c) { frameWarn.style.display = 'none'; } else { updateFrameWarn(); }
    btnCollapse.textContent = c ? '\u25b8' : '\u25be';   // ▸ replié / ▾ déplié
  }
  btnCollapse.addEventListener('click', function () { setCollapsed(!collapsed); });

  // déplacement du panneau en glissant l'en-tête (bascule de right/bottom vers left/top)
  var drag = null;
  function onDragDown(e) {
    if (e.target.tagName === 'BUTTON') return;
    var r = panel.getBoundingClientRect();
    drag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    panel.style.right = 'auto'; panel.style.bottom = 'auto';
    panel.style.left = r.left + 'px'; panel.style.top = r.top + 'px';
    e.preventDefault();
  }
  function onDragMove(e) {
    if (!drag) return;
    // un mouseup hors de la fenêtre ne nous parvient jamais : un mouvement
    // sans bouton enfoncé signifie que le drag est déjà terminé.
    if (e.buttons === 0) { drag = null; return; }
    panel.style.left = (e.clientX - drag.dx) + 'px';
    panel.style.top = (e.clientY - drag.dy) + 'px';
  }
  function onDragUp() { drag = null; }
  head.addEventListener('mousedown', onDragDown, true);
  document.addEventListener('mousemove', onDragMove, true);
  document.addEventListener('mouseup', onDragUp, true);

  function mkBtn(label, text) {
    var b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'margin:0 4px 0 0;border:1px solid #0a6ed1;background:#fff;' +
      'color:#0a6ed1;border-radius:4px;cursor:pointer;font:11px monospace;padding:1px 7px;';
    b.addEventListener('click', function () { copy(text, b); });
    return b;
  }
  var flashTimer = 0, flashOrig = '';
  function flashGreen() {
    // Le fond de repos n'est photographié qu'à l'arrêt : deux flashs qui se
    // chevauchent (fill + Entrée différée dans le même tick) photographieraient
    // le vert et restaureraient le vert, définitivement.
    if (flashTimer) clearTimeout(flashTimer);
    else flashOrig = box.style.background;
    box.style.background = 'rgba(16,179,16,0.25)';
    flashTimer = setTimeout(function () {
      box.style.background = flashOrig;
      flashTimer = 0;
    }, 150);
  }
  // Clé d'identité d'un step Fill (keyword + localisateur, valeur exclue) : une
  // re-saisie du même champ REMPLACE la précédente au lieu de s'empiler.
  function fillKey(line) {
    // Cellules d'action seulement : un commentaire de fin de ligne (repli
    // xpath, avertissement) ne fait pas partie de l'identité du localisateur.
    var cells = splitStepCells(line).cells;
    if (cells[0] === 'Fill Ui5 Input' || cells[0] === 'Fill Wc Input' ||
        cells[0] === 'Fill Dom Input') return cells[0] + '|' + cells.slice(2).join('|');
    if (cells[0] === 'Fill Sid Input') return cells[0] + '|' + cells[1];
    return null;
  }
  var WAIT_STEPS = { 'Wait For Load State    load': 1, 'Wait For UI5 Ready': 1 };
  // Deux clics (ou deux Entrées) identiques enregistrés à moins de 500 ms = un
  // double dispatch du même événement ; au-delà, c'est une répétition
  // VOLONTAIRE (bouton « + » d'un stepper, pagination, double validation) qui
  // doit produire deux steps.
  var CLICK_DEDUP_WINDOW_MS = 500;
  var lastStepAt = 0;
  function addStep(line) {
    var now = Date.now();
    var last = steps.length ? steps[steps.length - 1] : null;
    if (last === line &&
        !(/^(Click |Keyboard Key)/.test(line) && now - lastStepAt >= CLICK_DEDUP_WINDOW_MS)) {
      return;                                                     // dédup consécutif
    }
    var replaced = false;
    if (last === line) { /* répétition volontaire : append */ }
    else {
      if (last && fillKey(last) !== null && fillKey(last) === fillKey(line)) replaced = true;
      if (last && WAIT_STEPS[last] && WAIT_STEPS[line]) replaced = true;   // attentes consécutives
    }
    if (replaced) steps[steps.length - 1] = line;
    else steps.push(line);
    lastStepAt = now;
    saveSteps(); render(); flashGreen();
  }
  // Déclenche le téléchargement d'un fichier texte (sans dépendance, via un Blob).
  // L'ancre est parentée AU PANNEAU (inOurUI) : sinon la capture dom intercepte
  // son propre clic synthétique : une ancre href a le rôle 'link', donc cible
  // interactive → preventDefault → téléchargement annulé (attrapé par le smoke
  // recorder_web_smoke lors du passage à captureDom, 2026-07-19).
  function download(text, filename) {
    try {
      var blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = filename; a.style.display = 'none';
      panel.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    } catch (e) {
      // Un échec (CSP sandbox, Blob/objectURL interdits...) était avalé en
      // silence : l'utilisateur croyait son export parti. Remonté dans le
      // bandeau du panneau ; la copie presse-papiers reste le secours.
      hint.textContent = '\u00c9chec du t\u00e9l\u00e9chargement de ' + filename + ' : ' +
        (e && e.message ? e.message : e) + '. Utiliser la copie presse-papiers.';
    }
  }
  function testName() { return (nameInput.value || '').trim() || 'Scenario enregistre'; }
  // Le keyword Wait For UI5 Ready (copie de resources/fiori_keywords.resource) est
  // embarqué dans les exports qui l'utilisent : le fichier téléchargé reste
  // AUTONOME (il n'importe que Browser + SapFioriLibrary).
  var UI5_READY_KEYWORD = '*** Keywords ***\n' +
    'Wait For UI5 Ready\n' +
    '    Wait For Function    () => { const s = window.sap; if (!(s && s.ui)) return false; ' +
    'let E = null; try { E = s.ui.require && s.ui.require(\'sap/ui/core/Element\'); } catch (e) {} ' +
    'const c = s.ui.getCore ? s.ui.getCore() : null; if (!c && !E) return false; ' +
    'if (c && typeof c.getUIDirty === \'function\' && c.getUIDirty()) return false; ' +
    'const b = document.querySelectorAll(\'.sapUiLocalBusyIndicator, .sapMBusyDialog, #sapUiBusyIndicator\'); ' +
    'for (let i = 0; i < b.length; i++) { if (b[i].offsetParent !== null) return false; } return true; }\n' +
    '    ...    message=UI5 runtime did not become idle\n';
  function needsUi5Ready() { return steps.indexOf('Wait For UI5 Ready') !== -1; }
  // --- multi-scénarios : un marqueur (commentaire RF) sépare les tests --------
  // « +test » insère le marqueur ; chaque export le convertit en un nouveau
  // *** Test Case *** (le bootstrap New Browser/New Page ne vit que dans le
  // premier : les suivants continuent la même session).
  var TEST_MARKER = /^# --- test: (.+)$/;
  function testMarkerLine(name) { return '# --- test: ' + cleanCell(name); }
  function splitScenarios() {
    var groups = [{ name: testName(), steps: [] }];
    steps.forEach(function (line) {
      var m = line.match(TEST_MARKER);
      if (m) { groups.push({ name: m[1], steps: [] }); return; }
      groups[groups.length - 1].steps.push(line);
    });
    return groups;
  }
  // Fichier .robot COMPLET et rejouable : en-tête Settings + ouverture navigateur + steps.
  function buildScript() {
    var s = '*** Settings ***\nLibrary    Browser\nLibrary    SapFioriLibrary\n\n';
    s += '*** Test Cases ***\n';
    splitScenarios().forEach(function (group, gi) {
      s += group.name + '\n';
      if (gi === 0) {
        s += '    New Browser    chromium    headless=False\n';
        s += '    New Page    ' + startUrl() + '\n';
      }
      group.steps.forEach(function (st) { s += '    ' + st + '\n'; });
      s += '\n';
    });
    s = s.replace(/\n\n$/, '\n');
    if (needsUi5Ready()) s += '\n' + UI5_READY_KEYWORD;
    return s;
  }
  // --- export resource-first : la paire .resource + .robot sans localisateur ---
  // (convention n°1 du projet : les tests parlent métier, les localisateurs
  // vivent dans la couche resources, celle que sap-healer sait réparer).
  function slugFromArgs(argCells, fallback) {
    var text = null, id = null, tag = null, role = null, name = null, m;
    argCells.forEach(function (c) {
      if ((m = c.match(/^id=(.+)$/))) id = id || m[1];
      else if ((m = c.match(/^idSuffix=(.+)$/))) id = id || m[1];
      else if ((m = c.match(/^properties=\{'[^']+':\s*'([^']*)'\}$/))) text = text || m[1];
      else if ((m = c.match(/^text=(.+)$/))) text = text || m[1];
      else if ((m = c.match(/^name=(.+)$/))) name = name || m[1];
      else if ((m = c.match(/^tag=(.+)$/))) tag = tag || m[1];
      else if ((m = c.match(/^role=(.+)$/))) role = role || m[1];
      else if ((m = c.match(/^controlType=(.+)$/))) tag = tag || m[1];
      else if ((m = c.match(/^wnd\[/))) id = id || c;
    });
    var base = text || name || id || tag || role || fallback;
    base = String(base).replace(/[^0-9A-Za-z]+/g, '_').replace(/^_+|_+$/g, '')
      .toUpperCase().slice(0, 28);
    return base || fallback;
  }
  // keyword -> comment retrouver localisateur/valeur dans la ligne enregistrée.
  var RF_WRAPPERS = {
    'Click Ui5 Control':  { verb: 'Cliquer', locFrom: 1 },
    'Click Sid':          { verb: 'Cliquer', locFrom: 1 },
    'Click Wc Control':   { verb: 'Cliquer', locFrom: 1 },
    'Click Dom Element':  { verb: 'Cliquer', locFrom: 1 },
    'Fill Ui5 Input':     { verb: 'Saisir', locFrom: 2, valueAt: 1 },
    'Fill Wc Input':      { verb: 'Saisir', locFrom: 2, valueAt: 1 },
    'Fill Dom Input':     { verb: 'Saisir', locFrom: 2, valueAt: 1 },
    'Fill Sid Input':     { verb: 'Saisir', locFrom: 1, locTo: 2, valueAt: 2 },
    'Ui5 Control Should Be Visible': { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Wc Control Should Be Visible':  { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Dom Element Should Be Visible': { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Sid Should Be Visible':         { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Ui5 Text Should Be': { verb: 'V\u00e9rifier Texte', locFrom: 2, valueAt: 1 }
  };
  // Sépare les cellules d'action du commentaire de fin de ligne, et extrait
  // l'indice de repli xpath (posé par withXpathHint à l'enregistrement).
  function splitStepCells(line) {
    var raw = line.split('    ');
    var at = raw.length;
    for (var i = 0; i < raw.length; i++) {
      if (raw[i].charAt(0) === '#') { at = i; break; }
    }
    var comment = raw.slice(at).join('    ');
    var m = comment.match(/^# xpath: (.+)$/);
    return { cells: raw.slice(0, at), xpath: m ? m[1] : null };
  }
  function buildResourceFirst() {
    var kws = {}, order = [], counter = 0;
    function wrapLine(line) {
      var parsed = splitStepCells(line);
      var cells = parsed.cells;
      var spec = RF_WRAPPERS[cells[0]];
      if (!spec || !cells.length) return line;
      counter++;
      var locCells = spec.locTo ? cells.slice(spec.locFrom, spec.locTo)
                                : cells.slice(spec.locFrom);
      var value = (spec.valueAt !== undefined) ? cells[spec.valueAt] : null;
      var body;
      var healable = parsed.xpath &&
        (cells[0] === 'Click Ui5 Control' || cells[0] === 'Fill Ui5 Input');
      if (healable) {
        // Le step naît AUTO-RÉPARABLE : sélecteur primaire d'abord, repli xpath
        // journalisé par la chaîne de fallback de la bibliothèque sinon.
        var resolveLine = '    ${cible}=    Resolve Ui5 With Fallback    xpath=' +
          parsed.xpath + '    ' + locCells.join('    ');
        // Saisie : on descend dans l'<input>/<textarea> INTERNE, comme le fait
        // Fill Ui5 Input : un champ UI5 composite (sap.m.Input, SearchField…)
        // a une <div> pour racine, que Fill Text ne peut pas remplir.
        // (Attrapé par le run live de la paire exportée contre Fiori Elements.)
        var action = (cells[0] === 'Click Ui5 Control')
          ? '    Click    ${cible}'
          : '    Fill Text    ${cible} >> css=input, textarea    ${valeur}';
        body = ((spec.valueAt !== undefined) ? '    [Arguments]    ${valeur}\n' : '') +
          resolveLine + '\n' + action;
      } else {
        var bodyCells = cells.slice();
        if (spec.valueAt !== undefined) bodyCells[spec.valueAt] = '${valeur}';
        body = ((spec.valueAt !== undefined) ? '    [Arguments]    ${valeur}\n' : '') +
          '    ' + bodyCells.join('    ');
      }
      var kwName = spec.verb + ' ' + slugFromArgs(locCells, 'CIBLE_' + counter);
      if (kws[kwName] !== undefined && kws[kwName] !== body) kwName += ' ' + counter;
      if (kws[kwName] === undefined) { kws[kwName] = body; order.push(kwName); }
      return kwName + (value !== null ? '    ' + value : '');
    }
    // Paire d'assertion texte (menu clic droit) : `${texte} =    Get Wc/Dom
    // Text    <loc>` suivi de `Should Be Equal    ${texte}    <attendu>`,
    // enveloppée en UN keyword métier, sinon les localisateurs de la paire
    // resteraient dans la suite (convention n°1).
    function textAssertPair(line, nextLine) {
      var m = line.match(/^\$\{([^}]+)\} =    (Get Wc Text|Get Dom Text)    (.+)$/);
      if (!m || !nextLine) return null;
      var nxt = nextLine.split('    ');
      if (nxt[0] !== 'Should Be Equal' || nxt[1] !== '${' + m[1] + '}' || nxt.length < 3) return null;
      return { getter: m[2], locCells: m[3].split('    '), expected: nxt.slice(2).join('    ') };
    }
    function wrapTextAssert(pair) {
      counter++;
      var kwName = 'V\u00e9rifier Texte ' + slugFromArgs(pair.locCells, 'CIBLE_' + counter);
      var body = '    [Arguments]    ${valeur_attendue}\n' +
        '    ${texte}=    ' + pair.getter + '    ' + pair.locCells.join('    ') + '\n' +
        '    Should Be Equal    ${texte}    ${valeur_attendue}';
      if (kws[kwName] !== undefined && kws[kwName] !== body) kwName += ' ' + counter;
      if (kws[kwName] === undefined) { kws[kwName] = body; order.push(kwName); }
      return kwName + '    ' + pair.expected;
    }
    var robot = '*** Settings ***\nLibrary    Browser\nLibrary    SapFioriLibrary\n' +
      'Resource    recorded_keywords.resource\n\n';
    robot += '*** Test Cases ***\n';
    splitScenarios().forEach(function (group, gi) {
      robot += group.name + '\n';
      if (gi === 0) {
        robot += '    New Browser    chromium    headless=False\n';
        robot += '    New Page    ' + startUrl() + '\n';
      }
      for (var si = 0; si < group.steps.length; si++) {
        var pair = textAssertPair(group.steps[si], group.steps[si + 1]);
        if (pair) {
          robot += '    ' + wrapTextAssert(pair) + '\n';
          si++;                          // consomme le Should Be Equal apparié
        } else {
          robot += '    ' + wrapLine(group.steps[si]) + '\n';
        }
      }
      robot += '\n';
    });
    robot = robot.replace(/\n\n$/, '\n');
    var resource = '*** Settings ***\nLibrary    Browser\nLibrary    SapFioriLibrary\n\n';
    resource += '*** Keywords ***\n';
    order.forEach(function (n) { resource += n + '\n' + kws[n] + '\n\n'; });
    if (needsUi5Ready()) resource += UI5_READY_KEYWORD;
    return { resource: resource, robot: robot };
  }
  // --- export spec : plan Markdown au format specs/ (brouillon pour les agents) ---
  function mdCode(t) {
    // Code span Markdown littéral quel que soit le contenu (règle CommonMark) :
    // clôture plus longue que toute série de backticks interne, bourrage d'un
    // espace si le contenu commence/finit par un backtick. Une valeur saisie
    // '*LH*' (joker SAP) rendrait « LH » en italique hors code span.
    t = String(t);
    var longest = 0;
    (t.match(/`+/g) || []).forEach(function (r) { if (r.length > longest) longest = r.length; });
    var fence = new Array(longest + 2).join('`');
    var pad = (!t || t.charAt(0) === '`' || t.charAt(t.length - 1) === '`') ? ' ' : '';
    return fence + pad + t + pad + fence;
  }
  function humanizeWebStep(line, fmt) {
    fmt = fmt || mdCode;                 // spec = code span Markdown ; rapport = guillemets
    // Le commentaire de fin de ligne (indice de repli xpath, avertissement de
    // sélecteur non discriminant) n'est PAS un argument : sans ce retrait il
    // entrait dans le libellé humain de la phrase générée.
    var cells = splitStepCells(line).cells;
    var kw = cells[0];
    function target(from, to) {
      return fmt(slugFromArgs(to ? cells.slice(from, to) : cells.slice(from), 'cible').toLowerCase());
    }
    if (kw === 'Click Ui5 Control' || kw === 'Click Wc Control' ||
        kw === 'Click Dom Element' || kw === 'Click Sid') return 'Cliquer ' + target(1);
    if (kw === 'Fill Ui5 Input' || kw === 'Fill Wc Input' || kw === 'Fill Dom Input')
      return 'Saisir ' + fmt(rfUnescape(cells[1])) + ' dans ' + target(2);
    if (kw === 'Fill Sid Input')
      return 'Saisir ' + fmt(rfUnescape(cells[2])) + ' dans ' + target(1, 2);
    if (kw === 'Ui5 Text Should Be')
      return 'V\u00e9rifier que ' + target(2) + ' affiche ' + fmt(rfUnescape(cells[1]));
    if (kw.indexOf('Should Be Visible') !== -1)
      return 'V\u00e9rifier la pr\u00e9sence de ' + target(1);
    if (kw === 'Wait For Load State' || kw === 'Wait For UI5 Ready')
      return 'Attendre la fin du chargement';
    if (kw === 'Keyboard Key') return 'Valider (Entr\u00e9e)';
    return null;                         // étape inconnue : l'appelant décide (contrat specs/)
  }
  function buildSpec() {
    var md = '# ' + testName() + '\n\n';
    md += '> **Brouillon g\u00e9n\u00e9r\u00e9 par le recorder web** : \u00e0 retravailler\n';
    md += '> (r\u00e9sultats attendus, donn\u00e9es) avant passage au sap-generator.\n\n';
    md += '- **Canal** : Fiori (web)\n';
    md += '- **Syst\u00e8me / URL** : ' + startUrl() + '\n';
    md += '- **Pr\u00e9conditions** : application accessible.\n\n';
    md += '## Donn\u00e9es observ\u00e9es\n\n- Valeurs saisies pendant l\'enregistrement : voir les \u00e9tapes.\n\n';
    md += '## Sc\u00e9narios\n\n';
    var vigilance = [];
    splitScenarios().forEach(function (group, gi) {
      md += '### ' + (gi + 1) + '. ' + group.name + '\n- **\u00c9tapes** :\n';
      group.steps.forEach(function (line, i) {
        var human = humanizeWebStep(line);
        var cells = line.split('    ');
        var hasLocator = false;
        for (var j = 1; j < cells.length; j++) {
          if (/^(controlType=|properties=|id=|idSuffix=|tag=|css=|role=|name=|text=|wnd\[)/.test(cells[j])) {
            hasLocator = true;
            vigilance.push('- ' + mdCode(line) + ' (sc\u00e9nario ' + (gi + 1) + ', \u00e9tape ' + (i + 1) + ')');
            break;
          }
        }
        if (human === null) {
          // Étape inconnue : la ligne exacte ne va dans les étapes QUE si elle
          // ne porte aucun localisateur (contrat specs/ : pas d'id dans les
          // étapes) ; sinon elle vit en « Points de vigilance », déjà relevée.
          human = hasLocator
            ? '\u00c9tape technique \u00e0 traduire (ligne exacte en \u00ab Points de vigilance \u00bb)'
            : '\u00c9tape brute \u00e0 traduire : ' + mdCode(line);
        }
        md += '  ' + (i + 1) + '. ' + human + '\n';
      });
      md += '- **R\u00e9sultat attendu** : \u00e0 compl\u00e9ter (assertions ind\u00e9pendantes de la locale).\n';
      md += '- **Keywords m\u00e9tier manquants** : \u00e0 cr\u00e9er par le sap-generator.\n\n';
    });
    md += '## Points de vigilance\n\n';
    md += vigilance.length
      ? 'Localisateurs relev\u00e9s (notes factuelles pour le g\u00e9n\u00e9rateur) :\n\n' + vigilance.join('\n') + '\n'
      : '- (aucun localisateur relev\u00e9)\n';
    return md;
  }
  // --- export ISTQB : plan de test + cas de test, humain ET rejouable --------
  // Miroir web de steps_to_istqb (recorder desktop) : UN document Markdown,
  // sections plan (objectif, préconditions, critères), un cas de test PAR
  // scénario (+test) avec tableau Action / Données / Résultat attendu, et un
  // bloc replay YAML aux actions normalisées (fill/click/press_key/assert_*),
  // indépendant du framework d'exécution : cible en langage humain d'abord, le
  // localisateur relevé (et son repli xpath posé à l'enregistrement) en hint.
  function yq(t) { return "'" + String(t).replace(/'/g, "''") + "'"; }
  function mdCell(t) { return String(t).replace(/\|/g, '\\|'); }
  function istqbSlug(t) {
    // accents translittérés (NFD + diacritiques retirés) : « Scénario
    // enregistré » -> scenario-enregistre, jamais sc-nario-enregistr.
    var s = String(t);
    try { s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, ''); } catch (e) {}
    s = s.replace(/[^0-9A-Za-z]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
    return s || 'enregistrement';
  }
  var ISTQB_GENERIC_EXPECTED = 'L\u2019action s\u2019ex\u00e9cute sans erreur (\u00e0 pr\u00e9ciser)';
  var ISTQB_EXPECTED = {
    fill: 'La valeur est accept\u00e9e',
    press_key: 'L\u2019\u00e9cran suivant s\u2019affiche (\u00e0 pr\u00e9ciser)',
    wait: 'Le chargement se termine',
    assert_text: 'Texte conforme (assertion ind\u00e9pendante de la locale)',
    assert_present: 'L\u2019\u00e9l\u00e9ment est pr\u00e9sent',
    raw: '\u00e0 pr\u00e9ciser'
  };
  function istqbStep(line) {
    var cells = line.split('    ');
    var ci = -1;
    for (var i = 0; i < cells.length; i++) {
      if (cells[i].charAt(0) === '#') { ci = i; break; }
    }
    var comment = ci >= 0 ? cells.slice(ci).join('    ') : '';
    if (ci >= 0) cells = cells.slice(0, ci);
    cells = cells.filter(function (c) { return c !== ''; });
    var kw = cells[0] || '';
    function target(from, to) {
      return slugFromArgs(to ? cells.slice(from, to) : cells.slice(from), 'cible').toLowerCase();
    }
    function sel(from, to) {
      return (to ? cells.slice(from, to) : cells.slice(from)).join('    ');
    }
    function hintFor(engine, loc) {
      var h = { engine: engine, locator: loc };
      var m = comment.match(/^#\s*xpath:\s*(.+)$/);
      if (m) h.fallback = m[1];
      return h;
    }
    if (kw === 'Click Ui5 Control') return { action: 'click', target: target(1), hint: hintFor('ui5-role', sel(1)) };
    if (kw === 'Click Wc Control') return { action: 'click', target: target(1), hint: hintFor('wc', sel(1)) };
    if (kw === 'Click Dom Element') return { action: 'click', target: target(1), hint: hintFor('dom', sel(1)) };
    if (kw === 'Click Sid') return { action: 'click', target: target(1), hint: hintFor('sid', sel(1)) };
    if (kw === 'Fill Ui5 Input' || kw === 'Fill Wc Input' || kw === 'Fill Dom Input')
      return { action: 'fill', target: 'champ ' + target(2), value: rfUnescape(cells[1]),
               hint: hintFor(kw === 'Fill Ui5 Input' ? 'ui5-role' : (kw === 'Fill Wc Input' ? 'wc' : 'dom'), sel(2)) };
    if (kw === 'Fill Sid Input')
      return { action: 'fill', target: 'champ ' + target(1, 2), value: rfUnescape(cells[2]),
               hint: hintFor('sid', sel(1, 2)) };
    if (kw === 'Ui5 Text Should Be')
      return { action: 'assert_text', target: target(2), expected: rfUnescape(cells[1]),
               hint: hintFor('ui5-role', sel(2)) };
    if (/Should Be Visible$/.test(kw)) {
      var eng = kw.indexOf('Ui5') === 0 ? 'ui5-role'
        : (kw.indexOf('Wc') === 0 ? 'wc' : (kw.indexOf('Dom') === 0 ? 'dom' : 'sid'));
      return { action: 'assert_present', target: target(1), hint: hintFor(eng, sel(1)) };
    }
    if (kw === 'Wait For UI5 Ready' || kw === 'Wait For Load State') return { action: 'wait' };
    if (kw === 'Keyboard Key') return { action: 'press_key', value: cells[cells.length - 1] };
    return null;
  }
  function istqbYaml(st) {
    var out = ['  - action: ' + st.action];
    ['target', 'value', 'expected', 'line', 'note'].forEach(function (k) {
      if (st[k] !== undefined && st[k] !== null) out.push('    ' + k + ': ' + yq(st[k]));
    });
    if (st.hint) {
      out.push('    hint: {engine: ' + yq(st.hint.engine) + ', locator: ' + yq(st.hint.locator) + '}');
      if (st.hint.fallback)
        out.push('    fallback: {engine: ' + yq('ui5-xpath') + ', locator: ' + yq(st.hint.fallback) + '}');
    }
    return out;
  }
  function buildIstqb() {
    var groups = splitScenarios();
    var values = [];
    var parsed = groups.map(function (group) {
      return group.steps.map(function (line) {
        var st = istqbStep(line);
        if (st === null) st = { action: 'raw', line: line,
                                note: '\u00e9tape non traduite : ligne Robot Framework exacte' };
        if (st.action === 'fill' && st.value) values.push(st.value);
        return st;
      });
    });
    var md = '# Plan de test ISTQB : ' + testName() + '\n\n';
    md += '> G\u00e9n\u00e9r\u00e9 par le recorder web depuis ' + startUrl() + '.\n';
    md += '> Document de conception de test (ISTQB / ISO 29119-3) : lisible par\n';
    md += '> un humain, rejouable par une IA via le bloc `replay` de chaque cas\n';
    md += '> de test, ind\u00e9pendant du framework d\u2019ex\u00e9cution. Les mentions\n';
    md += '> \u00ab \u00e0 compl\u00e9ter / \u00e0 pr\u00e9ciser \u00bb sont \u00e0 renseigner avant usage\n';
    md += '> formel (l\u2019agent sap-istqb peut r\u00e9diger ce document).\n\n';
    md += '- **Identifiant** : TP-' + istqbSlug(testName()) + '\n';
    md += '- **Canal** : Fiori (web)\n';
    md += '- **Syst\u00e8me / URL** : ' + startUrl() + '\n\n';
    md += '## 1. Objectif et p\u00e9rim\u00e8tre\n\n';
    md += '- **Objectif** : \u00e0 compl\u00e9ter (constat\u00e9 : d\u00e9roul\u00e9 enregistr\u00e9 ci-dessous).\n';
    md += '- **\u00c9l\u00e9ments \u00e0 tester** : \u00e0 compl\u00e9ter.\n';
    md += '- **Hors p\u00e9rim\u00e8tre** : \u00e0 compl\u00e9ter.\n\n';
    md += '## 2. Pr\u00e9conditions et donn\u00e9es de test\n\n';
    md += '- Application accessible \u00e0 ' + startUrl() + '.\n';
    md += '- Valeurs observ\u00e9es pendant l\u2019enregistrement : ' +
      (values.length ? values.map(mdCode).join(', ') : 'aucune') + '.\n\n';
    md += '## 3. Crit\u00e8res d\u2019entr\u00e9e / de sortie\n\n';
    md += '- **Entr\u00e9e** : application accessible, pr\u00e9conditions satisfaites.\n';
    md += '- **Sortie** : tous les cas de test ex\u00e9cut\u00e9s, r\u00e9sultats attendus confirm\u00e9s.\n\n';
    md += '## 4. Cas de test\n\n';
    var trace = [];
    groups.forEach(function (group, gi) {
      var tcId = 'TC-' + (gi + 1 < 10 ? '0' : '') + (gi + 1);
      md += '### ' + tcId + ' : ' + group.name + '\n\n- **Priorit\u00e9** : \u00e0 compl\u00e9ter\n\n';
      md += '| # | Action | Donn\u00e9es | R\u00e9sultat attendu |\n';
      md += '|---|--------|---------|------------------|\n';
      parsed[gi].forEach(function (st, i) {
        var human = st.action === 'raw'
          ? '\u00c9tape non traduite : ' + mdCode(st.line)
          : (humanizeWebStep(group.steps[i]) || st.action);
        var data = (st.action !== 'press_key' && st.value !== undefined) ? st.value
          : (st.action.indexOf('assert') === 0 && st.expected !== undefined ? st.expected : '');
        md += '| ' + (i + 1) + ' | ' + mdCell(human) + ' | ' +
          mdCell(data ? mdCode(data) : '') + ' | ' +
          mdCell(ISTQB_EXPECTED[st.action] || ISTQB_GENERIC_EXPECTED) + ' |\n';
      });
      md += '\n- **Postconditions** : \u00e0 compl\u00e9ter.\n\n';
      md += 'Bloc rejouable (actions normalis\u00e9es ; les `hint` sont les\n';
      md += 'localisateurs relev\u00e9s au moment de l\u2019enregistrement) :\n\n';
      md += '```yaml\ntest_case: ' + tcId + '\ntitle: ' + yq(group.name) + '\nchannel: web\nsteps:\n';
      parsed[gi].forEach(function (st) { md += istqbYaml(st).join('\n') + '\n'; });
      md += '```\n\n';
      trace.push('| ' + tcId + ' | sc\u00e9nario ' + (gi + 1) + ' de l\u2019enregistrement, \u00e9tapes 1 \u00e0 ' +
        parsed[gi].length + ' | \u00e0 relier |');
    });
    md += '## 5. Tra\u00e7abilit\u00e9\n\n';
    md += '| Cas de test | Source | Exigence / spec |\n|---|---|---|\n' + trace.join('\n') + '\n\n';
    md += '## 6. Risques et points de vigilance\n\n';
    md += '- Les localisateurs des `hint` datent de l\u2019enregistrement : les\n';
    md += '  re-v\u00e9rifier en cas de d\u00e9rive de la page (cha\u00eene de fallback).\n';
    md += '- Ne jamais rejouer avec des attentes fixes (time.sleep) : attendre la\n';
    md += '  fin du chargement (Wait For UI5 Ready / Wait For Load State).\n';
    return md;
  }
  function exportIstqb() {
    var md = buildIstqb();
    download(md, 'recorded.istqb.md');
    copy(md, btnExport);
  }
  // --- sélection multi-formats du menu export --------------------------------
  // Chaque ligne du menu porte une CASE À COCHER (cocher plusieurs formats,
  // puis « exporter la sélection » : téléchargements espacés pour que Chrome
  // affiche son invite multi-téléchargements au lieu de bloquer en silence) ;
  // cliquer le LIBELLÉ exporte toujours ce seul format immédiatement (le
  // comportement historique, sur lequel s'appuient les smokes). La sélection
  // survit à la navigation (sessionStorage, comme les steps).
  var EXPSEL_KEY = '__ui5RecorderExportSel';
  var EXPORT_FORMATS = [
    { key: 'robot', label: '.robot complet', run: exportScript, files: 1 },
    { key: 'resource', label: 'resource-first (.resource + .robot)', run: exportResourceFirst, files: 2 },
    { key: 'spec', label: 'plan specs/ (.spec.md)', run: exportSpec, files: 1 },
    { key: 'istqb', label: 'plan ISTQB (.istqb.md)', run: exportIstqb, files: 1 },
    { key: 'report', label: 'rapport HTML (.html)', run: exportReport, files: 1 }
  ];
  var exportSel = (function () {
    try { return JSON.parse(sessionStorage.getItem(EXPSEL_KEY)) || {}; }
    catch (e) { return {}; }
  })();
  function saveExportSel() {
    try { sessionStorage.setItem(EXPSEL_KEY, JSON.stringify(exportSel)); }
    catch (e) { warnStorage(e); }
  }
  function exportSelected() {
    var chosen = EXPORT_FORMATS.filter(function (f) { return exportSel[f.key]; });
    if (!chosen.length) {
      hint.textContent = 'Aucun format coch\u00e9 : cocher des cases du menu export, ' +
        'puis \u00ab exporter la s\u00e9lection \u00bb.';
      return;
    }
    var delay = 0;
    chosen.forEach(function (f) {
      if (delay) setTimeout(f.run, delay); else f.run();
      delay += 400 * f.files;
    });
    if (chosen.length > 1) {
      hint.textContent = 'Export de ' + chosen.length + ' formats : autoriser les ' +
        't\u00e9l\u00e9chargements multiples si le navigateur le demande.';
    }
  }
  function exportScript() {
    var body = buildScript();
    download(body, 'recorded.robot');   // télécharge un .robot complet
    copy(body, btnExport);              // + copie dans le presse-papiers
  }
  function exportResourceFirst() {
    var pair = buildResourceFirst();
    download(pair.resource, 'recorded_keywords.resource');
    // La protection « téléchargements multiples » de Chrome vise les downloads
    // d'une même tâche : espacer le second donne à l'utilisateur une invite
    // visible au lieu d'un .robot silencieusement manquant.
    setTimeout(function () { download(pair.robot, 'recorded.robot'); }, 350);
    copy(pair.robot, btnExport);
    hint.textContent = 'Export de 2 fichiers (.resource + .robot) : autoriser ' +
      'les t\u00e9l\u00e9chargements multiples si le navigateur le demande.';
  }
  function exportSpec() {
    var md = buildSpec();
    download(md, 'recorded.spec.md');
    copy(md, btnExport);
  }

  // --- export rapport HTML : la documentation humaine d'un enregistrement ----
  // Concept observé chez RoboSAPiens (saveHtmlReport, NOTICE) : page HTML
  // AUTO-CONTENUE (CSS minimal inline, aucune dépendance) documentant le
  // déroulé : phrase métier + ligne RF exacte par step, un chapitre par
  // scénario. Documentation, jamais un test : l'enregistrement brut fait foi.
  // Pas de capture d'écran depuis la page (une page ne se photographie pas
  // elle-même) : le log Robot et la démo vidéo couvrent ce besoin.
  function escapeHtml(t) {
    return String(t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function buildReport() {
    var css = 'body{font-family:system-ui,sans-serif;margin:2em auto;max-width:62em;' +
      'padding:0 1em;color:#1d2d3e}h1{font-size:1.5em;border-bottom:2px solid #0a6ed1;' +
      'padding-bottom:.3em}h2{font-size:1.15em;margin-top:1.4em}p.meta{color:#556b82;' +
      'font-size:.9em}ol.steps{padding-left:1.6em}ol.steps>li{margin:.9em 0}' +
      'p.human{margin:0 0 .15em}p.raw{margin:0}p.raw code{background:#f5f6f7;' +
      'border:1px solid #d9d9d9;border-radius:3px;padding:1px 5px;font-size:.85em;' +
      'color:#495a6e}';
    // Le rapport parle HTML, pas Markdown : les valeurs passent entre
    // guillemets français (la phrase entière est ensuite échappée HTML).
    var quote = function (t) { return '\u00ab\u202f' + String(t) + '\u202f\u00bb'; };
    var page = '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n' +
      '<title>' + escapeHtml(testName()) + '</title>\n<style>' + css + '</style>\n' +
      '</head>\n<body>\n<h1>' + escapeHtml(testName()) + '</h1>\n' +
      '<p class="meta">Rapport g\u00e9n\u00e9r\u00e9 par le recorder web : ' +
      escapeHtml(startUrl()) + '. Documentation du d\u00e9roul\u00e9 ' +
      'enregistr\u00e9 : l\u2019enregistrement brut fait foi, ce rapport ' +
      'n\u2019est pas un test.</p>\n';
    splitScenarios().forEach(function (group, gi) {
      page += '<h2>' + (gi + 1) + '. ' + escapeHtml(group.name) + '</h2>\n<ol class="steps">\n';
      group.steps.forEach(function (line) {
        var human = humanizeWebStep(line, quote);
        page += '<li>' +
          (human ? '<p class="human">' + escapeHtml(human) + '</p>' : '') +
          '<p class="raw"><code>' + escapeHtml(line) + '</code></p></li>\n';
      });
      page += '</ol>\n';
    });
    page += '</body>\n</html>\n';
    return page;
  }
  function exportReport() {
    var page = buildReport();
    download(page, 'recorded_report.html');
    copy(page, btnExport);
  }

  // --- replay in-page (« play ») : rejouer le déroulé dans la page ------------
  // Validation instantanée avant export, sans lancer robot : chaque step est
  // résolu par les MÊMES moteurs que la bibliothèque, surligné, exécuté ; le
  // premier échec arrête le replay et marque la ligne. Les steps UI5 essaient
  // leur repli xpath (l'indice posé à l'enregistrement) quand le sélecteur
  // primaire ne résout plus. Best-effort assumé : une navigation pleine page
  // recharge le recorder (les steps survivent via sessionStorage).
  var replaying = false;
  var replayState = { current: -1, failed: -1, message: '' };
  function parseUi5Sel(cells) {
    var sel = {}, m;
    cells.forEach(function (c) {
      if ((m = c.match(/^id=(.+)$/))) sel.id = m[1];
      else if ((m = c.match(/^idSuffix=(.+)$/))) sel.idSuffix = m[1];
      else if ((m = c.match(/^controlType=(.+)$/))) sel.controlType = m[1];
      else if ((m = c.match(/^properties=\{'([^']+)':\s*'([^']*)'\}$/))) {
        sel.properties = {}; sel.properties[m[1]] = m[2];
      }
    });
    return sel;
  }
  function parseWcSel(cells) {
    var sel = {}, m;
    cells.forEach(function (c) {
      if ((m = c.match(/^tag=(.+)$/))) sel.tag = m[1];
      else if ((m = c.match(/^text=(.+)$/))) sel.text = m[1];
    });
    return sel;
  }
  function parseDomSel(cells) {
    var sel = {}, m;
    cells.forEach(function (c) {
      if ((m = c.match(/^role=(.+)$/))) sel.role = m[1];
      else if ((m = c.match(/^name=(.+)$/))) sel.name = m[1];
      else if ((m = c.match(/^css=(.+)$/))) sel.css = m[1];
    });
    return sel;
  }
  function findUi5(cells, xpath) {
    try {
      var ids = window.__SAPFX.resolveByRole(JSON.stringify(parseUi5Sel(cells)));
      if (ids && ids.length) return document.getElementById(ids[0]);
    } catch (e) {}
    if (xpath) {
      try {
        var ids2 = window.__SAPFX.resolveByXPath(xpath);
        if (ids2 && ids2.length) return document.getElementById(ids2[0]);
      } catch (e) {}
    }
    return null;
  }
  function findBySid(sid) {
    var nodes = document.querySelectorAll('[lsdata]');
    for (var i = 0; i < nodes.length; i++) {
      var ls = nodes[i].getAttribute('lsdata') || '';
      if (ls.indexOf('"SID":"' + sid + '"') !== -1 ||
          ls.indexOf("SID:'" + sid + "'") !== -1) return nodes[i];
    }
    return null;
  }
  function findByPaths(paths) {
    if (!paths || !paths.length) return null;
    try { return document.querySelector(paths[0]); } catch (e) { return null; }
  }
  function findWc(cells) {
    try { return findByPaths(window.__SAPFX.resolveByWc(JSON.stringify(parseWcSel(cells)))); }
    catch (e) { return null; }
  }
  function findDom(cells) {
    try { return findByPaths(window.__SAPFX.resolveByDom(JSON.stringify(parseDomSel(cells)))); }
    catch (e) { return null; }
  }
  function fireClick(el) {
    ['mousedown', 'mouseup', 'click'].forEach(function (t) {
      el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true }));
    });
  }
  // Affectation via le setter NATIF du prototype : React trace la dernière
  // valeur posée par l'accesseur natif et déduplique les événements `input`
  // dont la valeur « n'a pas changé » : un simple t.value = x est exactement
  // ce qui est dédupliqué, donc les fills rejoués no-opaient sur les zones
  // React (la cible même du moteur dom).
  function setNativeValue(el, value) {
    var proto = null;
    try {
      if (window.HTMLInputElement && el instanceof HTMLInputElement) proto = HTMLInputElement.prototype;
      else if (window.HTMLTextAreaElement && el instanceof HTMLTextAreaElement) proto = HTMLTextAreaElement.prototype;
    } catch (e) {}
    if (proto) {
      try {
        var desc = Object.getOwnPropertyDescriptor(proto, 'value');
        if (desc && desc.set) { desc.set.call(el, value); return; }
      } catch (e) {}
    }
    el.value = value;
  }
  function fireFill(el, value) {
    var t = el;
    if (el.matches && !el.matches('input, textarea') && el.querySelector) {
      t = el.querySelector('input, textarea') || el;
    }
    try { if (t.focus) t.focus(); } catch (e) {}
    setNativeValue(t, value);
    t.dispatchEvent(new Event('input', { bubbles: true }));
    t.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function visibleEl(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return !!(r.width || r.height);
  }
  function elText(el) {
    return cleanCell(('value' in el && el.value) ? el.value : el.textContent);
  }
  function highlightEl(el) {
    try {
      var r = el.getBoundingClientRect();
      box.style.left = r.left + 'px'; box.style.top = r.top + 'px';
      box.style.width = r.width + 'px'; box.style.height = r.height + 'px';
      box.style.display = 'block';
      setTimeout(function () { box.style.display = 'none'; }, 300);
    } catch (e) {}
  }
  function waitUi5Idle(timeout, ok, ko) {
    var end = Date.now() + timeout;
    (function poll() {
      var busy = document.querySelectorAll(
        '.sapUiLocalBusyIndicator, .sapMBusyDialog, #sapUiBusyIndicator');
      var shown = false;
      for (var i = 0; i < busy.length; i++) {
        if (busy[i].offsetParent !== null) { shown = true; break; }
      }
      if (window.__SAPFX.isUI5() && !shown) return ok();
      if (Date.now() > end) return ko();
      setTimeout(poll, 200);
    })();
  }
  function executeStep(line, vars, done) {
    var parsed = splitStepCells(line);
    var cells = parsed.cells;
    function fail(msg) { done({ ok: false, message: msg }); }
    function okDone() { done({ ok: true }); }
    if (!cells.length || line.charAt(0) === '#') return done({ ok: true, skipped: true });
    var kw = cells[0], el;
    try {
      if (kw === 'Click Ui5 Control' || kw === 'Ui5 Control Should Be Visible') {
        el = findUi5(cells.slice(1), parsed.xpath);
        if (!el) return fail('contr\u00f4le UI5 introuvable');
        highlightEl(el);
        if (kw === 'Click Ui5 Control') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Ui5 Input' || kw === 'Ui5 Text Should Be') {
        el = findUi5(cells.slice(2), parsed.xpath);
        if (!el) return fail('contr\u00f4le UI5 introuvable');
        highlightEl(el);
        if (kw === 'Fill Ui5 Input') { fireFill(el, rfUnescape(cells[1])); return okDone(); }
        var wantText = rfUnescape(cells[1]);
        return (elText(el).indexOf(wantText) !== -1) ? okDone()
          : fail("texte '" + elText(el).slice(0, 40) + "' \u2260 '" + wantText + "'");
      }
      if (kw === 'Click Sid' || kw === 'Sid Should Be Visible') {
        el = findBySid(cells[1]);
        if (!el) return fail('SID introuvable');
        highlightEl(el);
        if (kw === 'Click Sid') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Sid Input') {
        el = findBySid(cells[1]);
        if (!el) return fail('SID introuvable');
        highlightEl(el); fireFill(el, rfUnescape(cells[2])); return okDone();
      }
      if (kw === 'Click Wc Control' || kw === 'Wc Control Should Be Visible') {
        el = findWc(cells.slice(1));
        if (!el) return fail('web component introuvable');
        highlightEl(el);
        if (kw === 'Click Wc Control') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Wc Input') {
        el = findWc(cells.slice(2));
        if (!el) return fail('web component introuvable');
        highlightEl(el); fireFill(el, rfUnescape(cells[1])); return okDone();
      }
      if (kw === 'Click Dom Element' || kw === 'Dom Element Should Be Visible') {
        el = findDom(cells.slice(1));
        if (!el) return fail('\u00e9l\u00e9ment dom introuvable');
        highlightEl(el);
        if (kw === 'Click Dom Element') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Dom Input') {
        el = findDom(cells.slice(2));
        if (!el) return fail('\u00e9l\u00e9ment dom introuvable');
        highlightEl(el); fireFill(el, rfUnescape(cells[1])); return okDone();
      }
      if (/^\$\{[^}]+\} =$/.test(kw)) {           // ${texte} =    Get Wc/Dom Text    ...
        var varName = kw.slice(2, kw.indexOf('}'));
        el = (cells[1] === 'Get Wc Text') ? findWc(cells.slice(2)) : findDom(cells.slice(2));
        if (!el) return fail('cible introuvable pour ' + cells[1]);
        vars[varName] = elText(el);
        return okDone();
      }
      if (kw === 'Should Be Equal') {
        var left = cells[1], m2 = left.match(/^\$\{([^}]+)\}$/);
        if (m2) left = vars[m2[1]];
        var want = rfUnescape(cells[2]);
        return (String(left) === want) ? okDone()
          : fail("'" + String(left).slice(0, 40) + "' \u2260 '" + want + "'");
      }
      if (kw === 'Keyboard Key') {
        var target = document.activeElement || document.body;
        ['keydown', 'keyup'].forEach(function (t) {
          target.dispatchEvent(new KeyboardEvent(t, { key: cells[2], bubbles: true }));
        });
        return okDone();
      }
      if (kw === 'Wait For Load State') { setTimeout(okDone, 300); return; }
      if (kw === 'Wait For UI5 Ready') {
        waitUi5Idle(5000, okDone, function () { fail('runtime UI5 pas inactif'); });
        return;
      }
    } catch (e) {
      return fail(String(e && e.message || e));
    }
    console.warn('[UI5 Recorder] replay : step non rejouable in-page, saut\u00e9 :', line);
    return done({ ok: true, skipped: true });
  }
  function playSteps() {
    if (replaying || !steps.length) return;
    replaying = true;
    replayState = { current: -1, failed: -1, message: '' };
    if (recording) setRecording(false);   // un replay ne se ré-enregistre jamais
    var vars = {};
    var i = 0;
    function finishOk() {
      replaying = false;
      replayState.current = -1;
      hint.textContent = 'Replay OK : ' + steps.length + ' step(s).';
      render();
    }
    function next() {
      if (!replaying) return;             // annulé (Échap) ou recorder arrêté
      if (i >= steps.length) return finishOk();
      replayState.current = i;
      render();
      executeStep(steps[i], vars, function (res) {
        if (!replaying) return;           // annulé pendant le step
        if (!res.ok) {
          replaying = false;
          replayState.failed = i;
          replayState.message = res.message || '';
          hint.textContent = '\u2716 step ' + (i + 1) + ' : ' + replayState.message;
          render();
          return;
        }
        i++;
        setTimeout(next, 350);
      });
    }
    next();
  }
  function cancelReplay() {
    if (!replaying) return;
    replaying = false;
    replayState.current = -1;
    hint.textContent = 'Replay annul\u00e9.';
    render();
  }

  // --- import d'un .robot exporté : le cycle d'édition se referme -------------
  function parseRobotSuite(text) {
    var name = null, out = [], skipped = 0, inTests = false, sawTest = false;
    String(text).split(/\r?\n/).forEach(function (raw) {
      var line = raw.replace(/\s+$/, '');
      var trimmed = line.trim();
      if (/^\*\*\*/.test(trimmed)) {
        inTests = /test cases/i.test(trimmed);
        return;
      }
      if (!inTests || !trimmed) return;
      if (line.charAt(0) !== ' ' && line.charAt(0) !== '\t') {
        if (trimmed.charAt(0) === '#') return;       // commentaire d'en-tête
        if (!sawTest) { name = trimmed; sawTest = true; }
        else out.push(testMarkerLine(trimmed));      // test suivant -> marqueur
        return;
      }
      if (/^(New Browser|New Page|\[)/.test(trimmed)) {
        // Round-trip : le New Page importé restaure l'URL de départ (le
        // bootstrap reste re-généré à l'export, donc toujours compté ignoré).
        var mNP = trimmed.match(/^New Page\s{2,}(\S+)/);
        if (mNP) { try { sessionStorage.setItem(URL_KEY, mNP[1]); } catch (e) { warnStorage(e); } }
        skipped++; return;
      }
      out.push(trimmed);
    });
    return { name: name, steps: out, skipped: skipped };
  }
  function applyImportedText(text) {
    var parsed = parseRobotSuite(text);
    steps = parsed.steps;
    if (parsed.name) {
      nameInput.value = parsed.name;
      try { sessionStorage.setItem(NAME_KEY, parsed.name); } catch (e) { warnStorage(e); }
    }
    saveSteps(); render();
    hint.textContent = parsed.steps.length + ' step(s) import\u00e9(s)' +
      (parsed.skipped ? ' : ' + parsed.skipped + ' ligne(s) de bootstrap ignor\u00e9e(s)' : '') + '.';
  }
  function importRobot() {
    var inp = document.createElement('input');
    inp.type = 'file'; inp.accept = '.robot,.txt'; inp.style.display = 'none';
    inp.addEventListener('change', function () {
      var f = inp.files && inp.files[0];
      if (!f) return;
      var reader = new FileReader();
      reader.onload = function () { applyImportedText(reader.result); };
      reader.readAsText(f);
    });
    panel.appendChild(inp);
    inp.click();
    setTimeout(function () { inp.remove(); }, 60000);
  }
  function moveStep(i, d) {
    var j = i + d;
    if (j < 0 || j >= steps.length) return;
    var t = steps[i]; steps[i] = steps[j]; steps[j] = t;
    saveSteps(); render();
  }
  function removeStep(i) { steps.splice(i, 1); saveSteps(); render(); }
  function stepBtn(label, fn) {
    var b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'margin-left:3px;border:1px solid #b3b3b3;background:#fff;cursor:pointer;' +
      'font:10px monospace;border-radius:3px;padding:0 4px;';
    b.addEventListener('click', fn);
    return b;
  }
  // Dans un launchpad (Work Zone/cFLP), le recorder tourne aussi dans l'iframe
  // de l'app : marquer le panneau pour distinguer shell et app embarquée.
  var frameTag = (window.top !== window.self) ? ' [iframe]' : '';
  // Édition in-place d'un step (double-clic) : Entrée valide, Échap annule.
  function startEditStep(i, row, txt) {
    if (replaying) return;
    var input = document.createElement('input');
    input.type = 'text';
    input.value = steps[i];
    input.style.cssText = 'flex:1;font:11px monospace;border:1px solid #0a6ed1;' +
      'border-radius:3px;padding:1px 4px;';
    row.replaceChild(input, txt);
    input.focus();
    input.select();
    var done = false;
    function commit() {
      if (done) return;
      done = true;
      var v = input.value.trim();
      if (v) steps[i] = v;
      saveSteps(); render();
    }
    input.addEventListener('keydown', function (e) {
      e.stopPropagation();
      if (e.key === 'Enter') commit();
      else if (e.key === 'Escape') { done = true; render(); }
    });
    input.addEventListener('blur', commit);
  }
  function renderSteps() {
    title.textContent = (recording ? 'Recording' : 'Steps') + ' : ' + steps.length + ' step(s)' + frameTag;
    list.textContent = '';
    steps.forEach(function (line, i) {
      var row = document.createElement('div');
      var bg = '';
      if (i === replayState.failed) bg = 'background:#fde8e8;';
      else if (i === replayState.current && replaying) bg = 'background:#eaf3fb;';
      else if (TEST_MARKER.test(line)) bg = 'background:#f4f0fa;';
      row.style.cssText = 'display:flex;align-items:center;gap:4px;padding:3px 4px;' +
        'border-bottom:1px solid #f0f0f0;' + bg;
      var txt = document.createElement('span');
      txt.style.cssText = 'flex:1;font:11px monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
      txt.textContent = (i + 1) + '. ' + line;
      txt.title = 'double-clic : \u00e9diter';
      txt.addEventListener('dblclick', function () { startEditStep(i, row, txt); });
      row.appendChild(txt);
      row.appendChild(stepBtn('\u2191', function () { moveStep(i, -1); }));
      row.appendChild(stepBtn('\u2193', function () { moveStep(i, 1); }));
      row.appendChild(stepBtn('\u2715', function () { removeStep(i); }));
      list.appendChild(row);
    });
  }
  function render() {
    if (recording || steps.length) { renderSteps(); return; }   // steps restaurés -> visibles
    title.textContent = 'UI5 Recorder : ' + captures.length + ' captured' + frameTag;
    list.textContent = '';
    captures.forEach(function (rec, i) {
      var row = document.createElement('div');
      row.style.cssText = 'padding:5px 4px;border-bottom:1px solid #f0f0f0;';
      var lab = document.createElement('div');
      lab.style.cssText = 'color:#0a6ed1;font:11px monospace;margin-bottom:3px;' +
        'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
      lab.textContent = (i + 1) + '. ' + rec.label;
      row.appendChild(lab);
      var bar = document.createElement('div');
      if (rec.cap) {
        bar.appendChild(mkBtn('role', roleLine(rec.cap)));
        if (xpathLine(rec.cap)) bar.appendChild(mkBtn('xpath', xpathLine(rec.cap)));
      }
      if (rec.sid) bar.appendChild(mkBtn('sid', 'Resolve Sid    ' + rec.sid));
      if (rec.wc) bar.appendChild(mkBtn('wc', 'Resolve Wc Control    ' + wcArgs(rec.wc)));
      if (rec.dom) bar.appendChild(mkBtn('dom', 'Resolve Dom Element    ' + domArgs(rec.dom)));
      bar.appendChild(mkBtn('all', allLines(rec)));
      row.appendChild(bar);
      list.appendChild(row);
    });
  }
  render();

  function inOurUI(node) {
    return !!(node && node.closest && node.closest('#__ui5SpyPanel'));
  }

  // --- menu flottant (assertions au clic droit, choix du format d'export) ----
  var menuEl = null;
  function closeMenus() { if (menuEl) { menuEl.remove(); menuEl = null; } }
  function showMenu(items, x, y) {
    closeMenus();
    menuEl = document.createElement('div');
    menuEl.style.cssText = 'position:fixed;z-index:2147483647;background:#fff;' +
      'border:1px solid #b3b3b3;border-radius:5px;box-shadow:0 4px 14px rgba(0,0,0,.25);' +
      'font:12px monospace;min-width:180px;overflow:hidden;';
    menuEl.style.left = Math.max(0, Math.min(x, window.innerWidth - 210)) + 'px';
    menuEl.style.top = Math.max(0, Math.min(y, window.innerHeight - items.length * 26 - 10)) + 'px';
    items.forEach(function (it) {
      var b = document.createElement('div');
      b.style.cssText = 'display:flex;align-items:center;cursor:pointer;color:#0a6ed1;';
      if (it.checkbox) {
        // zone case à cocher : toggle SANS fermer le menu (cocher plusieurs
        // formats d'affilée) ; le libellé reste l'action immédiate.
        var box = document.createElement('span');
        box.style.cssText = 'padding:5px 2px 5px 10px;';
        var paintBox = function () {
          box.textContent = it.checkbox.checked() ? '\u2611' : '\u2610';
        };
        paintBox();
        box.addEventListener('click', function (e) {
          e.preventDefault(); e.stopPropagation(); it.checkbox.toggle(); paintBox();
        });
        b.appendChild(box);
      }
      var lab = document.createElement('span');
      lab.textContent = it.label;
      lab.style.cssText = 'padding:5px 10px 5px ' + (it.checkbox ? '4px' : '10px') +
        ';flex:1;';
      b.appendChild(lab);
      b.addEventListener('mouseenter', function () { b.style.background = '#eaf3fb'; });
      b.addEventListener('mouseleave', function () { b.style.background = ''; });
      b.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation(); closeMenus(); it.run();
      });
      menuEl.appendChild(b);
    });
    document.documentElement.appendChild(menuEl);
  }
  // Choix d'assertions selon le moteur qui possède l'élément visé.
  function assertionItems(cap, sid, wc, dom, target) {
    var items = [];
    if (cap) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Ui5 Control Should Be Visible    ' + roleArgs(cap.role)); } });
      if (cap.text) items.push({ label: 'v\u00e9rifier : texte', run: function () {
        addStep('Ui5 Text Should Be    ' + rfEscape(cap.text, true) + '    ' + roleArgs(cap.role)); } });
    } else if (sid) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Sid Should Be Visible    ' + sid); } });
    } else if (wc) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Wc Control Should Be Visible    ' + wcArgs(wc)); } });
      if (wc.text) items.push({ label: 'v\u00e9rifier : texte', run: function () {
        addStep('${texte} =    Get Wc Text    ' + wcArgs(wc));
        addStep('Should Be Equal    ${texte}    ' + rfEscape(wc.text, true)); } });
    } else if (dom) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Dom Element Should Be Visible    ' + domArgs(dom)); } });
      var txt = cleanCell(target && target.textContent).slice(0, 40);
      if (txt) items.push({ label: 'v\u00e9rifier : texte', run: function () {
        addStep('${texte} =    Get Dom Text    ' + domArgs(dom));
        addStep('Should Be Equal    ${texte}    ' + rfEscape(txt, true)); } });
    }
    return items;
  }
  function onContextMenu(event) {
    if (replaying || !recording || inOurUI(event.target)) return;
    var cap = window.__SAPFX.isUI5() ? window.__SAPFX.capture(event.target) : null;
    var sidObj = cap ? null : window.__SAPFX.captureSid(event.target);
    var sid = sidObj && sidObj.sid;
    var wc = (!cap && !sid) ? window.__SAPFX.captureWc(event.target) : null;
    var dom = (!cap && !sid && !wc) ? window.__SAPFX.captureDom(event.target) : null;
    var items = assertionItems(cap, sid, wc, dom, event.target);
    if (!items.length) return;             // rien d'assertable : menu natif conservé
    event.preventDefault(); event.stopPropagation();
    showMenu(items, event.clientX, event.clientY);
  }

  // --- mise en surbrillance au survol ----------------------------------------
  var raf = 0, lastEvt = null;
  function paint() {
    raf = 0;
    var t = lastEvt ? lastEvt.target : null;
    var info = (t && !inOurUI(t)) ? window.__SAPFX.highlightInfo(t) : null;
    if (!info) { box.style.display = 'none'; chip.style.display = 'none'; return; }
    var r = info.rect;
    box.style.left = r.left + 'px'; box.style.top = r.top + 'px';
    box.style.width = r.width + 'px'; box.style.height = r.height + 'px';
    box.style.display = 'block';
    chip.textContent = info.label;
    var top = r.top - 20; if (top < 0) top = r.top + r.height + 2;
    chip.style.left = r.left + 'px'; chip.style.top = top + 'px';
    chip.style.display = 'block';
  }
  function onMove(event) { lastEvt = event; if (!raf) raf = requestAnimationFrame(paint); }

  function onClick(event) {
    if (replaying) return;               // les clics synthétiques du replay ne se ré-enregistrent pas
    if (menuEl) {                        // menu flottant ouvert : clic-ailleurs = fermeture
      if (!menuEl.contains(event.target)) { closeMenus(); event.preventDefault(); event.stopPropagation(); }
      return;
    }
    if (inOurUI(event.target)) return;   // let panel buttons handle their own clicks
    var cap = window.__SAPFX.isUI5() ? window.__SAPFX.capture(event.target) : null;
    var sidObj = window.__SAPFX.captureSid(event.target);
    var sid = sidObj && sidObj.sid;
    // Page hors registre UI5 (pur Web Components) : repli sur l'hôte ui5-*.
    var wc = (!cap && !sid) ? window.__SAPFX.captureWc(event.target) : null;
    // Zone non-SAP (React/Angular/vanilla) : repli sur le moteur dom générique.
    var dom = (!cap && !sid && !wc) ? window.__SAPFX.captureDom(event.target) : null;
    if (!cap && !sid && !wc && !dom) { console.warn('[UI5 Recorder] no UI5 control, WebGUI SID, ui5-* web component or interactive DOM element there.'); return; }
    if (recording) {                     // mode record : append une action ordonnée
      // En record, le clic n'est JAMAIS bloqué : l'application doit continuer à
      // réagir pour dérouler un vrai parcours (l'ancien preventDefault global
      // gelait l'app pendant l'enregistrement). Seuls les gestes MÉTA
      // (Alt+clic = assertion) sont avalés : ils ne font pas partie du flux.
      if (event.altKey && cap) {
        event.preventDefault(); event.stopPropagation();
        if (event.shiftKey && cap.text) {   // Shift+Alt+clic = assertion de VALEUR
          addStep('Ui5 Text Should Be    ' + rfEscape(cap.text, true) + '    ' + roleArgs(cap.role));
        } else {                            // Alt+clic = assertion de visibilité
          addStep('Ui5 Control Should Be Visible    ' + roleArgs(cap.role));
        }
      } else if (event.altKey && wc) {      // Alt+clic sur un WC = assertion de visibilité
        event.preventDefault(); event.stopPropagation();
        addStep('Wc Control Should Be Visible    ' + wcArgs(wc));
      } else if (event.altKey && dom) {     // Alt+clic zone non-SAP = assertion de visibilité
        event.preventDefault(); event.stopPropagation();
        addStep('Dom Element Should Be Visible    ' + domArgs(dom));
      } else {
        addStep(cap ? withXpathHint(clickLine(cap), cap)
                    : (sid ? ('Click Sid    ' + sid)
                           : (wc ? ('Click Wc Control    ' + wcArgs(wc))
                                 : ('Click Dom Element    ' + domArgs(dom)))));
      }
      return;
    }
    event.preventDefault(); event.stopPropagation();   // mode capture : inspection seule
    var info = window.__SAPFX.highlightInfo(event.target);
    var rec = { cap: cap, sid: sid, wc: wc, dom: dom,
                label: (info && info.label) || (sid ? 'SID ' + sid : 'control') };
    captures.push(rec);
    render();
    copy(allLines(rec));                 // also copy latest to clipboard
    flashGreen();
  }
  // mode record : une saisie validée (change) devient un Fill Ui5 Input ordonné.
  // Les champs SENSIBLES ne sont jamais capturés en clair (ils finiraient dans
  // recorded.robot / sessionStorage / le presse-papier) : on insère un
  // placeholder. type=password est le cas évident ('Password' est la graphie
  // UI5 WC) ; les tokens autocomplete couvrent paiement + OTP + gestionnaires
  // de mots de passe ; les motifs name/id/aria-label rattrapent les formulaires
  // sans autocomplete. Motifs volontairement étroits : un faux positif masque
  // en silence une valeur que l'utilisateur voulait enregistrer.
  var SENSITIVE_AUTOCOMPLETE = /^(cc-number|cc-csc|cc-exp(-month|-year)?|one-time-code|current-password|new-password)$/;
  var SENSITIVE_HINT = /passw|pwd|cvv|cvc|card.?number|cardnum|(^|[^a-z])(csc|otp)([^a-z]|$)|one.?time.?code|security.?code/;
  function isPasswordField(t) {
    return t.type === 'password' || (t.getAttribute && t.getAttribute('type') === 'Password');
  }
  function attrLower(t, name) {
    try {
      if (t && typeof t.getAttribute === 'function') return String(t.getAttribute(name) || '').toLowerCase();
    } catch (e) {}
    return '';
  }
  // Placeholder à enregistrer à la place de la vraie valeur : '<REDACTED>'
  // pour un password, '<SECRET>' pour paiement/OTP, null si la valeur est
  // sûre à enregistrer.
  function sensitiveMask(t) {
    if (isPasswordField(t)) return '<REDACTED>';
    // autocomplete est une liste de tokens séparés par des blancs ('billing cc-number')
    var tokens = attrLower(t, 'autocomplete').split(/\s+/);
    for (var i = 0; i < tokens.length; i++) {
      if (SENSITIVE_AUTOCOMPLETE.test(tokens[i])) return '<SECRET>';
    }
    var hintText = attrLower(t, 'name') + ' ' + attrLower(t, 'id') + ' ' + attrLower(t, 'aria-label');
    return SENSITIVE_HINT.test(hintText) ? '<SECRET>' : null;
  }
  function onChange(event) {
    if (replaying || !recording || inOurUI(event.target)) return;
    var t = event.target;
    if (!t || !('value' in t)) return;
    // Un <input type=file> n'a pas de valeur rejouable (C:\fakepath\...) et
    // l'affecter au replay lève une exception : rien d'utile à enregistrer.
    if (String(t.type || '').toLowerCase() === 'file') return;
    var cap = window.__SAPFX.isUI5() ? window.__SAPFX.capture(t) : null;
    var sidObj = cap ? null : window.__SAPFX.captureSid(t);
    var sid = sidObj && sidObj.sid;
    // NB : le `change` natif d'un <input> INTERNE à un shadow root n'est pas
    // composed : il n'atteint ce listener document que si le composant le
    // re-émet (les UI5 WC réels re-émettent ui5-change/change sur l'hôte).
    var wc = (!cap && !sid) ? window.__SAPFX.captureWc(t) : null;
    var dom = (!cap && !sid && !wc) ? window.__SAPFX.captureDom(t) : null;
    if (!cap && !sid && !wc && !dom) return;
    // Une valeur enregistrée est TOUJOURS échappée façon RF (variables ${...},
    // runs d'espaces, '#', 'mot='...) : le replay in-page la déséchappe.
    var mask = sensitiveMask(t);
    var value = mask || rfEscape(t.value, true);
    if (cap) {
      // Valeur masquée pour les champs sensibles, mais id ET xpath conservés :
      // le locator du champ reste exploitable pour rejouer le test (avec une
      // vraie valeur injectée à la main). Même logique de masquage côté WebGUI (sid).
      addStep(withXpathHint(fillLine(cap, value), cap));
      if (mask) {
        var x = xpathLine(cap);
        if (x) addStep(x);
      }
    } else if (sid) {
      addStep('Fill Sid Input    ' + sid + '    ' + value);
    } else if (wc) {
      addStep('Fill Wc Input    ' + value + '    ' + wcArgs(wc));
    } else {
      addStep('Fill Dom Input    ' + value + '    ' + domArgs(dom));
    }
  }
  var pendingEnter = null;
  function onKey(event) {
    if (replaying) {
      if (event.key === 'Escape') cancelReplay();   // Échap annule un replay en cours
      return;
    }
    if (event.key === 'Escape') {
      if (menuEl) { closeMenus(); return; }   // Échap ferme d'abord le menu flottant
      if (inOurUI(event.target)) return;      // édition in-place : Échap géré par l'input
      window.__ui5SpyStop();
      return;
    }
    // Entrée pendant le record : la touche de VALIDATION fait partie du déroulé
    // (soumission de formulaire, recherche). Différé d'un tick : le `change` du
    // champ, émis pendant l'action par défaut d'Entrée, doit précéder le
    // Keyboard Key dans l'ordre des steps. Textarea exclu (Entrée = nouvelle ligne).
    // Parqué dans pendingEnter : si Entrée déclenche une navigation pleine page,
    // onBeforeUnload le flush avant que le tick ne meure avec la page.
    if (recording && event.key === 'Enter' && !inOurUI(event.target)) {
      var tag = (event.target && event.target.tagName || '').toLowerCase();
      if (tag !== 'textarea') {
        pendingEnter = 'Keyboard Key    press    Enter';
        setTimeout(function () {
          if (pendingEnter) { var p = pendingEnter; pendingEnter = null; addStep(p); }
        }, 0);
      }
    }
  }
  // navigation Fiori (routing par hash / history) -> insère une attente rejouable :
  // Wait For UI5 Ready (moteur inactif, pas seulement chargé) quand le runtime UI5
  // est là, le keyword est embarqué dans l'export, sinon Wait For Load State.
  function onNav() {
    if (!recording) return;
    addStep(window.__SAPFX.isUI5() ? 'Wait For UI5 Ready' : 'Wait For Load State    load');
  }
  // Navigation PLEINE PAGE (soumission, lien hors routing) : flusher l'Entrée
  // différée puis marquer l'attente : les steps sont déjà persistés au fil de
  // l'eau, mais sans ce hook la touche qui a soumis disparaissait avec la page.
  function onBeforeUnload() {
    if (!recording || replaying) return;
    if (pendingEnter) { addStep(pendingEnter); pendingEnter = null; }
    addStep(window.__SAPFX.isUI5() ? 'Wait For UI5 Ready' : 'Wait For Load State    load');
  }

  function setRecording(on) {
    recording = !!on;
    saveRecording();
    if (on) rememberUrl();
    btnRec.textContent = on ? 'pause' : 'rec';
    btnRec.style.background = on ? '#d0021b' : 'transparent';
    dot.style.display = on ? 'inline-block' : 'none';
    dot.style.animation = on ? '__ui5RecBlink 1s infinite' : 'none';
    hint.textContent = on
      ? 'Recording: click/typed value = step. Right-click = assertion menu. +test = next scenario. export = .robot / resource / spec / istqb / report / import.'
      : 'Hover + click to capture. rec to record, play to replay in-page. Right-click / Alt+click = assert. Esc to stop.';
    updateFrameWarn();
    render();
    // notifie le pont d'extension (badge), voir extension/bridge.js
    try { document.dispatchEvent(new CustomEvent('__ui5RecorderState', { detail: on })); } catch (e) {}
  }
  btnRec.addEventListener('click', function () { setRecording(!recording); });
  btnPlay.addEventListener('click', function (e) { e.stopPropagation(); playSteps(); });
  btnNewTest.addEventListener('click', function (e) {
    e.stopPropagation();
    var suggested = 'Scenario ' + (splitScenarios().length + 1);
    var name = null;
    try { name = window.prompt('Nom du sc\u00e9nario suivant :', suggested); } catch (err) {}
    if (name) addStep(testMarkerLine(name));
  });
  btnExport.addEventListener('click', function (e) {
    e.stopPropagation();
    var r = btnExport.getBoundingClientRect();
    var items = EXPORT_FORMATS.map(function (f) {
      return { label: f.label, run: f.run, checkbox: {
        checked: function () { return !!exportSel[f.key]; },
        toggle: function () { exportSel[f.key] = !exportSel[f.key]; saveExportSel(); }
      } };
    });
    items.push({ label: 'exporter la s\u00e9lection', run: exportSelected });
    items.push({ label: 'importer un .robot\u2026', run: importRobot });
    showMenu(items, r.left, r.bottom + 4);
  });
  btnClear.addEventListener('click', function () {
    captures = []; steps = [];
    saveSteps();
    try { sessionStorage.removeItem(URL_KEY); } catch (e) {}
    render();
  });
  btnClose.addEventListener('click', function () { window.__ui5SpyStop(); });

  document.addEventListener('mousemove', onMove, true);
  document.addEventListener('click', onClick, true);
  document.addEventListener('change', onChange, true);
  document.addEventListener('keydown', onKey, true);
  document.addEventListener('contextmenu', onContextMenu, true);
  window.addEventListener('hashchange', onNav, true);
  window.addEventListener('popstate', onNav, true);
  window.addEventListener('beforeunload', onBeforeUnload, true);
  updateFrameWarn();
  if (loadRecording()) setRecording(true);   // l'enregistrement survit à la navigation + ré-injection
  console.info('[UI5 Recorder] Ready. Hover to highlight, click to capture, rec to record. ' +
               'Right-click opens the assertion menu while recording (Alt+click still works). ' +
               'Esc or window.__ui5SpyStop() to stop.');

  // API pilotable depuis le popup de l'extension / le raccourci clavier (monde MAIN).
  window.__ui5RecorderApi = {
    toggleRec: function () { setRecording(!recording); },
    // setRec(on) : état EXPLICITE : le raccourci/popup calcule UNE cible pour
    // toutes les frames au lieu de toggles par frame qui dérivent en anti-phase.
    setRec: function (on) { setRecording(!!on); },
    exportScript: exportScript,
    isRecording: function () { return recording; },
    play: playSteps,
    isReplaying: function () { return replaying; },
    addTestMarker: function (name) { addStep(testMarkerLine(name)); },
    importRobotText: applyImportedText,
    stop: function () { window.__ui5SpyStop(); }
  };

  window.__ui5SpyStop = function () {
    replaying = false;                       // coupe une chaîne de replay en cours
    recording = false;
    saveRecording();                         // un stop explicite ne reprend pas tout seul
    document.removeEventListener('mousemove', onMove, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('change', onChange, true);
    document.removeEventListener('keydown', onKey, true);
    document.removeEventListener('contextmenu', onContextMenu, true);
    document.removeEventListener('mousemove', onDragMove, true);
    document.removeEventListener('mouseup', onDragUp, true);
    window.removeEventListener('hashchange', onNav, true);
    window.removeEventListener('popstate', onNav, true);
    window.removeEventListener('beforeunload', onBeforeUnload, true);
    closeMenus();
    box.remove(); chip.remove(); panel.remove(); styleEl.remove();
    window.__ui5SpyStop = undefined;
    window.__ui5RecorderApi = undefined;
    try { document.dispatchEvent(new CustomEvent('__ui5RecorderState', { detail: false })); } catch (e) {}
    console.info('[UI5 Recorder] stopped.');
  };
})();
