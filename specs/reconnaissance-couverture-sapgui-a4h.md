# Reconnaissance de couverture : ce que SapEccLibrary ne sait pas encore faire sur un écran SAP GUI

> **Statut au 2026-09-07 (soir)** : lot de correction livré. Les dix-sept
> manques relevés le matin (plus le dix-huitième trouvé par la revue
> indépendante) sont comblés dans `src/` ; le registre rejoué sur la
> bibliothèque corrigée a rougi 18 fois sur 19 (la preuve que le registre
> mesure), puis les scénarios ont été portés à leur forme COUVERTE (section
> « Scénarios ») et validés live. La section « Données observées » garde les
> relevés du matin : c'est l'état AVANT, daté, qui justifie chaque keyword ;
> sa dernière sous-section porte les relevés du soir (statut système, liste
> SE16 standard) qui ont ouvert les scénarios 19 et 20 (registre à 20 clés).

- **Canal** : ECC (SAP GUI)
- **Système / URL** : A4H (ABAP Platform 1909 trial, Docker, release 754,
  kernel 777), connexion `/H/vhcala4hci/S/3200`, mandant 001, utilisateur
  DEVELOPER, SAP GUI 8.00, langue de session EN. Exploré live le 2026-09-07 en
  deux passes (une via rf-mcp, deux via des suites de sondes jetables jouées
  par `robot` sur le thread principal).
- **Préconditions** :
  - scripting serveur actif (`Scripting Should Be Fully Enabled` en setup) ;
  - SE16 en grille ALV (`Use ALV Grid In Data Browser`, réglage persistant par
    utilisateur, idempotent) pour le scénario grille ;
  - aucune donnée applicative requise : les écrans sondés sont des
    transactions Basis présentes sur tout système ABAP (SESSION_MANAGER, SU01,
    SM37, SE16, SE38, SPRO). `T000` est lue en lecture seule.

## Perception métier

> **Datée du matin du 2026-09-07.** Les risques ci-dessous sont ceux que le
> tour de reconnaissance a établis ; le lot du soir les a fermés dans `src/`
> (voir le statut en tête et la section « Écarts »). Ils restent écrits au
> présent parce que c'est ce que la campagne MESURE : un scénario qui rougit
> signale qu'un de ces risques est revenu.

- **Personas** : `@ecc` + `@basis`, et une casquette qui n'a pas de fiche :
  l'**architecte de la bibliothèque**. Cette campagne ne teste pas un
  processus métier, elle teste la BIBLIOTHÈQUE contre l'API SAP GUI Scripting.
  La persona Basis apporte les écrans (quels contrôles vivent où), l'architecte
  apporte la question (qu'est-ce que l'API expose que nos keywords ignorent).
