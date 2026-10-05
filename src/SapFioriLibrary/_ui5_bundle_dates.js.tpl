  // --- dates : saisie indépendante de la locale ------------------------------
  // Le miroir web de `Input Date` (ECC). Une date se TAPE dans le format que le
  // contrôle attend, et ce format dépend de la locale du navigateur ET du type
  // de contrôle : mesuré le 2026-09-24 sur un aperçu Fiori Elements RAP, en
  // `fr` un `sap.m.DatePicker` acceptait `15/10/2026` là où un
  // `sap.ui.mdc.Field` refusait `06/07/2025` et acceptait `6 juil. 2025`. La
  // seule source qui connaisse le format exact est le TYPE de la liaison de la
  // valeur : la valeur MODÈLE (ISO) est formatée par lui, puis relue après la
  // saisie. Aucun libellé, aucune locale supposée.

  // Le contrôle qui PORTE la valeur : un champ `sap.ui.mdc` (sa saisie interne
  // est liée à un modèle de conditions privé, pas à la donnée), sinon le
  // contrôle lui-même (`sap.m.DatePicker`).
  function dateOwner(c) {
    let cur = c;
    for (let depth = 0; cur && depth < 4; depth++) {
      try { if (cur.isA && cur.isA('sap.ui.mdc.field.FieldBase')) return cur; } catch (e) {}
      try { cur = cur.getParent ? cur.getParent() : null; } catch (e) { cur = null; }
    }
    return c;
  }

  function dateParts(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    return m ? { y: +m[1], m: +m[2], d: +m[3] } : null;
  }

  // Nature du type de liaison. Une date PURE se lit en heure locale ; un
  // `sap.ui.model.odata.type.DateTime` (OData V2 `Edm.DateTime`) contraint en
  // affichage `Date` porte une date à minuit UTC : il se formate et se RELIT en
  // UTC, sinon un navigateur à l'ouest d'UTC lit la veille. Un vrai type date
  // ET heure (DateTimeOffset, DateTime sans contrainte, heure) est refusé.
  // Les contraintes se lisent par l'API PUBLIQUE `getConstraints()` : le membre
  // interne `oConstraints` porte une AUTRE forme (`{isDateOnly: true}` au lieu
  // de `{displayFormat: 'Date'}`, relevé sur SAPUI5 1.120), gardée en repli.
  function dateKind(type) {
    const name = (type && type.getName && type.getName()) || '';
    let constraints = {};
    let internal = {};
    try { if (type && type.getConstraints) constraints = type.getConstraints() || {}; } catch (e) {}
    try { internal = (type && type.oConstraints) || {}; } catch (e) {}
    const dateOnly = constraints.displayFormat === 'Date' || internal.displayFormat === 'Date'
      || internal.isDateOnly === true;
    if (/odata\.type\.DateTime$/.test(name) && dateOnly) {
      return { name: name, utc: true, unsupported: false };
    }
    if (/DateTime|TimeOfDay|Time$/.test(name)) return { name: name, utc: false, unsupported: true };
    return { name: name, utc: false, unsupported: false };
  }

  function isoOf(value, utc) {
    if (value instanceof Date) {
      const pad = (n) => (n < 10 ? '0' : '') + n;
      const y = utc ? value.getUTCFullYear() : value.getFullYear();
      const mo = utc ? value.getUTCMonth() : value.getMonth();
      const d = utc ? value.getUTCDate() : value.getDate();
      return y + '-' + pad(mo + 1) + '-' + pad(d);
    }
    return value == null ? '' : String(value);
  }

  function dateBinding(owner) {
    let binding = null;
    let type = null;
    try { binding = owner.getBinding ? owner.getBinding('value') : null; } catch (e) {}
    try { type = binding && binding.getType ? binding.getType() : null; } catch (e) {}
    return { binding: binding, kind: dateKind(type), type: type };
  }

  function modelIso(owner, info) {
    try {
      if (info.binding) return isoOf(info.binding.getValue(), info.kind.utc);
      if (owner.getDateValue) return isoOf(owner.getDateValue(), false);
    } catch (e) {}
    return '';
  }

  // Texte à taper pour la date ISO demandée :
  // { text, source, type, before } ou { error }. `before` est la valeur modèle
  // d'AVANT la saisie : si elle vaut déjà la date demandée, la relecture seule
  // ne prouvera rien, et l'appelant le sait.
  function dateText(payload) {
    if (!isUI5()) return null;
    let req;
    try { req = JSON.parse(payload) || {}; } catch (e) { req = {}; }
    const c = byId(req.id);
    if (!c) return { error: 'not_found' };
    const parts = dateParts(req.iso);
    if (!parts) return { error: 'bad_iso' };
    const owner = dateOwner(c);
    const info = dateBinding(owner);
    if (info.kind.unsupported) return { error: 'not_a_date_type', type: info.kind.name };
    const before = modelIso(owner, info);
    if (info.type && typeof info.type.formatValue === 'function') {
      const asDate = info.kind.utc ? new Date(Date.UTC(parts.y, parts.m - 1, parts.d))
                                   : new Date(parts.y, parts.m - 1, parts.d);
      const candidates = info.kind.utc ? [asDate] : [req.iso, asDate];
      for (let i = 0; i < candidates.length; i++) {
        try {
          const text = info.type.formatValue(candidates[i], 'string');
          if (text) return { text: String(text), source: 'binding_type', type: info.kind.name, before: before };
        } catch (e) {}
      }
    }
    try {
      const DF = sap.ui.require && sap.ui.require('sap/ui/core/format/DateFormat');
      const fmt = (typeof c.getDisplayFormat === 'function' && c.getDisplayFormat()) || '';
      if (DF && typeof c.getDisplayFormat === 'function') {
        const styles = ['short', 'medium', 'long', 'full'];
        const opts = (!fmt || styles.indexOf(fmt) >= 0) ? { style: fmt || 'medium' } : { pattern: fmt };
        const text = DF.getDateInstance(opts).format(new Date(parts.y, parts.m - 1, parts.d));
        if (text) return { text: String(text), source: 'display_format', type: info.kind.name, before: before };
      }
    } catch (e) {}
    return { error: 'no_date_format', type: info.kind.name };
  }

  // Refus CÔTÉ CLIENT de la saisie : un message `Error` dont la cible est la
  // valeur du CONTRÔLE (`<id>/value`, saisie interne comprise), jamais une
  // cible de DONNÉES. La distinction compte, mesurée le 2026-09-24 sur un
  // brouillon RAP : une validation SERVEUR (début après la fin) met le champ
  // en état `Error` alors que la date a bien été retenue au modèle ; seul un
  // refus du contrôle lui-même (format, aide à la saisie qui valide) cible
  // `<id>/value`. `null` quand le modèle de messages est illisible.
  function clientRefusal(ids) {
    const model = messageModel();
    if (!model) return null;
    let data = [];
    try { data = model.getData() || []; } catch (e) { return null; }
    for (let i = 0; i < data.length; i++) {
      const m = data[i];
      let type = '';
      let targets = [];
      try { type = String(m.getType ? m.getType() : m.type); } catch (e) {}
      try { targets = m.getTargets ? m.getTargets() : [m.getTarget ? m.getTarget() : m.target]; } catch (e) {}
      if (type !== 'Error') continue;
      for (let j = 0; j < targets.length; j++) {
        const t = String(targets[j] || '');
        if (/\/value$/.test(t) && ids.some((id) => id && t.indexOf(id) === 0)) return true;
      }
    }
    return false;
  }

  // Valeur MODÈLE retenue après la saisie, l'état de saisie (celui du contrôle
  // résolu ou du champ qui porte la valeur, `Error` l'emportant) et le refus
  // côté client (voir `clientRefusal`).
  function dateValue(payload) {
    if (!isUI5()) return null;
    let req;
    try { req = JSON.parse(payload) || {}; } catch (e) { req = {}; }
    const c = byId(req.id);
    if (!c) return { error: 'not_found' };
    const owner = dateOwner(c);
    const value = modelIso(owner, dateBinding(owner));
    const states = [];
    [c, owner].forEach((x) => {
      try { if (x && typeof x.getValueState === 'function') states.push(String(x.getValueState() || '')); } catch (e) {}
    });
    const state = states.indexOf('Error') >= 0 ? 'Error' : (states[0] || '');
    let ids = [];
    try { ids = [String(c.getId()), String(owner.getId())]; } catch (e) {}
    return { value: value, state: state, client_refusal: clientRefusal(ids) };
  }
