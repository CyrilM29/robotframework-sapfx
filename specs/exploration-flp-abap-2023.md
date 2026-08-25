# Launchpad Fiori (FLP) du système ABAP Platform 2023 : perception et parcours de shell

- **Canal** : Fiori (web), runtime SAPUI5 classique servi par un serveur ABAP
  (pas un cFLP SAP BTP, pas de Web Components, pas d'iframe applicative).
- **Système / URL** : `https://localhost:50101/sap/bc/ui2/flp?sap-client=001`
  (ABAP Platform 2023 en conteneur Docker, conteneur dit « abap2023 »).
- **Exploration live** : 2026-08-24, rf-mcp (Browser + SapFioriLibrary),
  utilisateur `DEVELOPER`, mandant `001`, langue servie `EN`, thème `sap_horizon`.
- **Pendant de** : `specs/exploration-flp-abap-a4h.md` (ABAP Platform 1909,
  SAPUI5 1.71.47). Les deux campagnes partagent le page object
  `resources/page_objects/abap_flp.resource` ; la raison d'être de celle-ci est
  de mesurer ce qui, dans le plan 1.71, tenait à la RELEASE et non au produit.
  La section « Écarts constatés face au FLP 1.71 » est le cœur du document.
- **Préconditions** :
  - le conteneur répond en **HTTPS sur le port 50101** (voir « Pièges » : la voie
    HTTP mène à l'AUTRE conteneur du poste, pas à celui-ci) ;
  - certificat auto-signé, donc contexte navigateur ouvert avec
    `ignoreHTTPSErrors=True` (orthographe exacte, voir « Pièges ») ;
  - identifiants passés en ligne de commande (`-v ABAP_FLP_USER:…`,
    `-v "ABAP_FLP_PASSWORD: Secret:…"`), jamais committés (convention 11) ;
  - aucune donnée de démonstration à provisionner : le contenu vient des rôles
    livrés avec l'image.
- **Portée** : **lecture seule par défaut**, aucun scénario n'écrit de donnée
  métier. Un seul scénario écrit, et il écrit une personnalisation d'accueil
  RÉVERSIBLE (scénario 22, épingler puis dépingler), derrière un accord explicite
  à deux tours : sans lui il est sauté. L'autre écriture possible relevée à
  l'exploration (approuver une commande d'achat) est **refusée**, voir la section
  des décisions.

## Données observées

Tout ce qui suit a été relevé live le 2026-08-24. Rien n'est déduit, et ce qui
n'a pas été observé est nommé comme tel en fin de document.

### Identité de la cible

| Fait | Valeur observée |
|---|---|
| URL demandée = URL atteinte | oui, **aucune redirection** (`https://localhost:50101/…`) |
| Runtime UI5 (`sap.ui.version`) | `1.120.15` |
| SAPUI5 annoncé par le dialogue « À propos » | `1.120.14 (202405081437)` |
| Application / composant | ID `LAUNCHPAD`, composant `CA-FLP-FE-COR`, composant technique `sap.ushell.components.homepage` |
| Product Version (dialogue « À propos ») | SAP LTRS FOR SAP S/4HANA 1.0, SAP S/4HANA FOUNDATION 2023, SAP FIORI FES 2023 FOR S/4HANA, **ABAP PLATFORM 2023** |
| Utilisateur / nom affiché | `DEVELOPER` / « John Doe » (tooltip de l'avatar) |
| Langue servie / thème | `EN` / **`sap_horizon`** |
| Langues proposées à la connexion | 2 valeurs non vides : `DE`, `EN` |
| Contrôles UI5 sur l'accueil | **134** au premier chargement propre, **169** en fin de parcours |
| Web Components (`wc_hosts`) | 0 |
| iframes | **0, y compris application ouverte** |
| Moteurs de résolution recommandés | `role`, `xpath`, `dom` |

Les deux numéros de version cohabitent légitimement, comme sur la cible 1.71 :
`sap.ui.version` donne le runtime chargé, le dialogue donne la version de
distribution et son horodatage de build (`~20240508143700~` dans les URL de
ressources). La ligne majeure/mineure, elle, coïncide, et c'est la seule
assertion tenable.

### Architecture : un seul document, un seul registre

Fait structurant, **identique à la cible 1.71** et opposé au launchpad SAP Build
Work Zone (`specs/workzone-launchpad-btp-perception.md`) :

- l'application ouverte **n'est PAS dans une iframe** : `Get Page Composition`
  rapporte `frames: []` application chargée, et `Get Ui5 App Frame` échoue en
  nommant l'absence d'iframe ;
- ni pile de frames, ni portée à empiler, ni étanchéité de portée : shell et
  application partagent le même registre UI5 ;
- le nombre de contrôles est le témoin du chargement : 134 (accueil), 638
  (Manage Products), 1232 (Shop), 2258 (Git-Enabled CTS) ;
- le témoin de « quelle application est ouverte » reste le conteneur dont l'id
  est DÉRIVÉ de l'intent : `application-<SemanticObject>-<action>`
  (`ApplicationContainer`) et `application-<SemanticObject>-<action>-content`
  (`ComponentContainer`). Vérifié live : 1 quand l'application est ouverte, 0 sur
  l'accueil.

### Services ushell disponibles

Sondés un à un sur le conteneur ushell (ce sondage POLLUE la console, voir
« Pièges ») :

| Présents | Absents et pourquoi |
|---|---|
| `SearchableContent`, `LaunchPage`, `CrossApplicationNavigation`, `Navigation`, `NavTargetResolution`, `UserInfo`, `ShellNavigation`, `URLParsing`, `Menu`, `VisualizationDataProvider`, `Search`, `Bookmark`, `Personalization`, `Pages`, `SpaceContent`, `UserDefaultParameters`, `AppLifeCycle`, `SupportTicket`, `UserRecents` | `AppConfiguration` (adaptateur ABAP `AppConfigurationAdapter.js` introuvable), `CommonDataModel` (`t.getSite is not a function`), `Spaces` (module absent des ressources servies), `Ushell` (module absent) |

### Catalogue réel de l'utilisateur, lu par DEUX services

| Fait | `LaunchPage` | `SearchableContent` |
|---|---|---|
| Catalogues assignés | 2 | (ne raisonne pas par catalogue) |
| `X-SAP-UI2-CATALOGPAGE:SAP_BASIS_TCR_T` | 64 tuiles | |
| `X-SAP-UI2-CATALOGPAGE:SAP_EPM_BC_PURCHASER_T` | 3 tuiles | |
| Éléments retournés | **67** tuiles | **66** applications |
| Intents uniques | **62** | **62** |
| Écart entre les deux ensembles d'intents | **aucun dans les deux sens** | |

Objets sémantiques distincts : 46. Intents résolvables
(`CrossApplicationNavigation.isIntentSupported`) : **61 sur 62**, le seul écart
étant `ApplicationJob-show`. L'intent fabriqué `Foo-bar` est bien déclaré non
résolvable (contre-preuve).

Chaque application rendue par `SearchableContent` porte
`_instantiationData.platform = "LAUNCHPAD"` : sur ce FLP ABAP, le service neuf
est une façade au-dessus de l'ancien, ce qui explique l'égalité stricte des
intents.

### Groupes et tuiles de l'accueil

| Groupe (id technique) | Tuiles |
|---|---|
| `/UI2/Fiori2LaunchpadHome` | **1** |
| `SAP_EPM_BCG_PURCHASER_T` | **0** |

L'accueil ne rend donc **qu'une seule tuile**, et c'est celle dont le
fournisseur de données ne répond pas :

| Titre (propriété `header`) | Sous-titre | Intent | Compteur | Pied de tuile |
|---|---|---|---|---|
| Git-enabled CTS | Manage Repositories | `Repository-manage` | `...` | (vide) |

Tuile **dynamique** (`applauncherdynamic`), état `Loaded`, compteur jamais
résolu. La configuration du composant nomme sa source :
`service_url = /sap/bc/cts_abapvcs`, `navigation_semantic_object = Repository`,
`navigation_semantic_action = manage`.

Les trois applications de démonstration EPM (`EPMProduct-shop`,
`EPMProduct-manage_st`, `EPMPurchaseOrder-approve`) sont **au catalogue et
résolvables**, mais **pas sur l'accueil** : le groupe qui les porterait est vide.

### Barre shell et zone utilisateur

| Rôle | Id | Type | Rendu à l'accueil | Rendu dans une application |
|---|---|---|---|---|
| Zone utilisateur | `userActionsMenuHeaderButton` | **`sap.m.Avatar`** | oui | oui |
| Recherche | `sf` | `ShellHeadItem` | oui | oui |
| Titre / menu « All My Apps » | `shellAppTitle` | `ShellAppTitle` | oui | oui |
| Retour | `backBtn` | `ShellHeadItem` | non | **oui** |
| Débordement | `endItemsOverflowBtn` | `ShellHeadItem` | non | non |
| Accueil | `homeBtn` | (aucun) | **le contrôle n'existe pas** | **le contrôle n'existe pas** |

Nombre de `ShellHeadItem` **rendus** : **1 à l'accueil** (la recherche seule),
**2 dans une application** (recherche et retour). L'avatar de la zone
utilisateur n'en est plus un.

Popover de la zone utilisateur : `sapUshellUserActionsMenuPopover`. Ses entrées
sont des `sap.m.StandardListItem` dont l'id vaut `__list0-<index>-<action>` : le
préfixe et l'INDEX bougent, seul le suffixe d'action est stable.

| Entrée | Suffixe d'id stable | Position à l'accueil | Présente dans une application |
|---|---|---|---|
| Recent Activities | `-recentActivitiesBtn` | 0 | oui |
| Frequently Used | `-frequentActivitiesBtn` | 1 | oui |
| App Finder | `-openCatalogBtn` | 2 | oui |
| Settings | `-userSettingsBtn` | 3 | oui |
| **Edit Home Page** | `-ActionModeBtn` | 4 | **non** |
| About | `-aboutBtn` | 5 | oui |
| Sign Out | `-logoutBtn` | 6 | oui |

Soit **7 entrées à l'accueil, 6 dans une application**, l'écart se réduisant
exactement à l'entrée d'édition. Aucune entrée de retour utilisateur
(« Give Feedback ») n'existe sur cette cible, ni rendue ni déclarée.

Piège de portée : les prototypes `sap.ushell.ui.launchpad.ActionItem` portent
l'id NU (`ActionModeBtn`, `openCatalogBtn`, `userSettingsBtn`, `logoutBtn`,
`recentActivitiesBtn`, `frequentActivitiesBtn`) et ne sont jamais rendus. Ancrer
sur le suffixe AVEC son tiret (`-aboutBtn`) évite de les toucher.

Panneau « activités » (jamais ouvert sur la cible 1.71) : l'entrée
« Recent Activities » déplie un panneau DANS le popover, sans changer l'URL
(`#Shell-home`). Ids stables : liste
`sapUshellActivityListrecentActivities`, onglets `recentActivityFilter` et
`frequentlyUsedFilter`. 5 entrées observées, correspondant aux applications
visitées, y compris depuis une session antérieure.

### Dialogues du shell

| Dialogue | Id | Nature | Boutons |
|---|---|---|---|
| À propos | `aboutDialogFragment--aboutDialog` | id stable | 1 (position 0 = acquittement) |
| Paramètres | `settingsView--userSettingsDialog` | id stable | **0 dans l'agrégation `buttons`** |
| Refus de navigation | `__dialog0`, `__dialog1`, `__dialog2` (générés, un par refus) | `state = Error` | 2 : **[0] Copy, [1] Close (Emphasized)** |
| Confirmation de déconnexion | `__confirm0` (généré) | `state = None` | 2 : **[0] OK, [1] Cancel** |

Le dialogue des paramètres porte ses actions dans un `OverflowToolbar` de pied
de page, d'où le zéro : `settingsView--userSettingSaveButton` et
`settingsView--userSettingCancelButton` sont bien là, avec leurs suffixes
stables.

Rubriques rendues de la liste maître `settingsView--userSettingEntryList` : **5**
(`User Account`, `Appearance`, `Home Page`, `User Activities`,
`Language and Region`). Leurs ids sont **entièrement générés**
(`__item3-settingsView--userSettingEntryList-<index>`) : la clé technique n'est
plus dans l'id, elle vit dans le contexte de liaison, propriété `id` :
`userAccountEntry`, `themes`, `homepageEntry`, `userActivitiesEntry`, `language`.

### App Finder

Fragment `Shell-appfinder`. Ids stables, **sans préfixe de vue** :
`appFinderSearch` (`sap.m.SearchField`), `catalogSelect` (`sap.m.List`),
`appFinderPage` (`sap.m.Page`), `catalogTiles`
(`sap.ushell.ui.launchpad.CatalogsContainer`), `catalogTilesDetailedPage`
(`sap.m.Page`). `appFinderView` n'existe plus.

Mesuré : **54** vignettes `AppBox` rendues pour 67 tuiles déclarées au catalogue
(rendu paresseux), 54 boutons d'épinglage `PinButton`, **3** sources de
catalogue (2 catalogues assignés plus l'entrée « toutes »), et **1** vignette
après filtrage sur « Shop ».

### Menu « toutes mes applications »

Popover `sapUshellAllMyAppsPopover-popover`, liste des sources
`allMyAppsView--sapUshellAllMyAppsDataSourcesList` (3 entrées), **60** entrées
d'application rendues pour 67 tuiles déclarées : le menu rend la source
sélectionnée, pas la totalité du catalogue.

### Recherche du shell

Le bouton `sf` déplie `searchFieldInShell-input`. Un terme PARTIEL (« Manage »)
atteint `Action-search` avec le filtre décodé :

```
Action-search&/top=20&filter={"dataSource":{"type":"Category","id":"$$APPS$$",
"label":"Apps","labelPlural":"Apps"},"searchTerm":"Manage", ...}
```

16 tuiles de résultats rendues, contre 1 sur l'accueil. La source `$$APPS$$` est
un identifiant technique ; son libellé « Apps » ne l'est pas.

### Console au chargement propre de l'accueil

**4 erreurs console, 0 exception JS non rattrapée** (`page_errors: []`), toutes
tracées et reproductibles. Trois arrivent au rendu du shell, la quatrième une
vingtaine de secondes plus tard :

1. `[FUTURE FATAL] The registered Event Listener 'init' must not have a return
   value. - __renderer0---Shell-home-component`, émise par le **renderer du shell
   de SAP lui-même** ;
2. `Defining the object type ('sap.m.PageAccessibleLandmarkInfo') via its string
   name is deprecated …`, dépréciation, même origine ;
3. `Failed to load resource: 404` sur `/sap/es/ina/GetServerInfo` : la recherche
   d'entreprise (InA) n'est pas déployée ;
4. `sessionTimeoutReminderInMinutes needs to be higher than
   sessionTimeoutIntervalInMinutes. sessionTimeoutReminderInMinutes adapted to:
   4 - SessionHandler`, message de configuration du shell, journalisé au niveau
   erreur.

Fait à ne pas mal lire : la tuile dont le compteur reste `...` **n'émet AUCUNE
erreur console** sur cette cible. Le fournisseur de données échoue en silence.

### Page de connexion et branche négative

Page de logon ICF, **pas de runtime UI5** (`ui5_controls: 0`, moteur `dom`
seul, titre `Logon`). Formulaire `LOGIN_FORM` en POST sur `/sap/bc/ui2/flp`,
champs cachés dont `sap-login-XSRF`, `sap-client`, `sap-hash`. Ids :
`USERNAME_FIELD-inner`, `PASSWORD_FIELD-inner`, `LANGUAGE_SELECT`, `LOGIN_LINK`,
`CHANGE_PASSWORD_LINK`, `LOGIN_ERROR_BLOCK`.

Mot de passe erroné (**une seule tentative dans toute la campagne**) : la page
de connexion reste en place, l'URL **perd son paramètre `?sap-client=001`**
(POST), et un message `LOGIN_MESSAGE_0` apparaît avec la classe
**`loginMessage sapUiError`**. La classe est l'ancre locale-indépendante ; le
texte (« Client, name, or password is not correct; log on again ») ne l'est pas.

### Après déconnexion

URL `https://localhost:50101/sap/public/bc/icf/logoff?sap-client=001`, titre
`Logoff`, **aucun runtime UI5**.

## Scénarios

### 1. La page de connexion est bien celle du serveur ABAP 2023 visé

- **Préconditions** : navigateur ouvert, contexte tolérant le certificat
  auto-signé, aucune session en cours.
- **Étapes** :
  1. Ouvrir l'URL du launchpad en HTTPS.
  2. Relever l'URL réellement atteinte, AVANT toute frappe.
  3. Constater qu'aucun runtime UI5 n'est présent.
  4. Percevoir la composition de la page.
  5. Relever les champs du formulaire et les langues proposées.
- **Résultat attendu** : l'hôte atteint est exactement l'hôte demandé (aucune
  redirection) ; le runtime UI5 est **absent** ; la composition annonce
  `ui5_controls = 0` et le seul moteur `dom` ; le formulaire porte un champ
  utilisateur, un champ mot de passe, un sélecteur de langue et un bouton de
  connexion ; le sélecteur propose exactement **2** langues non vides.
- **Pourquoi ce scénario existe** : sans le contrôle d'URL de l'étape 2, la page
  de connexion de l'AUTRE conteneur ABAP du poste rendrait ce test parfaitement
  vert. Voir « Pièges ».
- **Keywords métier manquants** : aucun, `Ouvrir Le Launchpad ABAP`,
  `La Page De Connexion Est Rendue` et `Lire Les Langues De Connexion` du page
  object partagé conviennent tels quels (vérifié live).

### 2. Une authentification refusée le dit, et ne laisse pas entrer

- **Préconditions** : scénario 1 atteint.
- **Étapes** :
  1. Saisir un utilisateur valide et un mot de passe volontairement faux.
  2. Valider la connexion.
  3. Constater l'état de la page.
- **Résultat attendu** : la page de connexion est **toujours** là ; un message
  portant la classe d'erreur du logon ICF est rendu ; aucun runtime UI5 n'est
  chargé.
- **À exécuter AVANT le scénario 3**, et **une seule fois** : au-delà, on
  s'approche du verrouillage du compte, dont le seuil est un réglage serveur non
  observé ici. Une connexion réussie remet le compteur à zéro.
- **Keywords métier manquants** : aucun (`Tenter Une Connexion`,
  `La Connexion Est Refusee`, vérifiés live).

### 3. La connexion nominale rend un shell FLP 1.120 identifiable

- **Préconditions** : page de connexion affichée.
- **Étapes** :
  1. Se connecter avec les identifiants fournis.
  2. Attendre que le conteneur ushell existe, que la page revienne au repos, puis
     que le shell ait construit des contrôles.
  3. Percevoir la composition de la page.
  4. Lire l'utilisateur, sa langue et son thème au conteneur ushell.
- **Résultat attendu** : le runtime UI5 est présent et sa version commence par
  la ligne attendue de la cible (mesuré `1.120.15`) ; la composition annonce
  **zéro** hôte Web Component, **zéro** iframe, et les moteurs
  `role`/`xpath`/`dom` ; le nombre de contrôles rendus dépasse le plancher de la
  cible (mesuré entre 134 et 169, donc plancher à 100) ; l'utilisateur retourné
  par le conteneur est celui fourni en paramètre ; l'URL porte le fragment de
  l'accueil.
- **Note d'assertion** : ne jamais asserter le titre de page (« Home » est
  traduit) ; le fragment, lui, ne l'est pas. Le thème (`sap_horizon`) est un
  réglage, à journaliser plutôt qu'à figer.
- **Keywords métier manquants** : aucun.

### 4. Le dialogue « à propos » prouve la release du système

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Ouvrir la zone utilisateur, puis l'entrée « à propos ».
  2. Constater l'ouverture du dialogue.
  3. Relever son contenu technique.
  4. Refermer par la position de son bouton.
- **Résultat attendu** : le dialogue est ouvert ; il nomme la version du produit
  ABAP attendue pour la cible (mesuré « ABAP PLATFORM 2023 ») ; la version SAPUI5
  qu'il annonce partage la ligne majeure/mineure du runtime chargé ; après
  fermeture, aucun dialogue n'est ouvert.
- **Valeur pour la campagne** : c'est l'empreinte de cible qui distingue ce
  système de son voisin 1909, et c'est le seul endroit de l'interface qui nomme
  le produit. Le scénario 1 prouve qu'on a parlé au bon HÔTE, celui-ci prouve
  qu'on a parlé à la bonne RELEASE.
- **Keywords métier manquants** : aucun, mais **l'ancre du dialogue et la
  position du bouton d'acquittement doivent être des variables** (voir « Écarts »
  points 4 et 8).

