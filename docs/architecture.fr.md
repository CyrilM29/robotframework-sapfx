> [🇬🇧 English](architecture.md) · **🇫🇷 Français**

# Architecture

## Deux paradigmes SAP, un seul vocabulaire de test

SAP expose deux univers d'automatisation qui ne partagent presque rien au niveau technique :

- **GUI Desktop (ECC, et le front-end SAP GUI de S/4HANA)** : piloté via l'
  **API de scripting SAP GUI**, une interface d'automatisation COM accessible depuis Python via
  `win32com`. Synchrone, adressage par identifiant (`wnd[0]/usr/txtRSYST-BNAME`).
- **Web (Fiori / S/4HANA / SAPUI5)** : une application navigateur pilotée via Playwright
  (bibliothèque Robot Framework Browser). DOM asynchrone, identifiants dynamiques.

Nous ne cherchons **pas** à unifier ces deux mondes en dessous. Nous les unifions **au-dessus**, dans Robot
Framework, où un keyword constitue l'abstraction :

```
          ┌───────────────────────────────────────────────────────────────┐
          │   Tests  (tests/robot/**/*.robot)                              │
          │   speak business language only                                 │
          └────────────────────────────┬──────────────────────────────────┘
          ┌────────────────────────────┴──────────────────────────────────┐
          │  Business keywords (resources/*.resource)                      │
          │  ecc_keywords  +  fiori_keywords  +  api_keywords              │  ← one vocabulary
          └───────┬─────────────────┬─────────────────────┬───────────────┘
      ┌───────────▼────────┐ ┌──────▼─────────────┐ ┌─────▼──────────────┐
      │  SapEccLibrary     │ │  SapFioriLibrary   │ │  SapApiLibrary     │
      │  COM / win32com    │ │  + Browser library │ │  stdlib HTTP       │
      └───────────┬────────┘ └──────┬─────────────┘ └─────┬──────────────┘
   SAP GUI Scripting API      SAPUI5 runtime (sap.ui.*)   OData v2/v4, RFC
```

Les trois canaux sont des pairs, et ils ne partagent aucun localisateur. Chaque
bibliothèque garde le localisateur de sa technologie : un id de scripting SAP GUI
(`wnd[0]/usr/ctxtDATABROWSE-TABLENAME`), un sélecteur de contrôle UI5
(`controlType=sap.m.SearchField`), un entity set OData. C'est voulu. Le canal API
n'a aucun écran, et c'est bien pour cela qu'il compte : la façon la moins
coûteuse de préparer ou de recouper des données n'est pas de piloter un écran ;
et un localisateur de plus petit dénominateur commun, le libellé affiché,
changerait avec la langue de connexion. Ce qui se partage en dessous, ce sont
des contrats, dans `sapfx_common` : une seule règle de complétude pour extraire
un tableau quel que soit le canal, une même identité de message (`MO/E/402`) à
l'écran et en RFC, et, pour les deux canaux à écran, la même boucle perception →
action et un même journal de réparation des localisateurs.

Le canal devient alors un choix de keyword métier. Dans ce test cross-canal,
chaque keyword est écrit dans un fichier de resources au-dessus d'une seule
bibliothèque (SE16 par le scripting SAP GUI pour le premier, un `$count` OData
pour le second), et le test ne nomme que le fait qu'il vérifie :

```robotframework
Product Count Is The Same On Screen And Through The API
    ${on_screen}=    Count Table Entries        ${EPM_PRODUCTS_TABLE}    # SAP GUI, SE16
    ${via_api}=      Count Business Entities    ${EPM_PRODUCTS}          # OData $count
    Should Be Equal As Integers    ${via_api}    ${on_screen}
```

## Internals de la bibliothèque ECC (`src/SapEccLibrary`)

Composition par mixins, sans classe de base (abrégé) :

```
SapEccLibrary(ConnectionKeywords, WaitKeywords, GridKeywords,
              PerceptionKeywords, DiagnosticsKeywords, HealingKeywords,
              SemanticKeywords, EmbeddedBrowserKeywords, ...,
              GridCellKeywords, ElementKeywords, InputKeywords,
              ValueCheckKeywords)
```

