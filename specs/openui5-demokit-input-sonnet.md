# Consultation de la documentation du contrôle sap.m.Input (OpenUI5 Demo Kit)

- **Canal** : Fiori (web)
- **Système / URL** : Demo Kit public OpenUI5 SDK, `https://sdk.openui5.org/`.
  Application SAPUI5 mono-page (SPA à routage par hash `#/...`), runtime SAPUI5
  **1.151.0** (relevé live le 2026-08-16). Aucune authentification. Cible smoke
  Fiori documentée dans `docs/sap-test-data.md`.
- **Préconditions** :
  - Accès réseau à `sdk.openui5.org` (cible publique, pas d'identifiants).
  - Une **bannière de consentement cookies TrustArc** (élément DOM
    `id=truste-consent-button`, 1 exemplaire) s'affiche au premier chargement et
    intercepte les clics tant qu'elle n'est pas acceptée. Elle doit être acceptée
    avant toute navigation vers les onglets UI5.
  - Aucun réglage persistant requis, consultation seule.

## Données observées

Relevé live le 2026-08-16, exploration pilotée via rf-mcp (Browser + SapFioriLibrary),
navigateur Chrome (channel=chrome), non headless.

### Composition de la page

`Get Page Composition` sur l'accueil : `ui5_runtime=True`, `ui5_version=1.151.0`,
`ui5_controls=551`, `wc_hosts=0`, `webgui_elements=0`, `frameworks=[]`, `frames=[]`,
moteurs recommandés `['role', 'xpath', 'dom']`. Page mono-technologie UI5 : le moteur
`role` (résolution par controlType / idSuffix) suffit, aucune frame à empiler.

Sur la fiche `sap.m.Input` chargée intégralement : `ui5_controls=5827` (la fiche
est volumineuse, données chargées par requêtes réseau, repos mesuré par
`Wait For Ui5 Idle` à ~6,9 s de calme continu : `{'pending': 0, 'busy': False,
'quiet_ms': 6898}`).

La bannière TrustArc est **hors runtime UI5** : elle n'apparaît pas dans l'arbre
UI5 ni dans la carte des cibles, seulement au DOM.

### Barre de navigation principale (toutes les pages)

Onglets de navigation : `sap.m.IconTabFilter`, id complet `sdk---app--<tab>Tab`,
ancre stable = idSuffix `<tab>Tab`.

| Rôle fonctionnel | idSuffix | id complet observé |
|---|---|---|
| Accueil (Home) | `welcomeTab` | `sdk---app--welcomeTab` |
| Documentation | `topicMasterTab` | `sdk---app--topicMasterTab` |
| **Référence de l'API (API Reference)** | `apiMasterTab` | `sdk---app--apiMasterTab` |
| Échantillons (Samples) | `controlsMasterTab` | `sdk---app--controlsMasterTab` |
| Demo Apps | `demoAppsTab` | `sdk---app--demoAppsTab` |
| Resources | `resourcesTab` | `sdk---app--resourcesTab` |

- Zone de recherche globale de l'en-tête : idSuffix `searchControl-searchField`
  (`sap.m.SearchField`), id complet `sdk---app--searchControl-searchField`.
- Les libellés de ces onglets sont **localisés** (« Référence de l'API » / « API
  Reference » selon la locale détectée) et ne constituent pas des ancres fiables.
  Le clic sur « API Reference » fait passer l'URL de `#/` à `#/api`.

### Page « API Reference » (`#/api`)

- Champ de filtre du panneau maître : idSuffix `apiMaster--searchField`,
  id complet `sdk---apiMaster--searchField` (`sap.m.SearchField`).
- Boutons déplier / replier : idSuffix `apiMaster--expandAllButton` et
  `apiMaster--collapseAllButton` (`sap.m.Button`).
- La fiche d'un contrôle est accessible directement par la route de hash
  `#/api/<nom.qualifié>` : c'est le chemin déterministe utilisé pour ouvrir
  `sap.m.Input` sans dépendre du dépliage de l'arbre de navigation.

### Fiche du contrôle `sap.m.Input` (`#/api/sap.m.Input`)

- **Titre du document** (onglet du navigateur) :
  `sap.m.Input - API Reference - Demo Kit - OPENUI5 SDK`. Identifiants techniques
  non traduits : assertion primaire locale-indépendante.
- **ObjectPageLayout** : idSuffix `apiDetailObjectPage`, id complet
  `__xmlview0--apiDetailObjectPage`, classe CSS `sapUxAPObjectPageLayout`
  (1 match unique, c'est l'ancre structurelle de la fiche).
- **Titre affiché de la fiche** : texte `class sap.m.Input` porté par un
  `sap.m.Title`. Ce texte apparaît en **2 exemplaires** dans l'ObjectPage
  (ids observés `__title9` et `__title10`, version étendue + version snappée
  de l'en-tête dynamique) : cibler par le titre du document ou par
  l'ObjectPageLayout, jamais par le `sap.m.Title` seul.
- **Structure de la fiche** : 8 `sap.uxap.ObjectPageSection` (rubriques de
  documentation), relevées live par `css=section.sapUxAPObjectPageSection` :

| Rang | Titre observé | idSuffix de section |
|---|---|---|
| 1 | Overview | `overview` |
| 2 | Fields | `properties` |
| 3 | Constructor | `constructor` |
| 4 | Properties | `controlproperties` |
| 5 | Aggregations | `aggregations` |
| 6 | Associations | `associations` |
| 7 | Events | `events` |
| 8 | Methods | `methods` |

  Note : `sap.m.Input` a **8 rubriques** (dont « Fields » et « Associations »),
  contre 7 pour `sap.m.Button`. Ne pas asserter la valeur exacte : elle varie
  selon le contrôle et la version du SDK.

- **Contenu de la section Overview** (texte extrait live) : « Allows the user to
  enter and edit text or numeric values in one line. » (début de la description).
  Identifiant DOM de la section : `__xmlview0--overview`.

- **Propriétés documentées** (section Properties, id `__xmlview0--controlproperties`) :
  parmi les propriétés visibles dans la fiche, on trouve notamment :
  `autocomplete` (boolean, valeur par défaut `true`), `dateFormat` (string,
  valeur par défaut `YYYY-MM-dd`), `maxLength`, `showClearIcon`, `showValueHelp`,
  `textFormatMode`, `type`, `valueHelpOnly`. Les libellés de colonne du tableau
  sont localisés (Name / Type / Default Value / Description en EN, ou leurs
  traductions) : ne jamais asserter ces libellés.

- **Signature du constructeur** (section Constructor, id `__xmlview0--constructor`) :
  `new sap.m.Input(sId?, mSettings?)`.

- **Événements documentés** (section Events, id `__xmlview0--events`) :
  liens hypertextes observés dans la section : `liveChange`, `submit`, `suggest`,
  `suggestionItemSelected`, `valueHelpRequest`, `change`, `validateFieldGroup`,
  `formatError`, `parseError`, `validationError`, `validationSuccess`.
  Événements propres à l'Input (hors héritage) : `liveChange`, `submit`,
  `suggest`, `suggestionItemSelected`, `valueHelpRequest`.

## Scénarios

### 1. L'accueil du Demo Kit se charge et expose la barre de navigation

- **Préconditions** : accès réseau à `sdk.openui5.org`.
- **Étapes** :
  1. Ouvrir le navigateur sur `https://sdk.openui5.org/` (Suite Setup).
  2. Attendre le retour du runtime UI5 (`Wait For Ui5 Ready`).
  3. Accepter la bannière de consentement cookies si présente
     (clic sur `id=truste-consent-button`, conditionnel au comptage `>= 1`).
  4. Attendre à nouveau le runtime UI5.
  5. Lire le titre du document (`Get Title`).
- **Résultats attendus** :
  - le titre du document est `Demo Kit - OPENUI5 SDK` (identifiant technique,
    non traduit) ;
  - `Get Page Composition` retourne `ui5_runtime=True` ;
  - l'onglet de navigation `idSuffix=apiMasterTab` (`sap.m.IconTabFilter`)
    est présent (résolution réussie, 1 match) ;
  - la bannière de consentement est absente après acceptation (comptage `= 0`).
  - Aucune assertion sur les libellés affichés des onglets (localisés, variables).
- **Keywords métier manquants** :
  - `Open Demo Kit` : ouvre le navigateur sur l'URL du Demo Kit, attend le
    runtime UI5, accepte la bannière TrustArc si présente.
  - `Accept Cookie Consent` : clique `id=truste-consent-button` si présent
    (idempotent, ne fait rien si absent).

### 2. La navigation vers la Référence de l'API répond

- **Préconditions** : scénario 1 exécuté (navigateur sur l'accueil, cookies
  acceptés).
- **Étapes** :
  1. Cliquer l'onglet de navigation « API Reference » par son idSuffix
     `apiMasterTab` (`Click Ui5 Control    idSuffix=apiMasterTab`).
  2. Attendre le retour du runtime UI5 (`Wait For Ui5 Ready`).
  3. Lire l'URL courante (`Get Url`).
- **Résultats attendus** :
  - l'URL porte le fragment `#/api` (assertion sur le fragment d'URL) ;
  - le champ de filtre du panneau maître (idSuffix `apiMaster--searchField`,
    `sap.m.SearchField`) est présent (résolution réussie).
  - Aucune assertion sur le libellé de l'onglet ni sur le titre de la page
    (tous deux localisés).
- **Keywords métier manquants** :
  - `Open Api Reference` : clique l'onglet de navigation « API Reference » par
    son idSuffix, attend le runtime UI5, vérifie le fragment d'URL `#/api`.

### 3. La fiche de documentation de `sap.m.Input` s'affiche

- **Préconditions** : scénario 2 exécuté (page sur `#/api`).
- **Étapes** :
  1. Naviguer vers `https://sdk.openui5.org/#/api/sap.m.Input` (`Go To`).
  2. Attendre le retour du runtime UI5 (`Wait For Ui5 Ready`).
  3. Attendre le repos réseau réel de la fiche (`Wait For Ui5 Idle`).
  4. Lire le titre du document (`Get Title`).
- **Résultats attendus** :
  - le titre du document est exactement
    `sap.m.Input - API Reference - Demo Kit - OPENUI5 SDK` (assertion primaire,
    identifiants techniques non traduits) ;
  - l'ObjectPageLayout (`idSuffix=apiDetailObjectPage`) est présent, exactement
    1 match ;
  - la fiche comporte au moins une rubrique de documentation
    (`css=section.sapUxAPObjectPageSection`, comptage `>= 1` ; 8 observées :
    ne pas asserter la valeur exacte).
  - Aucune assertion sur les libellés de rubriques (localisés).
- **Keywords métier manquants** :
  - `Open Control Api Doc` (`${controlName}`) : navigue par la route de hash
    `#/api/${controlName}`, attend le runtime UI5 et le repos réseau, vérifie
    que le titre du document commence par `${controlName} - API Reference`.
  - `Control Api Doc Should Be Displayed` (`${controlName}`) : vérifie que la
    fiche est rendue (ObjectPageLayout `idSuffix=apiDetailObjectPage` unique,
    au moins une `section.sapUxAPObjectPageSection`).

### 4. Les rubriques clés de la fiche `sap.m.Input` sont accessibles

- **Préconditions** : scénario 3 exécuté (fiche `sap.m.Input` chargée).
- **Étapes** :
  1. Vérifier la présence de la section Overview (`idSuffix=overview`).
  2. Lire le texte visible de la section Overview.
  3. Vérifier la présence de la section Properties (`idSuffix=controlproperties`).
  4. Vérifier la présence de la section Events (`idSuffix=events`).
- **Résultats attendus** :
  - la section `idSuffix=overview` est présente (1 match) ;
  - le texte de la section Overview contient la mention du champ de saisie
    (extrait observé : « Allows the user to enter and edit text or numeric
    values in one line. ») ; l'assertion porte sur la présence de la section,
    pas sur un texte traduit ;
  - la section `idSuffix=controlproperties` est présente (1 match) ;
  - la section `idSuffix=events` est présente (1 match).
  - Aucune assertion sur les libellés traduits des rubriques (« Overview »,
    « Properties », « Events » sont des libellés UI localisés).
- **Keywords métier manquants** :
  - `Api Doc Section Should Be Present` (`${idSuffix}`) : vérifie qu'une
    rubrique de fiche d'API (idSuffix de section) est présente, 1 match.

## Localisateurs observés

Tous les idSuffixes ci-dessous ont été résolus live par `Resolve Ui5 Control` ou
confirmés via `Get Element Count` / `Evaluate JavaScript`.

| Élément | idSuffix (ancre stable) | id complet observé | controlType |
|---|---|---|---|
| Onglet API Reference | `apiMasterTab` | `sdk---app--apiMasterTab` | `sap.m.IconTabFilter` |
| Onglet Accueil | `welcomeTab` | `sdk---app--welcomeTab` | `sap.m.IconTabFilter` |
| Champ de filtre API Master | `apiMaster--searchField` | `sdk---apiMaster--searchField` | `sap.m.SearchField` |
| ObjectPageLayout de la fiche | `apiDetailObjectPage` | `__xmlview0--apiDetailObjectPage` | `sap.uxap.ObjectPageLayout` |
| Section Overview | `overview` | `__xmlview0--overview` | `sap.uxap.ObjectPageSection` |
| Section Fields | `properties` | `__xmlview0--properties` | `sap.uxap.ObjectPageSection` |
| Section Constructor | `constructor` | `__xmlview0--constructor` | `sap.uxap.ObjectPageSection` |
| Section Properties | `controlproperties` | `__xmlview0--controlproperties` | `sap.uxap.ObjectPageSection` |
| Section Aggregations | `aggregations` | `__xmlview0--aggregations` | `sap.uxap.ObjectPageSection` |
| Section Associations | `associations` | `__xmlview0--associations` | `sap.uxap.ObjectPageSection` |
| Section Events | `events` | `__xmlview0--events` | `sap.uxap.ObjectPageSection` |
| Section Methods | `methods` | `__xmlview0--methods` | `sap.uxap.ObjectPageSection` |
| Bannière TrustArc (DOM) | N/A | `truste-consent-button` | Élément DOM (hors UI5) |

Note : le préfixe `sdk---app--` des onglets et `__xmlview0--` des sections de fiche
sont des préfixes de composant instables. Seul le **suffixe** (la partie après `--`)
est l'ancre déterministe à passer en `idSuffix`.

## Données de test

- **URL cible** : `https://sdk.openui5.org/`
- **Route de hash du contrôle** : `#/api/sap.m.Input`
- **Titre attendu de la fiche** : `sap.m.Input - API Reference - Demo Kit - OPENUI5 SDK`
- **Titre attendu de l'accueil** : `Demo Kit - OPENUI5 SDK`
- **Titre affiché de la fiche** (texte du `sap.m.Title`) : `class sap.m.Input`
  (non localisé, nom de classe UI5 technique).
- **Nombre de sections observées** : 8 (Overview, Fields, Constructor, Properties,
  Aggregations, Associations, Events, Methods).
- **Propriétés échantillon** : `autocomplete` (boolean, défaut `true`),
  `dateFormat` (string, défaut `YYYY-MM-dd`), `maxLength`, `showClearIcon`,
  `showValueHelp`, `type`, `valueHelpOnly`.
- **Événements propres** : `liveChange`, `submit`, `suggest`, `suggestionItemSelected`,
  `valueHelpRequest`.
- **Signature du constructeur** : `new sap.m.Input(sId?, mSettings?)`.

## Keywords métier manquants

À créer par sap-generator dans `resources/fiori_keywords.resource` (ou dans une
resource dédiée au Demo Kit si ce type d'exploration est récurrent) :

| Nom proposé | Intention |
|---|---|
| `Open Demo Kit` | Ouvre le navigateur sur `https://sdk.openui5.org/`, attend le runtime UI5, accepte la bannière TrustArc si présente. |
| `Accept Cookie Consent` | Clique `id=truste-consent-button` si présent (idempotent). |
| `Open Api Reference` | Clique l'onglet `idSuffix=apiMasterTab`, attend le runtime UI5, vérifie le fragment d'URL `#/api`. |
| `Open Control Api Doc` | Navigue vers `#/api/${controlName}`, attend UI5 + repos réseau, vérifie le titre du document. |
| `Control Api Doc Should Be Displayed` | Vérifie que l'ObjectPageLayout `idSuffix=apiDetailObjectPage` est présent (1 match) et qu'au moins une section est rendue. |
| `Api Doc Section Should Be Present` | Vérifie qu'une section de fiche (idSuffix) est rendue, 1 match. |

## Points de vigilance

- **Bannière TrustArc bloquante.** Au premier chargement, l'overlay de consentement
  (`truste-consent-button`) intercepte tous les clics sur la page. Le cliquer avant
  toute interaction avec les onglets UI5. Cette bannière est hors runtime UI5 et
  n'apparaît pas dans la carte des cibles (`Get Ui5 Page Map`).
- **Locale d'affichage non maîtrisée.** L'interface peut s'afficher en français
  ou en anglais selon la locale détectée. Aucune assertion sur les libellés
  d'onglets, de boutons ou de rubriques. Les ancres valides sont les identifiants
  techniques non traduits : nom de classe `sap.m.Input`, titre du document,
  idSuffixes des contrôles.
- **SPA à routage par hash.** Toute la navigation se fait par fragment d'URL.
  L'ouverture directe d'une fiche par `#/api/sap.m.Input` est le chemin le plus
  déterministe. Le dépliage de l'arbre de navigation du panneau maître (arbre
  volumineux, positions variables) n'a pas été exploré et n'est pas décrit.
- **Titre de fiche non unique.** Le texte `class sap.m.Input` existe en **2
  exemplaires** dans l'ObjectPage (titre étendu + version snappée de l'en-tête
  dynamique). Cibler par le titre du document ou l'ObjectPageLayout, pas par le
  `sap.m.Title` seul.
- **Repos réseau nécessaire après navigation.** La fiche charge ses données par
  requêtes ; `Wait For Ui5 Idle` a mesuré ~6,9 s de calme continu. Utiliser
  `Wait For Ui5 Idle` (repos réel réseau/DOM), pas d'attente fixe (convention #2).
- **idSuffix `apiDetailObjectPage` versus `apiDetailPage`.** Les deux idSuffixes
  existent dans le DOM (`__xmlview0--apiDetailPage` est un autre élément, probablement
  la vue parente). L'ObjectPageLayout est `apiDetailObjectPage` (classe CSS
  `sapUxAPObjectPageLayout`).
- **Consultation seule.** Aucun scénario ne remplit le champ de recherche global
  ni le filtre du panneau maître, ne déplie l'arbre d'API, ni ne déclenche d'action
  autre que la navigation.