- **Où se lit la vérité** : dans ce que l'API Scripting EXPOSE sur le contrôle
  vivant (vérifié live, propriété par propriété : `SubType` d'un `GuiShell`,
  `Entries`/`Key` d'un `GuiComboBox`, `GetAllNodeKeys`/`GetNodeTextByKey`/
  `SelectNode` d'un arbre, `SetCurrentCell`+`DoubleClickCurrentCell` d'une
  grille, `SelectionInterval` d'un calendrier), jamais dans la documentation
  d'un keyword ni dans la doc amont de `robotframework-sapguilibrary`. Un
  manque n'est affirmé que quand l'API le permet ET que la bibliothèque ne le
  fait pas ; ce que l'API ne permet pas est classé « hors API », pas « manque ».
- **Risques priorisés** (ceux que la campagne couvre) :
  1. le **vert et faux de perception** : un keyword qui rend une valeur
     plausible là où il n'a rien lu (`Get Value` sur un shell rend son ProgID ;
     `Get Screen Signature` et `Get Open Windows` rendent une vue VIDE en
     PASS quand le COM est inaccessible ; `Wait Until Busy Done` maquille une
     exception de sonde en « serveur occupé ») ;
  2. les **keywords hérités cassés sur les contrôles réels** (`Doubleclick
     Element` appelle l'API des arbres sur une grille, `Select Context Menu
     Item` refuse une grille par son type, `Select Node` échoue sur certains
     nœuds avec une erreur COM non actionnable) ;
  3. les **familles de contrôles sans keyword** (arbres, combo box par CLÉ,
     calendrier, cases et radios par libellé, menus par chemin, éditeurs) ;
  4. la **dépendance à la locale** que le seul keyword de combo (par libellé)
     et la saisie brute d'une date imposent, en contradiction avec la
     convention #3 ;
  5. la **perception illisible pour un agent** : une carte `@N` dont les 120
     premières références sont des entrées de menu ;
  6. le **préflight qui alerte à tort** : `Get List Rendering Status` déclare
     « mode accessibilité nécessaire » sur une grille ALV et sur un éditeur,
     parce qu'il ne lit pas le sous-type du shell (le manque 1 vu depuis un
     autre keyword).
  - **Hors périmètre (dit)** : le contenu d'un `HTMLViewer`, d'une `Picture`
    ou d'un `AbapEditor` (l'API ne l'expose pas : la seule voie est
    `Click Element At Offset`, déjà livrée) ; la mesure du mode accessibilité
    du poste (aucune liste ABAP classique dans le parcours, et le préflight
    qui la constate est lui-même en manque, scénario 18) ; la reproduction dans une
    suite Robot du comportement cross-thread sous rf-mcp (un run `robot` est
    mono-thread : ce manque se verrouille par un test UNITAIRE hors SAP, voir
    Points de vigilance) ; SM30 sur `TVARVC` (dialogue de maintenance absent
    sur A4H, message SAP, pas un manque) ; SE91 et SO10 (écrans initiaux
    relevés, flux non explorés).
- **Assertion reine** : **le registre des capacités est exact**. Chaque
  scénario reproduit UN manque (ou exerce une capacité couverte) et consigne
  un verdict `gap` / `covered` / `poste` / `hors_api` dans un registre JSON
  déterministe ; le scénario ÉCHOUE le jour où l'observation diverge du plan
  dans un sens comme dans l'autre (manque comblé, capacité perdue), en
  nommant la mise à jour du registre. Prouvé le 2026-09-07 : le lot de
  correction a fait rougir 18 scénarios sur 19.
  Portée par TOUS les scénarios, et par le dernier qui écrit le registre et le
  compare au plan. Un manque n'est jamais contourné dans la suite ni dans un
  page object : c'est la règle de la convention #12, et c'est ce que le
  registre mesure.
- **Réversibilité** : lecture seule. Les seules valeurs posées le sont dans
  des champs d'ÉCRAN DE SÉLECTION jamais exécutés en écriture (date « From »
  et combo « Or after event » de SM37, remis à leur valeur initiale), dans le
  Data Browser sur `T000` en affichage, et dans SU01/SE38/SPRO en mode
  affichage. Le seul réglage persistant est celui que toutes les suites SE16
  posent déjà. Session refermée même sur échec.

## Données observées

Relevées live le 2026-09-07 (SAP GUI 8.00, session EN). Les ids sont donnés
pour la couche `resources/` (page object), jamais pour les scénarios.

### SESSION_MANAGER (`SAPLSMTR_NAVIGATION/SESSION_MANAGER/100`)

- Le menu utilisateur est un **arbre** :
  `wnd[0]/usr/cntlIMAGE_CONTAINER/shellcont/shell/shellcont[0]/shell`, de
  type `GuiShell`, `SubType = Tree`, `GetTreeType() = 1` (arbre simple),
  25 nœuds, `TopNode = 'Favo'`. Clés relevées : `Favo` (Favorites), `Root`
  (« User Menu for John Doe », 4 enfants), `0000000003` (« Plain ABAP »).
  L'image voisine `shellcont[1]/shell` est `SubType = Picture`.
- **Ce que la perception en dit** : la ligne de signature porte `GuiShell` et,
  en guise de texte, le ProgID `SAP.TableTreeControl.1` (resp.
  `SAPGUI.ImageCtrl.1`). Aucune colonne ne porte le `SubType`. Une carte `@N`
  ne peut donc pas dire « ceci est un arbre ».
- **API vérifiée** : `GetAllNodeKeys()` (collection, `.Count`), `GetNodeTextByKey(k)`,
  `SelectNode(k)` puis `SelectedNode` relu = `k`, `ExpandNode(k)`,
  `IsFolder(k)`, `GetSubNodesCol(k).Count`, `GetNodeChildrenCount(k)`. Tous
  passent sur `Root` et `0000000003`.
- **Keywords** : `Select Node` (hérité) a ÉCHOUÉ sur la clé `Favo`
  (`AttributeError: Property '<unknown>.selectedNode' can not be set`) et
  PASSÉ sur `0000000003` avec `expand=True` : fragile et non actionnable.
  `Get Value` sur l'arbre rend `SAP.TableTreeControl.1`. Aucun keyword ne lit
  les nœuds, ne les développe, ni ne sélectionne par texte ou par chemin.
- Barre de menus : `wnd[0]/mbar/menu[4]/menu[11]` = « System > Status » ;
  `Click Element` sur ce `GuiMenu` OUVRE le modal `wnd[1]` « System: Status »
  (`Get Open Windows` : `modal = True`). Le modal expose 30 champs texte non
  modifiables ; `Read Field By Label    Transaction` y lit `SESSION_MANAGER`.
  Aucun keyword ne sélectionne un menu par chemin de libellés ni par position.

### SU01 en affichage (`SAPLSUID_MAINTENANCE/SU01/1100`, titre « Display Users »)

- Écran initial : `wnd[0]/usr/ctxtSUID_ST_BNAME-BNAME`, F7 = affichage.
- Tabstrip `wnd[0]/usr/tabsTABSTRIP1`, onglets `tabpDOCU`, `tabpADDR` (actif à
  l'arrivée), `tabpLOGO`, `tabpSNC`, `tabpDEFA`, `tabpPARAM`, `tabpACTG`,
  `tabpPROF`, `tabpGRUP`, `tabpPERS`, `tabpLAW`. `Click Element` sur un
  `GuiTab` fonctionne.
- Onglet Logon Data : combo `.../tabpLOGO/ssubMAINAREA:SAPLSUID_MAINTENANCE:1101/cmbSUID_ST_NODE_LOGONDATA-USTYP`,
  `Changeable = False` (affichage), `Key = A`, `Text = Dialog`, `Entries` =
  `A Dialog`, `B System`, `C Communications Data`, `L Reference (Logon not
  possible)`, `S Service`. `Get Value` rend `Dialog` (texte LOCALISÉ), rien ne
  rend la clé `A`, rien ne liste les entrées. `Select From List By Label`
  échoue par `AttributeError: Property '<unknown>.value' can not be set`, sans
  dire que le combo est en affichage. `Read Field By Label    User Group` =
  `SUPER`, `User Type` = `Dialog` (ancres de libellé valides).
- Onglet Defaults (`:1105`) : trois combos en affichage,
  `cmbSUID_ST_NODE_DEFAULTS-DCPFM` (notation décimale, clé vide =
  `1.234.567,89`, `X` = `1,234,567.89`, `Y` = `1 234 567,89`),
  `cmbSUID_ST_NODE_DEFAULTS-DATFM` (format de date, clé `1` = `DD.MM.YYYY`,
  `6` = `YYYY-MM-DD (ISO 8601)`, douze entrées), `cmbSUID_ST_NODE_DEFAULTS-TIMEFM`
  (`24 Hour Format`). Libellés lisibles par `Read Field By Label` :
  « Decimal Notation », « Date Format », « Time Format ». C'est ici que se lit
  la locale de l'utilisateur, et l'utilisateur DEVELOPER de ce trial est en
  notation décimale ALLEMANDE avec des dates `DD.MM.YYYY`.
- Onglet Parameters (`:1104`) : une **grille ALV** dans le sous-écran,
  `.../tabpPARAM/ssubMAINAREA:SAPLSUID_MAINTENANCE:1104/cntlG_PARAMETER_CONTAINER/shellcont/shell`,
  `SubType = GridView`, 5 lignes : `Read Grid` la lit (témoin couvert).

### SM37 (`Simple Job Selection`)

- Champs : `wnd[0]/usr/txtBTCH2170-JOBNAME`, `ctxtBTCH2170-FROM_DATE`
  (valeur du jour `07.09.2026`), `ctxtBTCH2170-FROM_TIME`, cases de statut
  de job : `chkBTCH2170-PRELIM` porte le texte propre « Sched. » (`Get Value`
  = `unchecked` à l'arrivée : c'est la case du scénario 15) et
  `chkBTCH2170-SCHEDUL` porte « Released » (`checked` à l'arrivée) ; le nom
  technique et le texte affiché ne se correspondent PAS (relevé corrigé le
  soir : le matin, cette ligne attribuait « Sched. » à `SCHEDUL`). Combo
  modifiable `cmbBTCH2170-EVENTID` (`Changeable = True`, clé initiale ` `,
  entrées `*` puis les événements système).
- **Dates** : `Input Text` de `2026-09-01` puis Entrée = message de type **E**
  (`00`/`065`, « Enter date in the format __.__.____ ») ; `01.09.2026` passe
  sans message et se relit tel quel. Aucun keyword ne convertit une date ISO
  vers le format de l'utilisateur, ni ne lit ce format.
- **Libellé « From »** : ambigu (date ET heure à droite du même libellé), la
  bibliothèque le dit avec les deux candidats : comportement attendu, pas un
  manque.
- **F4 sur la date** : ouvre `wnd[1]` « Calendar » portant
  `wnd[1]/usr/cntlCONTAINER/shellcont/shell`, `SubType = Calendar`,
  `FirstVisibleDate = 20260831`, `FocusDate = 202609 7`. `Pick F4 Value`
  échoue par un `com_error` brut (exception 634 « Error description not
  available ») : il attend une grille ou une liste. Poser
  `SelectionInterval = "20260901,20260901"` SÉLECTIONNE la date, referme le
  popup et le champ vaut `01.09.2026`.
- **Combo modifiable** : `obj.Key = "*"` et `obj.Value = "*"` passent tous
  deux ; `Select From List By Label    *` passe aussi ; remise à ` ` vérifiée.
- **Case par libellé** : `Find Element By Label    Scheduled` (avec ou sans
  `control_types=GuiCheckBox`, avec `exact=True`) échoue en listant les
  libellés visibles (« Job Name », « User Name », « From », « To », « Or after
  event », « ABAP Program Name ») : le moteur sémantique n'indexe pas le texte
  PROPRE d'une case ou d'un radio comme libellé.

### SE16 sur T000 en grille ALV (`/1BCDWB/DBT000/SE16/1000` puis `SAPLSLVC_FULLSCREEN/SE16/500`)

- Grille `wnd[0]/usr/cntlGRID1/shellcont/shell`, `SubType = GridView`,
  2 lignes, 17 colonnes (`MANDT`, `MTEXT`, `ORT01`, `MWAER`, `ADRNR`, ...),
  `ToolbarButtonCount = 0` (la barre de la grille est vide : les fonctions
  vivent dans la barre d'application et le menu contextuel).
- Couvert : `Get Grid Column Ids`, `Read Grid`, `Get Cell Value`,
  `Select Table Column`, `Select Table Row` (relu `SelectedRows = 1`).
- **Double-clic** : `Doubleclick Element` échoue par
  `AttributeError: <unknown>.doubleClickItem` (API des arbres). Le chemin
  correct, `SetCurrentCell(0, "MANDT")` + `DoubleClickCurrentCell()`, ouvre le
  modal `wnd[1]` « Details » (vérifié).
- **Menu contextuel** : `Select Context Menu Item` refuse la grille (« Cannot
  use keyword ... for element type 'GuiShell' ») parce qu'il cherche
  `nodeContextMenu`/`pressContextButton`. `ContextMenu()` puis
  `CurrentContextMenu` rend les entrées `&LOCAL&COPY`, `&OPTIMIZE`, `&CDF`,
  `&FIND`, `&FILTER`, `&XXL` (codes fonction STABLES, textes localisés).
- **Barre d'outils** : `Click Toolbar Button    &SORT_DSC` / `&MB_FILTER`
  échouent par « Cannot find Button_id » sans lister ce qui existe (ici :
  rien). Aucun keyword de tri ni de filtre de grille.

### SE38 en affichage (RSPARAM)

- `wnd[0]/usr/cntlEDITOR/shellcont/shell`, `SubType = AbapEditor`,
  `Text = SAPGUI.AbapEditor.1` (le ProgID, pas le source), `AccText` vide.
  `Get Value` rend `SAPGUI.AbapEditor.1` en PASS : vert et faux. Le source est
  hors API (hors périmètre), mais le keyword doit REFUSER, pas inventer.

### SPRO, Reference IMG

- Bouton « SAP Reference IMG » = `wnd[0]/tbar[1]/btn[5]` (résolu par
  `Click Button By Label`). L'IMG est un **arbre à colonnes** :
  `wnd[0]/usr/cntlTREE_CONTROL_CONTAINER/shellcont/shell`, `SubType = Tree`,
  `GetTreeType() = 2`, colonnes `1 2 3 4 5 6 8 TEXT`, 8 nœuds rendus, clés
  COMPLÉTÉES À GAUCHE (`'01  1      1'`, `'02  1      2'`),
  `GetNodeTextByKey` rend une chaîne VIDE : le texte vit dans la colonne
  `TEXT` (`GetItemText(clé, "TEXT")`). Deuxième famille d'arbre, même absence
  de keyword.

### Écran de sélection SE16 et liste classique

- `Count Entries On Current Selection Screen` = 2, `Get Se16 Selection
  Criteria` dérive 16 critères pour T000 (couvert).
- Sur la grille ALV de T000 (`SAPLSLVC_FULLSCREEN/SE16/500`, un seul shell,
  `SubType = GridView`), `Get List Rendering Status` rend `readable_labels =
  0`, `shell_rendered = True`, `accessibility_mode_needed = True` et le
  conseil d'activer le mode accessibilité ; sur l'éditeur de SE38
  (`AbapEditor`), la même réponse. Le keyword calcule « shell ET zéro label »
  sans regarder le sous-type : une grille et un éditeur passent pour une
  liste illisible, sur tout poste. Le mode accessibilité du poste
  d'exploration n'a donc PAS été mesuré par cette campagne.
- `Get Screen Map` sur l'écran de résultat : `@1` à `@10` sont des `GuiMenu`
  (« Table Entry », « Display », « List », « Print Preview »...), la première
  cible de la zone utilisateur arrive après plus de cent entrées de menu.
  `mode=semantic` a la même forme.

### System > Status et SE16 en liste standard (relevés du soir, 2026-09-07)

- **Le menu System est l'AVANT-DERNIER menu de la barre, et « Status... » son
  entrée 11, sur les six écrans sondés** : SESSION_MANAGER (7 menus,
  `menu[4]`), SE16, SU01, SE38, SE11 (7 menus, `menu[5]`), SM37 (5 menus,
  `menu[3]`) ; l'entrée ouvre `SAPLSHSY/<tcode>/700`, « System: Status »,
  `wnd[1]`. Champs à ids TECHNIQUES : `txtSYST-MANDT`, `txtSYST-UNAME`,
  `txtSYST-LANGU`, `txtSHKONTEXT-TCODE`, `txtCVERS_TXT-STEXT` (« Product
  Version » : `- See Details -` sur le trial), `txtCUSTOMER` (installation),
  `txtSERVERNAME` (`vhcala4hci_A4H_00` : hôte, SID, instance), `txtSYST-OPSYS`,
  `txtDBNAME` (`HDB`), `txtSTATUS_INFO-DATABASE_RELEASE`, `-DATABASE_HOST`,
  `-DB_SCHEMA`. Boutons : `tbar[0]/btn[17]` « Other Kernel Information »
  (Shift+F5) et `usr/btnPRELINFO` « Details ».
- **Le popup « Kernel information »** (`SAPLSHSY/.../701`, `wnd[2]`) :
  `txtKINFOSTRUC-KERNEL_RELEASE` = `777`, `-KERNEL_PATCH_LEVEL` = `500`,
  `-ABAP_LOAD`, `-CUA_LOAD`, `-KERNEL_KIND` = `opt`, `-SUPPORTED_SAP_VERS` =
  `753, 754, 777`, `-IP_ADDRESS` (`172.17.0.2`, VOLATILE), `txtDBINFO-*`.
- **Le dialogue « Installed Software »** (`SAPLOCS_UI_CONTROLS/.../300`,
  `wnd[2]`, modal INFORMATIF : seul `btn[0]`) : onglet `tabpCOMP_VERS`, grille
  `.../cntlSCV_CU_CONTROL/shellcont/shell` (`GuiShell/GridView`), colonnes
  techniques `COMPONENT`, `RELEASE`, `EXTRELEASE` (SP), `HIGH_PATCH`,
  `DESC_TEXT` ; première ligne `SAP_BASIS 754 0007 SAPK-75407INSAPBASIS`.
  C'est LA release ABAP, absente du modal principal et du kernel.
- **La liste SE16 standard** (Settings → User Parameters, radio `radTB_DUMMY`
  « Standard SE16 list », à côté de `radRSEUMOD-TBALV_GRID` et
  `radRSEUMOD-TBALV_STAN`) : T000 exécutée rend `SAPMSSY0/SE16/120` en
  **42 `GuiLabel`**, `shell_rendered` faux, `accessibility_mode_needed` faux,
  et `Read Abap List` rend 5 lignes (en-tête « Table: T000 », en-tête de
  colonnes en NOMS de champs `MANDT MTEXT ...` (réglage utilisateur « Field
  Name »), puis les mandants `000` et `001`). Aucun mode accessibilité n'est
  donc requis pour cette liste classique sur ce poste (le registre Windows
  ne porte aucune clé `Accessibility` sous SAP Frontend Server : réglage au
  défaut). Le mode `alv_grid` relu après restauration.

## Scénarios

Chaque scénario consigne un verdict dans le registre (`Consigner Le Verdict`,
mot-clé de page object) : `gap` (l'API le permet, la bibliothèque ne le fait
pas), `covered` (la capacité est exercée live et tient), `poste` (limite de
poste constatée par un préflight : vocabulaire réservé), `hors_api` (l'API ne
l'expose pas). Le verdict ATTENDU est celui de la table « Clés de registre » :
le scénario échoue si l'observation en diverge, dans les deux sens.

**État au 2026-09-07, après le lot de correction** : les dix-sept manques du
tour de reconnaissance ont été comblés dans `src/` le jour même (mixins
`_trees.py`, `_combobox.py`, `_menus.py`, `_grid_actions.py`, ajouts dans
`_semantic.py`, `_perception.py`, `_diagnostics.py`, `_waits.py` et le rail
STA de `SapEccLibrary.py` ; logique pure dans `sapfx_common`). Le registre
rejoué sur la bibliothèque corrigée a rougi 18 fois sur 19 en nommant « mettre
à jour le plan et le registre » : c'est la preuve attendue, et les scénarios
ci-dessous sont leur forme COUVERTE, chacun exerçant la capacité livrée sur
l'écran réel. Un scénario qui rougit désormais signale une capacité PERDUE.

### 1. La perception distingue les sous-types de shell

- **Étapes** : sur l'accueil, lire la signature d'écran ; isoler la ligne du
  contrôle-arbre du menu utilisateur.
- **Résultat attendu** : trois colonnes, la colonne type vaut
  `GuiShell/Tree` (le sous-type est affiché, le ProgID reste en texte).
  Verdict `covered`.

### 2. L'arbre du menu SAP se lit par keyword

- **Étapes** : sur l'accueil, `Read Tree Nodes` sur le contrôle-arbre ;
  tenter `Get Value` sur ce contrôle.
- **Résultat attendu** : au moins un nœud rendu, chacun avec `key` et
  `text` ; `Get Value` REFUSE en nommant le ProgID et `Read Tree Nodes`.
  Verdict `covered`.

### 3. Sélectionner un nœud d'arbre est vérifié

- **Étapes** : `Select Tree Node By Text` sur le dossier « Plain ABAP » du
  menu utilisateur (texte porté par le page object), puis `Get Selected Tree
  Node`.
- **Résultat attendu** : la clé rendue par la sélection est celle relue comme
  nœud sélectionné. Verdict `covered`.

### 4. L'arbre à colonnes de l'IMG se lit

- **Étapes** : ouvrir SPRO, cliquer « SAP Reference IMG » (par libellé) ;
  `Read Tree Nodes` sur l'arbre de l'IMG.
- **Résultat attendu** : au moins un nœud, la clé complétée à gauche rendue
  telle quelle, un texte NON vide lu dans la colonne `TEXT`. Verdict
  `covered`.

### 5. Une combo box en affichage est refusée en le disant

- **Étapes** : afficher l'utilisateur DEVELOPER en SU01, onglet Logon Data ;
  `Get Combo Box Key` et `Get Combo Box Entries` sur le type d'utilisateur ;
  tenter `Select From List By Label    System`.
- **Résultat attendu** : la clé lue est `A` (clé technique de « Dialog »,
  locale-safe), l'entrée `A` figure dans la liste, et la sélection échoue en
  nommant le mode AFFICHAGE (jamais une `AttributeError` COM muette).
  Verdict `covered`.

### 6. Une combo box modifiable se sélectionne par clé

- **Étapes** : sur SM37, lire la clé initiale de « Or after event » et
  vérifier qu'elle est le BLANC `" "` (clé distincte de la clé vide `""`,
  relevé live : la constante vit dans le page object), `Select Combo Box
  Entry By Key    *`, relire la clé, puis remettre la clé initiale par clé.
- **Résultat attendu** : la clé initiale est `" "` (rendue TELLE QUELLE par
  `Get Combo Box Key`, sans normalisation), la clé relue vaut `*` après
  sélection et `" "` après restauration : c'est la preuve que la restauration
  a visé la bonne des deux entrées. Verdict `covered`.

### 7. La saisie d'une date se convertit au format de l'utilisateur

- **Étapes** : sur SM37, lire la date « From » initiale ; `Input Date` avec
  `2026-09-01` puis Entrée ; lire le type de message ; relire le champ ;
  restaurer la date initiale EN TEARDOWN (même sur échec ; rien à restaurer
  si le test a échoué avant de la relever).
- **Résultat attendu** : aucun message de type `E`, la chaîne rendue par
  `Input Date` est la forme LOCALE relevée (`01.09.2026`, portée par le page
  object : la conversion est confrontée à une valeur mesurée, pas seulement
  à « différent de l'ISO »), la valeur relue est cette même chaîne, date
  initiale restaurée ET VÉRIFIÉE (aucun type `E`, valeur relue égale à
  l'initiale). Verdict `covered`.

### 8. Les formats de l'utilisateur se lisent par clé technique

- **Étapes** : `Get User Formats` (déjà appelé en Suite Setup, rejoué ici).
- **Résultat attendu** : `date_format` dans `1` à `6`, `gregorian` vrai,
  `decimal_notation` dans {vide, `X`, `Y`}, `date_pattern` non vide : des
  CLÉS, jamais un libellé localisé. Verdict `covered`.

### 9. Le calendrier F4 d'une date se pilote

- **Étapes** : sur SM37, `Pick Calendar Date` sur « From » avec
  `2026-09-01` ; relire le champ ; tenter `Pick F4 Value` sur le même champ ;
  restaurer la date initiale EN TEARDOWN (même sur échec).
- **Résultat attendu** : la valeur rendue est la forme LOCALE relevée
  (`01.09.2026`, portée par le page object ; le scénario ne fait AUCUNE
  saisie `Input Date`, sans quoi le calendrier ne serait pas ce qui est
  mesuré), aucun modal résiduel ; `Pick F4 Value` échoue en nommant le
  CALENDRIER et `Pick Calendar Date` ; date initiale restaurée ET VÉRIFIÉE
  comme au scénario 7 (même mot-clé de page object). Verdict `covered`.

### 10. Le double-clic d'une cellule ouvre le détail

- **Étapes** : SE16 sur T000 en grille ; `Double Click Grid Cell` ligne 0,
  colonne `MANDT` ; lire la pile de fenêtres ; refermer le modal.
- **Résultat attendu** : une fenêtre modale est ouverte après le double-clic
  (le détail de la ligne), plus aucune après fermeture. Verdict `covered`.

### 11. Le menu contextuel d'une grille se pilote par code fonction

- **Étapes** : même grille ; `List Grid Context Menu` ; `Select Grid Context
  Menu Item    &FILTER` ; lire la pile de fenêtres ; refermer.
- **Résultat attendu** : le code `&FILTER` figure dans le menu listé, le
  dialogue de filtre s'ouvre (modal présent) puis se referme. Verdict
  `covered`.

### 12. Un bouton de barre d'outils absent est refusé avec inventaire

- **Étapes** : même grille ; `List Grid Toolbar Buttons` ; `Click Toolbar
  Button    &SORT_DSC` ; `Sort Grid By Column    MANDT`.
- **Résultat attendu** : la barre de la grille est vide, le clic échoue en
  nommant la barre d'application, et le tri échoue de même (SE16 porte son
  tri dans la barre d'application) : deux échecs qui DISENT où est la
  fonction. Verdict `covered`.

### 13. Une grille dans un sous-écran de tabstrip se lit (témoin couvert)

- **Étapes** : SU01, DEVELOPER, onglet Parameters ; `Read Grid` sur la grille
  du sous-écran avec `max_rows=5`.
- **Résultat attendu** : au moins une ligne portant des clés de colonnes
  techniques. Verdict `covered`.

### 14. `Get Value` sur un éditeur ABAP refuse

- **Étapes** : SE38, RSPARAM, F7 ; `Get Value` sur le contrôle éditeur.
- **Résultat attendu** : échec nommant le ProgID et `GuiShell/AbapEditor` (le
  source est hors API : le refus est la capacité). Verdict `covered`.

### 15. Une case à cocher se coche par son texte propre

- **Étapes** : SM37 ; lire l'état de la case « Sched. » (son TEXTE PROPRE,
  porté par le page object) ; la BASCULER vers l'état OPPOSÉ à l'initial
  (`Select Checkbox By Label` si elle est décochée, `Unselect Checkbox By
  Label` si elle est cochée) ; `Checkbox By Label Should Be` sur l'état
  opposé ; restaurer l'état initial.
- **Résultat attendu** : l'id résolu est celui d'une `GuiCheckBox`, l'état
  relu est l'OPPOSÉ de l'initial (une case déjà cochée qu'on « coche » ne
  prouverait rien), l'état initial est restauré. Verdict `covered`.

### 16. Un menu se sélectionne par chemin

- **Étapes** : accueil ; `Select Menu Item` avec le chemin « System > Status »
  (chemin de textes porté par le page object) ; lire la pile de fenêtres ;
  lire « Transaction » par libellé dans le modal ; refermer par F12.
- **Résultat attendu** : l'id sélectionné est celui de la position relevée
  (`menu[4]/menu[11]`), modal présent, `SESSION_MANAGER` lu. Verdict
  `covered`.

### 17. La carte numérotée commence par la zone actionnable

- **Étapes** : SE16 sur T000 en grille ; `Get Screen Map` ; isoler `@1` et
  compter les entrées de menu.
- **Résultat attendu** : `@1` n'est pas un `GuiMenu` et la carte ne porte
  AUCUNE entrée `GuiMenu`. Verdict `covered`.

### 18. Le préflight de liste reconnaît une grille ALV

- **Étapes** : SE16 sur T000 en grille ; `Get List Rendering Status`.
- **Résultat attendu** : `shell_subtypes` porte `GridView`,
  `accessibility_mode_needed` FAUX, et le conseil nomme `Read Grid`. Verdict
  `covered`.

### 19. La liste SE16 standard se lit en labels

- **Étapes** : basculer la sortie du Data Browser en liste standard (`Use
  Standard List In Data Browser`, réglage persistant par utilisateur) ;
  atteindre l'écran de sélection de T000 et exécuter (F8) ; `Get List
  Rendering Status` ; `Read Abap List` ; en teardown, MÊME SUR ÉCHEC,
  `Use ALV Grid In Data Browser` puis relire le mode (`Get Data Browser
  Output`) pour prouver la restauration.
- **Résultat attendu** : la liste classique (dynpro `SAPMSSY0/120`) est
  rendue en labels : `list_readable` vrai, `shell_rendered` faux,
  `accessibility_mode_needed` faux, et la liste lue porte une ligne commençant
  par le mandant de référence `000` (présent dans T000 de tout système ABAP,
  l'ancre de DONNÉES locale-safe : les en-têtes suivent un réglage
  utilisateur, noms ou libellés de champs). Verdict `covered`. Mode relu
  `alv_grid` après restauration.

### 20. L'identité du système prouve sa release et son kernel

- **Étapes** : accueil ; `Get System Identity` (System > Status ouvert PAR
  POSITION, avant-dernier menu et entrée 11, vérifié structurellement ; popup
  « Kernel information » ; dialogue « Installed Software ») ; comparer le SID
  lu à celui de la session (`List Sap Sessions`) ; lire la pile de fenêtres.
- **Résultat attendu** : `basis_release` sur trois caractères (la ligne
  `SAP_BASIS` des composants), `kernel_release` non vide, `unread` VIDE
  (aucune section remplacée par une valeur plausible), SID identique à celui
  de la session, aucun modal résiduel. Verdict `covered`.

### 21. Le registre est écrit, déterministe, et conforme au plan

- **Étapes** : écrire le registre par `Write Deterministic Artifact`
  (`sapfx_common.artifacts` : JSON trié, empreinte SHA-256 sur la seule clé
  `capabilities`, périmètre DÉCLARÉ dans `hash_scope`) avec l'IDENTITÉ de la
  cible mesurée en Suite Setup par `Get System Identity` (SID, mandant,
  utilisateur, release SAP_BASIS, kernel, serveur ; jamais de mot de passe) ;
  le relire par `Read Deterministic Artifact` (empreinte RECALCULÉE : un
  registre édité après coup est refusé) ; vérifier que chaque clé de la table
  « Clés de registre » y figure avec le verdict attendu, que l'identité porte
  SID, mandant, utilisateur, release et kernel non vides, que le périmètre
  haché est `capabilities`, et journaliser le tableau Markdown.
- **Résultat attendu** : registre présent, exactement les 20 clés de la table,
  aucun écart avec le plan, identité de cible renseignée (deux cibles aux
  mêmes verdicts donnent la même empreinte, et l'identité dit LAQUELLE a été
  mesurée, release et kernel compris).

## Clés de registre

La suite recopie cette table dans `&{PLANNED_VERDICTS}` : c'est la table que
le scénario 21 confronte au registre, et ce qu'un relecteur diffe entre plan
et suite. Au 2026-09-07 (lot de correction livré), toutes les clés sont
`covered` ; la colonne « avant » garde le verdict du tour de reconnaissance
(`n/a` pour les deux clés ajoutées le soir, après le lot : elles exercent des
capacités livrées en réponse aux réserves de la revue et au backlog).

| Scénario | Clé de registre | Verdict attendu | Avant le lot |
| --- | --- | --- | --- |
| 1 | `perception.shell_subtype` | `covered` | `gap` |
| 2 | `tree.read_nodes` | `covered` | `gap` |
| 3 | `tree.select_node` | `covered` | `gap` |
| 4 | `tree.column_tree_read` | `covered` | `gap` |
| 5 | `combobox.display_mode` | `covered` | `gap` |
| 6 | `combobox.select_by_key` | `covered` | `gap` |
| 7 | `date.input_user_format` | `covered` | `gap` |
| 8 | `user.formats` | `covered` | `gap` |
| 9 | `f4.calendar` | `covered` | `gap` |
| 10 | `grid.double_click_cell` | `covered` | `gap` |
| 11 | `grid.context_menu` | `covered` | `gap` |
| 12 | `grid.toolbar_inventory` | `covered` | `gap` |
| 13 | `grid.in_tabstrip_subscreen` | `covered` | `covered` |
| 14 | `editor.get_value_refuses` | `covered` | `gap` |
| 15 | `checkbox.by_own_label` | `covered` | `gap` |
| 16 | `menu.select_by_path` | `covered` | `gap` |
| 17 | `screen_map.menus_first` | `covered` | `gap` |
| 18 | `perception.list_status_on_grid` | `covered` | `gap` |
| 19 | `list.standard_se16_readable` | `covered` | `n/a` |
| 20 | `identity.release_and_kernel` | `covered` | `n/a` |

## Keywords métier manquants

Page object à créer : `resources/page_objects/sapgui_capability_probes.resource`
(ids de la section « Données observées », mots-clés métier ci-dessous). Les
mots-clés de REGISTRE sont transverses et vivent dans le même fichier.

1. `Consigner Le Verdict    ${capacite}    ${verdict}    ${preuve}` : ajoute
   une entrée au registre de suite ; `Le Verdict Devrait Etre    ${capacite}
   ${attendu}` échoue en nommant « capacité désormais couverte : mettre à jour
   le plan et le registre » quand l'observé diverge.
2. `Ecrire Le Registre Des Capacites    ${chemin}` : JSON trié, sans
   horodatage dans la partie hachée.
3. `Ligne De Signature Du Menu Utilisateur` : la ligne de la signature portant
   l'id de l'arbre.
4. `Afficher L Utilisateur    ${user}` (SU01 + F7) et `Ouvrir L Onglet
   ${onglet}` (Logon Data, Defaults, Parameters).
5. `Tenter De Changer Le Type D Utilisateur` (les lectures par libellé du
   matin, `Lire Le Type D Utilisateur` et `Lire Les Formats De L
   Utilisateur`, ont été RETIRÉES le soir : la forme couverte lit des clés).
6. `Ouvrir La Selection Simple Des Jobs` (SM37), `Saisir La Date De Debut
   ${date}` (Entrée + type de message), `Lire La Date De Debut`
   (`Ouvrir Le Calendrier De La Date De Debut` et `Choisir L Evenement
   ${cle}`, par libellé, retirés le soir).
7. `Afficher T000 En Grille`, `Cliquer Un Bouton De Grille    ${id}`
   (`Double Cliquer La Premiere Cellule` et `Ouvrir Le Menu Contextuel De La
   Grille`, qui reproduisaient les keywords hérités cassés, retirés le soir).
8. `Afficher Le Programme    ${nom}` (SE38 + F7) et `Lire Le Controle Editeur`.
9. `Ouvrir L IMG De Reference` (SPRO) (`Lire Le Controle Arbre De L IMG`
   retiré le soir).
10. `Ouvrir Le Statut Systeme Par Le Menu` (position `menu[4]/menu[11]`
    relevée live) retiré le soir au profit du chemin de textes ; la position
    reste dans le page object comme valeur ATTENDUE du scénario 16.
11. `Un Keyword Devrait Etre Absent    ${nom}` : `Keyword Should Exist`
    inversé, la preuve d'absence d'une capacité (conservé avec `Verdict De
    Manque` : c'est le vocabulaire d'un FUTUR manque).
12. Depuis le lot de correction (2026-09-07 soir), les mots-clés de la forme
    COUVERTE, tous des compositions de keywords de bibliothèque :
    `Verdict De Capacite` (le miroir de `Verdict De Manque`), `Lire Les
    Noeuds Du Menu Utilisateur`, `Selectionner Le Dossier Plain ABAP Par
    Texte`, `Noeud Selectionne Du Menu Utilisateur`, `Lire Les Noeuds De L
    IMG`, `Lire La Cle Du Type D Utilisateur`, `Lire Les Entrees Du Type D
    Utilisateur`, `Choisir L Evenement Par Cle`, `Lire La Cle De L Evenement`,
    `La Cle Initiale De L Evenement Devrait Etre Un Blanc`, `Saisir La Date
    De Debut En ISO`, `La Date Saisie Devrait Etre La Forme Locale`, `Forme
    Locale De La Date De Sonde`, `Restaurer La Date De Debut` (restauration
    VÉRIFIÉE : type de message vide et valeur relue égale à l'initiale),
    `Choisir La Date De Debut Au Calendrier`,
    `Ouvrir Le Detail De La Premiere Ligne`, `Codes Du Menu Contextuel De La
    Grille`, `Ouvrir Le Filtre De La Grille`, `Boutons De La Barre De La
    Grille`, `Trier La Grille Par Client`, `Etat De La Case Planifie`,
    `Basculer La Case Planifie    ${initial}` (vers l'état OPPOSÉ, rend l'id
    et l'état attendu), `La Case Planifie Devrait Etre`, `Restaurer La Case
    Planifie`, `Ouvrir Le Statut Systeme Par Chemin`, `Entrees De Menu De La
    Carte`, `Identite De La Cible` (système, mandant, utilisateur lus par
    `List Sap Sessions` en Suite Setup), et les trois assertions de forme
    `Les Noeuds Devraient Porter Cle Et Texte`, `L Entree De Cle Devrait
    Figurer`, `Les Formats Devraient Etre Des Cles`. Le Suite Setup appelle
    `Get User Formats` (SU3) pour `Input Date`.
13. Depuis les scénarios 19 à 21 (même soir) : `Mode De Sortie Du Data
    Browser`, `Afficher T000 En Liste Standard`, `Statut De Rendu De L
    Ecran`, `Lire La Liste Standard`, `La Liste Devrait Porter Le Mandant De
    Reference` (ancre `000`), `Restaurer La Grille ALV Du Data Browser`
    (restauration RELUE) ; `Identite Du Systeme`, `L Identite Devrait Prouver
    La Release`, `Le Systeme Lu Devrait Etre Celui De La Session` ;
    `Identite De La Cible` passe par `Get System Identity` ; `Ecrire` /
    `Relire Le Registre Des Capacites` passent par `Write` / `Read
    Deterministic Artifact` (`Library    sapfx_common.artifacts`, plus aucun
    `Evaluate json` dans le page object).

## Points de vigilance

> **Datés du matin du 2026-09-07**, sauf mention contraire : chaque point
> garde le constat qui a motivé une correction, suivi de ce que le lot du soir
> en a fait. Ce qui est fermé est dit fermé, avec sa preuve.

- **Cross-thread sous rf-mcp, à verrouiller hors SAP.** (Fermé le soir :
  verrouillé par `tests/unit/test_perception_unreadable.py`,
  `test_wait_busy_cause.py`, `test_sta_reattach.py`, et PROUVÉ à travers
  rf-mcp lui-même après hot-swap de la bibliothèque dans le serveur : un
  `execute_batch` sur un thread étranger a rendu la pile de fenêtres réelle
  et une signature de 165 lignes portant `SESSION_MANAGER`, là où le matin il
  rendait `[]` et `# screen ?`.) Pendant la passe rf-mcp,
  `execute_batch` et `Evaluate` se sont exécutés sur un autre thread que les
  keywords de bibliothèque, et le rail STA « défensif » de la bibliothèque
  (CoInitialize sans marshaling) n'a pas suffi : `Wait Until Busy Done` a
  rendu « SAP session was still busy after 30 seconds » sur un écran au repos,
  `Get Screen Signature` a rendu `# screen ?` sans aucun élément en PASS,
  `Get Open Windows` a rendu `[]` en PASS, `Element Should Be Present
  wnd[0]` a échoué, et l'`AttributeError` COM d'un thread étranger a verrouillé
  `_object_tree_unsupported` (la géométrie disparaît, les localisateurs par
  libellé se dégradent en accusant un `GetObjectTree` « absent »). Remède de
  session : `use_context=true` sur chaque `execute_step`, jamais
  `execute_batch`, jamais d'objet COM dans un `Evaluate`. Remède de
  bibliothèque (hors de cette campagne, tests unitaires avec une session
  factice levant `com_error` RPC_E_WRONG_THREAD, hresult -2147417842) : une
  perception qui ne peut pas lire ÉCHOUE en nommant la cause, le message de
  `Wait Until Busy Done` porte la dernière exception, la latche
  `GetObjectTree` ne se ferme que sur une vraie absence d'API, et le rail STA
  ré-attache la session par index sur le thread étranger.
- **Position de menu** : `menu[4]/menu[11]` est relevée sur A4H 1909 en EN ;
  la position du menu System varie par transaction (avant-dernier menu, en
  règle générale) et le libellé par langue. Le page object porte la position
  ET le libellé, le scénario aucun des deux.
- **`Select Node`** : la clé `Favo` a échoué dans une passe de sondes et passé
  dans le run de génération, `0000000003` a passé partout : ne rien
  généraliser. (Le soir : le scénario 3 passe par `Select Tree Node By
  Text`, qui sélectionne par `SelectNode(clé)` et VÉRIFIE le nœud relu ; le
  `Select Node` hérité est surchargé par la même voie.)
- **SM37 pose des valeurs dans un écran de sélection** : jamais exécuté en
  écriture ; la date « From » est restaurée explicitement à sa valeur initiale
  relue en début de scénario. (Le soir : la combo EST remise à sa clé
  initiale `" "` par `Select Combo Box Entry By Key`, et la restauration est
  assertée sur la clé relue ; la non-persistance de l'écran de sélection,
  mesurée le matin, n'est plus le seul filet.) Le job listing (F8) n'est pas
  rejoué dans la suite.
- **`Read Field By Label    From`** est ambigu sur SM37 (date et heure) : viser
  l'id du champ date dans le page object, ou `Gauche @ Haut`.
- **Le modal « Details » d'une grille** (ouvert par le double-clic API) doit
  être refermé par F12 sur `window=1` AVANT tout F3 : un F3 sur `wnd[0]` avec
  un modal ouvert ne fait rien.
- **Le mode accessibilité du poste n'est PAS mesuré par cette campagne** :
  le seul écran de liste classique visité (SE16 sans ALV, SE38 exécuté) n'y
  figure pas, et `Get List Rendering Status` rend `accessibility_mode_needed`
  vrai sur une grille comme sur un éditeur (scénario 18). Une vraie mesure du
  poste demande une liste ABAP classique ET un keyword qui distingue les
  sous-types de shell. (Le soir : le préflight lit les sous-types et ne
  déclare plus le mode accessibilité sur une `GridView`, scénario 18 en forme
  couverte. Puis, plus tard le même soir, une VRAIE liste classique a été
  observée, la liste SE16 standard : elle est rendue en labels, sans shell,
  et se lit par `Read Abap List` sans aucun réglage de poste (scénario 19).
  Le cas « shell opaque sans label » qui justifiait le préflight n'a donc
  toujours PAS été observé sur ce poste : il reste asservi par un test
  unitaire, et la note historique de RSPARAM visait en réalité une
  `GridView`.)

## Écarts constatés à la génération

Relevés le 2026-09-07 par sap-generator, sur la même cible (A4H 1909, mandant
001, DEVELOPER, SAP GUI 8.00, session EN), suite validée live 19/19 avec les
verdicts du plan. Aucun écart ne change un verdict ; deux changent la
REPRODUCTION d'un manque (le plan avait relevé un motif d'échec que la suite
n'observe pas dans les mêmes conditions), un écart est un fait d'écran nouveau
(retour à l'accueil), les autres précisent une assertion.

1. **Scénario 3, `Select Node` sur la clé `Favo`.** Le plan attend une
   `AttributeError: Property '<unknown>.selectedNode' can not be set`. Dans la
   suite, l'appel PASSE, deux fois (avant et après la sélection de « Plain
   ABAP » avec développement). L'échec du plan avait pourtant été relevé lui
   aussi par un run `robot` sur le thread principal (preuve `P01.select_node_kw`
   de la passe 1), juste après une lecture COM directe des clés de l'arbre : le
   comportement est donc INTERMITTENT ou dépendant de l'ordre des accès, pas
   un artefact cross-thread, et c'est précisément ce que « fragile » veut dire
   dans le titre. Ce que fait la suite : elle tente les deux appels SOUS FILET,
   consigne leurs issues en preuve, et prouve le manque par l'aveuglement
   (aucun keyword ne relit le nœud sélectionné ni ne sélectionne par chemin de
   textes : absence de `Get Selected Tree Node` et de `Select Tree Node By
   Path`). Verdict `gap` inchangé ; le titre du scénario est conservé ; le
   keyword de remplacement devra passer par `SelectNode(clé)` et échouer en
   nommant clé et type d'arbre, quelle que soit la cause de l'intermittence.
2. **Scénario 9, `Pick F4 Value` sur le calendrier.** Le plan attend un
   `com_error` brut (exception 634) : c'est ce que rend le keyword quand le
   calendrier est DÉJÀ ouvert par un F4 préalable (preuve `P03.f4.pick_f4` de la
   passe 1, run `robot`). Appelé calendrier fermé, le keyword ouvre l'aide
   lui-même et échoue par sa propre assertion, « Aucune entrée '01.09.2026' dans
   l'aide F4 de '...'. Valeurs visibles (extrait) : aucune lisible », puis
   referme le popup (F12). Le manque est intact dans les deux ordres (l'échec
   ne nomme jamais le calendrier, aucun `Pick Calendar Date`) ; la suite
   reproduit le second, le seul qui teste le keyword dans son contrat (il gère
   l'ouverture de l'aide), et le premier reste documenté ici.
3. **Scénario 6, remise à blanc de la combo « Or after event ».** Le plan
   prévoit de « remettre la valeur initiale ». Par `Select From List By Label`,
   ni `${SPACE}` ni `${EMPTY}` ne re-sélectionnent l'entrée initiale (clé ` `,
   texte vide) : `AttributeError: Property '<unknown>.value' can not be set`.
   C'est le manque par clé lui-même, vu depuis l'autre côté, et la suite
   l'asserte comme tel. La réversibilité est constatée autrement, et c'est un
   fait mesuré : l'écran de sélection SM37 n'est PAS persistant (rouvrir SM37
   rend l'événement vide et la date du jour) ; le scénario 6 rouvre SM37 et
   relit la valeur initiale, le scénario 7 restaure en plus la date « From »
   explicitement avant de quitter.
4. **Retour à l'accueil.** `/n` depuis une transaction rend l'accueil, mais
   `/n` depuis l'accueil LUI-MÊME laisse l'écran vide `SAPMSYST/S000/40`, sans
   arbre (trois scénarios ont rougi sur ce point au premier run). De là,
   `Run Transaction SESSION_MANAGER` rouvre l'accueil sans modal (deux cycles
   vérifiés) ; le lancer DEPUIS l'accueil ouvre le modal « Cannot start
   transaction » (piège déjà documenté). Le page object ne lance donc le tcode
   que si l'arbre manque.
5. **Scénario 13, clés de `Read Grid`.** Les dicts rendus par `Read Grid` sont
   indexés par les TITRES de colonnes (« SET/GET Parameter ID »), pas par les
   ids techniques ; ceux-ci viennent de `Get Grid Column Ids` (`PARID`, `PARVA`,
   `PARTXT`). Le témoin couvert asserte les deux : ids techniques non vides et
   au moins une ligne lue.
6. **Scénario 5, valeur lue.** `Get Value` rend `Dialog`, texte localisé ; la
   suite n'asserte pas ce texte (convention #3) mais ce qu'il prouve : valeur
   non vide et DIFFÉRENTE de la clé `A`.
7. **Session rf-mcp pendant la génération.** Le serveur a reproduit l'artefact
   cross-thread décrit dans les points de vigilance : deux `execute_step`
   lancés en parallèle ont rendu `Get Open Windows = []` en PASS,
   `Get Screen Signature` a rendu `# screen ?`, puis `<unknown>.findById` a
   persisté malgré deux `Attach To Open Session 0 0`. Les étapes ont donc été
   vérifiées live par des sondes jetables jouées par `robot` sur le thread
   principal (la voie des passes de sondes du plan), puis par la suite
   elle-même. Le manque de bibliothèque à verrouiller hors SAP (perception qui
   rend une vue vide en PASS) reste celui du plan, et c'est la deuxième
   session d'agent de la journée qu'il fait dérailler : il est en tête du lot
   de correction.

### Lot de correction du 2026-09-07 (soir) : ce que le rejeu a montré

Relevé par le planner en portant les scénarios à leur forme couverte, sur la
même cible.

1. **Le registre a mesuré** : rejoué tel quel sur la bibliothèque corrigée,
   18 scénarios sur 19 ont rougi en nommant « capacité désormais couverte :
   mettre à jour le plan et le registre » (le 13e, témoin, est resté vert).
   C'est l'assertion reine du plan, vérifiée dans le sens qui compte.
2. **Deux clés distinctes, vide et blanc.** La combo « Or after event » de
   SM37 (et « Decimal Notation » de SU01) porte une entrée de clé `""` ET une
   entrée de clé `" "` ; poser `""` là où SAP attend `" "` sort en `com_error`
   « invalid argument ». La clé d'une entrée ne se normalise donc jamais à
   l'écriture (`sapfx_common.combo_box` la garde telle quelle, la
   correspondance sans blancs n'est qu'un repli quand elle est unique). Le
   scénario 6 restaure la clé initiale RELUE, jamais une constante.
