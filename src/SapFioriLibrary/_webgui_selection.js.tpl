() => {
  // ATTENTION : ce fichier DOIT commencer par la fonction. Un commentaire posé
  // avant fait évaluer la source comme une simple expression : la fonction
  // n'est alors jamais appelée, le résultat revient VIDE et l'appel RÉUSSIT
  // (vérifié isolément le 2026-09-15).
  //
  // Sonde PURE de l'écran de sélection SE16 rendu par le WebGUI : aucune
  // injection, rien de modifié sur la page. Elle PERÇOIT (les champs et les
  // textes, avec leur rectangle) et ne JUGE pas : l'appariement libellé/champ
  // et le filtre « nom technique » vivent dans
  // `sapfx_common.webgui_selection`, donc éprouvables hors navigateur.
  //
  // Le SID vit dans l'attribut `lsdata` sous DEUX encodages selon la version
  // de l'ITS : JSON `"SID":"..."` et littéral JS `SID:'...'` (le WebGUI live).
  // Ne matcher que le premier ne rendrait RIEN sur un vrai système.
  const SID = /["']?SID["']?\s*:\s*["']([^"']+)["']/;
  const rectangleDe = (element) => {
    const r = element.getBoundingClientRect();
    return {
      top: Math.round(r.top), bottom: Math.round(r.bottom),
      left: Math.round(r.left), right: Math.round(r.right)
    };
  };
  const visible = (element) => element.offsetParent !== null;

  const fields = [];
  const porteurs = document.querySelectorAll('[lsdata]');
  for (let i = 0; i < porteurs.length; i++) {
    const element = porteurs[i];
    if (!visible(element)) continue;
    const trouve = (element.getAttribute('lsdata') || '').match(SID);
    if (!trouve) continue;
    const zone = rectangleDe(element);
    if (zone.right - zone.left <= 0) continue;
    fields.push(Object.assign({ sid: trouve[1] }, zone));
  }

  // Les libellés sont pris sur les noeuds qui portent AU PLUS un enfant : la
  // feuille elle-même, et son parent immédiat. Se limiter aux feuilles
  // paraissait suffisant et ne l'est pas, parce que le rendu DIFFÈRE d'une
  // release à l'autre (mesuré le 2026-09-21 sur les deux systèmes du banc) :
  // sur l'une, un libellé d'écran de sélection est une feuille portant tout
  // son texte ; sur l'autre, le WebGUI isole le caractère d'ACCÉLÉRATEUR
  // clavier dans sa propre feuille, si bien que `CATEGORY` se rend en un
  // parent `CATEGORY` contenant une feuille `C`. Ne lire que les feuilles y
  // ramenait une poignée de lettres seules, que la couche Python prenait pour
  // des noms de champ d'un caractère.
  //
  // Un conteneur plus haut rend le texte de toute sa descendance et son
  // rectangle ne désigne alors aucune ligne : la borne à un enfant l'écarte.
  // Les fragments restants sont retirés côté Python (un fragment est
  // géométriquement INCLUS dans son libellé), là où c'est testable.
  const labels = [];
  const candidats = document.querySelectorAll('span, label, div, td, a');
  for (let i = 0; i < candidats.length; i++) {
    const element = candidats[i];
    if (element.childElementCount > 1) continue;
    if (!visible(element)) continue;
    const texte = String(element.textContent || '').trim();
    if (!texte || texte.length > 40) continue;
    labels.push(Object.assign({ text: texte }, rectangleDe(element)));
  }

  return { fields: fields, labels: labels };
}
