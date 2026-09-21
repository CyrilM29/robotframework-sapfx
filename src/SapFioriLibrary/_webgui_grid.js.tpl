(first, second) => {
  // ATTENTION : ce fichier DOIT commencer par la fonction. Un commentaire posé
  // avant fait évaluer la source comme une simple expression : la fonction
  // n'est alors jamais appelée, le résultat revient VIDE et l'appel RÉUSSIT.
  // Mesuré le 2026-09-15, et c'est le genre d'échec qui ne se voit pas.
  //
  // Lecture d'une grille ALV rendue par le WebGUI (SAP GUI for HTML / ITS).
  // Sonde PURE : elle n'injecte rien et ne modifie rien (une page WebGUI n'a
  // pas de runtime UI5, et observer ne doit jamais instrumenter).
  //
  // Deux faits de rendu commandent tout ce fichier.
  //
  // 1. Le DOM ÉCLATE la grille, le SID la ré-unifie. Une ALV à colonnes figées
  //    est rendue en DEUX tables HTML distinctes (`<id>-mrss-cont-left-content`
  //    pour les colonnes gelées, `-none-content` pour les défilantes) : lire le
  //    `<table>` porteur du `lsdata` rend un texte où tout est collé, et lire
  //    les deux tables séparément oblige à deviner comment les recoller. Or
  //    chaque cellule porte son propre SID `.../row[N]/cell[M]`, où M est
  //    l'index dans `ColumnIDs` : l'adressage par SID traverse la découpe sans
  //    avoir à la connaître.
  //
  // 2. La grille PUBLIE son contrat dans son `lsdata`, et c'est la seule chose
  //    qui distingue une lecture complète d'une lecture amputée. Mesuré : une
  //    sélection SE16 de 2000 lignes rend `totalRows:2000` alors que le DOM
  //    n'en porte que 200, renumérotées `row[1]`..`row[200]`. Les 200 lignes
  //    sont propres et complètes : AUCUNE autre trace ne signale qu'il en
  //    manque 1800. D'où `declared_rows`, rendu systématiquement.
  //
  // Les valeurs sont lues en `innerText` et non en `textContent` : le second
  // COLLE les morceaux d'une cellule composite (mesuré côté UI5 :
  // « New York4 133 » au lieu de deux valeurs), le premier respecte le rendu.
  const arg = (second === undefined) ? first : second;
  const wanted = String((arg === null || arg === undefined) ? '' : arg).trim();

  const sidOf = (el) => {
    const d = el.getAttribute('lsdata') || '';
    const m = d.match(/SID:'([^']*)'/) || d.match(/"SID":"([^"]*)"/);
    return m ? m[1] : '';
  };
  const texte = (el) => {
    if (!el) return '';
    const t = (el.innerText !== undefined && el.innerText !== null)
      ? el.innerText : el.textContent;
    return String(t || '').replace(/\s+/g, ' ').trim();
  };

  // --- la grille visée -------------------------------------------------------
  // TOUS les candidats sont collectés, jamais interrompus au premier trouvé :
  // sans la liste complète, l'appelant ne peut pas savoir que l'écran en porte
  // plusieurs, et prendre la première du DOM en silence produirait cinq
  // fichiers complets d'un AUTRE tableau que celui annoncé. Le dépôt remonte
  // toujours une ambiguïté avec ses candidats (moteur sémantique, chemins de
  // menu, combo) ; c'est `read_webgui_grid` qui tranche, pas cette sonde.
  let grid = null, gridSid = '';
  const candidats = [];
  for (const el of document.querySelectorAll('table[lsdata]')) {
    const sid = sidOf(el);
    const ls = el.getAttribute('lsdata') || '';
    if (ls.indexOf("Type:'GuiGridView'") === -1 && ls.indexOf('"GuiGridView"') === -1) continue;
    candidats.push(sid);
    if (wanted ? (sid === wanted) : (grid === null)) { grid = el; gridSid = sid; }
  }
  if (!grid) {
    return { found: false, wanted: wanted, candidates: candidats,
             lsdata_elements: document.querySelectorAll('[lsdata]').length };
  }

  // --- le contrat publié par la grille ---------------------------------------
  // Les extracteurs acceptent les DEUX dialectes de `lsdata`, comme le fait
  // déjà le résolveur de SID de la bibliothèque : littéral JS aux clés non
  // citées (`totalRows:200`, ce que rend un WebGUI réel) et JSON
  // (`"totalRows":200`, anciens ITS et fixtures). Ne lire que le premier
  // ferait d'une grille au second dialecte une grille RECONNUE dont le
  // contrat serait vide, donc refusée pour la mauvaise raison.
  const ls = grid.getAttribute('lsdata') || '';
  const entier = (cle) => {
    const m = ls.match(new RegExp('"?' + cle + '"?:(-?\\d+)'));
    return m ? parseInt(m[1], 10) : null;
  };
  const chaine = (cle) => {
    const m = ls.match(new RegExp('"?' + cle + '"?:\\s*[\'"]([^\'"]*)[\'"]'));
    return m ? m[1] : '';
  };
  const brutIds = ls.match(/"?ColumnIDs"?:\[([^\]]*)\]/);
  const columns = brutIds
    ? brutIds[1].split(',').map(s => s.replace(/^\s*['"]|['"]\s*$/g, '').trim())
        .filter(s => s !== '')
    : [];

  // --- les titres AFFICHÉS, par identifiant technique ------------------------
  // L'en-tête de sélection porte le SID `.../col` sans nom de champ : il n'est
  // pas une colonne de donnée et ne doit pas entrer dans la carte.
  //
  // `headers_found` compte ce que le balayage a RÉELLEMENT trouvé, et ce
  // compteur est la seule chose qui distingue « les titres affichés sont
  // identiques aux identifiants » (le cas de SE16, qui affiche les noms de
  // champs) de « le balayage n'a rien trouvé et on est retombé sur les
  // identifiants ». Sans lui, un préfixe de SID qui cesse de correspondre sur
  // une autre release livre cinq fichiers en-têtés `SPRSL` au lieu du titre,
  // sans qu'aucune assertion puisse le voir.
  const headers = {};
  let headersFound = 0;
  const prefixe = gridSid + '/col';
  for (const th of document.querySelectorAll('th[lsdata]')) {
    const sid = sidOf(th);
    if (sid.indexOf(prefixe) !== 0) continue;
    const champ = sid.slice(prefixe.length);
    if (!champ) continue;
    headersFound++;
    headers[champ] = texte(th) || th.getAttribute('title') || champ;
  }

  // --- les cellules RÉELLEMENT rendues, adressées par SID --------------------
  const parLigne = new Map();
  const motif = new RegExp('^' + gridSid.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
                           + '/.*?/row\\[(\\d+)\\]/cell\\[(\\d+)\\]$');
  for (const td of document.querySelectorAll('td[lsdata]')) {
    const m = sidOf(td).match(motif);
    if (!m) continue;
    const ligne = parseInt(m[1], 10);
    const colonne = parseInt(m[2], 10);
    if (!parLigne.has(ligne)) parLigne.set(ligne, {});
    const cible = parLigne.get(ligne);
    const nom = columns[colonne] !== undefined ? columns[colonne] : ('COL' + colonne);
    const valeur = texte(td);
    if (!cible[nom]) cible[nom] = valeur;
  }
  const indices = Array.from(parLigne.keys()).sort((a, b) => a - b);
  const rows = indices.map(i => {
    const brute = parLigne.get(i);
    const ligne = {};
    // L'ordre des colonnes est celui que la grille DÉCLARE, jamais celui de
    // parcours du DOM : une colonne gelée est rendue dans une autre table.
    columns.forEach(c => { ligne[c] = (brute[c] !== undefined) ? brute[c] : ''; });
    Object.keys(brute).forEach(c => { if (!(c in ligne)) ligne[c] = brute[c]; });
    return ligne;
  });

  return {
    found: true,
    sid: gridSid,
    candidates: candidats,
    container: chaine('containerName'),
    columns: columns,
    headers: headers,
    headers_found: headersFound,
    rows: rows,
    rendered_rows: rows.length,
    declared_rows: entier('totalRows'),
    visible_rows: entier('visibleRows'),
    first_visible_row: entier('firstVisibleRow'),
    declared_columns: entier('totalColumns'),
    scrolling: chaine('scrolling'),
    scrolling_on_demand: entier('scrollingOnDemand') === 1,
    client_cell_threshold: entier('clientCellThreshold'),
    first_row_index: indices.length ? indices[0] : null,
    last_row_index: indices.length ? indices[indices.length - 1] : null
  };
}