3. **« Scheduled » n'existe pas à l'écran** : la case porte le texte propre
   `Sched.` (abrégé), et le moteur sémantique l'indexait déjà (`Find Element
   By Label    Sched.` résout la case). Le manque 15 était donc plus étroit
   que ne le disait le plan du matin : pas d'indexation manquante, mais des
   keywords de confort absents (`Select Checkbox By Label`...) et un message
   d'échec qui ne montrait pas les textes propres. Les deux sont livrés ; le
   texte `Sched.` vit dans le page object.
4. **Le tri n'est pas dans le menu contextuel de colonne de SE16** (mesuré :
   `&SORT_DSC` y est un argument invalide, même colonne sélectionnée) et la
   grille de SE16 n'a pas de barre propre : `Sort Grid By Column` échoue en
   nommant la barre d'application, et c'est ce que le scénario 12 asserte.
5. **La sortie de RSPARAM est une GridView** (1639 lignes) sur SAP GUI 8.00,
   pas une liste classique : le parcours ne contient AUCUNE liste ABAP
   rendue sans le mode accessibilité, donc `accessibility_mode_needed` reste
   inobservable en vrai sur cette cible ; la nouvelle logique (sous-type
   inconnu ou vide ET zéro label) est verrouillée en unitaire.
6. **Le rail STA ré-attache** : mesuré par une sonde en thread étranger, le
   moteur ré-acquis via la ROT puis `FindById("/app/con[0]/ses[0]")` lit la
   transaction là où l'accès direct sort en RPC_E_WRONG_THREAD (hresult
   -2147417842). C'est la voie implémentée dans `SapEccLibrary.session`
   (proxy par thread, `Attach To Open Session` reste la voie manuelle).
   Puis prouvé À TRAVERS rf-mcp le même soir, sans redémarrer le serveur :
   bibliothèque rechargée et instance hot-swappée, `Attach To Open Session
   0 0` en contexte, puis `Get Open Windows` hors contexte et un
   `execute_batch` (fenêtres + signature) sur un thread étranger ont rendu
   la pile réelle (`wnd[0]`, `SAP Easy Access`) et 165 lignes de signature
   portant `SESSION_MANAGER`, là où la session du matin rendait `[]` et
   `# screen ?` en PASS. `use_context=true` reste la consigne de session pour
   un serveur qui n'a pas encore rechargé la bibliothèque.