### 5. Le catalogue est inventorié par le service, et les deux services concordent

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Inventorier les catalogues assignés et leurs tuiles par le service
     historique du launchpad.
  2. Inventorier les applications par le service de contenu recherchable, quand
     il est disponible sur la cible.
  3. Dédoublonner les intents des deux côtés et comparer les deux ensembles.
- **Résultat attendu** : au moins un catalogue est retourné ; chaque tuile porte
  un intent de forme `SemanticObject-action` ; le nombre d'intents uniques est
  inférieur ou égal au nombre de tuiles (mesuré 62 pour 67) ; quand les deux
  services répondent, leurs ensembles d'intents sont **identiques dans les deux
  sens** (mesuré : 62 = 62, zéro écart).
- **Décision de conception** : la comparaison des deux voies est **conditionnée
  à la présence** du second service, absent sur la cible 1.71. Sur un système où
  il manque, le scénario se réduit à la première voie et le dit, plutôt que
  d'échouer.
- **Pourquoi lire au service** : l'App Finder ne rend que ce qui est filtré et
  visible (54 vignettes pour 67 tuiles déclarées). Compter à l'écran donnerait un
  nombre faux.
- **Keywords métier manquants** : `Inventorier Les Applications Recherchables`
  (lecture du service de contenu recherchable, liste de dicts `{intent, titre}`),
  `Le Service De Contenu Recherchable Est Disponible` (prédicat de branchement).

