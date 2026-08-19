
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
  // --- multi-scénarios : un marqueur (commentaire RF) sépare les tests --------
  // « +test » insère le marqueur ; chaque export le convertit en un nouveau
  // *** Test Case *** (le bootstrap New Browser/New Page ne vit que dans le
  // premier : les suivants continuent la même session).
  var TEST_MARKER = /^# --- test: (.+)$/;
  function testMarkerLine(name) { return '# --- test: ' + cleanCell(name); }
  function splitScenarios() {
    var groups = [{ name: testName(), steps: [] }];
    steps.forEach(function (line) {
      var m = line.match(TEST_MARKER);
      if (m) { groups.push({ name: m[1], steps: [] }); return; }
      groups[groups.length - 1].steps.push(line);
    });
    return groups;
  }
  // Fichier .robot COMPLET et rejouable : en-tête Settings + ouverture navigateur + steps.
  function buildScript() {
    var s = '*** Settings ***\nLibrary    Browser\nLibrary    SapFioriLibrary\n\n';
    s += '*** Test Cases ***\n';
    splitScenarios().forEach(function (group, gi) {
      s += group.name + '\n';
      if (gi === 0) {
        s += '    New Browser    chromium    headless=False\n';
        s += '    New Page    ' + startUrl() + '\n';
      }
      group.steps.forEach(function (st) { s += '    ' + st + '\n'; });
      s += '\n';
    });
    s = s.replace(/\n\n$/, '\n');
    if (needsUi5Ready()) s += '\n' + UI5_READY_KEYWORD;
    return s;
  }
  // --- export resource-first : la paire .resource + .robot sans localisateur ---
  // (convention n°1 du projet : les tests parlent métier, les localisateurs
  // vivent dans la couche resources, celle que sap-healer sait réparer).
  function slugFromArgs(argCells, fallback) {
    var text = null, id = null, tag = null, role = null, name = null, m;
    argCells.forEach(function (c) {
      if ((m = c.match(/^id=(.+)$/))) id = id || m[1];
      else if ((m = c.match(/^idSuffix=(.+)$/))) id = id || m[1];
      else if ((m = c.match(/^properties=\{'[^']+':\s*'([^']*)'\}$/))) text = text || m[1];
      else if ((m = c.match(/^text=(.+)$/))) text = text || m[1];
      else if ((m = c.match(/^name=(.+)$/))) name = name || m[1];
      else if ((m = c.match(/^tag=(.+)$/))) tag = tag || m[1];
      else if ((m = c.match(/^role=(.+)$/))) role = role || m[1];
      else if ((m = c.match(/^controlType=(.+)$/))) tag = tag || m[1];
      else if ((m = c.match(/^wnd\[/))) id = id || c;
    });
    var base = text || name || id || tag || role || fallback;
    base = String(base).replace(/[^0-9A-Za-z]+/g, '_').replace(/^_+|_+$/g, '')
      .toUpperCase().slice(0, 28);
    return base || fallback;
  }
  // keyword -> comment retrouver localisateur/valeur dans la ligne enregistrée.
  var RF_WRAPPERS = {
    'Click Ui5 Control':  { verb: 'Cliquer', locFrom: 1 },
    'Click Sid':          { verb: 'Cliquer', locFrom: 1 },
    'Click Wc Control':   { verb: 'Cliquer', locFrom: 1 },
    'Click Dom Element':  { verb: 'Cliquer', locFrom: 1 },
    'Fill Ui5 Input':     { verb: 'Saisir', locFrom: 2, valueAt: 1 },
    'Fill Wc Input':      { verb: 'Saisir', locFrom: 2, valueAt: 1 },
    'Fill Dom Input':     { verb: 'Saisir', locFrom: 2, valueAt: 1 },
    'Fill Sid Input':     { verb: 'Saisir', locFrom: 1, locTo: 2, valueAt: 2 },
    'Ui5 Control Should Be Visible': { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Wc Control Should Be Visible':  { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Dom Element Should Be Visible': { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Sid Should Be Visible':         { verb: 'V\u00e9rifier Visible', locFrom: 1 },
    'Ui5 Text Should Be': { verb: 'V\u00e9rifier Texte', locFrom: 2, valueAt: 1 }
  };
  // Sépare les cellules d'action du commentaire de fin de ligne, et extrait
  // l'indice de repli xpath (posé par withXpathHint à l'enregistrement).
  function splitStepCells(line) {
    var raw = line.split('    ');
    var at = raw.length;
    for (var i = 0; i < raw.length; i++) {
      if (raw[i].charAt(0) === '#') { at = i; break; }
    }
    var comment = raw.slice(at).join('    ');
    var m = comment.match(/^# xpath: (.+)$/);
    return { cells: raw.slice(0, at), xpath: m ? m[1] : null };
  }
  function buildResourceFirst() {
    var kws = {}, order = [], counter = 0;
    function wrapLine(line) {
      var parsed = splitStepCells(line);
      var cells = parsed.cells;
      var spec = RF_WRAPPERS[cells[0]];
      if (!spec || !cells.length) return line;
      counter++;
      var locCells = spec.locTo ? cells.slice(spec.locFrom, spec.locTo)
                                : cells.slice(spec.locFrom);
      var value = (spec.valueAt !== undefined) ? cells[spec.valueAt] : null;
      var body;
      var healable = parsed.xpath &&
        (cells[0] === 'Click Ui5 Control' || cells[0] === 'Fill Ui5 Input');
      if (healable) {
        // Le step naît AUTO-RÉPARABLE : sélecteur primaire d'abord, repli xpath
        // journalisé par la chaîne de fallback de la bibliothèque sinon.
        var resolveLine = '    ${cible}=    Resolve Ui5 With Fallback    xpath=' +
          parsed.xpath + '    ' + locCells.join('    ');
        // Saisie : on descend dans l'<input>/<textarea> INTERNE, comme le fait
        // Fill Ui5 Input : un champ UI5 composite (sap.m.Input, SearchField…)
        // a une <div> pour racine, que Fill Text ne peut pas remplir.
        // (Attrapé par le run live de la paire exportée contre Fiori Elements.)
        var action = (cells[0] === 'Click Ui5 Control')
          ? '    Click    ${cible}'
          : '    Fill Text    ${cible} >> css=input, textarea    ${valeur}';
        body = ((spec.valueAt !== undefined) ? '    [Arguments]    ${valeur}\n' : '') +
          resolveLine + '\n' + action;
      } else {
        var bodyCells = cells.slice();
        if (spec.valueAt !== undefined) bodyCells[spec.valueAt] = '${valeur}';
        body = ((spec.valueAt !== undefined) ? '    [Arguments]    ${valeur}\n' : '') +
          '    ' + bodyCells.join('    ');
      }
      var kwName = spec.verb + ' ' + slugFromArgs(locCells, 'CIBLE_' + counter);
      if (kws[kwName] !== undefined && kws[kwName] !== body) kwName += ' ' + counter;
      if (kws[kwName] === undefined) { kws[kwName] = body; order.push(kwName); }
      return kwName + (value !== null ? '    ' + value : '');
    }
    // Paire d'assertion texte (menu clic droit) : `${texte} =    Get Wc/Dom
    // Text    <loc>` suivi de `Should Be Equal    ${texte}    <attendu>`,
    // enveloppée en UN keyword métier, sinon les localisateurs de la paire
    // resteraient dans la suite (convention n°1).
    function textAssertPair(line, nextLine) {
      var m = line.match(/^\$\{([^}]+)\} =    (Get Wc Text|Get Dom Text)    (.+)$/);
      if (!m || !nextLine) return null;
      var nxt = nextLine.split('    ');
      if (nxt[0] !== 'Should Be Equal' || nxt[1] !== '${' + m[1] + '}' || nxt.length < 3) return null;
      return { getter: m[2], locCells: m[3].split('    '), expected: nxt.slice(2).join('    ') };
    }
    function wrapTextAssert(pair) {
      counter++;
      var kwName = 'V\u00e9rifier Texte ' + slugFromArgs(pair.locCells, 'CIBLE_' + counter);
      var body = '    [Arguments]    ${valeur_attendue}\n' +
        '    ${texte}=    ' + pair.getter + '    ' + pair.locCells.join('    ') + '\n' +
        '    Should Be Equal    ${texte}    ${valeur_attendue}';
      if (kws[kwName] !== undefined && kws[kwName] !== body) kwName += ' ' + counter;
      if (kws[kwName] === undefined) { kws[kwName] = body; order.push(kwName); }
      return kwName + '    ' + pair.expected;
    }
    var robot = '*** Settings ***\nLibrary    Browser\nLibrary    SapFioriLibrary\n' +
      'Resource    recorded_keywords.resource\n\n';
    robot += '*** Test Cases ***\n';
    splitScenarios().forEach(function (group, gi) {
      robot += group.name + '\n';
      if (gi === 0) {
        robot += '    New Browser    chromium    headless=False\n';
        robot += '    New Page    ' + startUrl() + '\n';
      }
      for (var si = 0; si < group.steps.length; si++) {
        var pair = textAssertPair(group.steps[si], group.steps[si + 1]);
        if (pair) {
          robot += '    ' + wrapTextAssert(pair) + '\n';
          si++;                          // consomme le Should Be Equal apparié
        } else {
          robot += '    ' + wrapLine(group.steps[si]) + '\n';
        }
      }
      robot += '\n';
    });
    robot = robot.replace(/\n\n$/, '\n');
    var resource = '*** Settings ***\nLibrary    Browser\nLibrary    SapFioriLibrary\n\n';
    resource += '*** Keywords ***\n';
    order.forEach(function (n) { resource += n + '\n' + kws[n] + '\n\n'; });
    if (needsUi5Ready()) resource += UI5_READY_KEYWORD;
    return { resource: resource, robot: robot };
  }
  // --- export spec : plan Markdown au format specs/ (brouillon pour les agents) ---
  function mdCode(t) {
    // Code span Markdown littéral quel que soit le contenu (règle CommonMark) :
    // clôture plus longue que toute série de backticks interne, bourrage d'un
    // espace si le contenu commence/finit par un backtick. Une valeur saisie
    // '*LH*' (joker SAP) rendrait « LH » en italique hors code span.
    t = String(t);
    var longest = 0;
    (t.match(/`+/g) || []).forEach(function (r) { if (r.length > longest) longest = r.length; });
    var fence = new Array(longest + 2).join('`');
    var pad = (!t || t.charAt(0) === '`' || t.charAt(t.length - 1) === '`') ? ' ' : '';
    return fence + pad + t + pad + fence;
  }
  function humanizeWebStep(line, fmt) {
    fmt = fmt || mdCode;                 // spec = code span Markdown ; rapport = guillemets
    // Le commentaire de fin de ligne (indice de repli xpath, avertissement de
    // sélecteur non discriminant) n'est PAS un argument : sans ce retrait il
    // entrait dans le libellé humain de la phrase générée.
    var cells = splitStepCells(line).cells;
    var kw = cells[0];
    function target(from, to) {
      return fmt(slugFromArgs(to ? cells.slice(from, to) : cells.slice(from), 'cible').toLowerCase());
    }
    if (kw === 'Click Ui5 Control' || kw === 'Click Wc Control' ||
        kw === 'Click Dom Element' || kw === 'Click Sid') return 'Cliquer ' + target(1);
    if (kw === 'Fill Ui5 Input' || kw === 'Fill Wc Input' || kw === 'Fill Dom Input')
      return 'Saisir ' + fmt(rfUnescape(cells[1])) + ' dans ' + target(2);
    if (kw === 'Fill Sid Input')
      return 'Saisir ' + fmt(rfUnescape(cells[2])) + ' dans ' + target(1, 2);
    if (kw === 'Ui5 Text Should Be')
      return 'V\u00e9rifier que ' + target(2) + ' affiche ' + fmt(rfUnescape(cells[1]));
    if (kw.indexOf('Should Be Visible') !== -1)
      return 'V\u00e9rifier la pr\u00e9sence de ' + target(1);
    if (kw === 'Wait For Load State' || kw === 'Wait For UI5 Ready')
      return 'Attendre la fin du chargement';
    if (kw === 'Keyboard Key') return 'Valider (Entr\u00e9e)';
    return null;                         // étape inconnue : l'appelant décide (contrat specs/)
  }
  function buildSpec() {
    var md = '# ' + testName() + '\n\n';
    md += '> **Brouillon g\u00e9n\u00e9r\u00e9 par le recorder web** : \u00e0 retravailler\n';
    md += '> (r\u00e9sultats attendus, donn\u00e9es) avant passage au sap-generator.\n\n';
    md += '- **Canal** : Fiori (web)\n';
    md += '- **Syst\u00e8me / URL** : ' + startUrl() + '\n';
    md += '- **Pr\u00e9conditions** : application accessible.\n\n';
    md += '## Donn\u00e9es observ\u00e9es\n\n- Valeurs saisies pendant l\'enregistrement : voir les \u00e9tapes.\n\n';
    md += '## Sc\u00e9narios\n\n';
    var vigilance = [];
    splitScenarios().forEach(function (group, gi) {
      md += '### ' + (gi + 1) + '. ' + group.name + '\n- **\u00c9tapes** :\n';
      group.steps.forEach(function (line, i) {
        var human = humanizeWebStep(line);
        var cells = line.split('    ');
        var hasLocator = false;
        for (var j = 1; j < cells.length; j++) {
          if (/^(controlType=|properties=|id=|idSuffix=|tag=|css=|role=|name=|text=|wnd\[)/.test(cells[j])) {
            hasLocator = true;
            vigilance.push('- ' + mdCode(line) + ' (sc\u00e9nario ' + (gi + 1) + ', \u00e9tape ' + (i + 1) + ')');
            break;
          }
        }
        if (human === null) {
          // Étape inconnue : la ligne exacte ne va dans les étapes QUE si elle
          // ne porte aucun localisateur (contrat specs/ : pas d'id dans les
          // étapes) ; sinon elle vit en « Points de vigilance », déjà relevée.
          human = hasLocator
            ? '\u00c9tape technique \u00e0 traduire (ligne exacte en \u00ab Points de vigilance \u00bb)'
            : '\u00c9tape brute \u00e0 traduire : ' + mdCode(line);
        }
        md += '  ' + (i + 1) + '. ' + human + '\n';
      });
      md += '- **R\u00e9sultat attendu** : \u00e0 compl\u00e9ter (assertions ind\u00e9pendantes de la locale).\n';
      md += '- **Keywords m\u00e9tier manquants** : \u00e0 cr\u00e9er par le sap-generator.\n\n';
    });
    md += '## Points de vigilance\n\n';
    md += vigilance.length
      ? 'Localisateurs relev\u00e9s (notes factuelles pour le g\u00e9n\u00e9rateur) :\n\n' + vigilance.join('\n') + '\n'
      : '- (aucun localisateur relev\u00e9)\n';
    return md;
  }
  // --- export ISTQB : plan de test + cas de test, humain ET rejouable --------
  // Miroir web de steps_to_istqb (recorder desktop) : UN document Markdown,
  // sections plan (objectif, préconditions, critères), un cas de test PAR
  // scénario (+test) avec tableau Action / Données / Résultat attendu, et un
  // bloc replay YAML aux actions normalisées (fill/click/press_key/assert_*),
  // indépendant du framework d'exécution : cible en langage humain d'abord, le
  // localisateur relevé (et son repli xpath posé à l'enregistrement) en hint.
  function yq(t) { return "'" + String(t).replace(/'/g, "''") + "'"; }
  function mdCell(t) { return String(t).replace(/\|/g, '\\|'); }
  function istqbSlug(t) {
    // accents translittérés (NFD + diacritiques retirés) : « Scénario
    // enregistré » -> scenario-enregistre, jamais sc-nario-enregistr.
    var s = String(t);
    try { s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, ''); } catch (e) {}
    s = s.replace(/[^0-9A-Za-z]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
    return s || 'enregistrement';
  }
  var ISTQB_GENERIC_EXPECTED = 'L\u2019action s\u2019ex\u00e9cute sans erreur (\u00e0 pr\u00e9ciser)';
  var ISTQB_EXPECTED = {
    fill: 'La valeur est accept\u00e9e',
    press_key: 'L\u2019\u00e9cran suivant s\u2019affiche (\u00e0 pr\u00e9ciser)',
    wait: 'Le chargement se termine',
    assert_text: 'Texte conforme (assertion ind\u00e9pendante de la locale)',
    assert_present: 'L\u2019\u00e9l\u00e9ment est pr\u00e9sent',
    raw: '\u00e0 pr\u00e9ciser'
  };
  function istqbStep(line) {
    var cells = line.split('    ');
    var ci = -1;
    for (var i = 0; i < cells.length; i++) {
      if (cells[i].charAt(0) === '#') { ci = i; break; }
    }
    var comment = ci >= 0 ? cells.slice(ci).join('    ') : '';
    if (ci >= 0) cells = cells.slice(0, ci);
    cells = cells.filter(function (c) { return c !== ''; });
    var kw = cells[0] || '';
    function target(from, to) {
      return slugFromArgs(to ? cells.slice(from, to) : cells.slice(from), 'cible').toLowerCase();
    }
    function sel(from, to) {
      return (to ? cells.slice(from, to) : cells.slice(from)).join('    ');
    }
    function hintFor(engine, loc) {
      var h = { engine: engine, locator: loc };
      var m = comment.match(/^#\s*xpath:\s*(.+)$/);
      if (m) h.fallback = m[1];
      return h;
    }
    if (kw === 'Click Ui5 Control') return { action: 'click', target: target(1), hint: hintFor('ui5-role', sel(1)) };
    if (kw === 'Click Wc Control') return { action: 'click', target: target(1), hint: hintFor('wc', sel(1)) };
    if (kw === 'Click Dom Element') return { action: 'click', target: target(1), hint: hintFor('dom', sel(1)) };
    if (kw === 'Click Sid') return { action: 'click', target: target(1), hint: hintFor('sid', sel(1)) };
    if (kw === 'Fill Ui5 Input' || kw === 'Fill Wc Input' || kw === 'Fill Dom Input')
      return { action: 'fill', target: 'champ ' + target(2), value: rfUnescape(cells[1]),
               hint: hintFor(kw === 'Fill Ui5 Input' ? 'ui5-role' : (kw === 'Fill Wc Input' ? 'wc' : 'dom'), sel(2)) };
    if (kw === 'Fill Sid Input')
      return { action: 'fill', target: 'champ ' + target(1, 2), value: rfUnescape(cells[2]),
               hint: hintFor('sid', sel(1, 2)) };
    if (kw === 'Ui5 Text Should Be')
      return { action: 'assert_text', target: target(2), expected: rfUnescape(cells[1]),
               hint: hintFor('ui5-role', sel(2)) };
    if (/Should Be Visible$/.test(kw)) {
      var eng = kw.indexOf('Ui5') === 0 ? 'ui5-role'
        : (kw.indexOf('Wc') === 0 ? 'wc' : (kw.indexOf('Dom') === 0 ? 'dom' : 'sid'));
      return { action: 'assert_present', target: target(1), hint: hintFor(eng, sel(1)) };
    }
    if (kw === 'Wait For UI5 Ready' || kw === 'Wait For Load State') return { action: 'wait' };
    if (kw === 'Keyboard Key') return { action: 'press_key', value: cells[cells.length - 1] };
    return null;
  }
  function istqbYaml(st) {
    var out = ['  - action: ' + st.action];
    ['target', 'value', 'expected', 'line', 'note'].forEach(function (k) {
      if (st[k] !== undefined && st[k] !== null) out.push('    ' + k + ': ' + yq(st[k]));
    });
    if (st.hint) {
      out.push('    hint: {engine: ' + yq(st.hint.engine) + ', locator: ' + yq(st.hint.locator) + '}');
      if (st.hint.fallback)
        out.push('    fallback: {engine: ' + yq('ui5-xpath') + ', locator: ' + yq(st.hint.fallback) + '}');
    }
    return out;
  }
  function buildIstqb() {
    var groups = splitScenarios();
    var values = [];
    var parsed = groups.map(function (group) {
      return group.steps.map(function (line) {
        var st = istqbStep(line);
        if (st === null) st = { action: 'raw', line: line,
                                note: '\u00e9tape non traduite : ligne Robot Framework exacte' };
        if (st.action === 'fill' && st.value) values.push(st.value);
        return st;
      });
    });
    var md = '# Plan de test ISTQB : ' + testName() + '\n\n';
    md += '> G\u00e9n\u00e9r\u00e9 par le recorder web depuis ' + startUrl() + '.\n';
    md += '> Document de conception de test (ISTQB / ISO 29119-3) : lisible par\n';
    md += '> un humain, rejouable par une IA via le bloc `replay` de chaque cas\n';
    md += '> de test, ind\u00e9pendant du framework d\u2019ex\u00e9cution. Les mentions\n';
    md += '> \u00ab \u00e0 compl\u00e9ter / \u00e0 pr\u00e9ciser \u00bb sont \u00e0 renseigner avant usage\n';
    md += '> formel (l\u2019agent sap-istqb peut r\u00e9diger ce document).\n\n';
    md += '- **Identifiant** : TP-' + istqbSlug(testName()) + '\n';
    md += '- **Canal** : Fiori (web)\n';
    md += '- **Syst\u00e8me / URL** : ' + startUrl() + '\n\n';
    md += '## 1. Objectif et p\u00e9rim\u00e8tre\n\n';
    md += '- **Objectif** : \u00e0 compl\u00e9ter (constat\u00e9 : d\u00e9roul\u00e9 enregistr\u00e9 ci-dessous).\n';
    md += '- **\u00c9l\u00e9ments \u00e0 tester** : \u00e0 compl\u00e9ter.\n';
    md += '- **Hors p\u00e9rim\u00e8tre** : \u00e0 compl\u00e9ter.\n\n';
    md += '## 2. Pr\u00e9conditions et donn\u00e9es de test\n\n';
    md += '- Application accessible \u00e0 ' + startUrl() + '.\n';
    md += '- Valeurs observ\u00e9es pendant l\u2019enregistrement : ' +
      (values.length ? values.map(mdCode).join(', ') : 'aucune') + '.\n\n';
    md += '## 3. Crit\u00e8res d\u2019entr\u00e9e / de sortie\n\n';
    md += '- **Entr\u00e9e** : application accessible, pr\u00e9conditions satisfaites.\n';
    md += '- **Sortie** : tous les cas de test ex\u00e9cut\u00e9s, r\u00e9sultats attendus confirm\u00e9s.\n\n';
    md += '## 4. Cas de test\n\n';
    var trace = [];
    groups.forEach(function (group, gi) {
      var tcId = 'TC-' + (gi + 1 < 10 ? '0' : '') + (gi + 1);
      md += '### ' + tcId + ' : ' + group.name + '\n\n- **Priorit\u00e9** : \u00e0 compl\u00e9ter\n\n';
      md += '| # | Action | Donn\u00e9es | R\u00e9sultat attendu |\n';
      md += '|---|--------|---------|------------------|\n';
      parsed[gi].forEach(function (st, i) {
        var human = st.action === 'raw'
          ? '\u00c9tape non traduite : ' + mdCode(st.line)
          : (humanizeWebStep(group.steps[i]) || st.action);
        var data = (st.action !== 'press_key' && st.value !== undefined) ? st.value
          : (st.action.indexOf('assert') === 0 && st.expected !== undefined ? st.expected : '');
        md += '| ' + (i + 1) + ' | ' + mdCell(human) + ' | ' +
          mdCell(data ? mdCode(data) : '') + ' | ' +
          mdCell(ISTQB_EXPECTED[st.action] || ISTQB_GENERIC_EXPECTED) + ' |\n';
      });
      md += '\n- **Postconditions** : \u00e0 compl\u00e9ter.\n\n';
      md += 'Bloc rejouable (actions normalis\u00e9es ; les `hint` sont les\n';
      md += 'localisateurs relev\u00e9s au moment de l\u2019enregistrement) :\n\n';
      md += '```yaml\ntest_case: ' + tcId + '\ntitle: ' + yq(group.name) + '\nchannel: web\nsteps:\n';
      parsed[gi].forEach(function (st) { md += istqbYaml(st).join('\n') + '\n'; });
      md += '```\n\n';
      trace.push('| ' + tcId + ' | sc\u00e9nario ' + (gi + 1) + ' de l\u2019enregistrement, \u00e9tapes 1 \u00e0 ' +
        parsed[gi].length + ' | \u00e0 relier |');
    });
    md += '## 5. Tra\u00e7abilit\u00e9\n\n';
    md += '| Cas de test | Source | Exigence / spec |\n|---|---|---|\n' + trace.join('\n') + '\n\n';
    md += '## 6. Risques et points de vigilance\n\n';
    md += '- Les localisateurs des `hint` datent de l\u2019enregistrement : les\n';
    md += '  re-v\u00e9rifier en cas de d\u00e9rive de la page (cha\u00eene de fallback).\n';
    md += '- Ne jamais rejouer avec des attentes fixes (time.sleep) : attendre la\n';
    md += '  fin du chargement (Wait For UI5 Ready / Wait For Load State).\n';
    return md;
  }
  function exportIstqb() {
    var md = buildIstqb();
    download(md, 'recorded.istqb.md');
    copy(md, btnExport);
  }
  // --- sélection multi-formats du menu export --------------------------------
  // Chaque ligne du menu porte une CASE À COCHER (cocher plusieurs formats,
  // puis « exporter la sélection » : téléchargements espacés pour que Chrome
  // affiche son invite multi-téléchargements au lieu de bloquer en silence) ;
  // cliquer le LIBELLÉ exporte toujours ce seul format immédiatement (le
  // comportement historique, sur lequel s'appuient les smokes). La sélection
  // survit à la navigation (sessionStorage, comme les steps).
  var EXPSEL_KEY = '__ui5RecorderExportSel';
  var EXPORT_FORMATS = [
    { key: 'robot', label: '.robot complet', run: exportScript, files: 1 },
    { key: 'resource', label: 'resource-first (.resource + .robot)', run: exportResourceFirst, files: 2 },
    { key: 'spec', label: 'plan specs/ (.spec.md)', run: exportSpec, files: 1 },
    { key: 'istqb', label: 'plan ISTQB (.istqb.md)', run: exportIstqb, files: 1 },
    { key: 'report', label: 'rapport HTML (.html)', run: exportReport, files: 1 }
  ];
  var exportSel = (function () {
    try { return JSON.parse(sessionStorage.getItem(EXPSEL_KEY)) || {}; }
    catch (e) { return {}; }
  })();
  function saveExportSel() {
    try { sessionStorage.setItem(EXPSEL_KEY, JSON.stringify(exportSel)); }
    catch (e) { warnStorage(e); }
  }
  function exportSelected() {
    var chosen = EXPORT_FORMATS.filter(function (f) { return exportSel[f.key]; });
    if (!chosen.length) {
      hint.textContent = 'Aucun format coch\u00e9 : cocher des cases du menu export, ' +
        'puis \u00ab exporter la s\u00e9lection \u00bb.';
      return;
    }
    var delay = 0;
    chosen.forEach(function (f) {
      if (delay) setTimeout(f.run, delay); else f.run();
      delay += 400 * f.files;
    });
    if (chosen.length > 1) {
      hint.textContent = 'Export de ' + chosen.length + ' formats : autoriser les ' +
        't\u00e9l\u00e9chargements multiples si le navigateur le demande.';
    }
  }
  function exportScript() {
    var body = buildScript();
    download(body, 'recorded.robot');   // télécharge un .robot complet
    copy(body, btnExport);              // + copie dans le presse-papiers
  }
  function exportResourceFirst() {
    var pair = buildResourceFirst();
    download(pair.resource, 'recorded_keywords.resource');
    // La protection « téléchargements multiples » de Chrome vise les downloads
    // d'une même tâche : espacer le second donne à l'utilisateur une invite
    // visible au lieu d'un .robot silencieusement manquant.
    setTimeout(function () { download(pair.robot, 'recorded.robot'); }, 350);
    copy(pair.robot, btnExport);
    hint.textContent = 'Export de 2 fichiers (.resource + .robot) : autoriser ' +
      'les t\u00e9l\u00e9chargements multiples si le navigateur le demande.';
  }
  function exportSpec() {
    var md = buildSpec();
    download(md, 'recorded.spec.md');
    copy(md, btnExport);
  }

  // --- export rapport HTML : la documentation humaine d'un enregistrement ----
  // Concept observé chez RoboSAPiens (saveHtmlReport, NOTICE) : page HTML
  // AUTO-CONTENUE (CSS minimal inline, aucune dépendance) documentant le
  // déroulé : phrase métier + ligne RF exacte par step, un chapitre par
  // scénario. Documentation, jamais un test : l'enregistrement brut fait foi.
  // Pas de capture d'écran depuis la page (une page ne se photographie pas
  // elle-même) : le log Robot et la démo vidéo couvrent ce besoin.
  function escapeHtml(t) {
    return String(t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function buildReport() {
    var css = 'body{font-family:system-ui,sans-serif;margin:2em auto;max-width:62em;' +
      'padding:0 1em;color:#1d2d3e}h1{font-size:1.5em;border-bottom:2px solid #0a6ed1;' +
      'padding-bottom:.3em}h2{font-size:1.15em;margin-top:1.4em}p.meta{color:#556b82;' +
      'font-size:.9em}ol.steps{padding-left:1.6em}ol.steps>li{margin:.9em 0}' +
      'p.human{margin:0 0 .15em}p.raw{margin:0}p.raw code{background:#f5f6f7;' +
      'border:1px solid #d9d9d9;border-radius:3px;padding:1px 5px;font-size:.85em;' +
      'color:#495a6e}';
    // Le rapport parle HTML, pas Markdown : les valeurs passent entre
    // guillemets français (la phrase entière est ensuite échappée HTML).
    var quote = function (t) { return '\u00ab\u202f' + String(t) + '\u202f\u00bb'; };
    var page = '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n' +
      '<title>' + escapeHtml(testName()) + '</title>\n<style>' + css + '</style>\n' +
      '</head>\n<body>\n<h1>' + escapeHtml(testName()) + '</h1>\n' +
      '<p class="meta">Rapport g\u00e9n\u00e9r\u00e9 par le recorder web : ' +
      escapeHtml(startUrl()) + '. Documentation du d\u00e9roul\u00e9 ' +
      'enregistr\u00e9 : l\u2019enregistrement brut fait foi, ce rapport ' +
      'n\u2019est pas un test.</p>\n';
    splitScenarios().forEach(function (group, gi) {
      page += '<h2>' + (gi + 1) + '. ' + escapeHtml(group.name) + '</h2>\n<ol class="steps">\n';
      group.steps.forEach(function (line) {
        var human = humanizeWebStep(line, quote);
        page += '<li>' +
          (human ? '<p class="human">' + escapeHtml(human) + '</p>' : '') +
          '<p class="raw"><code>' + escapeHtml(line) + '</code></p></li>\n';
      });
      page += '</ol>\n';
    });
    page += '</body>\n</html>\n';
    return page;
  }
  function exportReport() {
    var page = buildReport();
    download(page, 'recorded_report.html');
    copy(page, btnExport);
  }

  // --- replay in-page (« play ») : rejouer le déroulé dans la page ------------
  // Validation instantanée avant export, sans lancer robot : chaque step est
  // résolu par les MÊMES moteurs que la bibliothèque, surligné, exécuté ; le
  // premier échec arrête le replay et marque la ligne. Les steps UI5 essaient
  // leur repli xpath (l'indice posé à l'enregistrement) quand le sélecteur
  // primaire ne résout plus. Best-effort assumé : une navigation pleine page
  // recharge le recorder (les steps survivent via sessionStorage).
  var replaying = false;
  var replayState = { current: -1, failed: -1, message: '' };
  function parseUi5Sel(cells) {
    var sel = {}, m;
    cells.forEach(function (c) {
      if ((m = c.match(/^id=(.+)$/))) sel.id = m[1];
      else if ((m = c.match(/^idSuffix=(.+)$/))) sel.idSuffix = m[1];
      else if ((m = c.match(/^controlType=(.+)$/))) sel.controlType = m[1];
      else if ((m = c.match(/^properties=\{'([^']+)':\s*'([^']*)'\}$/))) {
        sel.properties = {}; sel.properties[m[1]] = m[2];
      }
    });
    return sel;
  }
  function parseWcSel(cells) {
    var sel = {}, m;
    cells.forEach(function (c) {
      if ((m = c.match(/^tag=(.+)$/))) sel.tag = m[1];
      else if ((m = c.match(/^text=(.+)$/))) sel.text = m[1];
    });
    return sel;
  }
  function parseDomSel(cells) {
    var sel = {}, m;
    cells.forEach(function (c) {
      if ((m = c.match(/^role=(.+)$/))) sel.role = m[1];
      else if ((m = c.match(/^name=(.+)$/))) sel.name = m[1];
      else if ((m = c.match(/^css=(.+)$/))) sel.css = m[1];
    });
    return sel;
  }
  function findUi5(cells, xpath) {
    try {
      var ids = window.__SAPFX.resolveByRole(JSON.stringify(parseUi5Sel(cells)));
      if (ids && ids.length) return document.getElementById(ids[0]);
    } catch (e) {}
    if (xpath) {
      try {
        var ids2 = window.__SAPFX.resolveByXPath(xpath);
        if (ids2 && ids2.length) return document.getElementById(ids2[0]);
      } catch (e) {}
    }
    return null;
  }
  function findBySid(sid) {
    var nodes = document.querySelectorAll('[lsdata]');
    for (var i = 0; i < nodes.length; i++) {
      var ls = nodes[i].getAttribute('lsdata') || '';
      if (ls.indexOf('"SID":"' + sid + '"') !== -1 ||
          ls.indexOf("SID:'" + sid + "'") !== -1) return nodes[i];
    }
    return null;
  }
  function findByPaths(paths) {
    if (!paths || !paths.length) return null;
    try { return document.querySelector(paths[0]); } catch (e) { return null; }
  }
  function findWc(cells) {
    try { return findByPaths(window.__SAPFX.resolveByWc(JSON.stringify(parseWcSel(cells)))); }
    catch (e) { return null; }
  }
  function findDom(cells) {
    try { return findByPaths(window.__SAPFX.resolveByDom(JSON.stringify(parseDomSel(cells)))); }
    catch (e) { return null; }
  }
  function fireClick(el) {
    ['mousedown', 'mouseup', 'click'].forEach(function (t) {
      el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true }));
    });
  }
  // Affectation via le setter NATIF du prototype : React trace la dernière
  // valeur posée par l'accesseur natif et déduplique les événements `input`
  // dont la valeur « n'a pas changé » : un simple t.value = x est exactement
  // ce qui est dédupliqué, donc les fills rejoués no-opaient sur les zones
  // React (la cible même du moteur dom).
  function setNativeValue(el, value) {
    var proto = null;
    try {
      if (window.HTMLInputElement && el instanceof HTMLInputElement) proto = HTMLInputElement.prototype;
      else if (window.HTMLTextAreaElement && el instanceof HTMLTextAreaElement) proto = HTMLTextAreaElement.prototype;
    } catch (e) {}
    if (proto) {
      try {
        var desc = Object.getOwnPropertyDescriptor(proto, 'value');
        if (desc && desc.set) { desc.set.call(el, value); return; }
      } catch (e) {}
    }
    el.value = value;
  }
  function fireFill(el, value) {
    var t = el;
    if (el.matches && !el.matches('input, textarea') && el.querySelector) {
      t = el.querySelector('input, textarea') || el;
    }
    try { if (t.focus) t.focus(); } catch (e) {}
    setNativeValue(t, value);
    t.dispatchEvent(new Event('input', { bubbles: true }));
    t.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function visibleEl(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return !!(r.width || r.height);
  }
  function elText(el) {
    return cleanCell(('value' in el && el.value) ? el.value : el.textContent);
  }
  function highlightEl(el) {
    try {
      var r = el.getBoundingClientRect();
      box.style.left = r.left + 'px'; box.style.top = r.top + 'px';
      box.style.width = r.width + 'px'; box.style.height = r.height + 'px';
      box.style.display = 'block';
      setTimeout(function () { box.style.display = 'none'; }, 300);
    } catch (e) {}
  }
  function waitUi5Idle(timeout, ok, ko) {
    var end = Date.now() + timeout;
    (function poll() {
      var busy = document.querySelectorAll(
        '.sapUiLocalBusyIndicator, .sapMBusyDialog, #sapUiBusyIndicator');
      var shown = false;
      for (var i = 0; i < busy.length; i++) {
        if (busy[i].offsetParent !== null) { shown = true; break; }
      }
      if (window.__SAPFX.isUI5() && !shown) return ok();
      if (Date.now() > end) return ko();
      setTimeout(poll, 200);
    })();
  }
  function executeStep(line, vars, done) {
    var parsed = splitStepCells(line);
    var cells = parsed.cells;
    function fail(msg) { done({ ok: false, message: msg }); }
    function okDone() { done({ ok: true }); }
    if (!cells.length || line.charAt(0) === '#') return done({ ok: true, skipped: true });
    var kw = cells[0], el;
    try {
      if (kw === 'Click Ui5 Control' || kw === 'Ui5 Control Should Be Visible') {
        el = findUi5(cells.slice(1), parsed.xpath);
        if (!el) return fail('contr\u00f4le UI5 introuvable');
        highlightEl(el);
        if (kw === 'Click Ui5 Control') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Ui5 Input' || kw === 'Ui5 Text Should Be') {
        el = findUi5(cells.slice(2), parsed.xpath);
        if (!el) return fail('contr\u00f4le UI5 introuvable');
        highlightEl(el);
        if (kw === 'Fill Ui5 Input') { fireFill(el, rfUnescape(cells[1])); return okDone(); }
        var wantText = rfUnescape(cells[1]);
        return (elText(el).indexOf(wantText) !== -1) ? okDone()
          : fail("texte '" + elText(el).slice(0, 40) + "' \u2260 '" + wantText + "'");
      }
      if (kw === 'Click Sid' || kw === 'Sid Should Be Visible') {
        el = findBySid(cells[1]);
        if (!el) return fail('SID introuvable');
        highlightEl(el);
        if (kw === 'Click Sid') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Sid Input') {
        el = findBySid(cells[1]);
        if (!el) return fail('SID introuvable');
        highlightEl(el); fireFill(el, rfUnescape(cells[2])); return okDone();
      }
      if (kw === 'Click Wc Control' || kw === 'Wc Control Should Be Visible') {
        el = findWc(cells.slice(1));
        if (!el) return fail('web component introuvable');
        highlightEl(el);
        if (kw === 'Click Wc Control') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Wc Input') {
        el = findWc(cells.slice(2));
        if (!el) return fail('web component introuvable');
        highlightEl(el); fireFill(el, rfUnescape(cells[1])); return okDone();
      }
      if (kw === 'Click Dom Element' || kw === 'Dom Element Should Be Visible') {
        el = findDom(cells.slice(1));
        if (!el) return fail('\u00e9l\u00e9ment dom introuvable');
        highlightEl(el);
        if (kw === 'Click Dom Element') { fireClick(el); return okDone(); }
        return visibleEl(el) ? okDone() : fail('non visible');
      }
      if (kw === 'Fill Dom Input') {
        el = findDom(cells.slice(2));
        if (!el) return fail('\u00e9l\u00e9ment dom introuvable');
        highlightEl(el); fireFill(el, rfUnescape(cells[1])); return okDone();
      }
      if (/^\$\{[^}]+\} =$/.test(kw)) {           // ${texte} =    Get Wc/Dom Text    ...
        var varName = kw.slice(2, kw.indexOf('}'));
        el = (cells[1] === 'Get Wc Text') ? findWc(cells.slice(2)) : findDom(cells.slice(2));
        if (!el) return fail('cible introuvable pour ' + cells[1]);
        vars[varName] = elText(el);
        return okDone();
      }
      if (kw === 'Should Be Equal') {
        var left = cells[1], m2 = left.match(/^\$\{([^}]+)\}$/);
        if (m2) left = vars[m2[1]];
        var want = rfUnescape(cells[2]);
        return (String(left) === want) ? okDone()
          : fail("'" + String(left).slice(0, 40) + "' \u2260 '" + want + "'");
      }
      if (kw === 'Keyboard Key') {
        var target = document.activeElement || document.body;
        ['keydown', 'keyup'].forEach(function (t) {
          target.dispatchEvent(new KeyboardEvent(t, { key: cells[2], bubbles: true }));
        });
        return okDone();
      }
      if (kw === 'Wait For Load State') { setTimeout(okDone, 300); return; }
      if (kw === 'Wait For UI5 Ready') {
        waitUi5Idle(5000, okDone, function () { fail('runtime UI5 pas inactif'); });
        return;
      }
    } catch (e) {
      return fail(String(e && e.message || e));
    }
    console.warn('[UI5 Recorder] replay : step non rejouable in-page, saut\u00e9 :', line);
    return done({ ok: true, skipped: true });
  }
  function playSteps() {
    if (replaying || !steps.length) return;
    replaying = true;
    replayState = { current: -1, failed: -1, message: '' };
    if (recording) setRecording(false);   // un replay ne se ré-enregistre jamais
    var vars = {};
    var i = 0;
    function finishOk() {
      replaying = false;
      replayState.current = -1;
      hint.textContent = 'Replay OK : ' + steps.length + ' step(s).';
      render();
    }
    function next() {
      if (!replaying) return;             // annulé (Échap) ou recorder arrêté
      if (i >= steps.length) return finishOk();
      replayState.current = i;
      render();
      executeStep(steps[i], vars, function (res) {
        if (!replaying) return;           // annulé pendant le step
        if (!res.ok) {
          replaying = false;
          replayState.failed = i;
          replayState.message = res.message || '';
          hint.textContent = '\u2716 step ' + (i + 1) + ' : ' + replayState.message;
          render();
          return;
        }
        i++;
        setTimeout(next, 350);
      });
    }
    next();
  }
  function cancelReplay() {
    if (!replaying) return;
    replaying = false;
    replayState.current = -1;
    hint.textContent = 'Replay annul\u00e9.';
    render();
  }

  // --- import d'un .robot exporté : le cycle d'édition se referme -------------
  function parseRobotSuite(text) {
    var name = null, out = [], skipped = 0, inTests = false, sawTest = false;
    String(text).split(/\r?\n/).forEach(function (raw) {
      var line = raw.replace(/\s+$/, '');
      var trimmed = line.trim();
      if (/^\*\*\*/.test(trimmed)) {
        inTests = /test cases/i.test(trimmed);
        return;
      }
      if (!inTests || !trimmed) return;
      if (line.charAt(0) !== ' ' && line.charAt(0) !== '\t') {
        if (trimmed.charAt(0) === '#') return;       // commentaire d'en-tête
        if (!sawTest) { name = trimmed; sawTest = true; }
        else out.push(testMarkerLine(trimmed));      // test suivant -> marqueur
        return;
      }
      if (/^(New Browser|New Page|\[)/.test(trimmed)) {
        // Round-trip : le New Page importé restaure l'URL de départ (le
        // bootstrap reste re-généré à l'export, donc toujours compté ignoré).
        var mNP = trimmed.match(/^New Page\s{2,}(\S+)/);
        if (mNP) { try { sessionStorage.setItem(URL_KEY, mNP[1]); } catch (e) { warnStorage(e); } }
        skipped++; return;
      }
      out.push(trimmed);
    });
    return { name: name, steps: out, skipped: skipped };
  }
  function applyImportedText(text) {
    var parsed = parseRobotSuite(text);
    steps = parsed.steps;
    if (parsed.name) {
      nameInput.value = parsed.name;
      try { sessionStorage.setItem(NAME_KEY, parsed.name); } catch (e) { warnStorage(e); }
    }
    saveSteps(); render();
    hint.textContent = parsed.steps.length + ' step(s) import\u00e9(s)' +
      (parsed.skipped ? ' : ' + parsed.skipped + ' ligne(s) de bootstrap ignor\u00e9e(s)' : '') + '.';
  }
  function importRobot() {
    var inp = document.createElement('input');
    inp.type = 'file'; inp.accept = '.robot,.txt'; inp.style.display = 'none';
    inp.addEventListener('change', function () {
      var f = inp.files && inp.files[0];
      if (!f) return;
      var reader = new FileReader();
      reader.onload = function () { applyImportedText(reader.result); };
      reader.readAsText(f);
    });
    panel.appendChild(inp);
    inp.click();
    setTimeout(function () { inp.remove(); }, 60000);
  }
  function moveStep(i, d) {
    var j = i + d;
    if (j < 0 || j >= steps.length) return;
    var t = steps[i]; steps[i] = steps[j]; steps[j] = t;
    saveSteps(); render();
  }
  function removeStep(i) { steps.splice(i, 1); saveSteps(); render(); }
  function stepBtn(label, fn) {
    var b = document.createElement('button');
    b.textContent = label;
    b.style.cssText = 'margin-left:3px;border:1px solid #b3b3b3;background:#fff;cursor:pointer;' +
      'font:10px monospace;border-radius:3px;padding:0 4px;';
    b.addEventListener('click', fn);
    return b;
  }
  // Dans un launchpad (Work Zone/cFLP), le recorder tourne aussi dans l'iframe
  // de l'app : marquer le panneau pour distinguer shell et app embarquée.
  var frameTag = (window.top !== window.self) ? ' [iframe]' : '';
  // Édition in-place d'un step (double-clic) : Entrée valide, Échap annule.
  function startEditStep(i, row, txt) {
    if (replaying) return;
    var input = document.createElement('input');
    input.type = 'text';
    input.value = steps[i];
    input.style.cssText = 'flex:1;font:11px monospace;border:1px solid #0a6ed1;' +
      'border-radius:3px;padding:1px 4px;';
    row.replaceChild(input, txt);
    input.focus();
    input.select();
    var done = false;
    function commit() {
      if (done) return;
      done = true;
      var v = input.value.trim();
      if (v) steps[i] = v;
      saveSteps(); render();
    }
    input.addEventListener('keydown', function (e) {
      e.stopPropagation();
      if (e.key === 'Enter') commit();
      else if (e.key === 'Escape') { done = true; render(); }
    });
    input.addEventListener('blur', commit);
  }
  function renderSteps() {
    title.textContent = (recording ? 'Recording' : 'Steps') + ' : ' + steps.length + ' step(s)' + frameTag;
    list.textContent = '';
    steps.forEach(function (line, i) {
      var row = document.createElement('div');
      var bg = '';
      if (i === replayState.failed) bg = 'background:#fde8e8;';
      else if (i === replayState.current && replaying) bg = 'background:#eaf3fb;';
      else if (TEST_MARKER.test(line)) bg = 'background:#f4f0fa;';
      row.style.cssText = 'display:flex;align-items:center;gap:4px;padding:3px 4px;' +
        'border-bottom:1px solid #f0f0f0;' + bg;
      var txt = document.createElement('span');
      txt.style.cssText = 'flex:1;font:11px monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
      txt.textContent = (i + 1) + '. ' + line;
      txt.title = 'double-clic : \u00e9diter';
      txt.addEventListener('dblclick', function () { startEditStep(i, row, txt); });
      row.appendChild(txt);
      row.appendChild(stepBtn('\u2191', function () { moveStep(i, -1); }));
      row.appendChild(stepBtn('\u2193', function () { moveStep(i, 1); }));
      row.appendChild(stepBtn('\u2715', function () { removeStep(i); }));
      list.appendChild(row);
    });
  }
  function render() {
    if (recording || steps.length) { renderSteps(); return; }   // steps restaurés -> visibles
    title.textContent = 'UI5 Recorder : ' + captures.length + ' captured' + frameTag;
    list.textContent = '';
    captures.forEach(function (rec, i) {
      var row = document.createElement('div');
      row.style.cssText = 'padding:5px 4px;border-bottom:1px solid #f0f0f0;';
      var lab = document.createElement('div');
      lab.style.cssText = 'color:#0a6ed1;font:11px monospace;margin-bottom:3px;' +
        'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
      lab.textContent = (i + 1) + '. ' + rec.label;
      row.appendChild(lab);
      var bar = document.createElement('div');
      if (rec.cap) {
        bar.appendChild(mkBtn('role', roleLine(rec.cap)));
        if (xpathLine(rec.cap)) bar.appendChild(mkBtn('xpath', xpathLine(rec.cap)));
      }
      if (rec.sid) bar.appendChild(mkBtn('sid', 'Resolve Sid    ' + rec.sid));
      if (rec.wc) bar.appendChild(mkBtn('wc', 'Resolve Wc Control    ' + wcArgs(rec.wc)));
      if (rec.dom) bar.appendChild(mkBtn('dom', 'Resolve Dom Element    ' + domArgs(rec.dom)));
      bar.appendChild(mkBtn('all', allLines(rec)));
      row.appendChild(bar);
      list.appendChild(row);
    });
  }
  render();

  function inOurUI(node) {
    return !!(node && node.closest && node.closest('#__ui5SpyPanel'));
  }

  // --- menu flottant (assertions au clic droit, choix du format d'export) ----
  var menuEl = null;
  function closeMenus() { if (menuEl) { menuEl.remove(); menuEl = null; } }
  function showMenu(items, x, y) {
    closeMenus();
    menuEl = document.createElement('div');
    menuEl.style.cssText = 'position:fixed;z-index:2147483647;background:#fff;' +
      'border:1px solid #b3b3b3;border-radius:5px;box-shadow:0 4px 14px rgba(0,0,0,.25);' +
      'font:12px monospace;min-width:180px;overflow:hidden;';
    menuEl.style.left = Math.max(0, Math.min(x, window.innerWidth - 210)) + 'px';
    menuEl.style.top = Math.max(0, Math.min(y, window.innerHeight - items.length * 26 - 10)) + 'px';
    items.forEach(function (it) {
      var b = document.createElement('div');
      b.style.cssText = 'display:flex;align-items:center;cursor:pointer;color:#0a6ed1;';
      if (it.checkbox) {
        // zone case à cocher : toggle SANS fermer le menu (cocher plusieurs
        // formats d'affilée) ; le libellé reste l'action immédiate.
        var box = document.createElement('span');
        box.style.cssText = 'padding:5px 2px 5px 10px;';
        var paintBox = function () {
          box.textContent = it.checkbox.checked() ? '\u2611' : '\u2610';
        };
        paintBox();
        box.addEventListener('click', function (e) {
          e.preventDefault(); e.stopPropagation(); it.checkbox.toggle(); paintBox();
        });
        b.appendChild(box);
      }
      var lab = document.createElement('span');
      lab.textContent = it.label;
      lab.style.cssText = 'padding:5px 10px 5px ' + (it.checkbox ? '4px' : '10px') +
        ';flex:1;';
      b.appendChild(lab);
      b.addEventListener('mouseenter', function () { b.style.background = '#eaf3fb'; });
      b.addEventListener('mouseleave', function () { b.style.background = ''; });
      b.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation(); closeMenus(); it.run();
      });
      menuEl.appendChild(b);
    });
    document.documentElement.appendChild(menuEl);
  }
  // Choix d'assertions selon le moteur qui possède l'élément visé.
  function assertionItems(cap, sid, wc, dom, target) {
    var items = [];
    if (cap) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Ui5 Control Should Be Visible    ' + roleArgs(cap.role)); } });
      if (cap.text) items.push({ label: 'v\u00e9rifier : texte', run: function () {
        addStep('Ui5 Text Should Be    ' + rfEscape(cap.text, true) + '    ' + roleArgs(cap.role)); } });
    } else if (sid) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Sid Should Be Visible    ' + sid); } });
    } else if (wc) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Wc Control Should Be Visible    ' + wcArgs(wc)); } });
      if (wc.text) items.push({ label: 'v\u00e9rifier : texte', run: function () {
        addStep('${texte} =    Get Wc Text    ' + wcArgs(wc));
        addStep('Should Be Equal    ${texte}    ' + rfEscape(wc.text, true)); } });
    } else if (dom) {
      items.push({ label: 'v\u00e9rifier : visible', run: function () {
        addStep('Dom Element Should Be Visible    ' + domArgs(dom)); } });
      var txt = cleanCell(target && target.textContent).slice(0, 40);
      if (txt) items.push({ label: 'v\u00e9rifier : texte', run: function () {
        addStep('${texte} =    Get Dom Text    ' + domArgs(dom));
        addStep('Should Be Equal    ${texte}    ' + rfEscape(txt, true)); } });
    }
    return items;
  }
  function onContextMenu(event) {
    if (replaying || !recording || inOurUI(event.target)) return;
    var cap = window.__SAPFX.isUI5() ? window.__SAPFX.capture(event.target) : null;
    var sidObj = cap ? null : window.__SAPFX.captureSid(event.target);
    var sid = sidObj && sidObj.sid;
    var wc = (!cap && !sid) ? window.__SAPFX.captureWc(event.target) : null;
    var dom = (!cap && !sid && !wc) ? window.__SAPFX.captureDom(event.target) : null;
    var items = assertionItems(cap, sid, wc, dom, event.target);
    if (!items.length) return;             // rien d'assertable : menu natif conservé
    event.preventDefault(); event.stopPropagation();
    showMenu(items, event.clientX, event.clientY);
  }

  // --- mise en surbrillance au survol ----------------------------------------
  var raf = 0, lastEvt = null;
  function paint() {
    raf = 0;
    var t = lastEvt ? lastEvt.target : null;
    var info = (t && !inOurUI(t)) ? window.__SAPFX.highlightInfo(t) : null;
    if (!info) { box.style.display = 'none'; chip.style.display = 'none'; return; }
    var r = info.rect;
    box.style.left = r.left + 'px'; box.style.top = r.top + 'px';
    box.style.width = r.width + 'px'; box.style.height = r.height + 'px';
    box.style.display = 'block';
    chip.textContent = info.label;
    var top = r.top - 20; if (top < 0) top = r.top + r.height + 2;
    chip.style.left = r.left + 'px'; chip.style.top = top + 'px';
    chip.style.display = 'block';
  }
  function onMove(event) { lastEvt = event; if (!raf) raf = requestAnimationFrame(paint); }

  function onClick(event) {
    if (replaying) return;               // les clics synthétiques du replay ne se ré-enregistrent pas
    if (menuEl) {                        // menu flottant ouvert : clic-ailleurs = fermeture
      if (!menuEl.contains(event.target)) { closeMenus(); event.preventDefault(); event.stopPropagation(); }
      return;
    }
    if (inOurUI(event.target)) return;   // let panel buttons handle their own clicks
    var cap = window.__SAPFX.isUI5() ? window.__SAPFX.capture(event.target) : null;
    var sidObj = window.__SAPFX.captureSid(event.target);
    var sid = sidObj && sidObj.sid;
    // Page hors registre UI5 (pur Web Components) : repli sur l'hôte ui5-*.
    var wc = (!cap && !sid) ? window.__SAPFX.captureWc(event.target) : null;
    // Zone non-SAP (React/Angular/vanilla) : repli sur le moteur dom générique.
    var dom = (!cap && !sid && !wc) ? window.__SAPFX.captureDom(event.target) : null;
    if (!cap && !sid && !wc && !dom) { console.warn('[UI5 Recorder] no UI5 control, WebGUI SID, ui5-* web component or interactive DOM element there.'); return; }
    if (recording) {                     // mode record : append une action ordonnée
      // En record, le clic n'est JAMAIS bloqué : l'application doit continuer à
      // réagir pour dérouler un vrai parcours (l'ancien preventDefault global
      // gelait l'app pendant l'enregistrement). Seuls les gestes MÉTA
      // (Alt+clic = assertion) sont avalés : ils ne font pas partie du flux.
      if (event.altKey && cap) {
        event.preventDefault(); event.stopPropagation();
        if (event.shiftKey && cap.text) {   // Shift+Alt+clic = assertion de VALEUR
          addStep('Ui5 Text Should Be    ' + rfEscape(cap.text, true) + '    ' + roleArgs(cap.role));
        } else {                            // Alt+clic = assertion de visibilité
          addStep('Ui5 Control Should Be Visible    ' + roleArgs(cap.role));
        }
      } else if (event.altKey && wc) {      // Alt+clic sur un WC = assertion de visibilité
        event.preventDefault(); event.stopPropagation();
        addStep('Wc Control Should Be Visible    ' + wcArgs(wc));
      } else if (event.altKey && dom) {     // Alt+clic zone non-SAP = assertion de visibilité
        event.preventDefault(); event.stopPropagation();
        addStep('Dom Element Should Be Visible    ' + domArgs(dom));
      } else {
        addStep(cap ? withXpathHint(clickLine(cap), cap)
                    : (sid ? ('Click Sid    ' + sid)
                           : (wc ? ('Click Wc Control    ' + wcArgs(wc))
                                 : ('Click Dom Element    ' + domArgs(dom)))));
      }
      return;
    }
    event.preventDefault(); event.stopPropagation();   // mode capture : inspection seule
    var info = window.__SAPFX.highlightInfo(event.target);
    var rec = { cap: cap, sid: sid, wc: wc, dom: dom,
                label: (info && info.label) || (sid ? 'SID ' + sid : 'control') };
    captures.push(rec);
    render();
    copy(allLines(rec));                 // also copy latest to clipboard
    flashGreen();
  }
  // mode record : une saisie validée (change) devient un Fill Ui5 Input ordonné.
  // Les champs SENSIBLES ne sont jamais capturés en clair (ils finiraient dans
  // recorded.robot / sessionStorage / le presse-papier) : on insère un
  // placeholder. type=password est le cas évident ('Password' est la graphie
  // UI5 WC) ; les tokens autocomplete couvrent paiement + OTP + gestionnaires
  // de mots de passe ; les motifs name/id/aria-label rattrapent les formulaires
  // sans autocomplete. Motifs volontairement étroits : un faux positif masque
  // en silence une valeur que l'utilisateur voulait enregistrer.
  var SENSITIVE_AUTOCOMPLETE = /^(cc-number|cc-csc|cc-exp(-month|-year)?|one-time-code|current-password|new-password)$/;
  var SENSITIVE_HINT = /passw|pwd|cvv|cvc|card.?number|cardnum|(^|[^a-z])(csc|otp)([^a-z]|$)|one.?time.?code|security.?code/;
  function isPasswordField(t) {
    return t.type === 'password' || (t.getAttribute && t.getAttribute('type') === 'Password');
  }
  function attrLower(t, name) {
    try {
      if (t && typeof t.getAttribute === 'function') return String(t.getAttribute(name) || '').toLowerCase();
    } catch (e) {}
    return '';
  }
  // Placeholder à enregistrer à la place de la vraie valeur : '<REDACTED>'
  // pour un password, '<SECRET>' pour paiement/OTP, null si la valeur est
  // sûre à enregistrer.
  function sensitiveMask(t) {
    if (isPasswordField(t)) return '<REDACTED>';
    // autocomplete est une liste de tokens séparés par des blancs ('billing cc-number')
    var tokens = attrLower(t, 'autocomplete').split(/\s+/);
    for (var i = 0; i < tokens.length; i++) {
      if (SENSITIVE_AUTOCOMPLETE.test(tokens[i])) return '<SECRET>';
    }
    var hintText = attrLower(t, 'name') + ' ' + attrLower(t, 'id') + ' ' + attrLower(t, 'aria-label');
    return SENSITIVE_HINT.test(hintText) ? '<SECRET>' : null;
  }
  function onChange(event) {
    if (replaying || !recording || inOurUI(event.target)) return;
    var t = event.target;
    if (!t || !('value' in t)) return;
    // Un <input type=file> n'a pas de valeur rejouable (C:\fakepath\...) et
    // l'affecter au replay lève une exception : rien d'utile à enregistrer.
    if (String(t.type || '').toLowerCase() === 'file') return;
    var cap = window.__SAPFX.isUI5() ? window.__SAPFX.capture(t) : null;
    var sidObj = cap ? null : window.__SAPFX.captureSid(t);
    var sid = sidObj && sidObj.sid;
    // NB : le `change` natif d'un <input> INTERNE à un shadow root n'est pas
    // composed : il n'atteint ce listener document que si le composant le
    // re-émet (les UI5 WC réels re-émettent ui5-change/change sur l'hôte).
    var wc = (!cap && !sid) ? window.__SAPFX.captureWc(t) : null;
    var dom = (!cap && !sid && !wc) ? window.__SAPFX.captureDom(t) : null;
    if (!cap && !sid && !wc && !dom) return;
    // Une valeur enregistrée est TOUJOURS échappée façon RF (variables ${...},
    // runs d'espaces, '#', 'mot='...) : le replay in-page la déséchappe.
    var mask = sensitiveMask(t);
    var value = mask || rfEscape(t.value, true);
    if (cap) {
      // Valeur masquée pour les champs sensibles, mais id ET xpath conservés :
      // le locator du champ reste exploitable pour rejouer le test (avec une
      // vraie valeur injectée à la main). Même logique de masquage côté WebGUI (sid).
      addStep(withXpathHint(fillLine(cap, value), cap));
      if (mask) {
        var x = xpathLine(cap);
        if (x) addStep(x);
      }
    } else if (sid) {
      addStep('Fill Sid Input    ' + sid + '    ' + value);
    } else if (wc) {
      addStep('Fill Wc Input    ' + value + '    ' + wcArgs(wc));
    } else {
      addStep('Fill Dom Input    ' + value + '    ' + domArgs(dom));
    }
  }
  var pendingEnter = null;
  function onKey(event) {
    if (replaying) {
      if (event.key === 'Escape') cancelReplay();   // Échap annule un replay en cours
      return;
    }
    if (event.key === 'Escape') {
      if (menuEl) { closeMenus(); return; }   // Échap ferme d'abord le menu flottant
      if (inOurUI(event.target)) return;      // édition in-place : Échap géré par l'input
      window.__ui5SpyStop();
      return;
    }
    // Entrée pendant le record : la touche de VALIDATION fait partie du déroulé
    // (soumission de formulaire, recherche). Différé d'un tick : le `change` du
    // champ, émis pendant l'action par défaut d'Entrée, doit précéder le
    // Keyboard Key dans l'ordre des steps. Textarea exclu (Entrée = nouvelle ligne).
    // Parqué dans pendingEnter : si Entrée déclenche une navigation pleine page,
    // onBeforeUnload le flush avant que le tick ne meure avec la page.
    if (recording && event.key === 'Enter' && !inOurUI(event.target)) {
      var tag = (event.target && event.target.tagName || '').toLowerCase();
      if (tag !== 'textarea') {
        pendingEnter = 'Keyboard Key    press    Enter';
        setTimeout(function () {
          if (pendingEnter) { var p = pendingEnter; pendingEnter = null; addStep(p); }
        }, 0);
      }
    }
  }
  // navigation Fiori (routing par hash / history) -> insère une attente rejouable :
  // Wait For UI5 Ready (moteur inactif, pas seulement chargé) quand le runtime UI5
  // est là, le keyword est embarqué dans l'export, sinon Wait For Load State.
  function onNav() {
    if (!recording) return;
    addStep(window.__SAPFX.isUI5() ? 'Wait For UI5 Ready' : 'Wait For Load State    load');
  }
  // Navigation PLEINE PAGE (soumission, lien hors routing) : flusher l'Entrée
  // différée puis marquer l'attente : les steps sont déjà persistés au fil de
  // l'eau, mais sans ce hook la touche qui a soumis disparaissait avec la page.
  function onBeforeUnload() {
    if (!recording || replaying) return;
    if (pendingEnter) { addStep(pendingEnter); pendingEnter = null; }
    addStep(window.__SAPFX.isUI5() ? 'Wait For UI5 Ready' : 'Wait For Load State    load');
  }

  function setRecording(on) {
    recording = !!on;
    saveRecording();
    if (on) rememberUrl();
    btnRec.textContent = on ? 'pause' : 'rec';
    btnRec.style.background = on ? '#d0021b' : 'transparent';
    dot.style.display = on ? 'inline-block' : 'none';
    dot.style.animation = on ? '__ui5RecBlink 1s infinite' : 'none';
    hint.textContent = on
      ? 'Recording: click/typed value = step. Right-click = assertion menu. +test = next scenario. export = .robot / resource / spec / istqb / report / import.'
      : 'Hover + click to capture. rec to record, play to replay in-page. Right-click / Alt+click = assert. Esc to stop.';
    updateFrameWarn();
    render();
    // notifie le pont d'extension (badge), voir extension/bridge.js
    try { document.dispatchEvent(new CustomEvent('__ui5RecorderState', { detail: on })); } catch (e) {}
  }
  btnRec.addEventListener('click', function () { setRecording(!recording); });
  btnPlay.addEventListener('click', function (e) { e.stopPropagation(); playSteps(); });
  btnNewTest.addEventListener('click', function (e) {
    e.stopPropagation();
    var suggested = 'Scenario ' + (splitScenarios().length + 1);
    var name = null;
    try { name = window.prompt('Nom du sc\u00e9nario suivant :', suggested); } catch (err) {}
    if (name) addStep(testMarkerLine(name));
  });
  btnExport.addEventListener('click', function (e) {
    e.stopPropagation();
    var r = btnExport.getBoundingClientRect();
    var items = EXPORT_FORMATS.map(function (f) {
      return { label: f.label, run: f.run, checkbox: {
        checked: function () { return !!exportSel[f.key]; },
        toggle: function () { exportSel[f.key] = !exportSel[f.key]; saveExportSel(); }
      } };
    });
    items.push({ label: 'exporter la s\u00e9lection', run: exportSelected });
    items.push({ label: 'importer un .robot\u2026', run: importRobot });
    showMenu(items, r.left, r.bottom + 4);
  });
  btnClear.addEventListener('click', function () {
    captures = []; steps = [];
    saveSteps();
    try { sessionStorage.removeItem(URL_KEY); } catch (e) {}
    render();
  });
  btnClose.addEventListener('click', function () { window.__ui5SpyStop(); });

  document.addEventListener('mousemove', onMove, true);
  document.addEventListener('click', onClick, true);
  document.addEventListener('change', onChange, true);
  document.addEventListener('keydown', onKey, true);
  document.addEventListener('contextmenu', onContextMenu, true);
  window.addEventListener('hashchange', onNav, true);
  window.addEventListener('popstate', onNav, true);
  window.addEventListener('beforeunload', onBeforeUnload, true);
  updateFrameWarn();
  if (loadRecording()) setRecording(true);   // l'enregistrement survit à la navigation + ré-injection
  console.info('[UI5 Recorder] Ready. Hover to highlight, click to capture, rec to record. ' +
               'Right-click opens the assertion menu while recording (Alt+click still works). ' +
               'Esc or window.__ui5SpyStop() to stop.');

  // API pilotable depuis le popup de l'extension / le raccourci clavier (monde MAIN).
  window.__ui5RecorderApi = {
    toggleRec: function () { setRecording(!recording); },
    // setRec(on) : état EXPLICITE : le raccourci/popup calcule UNE cible pour
    // toutes les frames au lieu de toggles par frame qui dérivent en anti-phase.
    setRec: function (on) { setRecording(!!on); },
    exportScript: exportScript,
    isRecording: function () { return recording; },
    play: playSteps,
    isReplaying: function () { return replaying; },
    addTestMarker: function (name) { addStep(testMarkerLine(name)); },
    importRobotText: applyImportedText,
    stop: function () { window.__ui5SpyStop(); }
  };

  window.__ui5SpyStop = function () {
    replaying = false;                       // coupe une chaîne de replay en cours
    recording = false;
    saveRecording();                         // un stop explicite ne reprend pas tout seul
    document.removeEventListener('mousemove', onMove, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('change', onChange, true);
    document.removeEventListener('keydown', onKey, true);
    document.removeEventListener('contextmenu', onContextMenu, true);
    document.removeEventListener('mousemove', onDragMove, true);
    document.removeEventListener('mouseup', onDragUp, true);
    window.removeEventListener('hashchange', onNav, true);
    window.removeEventListener('popstate', onNav, true);
    window.removeEventListener('beforeunload', onBeforeUnload, true);
    closeMenus();
    box.remove(); chip.remove(); panel.remove(); styleEl.remove();
    window.__ui5SpyStop = undefined;
    window.__ui5RecorderApi = undefined;
    try { document.dispatchEvent(new CustomEvent('__ui5RecorderState', { detail: false })); } catch (e) {}
    console.info('[UI5 Recorder] stopped.');
  };
})();