7. **La revue indépendante a durci trois assertions** (sap-verifier,
   `needs_human` sur la forme couverte) : la clé d'une combo est rendue
   TELLE QUELLE par `Get Combo Box Key` (elle retirait les blancs, ce qui
   rendait la restauration de `" "` invérifiable : scénario 6 asserte
   désormais que la clé initiale est le blanc) ; la case du scénario 15 est
   basculée vers l'état OPPOSÉ à l'initial (cocher une case déjà cochée ne
   mesurait rien) ; les scénarios 7 et 9 confrontent la date à la forme
   locale RELEVÉE (`01.09.2026`) et le 9 ne fait plus aucune saisie `Input
   Date` (l'attendu était produit par le keyword voisin, pas mesuré). Le
   registre porte enfin l'identité de la cible (système, mandant,
   utilisateur), et le page object a été apuré des mots-clés du matin qui
   reproduisaient les keywords hérités cassés.
8. **Troisième revue indépendante : `verified`** (sap-verifier, sur la forme
   corrigée et le run v6 : les onze corrections constatées dans les fichiers
   ET dans les preuves, conventions #1 et #3 tenues, aucun verdict ni aucune
   preuve affaiblis entre v5 et v6, table « Clés de registre » = suite =
   registre). Quatre réserves, aucune bloquante, et ce qui en est fait :
   (a) l'identité de cible ne prouve pas la RELEASE (les deux conteneurs du
   poste annoncent le même SID) : mesurer release et kernel en Suite Setup,
   backlog § 2.25 ; (b) la restauration de la date n'était vérifiée qu'au
   scénario 7 et jamais relue : `Restaurer La Date De Debut` (page object)
   asserte désormais le type de message ET la valeur relue, aux scénarios 7
   et 9, rejoué live ; (c) les clés d'onglet SU01 sont des libellés anglais
   (`Logon Data`, `Parameters`) : ce sont des NOMS de la carte du page
   object, rien n'est asserté contre l'écran, accepté tel quel ; (d) la
   preuve du rail STA à travers rf-mcp est un relevé de session consigné
   par l'auteur, sans artefact de résultats inspectable (`not_verified`
   pour cette seule sous-affirmation, dit tel quel dans la preuve du soir).
