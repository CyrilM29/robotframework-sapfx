# Zone utilisateur et paramètres du shell d'un launchpad Work Zone (BTP)

- **Canal** : Fiori (web), cFLP **SAP Build Work Zone** hébergé sur SAP BTP,
  derrière un tenant **SAP Cloud Identity Services** (IAS).
- **Système / URL** : fournis en ligne de commande (`-v WORKZONE_SITE:…`,
  `-v WORKZONE_USER:…`, `-v "WORKZONE_PASSWORD: Secret:…"`), jamais écrits dans
  le dépôt (convention 11 ; l'URL du site et celle du tenant sont des données
  privées).
- **Exploration live** : **2026-08-26**, rf-mcp (Browser + SapFioriLibrary),
  Chromium sans interface, fenêtre 1600 x 1000, navigateur en français.
  Runtime relevé : **SAPUI5 1.151.0** (identique au relevé du 2026-08-24 de
  [workzone-launchpad-btp-perception.md](workzone-launchpad-btp-perception.md),
  re-constaté et non recopié).
- **Pendant de** : [exploration-flp-abap-a4h.md](exploration-flp-abap-a4h.md)
  (ushell ABAP 1.71) et [exploration-flp-abap-2023.md](exploration-flp-abap-2023.md)
  (ushell ABAP 1.120). Ces deux campagnes mesurent les mêmes dimensions sur un
  launchpad servi par un serveur ABAP ; celle-ci les mesure sur un cFLP de
  plateforme, et la section « Écarts face aux launchpads ABAP » est la raison
  d'être du document.
- **Préconditions** :
  - un utilisateur du tenant, avec au moins une application publiée au
    catalogue du site ;
  - navigateur Chromium fourni par la bibliothèque Browser (`rfbrowser init`).
- **Portée** : **lecture seule**. Les dialogues sont ouverts, lus, puis
  refermés par leur action d'annulation. Aucun bouton d'enregistrement n'est
  actionné. Deux surfaces sont ouvertes mais **jamais actionnées** : le
  **Theme Manager** (administration du site, voir scénario 8) et l'entrée
  **Manage Site** de la zone utilisateur. Le teardown de suite vérifie que le
  thème et la langue du compte sont ceux relevés au démarrage.

## Données observées

Tout ce qui suit a été relevé live le 2026-08-26. Rien n'est déduit.

### Identité de la cible et du compte

| Fait | Valeur relevée |
|---|---|
| Runtime UI5 (`sap.ui.version`) | `1.151.0` |
| Contrôles UI5 sur l'accueil, chargement neuf | **139** |
| Hôtes Web Components dans le **light DOM** | **6** |
| Hôtes Web Components **en comptant les shadow roots** | **16** |
| iframes sur l'accueil | 0 |
| Moteurs recommandés | `role`, `xpath`, `wc`, `dom` |
| Identifiant utilisateur (`Container.getUser().getId()`) | un **GUID**, jamais un nom de connexion |
| Langue du compte (`getLanguage()`) | `en` |
| Thème du compte (`getTheme()`) | `sap_horizon` |
| `document.documentElement.lang` | `en` |
| `navigator.language` du poste | `fr` |

Le dernier couple est un fait de campagne, pas un détail : **le shell rend ses
libellés en anglais sur un navigateur français**, parce que le site ne publie
pas de traduction française (voir la rubrique de langue ci-dessous). Une
assertion de texte serait donc fausse dans un sens ou dans l'autre selon le
poste ET selon le site.

### Barre shell : Web Components à tags scopés

Les hôtes portent un suffixe de scoping (forme `ui5-shellbar-<suffixe>`), déjà
relevé le 2026-08-24 avec la même valeur. **Ce suffixe ne doit jamais entrer
dans un localisateur** : c'est une empreinte de build.

| Rôle | Ancre retenue | Type de contrôle | Emplacement | Accueil | Application |
|---|---|---|---|---|---|
| Zone utilisateur | `userActionsMenuHeaderButton` | `sap.f.gen.ui5.webcomponents.dist.Avatar` (hôte `ui5-avatar`) | light DOM | oui | oui |
| Theme Manager | `controlType=ShellBarItem` + `properties={'icon': 'palette'}` | `…webcomponents_fiori.dist.ShellBarItem` | light DOM | oui | oui |
| Titre / menu des applications | `shellAppTitle` | `sap.ushell.ui.shell.ShellAppTitle` | light DOM | oui | oui |
| Marque du site | id généré `__branding0` | `…dist.ShellBarBranding` | light DOM | oui | oui |
| Espaceur | `shellBarSpacer` | `…dist.ShellBarSpacer` | light DOM | déclaré, jamais rendu | idem |
| Bouton retour | `backBtn` | hôte `ui5-button` | light DOM | **absent** | **présent** |
| Bouton de recherche | **aucun identifiant** | hôte `ui5-button`, attribut `icon="search"` | **shadow root du `ui5-shellbar`** | oui | oui |
| Notifications | **inexistant** | | | | |

