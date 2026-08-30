
  // ---- Fiche de contrôle (Get Ui5 Control Info / Get Ui5 Aggregation Info) --
  // Chapitre du bundle (convention #13 : un chapitre par fichier, concaténés
  // par _ui5_js.py). Promu de sondes JS inline vivant dans des page objects
  // (convention #12) : lire le TYPE d'un contrôle rendu, son CONTEXTE DE
  // LIAISON (la clé technique d'un item de liste dont l'id est généré) et les
  // enfants d'une AGRÉGATION (les items d'un Select ne sont PAS rendus tant
  // que le popover est fermé, donc invisibles au moteur role). Le contexte de
  // liaison est réduit à ses entrées primitives de premier niveau : les
  // valeurs profondes portent des contrôles et des cycles, et tout ce que les
  // campagnes lisent (id, name, target) est primitif ; `object_keys` liste ce
  // qui existait en plus. S'appuie sur isUI5/byId/props/resolveByRole du
  // chapitre core (même IIFE, déclarations hissées).
  function primitiveEntries(obj) {
    const out = {};
    if (!obj || typeof obj !== 'object') return out;
    Object.keys(obj).forEach((k) => {
      const v = obj[k];
      const t = typeof v;
      if (v === null || t === 'string' || t === 'number' || t === 'boolean') out[k] = v;
    });
    return out;
  }
  function describeControl(c, model) {
    const info = { id: '', type: '', rendered: false, properties: {}, binding: null };
    try { info.id = String(c.getId()); } catch (e) {}
    try { info.type = String(c.getMetadata().getName()); } catch (e) {}
    try { info.rendered = !!(c.getDomRef && c.getDomRef()); } catch (e) {}
    info.properties = primitiveEntries(props(c));
    try {
      const ctx = c.getBindingContext ? c.getBindingContext(model || undefined) : null;
      if (ctx) {
        const o = (ctx.getObject && ctx.getObject()) || {};
        info.binding = { path: String(ctx.getPath ? ctx.getPath() : ''),
                         object: primitiveEntries(o),
                         object_keys: Object.keys(o || {}) };
      }
    } catch (e) {}
    return info;
  }
  function controlInfo(payload) {
    if (!isUI5()) return null;
    let req;
    try { req = JSON.parse(payload); } catch (e) { return null; }
    const ids = resolveByRole(JSON.stringify(req.selector || {}));
    if (ids === null) return null;
    const model = req.model ? String(req.model) : null;
    if (!req.aggregation) {
      const out = [];
      ids.forEach((id) => { const c = byId(id); if (c) out.push(describeControl(c, model)); });
      return out;
    }
    const idx = req.index ? (parseInt(req.index, 10) || 0) : 0;
    const host = (idx >= 0 && idx < ids.length) ? byId(ids[idx]) : null;
    if (!host) return { __out_of_range: ids.length };
    let kids = null;
    // Une agrégation NON DÉCLARÉE lève côté UI5 ; une agrégation déclarée mais
    // vide rend null/[] : les deux cas restent distincts pour l'appelant.
    try { kids = host.getAggregation ? host.getAggregation(String(req.aggregation)) : null; }
    catch (e) { return { __no_aggregation: String(req.aggregation) }; }
    if (kids === null || kids === undefined) kids = [];
    if (!Array.isArray(kids)) kids = [kids];
    return kids.map((k) => describeControl(k, model));
  }
