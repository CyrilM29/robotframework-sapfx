
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
  logo.src = '__AICABRA_ICON__';
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
