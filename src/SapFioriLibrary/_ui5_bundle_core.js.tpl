
(() => {
  // Version du bundle : empreinte courte de son propre contenu, calculée côté
  // Python à la construction. La garde n'est PAS « déjà présent » mais « présent
  // ET de la même version » : l'idempotence reste entière (le cas courant, à
  // chaque appel de keyword, sort ici sans rien réinstaller), et une version
  // NEUVE remplace l'ancienne au lieu d'être ignorée en silence.
  // Sans cela, une page ayant reçu un bundle le garde pour sa vie entière : après
  // un hot-swap de la bibliothèque dans un serveur rf-mcp, les nouveaux keywords
  // sont visibles côté Robot et l'appel sort en « window.__SAPFX.<x> is not a
  // function », message qui accuse le keyword là où le fautif est ce cache.
  const V = '__SAPFX_BUNDLE_VERSION__';
  if (window.__SAPFX && window.__SAPFX.__v === V) return;
  const ALLOWED = %s;
  const ALLOW_WITHOUT = %s;

  // État MUTABLE partagé, porté par la fenêtre et non par la clôture du bundle :
  // c'est lui qui rend une réinstallation inoffensive. Les hooks posés au premier
  // passage (fetch/XHR, MessageToast) continuent d'écrire ICI, donc une nouvelle
  // version du bundle ne perd ni les requêtes en vol ni les toasts déjà captés,
  // et n'a pas besoin de reposer des hooks qui feraient double emploi.
  const STATE = window.__SAPFX_STATE ||
    (window.__SAPFX_STATE = { net: { pending: 0, last: Date.now() }, toasts: [] });

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
  // XHR et fetch instrumentés au PREMIER passage du bundle : on ne compte que
  // les requêtes lancées après l'injection, exactement le besoin du keyword
  // (agir, puis attendre que la page ait fini de parler au serveur).
  // Indépendant du runtime UI5 : les pages WC/hybrides en profitent aussi.
  // Chaque enveloppe est MARQUÉE et l'état qu'elle nourrit vit sur la fenêtre :
  // une réinstallation (version neuve du bundle) ne repose donc rien et ne perd
  // rien. Réinstaller sans la marque empilerait une enveloppe par passage, et
  // chaque requête serait comptée autant de fois.
  const NET = STATE.net;
  function netDone() { NET.pending = NET.pending > 0 ? NET.pending - 1 : 0; NET.last = Date.now(); }
  try {
    const xhrSend = XMLHttpRequest.prototype.send;
    if (!xhrSend.__sapfxHook) {
      const xhrHook = function () {
        const net = window.__SAPFX_STATE.net;
        net.pending += 1; net.last = Date.now();
        try { this.addEventListener('loadend', netDone); } catch (e) { netDone(); }
        return xhrSend.apply(this, arguments);
      };
      xhrHook.__sapfxHook = true;
      XMLHttpRequest.prototype.send = xhrHook;
    }
  } catch (e) {}
  try {
    if (window.fetch && !window.fetch.__sapfxHook) {
      const realFetch = window.fetch;
      const fetchHook = function () {
        const net = window.__SAPFX_STATE.net;
        net.pending += 1; net.last = Date.now();
        const p = realFetch.apply(this, arguments);
        try { p.then(netDone, netDone); } catch (e) { netDone(); }
        return p;
      };
      fetchHook.__sapfxHook = true;
      window.fetch = fetchHook;
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
  // Même règle que pour le réseau : la liste vit sur la fenêtre, le hook porte sa
  // marque, donc une réinstallation ne double pas la capture et ne jette pas ce
  // qui a déjà été capté.
  const TOASTS = STATE.toasts;
  try {
    if (window.sap && sap.ui && sap.ui.require) {
      sap.ui.require(['sap/m/MessageToast'], function (MT) {
        try {
          // La marque est le RÉCEPTACLE lui-même, pas un booléen : un booléen
          // dirait « déjà accroché » alors qu'un hook laissé par une version
          // antérieure du bundle remplirait une liste orpheline, et les toasts
          // seraient perdus en silence après remplacement du bundle.
          if (!MT || MT.__sapfxToastSink === TOASTS) return;
          const realShow = MT.show;
          MT.show = function (message) {
            try {
              TOASTS.push({ text: String(message), time: Date.now() });
              if (TOASTS.length > 20) TOASTS.shift();
            } catch (e) {}
            return realShow.apply(this, arguments);
          };
          MT.__sapfxToastSink = TOASTS;
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
  // `viewId` désigne la VUE propriétaire du contrôle. La forme historique
  // comparait ce paramètre à l'id du CONTRÔLE (correspondance de sous-chaîne),
  // ce qui marche pour un contrôle de fabrique (dont l'id contient celui de sa
  // liste) mais pas pour un contrôle à id entièrement GÉNÉRÉ : mesuré live,
  // `controlType=Button viewId=<vue>` rendait 0 sur une vue qui portait pourtant
  // trois boutons. On remonte donc la hiérarchie jusqu'à la vue propriétaire, en
  // gardant la correspondance de sous-chaîne en second : elle reste vraie pour
  // tous les usages existants, ce keyword ne perd donc rien et gagne le cas que
  // son nom promettait.
  function ownerViewId(control) {
    let node = control;
    while (node) {
      try { if (node.isA && node.isA('sap.ui.core.mvc.View')) return node.getId(); }
      catch (e) {}
      node = node.getParent ? node.getParent() : null;
    }
    return null;
  }
  function viewIdMatches(control, wanted) {
    const want = String(wanted);
    if (String(control.getId()).indexOf(want) !== -1) return true;
    const view = ownerViewId(control);
    if (!view) return false;
    return view === want || String(view).slice(-want.length) === want;
  }

  // CONTAINMENT DOM : le nœud du contrôle désigné, cherché par id exact puis par
  // suffixe d'id, et seulement parmi les contrôles RENDUS (un contrôle sans nœud
  // ne contient rien). Relation distincte de `viewId`, qui suit la propriété/
  // l'agrégation : une tuile de launchpad rendue par un composant séparé porte
  // dans son nœud DOM des contrôles qui ne sont ni dans sa vue ni dans ses
  // agrégations, et c'est précisément le cas que celle-ci attrape.
  function containerDom(wanted) {
    const want = String(wanted);
    let exact = null;
    let suffix = null;
    registryForEach((c) => {
      try {
        if (exact) return;
        const id = String(c.getId());
        if (id !== want && id.slice(-want.length) !== want) return;
        const d = c.getDomRef();
        if (!d) return;
        if (id === want) exact = d; else if (!suffix) suffix = d;
      } catch (e) {}
    });
    if (exact || suffix) return exact || suffix;
    // Repli sur le nœud DOM de même id : ce que retourne `Get Ui5 Ids` est l'id
    // du NŒUD rendu, qui vaut celui du contrôle dans le cas ordinaire mais pas
    // toujours (un contrôle peut se rendre sous un autre id). Refuser cet
    // identifiant-là serait refuser la valeur que la bibliothèque vient de
    // servir à l'appelant.
    try { return document.getElementById(want) || null; } catch (e) { return null; }
  }

  function resolveByRole(selJson) {
    if (!isUI5()) return null;
    const sel = JSON.parse(selJson);
    const shortWant = sel.controlType ? shortType(sel.controlType) : null;
    // Conteneur résolu UNE fois pour toute la passe : le chercher par contrôle
    // coûterait un parcours de registre par candidat. Conteneur absent ou non
    // rendu = aucune correspondance, jamais un périmètre élargi en silence.
    let scope = null;
    if (sel.containedIn) {
      scope = containerDom(sel.containedIn);
      if (!scope) return [];
    }
    const ids = [];
    registryForEach((c) => {
      try {
        if (sel.id && c.getId() !== sel.id) return;
        if (sel.idSuffix && String(c.getId()).slice(-String(sel.idSuffix).length) !== String(sel.idSuffix)) return;
        if (sel.controlType) {
          const full = c.getMetadata().getName();
          if (full !== sel.controlType && shortType(full) !== shortWant) return;
        }
        if (sel.viewId && !viewIdMatches(c, sel.viewId)) return;
        if (sel.properties && !matchProps(c, sel.properties)) return;
        if (sel.bindingPath && !matchBinding(c, sel.bindingPath)) return;
        const d = c.getDomRef();
        if (!d || !d.id) return;
        // Descendant STRICT : le conteneur lui-même n'est pas son propre contenu.
        if (scope && (d === scope || !scope.contains(d))) return;
        ids.push(d.id);
      } catch (e) {}
    });
    return ids;
  }

  // Lit UNE propriété sur CHAQUE contrôle correspondant au sélecteur rôle, dans
  // l'ordre du registre. Deux raisons de lire la propriété du CONTRÔLE plutôt
  // que le texte rendu : la valeur est exacte (le rendu peut y ajouter ce que le
  // contrôle affiche en plus, comme le compteur d'un StandardListItem), et elle
  // reste lisible quand le contrôle est rendu mais MASQUÉ (colonne repliée d'un
  // FlexibleColumnLayout, onglet inactif), là où une lecture de texte attend une
  // visibilité qui ne viendra pas.
  // Retourne { values, unknown, available } : `unknown` signale une propriété
  // absente des métadonnées du contrôle, et `available` liste alors ce qui
  // existe, pour que l'appelant puisse échouer en nommant les bons noms.
  // Une valeur franchit la frontière en JSON-safe : les TABLEAUX gardent leurs
  // éléments primitifs (fieldGroupIds vaut ['a','b'], que String() écrasait en
  // 'a,b' et [] en '', indiscernable d'une chaîne vide légitime) ; tout autre
  // objet reste coercé en chaîne (types rares, cycles possibles).
  function jsonSafeValue(v) {
    if (v === undefined || v === null) return null;
    const t = typeof v;
    if (t === 'string' || t === 'number' || t === 'boolean') return v;
    if (Array.isArray(v)) {
      return v.map((e) => {
        const te = typeof e;
        if (e === null || te === 'string' || te === 'number' || te === 'boolean') return e;
        return String(e);
      });
    }
    return String(v);
  }
  function readProperty(payload) {
    if (!isUI5()) return null;
    let req;
    try { req = JSON.parse(payload); } catch (e) { return null; }
    const name = String(req.property || '');
    const ids = resolveByRole(JSON.stringify(req.selector || {}));
    if (ids === null) return null;
    const out = { values: [], unknown: false, available: [] };
    ids.forEach((id) => {
      const c = byId(id);
      if (!c) return;
      let known = false;
      try {
        const md = c.getMetadata();
        const all = md.getAllProperties ? md.getAllProperties() : md.getProperties();
        known = !!(all && Object.prototype.hasOwnProperty.call(all, name));
        if (!known && !out.available.length && all) out.available = Object.keys(all).sort();
      } catch (e) {}
      if (!known) { out.unknown = true; return; }
      let v = null;
      try { v = c.getProperty(name); } catch (e) { v = null; }
      out.values.push(jsonSafeValue(v));
    });
    return out;
  }

