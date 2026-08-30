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
  // Un type court en DEUX mots (ShellBar) devient 'shell-bar' : il contient donc
  // un tiret, et l'ancienne version le prenait pour un tag COMPLET, jamais
  // préfixé par 'ui5-'. Conséquence mesurée live sur une barre shell Work Zone :
  // `tag=ShellBar` ne matchait RIEN alors que la page portait bien un
  // <ui5-shellbar-6bfd01e3>. Les orthographes réelles d'UI5 Web Components
  // MÉLANGENT en outre les deux régimes : 'ui5-shellbar' (collé),
  // 'ui5-side-navigation' (à tirets), et 'ui5-shellbar-item' (MIXTE : la
  // famille collée, le composant séparé). Mesuré live sur la même barre le
  // 2026-08-26 : les deux seules formes essayées ('ui5-shellbaritem',
  // 'ui5-shell-bar-item') laissaient `tag=ShellBarItem` à 0 correspondance.
  // On génère donc TOUTES les combinaisons collé/tiret entre les mots
  // (2^(n-1), borné : au-delà de 8 mots, un nom pareil n'existe pas chez UI5,
  // on retombe sur les deux formes extrêmes), sans jamais élargir un tag déjà
  // préfixé (celui-là est une demande explicite).
  function wcTagForms(want) {
    const parts = want.split('-');
    if (parts.length < 2) return [want];
    if (parts.length > 8) return [want, parts.join('')];
    const forms = [];
    for (let mask = 0; mask < (1 << (parts.length - 1)); mask++) {
      let form = parts[0];
      for (let i = 1; i < parts.length; i++) {
        form += (((mask >> (i - 1)) & 1) ? '-' : '') + parts[i];
      }
      forms.push(form);
    }
    return forms;
  }
  function wcTagMatches(tag, wanted) {
    const want = wcKebab(wanted);
    const candidates = [];
    let prefixed = false;
    for (let i = 0; i < WC_PREFIXES.length; i++) {
      if (want.lastIndexOf(WC_PREFIXES[i], 0) === 0) { prefixed = true; break; }
    }
    if (prefixed || want.indexOf('-') !== -1) candidates.push(want);
    if (!prefixed) {
      const forms = wcTagForms(want);
      for (let i = 0; i < WC_PREFIXES.length; i++) {
        for (let j = 0; j < forms.length; j++) {
          candidates.push(WC_PREFIXES[i] + forms[j]);
        }
      }
    }
    for (let i = 0; i < candidates.length; i++) {
      const c = candidates[i];
      if (tag === c || tag.lastIndexOf(c + '-', 0) === 0) return true;
    }
    return false;
  }
  function wcVisible(el) {
    const r = el.getBoundingClientRect();
    return !!(r.width || r.height);
  }
  // Les primitives de franchissement des frontières de shadow root
  // (`deepQueryAll`, `deepParent`, `wcCssPath`, `piercingQueryAll`) vivent
  // dans le chapitre `_ui5_bundle_shadow.js.tpl` (convention #13), concaténé
  // dans le même IIFE.
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
  // Résout un sélecteur WC vers des CHEMINS CSS (pas des ids : voir
  // wcCssPath). Ne retourne que les hôtes rendus (rect non nul). Parcours
  // PROFOND (deepQueryAll) : les hôtes imbriqués dans les shadow roots
  // d'autres hôtes entrent dans le résultat, avec un chemin que le CSS de
  // Playwright sait suivre (jonction descendante aux frontières).
  function resolveByWc(selJson) {
    const sel = JSON.parse(selJson);
    const out = [];
    const nodes = deepQueryAll();
    for (let i = 0; i < nodes.length; i++) {
      const el = nodes[i];
      if (!wcMatches(el, sel)) continue;
      if (!wcVisible(el)) continue;
      out.push(wcCssPath(el));
    }
    return out;
  }
  // Recorder : l'hôte custom element ui5-* propriétaire le plus proche du
  // nœud. Remontée par deepParent : un clic DANS le shadow root d'un hôte
  // (la barre shell Work Zone) doit franchir la frontière pour le trouver.
  function closestWcElement(node) {
    let cur = (node && node.nodeType === 1) ? node : (node ? node.parentElement : null);
    while (cur) {
      const tag = cur.tagName ? cur.tagName.toLowerCase() : '';
      if (tag.indexOf('-') !== -1) {
        for (let i = 0; i < WC_PREFIXES.length; i++) {
          if (tag.lastIndexOf(WC_PREFIXES[i], 0) === 0) return cur;
        }
      }
      cur = deepParent(cur);
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
      cur = deepParent(cur);   // franchit une frontière de shadow root
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
  // Candidats du moteur dom, en DEUX temps. D'abord le parcours profond
  // filtré par `matches()` : il couvre le light DOM (comportement
  // historique, inchangé) et les éléments d'un shadow root désignés par un
  // sélecteur ancré DANS leur portée. Puis, seulement si cela ne donne rien,
  // la résolution perçante segment par segment : elle rattrape les chemins
  // qui FRANCHISSENT une frontière, que `matches()` ne peut pas reconnaître
  // (les ancêtres d'un élément shadow ne comprennent pas ses hôtes
  // light-DOM), et c'est la forme exacte que rend `wcCssPath`. Le repli ne
  // s'exécute qu'en l'absence de correspondance : un sélecteur qui résolvait
  // déjà garde son résultat, à l'élément près.
  function domCandidates(css) {
    if (!css) return deepQueryAll();
    const nodes = deepQueryAll();
    const out = [];
    for (let i = 0; i < nodes.length; i++) {
      let hit = false;
      try { hit = nodes[i].matches && nodes[i].matches(css); } catch (e) { hit = false; }
      if (hit) out.push(nodes[i]);
    }
    return out.length ? out : piercingQueryAll(css);
  }
  function resolveByDom(selJson) {
    const sel = JSON.parse(selJson);
    if (sel.css) {
      // CSS invalide : aucune correspondance (l'échec du keyword mentionne
      // cette cause). Validé UNE fois ici, avant tout parcours.
      try { document.querySelectorAll(sel.css); } catch (e) { return []; }
    }
    const nodes = domCandidates(sel.css);
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
      // Comptage PROFOND (shadow roots ouverts compris) : mesuré live sur un
      // shell Work Zone, 6 hôtes en light DOM et 16 en profondeur ; le
      // comptage light-DOM sous-estimait ce que le moteur wc sait désormais
      // atteindre. `wc_hosts_light` conserve la mesure de surface : l'écart
      // entre les deux dit qu'un shell imbrique ses composants.
      const all = deepQueryAll();
      let wc = 0, light = 0;
      for (let i = 0; i < all.length; i++) {
        const tag = all[i].tagName.toLowerCase();
        if (tag.indexOf('-') === -1) continue;
        for (let j = 0; j < WC_PREFIXES.length; j++) {
          if (tag.lastIndexOf(WC_PREFIXES[j], 0) === 0) {
            wc++;
            if (all[i].getRootNode() === document) light++;
            break;
          }
        }
      }
      out.wc_hosts = wc;
      out.wc_hosts_light = light;
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

  // Les correspondances du moteur role dont le nœud DOM a un rectangle NON
  // NUL. Le registre « rendu » ne suffit pas : mesuré live (2026-08-26, shell
  // Work Zone), un champ de recherche RENDU garde un rectangle 0x0 en
  // permanence (`offsetParent` nul), et `Ui5 Control Should Be Visible`
  // passait dessus là où ses miroirs wc/dom exigent déjà un rect non nul.
  function resolveVisibleByRole(selJson) {
    const ids = resolveByRole(selJson) || [];
    const out = [];
    for (let i = 0; i < ids.length; i++) {
      try {
        const el = document.getElementById(ids[i]);
        if (el && wcVisible(el)) out.push(ids[i]);
      } catch (e) {}
    }
    return out;
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

  window.__SAPFX = { __v: V, isUI5: isUI5, resolveByXPath: resolveByXPath,
                     resolveByRole: resolveByRole, resolveByWc: resolveByWc,
                     resolveByDom: resolveByDom, pageComposition: pageComposition,
                     resolveVisibleByRole: resolveVisibleByRole,
                     capture: capture, captureWc: captureWc, captureDom: captureDom,
                     bestXpath: bestXpath, readTable: readTable, dumpTree: dumpTree,
                     readProperty: readProperty, controlInfo: controlInfo,
                     openPopups: openPopups, dialogButton: dialogButton,
                     idleState: idleState, getMessages: getMessages,
                     captureSid: captureSid, highlightInfo: highlightInfo };
})();
