  // ==== Chapitre : LECTURE D'UN TABLEAU UI5 ==================================
  // Extrait de `_ui5_bundle_capture.js.tpl` le 2026-09-15 (convention #13 :
  // un chapitre par fichier). La couture est reelle : la capture sert le
  // recorder (decrire un controle pour en faire un localisateur), ceci sert
  // l'EXTRACTION (sortir le contenu d'une table avec son contrat). Les deux
  // chapitres sont concatenes dans le meme IIFE, donc `controlText` reste
  // visible de ses deux appelants.
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
    // Repli DOM : `innerText` et non `textContent`. Le second COLLE les
    // morceaux d'une cellule composite, produisant une valeur qui n'existe
    // nulle part à l'écran (mesuré le 2026-09-15 sur une List Report Fiori
    // Elements : un sap.fe.macros.Field rendant description et identifiant
    // donnait « Sightseeing in New York City, New York4 133 »). `innerText`
    // respecte le rendu et sépare les deux ; le repli reste `textContent`,
    // qui seul répond sur un noeud non rendu.
    try {
      const dom = c.getDomRef && c.getDomRef();
      if (dom) {
        const brut = (dom.innerText !== undefined && dom.innerText !== null)
          ? dom.innerText : dom.textContent;
        return String(brut || '').trim();
      }
    } catch (e) {}
    return '';
  }
  // Lit une table sap.m.Table (getItems/getCells) ou sap.ui.table.Table (getRows, lignes
  // VISIBLES seulement, virtualisation) vers une liste d'objets {en-tête: valeur}.
  // Rend un CONSTAT, pas seulement des lignes : le type du contrôle, la voie de lecture
  // employée, le nombre de lignes candidates et combien ont été écartées faute de
  // cellules. Sans ces compteurs, un contrôle qui porte bien des lignes mais ne les
  // expose pas par `getCells` (sap.ui.documentation.LightTable, mesuré 2026-08-30) est
  // indiscernable d'une table légitimement vide : l'appelant rendait alors [] en
  // silence, vert et faux. C'est `tableReadVerdict` (Python) qui tranche.
  function readTable(controlId) {
    if (!isUI5()) return null;
    const t = byId(controlId);
    if (!t) return null;
    let type = '';
    try { type = String(t.getMetadata && t.getMetadata().getName ? t.getMetadata().getName() : ''); }
    catch (e) {}
    const hasColumns = (typeof t.getColumns === 'function');
    const cols = hasColumns ? (t.getColumns() || []) : [];
    const headers = cols.map((col, i) => {
      let h = '';
      try {
        if (typeof col.getHeader === 'function') h = controlText(col.getHeader());
        if (!h && typeof col.getLabel === 'function') h = controlText(col.getLabel());
      } catch (e) {}
      return h || ('col' + i);
    });
    let items = [], source = null;
    if (typeof t.getItems === 'function') { items = t.getItems() || []; source = 'items'; }
    else if (typeof t.getRows === 'function') { items = t.getRows() || []; source = 'rows'; }
    const out = [];
    let skipped = 0;
    items.forEach((row) => {
      if (typeof row.getCells !== 'function') { skipped++; return; }   // en-tête de groupe
      const cells = row.getCells();
      const obj = {};
      cells.forEach((cell, i) => { obj[headers[i] || ('col' + i)] = controlText(cell); });
      out.push(obj);
    });
    // Le total DÉCLARÉ voyage avec les lignes, pour que `Read Ui5 Table` puisse
    // AVERTIR quand il n'a rendu qu'une partie de la table. Rendre une lecture
    // partielle en silence est le défaut que tout ce lot combat ; ce keyword
    // garde son contrat (il rend les lignes instanciées, des suites légitimes
    // en dépendent) mais cesse d'être muet, comme la réparation de localisateur
    // qui journalise toujours ce qu'elle a fait.
    let declared = null;
    for (const nom of ['items', 'rows']) {
      let b = null;
      try { b = t.getBinding(nom); } catch (e) {}
      if (!b) continue;
      try { declared = b.getLength(); } catch (e) {}
      break;
    }
    return { type: type, source: source, hasColumns: hasColumns, headers: headers,
             candidates: items.length, skipped: skipped, declared: declared,
             rows: out };
  }

  // Ce qu'une table UI5 DÉCLARE contenir, par opposition à ce qu'elle a rendu.
  // La seule chose qui distingue « la table tient en N lignes » de « la lecture
  // s'est arrêtée à N lignes », et rien d'autre ne le trahit : mesuré le
  // 2026-09-15 sur une List Report Fiori Elements, `getItems()` rendait 30
  // lignes (le seuil de croissance) quand le binding en déclarait 4133, et les
  // 30 étaient parfaitement remplies. `isLengthFinal` à false signale que le
  // total lui-même est provisoire (le modèle n'a pas fini de compter), auquel
  // cas il ne borne rien et doit être rapporté comme tel.
  function tableInfo(controlId) {
    if (!isUI5()) return null;
    const t = byId(controlId);
    if (!t) return null;
    let type = '';
    try { type = String(t.getMetadata && t.getMetadata().getName ? t.getMetadata().getName() : ''); }
    catch (e) {}
    const hasColumns = (typeof t.getColumns === 'function');
    const cols = hasColumns ? (t.getColumns() || []) : [];
    const headers = cols.map((col, i) => {
      let h = '';
      try {
        if (typeof col.getHeader === 'function') h = controlText(col.getHeader());
        if (!h && typeof col.getLabel === 'function') h = controlText(col.getLabel());
      } catch (e) {}
      return h || ('col' + i);
    });
    let rendered = 0, source = null;
    if (typeof t.getItems === 'function') { rendered = (t.getItems() || []).length; source = 'items'; }
    else if (typeof t.getRows === 'function') { rendered = (t.getRows() || []).length; source = 'rows'; }
    let declared = null, lengthFinal = null, contexts = null, binding = '';
    for (const name of ['items', 'rows']) {
      let b = null;
      try { b = t.getBinding(name); } catch (e) {}
      if (!b) continue;
      binding = name;
      try { declared = b.getLength(); } catch (e) {}
      try { lengthFinal = (typeof b.isLengthFinal === 'function') ? b.isLengthFinal() : null; }
      catch (e) {}
      try { contexts = (b.getCurrentContexts() || []).length; } catch (e) {}
      break;
    }
    let growing = null, threshold = null;
    try { growing = (typeof t.getGrowing === 'function') ? t.getGrowing() : null; } catch (e) {}
    try { threshold = (typeof t.getGrowingThreshold === 'function') ? t.getGrowingThreshold() : null; }
    catch (e) {}
    return { type: type, source: source, binding: binding, headers: headers,
             rendered_rows: rendered, declared_rows: declared, contexts: contexts,
             length_final: lengthFinal, growing: growing, growing_threshold: threshold,
             columns: cols.length };
  }

