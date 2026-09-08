# Exploration en profondeur du Demo Kit OpenUI5 : Documentation, fiches d'API, galerie d'échantillons, Demo Apps

- **Canal** : Fiori (web)
- **Système / URL** : Demo Kit public **OpenUI5 SDK**, `https://sdk.openui5.org/`.
  Application SAPUI5 mono-page à routage par hash (`#/...`), runtime SAPUI5
  **1.152.0** (relevé live le **2026-09-05**, shell en UI5 Web Components
  depuis ce SDK). Aucune authentification, aucune donnée métier, cible
  publique.
- **Préconditions** :
  - Accès réseau à `sdk.openui5.org`.
  - Bannière de consentement TrustArc à accepter (keyword existant
    `Accepter Le Consentement Cookies` du page object, moteur `dom`,
    idempotent, apparition APRÈS le runtime).
  - **LECTURE SEULE.** Le seul réglage touché (case « borrowed properties »
    d'une fiche d'API) est remis en état par le scénario ET par un teardown
    qui s'exécute même sur échec. Aucun téléchargement, aucun onglet externe
    ouvert (les boutons qui le feraient sont perçus, jamais actionnés).
  - Navigateur headless PARAMÉTRABLE (`${DEMOKIT_HEADLESS}`, même variable
    que la campagne sœur ; l'exploration de ce plan a été menée headless).

Cette campagne est **complémentaire** de
`specs/openui5-demokit-navigation-interaction.md` (validée 12/12, re-validée
le 2026-09-05) : elle n'y reprend ni les onglets/routes, ni la recherche
globale, ni l'arbre de l'API filtré, ni le menu Options/thème, ni
l'étanchéité de l'iframe d'échantillon. Elle couvre ce que la campagne
existante ne touche pas : la section **Documentation** (`#/topic`), les
fiches d'API **au-delà de la table des propriétés** (méthodes, événements,
agrégations, éléments empruntés, bascules « borrowed »), la **galerie
d'échantillons** (`#/entity/...`) avec sa **vue du code source**, et les
pages **Demo Apps** / **Resources** en perception seule. Elle réutilise le
page object `resources/page_objects/openui5_demokit.resource` (ouverture,
consentement, perception, navigation par clés) et l'étend.

## Perception métier

- **Personas** : `@fiori` (canal) + `@basis` (cible technique transverse,
  lecture seule), fiches lues dans `PERSONAS.md`.
- **Où se lit la vérité** : le **registre UI5** et ses clés techniques,
  jamais le rendu : `target` des nœuds d'arbre (GUID hexadécimal de sujet,
  nom qualifié d'entité), **contextes de liaison** (`/entity/samples/<n>`,
  `/ui5-metadata/properties|aggregations/<n>`, `/borrowed/methods/<n>`),
  routes de hash, `selectedKey` des conteneurs d'onglets, `key` des onglets
  de fichier de la vue code (tout cela **vérifié live** le 2026-09-05). Pour
  les tables méthodes/événements, la vérité technique vit dans les **liens
  DOM relatifs** (`api/<classe>#methods/<nom>`), le contexte de liaison y
  étant absent (vérifié live, voir vigilance).
- **Risques métier priorisés** :
  1. le « vert et faux » des lectures NON PORTÉES : cette SPA **accumule**
     les vues visitées (511 contrôles à l'ouverture, 5442 après le tour
     complet, mesuré) et garde l'iframe d'échantillon vivante après l'avoir
     quittée ; toute lecture globale compte du contenu d'autres sections ;
  2. la documentation qui divergerait du runtime réellement servi (l'écart
     doc ↔ contrôle vivant, couvert par l'assertion reine) ;
  3. la dérive rapide de la cible publique (le shell est passé aux Web
     Components en quatre jours, fiche
     `memory/demokit-shell-passe-aux-web-components.md`) : les scénarios
     s'ancrent sur les ids stables et les clés, et journalisent la version ;
  4. la localisation instable (langue mixte re-mesurée ce jour : instantané
     ARIA portant des libellés français ET des onglets anglais sur la même
     page ; fiche `memory/la-langue-peut-basculer-en-cours-de-run.md`).
  **Hors périmètre, dit** : le contenu rédactionnel des sujets de
  documentation (prose non testable et non traduite) ; les interactions DANS
  l'iframe d'échantillon (portée déjà couverte par la campagne existante) ;
  les Demo Apps elles-mêmes (des cibles séparées, perçues sans être
  ouvertes) ; le téléchargement d'un échantillon (écriture disque, interdit
  en lecture seule).
- **Assertion reine** : la **documentation complète décrit exactement le
  runtime servi** : bascule « borrowed properties » activée, l'ensemble des
  noms techniques documentés de la table des propriétés est ÉGAL (égalité
  stricte des ensembles, plus seulement une inclusion) à l'ensemble des
  propriétés d'une instance vivante du contrôle (12 propres + 6 empruntées =
  18 = 18, mesuré sur `sap.m.Button`). Portée par le scénario 6.
- **Réversibilité** : lecture seule de bout en bout ; la seule bascule
  touchée est remise dans son état RELEVÉ (constaté sur la propriété
  `selected`, jamais sur une mesure dérivée), dans le scénario et dans le
  teardown ; les pages supplémentaires éventuelles sont refermées ; le
  navigateur est fermé en Suite Teardown sur toutes les branches.

## Données observées

