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
  reconstruit géométriquement. Exige le mode accessibilité SAP GUI, à
  provisionner sur le poste : `Get List Rendering Status` /
  `Abap List Should Be Readable` le CONSTATENT.
- **Aide à la recherche** : `Pick F4 Value` (F4 ouvert, entrée choisie en grille
  ou en liste, popup refermé ; valeur introuvable = F12 puis échec listant un
  échantillon).
- **Zones opaques** (intérieur d'un GuiShell, GuiChart, drag and drop) :
  `Click Element At Offset`, le geste matériel en DERNIER recours, position
  relative journalisée.

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
écrite à la main), `Use ALV Grid In Data Browser` et
`Count Entries On Current Selection Screen`.

Trois garde-fous « jamais vert et faux » : grille absente hors écran de
sélection = échec nommant le réglage ALV, plafond de lecture ATTEINT = échec
(troncature jamais muette), lot revenu VIDE = sonde canari.

Pièges SE16 et ALV relevés live : voir [pieges-terrain.md](pieges-terrain.md).
