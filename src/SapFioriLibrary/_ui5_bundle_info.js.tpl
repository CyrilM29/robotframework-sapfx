
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
  // qui existait en plus. Même contrat côté propriétés : `properties` ne porte
  // que les valeurs primitives, et `property_keys` liste TOUT ce qui a été lu
  // (une propriété à valeur tableau comme fieldGroupIds disparaissait sans
  // trace, relevé 2026-09-05 en croisant la fiche avec la doc du Demo Kit :
  // 17 clés contre 18 documentées). S'appuie sur isUI5/byId/props/
  // resolveByRole/jsonSafeValue du chapitre core (même IIFE, déclarations
  // hissées).
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
    const p = props(c);
    info.properties = primitiveEntries(p);
    info.property_keys = Object.keys(p).sort();
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

  // ---- Inventaire de métadonnées (Get Ui5 Control Metadata) ----------------
  // Le CONTRAT DÉCLARÉ d'un contrôle, indépendant des valeurs courantes et de
  // leur primitivité : propriétés, agrégations, associations et événements
  // avec type, valeur par défaut, provenance (propre ou emprunté) et classe
  // d'origine, plus la chaîne d'héritage. C'est la lecture qui permet de
  // confronter une documentation d'API au contrôle VIVANT : la fiche de
  // `controlInfo` porte les VALEURS (et réduit aux primitives), celle-ci
  // porte l'INVENTAIRE. `getProperties()` et ses pairs rendent les membres
  // PROPRES de la classe, `getAllProperties()` ajoute l'hérité : la
  // provenance se lit dans cet écart, et la classe d'origine en remontant
  // `getParent()` jusqu'à la classe qui déclare le membre.
  function metadataLineage(md) {
    const out = [];
    let cur = md;
    let guard = 0;
    while (cur && guard < 50) {
      try { out.push(String(cur.getName())); } catch (e) { break; }
      try { cur = cur.getParent ? cur.getParent() : null; } catch (e) { cur = null; }
      guard += 1;
    }
    return out;
  }
  function ownMembers(md, getter) {
    try { const m = md[getter] ? md[getter]() : null; return m || {}; }
    catch (e) { return {}; }
  }
  function declaringClass(md, getter, name) {
    let cur = md;
    let guard = 0;
    while (cur && guard < 50) {
      if (Object.prototype.hasOwnProperty.call(ownMembers(cur, getter), name)) {
        try { return String(cur.getName()); } catch (e) { return ''; }
      }
      try { cur = cur.getParent ? cur.getParent() : null; } catch (e) { cur = null; }
      guard += 1;
    }
    return '';
  }
  function describeMembers(md, allGetter, ownGetter, opts) {
    const out = {};
    let all = null;
    try { all = md[allGetter] ? md[allGetter]() : null; } catch (e) { all = null; }
    if (!all) return out;
    const own = ownMembers(md, ownGetter);
    Object.keys(all).forEach((name) => {
      const entry = all[name] || {};
      const desc = {
        borrowed: !Object.prototype.hasOwnProperty.call(own, name),
        origin: declaringClass(md, ownGetter, name),
      };
      if (opts.type) {
        desc.type = (entry.type === undefined || entry.type === null)
          ? '' : String(entry.type);
      }
      if (opts.multiple) desc.multiple = !!entry.multiple;
      if (opts.defaultValue) desc.default = jsonSafeValue(entry.defaultValue);
      out[name] = desc;
    });
    return out;
  }
  function controlMetadata(payload) {
    if (!isUI5()) return null;
    let req;
    try { req = JSON.parse(payload); } catch (e) { return null; }
    const ids = resolveByRole(JSON.stringify(req.selector || {}));
    if (ids === null) return null;
    const out = [];
    ids.forEach((id) => {
      const c = byId(id);
      if (!c) return;
      let md = null;
      try { md = c.getMetadata(); } catch (e) { md = null; }
      if (!md) return;
      let full = '';
      try { full = String(md.getName()); } catch (e) {}
      out.push({
        id: String(id),
        type: full,
        lineage: metadataLineage(md),
        properties: describeMembers(md, 'getAllProperties', 'getProperties',
                                    { type: true, defaultValue: true }),
        aggregations: describeMembers(md, 'getAllAggregations', 'getAggregations',
                                      { type: true, multiple: true }),
        associations: describeMembers(md, 'getAllAssociations', 'getAssociations',
                                      { type: true, multiple: true }),
        events: describeMembers(md, 'getAllEvents', 'getEvents', {}),
      });
    });
    return out;
  }
