
(() => {
  if (window.__SAPFX) return;
  const ALLOWED = %s;
  const ALLOW_WITHOUT = %s;

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