- **Les 37 keywords de robotframework-sapguilibrary** (Apache-2.0, voir
  `NOTICE`) vivent dans nos propres mixins depuis le 6 octobre 2026 :
  `_elements`, `_inputs`, `_value_checks`, `_grid_cells`, plus la connexion,
  les attentes et la capture sur erreur. Leur code, d'abord vendorisé tel
  quel, a été absorbé et réécrit (écritures relues, aucun focus déplacé par
  une vérification, la fenêtre SAP capturée au lieu de l'écran entier) ; leurs
  noms et signatures sont tenus par un test unitaire, donc les suites écrites
  pour la bibliothèque amont tournent sans modification. Voir
  [audit-upstream.fr.md](audit-upstream.fr.md).
- **Les mixins** (`keywords/_*.py`) portent chacun une capacité et s'appellent
  les uns les autres via `self` ; les quatre mixins des keywords absorbés
  ferment le MRO :
  - `_connection` : bootstrap autonome (Logon Pad, connexion avec retry, `CoInitialize`
    pour l'exécution hors thread principal, p. ex. rf-mcp).
  - `_waits` : vraie synchronisation (`session.Busy` + polling d'éléments) ; les échecs
    ajoutent des **suggestions de correspondances proches** (scorées par
    `sapfx_common.healing`) pour qu'un agent (ou un humain) puisse auto-corriger un
    identifiant presque juste.
  - `_grid` : ergonomie ALV (par *titre* de colonne, `Read Grid` → liste de dicts,
    adressage de ligne par **contenu** avec `Get Cell Value By Row Content`), plus
    `Read Abap List` pour les sorties liste classiques (aucun objet grille
    scriptable : lignes reconstruites géométriquement depuis les labels positionnés).
  - `_perception` : `Get Screen Signature` (vue texte en lecture seule de l'écran
    actif ; `mode=diff` ne retourne que ce qui a changé depuis la perception
    précédente ; `pair_renames=True` le transforme en **diff intelligent** :
    les lignes disparues/apparues dont les ids se ressemblent au sens du
    scoring de healing sont appariées en une seule ligne `~ ancien -> nouveau`,
    un sous-écran renuméroté se lit comme un renommage, pas comme quarante
    changements ; `mode=semantic` retourne la **vue formulaire** : une ligne
    par cible actionnable avec son libellé humain *vérifié* à côté de l'id
    technique, la perception qu'un agent rejoue directement en
    `Fill Field By Label` ; colonne géométrie optionnelle). Passe par le
    **chemin rapide** `GetObjectTree` (un appel COM pour tout le sous-arbre)
    avec repli automatique sur la marche COM nœud par nœud. Également les
    captures en mémoire (`Get Screenshot As Base64`, `Log Screenshot` :
    data-URI inline dans le log Robot), le **screenshot annoté**
    (`Get/Log Annotated Screenshot`, façon Set-of-Mark : boîtes numérotées sur
    chaque cible actionnable + légende `numéro -> id` ; un agent à vision lit
    le numéro et donne l'id à un keyword déterministe au lieu de deviner des
    coordonnées) et les **assertions visuelles** (`Get Screen Perceptual
    Hash`, `Screen Should Match Baseline` : sémantique snapshot sur un dHash
    pur, `sapfx_common.visual_hash` + `sapfx_common.visual_baseline` partagé ;
    Pillow seulement à la frontière image, extra optionnel `visual` ;
    `mask_elements=auto` neutralise avant hachage les barres de statut/titre,
    légitimement volatiles). Le canal pixels gagne trois outils de précision :
    `Get Element Perceptual Hash` / `Element Should Match Baseline` (la grille
    du hash couvre la région recadrée d'UN élément : un changement dans un
    GuiShell opaque pèse sur les 64 bits au lieu d'être dilué dans l'écran) et
    `Get Screen Tile Hashes` (une empreinte par tuile d'une grille 4×4 : la
    dérive est **localisée**, pas seulement détectée). Une empreinte
    perceptuelle encode la **géométrie de capture** autant que le contenu :
    `per_resolution=True` garde une baseline committée par géométrie
    (`<name>@1920x1032.png`), donc une même suite reste comparable sur des
    postes qui n'affichent pas la même taille ; sans l'option, un échec dont
    les deux géométries diffèrent le dit, au lieu de se lire comme une
    régression fonctionnelle. Le canal pixels couvre exactement ce que l'API
    Scripting ne voit pas : rendu GuiShell opaque des listes, graphiques
    record-only.
  - `_diagnostics` : **préflight** scripting (`Get Scripting Status`,
    `Scripting Should Be Fully Enabled`, soit un échec précoce avec le paramètre RZ11 exact à
    corriger), `Enable Test Tool Mode`, `Get Session Telemetry`.
  - `_healing` : **auto-réparation** de localisateurs (`Resolve Element With Healing` :
    répare au-dessus d'un seuil de similarité avec un WARNING journalisé, jamais en
    silence ; une ancre ``label=`` ajoute une voie de réparation par libellé, car un
    libellé visible survit aux renumérotations de sous-écrans qui tuent les ids ;
    `Get Closest Element Ids`). Le scoring pur vit dans `sapfx_common.healing`.
  - `_semantic` : **localisateurs humains** (portés de RoboSAPiens, Apache-2.0 ;
    voir `NOTICE`) : `Find/Fill/Read Field By Label`, `Click Button By Label`
    ciblent les contrôles comme un utilisateur métier les décrit (libellé
    visible + proximité géométrique ; grammaire `Libellé`, `@ Libellé`,
    `Gauche @ Haut`, `= contenu`, positions de grille `N @ Libellé` /
    `Libellé @ N`, et la portée `Ancre >> Reste` : résolution réduite au
    voisinage d'un libellé unique, rayon exposé en paramètre d'intention
    `scope_radius`, échecs diagnostiqués par `scope_hint`). Différence assumée
    avec RoboSAPiens : l'ambiguïté est **détectée et remontée avec la liste des
    candidats**, jamais tranchée en silence au premier match. La saisie ne
    cible que des champs modifiables (le séparateur « to » en lecture seule
    n'est jamais une position de grille) ; la lecture préfère les champs
    modifiables puis replie sur la lecture seule (dynpros d'affichage). Les
    ids restent le chemin nominal dans `resources/`.
  - `_embedded_browser` : le **pont contrôle-navigateur-embarqué** (WebView2/CDP,
    workflow documenté par RoboSAPiens ; voir `NOTICE`) : `Enable Embedded
    Browser Debugging` avant le démarrage du client SAP, puis `Switch To
    Embedded Browser Page` confie la page hébergée par un contrôle WebView2
    d'une fenêtre SAP GUI/Business Client à la **bibliothèque Browser via
    CDP** : les deux canaux du projet reliés dans une même suite.
  - `_pointer` : l'**effecteur coordonnées**, l'hybride « déterministe
    d'abord, geste matériel en dernier recours » pour ce que l'API Scripting
    ne scripte officiellement pas (intérieur des GuiShell opaques, graphiques
    record-only, drag & drop) : `Get Element Screen Region` donne la
    géométrie écran réelle (la moitié perception : un agent la croise avec
    `Get Screenshot As Base64` pour décider *où*), `Click Element At Offset`
    exécute un clic win32 matériel à une position **relative à l'élément**
    (survit aux déplacements de fenêtre ; journalisé, jamais silencieux).
    Les ids et libellés restent le chemin nominal.
  - `_trees`, `_combobox`, `_menus`, `_grid_actions`, `_windows` (2026-09-07,
    le lot qui a fermé le registre de capacités SAP GUI) : **arbres**
    (`Read Tree Nodes`, `Select Tree Node By Text`/`By Path`, clés opaques
    conservées telles quelles, arbres à colonnes lus par leur colonne
    `TEXT`), **combo box par clé technique** (`Select Combo Box Entry By
    Key`, `Get Combo Box Entries`) plus les **formats de l'utilisateur**
    (`Get User Formats` depuis SU3, `Input Date` et `Input Number` qui
    convertissent une entrée ISO/technique en ce que le dynpro accepte), la
    **barre de menus par chemin** (`Select Menu Item`), les **actions de
    grille** au-delà de la lecture (`Double Click Grid Cell`, menu contextuel
    par code fonction, inventaire de la barre, `Sort Grid By Column`) et les
    **fenêtres modales** (`Dismiss Modal Window` : plusieurs dialogues SAP
    refusent `sendVKey`, les replis pressent le bon bouton et la disparition
    est vérifiée). La perception elle-même affiche `GuiShell/<SubType>`,
    refuse de servir un ProgID en guise de valeur, et ÉCHOUE en nommant la
    cause quand la session est illisible au lieu de rendre une vue vide ; le
    rail STA ré-attache la session par thread. Logique pure dans
    `sapfx_common.tree_nodes`, `menu_path`, `combo_box`, `user_formats`.
  - `_identity` (le même soir) : **l'identité du système lue à l'écran**
    (`Get System Identity`, `System Identity Should Be`), le miroir SAP GUI
    du `Read System Identity` du canal RFC : « System: Status » ouvert PAR
    POSITION (le menu System est l'avant-dernier, « Status... » son entrée
    11 sur les six écrans mesurés) et vérifié structurellement, puis le popup
    du kernel et la grille « Installed Software » dont la ligne `SAP_BASIS`
    porte LA release ABAP. Deux systèmes du laboratoire partagent SID et
    hôte ; seuls release et kernel les distinguent. Les sections illisibles
    sont NOMMÉES (`unread`), jamais remplacées par une valeur plausible.
    Logique pure dans `sapfx_common.system_identity`. Le mixin SE16 gagne
    l'inverse du réglage ALV (`Use Standard List In Data Browser`, une liste
    classique rendue en labels et lue par `Read Abap List`) et `Get Data
    Browser Output`.
  - `_statusbar`, `_tabstrip`, `_toolbar` (2026-09-08, le lot qui a fermé le
    registre de capacités d'une SECONDE release, ABAP Platform 2023) :
    l'**identité d'un message** (`Get Status Message Identity` :
    classe/type/numéro, `MO/E/402`, vide quand rien n'est affiché ; `Status
    Message Should Be`, deux refus de type E du même écran distingués sans un
    mot localisé), les **onglets par clé technique** (`List Tabs`, `Get
    Selected Tab`, `Select Tab`, `Select Tab By Label`, sélection relue ; le
    jeu d'onglets diverge entre releases) et l'**inventaire de la barre
    d'application** (`List Toolbar Buttons`, `Click Application Toolbar
    Button`, les noms d'icône comme ancres locale-safe). Le même lot fait
    RÉSOUDRE l'entrée « Status... » par `Open System Status` (avant-dernière
    entrée de l'avant-dernier menu, un dialogue exigé : l'indice 11 gravé
    cliquait « Log Off » sur la 758) et fait lire le sous-type du shell aux
    deux résolveurs de contrôle : un arbre à colonnes n'est plus pris pour une
    ALV, un shell feuille est refusé en nommant son lecteur, un splitter est
    traversé, et aucun lecteur ne laisse plus fuir une erreur COM brute.
    Logique pure dans `sapfx_common.status_message`, `tab_strip`, `menu_path`.
  - `sapfx_common.artifacts` (le même soir, importable comme bibliothèque
    Robot) : l'**artefact déterministe générique**, JSON trié à périmètre
    d'empreinte DÉCLARÉ, empreinte recalculée à la relecture (un artefact
    édité après coup est refusé), différences nommées par chemin à la
    comparaison ; premier consommateur : le registre de capacités.
  - La campagne du rôle de partenaire commercial (du 2026-09-26 au 28,
    transaction BP sur A4H) a comblé sept manques dans la bibliothèque
    elle-même : sélection de combo relue sur l'élément RÉ-ACQUIS par son id
    (une combo à code fonction reconstruit l'écran pendant la sélection, et
    l'ancien proxy lève) ; `Element Is Changeable` et ses deux assertions (le
    MODE d'un écran lu sur un champ, puisque le titre est traduit et que F6
    est une bascule) ; `Element Is Present` (une sonde de présence qui ne
    capture jamais l'écran) ; une session FERMÉE reconnue par `Wait Until Busy
    Done`, qui échoue tout de suite en `SessionDisconnectedError`, et prise
    pour son succès par `Run Transaction    /nex` ; `field:<NOM>` pour les
    colonnes d'un table control ; le repli de ligne des localisateurs humains
    (le champ le plus proche sur la même ligne quand un libellé court laisse
    un blanc, rien entre les deux, 100 px à l'échelle) ; et `Open Sap Logon`
    sans capture à chaque sonde prématurée. Côté RFC, le pattern BAPI passe
    dans son propre mixin `_bapi.py` (`accept=` pour tolérer un refus nommé
    par identifiant de message, `Bapi Should Fail With Message Id` pour
    l'asserter), `Read Rfc Table` refuse un champ RAW (rendu tronqué de
    moitié), et `Filter Change Documents` / `Latest Change Number` énoncent
    une assertion d'audit hors ligne.
  - Le mixin de perception héberge aussi la **sentinelle de dérive**
    (`Check Screen Against Watch` sur le pur `sapfx_common.screen_watch`) :
    les écrans surveillés sont mémorisés (signature structurée + empreinte
    visuelle optionnelle + empreintes par tuile) et chaque passage suivant ne
    remonte QUE ce qui a bougé : la détection de changement **sans un seul
    test scripté** (`tests/robot/ecc_drift_sentinel.robot` est le harnais de
    veille nocturne). Trois canaux par écran : le diff structurel intelligent
    (renommages appariés, changements de valeur nommés), le hash visuel
    global, et la **grille de tuiles** : une dérive locale trop diluée pour le
    hash global est rattrapée par SA tuile et rapportée avec sa position, son
    rectangle en pixels et les éléments qui la recouvrent.
    `per_resolution=True` donne à chaque géométrie de capture ses propres
    références VISUELLES, le canal structurel restant partagé : une signature
    d'écran ne dépend pas de la résolution, une empreinte perceptuelle si.
    Sans l'option, une dérive visuelle entre deux géométries différentes est
    annotée comme pouvant n'être qu'un changement d'échelle.
- **`SapEccLibrary.py`** les assemble et redéfinit `run_transaction` pour une
  détection d'erreurs indépendante de la locale. `ROBOT_LIBRARY_SCOPE = SUITE` :
  les tests d'une suite partagent leur connexion COM, tandis que deux suites
  Robot normales reçoivent des instances isolées. Les limites rf-mcp sont documentées séparément.

Pourquoi des mixins plutôt qu'une sous-classe regroupant tout dans un seul fichier : chaque préoccupation (connexion,
attente, grille, perception, diagnostic, réparation) est testable de façon indépendante, et aucun fichier ne
dépasse la limite de taille du dépôt en accumulant des keywords sans rapport.

**`src/sapfx_common/`** est la couche partagée par les *deux* canaux : `polling`
(toutes les boucles d'attente/retry), `com_safety` (`ensure_com_initialized`),
`healing` (le scoring de similarité de localisateurs ECC↔Fiori), `perception_diff`
(le diff ligne à ligne derrière les deux perceptions `mode=diff`, y compris le
diff intelligent `pair_renames` qui réutilise le scoring de healing),
`object_tree` (l'aplatissement du JSON `GetObjectTree`, le modèle de
perception structuré), `semantic` (la résolution géométrique par libellé +
l'inverse vérifié `describe_element` utilisé par le recorder et par la vue
affordances `mode=semantic`), `abap_list` (la reconstruction géométrique des
listes ABAP classiques), `visual_hash` (le dHash perceptuel pur derrière les
assertions visuelles, plus les primitives crop/masque/tuiles) et
`visual_baseline` (la sémantique snapshot partagée des baselines et la
frontière de décodage Pillow, utilisée par les keywords visuels ECC **et**
Fiori : `Ui5 Screen Should Match Baseline` est le même cycle sur une capture
Browser). Toute nouvelle primitive trans-canal va là, jamais en inline.

## Le canal API (`src/SapApiLibrary`)

Le troisième canal, à côté du GUI desktop et du web : un test SAP robuste
**prépare et recoupe ses données par l'API** et ne pilote l'écran que pour ce
qu'il teste vraiment : le setup/teardown GUI est lent et fragile, l'API est
rapide et déterministe. `SapApiLibrary` est volontairement en **stdlib pure**
(aucune dépendance nouvelle à épingler) : OData **v2** (la Gateway embarquée
d'ECC/S4) et **v4** (CAP, S/4 moderne) derrière un seul jeu de keywords
(`Open Api Session` par alias, `Get Odata Entities`, `Get Odata Count`,
`Post Odata` avec le protocole de token **CSRF** SAP), plus le RFC optionnel
via `pyrfc` quand il est installé. Les échecs HTTP sont auto-corrigibles
(statut, URL effective, extrait du corps).

Le patron canonique est la **suite flagship cross-paradigme**
(`tests/robot/flagship_cross_paradigm.robot`) : le même fait métier vérifié par
deux canaux indépendants. Validé live sur A4H : le « Number of Entries » SE16
de `SNWD_PD` égale le `$count` du service Gateway `SEPMRA_SHOP/Products` du
même système. Une divergence signale un service qui filtre ou une donnée
fantôme, ce qu'aucun canal seul ne peut détecter.

Boucle de maintenance au-dessus de la télémétrie de healing :
`scripts/healing_drift_report.py` relit le journal cumulatif
`SAPFX_HEALING_LOG`, sépare les dérives **stables** (même localisateur réparé
plusieurs fois vers LA même cible : le patch de `resources/` est localisé et
proposé, `--apply` l'exécute) des **instables** (examen humain ou sap-healer),
et sort en code non nul comme signal d'alerte CI. Le healing devient de la
maintenance préventive, et il ne touche jamais les tests.

## Les Recorders (`tools/recorder`, `tools/recorder_web`)

`tools/recorder/sapgui_recorder.py` travaille sur la **même** connexion COM que la
bibliothèque, de sorte que tout identifiant qu'il remonte se résout de manière
identique à l'exécution. Modes : dump, `--highlight`, capture par clic
(`--capture`), inspecteur au survol (`--hover`) et un **recorder** de flux
(`--record`) qui transcrit les manipulations en séquence de keywords rejouable.
`--engine auto|native|poll` sélectionne le moteur du record : **natif** s'abonne
aux événements de l'API de scripting elle-même (`Session.Record` + `Change`, le
mécanisme derrière ALT+F12) et transcrit la commande *exacte*, y compris les clics
de boutons, actions de grilles et d'arbres invisibles au polling ; il replie
automatiquement sur le **polling** (diff de signature d'écran entre allers-retours)
quand le profil serveur désactive l'enregistrement. Avec `--semantic` (moteur
natif), chaque étape est réécrite en **keyword humain** (`Fill Field By Label
Table Name    T000`) quand le libellé calculé au moment de l'événement re-résout
de façon prouvée vers ce même élément ; l'id technique reste en commentaire de
fin de ligne : l'enregistrement parle le langage de `resources/` (règle de
conception n° 1) au lieu de livrer des ids à retravailler. Les vkeys connus
reçoivent un commentaire lisible (`# F8`), et `--screenshots` préfère désormais
le `HardCopyToMemory` de l'API de scripting (image fidèle de la fenêtre, même
recouverte) au repli GDI. Voir `tools/recorder/README.fr.md`.

Le pendant web (`tools/recorder_web/` : snippet DevTools + extension MV3) est
généré depuis le bundle de résolution de `SapFioriLibrary` : la capture ne diverge
jamais de la résolution. Voir [fiori-architecture.fr.md](fiori-architecture.fr.md).

## WebView2 embarqué dans SAP GUI (implémenté)

Les builds récents de SAP GUI embarquent de plus en plus de contrôles
**WebView2** (Edge) dans le client lourd : des écrans que l'API COM de scripting
ne voit que comme un shell opaque. Ces pages embarquées sont des cibles Chromium
ordinaires : le mixin `EmbeddedBrowserKeywords` active leur débogage distant
(`Enable Embedded Browser Debugging`, à appeler **avant** le démarrage du
client SAP, car WebView2 lit la variable d'environnement à la création du
contrôle), puis `Switch To Embedded Browser Page` retrouve la page hébergée
par son titre dans le catalogue de la bibliothèque Browser via **CDP** et en
fait la page active : tous les keywords Browser suivants (`Click`,
`Fill Text`, `Get Text`…) pilotent le contenu embarqué sans jamais quitter la
suite ECC. Le chemin CDP (connexion, sondage du catalogue, bascule de page,
clic aller-retour) est validé live contre un vrai point de terminaison
DevTools Edge ; le prérequis restant sur un vrai SAP GUI est l'option poste
*Browser Control = Edge*. RoboSAPiens documente la même voie (voir `NOTICE`).

## Règles de conception

1. Les tests ne contiennent jamais d'identifiants SAP bruts : ceux-ci résident dans
   une couche de resources métier (`resources/`). Cette couche est le vocabulaire
   métier d'**une** installation, écrit pour votre cible et votre métier ; la
   moitié universelle, c'est `src/`, les bibliothèques, qui portent les capacités.
2. Ne jamais utiliser `time.sleep` pour attendre SAP ; utiliser les keywords `Wait Until ...`.
3. Assertions indépendantes de la locale uniquement (type de *message*, pas *texte* du message).
4. Garder la surface de robotframework-sapguilibrary : ses 37 keywords gardent
   leur nom et leur signature.

## Marques

SAP, SAP ECC, SAP S/4HANA, SAP Fiori, SAP BTP, SAP HANA, SAP NetWeaver, SAP
GUI, SAPUI5, ABAP et les autres produits et services SAP cités sont des marques
commerciales ou des marques déposées de SAP SE ou de ses sociétés affiliées en
Allemagne et dans d'autres pays. SAPFX est un projet open source indépendant,
sans affiliation, parrainage ni approbation de SAP SE.