Relevé live le **2026-09-05**, exploration pilotée par rf-mcp (Browser +
SapFioriLibrary), Chromium **headless**, viewport 1600x950. SDK servi :
**SAPUI5 1.152.0** (`Get Page Composition` : `ui5_runtime=True`,
`wc_hosts=68` dont 26 en light DOM, `webgui_elements=0`, moteurs
`['role', 'xpath', 'wc', 'dom']`, 511 contrôles sur l'accueil à froid).

### Section Documentation (`#/topic`)

- Le panneau maître est le miroir de celui de l'API : arbre
  `sdk---topicMaster--tree` (1 correspondance), champ de filtre
  `sdk---topicMaster--searchField` (1), nœuds
  `sap.ui.documentation.DemokitTreeItem`.
- **9 nœuds racine** (arbre replié), dont le `target` est un **GUID
  hexadécimal de 32 caractères** (le « loio » stable du sujet), PAS un nom
  qualifié : `ec699e0817fb46a0817b0fa276a249f8` (Essentials),
  `68b9644a253741e8a4b9e4279a35c247` (Data Binding),
  `99ac68a5b1c3416ab5c84c99fefa250d` (What's New)... Les `title` sont de la
  prose anglaise (contenu documentaire, à journaliser seulement).
- Le clic sur un nœud **navigue ET déplie** : fragment
  `/topic/<guid>`, arbre passé de 9 à 30 nœuds sur Essentials, puis titre de
  document `Essentials - Documentation - Demo Kit - OPENUI5 SDK` ;
  `selectedKey` du conteneur d'onglets = `topic`.
- **Deux vues de détail portent le suffixe `topicDetailPage`** :
  `sdk---topicDetailInitial--topicDetailPage` (l'écran d'accueil de la
  section) et `sdk---topicDetail--topicDetailPage` (le sujet réel). Un
  `idSuffix=topicDetailPage` rend 2 correspondances : ancrer sur
  `topicDetail--topicDetailPage`.
- **Les liens croisés du contenu sont des ancres DOM RELATIVES, sans
  `#/`** : `topic/<guid>`, `api/<nom.qualifié>`,
  `api/<classe>#methods/<nom>` (relevés sur le sujet Data Binding :
  `api/sap.ui.model.BindingMode`,
  `api/sap.ui.model.odata.v4.ODataListBinding#methods/create`...). Le clic
  sur `api/sap.ui.model.BindingMode` a navigué vers
  `#/api/sap.ui.model.BindingMode`, titre
  `sap.ui.model.BindingMode - API Reference - ...`, et `selectedKey` est
  passé de `topic` à `api`.

### Fiche d'API en profondeur (`#/api/sap.m.Button`)

- 7 rubriques `sap.uxap.ObjectPageSection` aux idSuffixes connus
  (`overview`, `constructor`, `controlproperties`, `aggregations`,
  `associations`, `events`, `methods`).
- **Sous-navigation par lien de méthode/événement** : cliquer le lien DOM
  `api/sap.m.Button#events/press` donne le fragment
  `/api/sap.m.Button%23events/press` (le second dièse est ENCODÉ `%23` dans
  le hash) et le `selectedKey` de la barre d'ancrage (`sap.m.IconTabHeader`
  dans `apiDetailObjectPage`) devient `__xmlview1--events` : le préfixe de
  vue est GÉNÉRÉ, l'assertion porte sur le SUFFIXE `--events`.
  `selectedSectionId` n'est pas une propriété de l'`ObjectPageLayout` de
  cette version (association) : le témoin est la barre d'ancrage.
- **Trois cases « Show borrowed ... »** (properties / aggregations /
  associations) vivent dans la fiche, aux ids GÉNÉRÉS (`__box9`...) : elles
  s'ancrent par `controlType=sap.m.CheckBox` + `containedIn=<rubrique>`
  (exactement 1 par rubrique). **État par défaut relevé :
  `[False, True, False]`, la case des AGRÉGATIONS est cochée d'origine.**
- **Table des propriétés** (rubrique `controlproperties`) : 12 lignes par
  défaut, chaque ligne porte un contexte de liaison
  `/ui5-metadata/properties/<n>` aux clés `name`, `defaultValue`, `group`,
  `visibility`, `since`, `typeInfo`. **Après bascule de la case : 18
  lignes**, les 6 nouvelles (`blocked`, `busy`, `busyIndicatorDelay`,
  `busyIndicatorSize`, `fieldGroupIds`, `visible`) portant la clé
  supplémentaire **`borrowedFrom`**. 18 = exactement le nombre de propriétés
  du contrôle vivant lu au registre. Case remise à `False`, re-vérifiée.
- **Table des agrégations** : contextes de liaison
  `/ui5-metadata/aggregations/<n>` aux clés `name`, `singularName`, `type`,
  `cardinality`, `visibility`, et `borrowedFrom` sur les entrées héritées
  (`customData` empruntée à `sap.ui.core.Element`) : cohérent avec la case
  cochée par défaut.
- **Tables des méthodes et des événements : `binding: None` sur toutes les
  lignes** (44 lignes methods, 2 lignes events sur `sap.m.Button`). La voie
  du contexte de liaison, correcte pour propriétés/agrégations, ne rend RIEN
  ici : les noms techniques se lisent sur les liens DOM
  `api/sap.m.Button#methods/<nom>` / `#events/<nom>` dans la portée de la
  rubrique (relevés : `press`, `tap`, `addAriaDescribedBy`...).
- **Éléments empruntés (Borrowed)** : 7 `sap.ui.documentation.BorrowedList`
  sur la fiche, dont **5 dans la rubrique `methods`**, chacune liée à
  `/borrowed/methods/<n>` avec `object.name` = l'ancêtre : la chaîne
  d'héritage complète en clés techniques, dans l'ordre :
  `sap.ui.core.Control`, `sap.ui.core.Element`, `sap.ui.base.ManagedObject`,
  `sap.ui.base.EventProvider`, `sap.ui.base.Object`.

### Galerie d'échantillons (`#/entity/sap.m.Button`)

- Titre de document `sap.m.Button - Samples - Demo Kit - OPENUI5 SDK` ;
  vue `sdk---entity--` aux ids STABLES : `entity--ObjectPageLayout`,
  `entity--entityHeader`, une seule rubrique `sdk---entity--samples`, et
  surtout **`sdk---entity--table`, une vraie `sap.m.Table`** que
  `Read Ui5 Table` lit sans détour (2 lignes sur `sap.m.Button` :
  Name/Description).
- Les lignes (`sap.m.ColumnListItem`, `type=Navigation`) portent le contexte
  `/entity/samples/<n>` aux clés techniques `id` (`sap.m.sample.Button`),
  `entityId` (`sap.m.Button`), `library` (`sap.m`) et `key`
  (`#/sample/sap.m.sample.Button/preview`, la route d'exécution).
- Le clic sur une ligne mène à
  `#/entity/sap.m.Button/sample/sap.m.sample.Button` ; barre d'échantillon
  aux ids stables `sdk---sample--` : `infoSample`, `apiRefButton`,
  `prevSample`, `nextSample`, `toggleFullScreenBtn`, `toggleRTA`, **`code`**,
  `newTab`, `sampleSettings`.
- **Vue du code source** : le bouton `sample--code` mène à
  `#/entity/sap.m.Button/sample/sap.m.sample.Button/code` ; vue
  `sdk---code--` aux ids stables `fileEditor`, `downloadSampleButton`,
  `splitButton`, `newTab`, `prevSample`, `nextSample`. Les fichiers sont des
  onglets `sap.m.IconTabFilter` dont la **`key` EST le nom de fichier**
  (`Page.view.xml`, `Page.controller.js`, `manifest.json`), lisibles par le
  `selectedKey` de l'`IconTabHeader` de `code--fileEditor`. L'éditeur
  `sdk---code--fileEditor-editor` est un `sap.ui.codeeditor.CodeEditor` dont
  la propriété `value` porte le SOURCE réel, y compris l'identifiant
  technique de l'échantillon (`controllerName="sap.m.sample.Button.Page"`).
  La bascule d'onglet par clé fonctionne (selectedKey suit).
- **`nextSample` navigue vers l'échantillon suivant SANS quitter la vue** :
  depuis `.../sap.m.sample.Button/code`, arrivée sur
  `.../sap.m.sample.ButtonWithBadge/code`.

### Demo Apps (`#/demoapps`) et Resources (`#/resources`)

- Demo Apps : titre `Demo Apps - Demo Kit - OPENUI5 SDK`, vue
  `sdk---demoApps--` (`sapUiDemoKitDemoAppsPage`, `...Main`, `...Aside`),
  **9 `sap.f.Card`** dans la zone principale, 32 ancres dont les liens de
  lancement RELATIFS same-origin
  (`test-resources/sap/m/demokit/cart/webapp/index.html?sap-ui-theme=...`)
  et des liens GitHub externes.
- Resources : titre `Resources - Demo Kit - OPENUI5 SDK`, page de cartes
  (Icon Explorer...), perception seule.

### L'accumulation, mesurée (le piège central de cette campagne)

Après le tour complet (topic, api, entity, sample, code, demoapps,
resources), `Get Page Composition` sur `#/resources` rend **5442 contrôles**
(511 à l'ouverture) et **`frames` contient encore
`iframe[id="sampleFrame"]`**, `visible: False`, src portant les paramètres
techniques `sap-ui-xx-sample-id=sap.m.sample.Button&sap-ui-xx-sample-lib=sap.m` :
**l'iframe d'échantillon SURVIT à la navigation**, invisible, contrairement
au launchpad ABAP qui détruit la sienne au retour à l'accueil. Les masters
de toutes les sections visitées restent rendus côte à côte.

### Console et langue

- 22 erreurs console en fin de tour, TOUTES dans les familles déjà déclarées
  par la campagne sœur (première : `[FUTURE FATAL] ... unknown setting
  'style' for class sap.m.Link`) ; `page_errors` vide ; aucune famille
  NOUVELLE née des pages topic/entity/code/demoapps ce jour.
- Langue mixte re-mesurée : l'instantané ARIA porte à la fois des libellés
  français (« Kit de démonstration UI5 », « Zone de recherche ») et les
  onglets anglais (`Home`, `Documentation`...) sur la MÊME page.

## Scénarios

### 1. L'arbre des sujets de la Documentation se perçoit et porte des identifiants stables

- **Étapes** :
  1. Ouvrir le Demo Kit (keywords existants du page object : ouverture,
     consentement, perception).
  2. Ouvrir la section Documentation par sa clé technique (`topic`).
  3. Compter les nœuds de l'arbre des sujets DANS son conteneur et relever
     leurs identifiants de sujet.
- **Résultat attendu** :
  - fragment `/topic` et clé de section active `topic` (les deux témoins) ;
  - l'arbre des sujets porte des nœuds (9 racines observées : asserter
    `> 0`, journaliser le compte) ;
  - **chaque identifiant de sujet est un GUID hexadécimal de 32 caractères**
    (assertion structurelle par motif, indépendante de la langue et du
    contenu) ; les titres sont journalisés, jamais assertés ;
  - le champ de filtre du panneau des sujets est rendu (1 correspondance).
- **Keywords métier manquants** :
  - `Compter Les Noeuds De L Arbre Des Sujets` : comptage porté par le
    conteneur de l'arbre des sujets.
  - `Lister Les Identifiants De Sujets` : les `target` des nœuds rendus.
  - `Les Identifiants De Sujets Doivent Etre Des Guid` : le motif
    structurel, échec nommant les intrus.

### 2. Un sujet s'ouvre par son nœud : navigation et dépliage dans le même geste

- **Étapes** :
  1. Sur la section Documentation, relever le comptage de l'arbre.
  2. Cliquer un nœud racine par son identifiant de sujet (ancrage exact).
  3. Attendre l'arrivée sur le sujet, puis recompter l'arbre.
- **Résultat attendu** :
  - le fragment vaut `/topic/<guid>` (le guid cliqué) ;
  - la **vue de détail RÉELLE** est rendue (celle du sujet, pas l'écran
    d'accueil de la section : les deux portent le même suffixe de page,
    voir vigilance) ;
  - l'arbre s'est **déplié** : comptage strictement supérieur (9 → 30
    observés, la relation est l'assertion) ;
  - le titre du document est journalisé (prose documentaire, jamais
    assertée).
- **Keywords métier manquants** :
  - `Ouvrir Le Sujet` (`${guid}`) : clique le nœud d'ancrage exact, attend
    le fragment ET la vue de détail réelle.
  - `Le Sujet Affiche Doit Etre` (`${guid}`) : fragment + vue de détail
    réelle rendue.

### 3. Les liens croisés d'un sujet mènent à la Référence de l'API

- **Étapes** :
  1. Ouvrir un sujet riche en références (Data Binding,
     `68b9644a253741e8a4b9e4279a35c247`, relevé live).
  2. Compter les liens croisés vers l'API DANS la portée du détail du sujet
     (ancres relatives `api/...`).
  3. Cliquer un lien croisé vers une entité d'API (relevé :
     `api/sap.ui.model.BindingMode`).
  4. Percevoir : fragment, titre, clé de section active.
- **Résultat attendu** :
  - le sujet porte au moins un lien croisé `api/...` (comptage `> 0`,
    PORTÉ : le DOM garde le contenu des sections déjà visitées, voir
    vigilance) ;
  - après le clic, le fragment vaut `/api/<nom.qualifié>` et le titre du
    document commence par le nom qualifié ;
  - **la clé de section active est passée de `topic` à `api`** : la
    navigation croisée change de section, c'est le cœur du scénario.
- **Keywords métier manquants** :
  - `Compter Les Liens Croises Vers L Api` : ancres relatives dans la portée
    du détail du sujet.
  - `Ouvrir Le Lien Croise Vers L Api` (`${nom_qualifie}`) : clic DOM sur
    l'ancre relative, attente du couple fragment + titre, vérification du
    changement de section.

### 4. La fiche d'API se sous-navigue par ses rubriques et ses liens de membre

- **Étapes** :
  1. Ouvrir la fiche d'API de `sap.m.Button` (keyword existant).
  2. Relever les suffixes des rubriques rendues.
  3. Cliquer le lien DOM d'un événement propre de la fiche (relevé :
     `api/sap.m.Button#events/press`, dans la portée de la rubrique des
     événements).
  4. Lire le fragment et la rubrique sélectionnée de la barre d'ancrage.
- **Résultat attendu** :
  - les suffixes de rubriques contiennent `controlproperties`,
    `aggregations`, `events`, `methods` (7 observés, inclusion et non
    égalité) ;
  - le fragment porte le nom qualifié ET le membre visé, le second dièse
    étant **encodé** (`%23events/press` observé : l'assertion tolère les
    deux formes) ;
  - le `selectedKey` de la barre d'ancrage se termine par `--events` (le
    préfixe de vue est généré : assertion de SUFFIXE).