### 6. Toute application offerte au catalogue est réellement ouvrable, ou l'écart est nommé

- **Préconditions** : catalogue inventorié.
- **Étapes** :
  1. Soumettre la liste complète des intents du catalogue au service de
     résolution de navigation, **plus un intent fabriqué qui n'existe pas**.
  2. Séparer les intents résolvables des autres.
  3. Rapporter nommément chaque intent assigné mais non résolvable.
- **Résultat attendu** : l'intent fabriqué est déclaré **non** résolvable (sans
  cette contre-preuve, un service qui répondrait « oui » à tout rendrait le test
  vert et vide) ; au moins un intent du catalogue est résolvable ; les écarts
  sont listés. Sur la cible : 61 résolvables sur 62, l'écart étant
  `ApplicationJob-show`, **exactement comme sur la cible 1.71**.
- **Décision de conception** : cet écart est **rapporté**, pas mis en échec.
- **Keywords métier manquants** : aucun.

### 7. L'accueil rend ses groupes et sa tuile, compteur compris

- **Préconditions** : accueil affiché.
- **Étapes** :
  1. Inventorier les groupes de l'accueil et le volume de chacun.
  2. Lire les tuiles RENDUES : titre par propriété, intent, valeur du compteur.
  3. Vérifier que chaque intent de tuile appartient au catalogue.
  4. Séparer les compteurs numériques des compteurs non résolus et rapporter ces
     derniers nommément.
- **Résultat attendu** : au moins un groupe est retourné ; **un groupe peut être
  vide** (mesuré : `SAP_EPM_BCG_PURCHASER_T` déclare 0 tuile) ; chaque tuile
  rendue porte un titre non vide et un intent présent au catalogue ; les
  compteurs non résolus sont rapportés sans mettre la campagne en échec.
- **Piège majeur de cette cible** : l'accueil ne porte **qu'une tuile**, et son
  compteur n'est **jamais** résolu. Toute stratégie du type « prendre la première
  tuile dont le compteur est numérique » ne trouve **rien** ici. L'application
  sous test doit venir du CATALOGUE, par intent.
- **Assertion à ne pas écrire** : le nombre de tuiles de l'accueil, ni le titre
  des groupes (traduit et divergent entre service et écran).
- **Keywords métier manquants** : `Lire Les Tuiles De L Accueil` doit être
  **réécrit** pour cette release (voir « Écarts » point 9) : le titre se lit sur
  le contrôle `GenericTile` contenu dans la tuile, l'intent sur l'ancre HTML de
  la tuile, le compteur sur le `NumericContent` contenu. Nom proposé inchangé,
  implémentation paramétrée par release.

### 8. Ouvrir une application par sa tuile et par son intent mène au même endroit

- **Préconditions** : accueil affiché, au moins une tuile rendue.
- **Étapes** :
  1. Choisir la tuile de l'accueil (découverte, jamais en dur).
  2. Ouvrir l'application par son **intent**, constater.
  3. Revenir à l'accueil, constater que le conteneur a disparu.
  4. Rouvrir la **même** application en cliquant sa tuile, constater.
  5. Comparer les deux constats.
- **Résultat attendu** : dans les deux cas le fragment vaut l'intent, le
  conteneur d'application dérivé de l'intent est présent exactement une fois, et
  le nombre de contrôles rendus dépasse nettement celui de l'accueil (mesuré
  2258 contre 134 pour `Repository-manage`) ; aucune iframe n'apparaît ; les deux
  voies donnent le même fragment.
- **Fait mesuré** : le titre passé au clic vient de la propriété relevée dans le
  MÊME run (« Git-enabled CTS ») ; l'écrire en dur le figerait dans une langue.
- **Keywords métier manquants** : aucun (`Ouvrir L Application Par Intent`,
  `Ouvrir L Application Par Sa Tuile`, `Revenir A L Accueil`,
  `L Application Ouverte Est`, `Aucune Application N Est Ouverte`, tous vérifiés
  live sur cette release).

### 9. La navigation arrière du navigateur ramène à l'application précédente

- **Préconditions** : deux applications ouvrables connues du catalogue.
- **Étapes** :
  1. Ouvrir une première application par intent, la constater.
  2. Ouvrir une seconde application par intent, la constater.
  3. Vérifier que le conteneur de la première a disparu.
  4. Déclencher la navigation arrière du navigateur.
  5. Constater l'écran atteint.
- **Résultat attendu** : après la navigation arrière, le fragment et le conteneur
  sont **ceux de la première application** ; le conteneur de la seconde n'existe
  plus. Un seul conteneur d'application existe à la fois.
- **Piège de temporisation mesuré** : le retour arrière relance le chargement de
  données de l'application reconstruite, et la page a mis **environ 55 secondes**
  à revenir au repos. Le budget d'attente par défaut (15 s) échoue en annonçant
  une requête encore en vol, ce qui se lit à tort comme une anomalie. Ce budget
  doit être une variable de la cible.
- **Keywords métier manquants** : aucun, mais
  `Revenir En Arriere Dans Le Shell` doit accepter un budget d'attente en
  argument.

### 10. La barre shell et la zone utilisateur dépendent de l'endroit

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Sur l'accueil, compter les éléments de barre shell rendus, ouvrir la zone
     utilisateur, relever ses entrées, refermer.
  2. Ouvrir une application, refaire le même relevé.
  3. Comparer les deux relevés.
- **Résultat attendu** : le compte d'éléments de barre shell rendus est celui de
  la cible et il AUGMENTE dans une application (mesuré 1 puis 2, le shell
  ajoutant le bouton de retour) ; les deux relevés d'entrées contiennent les
  entrées permanentes ; le relevé fait sur l'ACCUEIL contient **exactement une
  entrée de plus**, celle d'édition de la page d'accueil.
- **Assertions locale-indépendantes** : le suffixe technique de chaque entrée,
  jamais son libellé ; un ÉCART entre deux relevés, jamais un cardinal absolu.
- **Keywords métier manquants** : aucun pour le relevé
  (`Lire Les Entrees De La Zone Utilisateur` fonctionne tel quel), mais
  **l'ouverture de la zone utilisateur doit viser une ancre variable** (voir
  « Écarts » point 4).

### 11. Le panneau des activités récentes s'ouvre et se referme

- **Préconditions** : shell rendu, au moins une application déjà visitée dans la
  campagne.
- **Étapes** :
  1. Ouvrir la zone utilisateur, puis l'entrée des activités récentes.
  2. Constater que la liste des activités est rendue et que les deux onglets
     (récentes, fréquentes) existent.
  3. Compter les entrées.
  4. Refermer le popover.