9. **Les trois lots restants du backlog (2.22, 2.24, 2.25) livrés le même
   soir, et deux scénarios de plus.** (2.25) `Get System Identity` lit
   release SAP_BASIS et kernel dans System > Status (page object : `Identite
   De La Cible` l'appelle, le registre porte `basis_release`/`kernel_release`,
   scénario 20 l'exerce) ; la sonde a établi que le menu System est
   l'avant-dernier et « Status... » l'entrée 11 sur six écrans, d'où une
   ouverture PAR POSITION vérifiée structurellement. (2.24) La liste SE16
   standard EST une liste classique et elle se lit en labels (scénario 19,
   `Use Standard List In Data Browser` / `Get Data Browser Output`) : le
   cas « shell opaque » n'a pas été observé. (2.22) Le registre est écrit et
   relu par `sapfx_common.artifacts` (`Write`/`Read Deterministic Artifact` :
   périmètre d'empreinte déclaré, empreinte recalculée à la relecture) ; la
   sérialisation canonique change l'empreinte des capacités par rapport aux
   runs v5 à v7 (même contenu, autre canonisation), ce que la preuve du soir
   dit. Aucun verdict antérieur ne bouge ; le registre passe à 20 clés.
10. **Quatrième revue indépendante : `verified`** (sur v8 : les trois
    scénarios ajoutés, la conformité des 20 clés, les dix-huit preuves
    identiques à v7, conventions #1 et #3 ; réserves (a) et (b) de la
    troisième revue réglées, (c) acceptée, (d) toujours déclarative). Quatre
    réserves nouvelles, non bloquantes, et ce qui en est fait : (1) un champ
    de statut absent du dialogue était vidé en silence : `Get System
    Identity` rend désormais `missing_fields` (par section lue, les champs
    non affichés), distinct de `unread` ; (2) la restauration de la date
    aux scénarios 7 et 9 vivait en corps de test : déplacée en `[Teardown]`
    (`Restaurer La Date De Debut Si Relevee`, sans effet si la date n'a pas
    été relevée), rejouée live ; (3) les docstrings de `Read Abap List` et
    `Get List Rendering Status` présentaient encore RSPARAM comme un shell
    opaque : reprises, Libdoc refaite ; (4) la cause du changement
    d'empreinte est désormais VÉRIFIABLE dans la preuve du soir : les
    capacités v7 re-hachées par le module générique et les capacités v8
    privées des deux clés neuves donnent la même empreinte.