- **Keywords métier manquants** :
  - `Lister Les Rubriques De La Fiche` : suffixes des sections rendues.
  - `Ouvrir Le Membre De La Fiche` (`${classe}`, `${type_membre}`,
    `${nom}`) : clic DOM sur le lien relatif du membre, dans la portée de sa
    rubrique.
  - `La Rubrique Selectionnee Doit Etre` (`${suffixe}`) : assertion de
    suffixe sur la barre d'ancrage.

### 5. Les méthodes et événements se lisent par leurs liens techniques, pas par le contexte de liaison

- **Étapes** :
  1. Sur la fiche de `sap.m.Button`, compter les lignes des tables des
     rubriques `methods` et `events` (agrégation `rows`).
  2. Extraire les noms techniques des MEMBRES PROPRES depuis les liens DOM
     de chaque rubrique (`api/sap.m.Button#methods/<nom>`,
     `api/sap.m.Button#events/<nom>` : le préfixe de classe filtre les
     membres propres des hérités).
- **Résultat attendu** :
  - chaque table porte des lignes (44 et 2 observées : `> 0`, jamais les
    nombres) ;
  - les lignes de ces deux tables portent un contexte de liaison ABSENT
    (`binding: None`, vérifié) : le scénario DOCUMENTE ce fait en
    l'assertant, pour que la voie de lecture erronée ne revienne pas ;
  - la liste des événements propres extraite des liens contient `press`
    (l'événement définitoire d'un bouton, clé technique) ;
  - la liste des méthodes propres est non vide et chaque nom est un
    identifiant JavaScript (motif structurel).