- **Résultat attendu** : la liste et ses deux onglets sont rendus, sous leurs
  identifiants stables ; la liste contient au moins une entrée ; l'URL n'a **pas**
  changé (c'est un panneau du popover, pas une navigation) ; après fermeture,
  aucun popover n'est ouvert.
- **Portée** : lecture seule, mais consigner que **la simple navigation écrit
  l'historique utilisateur côté serveur** (voir « Points de vigilance »).
- **Keywords métier manquants** : `Ouvrir Les Activites Recentes`,
  `Compter Les Activites Recentes`.

### 12. Le dialogue des paramètres s'ouvre et se referme sans rien modifier

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Ouvrir la zone utilisateur, puis l'entrée « paramètres ».
  2. Constater l'ouverture du dialogue.
  3. Relever les clés techniques des rubriques rendues.
  4. Refermer par **annuler**, jamais par enregistrer.
- **Résultat attendu** : le dialogue est ouvert ; sa liste maître rend au moins
  une rubrique et les clés relevées sont journalisées (mesuré 5 :
  `userAccountEntry`, `themes`, `homepageEntry`, `userActivitiesEntry`,
  `language`) ; après annulation, aucun dialogue n'est ouvert et aucun réglage
  n'a été écrit.
- **LECTURE SEULE assumée** : le bouton d'enregistrement écrit une
  personnalisation utilisateur côté serveur. Il n'est jamais actionné.
- **Keywords métier manquants** : `Lire Les Rubriques De Parametres` doit être
  **réécrit** pour cette release : la clé technique a quitté l'identifiant et vit
  dans le contexte de liaison (voir « Écarts » point 4).

### 13. L'App Finder ouvre le catalogue et sait le filtrer

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Ouvrir l'App Finder depuis la zone utilisateur.
  2. Constater le fragment atteint et le rendu du champ de recherche.
  3. Relever la liste des sources de catalogue.
  4. Compter les applications rendues.
  5. Saisir un terme de recherche, valider, recompter.
- **Résultat attendu** : le fragment est celui de l'App Finder ; la liste des
  sources contient une entrée par catalogue assigné plus l'entrée « toutes »
  (mesuré 3 pour 2 catalogues) ; le nombre d'applications rendues est strictement
  positif et strictement supérieur au nombre obtenu après filtrage (mesuré 54
  puis 1).
- **À ne pas faire** : compter le catalogue ici. Le rendu est paresseux.
- **Candidat d'écriture DEVENU le scénario 22** : chaque vignette porte un bouton
  d'épinglage (54 relevés) qui ajoute l'application à un groupe de l'accueil. Le
  cycle « épingler puis dépingler » est désormais couvert, sous accord explicite
  d'écriture (révision du 2026-08-24). Ce scénario-ci reste, lui, en lecture
  seule : il filtre, il n'épingle pas.
- **Keywords métier manquants** : aucun (tous vérifiés live sur cette release).

### 14. Le mode édition de l'accueil s'ouvre et se quitte sans rien changer

- **Préconditions** : accueil affiché.
- **Étapes** :
  1. Relever les groupes et le volume de chacun.
  2. Entrer en mode édition depuis la zone utilisateur.
  3. Constater que le mode est actif.
  4. Quitter le mode édition par son bouton de validation.
  5. Relever de nouveau les groupes et leur volume.
- **Résultat attendu** : le mode édition est bien entré puis bien quitté ; les
  groupes et leurs volumes sont **strictement identiques** avant et après.
- **Témoin d'état** : le bouton de fin d'édition. Il est le seul témoin valable
  sur les DEUX releases : la barre de pied de page, elle, est rendue en 1.120 et
  ne l'était pas en 1.71.
- **Keywords métier manquants** : aucun.

### 15. Le menu « toutes mes applications » liste les sources et une partie du catalogue

- **Préconditions** : accueil affiché.
- **Étapes** :
  1. Cliquer le titre de shell.
  2. Constater l'ouverture du popover.
  3. Relever les sources listées et compter les entrées rendues.
  4. Refermer.
- **Résultat attendu** : le popover est ouvert ; il propose une entrée par
  catalogue assigné plus une (mesuré 3) ; le nombre d'entrées rendues est
  strictement positif et inférieur ou égal au volume total du catalogue (mesuré
  60 pour 67).
- **Keywords métier manquants** : aucun.

### 16. La recherche du shell trouve les applications de l'utilisateur

- **Préconditions** : accueil affiché.
- **Étapes** :
  1. Compter les tuiles rendues sur l'accueil.
  2. Ouvrir la recherche depuis la barre shell.
  3. Saisir un terme **partiel** correspondant à des applications du catalogue.
  4. Déclencher la recherche.
  5. Lire le filtre atteint et compter les tuiles rendues.
- **Résultat attendu** : le fragment atteint est celui de la recherche du shell ;
  le filtre décodé nomme la source de données technique des applications et
  porte le terme soumis ; la page de résultats rend strictement plus de tuiles
  que l'accueil (mesuré 16 contre 1).
- **Deux faits à ne pas mal lire** : la recherche d'entreprise n'est PAS déployée
  (404 en console au chargement) et pourtant la recherche du shell fonctionne,
  car elle se rabat sur le catalogue local ; et un terme correspondant au titre
  EXACT d'une application fait naviguer le shell directement vers elle, sans page
  de résultats (relevé sur la cible 1.71, comportement à réserver, non
  re-vérifié ici).
- **Keywords métier manquants** : aucun.

### 17. Un intent inexistant est refusé proprement, sans quitter l'écran courant

- **Préconditions** : une application ouverte.
- **Étapes** :
  1. Relever le fragment courant et l'application ouverte.
  2. Demander la navigation vers un intent **fabriqué**, de forme correcte mais
     inconnu.
  3. Constater l'état du shell.
  4. Acquitter le dialogue.
  5. Relever de nouveau le fragment et l'application ouverte.
- **Résultat attendu** : un dialogue en **état d'erreur** est ouvert ; le
  fragment n'a **pas** changé ; l'application ouverte est toujours là. Après
  acquittement, plus aucun dialogue n'est ouvert et l'état est identique au
  relevé initial.
- **Assertion locale-indépendante** : la propriété d'état du dialogue, jamais son
  titre ni son texte. L'acquittement se fait par **position**, et cette position
  n'est PAS la même que celle de la confirmation de déconnexion (voir « Écarts »
  point 8) : ici l'acquittement est le **dernier** bouton, le premier étant une
  copie du message technique.
- **Keywords métier manquants** : aucun, mais la position d'acquittement d'un
  dialogue d'erreur doit être une variable distincte de celle d'une confirmation.

### 18. Un fragment d'URL malformé est refusé de la même façon

- **Préconditions** : une application ouverte.
- **Étapes** :
  1. Écrire dans l'URL un fragment sans partie action.
  2. Constater l'état du shell.
  3. Acquitter, vérifier le retour à l'état antérieur.
- **Résultat attendu** : dialogue en état d'erreur, même structure que le
  scénario 17 (deux boutons, acquittement en dernière position) ; le fragment
  revient à celui de l'application ouverte ; l'application survit.
- **Fait mesuré** : les dialogues des scénarios 17, 18 et 19 sont
  **structurellement identiques**. Ne pas chercher à les distinguer à l'écran.
- **Keywords métier manquants** : aucun.

### 19. Une application assignée mais non ouvrable produit le même refus

- **Préconditions** : une application ouverte, et un intent du catalogue déclaré
  non résolvable par le scénario 6.
- **Étapes** :
  1. Demander la navigation vers cet intent.
  2. Constater le refus.
  3. Acquitter et vérifier que l'écran courant a survécu.
- **Résultat attendu** : dialogue en état d'erreur, indiscernable de celui d'un
  intent inconnu ; l'écran courant est intact.
- **Ce que ce scénario établit** : c'est la préflight du scénario 6, sans
  navigation, qui distingue « assigné mais non déployé » de « inconnu ». L'écran,
  lui, ne le fait pas.
- **Conditionnement** : le scénario ne s'exécute que si le scénario 6 a trouvé au
  moins un écart. Sur un système sain il est SAUTÉ, pas rouge.
- **Keywords métier manquants** : aucun.

### 20. Aucune exception JavaScript non rattrapée, et les dépréciations du shell sont triées à part

- **Préconditions** : parcours complet joué.
- **Étapes** :
  1. Purger le journal de console, recharger l'accueil, attendre le repos.
  2. Collecter le diagnostic Fiori agrégé.
  3. Séparer les erreurs de page des erreurs console.
  4. Classer les erreurs console par famille et vérifier que le tri est
     **exhaustif**.
- **Résultat attendu** : **zéro** exception JavaScript non rattrapée ; toutes les
  erreurs console tombent dans une famille connue et documentée ; aucune erreur
  inclassée. Sur la cible : 4 erreurs, réparties en trois familles nouvelles par
  rapport à la cible 1.71 (dépréciations du shell SAP, recherche d'entreprise
  absente, configuration de session).
- **Décision de conception** : l'assertion dure porte sur les exceptions non
  rattrapées et sur l'EXHAUSTIVITÉ du tri, jamais sur un comptage brut. On
  classe, on ne compte pas.
- **Piège de mesure encodé** : l'exploration pollue sa propre mesure (chaque
  sonde d'un service ushell absent ajoute son 404, une connexion refusée laisse
  son message). La mesure de référence se prend sur un chargement propre.
- **Keywords métier manquants** : la table des marqueurs de classification doit
  gagner une famille **dépréciations émises par le shell** (marqueurs
  `[FUTURE FATAL]` et `is deprecated`) et une famille **configuration du shell**
  (marqueur `SessionHandler`), toutes deux paramétrables par cible.

### 21. La déconnexion demande confirmation et atterrit sur la page de sortie

- **Préconditions** : session ouverte. **Dernier scénario de la campagne.**
- **Étapes** :
  1. Ouvrir la zone utilisateur.
  2. Déclencher la déconnexion.
  3. Constater le dialogue de confirmation et sa structure.
  4. Confirmer.
  5. Constater l'écran d'arrivée.