L'identifiant du Theme Manager (`__item4` sur ce run) est **généré** : l'ancre
tenable est le couple type plus icône, mesuré à **1** correspondance sur
l'ensemble du shell.

L'absence de notifications est double et donc solide : aucun élément dans la
barre, et **aucun service de notification** parmi les **24** services déclarés
par la configuration ushell.

### Zone utilisateur : un `ui5-user-menu`, pas un `sap.m.Popover`

| Fait | Valeur relevée |
|---|---|
| Ancre du menu | `sapUshellUserActionsMenuPopover` |
| Type | `sap.f.gen.ui5.webcomponents_fiori.dist.UserMenu` (hôte `ui5-user-menu`) |
| Entête du menu | avatar, nom complet (`selected-account-title`) et adresse de courriel du compte |
| Entrée de compte | `__account0`, type `…dist.UserMenuAccount`, **jamais rendue visible** |
| Forme des identifiants d'entrée | `sapUshellUserActionsMenuPopover-<index>-<action>` |
| Type d'une entrée | `sap.f.gen.ui5.webcomponents_fiori.dist.UserMenuItem` |

Entrées relevées, avec leur position **sur l'accueil** :

| Entrée | Suffixe d'action | Libellé rendu | Icône | Position accueil | Position en application |
|---|---|---|---|---|---|
| Paramètres | `-userSettingsBtn` | Settings | `action-settings` | 0 | 0 |
| App Finder | `-openCatalogBtn` | App Finder | `sys-find` | 1 | 1 |
| Édition de l'accueil | `-ActionModeBtn` | Edit Home Page | `edit` | 2 | **absente** |
| Administration du site | `-manageSiteBtn` | Manage Site | `customize` | 3 | 2 |
| À propos | `-aboutBtn` | About | `hint` | 4 | 3 |