- **Keywords métier manquants** :
  - `Lire Les Membres Propres De La Rubrique` (`${classe}`,
    `${type_membre}`) : noms extraits des hrefs relatifs, portés par la
    rubrique.
  - `Les Lignes De La Rubrique Ne Portent Pas De Contexte` (`${rubrique}`) :
    l'assertion-documentation du fait mesuré.

### 6. La documentation complète égale le contrôle vivant (assertion reine)

- **Étapes** :
  1. Sur la fiche de `sap.m.Button`, relever l'état de la case « borrowed
     properties » de la rubrique des propriétés (ancrée par containment,
     PAS par id : ids générés) et le nombre de lignes de la table.
  2. Cocher la case, attendre ACTIVEMENT l'augmentation du nombre de lignes.
  3. Lire les noms techniques de TOUTES les lignes (contextes de liaison) et
     séparer les empruntées (clé `borrowedFrom` présente) des propres.
  4. Lire les propriétés d'une instance vivante du contrôle au registre.
  5. Confronter : égalité STRICTE des deux ensembles.
  6. Décocher la case, constater le retour à l'état relevé (propriété
     `selected`), également en teardown.
- **Résultat attendu** :
  - la table passe de 12 à 18 lignes (croissance stricte, les nombres
    journalisés) ;
  - chaque ligne ajoutée porte `borrowedFrom` ; aucune ligne propre ne le
    porte ;
  - **l'ensemble des noms documentés (complet) est ÉGAL à l'ensemble des
    propriétés du contrôle vivant** : l'inclusion de la campagne sœur devient
    une égalité, qui prouve que la doc décrit exactement le runtime servi ;
    l'échec nomme les noms manquants de chaque côté ;
  - la case et la table sont revenues à l'état relevé.
