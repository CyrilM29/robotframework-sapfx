  // --- popups OUVERTS ------------------------------------------------------
  // Le pendant Fiori de `Get Open Windows` (ECC). Il existe parce qu'un
  // dialogue FERMÉ reste RENDU : mesuré live sur un launchpad ABAP, le
  // dialogue « À propos » garde son nœud DOM après acquittement, donc ni un
  // comptage de correspondances ni une résolution ne distinguent ouvert de
  // fermé. `sap.m.InstanceManager` est la seule source qui le sache.
  function instanceManager() {
    try {
      const m = sap.ui.require && sap.ui.require('sap/m/InstanceManager');
      if (m) return m;
    } catch (e) {}
    return (window.sap && sap.m && sap.m.InstanceManager) || null;
  }

  // Boutons RENDUS d'un popup, dans l'ordre de l'agrégation. Les MessageBox
  // n'alimentent pas `buttons` mais `beginButton`/`endButton` : les deux
  // formes donnent la même liste ordonnée.
  function popupButtons(c) {
    const out = [];
    try {
      const list = (typeof c.getButtons === 'function' && c.getButtons()) || [];
      list.forEach((b) => { if (b && b.getDomRef && b.getDomRef()) out.push(b); });
    } catch (e) {}
    if (!out.length) {
      ['getBeginButton', 'getEndButton'].forEach((name) => {
        try {
          const b = typeof c[name] === 'function' ? c[name]() : null;
          if (b && b.getDomRef && b.getDomRef()) out.push(b);
        } catch (e) {}
      });
    }
    return out;
  }

  function popupEntry(c, kind) {
    let state = '';
    let type = '';
    try { if (typeof c.getState === 'function') state = String(c.getState() || ''); } catch (e) {}
    try { type = c.getMetadata().getName(); } catch (e) {}
    return { id: String(c.getId()), controlType: type, kind: kind,
             state: state, buttons: popupButtons(c).length };
  }

  function openPopups() {
    if (!isUI5()) return null;
    const IM = instanceManager();
    if (!IM) return [];
    const out = [];
    try { (IM.getOpenDialogs() || []).forEach((d) => out.push(popupEntry(d, 'dialog'))); } catch (e) {}
    try { (IM.getOpenPopovers() || []).forEach((p) => out.push(popupEntry(p, 'popover'))); } catch (e) {}
    return out;
  }

  // Id DOM du bouton d'INDEX donné (base 0) du dialogue ouvert le plus récent.
  // Les boutons d'une MessageBox portent un id GÉNÉRÉ (`__mbox-btn-0`) et un
  // texte TRADUIT : la position est la seule adresse locale-indépendante
  // (convention 3). Retourne { error } plutôt que de lever, pour que
  // l'appelant Python compose un message actionnable.
  function dialogButton(payload) {
    if (!isUI5()) return null;
    let req;
    try { req = JSON.parse(payload) || {}; } catch (e) { req = {}; }
    const IM = instanceManager();
    if (!IM) return { error: 'no_instance_manager' };
    let dialogs = [];
    try { dialogs = IM.getOpenDialogs() || []; } catch (e) { dialogs = []; }
    if (!dialogs.length) return { error: 'no_dialog' };
    const d = dialogs[dialogs.length - 1];
    const buttons = popupButtons(d);
    const idx = parseInt(req.position, 10);
    const pos = isNaN(idx) ? 0 : idx;
    if (pos < 0 || pos >= buttons.length) {
      return { error: 'out_of_range', count: buttons.length, dialog: String(d.getId()) };
    }
    const dom = buttons[pos].getDomRef();
    if (!dom || !dom.id) return { error: 'not_rendered', count: buttons.length, dialog: String(d.getId()) };
    return { id: dom.id, count: buttons.length, dialog: String(d.getId()) };
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

