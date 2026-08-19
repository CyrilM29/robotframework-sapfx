# Consultation de la documentation d'un contrôle UI5 (OpenUI5 Demo Kit)

- **Canal** : Fiori (web)
- **Système / URL** : Demo Kit public **OpenUI5 SDK**, `https://sdk.openui5.org/`.
  Application SAPUI5 mono-page (SPA à routage par hash `#/...`), runtime SAPUI5
  **1.151.0** (relevé live). Aucune authentification. C'est la cible smoke Fiori
  documentée du projet (`docs/sap-test-data.md`), avec les mêmes contrôles
  SAPUI5 qu'une vraie application Fiori.
- **Préconditions** :
  - Accès réseau à `sdk.openui5.org` (cible publique, pas d'identifiants).
  - Une **bannière de consentement cookies TrustArc** s'affiche au premier
    chargement et **intercepte les clics** tant qu'elle n'est pas acceptée
    (voir « Points de vigilance »). Elle doit être acceptée avant toute
    interaction avec les onglets de navigation UI5.
  - Aucun réglage persistant requis, consultation seule (aucun formulaire
    rempli, aucune écriture).

## Données observées

Relevé live le 2026-08-15, exploration pilotée par rf-mcp (Browser +
SapFioriLibrary), navigateur Chromium headless.

### Composition de la page

`Get Page Composition` sur l'accueil : `ui5_runtime=True`,
`ui5_version=1.151.0`, `ui5_controls=551`, `wc_hosts=0`, `webgui_elements=0`,
`frameworks=[]`, `frames=[]`, moteurs recommandés `['role', 'xpath', 'dom']`.
Page **mono-technologie UI5** : le moteur `role` (résolution par
controlType / properties / idSuffix) suffit, aucune frame à empiler. La
bannière cookies TrustArc est en dehors du runtime UI5 (élément **DOM** en
light DOM, pas un contrôle UI5) : elle n'apparaît pas dans l'arbre UI5 ni dans
`Get Ui5 Page Map`, seulement au DOM.

### Barre de navigation principale (accueil et toutes les pages)

Onglets de navigation, tous des `sap.m.IconTabFilter` à **id stable**
`sdk---app--<tab>Tab` (le préfixe `sdk---app--` est le composant SDK ; c'est le
suffixe `<tab>Tab` qui est l'ancre déterministe, à passer en `idSuffix`) :

| Rôle fonctionnel | idSuffix (ancre primaire) | controlType observé |
|---|---|---|
| Accueil (Home) | `welcomeTab` | `sap.m.IconTabFilter` |
| Documentation | `topicMasterTab` | `sap.m.IconTabFilter` |
| **Référence de l'API (API Reference)** | `apiMasterTab` | `sap.m.IconTabFilter` |
| Échantillons (Samples) | `controlsMasterTab` | `sap.m.IconTabFilter` |
| Applications de démo (Demo Apps) | `demoAppsTab` | `sap.m.IconTabFilter` |
| Ressources (Resources) | `resourcesTab` | `sap.m.IconTabFilter` |

- Zone de recherche globale de l'en-tête : `sdk---app--searchControl-searchField`
  (`sap.m.SearchField`).
- Les **libellés** de ces onglets sont **localisés** et ont même changé de langue
  en cours de session (« Référence de l'API » au premier affichage en locale FR,
  puis « API Reference » après acceptation des cookies) : ne jamais asserter ni
  cibler par ces textes. L'ancre est l'idSuffix (`apiMasterTab`), pas le libellé.
- Le clic sur l'onglet « API Reference » fait passer l'URL de `#/` à **`#/api`**
  (routage par hash observé).

### Page « API Reference » (`#/api`)

- Panneau maître avec un champ de filtre `sdk---apiMaster--searchField`
  (`sap.m.SearchField`, libellé « Filter » / « Filtrer », localisé) et des
  boutons `sdk---apiMaster--expandAllButton` / `sdk---apiMaster--collapseAllButton`
  (`sap.m.Button`) pour déplier/replier l'arbre de l'API.
- La fiche d'un contrôle s'atteint aussi directement par l'URL à hash
  **`#/api/<nom.qualifié.du.contrôle>`** (SPA à routage par hash) : c'est le
  chemin déterministe utilisé pour ouvrir `sap.m.Button` sans dépendre du
  dépliage de l'arbre de navigation du panneau maître.

### Fiche du contrôle `sap.m.Button` (`#/api/sap.m.Button`)

- **Titre du document** (onglet du navigateur) :
  `sap.m.Button - API Reference - Demo Kit - OPENUI5 SDK`. Le nom de classe
  `sap.m.Button` et « API Reference » y sont des identifiants **techniques**,
  non traduits : c'est l'assertion primaire **locale-indépendante**.
- **Titre affiché de la fiche** : un `sap.m.Title` de texte `class sap.m.Button`.
  Attention : ce texte apparaît **deux fois** (le titre pleine largeur de
  l'ObjectPage + sa version repliée dans l'en-tête snappé), donc
  `controlType=sap.m.Title` + `properties.text` n'est **pas unique** (2 matches).
- **Structure de la fiche** : un `sap.uxap.ObjectPageLayout` unique
  (`idSuffix=apiDetailPage`, 1 match ; id complet observé au DOM
  `sdk---apiDetail--apiDetailObjectPage`), contenant **7**
  `sap.uxap.ObjectPageSection` (les rubriques de doc : vue d'ensemble,
  constructeur, propriétés, agrégations, événements, méthodes... titres
  localisés). L'en-tête de l'ObjectPage expose des boutons
  `...apiDetailObjectPage-OPHeaderContent-collapseBtn` et `-pinBtn`.
- Après `Go To` sur `#/api/sap.m.Button`, `Wait For Ui5 Idle` renvoie
  `{'pending': 0, 'busy': False, 'quiet_ms': 2829}` : la fiche se charge par
  requêtes réseau (données d'API) puis se stabilise ; le repos réel se constate
  au niveau réseau/DOM, pas par une attente fixe.

## Scénarios

### 1. L'accueil du Demo Kit se charge et expose la barre de navigation

- **Étapes** :
  1. Ouvrir le navigateur sur `https://sdk.openui5.org/` (Suite Setup).
  2. Attendre le retour du runtime UI5.
  3. Accepter la bannière de consentement cookies (si présente).
  4. Vérifier que l'onglet de navigation « API Reference » est rendu.
- **Résultat attendu** :
  - l'URL est sur l'accueil (`#/`) ;
  - le runtime UI5 est présent (`Get Page Composition` : `ui5_runtime=True`) ;
  - l'onglet de navigation d'ancre `idSuffix=apiMasterTab`
    (`sap.m.IconTabFilter`) est présent (comptage `>= 1`). Aucune assertion sur
    le libellé de l'onglet (localisé, « Référence de l'API » / « API Reference »).
- **Keywords métier manquants** :
  - `Open Demo Kit` : ouvre le navigateur sur l'URL du Demo Kit, attend le
    runtime UI5, puis accepte la bannière cookies TrustArc si elle est présente
    (clic sur l'élément DOM de consentement ; ne fait rien si absente).
  - `Accept Cookie Consent` : clique le bouton d'acceptation de la bannière
    TrustArc s'il est présent, sinon ne fait rien (idempotent).

### 2. La navigation vers la Référence de l'API répond

- **Étapes** :
  1. Depuis l'accueil (cookies acceptés), cliquer l'onglet de navigation
     « API Reference » (ancre `idSuffix=apiMasterTab`).
  2. Attendre le retour du runtime UI5.
  3. Lire l'URL courante.
- **Résultat attendu** :
  - l'URL bascule sur la section API : le fragment de hash devient `#/api` ;
  - le champ de filtre du panneau maître (`idSuffix` `apiMaster--searchField`,
    `sap.m.SearchField`) est rendu (comptage `>= 1`).
  L'assertion porte sur le **fragment d'URL** (`#/api`) et sur la présence d'un
  contrôle par son id, jamais sur un texte d'interface.
- **Keywords métier manquants** :
  - `Open Api Reference` : clique l'onglet de navigation « API Reference » par
    son idSuffix stable, attend le runtime UI5, et vérifie que l'URL porte le
    fragment `#/api`.

### 3. La fiche de documentation de `sap.m.Button` s'affiche

- **Étapes** :
  1. Depuis la Référence de l'API, ouvrir la fiche du contrôle `sap.m.Button`
     (navigation par le hash de route `#/api/sap.m.Button`).
  2. Attendre le retour du runtime UI5 puis le repos réseau de la page.
  3. Lire le titre du document et le titre affiché de la fiche.
- **Résultat attendu** :
  - le titre du document est **exactement**
    `sap.m.Button - API Reference - Demo Kit - OPENUI5 SDK` (assertion primaire,
    identifiants techniques non traduits) ;
  - la fiche est structurée en `sap.uxap.ObjectPageLayout`
    (`idSuffix=apiDetailPage`, exactement 1 match) ;
  - le titre affiché de la fiche (`sap.m.Title`) vaut `class sap.m.Button` ;
  - la fiche comporte au moins une rubrique de documentation
    (`sap.uxap.ObjectPageSection`, comptage `>= 1` ; 7 observées : ne pas
    asserter la valeur exacte, le nombre de rubriques d'une fiche varie d'un
    contrôle à l'autre et d'une version de SDK à l'autre).
  L'assertion sur `class sap.m.Button` et sur le nom de classe dans le titre du
  document sont locale-indépendantes (nom de classe UI5, non traduit).
- **Keywords métier manquants** :
  - `Open Control Api Doc` (`${controlName}`) : navigue par la route de hash
    `#/api/${controlName}`, attend le runtime UI5 et le repos réseau, et vérifie
    que le titre du document commence par `${controlName} - API Reference`.
  - `Control Api Doc Should Be Displayed` (`${controlName}`) : vérifie que la
    fiche de doc du contrôle est rendue (ObjectPageLayout `idSuffix=apiDetailPage`
    unique, titre `class ${controlName}` présent, au moins une
    `sap.uxap.ObjectPageSection`).

## Points de vigilance

- **Bannière cookies TrustArc bloquante.** Au premier chargement, un overlay de
  consentement (`trustarc-banner-overlay` / dialogue `consent_blackbar`)
  recouvre la page et **intercepte tous les clics** : un clic sur un onglet UI5
  échoue en `TimeoutError` avec un journal Playwright citant explicitement
  l'overlay. Le bouton d'acceptation est l'élément DOM `truste-consent-button`
  (id DOM stable, 1 exemplaire, atteignable en light DOM). Il faut l'accepter
  avant toute navigation. Cette bannière est **hors runtime UI5** : elle
  n'apparaît ni dans l'arbre UI5 ni dans la carte des cibles, seulement au DOM.
  (Note : la doc du projet mentionnait un id `truste-consent-button` sur cette
  cible ; il est confirmé live, mais via un overlay `trustarc-banner-overlay`,
  pas via une simple case du bandeau.)
- **Locale d'affichage variable et non maîtrisée.** L'interface a été rendue
  en français au premier affichage (« Référence de l'API », « Rechercher tout »,
  « Nouveautés »...) puis a basculé en anglais après acceptation des cookies
  (« API Reference », « News »...). Corollaire : **aucune assertion sur un
  libellé d'onglet, de bouton ou de rubrique**. Les seuls textes exploitables
  sont les identifiants **techniques** non traduits : le nom de classe
  `sap.m.Button`, le titre affiché `class sap.m.Button`, le titre du document
  contenant `sap.m.Button - API Reference`.
- **Application SPA à routage par hash.** Toute la navigation se fait par
  fragment d'URL (`#/`, `#/api`, `#/api/sap.m.Button`). L'ouverture directe
  d'une fiche par son hash de route (`#/api/<contrôle>`) est le chemin le plus
  **déterministe** et reproduit un vrai parcours utilisateur (suivre/coller un
  lien d'API). Le dépliage de l'arbre de navigation du panneau maître est une
  alternative possible mais plus fragile (arbre volumineux, positions
  variables) : il n'a pas été exploré en détail dans cette session et n'est
  donc pas décrit comme chemin nominal.
- **Ancre primaire = idSuffix, jamais l'id complet ni le xpath.** Les ids
  complets portent le préfixe de composant `sdk---app--` / `sdk---apiDetail--` ;
  seul le suffixe (`apiMasterTab`, `apiDetailPage`...) est stable et doit être
  passé en `idSuffix`. Les xpath UI5 les plus courts relevés ici sont purement
  **positionnels** (l'onglet API a résolu `//IconTabFilter[3]`) : ils dérivent
  au moindre ajout d'onglet et ne valent qu'en repli d'une chaîne
  `Resolve Ui5 With Fallback`, jamais comme ancre primaire.
- **Titre de fiche non unique par (controlType + properties).** Le
  `sap.m.Title` de texte `class sap.m.Button` existe en **2 exemplaires**
  (titre pleine largeur + en-tête snappé de l'ObjectPage) : cibler l'unicité par
  l'ObjectPageLayout (`idSuffix=apiDetailPage`, 1 match) et/ou par le titre du
  document, pas par le `sap.m.Title` seul.
- **Le repos réel de la fiche est réseau, pas visuel.** La fiche d'API charge
  ses données par requêtes ; `Wait For Ui5 Idle` a mesuré ~2,8 s de calme
  continu après le rendu initial. Utiliser l'attente réseau/DOM du runtime, pas
  d'attente fixe (convention #2).
- **Périmètre strictement consultatif.** Aucun scénario ne remplit le champ de
  recherche global ni le filtre du panneau maître, ne déplie l'arbre d'API, ni
  ne déclenche d'action : consultation seule, conforme à la demande.