- **Keywords métier manquants** :
  - `Lire La Bascule Borrowed De La Rubrique` (`${rubrique}`) /
    `Basculer Les Borrowed De La Rubrique` (`${rubrique}`) : la case unique
    de la rubrique, par containment.
  - `Lire Les Noms Documentes Avec Provenance` (`${rubrique}`) : noms +
    marqueur `borrowedFrom` depuis les contextes de liaison.
  - `La Doc Complete Doit Egaler Le Controle Vivant` : le verdict d'égalité
    stricte, échec nommant les écarts des deux côtés.
  - `Restaurer Les Bascules Borrowed` : teardown sur l'état relevé.

### 7. Les éléments empruntés reconstruisent la chaîne d'héritage

- **Étapes** :
  1. Sur la fiche de `sap.m.Button`, lire les listes d'éléments empruntés de
     la rubrique des méthodes (contrôles dédiés du SDK, contexte
     `/borrowed/methods/<n>`).
  2. Extraire le nom d'ancêtre de chaque liste.
- **Résultat attendu** :
  - au moins une liste d'emprunts est rendue dans la rubrique (5 observées) ;
  - chaque nom d'ancêtre est un nom qualifié technique (motif `sap.*`) ;
  - la chaîne contient `sap.ui.core.Control` (l'ancêtre définitoire d'un
    contrôle) ; la chaîne complète observée
    (`Control`, `Element`, `ManagedObject`, `EventProvider`, `Object`) est
    journalisée, son ordre et sa longueur ne sont pas gravés (ils suivent le
    SDK).
- **Keywords métier manquants** :
  - `Lire La Chaine D Heritage Documentee` (`${rubrique}`) : noms d'ancêtres
    depuis les contextes de liaison des listes d'emprunts.
  - `La Chaine D Heritage Doit Porter` (`${ancetre}`) : inclusion.

### 8. La galerie d'échantillons se lit comme une table, ses lignes portent leurs clés

- **Étapes** :
  1. Ouvrir la galerie d'une entité (`#/entity/sap.m.Button`).
  2. Lire la table des échantillons par la lecture générique de table
     (id stable, vraie table UI5).
  3. Lire les contextes de liaison des lignes : identifiant technique
     d'échantillon, entité, route.
- **Résultat attendu** :
  - le titre du document commence par le nom qualifié de l'entité ; la clé
    de section active vaut `controls` ;
  - la lecture générique rend au moins une ligne (2 observées : cette table
    est une `sap.m.Table` standard, contrairement aux tables de doc des
    fiches d'API) ;
  - chaque ligne porte un `id` d'échantillon préfixé par la bibliothèque
    (`sap.m.sample.*` observé), un `entityId` ÉGAL à l'entité de la route,
    et une route d'exécution non vide ;
  - le nombre d'échantillons est journalisé, jamais gravé.
- **Keywords métier manquants** :
  - `Ouvrir La Galerie D Echantillons` (`${nom_qualifie}`) : navigation +
    les deux témoins.
  - `Lire Les Echantillons De La Galerie` : lignes lues par la table ET
    leurs clés techniques par les contextes de liaison, en un seul verdict
    de cohérence (autant de lignes que de contextes).

### 9. Un échantillon s'ouvre, sa vue code expose les fichiers par clés et le source réel

- **Étapes** :
  1. Depuis la galerie, ouvrir le premier échantillon par sa LIGNE
     (l'identifiant de ligne est découvert à l'exécution).
  2. Constater l'arrivée sur la route d'exécution et la barre d'échantillon.
  3. Ouvrir la vue du code source par son bouton stable.
  4. Lire l'onglet de fichier sélectionné et la liste des fichiers (clés).
  5. Basculer vers un autre fichier par sa clé.
  6. Lire le contenu de l'éditeur de code.
- **Résultat attendu** :
  - le fragment vaut `/entity/<entité>/sample/<id>` puis, après le bouton,
    `/entity/<entité>/sample/<id>/code` (l'`<id>` est celui lu au scénario
    8, jamais écrit en dur) ;
  - les clés de fichiers contiennent au moins une vue (suffixe `.view.xml`),
    un contrôleur (`.controller.js`) et `manifest.json` (motifs structurels,
    les noms exacts journalisés) ;
  - la bascule d'onglet par clé est suivie par le `selectedKey` ;
  - le contenu de l'éditeur est non vide et **porte l'identifiant technique
    de l'échantillon** (`sap.m.sample.Button` relevé dans le
    `controllerName` du source) : la vue code montre bien LE code de CET
    échantillon ;
  - aucun clic sur le téléchargement, l'ouverture d'onglet ou le mode RTA
    (perçus, jamais actionnés : lecture seule).