- **Résultat attendu** : un dialogue à **deux** boutons est ouvert et il n'est
  **pas** en état d'erreur (ce qui le distingue structurellement du refus de
  navigation) ; après confirmation, l'URL atteinte est celle de la page de
  déconnexion ICF et **aucun runtime UI5 n'est présent**.
- **Assertion locale-indépendante** : le chemin de l'URL et l'absence de runtime,
  jamais le texte d'adieu.
- **Keywords métier manquants** : aucun.

### 22. Épingler puis dépingler une application rend l'accueil à son état initial

- **Préconditions** : shell rendu, App Finder accessible, **accord explicite
  d'écriture donné** (voir ci-dessous). Joué AVANT la déconnexion.
- **Portée** : c'est le **seul scénario qui écrit** de la campagne, et il écrit
  une personnalisation d'accueil de l'utilisateur, pas une donnée métier. Il lève
  le « candidat d'écriture NON exécuté » du scénario 13.
- **Étapes** :
  1. Relever l'état initial de l'accueil : intents des tuiles rendues et volume
     de chaque groupe.
  2. Ouvrir l'App Finder et filtrer sur un terme qui ne laisse qu'UNE vignette,
     visant une application ABSENTE de l'accueil.
  3. Épingler cette application dans le groupe d'accueil, par la case de son
     rang dans le popover de choix des groupes.
  4. Revenir à l'accueil et constater.
  5. Rouvrir l'App Finder, refiltrer, retirer l'épinglage.
  6. Revenir à l'accueil et constater le retour à l'état initial.
- **Résultat attendu** : l'application épinglée est absente de l'accueil au
  départ ; après épinglage, son intent y figure et le volume total des groupes a
  augmenté d'exactement une tuile ; après retrait, son intent a **disparu**, les
  intents rendus et les volumes de groupe sont **identiques** au relevé initial.
- **Ce que le scénario refuse de supposer** : la restauration se constate sur la
  DISPARITION de l'intent épinglé, pas sur un compte revenu à sa valeur de
  départ, qui ne prouverait qu'une arithmétique. Et l'absence initiale de
  l'application est vérifiée : sans elle, le cycle serait vert sans rien prouver.
- **Opt-in à deux tours** : tag `write` ET `-v ABAP_FLP_WRITE_OPT_IN:yes`, sans
  quoi le test est SAUTÉ, y compris dans un run complet de `tests/robot/`. Un tag
  seul dépendrait de la mémoire de celui qui lance la commande.
