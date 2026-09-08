# Canal ECC : SAP GUI desktop (`SapEccLibrary`)

Pilotage du client lourd par l'API Scripting SAP GUI, en COM. Fork durci de
`robotframework-sapguilibrary` : le fichier amont vit dans `_vendor/` et n'est
JAMAIS modifié, tout comportement neuf est un mixin (convention #4).

## Percevoir

- `Get Screen Map` : carte numérotée `@N` des cibles actionnables (libellé, id,
  type, valeur), puis `Resolve/Click/Fill Screen Ref`. Éphémère : pilotage
  interactif, jamais une suite.
- `Get Screen Signature` : vue texte de l'écran. `mode=diff` ne rend que ce qui
  a changé, `pair_renames=True` apparie les ids renommés (un sous-écran
  renuméroté `SAPLMEGUI:0013` → `:0015` reste reconnaissable), `mode=semantic`
  rend une vue formulaire à libellés humains vérifiés, `include_geometry` ajoute
  les rectangles.
- `Get Open Windows` : la pile de fenêtres, `modal=True` sur les
  `GuiModalWindow`. Le garde-fou du piège SESSION_MANAGER.
- `Get Screenshot As Base64` / `Log Screenshot`, et le Set-of-Mark
  `Get/Log Annotated Screenshot` (boîtes numérotées + légende `numéro -> id`).
- `Get Element Screen Region` : la moitié perception de l'effecteur
  coordonnées.

## Agir sur les écrans classiques

- **Transactions** : `Run Transaction` (surchargé, locale-safe, gère les tcodes
  de namespace `/IWFND/…`). Vérifier l'écran d'arrivée, ne jamais croire le
  seul succès rapporté.
- **Grilles ALV** : `Read Grid` / `Read Full Grid` (argument `columns` restreint
  la lecture à des ids TECHNIQUES : locale-safe et beaucoup moins d'appels COM),
  `Get Cell Value By Row Content`, plus les primitives héritées surchargées
  (`Get Row Count`, `Get/Set Cell Value`, `Click Toolbar Button`,
  `Select Table Row`). Le localisateur adresse le CONTRÔLE, pas la mise en page :
  si le chemin porte un `GuiSplitterShell`, la résolution descend jusqu'au
  premier descendant portant `ColumnOrder`, en WARNING, jamais en silence.
- **Table controls de dynpro** (saisie de postes, liste de champs SE11) :
  `Read Table Control`, `Get/Set Table Control Cell` (ligne ABSOLUE, scroll
  automatique), `Find Table Control Row`.
- **Listes ABAP classiques** (SE38, SE16 sans ALV) : `Read Abap List`, qui
  reconstruit géométriquement. La liste SE16 STANDARD (`Use Standard List In
  Data Browser`, l'inverse du réglage ALV ; `Get Data Browser Output` lit le
  mode courant à restaurer en teardown) est rendue en labels et se lit sans
  aucun réglage de poste (mesuré 2026-09-07). Le mode accessibilité SAP GUI
  ne concerne qu'une liste rendue dans un shell opaque sans label, cas jamais
  observé sur le poste de laboratoire : `Get List Rendering Status` /
  `Abap List Should Be Readable` le CONSTATENT, en lisant le sous-type du
  shell (une `GridView` se lit par `Read Grid`, jamais une alerte).
- **Aide à la recherche** : `Pick F4 Value` (F4 ouvert, entrée choisie en grille
  ou en liste, popup refermé ; valeur introuvable = F12 puis échec listant un
  échantillon).
- **Zones opaques** (intérieur d'un GuiShell, GuiChart, drag and drop) :
  `Click Element At Offset`, le geste matériel en DERNIER recours, position
  relative journalisée.
- **Grilles ALV, au-delà de la lecture** (2026-09-07) : `Double Click Grid
  Cell` (le détail d'une ligne), `List Grid Context Menu` / `Select Grid
  Context Menu Item` par code fonction (`&FILTER`, `&FIND`, `&XXL` : stables,
  textes localisés), `List Grid Toolbar Buttons`, `Sort Grid By Column`
  (barre de la grille ou menu contextuel ; SE16 porte son tri dans la barre
  d'application, l'échec le dit). `Doubleclick Element` et `Select Context
  Menu Item` hérités sont surchargés sur une grille.
- **Arbres** (menu SAP Easy Access, IMG de SPRO, SE80, SM59, SICF :
  `GuiShell/Tree`) : `Read Tree Nodes` (clés opaques rendues TELLES QUELLES,
  padding compris ; un arbre à colonnes porte son texte dans `TEXT`),
  `Read Tree Children`, `Expand Tree Node`, `Select Tree Node`, `Select Tree
  Node By Text`, `Select Tree Node By Path` (`A > B > C`), `Get Selected Tree
  Node`, `Double Click Tree Node`, `Find Tree Nodes`.
- **Combo box** : `Get Combo Box Entries`, `Get Combo Box Key`, `Select Combo
  Box Entry By Key` (la voie locale-safe ; `Select From List By Label` hérité
  est surchargé : combo en affichage et libellé inconnu sont refusés en le
  disant).
- **Formats de l'utilisateur** : `Get User Formats` (SU3 > Defaults, clés
  `DATFM`/`DCPFM`, à appeler en Suite Setup) puis `Input Date` (ISO en
  entrée) et `Input Number` (notation technique en entrée) : un dynpro
  refuse une date ISO par un type E, et l'utilisateur du trial est en
  `DD.MM.YYYY` / `1.234.567,89`.
- **Calendrier F4** : `Pick Calendar Date    <champ>    AAAA-MM-JJ` (le F4
  d'un champ date ouvre un `GuiShell/Calendar`, pas une liste ; `Pick F4
  Value` le nomme).
- **Menus** : `Select Menu Item    System > Status` (textes, localisés :
  page object) ou `4 > 11` (positions) ; `List Menu Items`.
- **Onglets** : `Select Tab    <tabstrip>    LOGO` par CLÉ technique (le
  suffixe `tabp<CLÉ>`), `Get Selected Tab`, `List Tabs`, `Select Tab By Label`
  (libellé localisé : page object). Le jeu d'onglets diverge d'une release à
  l'autre : ne jamais graver une liste.
- **Barre d'application** : `List Toolbar Buttons` (id, icône `ICON_*`,
  tooltip), `Click Application Toolbar Button` par id, segment ou icône.
- **Identité d'un message** : `Get Status Message Identity` rend
  classe/type/numéro (`MO/E/402`) ; `Status Message Should Be    MO    402` :
  deux refus de type E du même écran se distinguent sans texte localisé.
- **Identité du système** : `Get System Identity` lit « System: Status »
  (ouvert PAR POSITION RÉSOLUE : le menu System est l'avant-dernier,
  « Status... » l'avant-dernière entrée de ce menu, un dialogue étant exigé
  avant de cliquer ; vérifié structurellement), son popup du kernel et la grille
  « Installed Software » : release SAP_BASIS, kernel, serveur
  `hôte_SID_instance`, base. Deux systèmes de laboratoire partagent SID et
  hôte, seuls release et kernel les distinguent ; `System Identity Should Be
  basis_release=754    kernel_release=777` en garde de tête. Les sections
  illisibles sont NOMMÉES dans `unread`, jamais remplacées par une valeur.
- **Cases et radios par libellé** : `Select Checkbox By Label`, `Unselect
  Checkbox By Label`, `Select Radio Button By Label`, `Checkbox By Label
  Should Be`, sur le TEXTE PROPRE du contrôle (« Sched. », pas « Scheduled »).
- **Perception** : la signature affiche `GuiShell/<SubType>` ; `Get Value` sur
  un shell REFUSE de rendre son ProgID et nomme le lecteur ; une session
  illisible ÉCHOUE (jamais `# screen ?` ni `[]` en PASS) ; la carte `@N` ne
  liste plus les menus.

## Localisateurs humains et auto-réparation

- `Find Element By Label`, `Fill Field By Label`, `Read Field By Label`,
  `Click Button By Label` : libellé visible plus proximité géométrique.
  Grammaire : `Libellé`, `@ Libellé` (dessous), `Gauche @ Haut` (intersection),
  `= contenu`, `N @ Libellé` (grille par position), `Ancre >> Reste` (portée
  réduite au voisinage d'un libellé unique), `exact=False` (préfixe insensible à
  la casse, pensé pour les tooltips finissant par le raccourci).
  **Une ambiguïté est TOUJOURS remontée avec la liste des candidats**, jamais
  tranchée par un premier match silencieux.
- `Resolve Element With Healing` : répare au-dessus d'un seuil, WARNING
  journalisé, `label=<libellé>` ajoute la voie ancre de libellé (adoptée
  seulement si le libellé re-résout vers UN élément).
  `Get Closest Element Ids` donne les candidats scorés.
  Télémétrie cumulative via `SAPFX_HEALING_LOG`, relue par
  `scripts/healing_drift_report.py`.
- `Lookup Business Term` : terme métier FR/EN vers champ ABAP et table.

## Attendre

`Wait Until Busy Done`, `Wait Until Element Present`. Les erreurs d'absence de
cette couche nomment l'écran RÉEL (`# screen <Programme>/<Transaction>/<Numéro>`)
parce qu'un id manquant ne distingue pas un localisateur périmé, un élément pas
encore rendu et un écran qui n'est pas celui qu'on croit : la troisième cause
est la plus fréquente en ECC.

## Sessions

`Open Sap Session` (nouvelle connexion, login optionnel avec `Secret`),
`Create Gui Session` (2e fenêtre sur la connexion active, l'équivalent `/o`
scripté, AUCUN re-login donc jamais de popup multi-logon : la voie recommandée
pour « écrire dans une session, vérifier dans l'autre »),
`Switch Sap Session`, `List Sap Sessions`, `Close Sap Session`,
`Close All Sap Sessions`, `Attach To Open Session` (rattache
moteur, connexion et session par INDEX : le prérequis du replay des suites
générées par le recorder, `Connect To Session` seul n'obtient que le moteur).

Multi-session = **multiplexage** (une session active, bascule explicite), jamais
du parallélisme de threads. Fermer un alias ne touche ni les autres ni une
connexion partagée.

## Préflights

- `Get Scripting Status` / `Scripting Should Be Fully Enabled` : serveur
  (DisabledByServer, readonly, recording_disabled), avec le paramètre RZ11 à
  corriger.
- `Get List Rendering Status` / `Abap List Should Be Readable` : poste (mode
  accessibilité). Un shell AVEC labels est un ALV légitime, rien à corriger.
- `Get Client Security Status` / `Client Security Should Be Hardened` : posture
  du client (CVE-2025-0055 de l'historique de saisie, bases `SAPHistory*.db`).
- `Enable Test Tool Mode`, `Get Session Telemetry`.

## Assertions visuelles et sentinelle

- `Get Screen Perceptual Hash` / `Screen Should Match Baseline`
  (`mask_elements=auto` neutralise sbar et titl avant hachage,
  `per_resolution=True` garde une baseline par géométrie de capture).
- Déclinaison par élément : `Get Element Perceptual Hash` /
  `Element Should Match Baseline`.
- `Get Screen Tile Hashes` : grille 4x4, la dérive se localise là où le hash
  global reste sous le seuil.
- `Check Screen Against Watch` : la sentinelle de dérive, sans test scripté.
  Première visite = référence à committer, ensuite chaque écart nommé.

## Inventaire DDIC et écrans SE16

Le mixin DDIC classe un LOT d'objets du dictionnaire en un appel
(`Classify Ddic Objects`, `Validate Ddic Scope`, `Write/Compare Ddic Inventory
Artifact`, `Read Ddic Table Fields`). Les primitives d'ÉCRAN SE16 vivent à côté :
`Reach Se16 Selection Screen` (l'ouverture d'un écran de sélection en UN seul
endroit : statut type `E`, popup de choix des champs, dialogue de génération,
attente de l'écran généré), `Fill Multiple Selection`,
`Get Se16 Selection Criteria` (carte `I<n>` vers champ, DÉRIVÉE live et jamais
écrite à la main), `Use ALV Grid In Data Browser` (et son inverse `Use
Standard List In Data Browser`, `Set`/`Get Data Browser Output`) et
`Count Entries On Current Selection Screen`.

Trois garde-fous « jamais vert et faux » : grille absente hors écran de
sélection = échec nommant le réglage ALV, plafond de lecture ATTEINT = échec
(troncature jamais muette), lot revenu VIDE = sonde canari.

Pièges SE16 et ALV relevés live : voir [pieges-terrain.md](pieges-terrain.md).