Soit **5 entrées à l'accueil et 4 dans une application**, l'écart se réduisant
exactement à l'entrée d'édition. **L'index change avec l'endroit** (`-4-aboutBtn`
à l'accueil, `-3-aboutBtn` en application) : seul le suffixe d'action est une
ancre.

**La déconnexion n'est pas une entrée de liste.** C'est un `ui5-button`
`design="Transparent"` rendu dans le shadow root du popover, **sans identifiant**,
au pied du menu.

Deux faits d'ouverture et de fermeture, tous deux mesurés :

- **Les 5 entrées restent RENDUES menu fermé** (`Get Ui5 Match Count` sur le
  type `UserMenuItem` retourne 5 dans les deux états). Compter les entrées ne
  prouve donc RIEN sur l'ouverture du menu.
- Le témoin qui tranche est la propriété **`open`** du menu : `False` fermé,
  `True` ouvert.
- L'échappement **et** un second clic sur l'avatar referment tous deux le menu
  sur cette cible.

### Dialogues du shell

| Dialogue | Identifiant | Type et état | Boutons dans l'agrégation `buttons` | Actions réelles |
|---|---|---|---|---|
| Paramètres | `settingsView--userSettingsDialog` | `sap.m.Dialog` | **0** | `settingsView--userSettingSaveButton`, `settingsView--userSettingCancelButton` (barre de pied) |
| À propos | `aboutDialogFragment--aboutDialog` | `sap.m.Dialog`, état `None` | **1** | **id stable** `aboutDialogFragment--aboutDialogCloseButton` |
| Theme Manager | `themeDesignDialog` | `sap.m.Dialog` | **0** | `userSelectionButton`, `saveButton`, `cancelButton`, plus Refresh, Set As Default, Preview, Launch Theme Designer |
| Refus de navigation | `__dialog0`, **généré et RÉUTILISÉ d'un refus à l'autre** | `sap.m.Dialog`, état **`Error`** | **2** | `[0]` Copy (`Default`), `[1]` Close (**`Emphasized`**) |

Fait mesuré et piégeux : **après annulation, le dialogue des paramètres reste
RENDU** (1 `sap.m.Dialog` dans le registre) alors qu'il n'est plus **ouvert**.
La lecture qui tranche est celle des popups ouverts, jamais un comptage de
dialogues rendus.

### Rubriques du dialogue des paramètres

Identifiants de rubrique **entièrement générés**
(`__item5-settingsView--userSettingEntryList-<index>`) : la clé technique vit
dans le contexte de liaison, propriété `id`.

| Position | Clé technique | Libellé rendu | Icône |
|---|---|---|---|
| 0 | `userAccountEntry` | User Account | `account` |
| 1 | `themes` | Appearance | `palette` |
| 2 | `language` | Language and Region | `map` |
| 3 | `homepageEntry` | Home Page | `home` |
| 4 | **`id-<horodatage>-<n>`** | Joule Work Mobile App | `iphone` |

La cinquième clé est **générée avec un horodatage** : une rubrique apportée par
une extension du site n'a pas de clé stable. Conséquence de conception : la
campagne vérifie la présence des clés du **socle** (`userAccountEntry`,
`themes`, `language`, `homepageEntry`) et **journalise** les autres, sans
jamais asserter l'ensemble complet.

Contenu relevé de la rubrique **User Account** : `userAccountSetting--userAccountuserName`,
`--userAccountuserMail`, `--userAccountuserServer` (l'hôte du site), et
**`--resetPersonalizationButton`** (« Reset All Personalization »), un bouton
d'écriture destructive **jamais actionné** par cette campagne.

### Rubrique « Appearance » : thèmes offerts

`userPrefThemeSelector--themeList` (`sap.m.List`), items `sap.m.CustomListItem`
aux ids générés. Les identifiants techniques vivent dans le contexte de liaison.

| Identifiant technique | Libellé rendu | Sélectionné |
|---|---|---|
| `sap_fiori_3_set` | Automatic (based on your operating system settings) | non |
| `sap_fiori_3` | SAP Quartz Light | non |
| `sap_fiori_3_dark` | SAP Quartz Dark | non |
| `sap_horizon_set` | Automatic (based on your operating system settings) | non |
| `sap_horizon` | SAP Morning Horizon | **oui** |
| `sap_horizon_dark` | SAP Evening Horizon | non |
| `sap_horizon_hcw` | SAP High Contrast White (Horizon) | non |
| `sap_horizon_hcb` | SAP High Contrast Black (Horizon) | non |

**Deux entrées portent exactement le même libellé** (`sap_fiori_3_set` et
`sap_horizon_set`) : un localisateur par nom visible est ambigu par
construction, et seul l'identifiant technique désambiguïse.

### Rubrique « Language and Region »

| Champ | Ancre | Valeur relevée |
|---|---|---|
| Sélecteur de langue | `userLanguageAndRegion--languageSelectionSelect` (`sap.m.ComboBox`) | clé sélectionnée **`default`** |
| Options offertes | | **2** : `default` (« Browser Language ») et `en` (« English ») |
| Fuseau horaire | `userLanguageAndRegion--selectedTimeZone` | `Europe/Paris` (identifiant IANA, locale-indépendant) |
| Format de date | `--selectedDateFormat` | rendu localisé, à journaliser seulement |
| Format d'heure | `--selectedTimeFormat` | `12 h` |
| Format décimal | `--selectedDecimalFormat` | `1,000.2` |
| Semaine de travail | `--selectedWorkWeek` | rendu localisé |

C'est l'explication mesurée du paradoxe d'entête : la langue est réglée sur
« langue du navigateur », le navigateur est en français, et le site ne publie
que l'anglais.

### Dialogue « à propos »

Trois rubriques, ids **entièrement générés**, aucune clé technique dans le
contexte de liaison : leur seule adresse est la **position** dans
`aboutDialogFragment--aboutDialogEntryList`.

| Position | Rubrique | Contenu relevé |
|---|---|---|
| 0 | App | SAP Fiori ID `LAUNCHPAD`, Version `1.151.0`, Application Component `CA-FLP-FE-COR`, SAPUI5 App ID `sap.ushell.components.homepage`, App Type `SAPUI5`, Framework Version `1.151.0 (<horodatage de build>)` |
| 1 | System | **vide** (aucune ligne) |
| 2 | Environment | Device Type `Desktop`, Theme **`sap_horizon`** (identifiant technique), indicateurs tactiles, agent utilisateur |

La rubrique « System » vide est un résultat, pas une anomalie : il n'y a pas de
système ABAP derrière ce launchpad. Et le thème y est donné sous sa forme
**technique**, ce qui en fait un recoupement locale-indépendant avec
`Container.getUser().getTheme()`.

### Ce que la configuration du shell déclare

`window['sap-ushell-config'].ushell`, lu live, annonce ce que le shell offre.
Ce sont des valeurs techniques, donc assertables :

| Clé | Valeur |
|---|---|
| `userActionsMenu.displayAvatar` | `true` |
| `shellBar.enabled` | `true` |
| `darkMode.enabled` | `true` |
| `home.tilesWrappingType` | `Hyphenated` |
| `workPages.userHome.configurable` | `false` |
| `searchCEPNew.enabled` | `false` (voir [workzone-recherche-shell.md](workzone-recherche-shell.md)) |

## Scénarios

### 1. La barre shell est en Web Components et sa zone utilisateur est un avatar
- **Étapes** :
  1. Ouvrir la session et attendre le rendu réel du shell.
  2. Lire la composition de la page.
  3. Compter les hôtes Web Components du light DOM, puis en comptant les
     shadow roots.
  4. Résoudre la zone utilisateur et lire son type de contrôle.
  5. Lire la clé de configuration qui déclare l'affichage en avatar.
- **Résultat attendu** : runtime UI5 présent, moteur `wc` proposé, au moins un
  hôte de barre shell ; le comptage **profond** est strictement supérieur au
  comptage **light** (mesuré 16 contre 6), ce qui prouve que le shell imbrique
  des composants dans des shadow roots ; le type de la zone utilisateur est un
  `Avatar` de la distribution Web Components, et la configuration le déclare.
- **Pourquoi ce scénario ne peut pas passer sur du vide** : le contrôle
  d'inégalité entre les deux comptages échoue sur une page qui n'aurait aucun
  composant imbriqué, et la lecture du type échoue si la zone utilisateur n'est
  pas rendue.
- **Keywords métier manquants** :
  - `Compter Les Web Components Du Shell` (portée light DOM),
  - `Compter Les Web Components Imbriques Du Shell` (en traversant les shadow
    roots),
  - `Lire Le Type De La Zone Utilisateur`,
  - `Lire La Configuration Du Shell` (retourne le dict `ushell` de la
    configuration, JSON-safe).

### 2. La zone utilisateur ouvre un menu dont l'ouverture se constate sur une propriété
- **Étapes** :
  1. Menu fermé : compter les entrées du menu, puis lire la propriété
     d'ouverture.
  2. Ouvrir la zone utilisateur.
  3. Compter de nouveau les entrées, relire la propriété d'ouverture.
  4. Refermer par l'échappement, relire la propriété.
  5. Rouvrir, refermer par un second clic sur l'avatar, relire la propriété.
- **Résultat attendu** : les deux comptages d'entrées sont **égaux** (mesuré 5
  et 5), donc le comptage ne distingue pas les deux états ; la propriété
  d'ouverture vaut **faux** avant, **vrai** après, **faux** après chacune des
  deux fermetures.
- **Ce que le scénario établit** : le témoin d'ouverture d'un menu en Web
  Components n'est ni la présence ni le comptage de ses entrées. Sans ce
  scénario, un test « j'ai cliqué l'avatar, je vois 5 entrées » serait vert
  sans avoir jamais ouvert le menu.
- **Keywords métier manquants** :
  - `Ouvrir La Zone Utilisateur`, `Fermer La Zone Utilisateur Par Echappement`,
    `Fermer La Zone Utilisateur Par Bascule`,
  - `La Zone Utilisateur Est Ouverte` / `La Zone Utilisateur Est Fermee`
    (prédicats sur la propriété d'ouverture),
  - `Compter Les Entrees De La Zone Utilisateur`.

### 3. Les entrées de la zone utilisateur dépendent de l'endroit
- **Étapes** :
  1. Sur l'accueil : ouvrir la zone utilisateur, relever les **suffixes
     d'action** de ses entrées, refermer.
  2. Ouvrir l'application du catalogue par son intent.
  3. Refaire le même relevé.
  4. Revenir à l'accueil et comparer les deux relevés.
- **Résultat attendu** : les deux relevés contiennent les entrées permanentes
  (paramètres, App Finder, administration du site, à propos) ; le relevé fait
  sur l'accueil contient **exactement une entrée de plus**, celle de l'édition
  de l'accueil ; l'**index** porté par l'identifiant d'une même entrée **diffère
  entre les deux endroits**, ce qui est journalisé comme la preuve que l'index
  n'est pas une ancre.
- **Assertions locale-indépendantes** : les suffixes d'action, l'**écart** entre
  deux relevés du même run, jamais un cardinal gravé ni un libellé.
- **Keywords métier manquants** :
  - `Lire Les Suffixes D Action De La Zone Utilisateur`,
  - `Lire Les Identifiants Des Entrees De La Zone Utilisateur` (pour la trace
    des index).

### 4. Le dialogue « à propos » identifie le launchpad et son runtime
- **Étapes** :
  1. Ouvrir la zone utilisateur, puis l'entrée « à propos ».
  2. Constater qu'un dialogue est **ouvert** et relever sa structure.
  3. Lire la rubrique « App ».
  4. Parcourir les trois rubriques par leur **position** et relever leur contenu.
  5. Refermer par le bouton de fermeture, à son **identifiant stable**.
- **Résultat attendu** : un unique popup ouvert, de type dialogue, état `None`,
  **un** bouton ; la rubrique « App » nomme le composant applicatif de la cible
  et une version de framework qui partage la ligne majeure et mineure du
  runtime chargé ; la rubrique « Environment » donne le thème sous sa forme
  **technique**, et cette valeur est **identique** à celle rendue par le
  conteneur ushell ; après fermeture, plus aucun popup n'est ouvert.
- **Note d'assertion** : la rubrique « System » est vide sur un cFLP. Le
  scénario le constate et ne l'exige pas non vide, sinon il serait rouge ici et
  vert sur un FLP ABAP pour une raison qui n'est pas un défaut.
- **Keywords métier manquants** :
  - `Ouvrir L Entree De La Zone Utilisateur` (par suffixe d'action),
  - `Le Dialogue A Propos Est Ouvert`, `Lire Les Rubriques Du Dialogue A Propos`,
    `Lire L Empreinte Du Launchpad`, `Fermer Le Dialogue A Propos`.

### 5. Le dialogue des paramètres s'ouvre, expose ses rubriques et se referme sans rien écrire
- **Étapes** :
  1. Relever le thème et la langue du compte au conteneur ushell.
  2. Ouvrir la zone utilisateur, puis l'entrée des paramètres.
  3. Constater l'ouverture, relever les **clés techniques** des rubriques
     (contexte de liaison, jamais l'identifiant ni le libellé).
  4. Vérifier que les actions d'enregistrement et d'annulation sont rendues.
  5. Refermer par **annuler**.
  6. Constater qu'aucun popup n'est ouvert, et que thème et langue sont
     inchangés.
- **Résultat attendu** : le dialogue est ouvert ; les quatre clés du socle sont
  présentes et les clés supplémentaires sont journalisées ; le dialogue expose
  bien **zéro** bouton dans son agrégation d'actions et **deux** actions dans sa
  barre de pied ; après annulation, aucun popup n'est ouvert et le couple thème
  plus langue est **strictement identique** au relevé de l'étape 1.
- **LECTURE SEULE assumée** : le bouton d'enregistrement écrit une
  personnalisation utilisateur, et le bouton de réinitialisation de la rubrique
  « User Account » détruit toutes les personnalisations. Ni l'un ni l'autre
  n'est actionné.
- **Piège à ne pas reproduire** : après annulation, le dialogue reste **rendu**.
  La constatation de fermeture porte sur les popups **ouverts**, jamais sur un
  comptage de dialogues rendus, faute de quoi le mot-clé générique
  `Popup Is Present` de la couche resources répondrait vrai sur un écran propre.
- **Keywords métier manquants** :
  - `Ouvrir Les Parametres Utilisateur`, `Le Dialogue Des Parametres Est Ouvert`,
  - `Lire Les Cles Des Rubriques De Parametres`,
  - `Annuler Les Parametres Utilisateur`,
  - `Lire L Identite De Session` (identifiant, langue, thème),
  - `Aucun Popup N Est Ouvert`.

### 6. La rubrique d'apparence propose des thèmes identifiés techniquement
- **Étapes** :
  1. Ouvrir les paramètres, puis la rubrique d'apparence **par sa clé
     technique** (l'identifiant de la rubrique étant généré).
  2. Relever la liste des thèmes : identifiant technique, libellé rendu, état
     de sélection.
  3. Comparer le thème marqué sélectionné avec celui que rend le conteneur
     ushell.
  4. Vérifier la présence d'au moins un libellé **partagé par deux thèmes
     distincts**.
  5. Refermer par annuler.
- **Résultat attendu** : la liste n'est pas vide ; **exactement un** thème est
  sélectionné et son identifiant technique **égale** celui rendu par le
  conteneur ushell ; au moins un libellé est porté par deux identifiants
  différents, ce qui est journalisé comme la preuve qu'un localisateur par nom
  visible est ambigu ici. Aucun thème n'est cliqué.
- **Pourquoi cette forme** : c'est le seul point de la campagne où le plan peut
  démontrer, chiffres à l'appui, pourquoi l'ancre doit être l'identifiant et non
  le libellé.
- **Keywords métier manquants** :
  - `Ouvrir La Rubrique De Parametres` (par clé technique),
  - `Lire Les Themes Offerts` (liste de dicts `{identifiant, libelle, selectionne}`),
  - `Lire Le Theme Du Compte`.

### 7. La rubrique de langue explique la langue réellement servie
- **Étapes** :
  1. Ouvrir les paramètres, puis la rubrique de langue et région.
  2. Relever la clé sélectionnée et les clés offertes par le sélecteur.
  3. Relever le fuseau horaire.
  4. Relever la langue du document et celle du navigateur.
  5. Refermer par annuler.
- **Résultat attendu** : le sélecteur offre au moins une clé et sa clé
  sélectionnée fait partie des clés offertes ; le fuseau est un identifiant
  IANA (contrôle de forme par **découpage sur la barre oblique**, jamais par une
  expression régulière à contre-oblique, leçon verrouillée par
  `tests/unit/test_se16_exploration_logic.py`) ; la langue du document est
  **cohérente** avec la clé sélectionnée, c'est-à-dire soit la clé elle-même,
  soit, quand la clé vaut « langue du navigateur », une langue **offerte par le
  site**. Sur la cible : clé `default`, navigateur `fr`, document `en`, et `fr`
  n'est pas offert.
- **Ce que le scénario protège** : c'est la démonstration, dans le test
  lui-même, que les libellés du shell ne sont pas ceux de la locale du poste, ce
  qui justifie la convention 3 pour tout le reste de la campagne.
- **Keywords métier manquants** :
  - `Lire Le Reglage De Langue` (clé sélectionnée plus clés offertes),
  - `Lire Le Fuseau Horaire Du Compte`,
  - `Lire La Langue Servie Par Le Document`.

### 8. Le Theme Manager est une surface d'administration, ouverte et refermée sans rien changer
- **Étapes** :
  1. Relever le thème du compte.
  2. Résoudre l'élément de barre shell par **type et icône**, constater qu'il y
     en a exactement un, et l'ouvrir.
  3. Constater qu'un dialogue est ouvert, et relever **les actions qu'il
     propose**.
  4. Refermer par l'action d'annulation.
  5. Constater que le thème du compte est inchangé et qu'aucun popup n'est
     ouvert.
- **Résultat attendu** : exactement un élément de barre shell correspond au
  couple type plus icône ; le dialogue ouvert propose des actions d'écriture
  identifiées nommément, dont au moins une action d'enregistrement et une
  action de bascule de la sélection utilisateur ; après annulation, le thème est
  celui de l'étape 1.
- **Portée, et c'est le point du scénario** : ce dialogue configure les thèmes
  offerts à **tous** les utilisateurs du site. La campagne le **constate** comme
  surface d'administration et n'actionne **aucune** de ses actions. C'est
  précisément parce qu'il est atteignable depuis la barre shell d'un
  utilisateur qu'il mérite d'être nommé dans un plan.
- **Keywords métier manquants** :
  - `Ouvrir Le Theme Manager`, `Le Theme Manager Est Ouvert`,
  - `Lire Les Actions Du Theme Manager`, `Annuler Le Theme Manager`.

### 9. Le parcours rend le compte à son état initial
- **Étapes** : dernier test de la suite. Relever thème, langue et popups
  ouverts, et comparer aux valeurs relevées par le Suite Setup.
- **Résultat attendu** : thème et langue **identiques** à ceux du démarrage,
  aucun popup ouvert, aucune iframe applicative résiduelle. C'est la propriété
  qui autorise à rejouer la campagne sur un site partagé.
- **Filet de sécurité** : le teardown de suite ferme tout popup encore ouvert
  et journalise le diagnostic Fiori en cas d'échec, **avant** de nettoyer.
- **Keywords métier manquants** :
  - `Memoriser L Etat Initial Du Compte` (Suite Setup),
  - `L Etat Du Compte Est Inchange`,
  - `Fermer Tout Popup Restant` (teardown).

## Écarts constatés à la génération

Relevés le 2026-08-26 par sap-generator, chaque étape rejouée live via rf-mcp
avant écriture de la suite. Aucun ne change le sens métier d'un scénario.

1. **Sur une session neuve, le menu utilisateur n'existe pas avant le premier
   clic.** Le plan dit que les 5 entrées restent rendues menu fermé : c'est
   vrai après une première ouverture, mais sur un navigateur fraîchement
   connecté, ni le menu ni ses entrées n'existent au registre (comptage 0,
   propriété `open` illisible faute de contrôle) tant que l'avatar n'a jamais
   été cliqué. Le scénario 2 de la suite mesure donc l'égalité des comptages
   entre « menu ouvert » et « menu refermé » (5 et 5 constatés), et journalise
   le comptage d'avant première ouverture sans l'asserter.
2. **Le dialogue des paramètres annulé finit par disparaître du registre.** Le
   plan relève « après annulation, le dialogue reste RENDU (1 `sap.m.Dialog`)
   alors qu'il n'est plus ouvert ». Observé à la génération : 1 dialogue rendu
   juste après l'annulation, 0 une fois la page au repos. La fenêtre de mesure
   décide du chiffre, ce qui confirme la recommandation du plan (seuls les
   popups OUVERTS font foi) : la suite journalise le comptage de dialogues
   rendus sans jamais l'asserter.
3. **Les fermetures de dialogues sont animées.** Juste après le clic de
   fermeture (« à propos », Theme Manager), la liste des popups ouverts
   contient encore le dialogue pendant l'animation, puis se vide. Les mots-clés
   de fermeture du page object attendent la disparition au lieu de lire
   immédiatement.
4. **Les pages de détail du dialogue « à propos » portent des ids stables, et
   la première s'appelle `DetailApplication`.** Le plan adresse les rubriques
   par position (leurs items sont générés : `__item12`, `__item6`, `__item20`
   sur trois runs). La génération a relevé en complément les ids stables des
   pages de détail (`aboutDialogFragment--aboutDialogDetailApplication`,
   `--aboutDialogDetailSystem`, `--aboutDialogDetailEnvironment`), et la
   lecture d'une rubrique se fait par containment sur SA page : lire le
   dialogue entier mélange les pages déjà visitées, restées rendues après
   navigation.
5. **La liste des thèmes rend 10 items, dont 2 entêtes de groupe.** Le tableau
   du plan liste les 8 thèmes identifiés ; la liste rendue contient en plus
   deux entêtes de groupe sans contexte de liaison (identifiant et libellé
   vides). Le mot-clé de lecture écarte les items sans identifiant, ce qui
   rend exactement les 8 thèmes du plan.
6. **Les cinq défauts de bibliothèque du plan sont résorbés.** Les capacités
   livrées le 2026-08-26 ont été re-vérifiées sur la cible pendant la
   génération : le comptage des hôtes Web Components existe en surface (6) et
   en profondeur (16) dans la composition perçue ; `tag=ShellBarItem` matche
   la forme mixte `ui5-shellbar-item` (1 correspondance) ; `Get Ui5 Open
   Popups` voit le menu utilisateur ouvert comme popover Web Components
   (`technology=wc`) ; et `Ui5 Control Should Be Visible` échoue désormais sur
   le champ de recherche replié (rectangle nul) en nommant l'id, contre-épreuve
   rejouée. La suite emploie ces capacités au lieu des contournements décrits
   par le plan.

## Écarts face aux launchpads ABAP

Comparaison point par point avec les deux campagnes ABAP du dépôt. « Identique »
signifie mesuré identique, pas supposé.

### 1. L'ancre de la zone utilisateur : le nom converge, le type diverge

| Cible | Identifiant | Type |
|---|---|---|
| FLP ABAP 1.71 | `meAreaHeaderButton` | `sap.ushell.ui.shell.ShellHeadItem` |
| FLP ABAP 1.120 | `userActionsMenuHeaderButton` | `sap.m.Avatar` |
| **cFLP Work Zone 1.151** | **`userActionsMenuHeaderButton`** | **`…webcomponents.dist.Avatar` (Web Component)** |

Le renommage opéré entre 1.71 et 1.120 est donc **définitif** : le cFLP porte le
même identifiant. Mais le **type** change une troisième fois, et cette fois il
change de technologie. Un page object partagé doit recevoir le type en variable,
exactement comme le fait déjà `abap_flp.resource`.

Même conclusion pour le popover : `sapUshellMeAreaPopover` en 1.71,
`sapUshellUserActionsMenuPopover` en 1.120 **et** ici, mais de type `sap.m.Popover`
là-bas et `ui5-user-menu` ici.

### 2. Les entrées de la zone utilisateur : la mécanique tient, le contenu non

- **Mécanique identique** : identifiant de la forme
  `<préfixe>-<index>-<action>`, index variable selon l'endroit, suffixe d'action
  stable, et écart accueil moins application **exactement égal à l'entrée
  d'édition de l'accueil**. C'est la troisième cible où cette règle tient.
- **Différence de préfixe** : les FLP ABAP portent un préfixe **généré**
  (`__list0-`), le cFLP porte l'**identifiant stable du popover**.
- **Volumétrie** : 7 puis 6 sur les deux cibles ABAP, **5 puis 4** ici.
- **Entrées absentes ici** : `-recentActivitiesBtn` et `-frequentActivitiesBtn`
  (le panneau des activités récentes n'existe pas sur ce cFLP), et
  `-logoutBtn`.
- **Entrée propre au cFLP** : `-manageSiteBtn`, l'administration du site.
- **La déconnexion change de nature** : entrée de liste sur les FLP ABAP, bouton
  sans identifiant dans le pied du menu ici. Un page object partagé ne peut pas
  la traiter comme une entrée.

### 3. Le dialogue des paramètres : convergence complète avec la 1.120

Même préfixe de vue `settingsView--`, mêmes identifiants
`userSettingsDialog`, `userSettingEntryList`, `userSettingSaveButton`,
`userSettingCancelButton`, même **zéro** bouton dans l'agrégation d'actions, et
même mécanique de clé technique **sortie de l'identifiant** vers le contexte de
liaison. Trois clés sur cinq sont identiques (`userAccountEntry`, `themes`,
`homepageEntry`, plus `language`), `userActivitiesEntry` n'existe pas ici, et
une cinquième rubrique est apportée par une extension avec une clé **générée
horodatée**.

### 4. Le dialogue « à propos » : identifiant identique, contenu adapté

`aboutDialogFragment--aboutDialog` sur les deux, un seul bouton, mêmes trois
rubriques. Deux différences : le bouton de fermeture porte ici un **identifiant
stable**, donc l'acquittement par position n'est pas nécessaire ; et la rubrique
« System » est **vide**, faute de système ABAP. Le composant applicatif
(`CA-FLP-FE-COR`) et l'identifiant SAPUI5 (`sap.ushell.components.homepage`) sont
en revanche **identiques** à la 1.120, ce qui montre que le cFLP sert le même
composant d'accueil.

### 5. L'acquittement d'un refus de navigation : le piège se reproduit

Deux boutons, `[0] Copy` puis `[1] Close`, ce dernier en `Emphasized` :
**exactement** la structure de la 1.120, donc acquitter en position 0 copierait
le message et laisserait le dialogue ouvert. L'ancre locale-indépendante retenue
est le **type** `Emphasized`, pas la position. Différence mineure mais utile : le
cFLP **réutilise** le même dialogue généré d'un refus à l'autre, là où la 1.120
en créait un par refus.

### 6. Ce que le cFLP n'a pas

Aucun panneau d'activités récentes, aucune notification (ni dans la barre, ni
dans les services déclarés), aucun bouton d'accueil, aucun bouton de
débordement rendu à cette largeur de fenêtre. La barre shell du cFLP est
nettement plus pauvre que celle d'un FLP ABAP, et c'est un fait de plateforme,
pas un défaut.

## Défauts et lacunes de bibliothèque relevés (convention 12)

Constats reproductibles, mesurés le 2026-08-26. Aucun n'a été contourné en
silence : les scénarios ci-dessus disent explicitement par quoi ils passent.

1. **Le moteur `wc` ne traverse pas les shadow roots.** Mesuré : 6 hôtes
   `ui5-*` dans le light DOM, **16** en comptant les shadow roots, dont
   **3 `ui5-button`**. `Get Wc Match Count tag=Button` retourne **0**. Le bouton
   de recherche de la barre shell, qui vit dans le shadow root du `ui5-shellbar`,
   est donc invisible aux moteurs de la bibliothèque. Contournement employé
   dans les scénarios : un sélecteur CSS de la bibliothèque Browser, qui perce
   les shadow roots ouverts.
2. **Le moteur `dom` ne perce pas non plus.** Le **même** sélecteur CSS
   retourne **1** via `Get Element Count` de Browser et **0** via
   `Get Dom Match Count`. C'est la même cause que le point 1, sur un autre
   moteur, et c'est la preuve la plus courte à rejouer.
3. **La forme courte des tags Web Components échoue sur la famille
   `ui5-shellbar-*`.** Mesuré : `tag=ShellBarItem` retourne **0**,
   `tag=ShellBarBranding` retourne **0**, alors que `tag=ui5-shellbar-item`
   retourne **1**. La conversion essaie la forme collée (`ui5-shellbaritem`) et
   la forme à tirets (`ui5-shell-bar-item`), mais pas la forme réelle
   (`ui5-shellbar-item`), qui mélange les deux. Le cas voisin
   `tag=UserMenuItem` fonctionne, parce que la forme à tirets y est la bonne.
4. **`Get Ui5 Open Popups` ignore les popups en Web Components.** Menu
   utilisateur **ouvert** (propriété `open` à vrai, popover visible), le mot-clé
   retourne `[]`. Il voit correctement les `sap.m.Dialog` (le dialogue « à
   propos » et le refus de navigation sont bien rendus). Conséquence pour les
   scénarios : l'ouverture du menu utilisateur se constate sur sa propriété, et
   `Aucun Popup N Est Ouvert` ne peut pas servir de garde pour ce menu.
5. **`Ui5 Control Should Be Visible` passe sur un contrôle de rectangle nul.**
   Mesuré sur le champ de recherche replié : rectangle 0 x 0, `offsetParent`
   nul, et pourtant le mot-clé **passe**, alors que sa documentation annonce
   « rendu, rectangle non nul » et que `Get Element States` de Browser rapporte
   bien `hidden`. Contre-épreuve faite : le mot-clé échoue correctement sur un
   contrôle inexistant. Détail utile pour la correction : la propriété UI5
   `visible` vaut `True` sur ce contrôle, l'invisibilité venant d'un ancêtre.

## Points de vigilance

- **Le nombre de contrôles rendus n'est pas une constante de la cible.** Mesuré
  le même jour, même compte : **139** sur un accueil chargé à neuf, **44** sur
  un accueil reconstruit après un accès direct à une application, **19** sur un
  accès direct à l'application. Tout plancher gravé serait rouge sur un chemin
  parfaitement sain. Le plancher est une **attente**, jamais une assertion.
- **Rendu ne veut pas dire ouvert**, et c'est vrai deux fois ici : les entrées
  du menu utilisateur restent rendues menu fermé, et le dialogue des paramètres
  reste rendu après annulation.
- **L'index d'une entrée de menu n'est pas une ancre**, le suffixe d'action l'est.
- **Aucun identifiant généré dans un test** : `__item4` (Theme Manager),
  `__branding0`, `__item5-…` (rubriques de paramètres), `__item12` à `__item14`
  (rubriques du dialogue « à propos »), `__dialog0` (refus de navigation). Les
  ancres tenables sont, dans l'ordre de préférence : l'identifiant stable, le
  suffixe d'identifiant, le couple type plus propriété, la clé du contexte de
  liaison, et en dernier recours la position dans une agrégation dont la
  structure a été **vérifiée** au préalable.
- **Le suffixe de scoping des Web Components est une empreinte de build** : il
  n'entre dans aucun localisateur, la forme courte du type suffit quand elle
  fonctionne (voir le défaut 3 ci-dessus).
- **Le compte est administrateur du site** sur cette cible (l'entrée
  d'administration est offerte). Un compte sans ce droit rendrait 4 entrées à
  l'accueil au lieu de 5 : le scénario 3 compare donc deux relevés du même run
  plutôt qu'un cardinal absolu.
- **Deux boutons ne sont jamais actionnés** : l'enregistrement des paramètres,
  et la réinitialisation de toutes les personnalisations. Le second est
  destructeur et vit dans la première rubrique du dialogue, à un clic de
  distance.
- **La page est ouverte au niveau SUITE** : l'auto-fermeture de la bibliothèque
  Browser est au niveau TEST.
- **Un test d'échec d'authentification ne se fait pas sur ce compte** : un IAS
  verrouille après quelques tentatives, et c'est le seul compte des campagnes
  Work Zone.