- **Filet de sécurité** : le teardown journalise le diagnostic AVANT de nettoyer
  (le nettoyage détruit l'écran en échec), puis retire l'épinglage s'il est
  encore là, y compris après un échec en cours de cycle.
- **Structure relevée live sur cette cible** : le bouton d'épinglage ouvre un
  popover `groupsPopover-popover` portant une case à cocher par groupe, dans
  l'ORDRE des groupes du service, plus une entrée « nouveau groupe » que le
  scénario ne touche JAMAIS (elle créerait un groupe), et un bouton de fermeture
  `closeButton`. Structure **identique sur les deux releases**, donc aucune
  variable de cible.
- **Deux pièges mesurés** : le service `LaunchPage` sert un modèle PÉRIMÉ tant
  qu'on est sur l'App Finder (le constat se prend après retour à l'accueil), et
  la propriété `selected` du bouton d'épinglage retarde d'un cycle (encore
  `False` juste après un épinglage, encore `True` juste après un retrait) :
  l'état qui fait foi est celui des cases du popover.
- **Keywords métier manquants** : `Lire L Unique Application De L App Finder`,
  `Epingler L Application`, `Depingler L Application`,
  `Lire Les Intents Des Tuiles De L Accueil`, `Exiger L Accord D Ecriture`,
  `Retirer L Epinglage Si Present`, `Nettoyer L Epinglage Et Diagnostiquer`.

## Écarts constatés face au FLP 1.71 (A4H 1909)

Point par point sur la liste que la campagne devait trancher. « Identique »
signifie mesuré identique, pas supposé.

### 1. Architecture : IDENTIQUE

Aucune iframe, ni sur l'accueil ni application ouverte (`frames: []`,
`Get Ui5 App Frame` échoue en nommant l'absence). Le témoin d'application ouverte
est le même : `application-<SemanticObject>-<action>` (`ApplicationContainer`)
plus `-content` (`ComponentContainer`), présent exactement une fois quand
l'application est ouverte, zéro sinon. Un seul conteneur à la fois, la navigation
arrière reconstruit le précédent. **Rien à paramétrer.**

### 2. Service de catalogue : DIFFÉRENT, et c'est une bonne nouvelle

`SearchableContent` **existe** en 1.120, là où son module répondait 404 en 1.71.
Les deux voies donnent **exactement le même ensemble de 62 intents** (zéro écart
dans les deux sens), avec une différence de granularité : 67 tuiles côté
`LaunchPage`, 66 applications côté `SearchableContent` (le service neuf fusionne
des visualisations qui partagent une cible). Chaque application retournée porte
`_instantiationData.platform = "LAUNCHPAD"` : sur ce FLP ABAP, le service neuf
est une façade sur l'ancien.

Autres services : `Navigation`, `Pages`, `SpaceContent`, `UserDefaultParameters`,
`AppLifeCycle`, `SupportTicket`, `UserRecents` sont présents ici et n'étaient pas
sondés là-bas. `AppConfiguration` et `CommonDataModel` restent absents sur les
DEUX cibles. `Spaces` et `Ushell` sont absents ici (modules non servis).

**Conséquence page object** : la SOURCE d'inventaire doit être une variable de
cible, avec `LaunchPage` comme voie universelle et le second service comme
vérification croisée conditionnelle.

### 3. Volumétries : moitié identiques, moitié pas

| Mesure | 1.71 (A4H) | 1.120 (2023) | Verdict |
|---|---|---|---|
| Catalogues assignés | 2 | 2 | identique |
| Tuiles de catalogue | 67 | 67 | identique |
| Intents uniques | 62 | 62 | identique |
| Intents résolvables | 61 | 61 | identique |
| Seul intent non résolvable | `ApplicationJob-show` | `ApplicationJob-show` | identique |
| Objets sémantiques | 46 | 46 | identique |
| Vignettes App Finder rendues | 54 | 54 | identique |
| **Contrôles à l'accueil** | 184 (192 à 200 en re-run) | **134 à 169** | **différent** |
| **`ShellHeadItem` rendus à l'accueil** | 2 | **1** | **différent** |
| **`ShellHeadItem` rendus en application** | 3 | **2** | **différent** |
| **Tuiles sur l'accueil** | 4 | **1** | **différent** |
| **Tuiles au compteur résolu** | 3 | **0** | **différent** |
| Entrées du menu « toutes mes applications » | 64 | 60 | différent, même règle relationnelle |
| **Erreurs console au chargement propre** | 3 | **4, familles différentes** | **différent** |
| Langue servie | EN | EN | identique |
| **Thème** | `sap_belize` | **`sap_horizon`** | **différent** |

Le plancher de contrôles de l'accueil de la suite 1.71 (« supérieur à 150 »)
**échouerait** sur cette cible, qui mesure 134 au premier chargement. Le plancher
doit être une variable, à 100 ici.

### 4. Identifiants : trois renommages, deux disparitions, une clé sortie de l'id

**Survivent tels quels** (utilisables par les deux campagnes) : `sf`,
`shellAppTitle`, `backBtn`, `endItemsOverflowBtn`, `searchFieldInShell-input`,
`searchFieldInShell-button`, `sapUshellDashboardPage`, `sapUshellDashboardFooter`,
`sapUshellDashboardFooterDoneBtn`, `appFinderSearch`, `catalogSelect`,
`appFinderPage`, `catalogTiles`, `catalogTilesDetailedPage`,
`sapUshellAllMyAppsPopover-popover`, `sapUshellAllMyAppsDataSourcesList`,
`userSettingEntryList`, `userSettingSaveButton`, `userSettingCancelButton`, et
les huit suffixes d'action de la zone utilisateur.

**Renommés** :

| Rôle | 1.71 | 1.120 |
|---|---|---|
| Zone utilisateur | `meAreaHeaderButton` (`ShellHeadItem`) | **`userActionsMenuHeaderButton` (`sap.m.Avatar`)** |
| Popover de la zone utilisateur | `sapUshellMeAreaPopover` | **`sapUshellUserActionsMenuPopover`** |
| Dialogue « à propos » | `aboutContainerDialogID` | **`aboutDialogFragment--aboutDialog`** |
| Préfixe du dialogue des paramètres | `sapFlpUserSettings-View--` | **`settingsView--`** |

**Disparus** : `homeBtn` (le contrôle n'existe plus, ni rendu ni au registre),
`appFinderView`.

**Clé sortie de l'identifiant** : les rubriques de paramètres, qui portaient leur
clé technique dans leur id (`themes-UserSettingsEntry`), ont désormais un id
entièrement généré (`__item3-settingsView--userSettingEntryList-<index>`). La clé
n'est plus lisible que dans le contexte de liaison, propriété `id`. Deux clés ont
aussi changé de nom ou de casse : `flpSettingsEntry` devient `homepageEntry`, et
`UserActivitiesEntry` devient `userActivitiesEntry`.

C'est **le résultat le plus utile de la campagne** : le page object partagé ne
peut pas graver ces ancres, il doit les recevoir en variables.

### 5. Piège de rendu (`homeBtn` visible sans nœud DOM) : NE SE REPRODUIT PAS

Et pour une raison plus radicale que prévu : en 1.120 le contrôle n'existe pas du
tout (`Get Ui5 Match Count idSuffix=homeBtn` retourne 0 partout). La règle
générale (« `visible` peut valoir vrai sur un contrôle jamais construit ») reste
juste, mais aucun cas n'a été observé sur cette release. Le remède du plan 1.71
(revenir à l'accueil par l'intent, jamais par le bouton) reste le bon, et il
devient obligatoire ici.

### 6. Zone utilisateur : même règle, même piège de position, une entrée en moins

7 entrées rendues à l'accueil, 6 dans une application, écart exact = l'entrée
d'édition. C'est le même RÉSULTAT que la cible 1.71 après correction du
générateur (7 et 6), et la même mécanique d'identifiant `__list0-<index>-<action>`
où l'index change d'un endroit à l'autre.

Différence : l'entrée « Give Feedback » (`-EndUserFeedbackBtn`), déclarée mais
jamais rendue en 1.71, **n'existe pas du tout** en 1.120. L'assertion écrite par
le générateur (comparer les deux relevés plutôt que compter) reste valide sans
retouche : c'est exactement pour cela qu'elle avait été écrite ainsi.

Nouveauté observable : le panneau des activités récentes, jamais ouvert lors de
la campagne 1.71, expose des identifiants stables
(`sapUshellActivityListrecentActivities`, `recentActivityFilter`,
`frequentlyUsedFilter`), donc du contenu de test neuf (scénario 11).

### 7. Nouveautés de release : présentes, mais pas toutes activées

- **Thème Horizon** : actif (`sap_horizon` contre `sap_belize`). Aucun impact sur
  les ancres relevées, mais tout scellement visuel serait à refaire.
- **Espaces et pages** : le runtime les porte (`Pages` et `SpaceContent`
  répondent) mais le mode **n'est pas activé** : la configuration ushell ne
  déclare que `ushell.spaces.myHome.enabled`, le service `Spaces` n'est même pas
  servi, et l'accueil rendu reste la page classique à groupes
  (`sap.ushell.components.homepage.DashboardContent`, `TileContainer`,
  `AnchorNavigationBar`). Constat honnête : **capacité présente, non activée sur
  cette cible**. Le comportement en mode espaces n'a pas été observé.
- **Web Components dans le shell** : **aucun** (`wc_hosts = 0`). Le shell reste
  du UI5 classique ; les moteurs `role` et `xpath` suffisent, `wc` est inutile.
- **Dépréciations `[FUTURE FATAL]`** : le contraste du plan 1.71 (« ce runtime
  n'émet aucune dépréciation, la famille est vide ») **tombe**. Le 1.120 en émet,
  comme le launchpad Work Zone 1.151. Le tri des erreurs console doit donc porter
  cette famille, et elle vient du shell de SAP lui-même.
- **Dialogue « à propos » restructuré** : trois sections (Application, System,
  Environment), avec le composant technique, le type d'appareil, le thème et
  l'agent utilisateur. En revanche il **ne nomme plus le rôle du mandant**, que
  la campagne 1.71 relevait.

### 8. Acquittement des dialogues : la position n'est plus universelle

C'est l'écart le plus piégeux, parce qu'il rend un test VERT ailleurs et ROUGE
ici sans changer de code.

| Dialogue | 1.71 | 1.120 |
|---|---|---|
| Refus de navigation | 3 boutons, acquittement en position 0 | **2 boutons : [0] `Copy`, [1] `Close`** |
| Confirmation de déconnexion | 2 boutons : [0] OK, [1] Cancel | 2 boutons : [0] OK, [1] Cancel |

Sur cette cible, acquitter un refus par la position 0 **copie le message
technique et laisse le dialogue ouvert**. La campagne l'a vécu : le mot-clé
d'acquittement a échoué après 20 secondes d'attente d'une fermeture qui ne
venait pas. La position d'acquittement doit donc être **deux variables
distinctes**, une par type de dialogue, et non la constante unique du page
object actuel.

### 9. Lecture des tuiles de l'accueil : le mot-clé partagé ne marche PAS ici

En 1.71, l'intent d'une tuile se lit dans le contexte de liaison
(propriété `target`) et son titre en descendant l'agrégation `content` jusqu'au
`GenericTile`. En 1.120 :

- `target` vaut **la chaîne vide** dans le contexte de liaison ;
- `content` ne contient plus qu'un `sap.ui.core.ComponentContainer` : la tuile
  est rendue par un COMPOSANT séparé, et la descente par agrégations ne l'atteint
  pas.

Résultat mesuré : le mot-clé partagé retourne une tuile au titre vide et à
l'intent vide, sans échouer. C'est le pire cas, une lecture silencieusement
fausse.

La voie qui fonctionne sur cette release, et qui a été vérifiée live : partir du
contrôle de tuile, prendre son nœud DOM, et lire (a) l'intent dans l'attribut
`href` de son ancre HTML, (b) le titre sur la propriété `header` du `GenericTile`
contenu dans ce nœud, (c) le compteur sur la propriété `value` du
`NumericContent` contenu. La sélection des contrôles « contenus » se fait par
CONTAINMENT DOM, pas par agrégation.

### 10. Budgets d'attente : la même page, deux ordres de grandeur

Sur cette cible et système chaud : connexion 3,7 s, rendu du shell environ 2 s,
ouverture de `Repository-manage` 2 s, mais ouverture de `EPMProduct-manage_st`
**40 s** et retour au repos après navigation arrière **55 s**. Le budget d'idle
par défaut de la bibliothèque (15 s) est insuffisant pour deux étapes sur ce
système. Il doit être une variable, et son échec ne doit pas se lire comme une
anomalie applicative.

## Écarts constatés à la génération

Relevés le 2026-08-24 par sap-generator, en rejouant chaque étape live avant
écriture puis en exécutant la suite complète. Aucun n'invalide un scénario : ce
sont des précisions de comportement, dont quatre ont fait rougir un premier run
et vivent désormais dans le page object partagé.

1. **Le panneau des activités récentes n'est pas un panneau du popover, c'est
   une BOÎTE DE DIALOGUE.** Le plan (scénario 11, écart 6) le décrit comme
   « un panneau DANS le popover ». Mesuré : l'entrée ouvre un dialogue
   d'identifiant `quickAccess`, et le popover de la zone utilisateur se referme
   à cet instant, exactement comme il le fait pour le dialogue « à propos ». Ce
   que le plan avait bien vu reste vrai : l'URL ne change pas, la liste et ses
   deux onglets portent les identifiants annoncés, et cinq entrées sont rendues.
   Conséquence sur la suite : le témoin d'ouverture est la LISTE elle-même et
   non le type du popup qui la porte, et la fermeture se constate sur
   l'ABSENCE DE TOUT POPUP, pas seulement de popover, sans quoi un dialogue
   resté ouvert passerait inaperçu.
2. **La touche d'échappement ne referme pas le popover de la zone utilisateur.**
   Non prévu par le plan, et payé par un premier run rouge : l'échappement reste
   sans effet (le clic d'ouverture ne déplace pas le focus dans le popover), et
   le mot-clé partagé échouait après vingt secondes d'attente d'une fermeture
   qui ne venait pas. Le geste qui referme est la BASCULE, c'est-à-dire un
   second clic sur le bouton. Le moyen de fermeture est donc devenu une
   stratégie nommée du page object, dont la valeur par défaut (échappement)
   reste celle qui marche sur la cible 1.71.
3. **Le menu « toutes mes applications » remplit ses sources progressivement.**
   Mesuré deux sources à la lecture immédiate, trois une seconde plus tard, sur
   deux catalogues assignés. Le repos réseau ne tranche pas : les catalogues
   sont déjà chargés, l'ajout est un rendu différé. La suite attend donc que la
   liste soit complète avant de la lire.
4. **Le filtrage de l'App Finder est local, donc invisible au repos réseau.**
   Même mécanique : aucune requête ne part, le repos est atteint instantanément
   et un comptage pris juste après la validation retrouve les 54 vignettes
   d'avant filtrage. L'attente porte désormais sur le CHANGEMENT du nombre de
   vignettes rendues.
5. **La recherche du shell change l'URL avant d'exister.** Le fragment
   `Action-search` apparaît alors que l'application de résultats n'est pas
   construite : un comptage pris à cet instant compte encore la tuile de
   l'ACCUEIL et conclut à une recherche sans résultat. Fait utile découvert en
   cherchant l'ancre : le shell rend ses résultats dans une application comme
   une autre, sous le conteneur `application-Action-search`, et c'est vrai des
   DEUX releases (vérifié live sur 1.71 avant de toucher au page object). Le
   témoin d'attente est donc universel, pas une variable de cible de plus.
6. **La quatrième erreur console n'est pas apparue.** Le plan en relève quatre
   sur un chargement propre, dont le message de configuration de session émis
   « une vingtaine de secondes plus tard ». La suite en mesure trois de façon
   reproductible (deux dépréciations du shell, un 404 de recherche
   d'entreprise) : le message de session arrive après la fenêtre de mesure. La
   famille est déclarée quand même, donc classée si elle survient, et le test
   ne compte pas : il vérifie que le tri est exhaustif.
7. **Le retour arrière n'a pas coûté 55 secondes.** Mesuré environ quatre
   secondes de retour au repos entre les deux applications de la campagne, là
   où le plan relevait 55 s sur un autre couple. Le budget reste porté à
   180 secondes : c'est un plafond, pas une attente, et le premier run l'aurait
   payé sans lui.
8. **Deux applications citées plutôt que découvertes, pour la navigation
   arrière.** Le plan le prévoit (l'accueil ne rend qu'une tuile, au compteur
   jamais résolu, donc la stratégie « prendre les premières tuiles saines » de
   la campagne 1.71 ne trouve rien). La suite cite `Repository-manage` et
   `EPMProduct-shop`, mais les VÉRIFIE assignées au catalogue et résolvables
   avant de les ouvrir : sur un système où elles ne seraient pas déployées, le
   test échoue en nommant le périmètre, jamais la navigation.
9. **Contrôles rendus à l'accueil : 167 pendant la campagne**, dans la
   fourchette annoncée (134 à 169). Le plancher retenu est 100.

### Second passage du 2026-08-24 (lot d'achèvement)

- **Le plancher de contrôles de l'accueil était une assertion, ce devait être
  une ATTENTE.** Un run a relevé 84 contrôles juste après le retour au repos, là
  où le même écran en porte 167 une seconde plus tard : le test échouait en
  disant « le shell n'a pas fini de se construire », ce qui était exactement le
  cas. Une mesure prise une seule fois ne peut pas trancher entre un shell pauvre
  et un shell en cours de construction. Les deux suites attendent désormais que
  le plancher soit atteint (`Attendre Que Le Shell Soit Construit`) et n'échouent
  que s'il ne l'est jamais ; le plancher est inchangé.
- **La fermeture du popover de la zone utilisateur n'est plus une divergence de
  release.** Cette suite surchargeait la stratégie par la bascule du bouton,
  l'échappement étant sans effet ici. Mesuré depuis sur la cible 1.71 :
  l'échappement y dépend de l'endroit où se trouve le focus (vert un run, rouge
  le suivant sur le même écran), quand la bascule referme sur les DEUX releases.
  La bascule devient donc le défaut du page object, et cette suite n'a plus rien
  à surcharger sur ce point.
- **La lecture des tuiles par containment ne passe plus par du JavaScript de page
  object.** La capacité (« quels contrôles sont rendus À L'INTÉRIEUR de
  celui-ci ») est montée dans la bibliothèque sous l'argument `containedIn` de
  `Get Ui5 Ids` / `Get Ui5 Properties` (convention 12) : elle vaut pour toute
  cible Fiori, pas seulement pour un launchpad. Le page object ne porte plus que
  du vocabulaire : ce qu'est une tuile, où se lit son intent. Vérifié live, la
  lecture rend exactement les mêmes valeurs qu'avant (titre « Git-enabled CTS »,
  intent `Repository-manage`, compteur non résolu).

## Points de vigilance

### Pièges de cible et d'environnement

1. **L'URL HTTP est un piège de cible, pas une commodité.** `http://…:50100/…`
   répond, mais l'ICF redirige vers le nom d'hôte virtuel `vhcala4hci:50001`, que
   les deux conteneurs ABAP du poste annoncent, et le port 50001 est celui de
   l'AUTRE système. On explore alors le mauvais système avec une perception
   parfaitement cohérente. Attaquer directement l'URL HTTPS de la cible : vérifié
   ce jour, aucune redirection ne se produit alors.
2. **Deux contrôles valent mieux qu'un pour identifier la cible.** Le scénario 1
   prouve l'hôte, le scénario 4 prouve la RELEASE. Les deux conteneurs servent le
   même chemin ICF, avec le même formulaire de connexion, dans la même langue.
3. **Le certificat est auto-signé.** Contexte ouvert avec
   `ignoreHTTPSErrors=True` ; l'orthographe `ignoreHttpsErrors` est refusée par
   la bibliothèque Browser.
4. **Le premier chargement d'un système froid peut dépasser deux minutes**
   (compilation côté serveur). Sur la session observée le système était chaud et
   tout est resté rapide. Un échec d'attente au tout premier appel n'est pas une
   panne : rejouer avant de conclure.
5. **Les identifiants de l'autre conteneur ne valent pas ici**, et
   réciproquement. Une seule tentative fautive par campagne (scénario 2).

### Pièges de perception et de localisation

6. **Lire la propriété, pas le rendu**, et sur cette release, pas non plus le
   contexte de liaison pour une tuile (écart 9). Le rendu d'une tuile ajoute
   sous-titre, compteur et pied ; le contexte de liaison, lui, ment par omission.
7. **Les préfixes de vue et les index sont générés.** Ancrer sur le SUFFIXE.
   L'identifiant d'une entrée de la zone utilisateur contient sa POSITION, qui
   change entre l'accueil et une application.
8. **Un contrôle non rendu peut porter l'id nu qu'on croit viser.** Les
   prototypes `ActionItem` de la zone utilisateur portent `aboutBtn`,
   `logoutBtn`, etc. sans tiret. Viser `-aboutBtn` (avec le tiret) ne matche que
   l'entrée réellement rendue.
9. **Le moteur ne voit que le rendu, et c'est ce qu'on veut.** Ne jamais compter
   au registre brut ce qu'on veut compter à l'écran.
10. **Un popup fermé peut rester rendu.** Ce n'est pas le cas du dialogue « à
    propos » de cette release (il disparaît du registre après fermeture), mais
    c'en était un en 1.71. La lecture qui tranche dans les deux cas est celle des
    popups OUVERTS, jamais un comptage ni une résolution.
11. **L'App Finder rend paresseusement** (54 vignettes pour 67 tuiles). Ne
    comparer son décompte qu'à lui-même, avant et après filtrage.
12. **Le menu « toutes mes applications » rend la source SÉLECTIONNÉE**, pas tout
    le catalogue (60 pour 67).

### Pièges d'assertion

13. **Tout libellé visible est traduit** : titres de tuile, de groupe, de
    dialogue, textes de bouton, libellés de compteur, titre de page. Les ancres
    locale-indépendantes disponibles sont : le fragment d'URL, l'intent, les
    identifiants techniques de groupe et de catalogue, les identifiants stables
    du shell, la propriété d'état d'un dialogue, le TYPE d'un bouton
    (`Emphasized`), les compteurs numériques, le nombre de contrôles rendus.
14. **Les boutons d'un dialogue se désignent par leur position, mais la bonne
    position dépend du dialogue** (écart 8). Là où un doute subsiste, le TYPE
    `Emphasized` désigne l'action principale de façon locale-indépendante et
    résiste mieux qu'un index.
15. **Ne pas compter les erreurs console : les classer**, et vérifier que le tri
    est exhaustif. Une dépréciation émise par le shell de SAP n'est pas un
    défaut ; une erreur inclassée, si.
16. **L'exploration pollue sa propre mesure.** Sonder les services ushell absents
    a ajouté plusieurs 404 imputés au bootstrap. La mesure de référence se prend
    sur un chargement propre, journal purgé.
17. **Un fournisseur de données peut échouer en silence.** La tuile au compteur
    `...` n'a produit AUCUNE erreur console ici, alors qu'elle en produisait une
    sur la cible 1.71. Un test qui déduirait l'état des tuiles du journal de
    console serait faux.

### Portée et effets de bord

18. **Naviguer écrit l'historique utilisateur.** Le panneau des activités
    récentes contenait, dès l'ouverture, des applications visitées lors de
    sessions antérieures. C'est un effet de bord inévitable de toute navigation,
    pas une écriture métier, mais il doit être consigné : une campagne en
    « lecture seule » modifie tout de même cet état, et un test qui asserterait
    le CONTENU de cette liste serait dépendant de l'historique.
19. **Le bouton d'enregistrement des paramètres écrit côté serveur.** Jamais
    actionné. Sortie par annuler.

### Pièges d'outillage

20. **`Wait For Ui5 Idle` prend un `settle` en chaîne de temps Robot.** Passer
    `settle=2000` vaut 2000 SECONDES. Écrire `settle=2 s`.
21. **Le budget d'idle par défaut (15 s) est trop court sur ce système** pour
    l'ouverture de certaines applications et pour la navigation arrière (mesuré
    55 s). Le paramétrer plutôt que d'interpréter son échec.
22. **Le serveur rf-mcp fige la bibliothèque ET son bundle JS déjà injecté.**
    Deux marches, pas une : recharger les modules puis échanger la classe de
    l'instance rend les nouveaux mots-clés VISIBLES, mais le bundle `__SAPFX`
    déjà présent dans la page reste l'ANCIEN, et l'appel échoue par
    `window.__SAPFX.openPopups is not a function`. Il faut **recharger la page**
    pour que le bundle neuf soit injecté. Constat de la présente campagne, à
    ajouter aux notes terrain rf-mcp du dépôt.
23. **Le serveur rf-mcp ne travaille pas forcément depuis la racine du dépôt** :
    importer les resources par chemin absolu.
24. **`sapfx_state` regarde les bibliothèques IMPORTÉES de la session**, pas
    celles qu'une resource embarque : importer explicitement `Browser` et
    `SapFioriLibrary`.

## Ce qui n'a pas été observé : décision par point

Révision du 2026-08-24 (second passage) : chaque point porte désormais un
verdict, pas un simple constat. Trois verdicts possibles, et rien d'autre :
**couvert** (un scénario existe maintenant), **refusé** (avec sa raison, la
décision est prise et ne sera pas reprise à l'identique), **reporté** (avec ce
qu'il faudrait pour le lever).

| Point | Verdict | Motif, ou ce qu'il faudrait |
|---|---|---|
| Cycle réversible « épingler puis dépingler » | **couvert** | Scénario 22, opt-in à deux tours, validé live sur cette cible |
| Le mode « espaces et pages » en fonctionnement | **reporté** | Capacité présente dans le runtime, non activée sur cette cible. Il faudrait l'activer côté serveur (réglage ushell), ce qui change l'accueil de TOUS les utilisateurs du système et invaliderait les relevés de la campagne : à ouvrir comme une campagne distincte, sur un système où le mode est déjà actif |
| Le premier chargement d'un système réellement froid | **reporté** | Il faudrait redémarrer le conteneur juste avant le run. C'est une mesure d'ENVIRONNEMENT, pas un comportement du launchpad : la seule conséquence produit (le budget d'attente de démarrage) est déjà paramétrée à 180 s et vérifiée par le fait que la campagne passe |
| Le seuil de verrouillage du compte | **refusé** | Ne se mesure pas sans verrouiller le compte, et c'est le SEUL compte des deux campagnes sur un système partagé : le prix d'un chiffre serait de rendre les deux suites injouables. Une seule tentative fautive par campagne, délibérément |
| Le bouton de débordement de la barre shell | **reporté** | Il faudrait une variante de largeur de fenêtre (jamais rendu en 1600 x 1000) : c'est un scénario de responsive design, à ouvrir comme tel |
| Le contenu de l'onglet « Frequently Used » | **reporté** | L'onglet est relevé et son ouverture est atteignable ; l'assertion resterait STRUCTURELLE, le contenu dépendant de l'historique de l'utilisateur, y compris de sessions antérieures |
| La recherche par titre EXACT d'application | **refusé** | Soumettre un titre exact, c'est soumettre un libellé TRADUIT : le scénario serait vert en anglais et rouge en allemand sur le même système (convention 3). Le comportement est consigné comme fait, pas comme test |
| L'envoi d'un retour utilisateur | **refusé** | L'entrée n'existe pas sur cette cible, et le composant émet une requête SORTANTE : ce n'est plus le launchpad qu'on éprouverait |
| Le changement de langue ou de thème | **refusé** | Écriture de personnalisation qui invaliderait tous les relevés de libellés de la campagne, pour éprouver un réglage et non un comportement |

## Annexe : localisateurs et intents relevés, pour le page object partagé

Rien de ce qui suit n'a sa place dans une suite (convention 1). Tout vit dans
`resources/page_objects/abap_flp.resource`. La colonne « variable » dit ce qui,
au vu des écarts ci-dessus, doit devenir **paramétrable par cible** au lieu de
rester une constante du fichier.

### Page de connexion ICF (moteur `dom`, aucun runtime UI5)

| Rôle | Sélecteur relevé | Variable ? |
|---|---|---|
| Formulaire | `[id="LOGIN_FORM"]` | non, identique sur les deux cibles |
| Champ utilisateur | `input[name="sap-user"]` | non |
| Champ mot de passe | `input[name="sap-password"]` | non |
| Sélecteur de langue | `[id="LANGUAGE_SELECT"]` | non |
| Bouton de connexion | `[id="LOGIN_LINK"]` | non |
| Message d'erreur (ancre de TYPE) | `.loginMessage.sapUiError` | non |

Rappel du piège déjà encodé : une valeur de cellule Robot qui commence par `#`
est un commentaire. Écrire les identifiants en sélecteur d'attribut.

### Shell (moteur `role`, ancrage par suffixe d'identifiant)

| Rôle | Ancre 1.120 | Type | Variable ? |
|---|---|---|---|
| Zone utilisateur | `userActionsMenuHeaderButton` | `sap.m.Avatar` | **OUI** (1.71 : `meAreaHeaderButton`, `ShellHeadItem`) |
| Popover de la zone utilisateur | `sapUshellUserActionsMenuPopover` | `sap.m.Popover` | **OUI** (1.71 : `sapUshellMeAreaPopover`) |
| Type du bouton de zone utilisateur | `sap.m.Avatar` | | **OUI** (le type a changé, pas seulement l'id) |
| Bouton retour | `backBtn` | `ShellHeadItem` | non |
| Bouton de débordement | `endItemsOverflowBtn` | `ShellHeadItem` | non |
| Bouton recherche | `sf` | `ShellHeadItem` | non |
| Champ de recherche | `searchFieldInShell-input` | `SearchInput` | non |
| Titre de shell / menu apps | `shellAppTitle` | `ShellAppTitle` | non |
| Popover « All My Apps » | `sapUshellAllMyAppsPopover-popover` | `sap.m.Popover` | non |
| Liste des sources « All My Apps » | `sapUshellAllMyAppsDataSourcesList` | `sap.m.List` | non |
| Page du tableau de bord | `sapUshellDashboardPage` | `sap.m.Page` | non |
| Bouton « terminé » du mode édition | `sapUshellDashboardFooterDoneBtn` | `sap.m.Button` | non, seul témoin valable sur les deux cibles |
| Bouton accueil | **inexistant** | | **OUI** (existe en 1.71, jamais rendu) |
| Nombre de `ShellHeadItem` rendus, accueil | 1 | | **OUI** (2 en 1.71) |
| Nombre de `ShellHeadItem` rendus, application | 2 | | **OUI** (3 en 1.71) |

### Entrées de la zone utilisateur (ancre = suffixe d'action, avec son tiret)

`-recentActivitiesBtn`, `-frequentActivitiesBtn`, `-openCatalogBtn`,
`-userSettingsBtn`, `-ActionModeBtn` (accueil seulement), `-aboutBtn`,
`-logoutBtn`. Identiques aux deux cibles. `-EndUserFeedbackBtn` n'existe pas ici.

Panneau des activités : liste `sapUshellActivityListrecentActivities`, onglets
`recentActivityFilter` et `frequentlyUsedFilter` (nouveau, non relevé en 1.71).

### Dialogues

| Rôle | Ancre 1.120 | Variable ? |
|---|---|---|
| Dialogue « à propos » | `aboutDialogFragment--aboutDialog` | **OUI** (1.71 : `aboutContainerDialogID`) |
| Dialogue des paramètres | `userSettingsDialog` (préfixe `settingsView--`) | non, le suffixe suffit |
| Annuler les paramètres | `userSettingCancelButton` | non |
| Enregistrer les paramètres | `userSettingSaveButton` | non, **ne jamais actionner** |
| Liste maître des paramètres | `userSettingEntryList` | non |
| Clé technique d'une rubrique | **contexte de liaison, propriété `id`** | **OUI** (1.71 : dans l'identifiant, suffixe `-UserSettingsEntry`) |
| Dialogue de refus de navigation | `controlType=sap.m.Dialog` + `state = Error` | non |
| Position d'acquittement d'un refus | **1** (dernière, `Close`, type `Emphasized`) | **OUI** (0 en 1.71) |
| Position de confirmation d'une déconnexion | 0 (`OK`) | non, identique |

### App Finder et tuiles

| Rôle | Ancre 1.120 | Variable ? |
|---|---|---|
| Champ de recherche | `appFinderSearch` | non |
| Liste des sources | `catalogSelect` | non |
| Page | `appFinderPage` | non |
| Conteneur des tuiles | `catalogTiles` | non |
| Page de détail | `catalogTilesDetailedPage` | non |
| Vue | **inexistante** (`appFinderView` en 1.71) | sans objet, non utilisée |
| Vignette d'application | `controlType=sap.ushell.ui.appfinder.AppBox` | non |
| Bouton d'épinglage | `controlType=sap.ushell.ui.appfinder.PinButton` | non, **écriture** |
| Tuile de l'accueil | `controlType=sap.ushell.ui.launchpad.Tile` | non |
| Titre d'une tuile | propriété `header` du `sap.m.GenericTile` CONTENU | **OUI** (agrégation `content` en 1.71) |
| Intent d'une tuile | attribut `href` de l'ancre HTML de la tuile | **OUI** (contexte de liaison `target` en 1.71, vide ici) |
| Compteur d'une tuile | propriété `value` du `sap.m.NumericContent` CONTENU | **OUI** (même raison) |
| Conteneur de groupe | `controlType=sap.ushell.ui.launchpad.TileContainer` | non |

### Témoin « quelle application est ouverte »

`application-<SemanticObject>-<action>` (`ApplicationContainer`) et
`application-<SemanticObject>-<action>-content` (`ComponentContainer`).
**Identique aux deux cibles, aucune variable.** Les intents servis par le shell
lui-même (`Shell-home`, `Shell-appfinder`) ne produisent aucun conteneur de ce
genre.

### Intents relevés (sous-ensemble utile)

| Intent | Application | Nature |
|---|---|---|
| `Shell-home` | accueil | page du shell |
| `Shell-appfinder` | App Finder | page du shell |
| `Action-search` | résultats de recherche | application du shell |
| `Repository-manage` | Git-enabled CTS | **seule tuile de l'accueil**, compteur non résolu |
| `EPMProduct-shop` | Shop | application de démonstration, lecture, 1232 contrôles |
| `EPMProduct-manage_st` | Manage Products | application de démonstration, 638 contrôles, ouverture lente |
| `EPMPurchaseOrder-approve` | Approve Purchase Orders | **écriture métier**, à n'ouvrir qu'en consultation, non ouverte ici |
| `ApplicationJob-show` | (aucune) | assigné au catalogue, **non résolvable** |
| `Foo-bar` | (aucune) | intent fabriqué, contre-preuve de la préflight |

Les trois intents de démonstration EPM sont **au catalogue mais pas sur
l'accueil** : la découverte de l'application sous test doit passer par le
catalogue, pas par les tuiles.

### Services de perception

| Besoin | Service | Remarque |
|---|---|---|
| Groupes et tuiles de l'accueil | `LaunchPage` | `getGroups`, `getGroupId`, `getGroupTiles` |
| Catalogues et leurs tuiles | `LaunchPage` | `getCatalogs` (résultats en `progress`), `getCatalogTiles`, `getCatalogTileTargetURL` |
| Inventaire des applications | `SearchableContent` | **disponible ici, absent en 1.71** : vérification croisée conditionnelle |
| Résolvabilité d'un intent | `CrossApplicationNavigation` | `isIntentSupported` sur une liste |
| Identité de session | `sap.ushell.Container.getUser()` | id, langue, thème |
| Intent d'une tuile de l'accueil | **ancre HTML de la tuile** | `getTileTarget` et le contexte de liaison ne répondent pas sur cette release |
