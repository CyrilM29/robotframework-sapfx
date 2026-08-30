  // ---- Frontières de shadow DOM (chapitre partagé, convention #13) ----------
  // Les primitives qui franchissent les frontières de shadow root OUVERT :
  // parcours profond, remontée, chemin CSS, et résolution perçante. Elles
  // servent les moteurs wc et dom, le balayage des popups Web Components et
  // les remontées du recorder. Extraites de `_ui5_bundle_engines.js.tpl` le
  // 2026-08-26, quand la résolution perçante a fait franchir les 500 lignes
  // à ce fichier.
  //
  // Pourquoi tout cela existe : un shell SAP Build Work Zone imbrique des Web
  // Components DANS le shadow root d'autres Web Components. Mesuré live le
  // 2026-08-26 : 6 hôtes `ui5-*` en light DOM, 16 en profondeur, dont trois
  // `ui5-button` qu'un `document.querySelectorAll` ne peut pas voir. Les
  // shadow roots FERMÉS restent invisibles, et c'est sans conséquence : rien
  // d'adressable n'y vit de toute façon (Playwright ne les perce pas non plus).

  // Tous les éléments d'un document ou d'un sous-arbre, shadow roots ouverts
  // compris (ordre : les éléments d'une portée, puis ses shadow roots dans
  // l'ordre de rencontre).
  function deepQueryAll(root) {
    const out = [];
    const scopes = [root || document];
    for (let s = 0; s < scopes.length; s++) {
      let nodes;
      try { nodes = scopes[s].querySelectorAll('*'); } catch (e) { continue; }
      for (let i = 0; i < nodes.length; i++) {
        out.push(nodes[i]);
        if (nodes[i].shadowRoot) scopes.push(nodes[i].shadowRoot);
      }
    }
    return out;
  }

  // Parent de remontée : l'élément parent, ou l'HÔTE du shadow root quand on
  // est à la racine d'un shadow tree. La remontée des moteurs et du recorder
  // doit franchir la frontière, sinon un clic dans la barre shell Work Zone
  // ne trouve jamais son hôte `ui5-*`.
  function deepParent(el) {
    if (!el) return null;
    if (el.parentElement) return el.parentElement;
    const root = el.getRootNode ? el.getRootNode() : null;
    return (root && root.host) ? root.host : null;
  }

  // Chemin CSS ancré au plus proche ancêtre à id (sinon body) : les hôtes WC
  // n'ont souvent PAS d'id, contrairement aux contrôles UI5 classiques, on ne
  // peut pas retourner un simple [id=…]. Les ids contenant un guillemet
  // (littéral CSS cassé) sont ignorés comme ancre. À une frontière de shadow
  // root, le chemin repart de l'HÔTE et la jonction se fait par combinateur
  // DESCENDANT (' ') : le CSS de Playwright perce les shadow roots ouverts en
  // descendance, jamais en enfant direct ('>') à travers la frontière.
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
      if (!cur.parentElement) {
        const root = cur.getRootNode ? cur.getRootNode() : null;
        if (root && root.host) {
          return wcCssPath(root.host) + ' ' + parts.join(' > ');
        }
      }
      cur = cur.parentElement;
    }
    parts.unshift('body');
    return parts.join(' > ');
  }

  // Les portées de recherche sous une racine : la racine, son propre shadow
  // root s'il en a un, et chaque shadow root ouvert de son sous-arbre.
  function scopesUnder(root) {
    const scopes = [root];
    if (root && root.shadowRoot) scopes.push(root.shadowRoot);
    for (let s = 0; s < scopes.length; s++) {
      let nodes;
      try { nodes = scopes[s].querySelectorAll('*'); } catch (e) { continue; }
      for (let i = 0; i < nodes.length; i++) {
        if (nodes[i].shadowRoot) scopes.push(nodes[i].shadowRoot);
      }
    }
    return scopes;
  }

  // Découpe un sélecteur sur ses combinateurs DESCENDANTS de haut niveau (les
  // espaces), en respectant crochets, parenthèses et guillemets, et en ne
  // coupant jamais autour d'un combinateur explicite : `a[x="y z"] > b c`
  // donne ['a[x="y z"] > b', 'c'].
  function splitDescendantCombinators(css) {
    const parts = [];
    let brackets = 0, parens = 0, quote = '';
    let current = '', pendingSpace = false;
    for (let i = 0; i < css.length; i++) {
      const ch = css[i];
      if (quote) {
        current += ch;
        if (ch === quote && css[i - 1] !== '\\') quote = '';
        continue;
      }
      if (ch === '"' || ch === "'") { quote = ch; current += ch; continue; }
      if (ch === '[') brackets++;
      else if (ch === ']') brackets--;
      else if (ch === '(') parens++;
      else if (ch === ')') parens--;
      if ((ch === ' ' || ch === '\t' || ch === '\n') && !brackets && !parens) {
        pendingSpace = true;
        continue;
      }
      if (pendingSpace) {
        pendingSpace = false;
        const trimmed = current.replace(/\s+$/, '');
        const last = trimmed.charAt(trimmed.length - 1);
        // combinateur explicite avant ou après l'espace : même segment
        if (ch === '>' || ch === '+' || ch === '~'
            || last === '>' || last === '+' || last === '~') {
          current = trimmed + ' ' + ch;
          continue;
        }
        if (trimmed) { parts.push(trimmed); current = ''; }
      }
      current += ch;
    }
    const tail = current.replace(/\s+$/, '');
    if (tail) parts.push(tail);
    return parts;
  }

  // Résolution PERÇANTE : chaque segment descendant est cherché dans le
  // contexte courant ET dans les shadow roots qu'il contient. C'est ce que
  // fait le CSS de Playwright, et ce que `matches()` ne peut PAS reproduire :
  // les ancêtres d'un élément shadow ne comprennent pas ses hôtes light-DOM,
  // donc un chemin qui FRANCHIT une frontière (celui que rend `wcCssPath`)
  // ne matche jamais l'élément qu'il désigne. Mesuré live le 2026-08-26 : le
  // même sélecteur rendait 1 correspondance via la bibliothèque Browser et 0
  // via le moteur dom. Employée en REPLI seulement (voir `resolveByDom`),
  // donc sans changer le sort d'un sélecteur qui résolvait déjà.
  // Hors périmètre volontaire : les listes de sélecteurs (virgule), qui
  // demanderaient de percer chaque branche séparément.
  function piercingQueryAll(css) {
    if (!css || css.indexOf(',') !== -1) return [];
    const segments = splitDescendantCombinators(css);
    if (segments.length < 2) return [];   // rien à franchir
    let contexts = [document];
    for (let s = 0; s < segments.length; s++) {
      const next = [];
      for (let c = 0; c < contexts.length && next.length < 2000; c++) {
        const scopes = scopesUnder(contexts[c]);
        for (let k = 0; k < scopes.length; k++) {
          let found;
          try { found = scopes[k].querySelectorAll(segments[s]); }
          catch (e) { return []; }        // segment invalide : aucune correspondance
          for (let i = 0; i < found.length; i++) {
            if (next.indexOf(found[i]) === -1) next.push(found[i]);
          }
        }
      }
      if (!next.length) return [];
      contexts = next;
    }
    return contexts;
  }