- **Keywords métier manquants** :
  - `Ouvrir L Echantillon Par Sa Ligne` (`${rang}`) : clic de ligne
    découvert, attente de la route.
  - `Ouvrir La Vue Du Code Source` : bouton stable, attente de la route
    `/code`.
  - `Lister Les Fichiers De L Echantillon` / `Choisir Le Fichier`
    (`${cle}`) : onglets par clé.
  - `Le Source Doit Porter L Identifiant` (`${id_echantillon}`) : lecture de
    la propriété de l'éditeur.

### 10. La navigation suivant/précédent traverse les échantillons sans quitter la vue

- **Étapes** :
  1. Depuis la vue code du premier échantillon, actionner « échantillon
     suivant » (id stable de la vue code).
  2. Lire le fragment.
  3. Revenir par « échantillon précédent ».
- **Résultat attendu** :
  - après « suivant », le fragment porte l'identifiant du DEUXIÈME
    échantillon lu au scénario 8 et se termine toujours par `/code` (la vue
    ne change pas, seul l'échantillon change) ;
  - après « précédent », le fragment porte de nouveau l'identifiant du
    premier ;
  - les deux gestes s'attendent sur le fragment, jamais sur le réseau.
- **Keywords métier manquants** :
  - `Passer A L Echantillon Suivant` / `Revenir A L Echantillon Precedent` :
    boutons stables + attente du fragment attendu.

### 11. Demo Apps et Resources se perçoivent sans rien ouvrir

- **Étapes** :
  1. Ouvrir la section Demo Apps par sa clé (`demoapps`).
  2. Compter les cartes d'applications dans la zone principale et relever
     les liens de lancement.
  3. Ouvrir la section Resources par sa clé (`resources`), percevoir.
- **Résultat attendu** :
  - Demo Apps : fragment `/demoapps`, des cartes rendues (9 observées :
    `> 0`), et **chaque lien de lancement relatif reste same-origin**
    (chemins `test-resources/...` observés ; les liens externes déclarés,
    GitHub, sont classés à part) ; aucune application ouverte ;
  - Resources : fragment `/resources`, la page porte des cartes rendues ;
    perception seule ;
  - les titres de documents sont journalisés.
- **Keywords métier manquants** :
  - `Compter Les Cartes Demo Apps` : cartes dans la zone principale.
  - `Les Liens De Lancement Doivent Etre Locaux` : classement
    relatif-same-origin / externe déclaré, échec nommant un lien hors des
    deux familles.

### 12. L'iframe d'échantillon survit à la navigation : la sentinelle d'accumulation

- **Étapes** :
  1. Après avoir visité un échantillon (scénario 9) puis navigué vers une
     AUTRE section (Demo Apps ou Resources), percevoir la composition.
  2. Relever les frames et le nombre de contrôles.
- **Résultat attendu** :
  - la composition porte ENCORE l'iframe d'échantillon (sélecteur à id
    stable connu), **`visible: False`** : elle a survécu à la navigation,
    invisible : c'est le comportement INVERSE du launchpad ABAP (qui détruit
    la sienne) et le fait qui justifie toutes les lectures portées de cette
    campagne ;
  - le nombre de contrôles a l'accumulation pour ordre de grandeur (5442
    relevés contre 511 à froid : journalisé, JAMAIS asserté : c'est la
    preuve mesurée qu'un plancher global n'a de sens que sur une page
    fraîche) ;
  - aucune erreur console hors des familles déjà déclarées par la campagne
    sœur (réutiliser son classement : aucune famille nouvelle n'est née des
    pages explorées ce jour, vérifié).
- **Keywords métier manquants** :
  - `L Iframe D Echantillon Doit Avoir Survecu` : frame présente ET
    invisible dans la composition.
  - (réutiliser `Classer Les Anomalies De La Page` /
    `Aucune Anomalie Hors Familles Connues` de la campagne sœur.)

## Points de vigilance

