> [🇬🇧 English](fiori-architecture.md) · **🇫🇷 Français**

# Fiori / côté web (phase 2)

La partie web du projet. Elle automatise les applications SAP Fiori / S/4HANA (SAPUI5) et
s'intègre au **même** vocabulaire métier Robot Framework que le côté ECC, de sorte que
les tests se lisent de manière identique selon les canaux (voir [architecture.fr.md](architecture.fr.md)).

## Le problème central : les ids UI5 dynamiques

SAPUI5 génère des ids DOM comme `__xmlview0--__button12` qui changent entre les builds,
les vues, et même les rendus. Les sélecteurs CSS/XPath basés sur ces ids sont fragiles. La solution consiste à
ne plus adresser le **DOM** mais à adresser directement le **contrôle UI5**.

## Fonctionnement

```text
  test  ──▶  fiori_keywords.resource  ──▶  Browser library (Playwright)  ──▶  page
                       │                              ▲
                       └──▶ SapFioriLibrary ──────────┘
                              injects the __SAPFX bundle (_ui5_js.py) which
                              resolves a control selector → stable control DOM id
```

- **Browser library** (Playwright) gère la page, les clics et la saisie.
- **`SapFioriLibrary`** transforme un *sélecteur de contrôle UI5* en un sélecteur utilisable par Browser,
  via un bundle JS injecté (`src/SapFioriLibrary/_ui5_js.py`) proposant trois
  moteurs :
  - **role** : parcourt le registre des contrôles en faisant correspondre `controlType` (nom court *ou* complet),
    `properties` (sous-chaîne insensible à la casse, ou `/regex/`), `id`,
    `bindingPath`, `viewId`. → `Resolve Ui5 Control`. Retourne
    `css=[id="<controlId>"]` (l'id du *contrôle*, par ex.
    `sdk---app--searchControl-searchField`, stable, et non l'id DOM généré qui change).
  - **xpath** : construit un arbre XML reproduisant la **hiérarchie des contrôles** (balise = type court du contrôle,
    attributs = ses propriétés) et évalue un XPath sur cet arbre, ce qui permet
    d'exprimer des relations d'ascendance et des prédicats. → `Resolve Ui5 By Xpath`.
    Même forme de retour.
  - **wc** : scan du light DOM des custom elements `ui5-*`, pour les pages
    **UI5 Web Components** sans runtime UI5 classique (voir plus bas).
    → `Resolve Wc Control`.
  - **dom** : scan light-DOM générique (CSS, texte, rôle ARIA calculé, nom
    accessible, attributs) pour
    les **régions non-SAP** d'une page hybride (voir plus bas).
    → `Resolve Dom Element`.
- Les applications rendent les vues de manière asynchrone ; la résolution **interroge en boucle** jusqu'à ce qu'un contrôle apparaisse
  ou que `ui5_timeout` soit dépassé, jamais une attente fixe (l'équivalent web du
  `Wait Until Element Present` côté ECC).

```robotframework
Click Ui5 Control    controlType=Button    properties={'text': 'Create'}
Resolve Ui5 By Xpath    //Table//ColumnListItem//Button[@text='Edit']
Resolve Ui5 By Xpath    //*[@controlType='sap.m.SearchField']
${xpath}=    Get Ui5 Xpath    controlType=SearchField    # -> shortest unique //SearchField
```

### XPath unique le plus court (`Get Ui5 Xpath`)

Porté depuis playwright-sap `getShortestXPath` : étant donné un contrôle résolu, retourne le
``//suffixe`` le plus court de son chemin positionnel dans l'arbre qui résout encore exactement vers ce
contrôle. Utile pour la génération de code et pour transformer un contrôle trouvé en un localisateur
hiérarchique stable et lisible.

### SAP WebGUI / SAP GUI for HTML : le moteur `sid`

Les pages WebGUI ABAP classiques (SAP GUI for HTML) ne sont **pas** en UI5. Leurs éléments portent un
attribut ``lsdata`` dont le JSON contient un ``"SID"`` stable : le même espace d'id que le
scripting SAP GUI (``wnd[0]/usr/ctxtVBAK-VBELN``). `Resolve Sid` le fait correspondre via
un XPath ``contains()`` sur ``@lsdata`` et retourne un sélecteur ``xpath=`` ; `Click Sid` /
`Fill Sid Input` / `Sid Should Be Visible` s'appuient dessus. Le Spy capture également les SIDs
(en analysant ``lsdata``). Ceci complète les moteurs UI5 pour les environnements hybrides. Il n'est
pas exercé par le smoke de l'OpenUI5 Demo Kit (pas de WebGUI là) ; le constructeur SID-XPath
et la logique de capture sont testés par des tests unitaires à la place.

### UI5 Web Components : le moteur `wc`

Les pages bâties sur les **UI5 Web Components** (page d'accueil SuccessFactors,
apps ui5-webcomponents) n'ont **aucun runtime UI5 classique** : pas de
`window.sap`, registre d'éléments vide : les moteurs role et xpath y sont
structurellement aveugles. Le moteur `wc` scanne le **light DOM** du document à
la recherche des custom elements `ui5-*` (le contenu applicatif reste dans le
light DOM via les slots ; seuls les internals des composants vivent dans les
shadow roots) :

- `tag=Button` (type court) matche `ui5-button` **et les tags scopés**
  `ui5-button-<suffixe>` (scoping UI5 WC) ; un tag complet (`tag=ui5-button`)
  fonctionne aussi ;
- `properties=` matche les attributs/propriétés de l'hôte avec le *même*
  comparateur que le moteur role (sous-chaîne insensible à la casse, `/regex/`
  borné ; implémentation `valueMatches` partagée) ; `text=` matche le
  `textContent` épuré ;
- `name=` matche le **nom accessible** de l'hôte, c'est-à-dire ce qu'un lecteur d'écran
  annoncerait : `aria-labelledby`/`aria-label`, puis la convention UI5 Web
  Components `accessible-name` (attribut) / `accessibleName` (propriété JS
  non reflétée), puis label/texte visible. Le localisateur « intention
  utilisateur » pour un `ui5-button` à icône seule ou un `ui5-input` sans
  label ;
- les hôtes WC n'ont souvent pas d'id : les correspondances reviennent en
  **chemins CSS light-DOM** ancrés à l'ancêtre à id le plus proche ; les shadow
  roots ouverts sont percés par le CSS de Playwright pour le clic/la saisie
  réels (`Click Wc Control`, `Fill Wc Input` cible l'`<input>` interne).

Le recorder web capture/enregistre aussi les hôtes WC sur les pages sans
registre (`Click Wc Control`, assertions Alt+clic). Prouvé hors ligne contre
une fixture locale avec un vrai tag scopé (`tests/robot/fiori_wc_smoke.robot`).

### Iframes de launchpad : `Set Ui5 Frame` (Work Zone / cFLP)

SAP Build Work Zone et le cFLP classique embarquent chaque application dans une
**iframe**, souvent cross-origin : le runtime UI5 dont le bundle a besoin vit
*dans* la frame, pas dans le shell. `Set Ui5 Frame    iframe#application-...`
bascule la bibliothèque : le bundle est injecté et évalué **dans le contexte de la
frame**, et chaque sélecteur retourné est préfixé par la frame + le combinateur de
perçage `>>>` de Playwright (qui traverse les origines). `Set Ui5 Frame` sans
argument revient à la page principale. Prouvé contre une fixture réellement
cross-origin (`tests/robot/fiori_frame_smoke.robot`).

### Pages hybrides : sonde de composition, pile de frames, moteur `dom`

Un vrai écran composite (shell Work Zone + une app UI5 dans une iframe + une
transaction WebGUI dans une autre + un widget React/vanilla dans un portlet)
mélange les technologies **par région d'une même page**. Trois keywords en font
des citoyens de première classe :

- **`Get Page Composition`**, la sonde de perception hybride : rapporte, par
  région, quelles technologies sont présentes (runtime UI5 classique / hôtes WC
  `ui5-*` / éléments `lsdata` WebGUI / indices React-Angular-Vue), les
  **moteurs recommandés** dans l'ordre de repli, et chaque iframe avec un
  sélecteur Browser réutilisable plus SA composition sondée (un niveau de
  profondeur, best-effort : une frame injoignable porte un champ `error`,
  jamais une perception en échec). À appeler en premier sur un écran inconnu
  pour savoir *quel moteur viser où*.
- **`Push Ui5 Frame` / `Pop Ui5 Frame` / `Get Ui5 Frame Stack`**, la portée de
  frames imbriquées au-dessus de `Set Ui5 Frame` (qui remplace toute la pile) :
  chaque niveau s'empile, la portée effective est le chaînage
  `niveau1 >>> niveau2` de Browser. Un `Pop` de trop échoue bruyamment :
  jamais une portée silencieusement fausse.
- **le moteur `dom`** (`Resolve/Click/Fill Dom …`, `Get Dom Text`,
  `Get Dom Match Count`, `Dom Element Should Be Visible`) : correspondance
  générique sur CSS, texte, rôle ARIA et attributs (mêmes règles
  `valueMatches` que role/wc, chemins CSS light-DOM comme wc) : les régions
  non-SAP entrent dans la *même grammaire* (polling, chaîne de repli et
  télémétrie de healing compris) au lieu de retomber sur des sélecteurs
  Browser bruts hors bibliothèque. `role=` est le rôle ARIA **calculé**,
  c'est-à-dire l'attribut `role` explicite *ou* la sémantique HTML implicite (un
  `<button>` nu, `a[href]` → `link`, `input[type=checkbox]` → `checkbox`,
  `h1`-`h6` → `heading`…, sous-ensemble pragmatique de HTML-AAM), et
  `name=` est le **nom accessible** (accname simplifié, dans l'ordre de
  précédence W3C : `aria-labelledby`, `aria-label`, `label[for]`/label
  englobant, `alt`, `value` de bouton, texte visible, `title`,
  `placeholder`). Ensemble ils donnent des **localisateurs d'intention
  utilisateur** à la Playwright `getByRole(name=…)` : `role=button
  name=Fermer la notification` survit à tout refactoring DOM/CSS qui
  préserve l'accessibilité du widget. Sur une région SAP, le moteur dédié
  gagne toujours ; `dom` est le dernier recours par conception.

Prouvé hors ligne contre `fixtures/hybrid_fixture.html` (quatre technologies,
deux niveaux de frames réellement imbriqués, voir
`tests/robot/fiori_hybrid_smoke.robot`).

### Chaîne de repli de sélecteurs : `Resolve Ui5 With Fallback`

Un keyword, cinq moteurs : essaie **role**, puis **xpath**, puis **sid**, puis
**wc** (`wc={'tag': 'Button', 'text': '…'}`, par ex. une app re-plateformée en
UI5 Web Components dont le registre a disparu), puis **dom**
(`dom={'role': 'button', 'text': '…'}` : le dernier recours, une région
re-plateformée hors de tout cadre SAP), chacun
avec son propre timeout court, et journalise un WARNING dès qu'il réussit sur un
autre moteur que le premier : un localisateur réparé n'est jamais silencieux (le
log dit quel sélecteur corriger, et la réparation est ajoutée au journal
cumulatif `SAPFX_HEALING_LOG` s'il est configuré ; voir
`sapfx_common.healing_telemetry`). Les échecs listent ce que *chaque* moteur a
tenté ; les échecs role ajoutent un indice au niveau du type (« N contrôle(s) de
ce type SONT rendus » vs « aucun ») pour distinguer une mauvaise propriété d'un
mauvais type de contrôle.

### Fiori Elements : `idSuffix` stable

Fiori Elements v4 génère des ids de contrôles stables et sémantiques se terminant
par des motifs comme `fe::table::Travel::LineItem-innerTable`. La clé de sélecteur
`idSuffix` matche sur ce suffixe (moteur role + capture) ; le recorder l'émet
automatiquement quand un id de contrôle porte un marqueur `fe::` : le localisateur
le plus robuste pour les applications FE.

### Porté depuis playwright-sap

L'arbre de contrôles et le moteur XPath, l'extraction des propriétés propres et héritées, le
comparateur de propriétés, le forage vers les éléments interactables, et la liste de propriétés
prioritaires du Spy sont dérivés de **playwright-sap** (Apache-2.0 ; voir le fichier NOTICE du projet),
ré-implémentés sous la forme d'un bundle injecté unique (sans fork de Playwright) pour Robot Framework.

> **Pourquoi pas `RecordReplay.findDOMElementByControlSelector` ?** Une conception antérieure utilisait
> `sap.ui.test.RecordReplay` de SAP. Lors de la validation contre OpenUI5 1.149, cette API
> levait une erreur en interne (`reading 'ancestor'`) en dehors du pipeline OPA5 complet, même avec
> un sélecteur valide codé en dur. L'approche par registre/arbre est plus robuste et
> moins dépendante.
>
> **Champs de saisie composites.** `sap.m.Input` / `SearchField` rendent un `<input>`/`<textarea>`
> interne à l'intérieur du `<div>` racine du contrôle ; il est impossible de saisir dans le
> div. `Fill Ui5 Input` fore automatiquement vers le champ interne.

## Validation

`tests/robot/fiori_smoke.robot` passe de bout en bout contre l'OpenUI5 Demo Kit en ligne
(Robot Framework 7.4.2, Browser 20.0.0) : résoudre un contrôle par type vers son id stable,
remplir son champ de saisie interne, et confirmer qu'un contrôle manquant échoue avec un message clair.

Couverture de versions au-delà du runtime courant (toutes validées en live) :

- **UI5 1.60** (avant `Element.registry`) : `fiori_legacy_smoke.robot` prouve le
  repli DOM `registryForEach` contre un vrai runtime 1.60.14.
- **UI5 2.0 nightly** : `fiori_ui5v2_smoke.robot` prouve la branche module
  `ElementRegistry` et l'absence de dépendance aux APIs supprimées en 2.x
  (`sap.ui.getCore()`, `Element.registry`, `sap.ui.version`). NB : à UI5con
  (juillet 2026), SAP a annoncé qu'aucune release UI5 2.0 n'est prévue : la
  voie officielle de modernisation est la ligne 1.x legacy-free. Ce smoke
  reste donc une sentinelle non bloquante tant que le CDN nightly/2 est servi
  (il peut disparaître) ; le smoke 1.136-legacy-free est la cible d'avenir.
- **Iframes cross-origin** : `fiori_frame_smoke.robot` (voir `Set Ui5 Frame` ci-dessus).
- **Fiori Elements v4** : `fiori_sflight_smoke.robot` vs un cap-sflight local.

## Pourquoi pas Selenium / CSS brut / wdi5

- **CSS/XPath brut** : cassé par le changement d'ids. C'est exactement le problème que l'on évite.
- **wdi5** : excellent et natif UI5, mais basé sur WebdriverIO et extérieur à
  Robot Framework. Notre stack est Robot, donc Browser + `RecordReplay` garde tout
  dans un seul runner et un seul rapport aux côtés des suites ECC.

## Tests sans SAP

Aucun accès requis : pointez `FIORI_BASE_URL` vers l'**OpenUI5 Demo Kit**
(`https://sdk.openui5.org/`). Ses contrôles sont les mêmes contrôles SAPUI5 qu'un vrai
S/4HANA, de sorte que la stratégie de localisation, `SapFioriLibrary`, et le Spy web peuvent tous être
construits et testés sur des pages de démonstration publiques. Voir
[testing-without-sap.fr.md](testing-without-sap.fr.md).

## Outillage de capture

Le Recorder web capture des localisateurs depuis une page en direct : le **survol** met en évidence le contrôle sous
le curseur (encadré bleu + étiquette) ; le **clic** le capture dans un **panneau flottant**
avec des boutons **copier** par ligne `role` / `xpath` / `sid` / `all` (et copie le dernier
dans le presse-papiers). Il sélectionne la meilleure propriété depuis la liste de priorité et émet
des lignes `Resolve Ui5 Control` + `Resolve Ui5 By Xpath` (XPath unique le plus court), avec
`idSuffix` pour les contrôles Fiori Elements, plus `Resolve Sid` sur les pages WebGUI classiques.
Le **mode record** (`rec`) transcrit un flux complet : clics → `Click Ui5 Control`, champs
saisis → `Fill Ui5 Input`, Alt+clic → assertion de visibilité, **Shift+Alt+clic →
assertion de valeur `Ui5 Text Should Be`** ; `export` télécharge un fichier `.robot`
exécutable. Fonctionne aussi dans les iframes de launchpad (les titres du panneau
affichent `[iframe]` ; l'extension s'injecte dans toutes les frames).
Deux interfaces, un seul programme :

- `tools/recorder_web/recorder_snippet.js` : à coller dans la console DevTools.
- `tools/recorder_web/extension/` : extension navigateur MV3 ; cliquer sur l'icône → Start. Elle
  injecte `recorder.js` dans le monde MAIN de la page (pour accéder à `window.sap`) via
  `chrome.scripting` + `activeTab` (sans permissions d'hôte étendues). Icônes générées
  (`gen_icons.py`) et un constructeur de zip prêt pour le store (`package.py` + `PUBLISHING.md`).

Les deux fichiers JS sont **générés depuis le bundle**
(`python -m SapFioriLibrary.regen_recorder`) afin que la capture ne diverge jamais de la résolution ; un test
unitaire garantit la synchronisation. Le **UI5 Test Recorder** intégré de SAP (Ctrl+Shift+Alt+T) est une
option complémentaire plus lourde.

## État d'avancement

- [x] Moteurs `SapFioriLibrary` role + **XPath**, mots-clés de commodité pour les interactions.
- [x] Moteur de localisation playwright-sap porté (arbre/XPath/comparateur/forage/liste de priorité).
- [x] Génération du **XPath unique le plus court** (`Get Ui5 Xpath`).
- [x] **Moteur WebGUI `sid`** (`Resolve/Click/Fill Sid…`) pour SAP GUI for HTML.
- [x] `fiori_keywords.resource` reflétant le vocabulaire ECC.
- [x] Tests unitaires hors navigateur pour le sélecteur, le bundle, le sid et la logique de synchronisation du recorder.
- [x] **Suite smoke validée de bout en bout** vs l'OpenUI5 Demo Kit en ligne (RF 7.4.2 /
      Browser 20.0.0) : role court/complet, arbre XPath + prédicat `@controlType`, remplissage
      du champ interne, comptage des correspondances, aller-retour xpath-le-plus-court, les deux moteurs échouent clairement.
- [x] Recorder web : mise en évidence au survol, panneau in-app, mode record + export
      `.robot`, généré depuis le bundle (snippet + extension MV3).
- [x] **Multi-versions** : UI5 1.60 → 2.0 nightly prouvé en live (chaîne de repli du
      registre), `Get Ui5 Page Tree mode=diff`, perception pour rf-mcp.
- [x] **0.2.0** : `Set Ui5 Frame` (iframes Work Zone/cFLP), `Resolve Ui5 With
      Fallback` (role→xpath→sid, réparation journalisée), `idSuffix` Fiori Elements,
      `Ui5 Text Should Be` (+ capture d'assertion au recorder).
- [x] **0.2.5** : **moteur `wc`** pour les pages UI5 Web Components sans runtime
      classique (scan light-DOM `ui5-*`, tags scopés, clic/saisie à travers les
      shadow roots, capture recorder ; smoke hors ligne 6/6), chaîne de repli
      étendue à role→xpath→sid→wc, journal de télémétrie de healing
      (`SAPFX_HEALING_LOG`).
- [x] **Parité du canal visuel avec l'ECC** : `Get Ui5 Perceptual Hash` +
      `Ui5 Screen Should Match Baseline` : le même cycle snapshot-baseline que
      `Screen Should Match Baseline` (`sapfx_common.visual_baseline` partagé),
      sur une capture de page de la bibliothèque Browser. Couvre ce que
      l'arbre UI5 ne dit pas (canvas, images, thème/rendu globalement altéré).
