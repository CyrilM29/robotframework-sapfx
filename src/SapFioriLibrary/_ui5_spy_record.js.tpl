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