- **Cette SPA accumule tout ce qu'elle a montré.** Les masters de toutes les
  sections visitées restent rendus côte à côte, le contenu des sujets déjà
  lus reste au DOM (mesuré : les liens `#methods/` du sujet Data Binding
  matchaient encore une requête DOM globale depuis la fiche de
  `sap.m.Button`), l'iframe d'échantillon survit invisible, et le compte de
  contrôles passe de 511 à 5442 sur un seul tour. Conséquences non
  négociables : toute lecture (registre OU DOM) est PORTÉE par son conteneur
  (`containedIn` pour le registre, portée d'élément pour les ancres DOM), et
  un plancher de contrôles ne s'asserte que sur une page fraîche.
- **`idSuffix=topicDetailPage` n'est pas unique** : la section Documentation
  garde DEUX vues au même suffixe de page
  (`topicDetailInitial--topicDetailPage`, l'écran d'accueil, et
  `topicDetail--topicDetailPage`, le sujet réel). Ancrer sur le suffixe LONG
  incluant le nom de vue.
- **Les liens croisés du contenu documentaire sont des ancres relatives SANS
  `#/`** (`topic/<guid>`, `api/<classe>`, `api/<classe>#methods/<nom>`) : un
  sélecteur qui cherche `href*="#/api/"` rend 0 en croyant qu'il n'y a pas
  de liens (mesuré). C'est du contenu HTML hors registre : moteur `dom`
  obligatoire, comme la bannière de consentement.
- **Le second dièse d'une route de membre est encodé dans le fragment** :
  cliquer `api/sap.m.Button#events/press` donne
  `/api/sap.m.Button%23events/press`. Une assertion d'égalité sur la forme à
  dièse échoue sur une navigation réussie : accepter les deux formes.
- **Deux familles de tables de doc, deux voies de lecture, et l'une des deux
  rend `binding: None` sans échouer.** Propriétés et agrégations portent des
  contextes de liaison ; méthodes et événements N'EN PORTENT PAS (44 lignes,
  toutes à `None`, mesuré). Un keyword qui généralise la voie du contexte
  aux quatre rubriques rend des listes vides plausibles : le profil « vert
  et faux ». Les noms techniques des méthodes/événements se lisent sur les
  liens DOM de la rubrique, filtrés par le préfixe de classe (les hérités
  pointent vers l'ancêtre).
- **La case « Show borrowed aggregations » est cochée PAR DÉFAUT** (état
  relevé `[False, True, False]`) : la table des agrégations contient des
  entrées héritées (`borrowedFrom`) SANS qu'on ait rien touché. Une lecture
  qui suppose « la table = les éléments propres » est fausse d'entrée sur
  cette rubrique. Relever l'état AVANT de lire, et que le teardown restaure
  l'état RELEVÉ, pas un état supposé.
- **Les trois cases « borrowed » ont des ids GÉNÉRÉS** (`__box9`...) : elles
  s'ancrent par containment de rubrique (exactement 1 CheckBox par rubrique,
  vérifié), jamais par id, et leurs libellés sont localisés (jamais
  d'ancrage texte).
- **`selectedSectionId` n'existe pas comme propriété** sur
  l'`ObjectPageLayout` de cette version : la rubrique sélectionnée se lit
  sur le `selectedKey` de la barre d'ancrage (IconTabHeader), par SUFFIXE
  (préfixe de vue généré `__xmlview<N>--`).
- **Les `target` des nœuds Documentation sont des GUID, pas des noms
  qualifiés** : l'ancrage exact par motif reste obligatoire (patron
  `Motif Exact` du page object), et aucun titre de sujet n'est une ancre
  (prose anglaise du corpus documentaire, qui ne suit d'ailleurs PAS la
  langue de l'interface).
- **Boutons à ne JAMAIS actionner** (lecture seule) :
  `downloadSampleButton` (écrit sur le disque), `newTab` (ouvre un onglet ;
  si un test en ouvre un par accident, le teardown referme les pages
  supplémentaires, keyword existant), `toggleRTA` (mode adaptation runtime).
  Ils se PERÇOIVENT (ids stables listés) pour prouver la barre d'outils,
  sans clic.
- **Pièges du shell Web Components (SDK >= 1.152.0)**, hérités de la fiche
  `memory/demokit-shell-passe-aux-web-components.md` : les ids stables
  survivent mais un enfant peut disparaître, les clés migrent dans les
  suffixes d'id (`menuItem-<clé>`), la pile de popups compte les couches
  d'implémentation WC, et le containment d'un popover WC ne vaut rien (il
  vit dans un shadow root). Cette campagne n'interagit pas avec le shell
  au-delà des onglets, mais toute extension future doit relire cette fiche.
- **La langue reste instable** (re-mesuré ce jour : instantané ARIA mixte
  français/anglais sur une même page) : clés, routes, GUID, noms qualifiés,
  suffixes d'id, noms de fichiers ; jamais un libellé, pas même anglais.
- **Le repos réseau ne témoigne pas des gestes locaux** (constat de la
  campagne sœur, confirmé : dépliage d'arbre, bascule de case, changement
  d'onglet de fichier n'émettent rien) : chaque geste attend SON témoin
  (comptage, propriété, fragment), jamais une durée.
- **Rejouabilité des scénarios 9-10** : l'identifiant d'échantillon et son
  successeur sont LUS au scénario 8 (contextes de liaison), jamais écrits en
  dur : la campagne survit à l'ajout d'un échantillon dans la galerie.

## Artefacts prévus

- **Page object** : étendre
  `resources/page_objects/openui5_demokit.resource` (mêmes variables
  d'ouverture, de consentement et de navigation ; nouvelles sections :
  arbre des sujets, liens croisés, rubriques et membres de fiche, bascules
  borrowed, galerie et vue code, Demo Apps, sentinelle d'accumulation). Les
  ids relevés ici (préfixes `sdk---topicMaster--`, `sdk---topicDetail--`,
  `sdk---entity--`, `sdk---sample--`, `sdk---code--`, `sdk---demoApps--`)
  vivent LÀ, jamais dans la suite (convention 1).
- **Suite** : `tests/robot/ui/fiori/exploration_profonde_demokit.robot`,
  même patron que la campagne sœur : `${DEMOKIT_HEADLESS}` surchargeable
  (`-v DEMOKIT_HEADLESS:True` pour la CI), Suite Setup ouvrant le Demo Kit
  et relevant les états initiaux (bascules borrowed comprises), Suite
  Teardown restaurant puis fermant le navigateur sur toutes les branches,
  Test Teardown ramenant à l'état de référence (pages supplémentaires,
  popups, filtres).
- **Aucun écart de capacité bibliothèque détecté** pendant cette
  exploration : `Read Ui5 Table` a correctement lu la vraie table de la
  galerie, `Get Ui5 Aggregation Info` a rendu les contextes là où ils
  existent et un `binding: None` honnête là où ils n'existent pas,
  `Get Page Composition` a vu l'iframe survivante avec son état de
  visibilité.

## Écarts constatés à la génération

Réplay live du 2026-09-05 (sap-generator, rf-mcp, Chromium headless, SDK
1.152.0, le jour même de l'exploration du planner). Cinq écarts entre le plan
et la cible mesurée, aucun ne change le sens métier d'un scénario :

1. **L'assertion reine « 18 = 18 » ne se reproduit pas telle quelle.** Le plan
   affirme que l'ensemble documenté complet (18 noms) égale l'ensemble des
   propriétés du contrôle vivant. Mesuré à la génération : la fiche du
   contrôle vivant rend **17** clés sur les 70 instances rendues de
   `sap.m.Button` (aucune ne porte `fieldGroupIds`), et une lecture directe de
   cette propriété échoue en la déclarant inexistante. Cause identifiée : la
   fiche de contrôle de la bibliothèque est réduite aux valeurs PRIMITIVES
   (MCP-safe), et `fieldGroupIds` est la seule propriété du contrôle à valeur
   tableau ; la même réduction explique l'absence de la clé `typeInfo` (un
   objet) dans les contextes de liaison relevés ce jour, là où le plan la
   liste (la clé `description` y figure). Ce que fait la suite : égalité
   stricte MODULO l'inventaire déclaré `@{DEMOKIT_PROPS_HORS_FICHE}` (une
   entrée, `fieldGroupIds`), avec garde de tolérance morte : si la propriété
   redevient lisible sur le vivant, le test échoue en demandant de purger
   l'inventaire, et toute autre propriété manquante échoue aussi.
