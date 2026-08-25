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

