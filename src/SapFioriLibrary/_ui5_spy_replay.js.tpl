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