2. **L'exécution d'un échantillon fait naître des anomalies console hors des
   familles déclarées**, là où le plan affirme « aucune famille nouvelle ».
   Mesuré : 6 entrées non classées, toutes le `Component-preload.js` de
   l'échantillon exécuté (Button ET ButtonWithBadge), sous DEUX formes (404
   réseau sur `test-resources/.../demokit/sample/<Nom>/Component-preload.js`
   et refus du ModuleSystem nommant `sap/m/sample/<Nom>/Component-preload.js`).
   Ce que fait la suite : l'entrée `component-preload.js` remplace
   `sdk/samples/component-preload.js` dans l'inventaire déclaré du page
   object, qu'elle subsume : la famille est celle des préchargements de
   composants, que le SDK ne sert jamais ; toute autre ressource manquante
   sort toujours non classée.
3. **La vue code laisse SA propre iframe survivante.** En plus de
   `sampleFrame`, la composition de fin de tour porte `sampleFrameEdit`
   (invisible, même src), née de la vue du code source. La sentinelle vise
   nommément `sampleFrame` et journalise le reste.
4. **Un 4e onglet de fichier à clé VIDE** est rendu dans la vue code à côté
   des trois fichiers (`Page.view.xml`, `Page.controller.js`,
   `manifest.json`) : la lecture des fichiers filtre les clés vides.
5. **La zone Demo Apps porte aussi des ancres `#` sans cible** (boutons rendus
   en ancre), en plus des lancements relatifs `test-resources/...` et des
   liens GitHub : le verdict de localité les classe avec les liens relatifs
   (same-origin trivial).
6. **Les routes de la section des échantillons ne portent pas la clé de
   section** : sur `#/entity/...`, la clé sélectionnée du shell vaut
   `controls` mais le fragment ne commence pas par `/controls` (mesuré au
   premier run complet). Le témoin de galerie du page object n'asserte donc
   que la clé du shell, le fragment restant `/entity/<entité>`.
7. **Revenir d'une sous-route de membre vers la fiche nue compte comme « URL
   à l'identique »** : depuis `/api/X%23events/press`, demander `/api/X`
   réinitialise le titre au titre générique de la section sans jamais le
   rétablir (même symptôme que la navigation à l'identique déjà documentée).
   La garde de rejouabilité de `Ouvrir La Fiche D Api` traite désormais la
   sous-route de membre de la même fiche comme un cas de rechargement.
8. **Le contenu des sections arrive APRÈS leurs témoins d'activation**, une
   famille entière relevée aux premiers runs et confirmée en perception
   live : les cartes Demo Apps et Resources (comptage 0 juste après
   l'activation, 9 ensuite), l'arbre des sujets de la Documentation (0 nœud à
   l'instant des témoins, champ de filtre déjà rendu, 9 nœuds ensuite), la
   barre de la vue code (bouton de téléchargement à 0 juste après la route
   `/code`), et les onglets de fichier de la vue code, qui arrivent APRÈS le
   bouton de téléchargement (bouton rendu, liste de clés vide, puis les
   trois fichiers). Chaque lecture de ces contenus est une attente ACTIVE
   sur son témoin réel, jamais une lecture unique ni une durée.
9. **La barre d'ancrage est un scroll spy, pas un témoin de route.** Le plan
   attendait un `selectedKey` se terminant par `--events` après la
   sous-navigation vers `press` ; reproduit au run puis en re-vérification
   live : la barre se stabilise sur `--associations` (la rubrique VOISINE
   d'une rubrique courte) alors que le fragment porte parfaitement le membre.
   Le témoin fort est le FRAGMENT ; la barre atteste seulement que le
   défilement a quitté la rubrique d'ouverture, sa valeur est journalisée.
10. **Les liens de membres portent aussi des méthodes STATIQUES sous leur nom
    qualifié** (`sap.m.Button.extend`, `sap.m.Button.getMetadata`) : le motif
    « identifiant JavaScript » accepte les noms pointés.
11. **Les cartes Demo Apps portent des liens absolus vers
    `sap-samples.github.io`** (GitHub Pages des exemples SAP-samples), en plus
    de `github.com` : l'inventaire des hôtes externes déclarés du page object
    porte les deux.

## Traçabilité de l'exploration

Exploration live du 2026-09-05 via rf-mcp (session `demokit_deep_explore`,
Chromium headless), navigateur fermé en fin de session. Mémoire QA partagée
(`qa-brain`, index green, 930 passages) consultée avant exploration : elle a
confirmé que la spec antérieure `openui5-demokit-consultation-doc-controle.md`
(2026-08-15) couvre la consultation d'une fiche et qu'aucune source ne
couvrait `#/topic`, `#/entity`, la vue code ni `#/demoapps` : le périmètre
complémentaire de ce plan vient de là. Fiches mémoire citées :
`demokit-shell-passe-aux-web-components.md`,
`la-langue-peut-basculer-en-cours-de-run.md`.
