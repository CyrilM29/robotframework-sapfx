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

Les trois canaux sont des pairs : même vocabulaire au-dessus, rien de partagé
en dessous. Le canal API n'a aucun écran, et c'est bien pour cela qu'il compte :
la façon la moins coûteuse de préparer ou de recouper des données n'est pas de
piloter un écran.

Un test se lit de la même façon quel que soit le canal :

```robotframework
Go To Transaction    VA01          # ECC
Open App             Sales Order    # Fiori (phase 2) : même intention, bibliothèque différente
```

## Internals de la bibliothèque ECC (`src/SapEccLibrary`)

Composition par mixins au-dessus de la classe amont vendorisée :

```
SapEccLibrary(ConnectionKeywords, WaitKeywords, GridKeywords,
              PerceptionKeywords, DiagnosticsKeywords, HealingKeywords,
              SemanticKeywords, EmbeddedBrowserKeywords, SapGuiBase)
```

- **`_vendor/sapgui_base.py`** : `SapGuiLibrary` amont, renommée `SapGuiBase`,
  Apache-2.0 (voir `NOTICE`). Traitée en lecture seule ; jamais modifiée sauf lors d'une re-synchronisation.
- **Les mixins** (`keywords/_*.py`) sont listés *avant* la base dans le MRO, ainsi une méthode de mixin remplace une
  méthode de base portant le même nom, et les mixins peuvent appeler les keywords hérités via `self` :
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
    dérive est **localisée**, pas seulement détectée). Le canal pixels couvre
    exactement ce que l'API Scripting ne voit pas : rendu GuiShell opaque des
    listes, graphiques record-only.
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
- **`SapEccLibrary.py`** les assemble et redéfinit `run_transaction` pour une
  détection d'erreurs indépendante de la locale. `ROBOT_LIBRARY_SCOPE = SUITE` :
  les tests d'une suite partagent leur connexion COM, tandis que deux suites
  Robot normales reçoivent des instances isolées. Les limites rf-mcp sont documentées séparément.

Pourquoi des mixins plutôt qu'une sous-classe regroupant tout dans un seul fichier : chaque préoccupation (connexion,
attente, grille, perception, diagnostic, réparation) est testable de façon indépendante et re-synchronisable de façon
indépendante, et le diff par rapport à l'amont reste lisible d'un coup d'œil.

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

1. Les tests ne contiennent jamais d'identifiants SAP bruts : ceux-ci résident dans `resources/`.
2. Ne jamais utiliser `time.sleep` pour attendre SAP ; utiliser les keywords `Wait Until ...`.
3. Assertions indépendantes de la locale uniquement (type de *message*, pas *texte* du message).
4. Limiter le diff avec le vendeur amont à une ligne.
