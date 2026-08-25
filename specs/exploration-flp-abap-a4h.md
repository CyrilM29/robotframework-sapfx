# Launchpad Fiori (FLP) du système ABAP A4H : perception et parcours de shell

- **Canal** : Fiori (web), runtime SAPUI5 classique servi par un serveur ABAP
  (pas un cFLP SAP BTP, pas de Web Components, pas d'iframe applicative).
- **Système / URL** : `https://localhost:50001/sap/bc/ui2/flp?sap-client=001`
  (ABAP Platform 1909 en conteneur Docker, dit « A4H »).
- **Exploration live** : 2026-08-24, rf-mcp (Browser + SapFioriLibrary),
  utilisateur `DEVELOPER`, mandant `001`, langue servie `EN`, thème `sap_belize`.
- **Préconditions** :
  - le conteneur A4H répond en **HTTPS sur le port 50001** (voir « Pièges » :
    la voie HTTP est un piège de cible, pas une commodité) ;
  - certificat auto-signé, donc contexte navigateur ouvert avec
    `ignoreHTTPSErrors=True` (orthographe exacte, voir « Pièges ») ;
  - identifiants passés en ligne de commande (`-v FLP_USER:…`,
    `-v "FLP_PASSWORD: Secret:…"`), jamais committés (convention 11) ;
  - aucune donnée de démo à générer : le contenu du launchpad vient des rôles
    livrés avec l'image, il n'y a rien à provisionner.
- **Portée** : **lecture seule par défaut**, aucun scénario n'écrit de donnée
  métier. Un seul scénario écrit, et il écrit une personnalisation d'accueil
  RÉVERSIBLE (scénario 20, épingler puis dépingler), derrière un accord explicite
  à deux tours : sans lui il est sauté. L'autre écriture possible relevée à
  l'exploration (approuver une commande d'achat) est **refusée**, voir la section
  des décisions.

## Données observées

Tout ce qui suit a été relevé live le 2026-08-24. Rien n'est déduit.

### Identité de la cible

| Fait | Valeur observée |
|---|---|
| Runtime UI5 (`sap.ui.version`) | `1.71.47` |
| SAPUI5 annoncé par le dialogue « À propos » | `1.71.50 (202208100916)` |
| Product Version (dialogue « À propos ») | SAP LT REPLICATION SERVER 2.0, **ABAP PLATFORM 1909**, SAP S/4HANA FOUNDATION 1909, **SAP FIORI FRONT-END SERVER 6.0** |
| Rôle du mandant | Customizing |
| Utilisateur / nom affiché | `DEVELOPER` / « John Doe » |
| Langue servie / thème | `EN` / `sap_belize` |
| Langues proposées à la connexion | 2 seulement : `DE - Deutsch`, `EN - English` |
| Contrôles UI5 sur l'accueil (chargement propre) | **184** |
| Web Components (`wc_hosts`) | 0 |
| iframes | **0, y compris application ouverte** |
| Moteurs de résolution recommandés | `role`, `xpath`, `dom` |

Les deux numéros de version cohabitent légitimement : `sap.ui.version` donne la
version du runtime chargé, le dialogue « À propos » donne la version de
distribution SAPUI5 et son horodatage de build, qui est aussi le cache-buster
présent dans les URL de ressources (`~20220810091600~`).

### Architecture : un seul document, un seul registre

C'est le fait structurant, et il oppose cette cible au launchpad SAP Build Work
Zone déjà exploré (`specs/workzone-launchpad-btp-perception.md`) :

- l'application ouverte **n'est PAS dans une iframe** : `Get Page Composition`
  rapporte `frames: []` avec l'application chargée, et `Get Ui5 App Frame`
  échoue en nommant l'absence d'iframe ;
- il n'y a donc **ni pile de frames, ni portée à empiler, ni étanchéité de
  portée** : shell et application partagent le même registre UI5 ;
- le nombre de contrôles est le témoin du chargement : 184 (accueil), 839 (Shop),
  1329 (Manage Products), 1576 (Approve Purchase Orders) ;
- l'entrée dans une application n'ajoute **aucune** iframe : l'hôte est un
  `sap.ushell.components.container.ApplicationContainer` construit dans la page.

### Catalogue réel de l'utilisateur

Lu au service ushell `LaunchPage`, pas sur les tuiles rendues.

| Fait | Valeur observée |
|---|---|
| Catalogues assignés | 2 |
| Catalogue `SAP_BASIS_TCR_T` (« SAP: Application Services ») | 64 tuiles |
| Catalogue `SAP_EPM_BC_PURCHASER_T` (« Sample Applications ») | 3 tuiles |
| Total tuiles de catalogue | **67** |
| Intents uniques | **62** (5 tuiles partagent un intent déjà présent) |
| Objets sémantiques distincts | 46 |
| Intents résolvables (`isIntentSupported`) | **61 sur 62** |
| Seul intent assigné mais NON résolvable | `ApplicationJob-show` |

Le service `SearchableContent`, qui est la bonne source sur un cFLP Work Zone,
**n'existe pas ici** : son module répond 404 sur ce ushell. Les services
`AppConfiguration` et `CommonDataModel` sont eux aussi absents (404). Les
services disponibles et utiles à la perception sont `LaunchPage`,
`CrossApplicationNavigation`, `NavTargetResolution`, `UserInfo`,
`ShellNavigation`, `URLParsing`, `Menu`, `VisualizationDataProvider`, `Search`,
`Bookmark`, `Personalization`.

### Groupes et tuiles de l'accueil

| Groupe (id technique) | Titre rendu | Tuiles |
|---|---|---|
| `/UI2/Fiori2LaunchpadHome` | **« My Home »** (le service, lui, retourne « Fiori Wave2 Launchpad Home ») | 1 |
| `SAP_EPM_BCG_PURCHASER_T` | « Sample Applications » | 3 |

Les quatre tuiles, avec leur intent cible relevé dans le contexte de liaison du
contrôle (jamais dans un attribut DOM : la page ne contient aucune ancre `#…`) :

| Titre de tuile | Sous-titre | Intent | Compteur | Libellé du compteur |
|---|---|---|---|---|
| git-enabled CTS | (aucun) | `Repository-manage` | `...` | **Error** |
| Approve Purchase Orders | Fiori Sample App | `EPMPurchaseOrder-approve` | 19 | Items to be Approved |
| Shop | Fiori Sample App | `EPMProduct-shop` | 0 | Items in My Cart |
| Manage Products (Fiori Elements) | Fiori Sample Apps | `EPMProduct-manage_st` | **214** | Products |

Les quatre sont des tuiles **dynamiques** (`applauncherdynamic`), pas statiques.
Trois résolvent leur compteur, la quatrième non : la tuile « git-enabled CTS »
interroge `/sap/bc/cts_abapvcs`, reçoit un HTTP 200 sans charge utile
exploitable, affiche `...` en valeur et « Error » en pied de tuile. C'est
reproductible et ce n'est pas un incident de test.

Le compteur **214** de « Manage Products » coïncide avec le `$count` OData de
`SEPMRA_C_PD_Product` relevé sur ce même système (214 = 205 actives + 9
brouillons, cf. les notes terrain du dépôt) : c'est un croisement écran ↔ API
disponible sans effort, et il est locale-indépendant.

### Barre shell et zone utilisateur

Identifiants **stables** (non générés), relevés sur le registre :

| Rôle | Id | Type | Rendu à l'accueil | Rendu dans une application |
|---|---|---|---|---|
| Accueil | `homeBtn` | `ShellHeadItem` | non | **non** (voir Pièges) |
| Retour | `backBtn` | `ShellHeadItem` | non | oui |
| Débordement | `endItemsOverflowBtn` | `ShellHeadItem` | non | non |
| Zone utilisateur | `meAreaHeaderButton` | `ShellHeadItem` | oui | oui |
| Recherche | `sf` | `ShellHeadItem` | oui | oui |
| Titre / menu « All My Apps » | `shellAppTitle` | `ShellAppTitle` | oui | oui |

Nombre de `ShellHeadItem` **rendus** : **2 à l'accueil**, **3 dans une
application**. C'est une assertion structurelle et locale-indépendante.

Popover de la zone utilisateur : `sapUshellMeAreaPopover`. Ses entrées sont des
`sap.m.StandardListItem` dont l'id vaut `__list0-<index>-<idAction>` : le
préfixe et l'INDEX bougent, seul le suffixe d'action est stable.

| Entrée | Suffixe d'id stable | Présente à l'accueil | Présente dans une application |
|---|---|---|---|
| Recent Activities | `-recentActivitiesBtn` | oui | oui |
| Frequently Used | `-frequentActivitiesBtn` | oui | oui |
| App Finder | `-openCatalogBtn` | oui | oui |
| Settings | `-userSettingsBtn` | oui | oui |
| **Edit Home Page** | `-ActionModeBtn` | **oui** | **non** |
| Give Feedback | `-EndUserFeedbackBtn` | oui | oui |
| About | `-aboutBtn` | oui | oui |
| Sign Out | `-logoutBtn` | oui | oui |

Soit **8 entrées à l'accueil, 7 dans une application**.

### Dialogues du shell

| Dialogue | Id | Nature |
|---|---|---|
| À propos | `aboutContainerDialogID` | stable, 1 bouton OK |
| Paramètres | `sapFlpUserSettings-View--userSettingsDialog` | stable, boutons `…--userSettingSaveButton` / `…--userSettingCancelButton` |
| Erreur de navigation | `__dialog0` (généré) | `state = Error` |
| Confirmation de déconnexion | `__confirm0` (généré) | `state = None`, boutons `__mbox-btn-0` (OK) / `__mbox-btn-1` (Cancel) |

Les 7 entrées de la liste maître des paramètres (`…--userSettingEntryList`),
toutes à id stable : `userAccountEntry-UserSettingsEntry`,
`themes-UserSettingsEntry`, `flpSettingsEntry-UserSettingsEntry`,
`language-UserSettingsEntry`, `UserActivitiesEntry-UserSettingsEntry`,
`userProfiling-UserSettingsEntry`, `defaultParameters-UserSettingsEntry`.

### Console au chargement propre de l'accueil

**3 erreurs console, 0 exception JS non rattrapée** (`page_errors: []`), toutes
les trois explicables par la configuration du système et reproductibles :

1. `/sap/bc/cts_abapvcs` : « Failed to update data via service … no handler for
   data - 200 » (le fournisseur de données de la tuile « git-enabled CTS ») ;
2. `/sap/opu/odata/sap/ESH_SEARCH_SRV/ServerInfos` : **HTTP 403** ;
3. `/sap/es/ina/GetServerInfo` : **HTTP 404**.

Les deux dernières signalent que la recherche d'entreprise (Enterprise Search /
InA) n'est pas déployée. Contrairement à ce qu'on pourrait en conclure, la
recherche du shell **fonctionne quand même** (voir scénario 8).

Contraste utile avec le launchpad Work Zone (UI5 1.151) : ce runtime 1.71
n'émet **aucune** dépréciation `[FUTURE FATAL]`. Le tri des erreurs reste
nécessaire, mais la famille « dépréciations du shell SAP » est vide ici.

### Page de connexion et branche négative

Page de logon ICF, **pas de runtime UI5** (`Ui5 Runtime Is Present` = `False`,
`ui5_controls: 0`, moteur `dom` seul). Formulaire `LOGIN_FORM` en POST sur
`/sap/bc/ui2/flp`, avec un jeton `sap-login-XSRF` caché.

Mot de passe erroné : la page reste la page de logon, l'URL **perd son
paramètre `?sap-client=001`** (POST), et un bloc d'erreur apparaît :
`LOGIN_ERROR_BLOCK` (classe `loginMessageContainer`) contenant
`LOGIN_MESSAGE_0` de classe **`loginMessage sapUiError`**. La classe
`sapUiError` est l'ancre locale-indépendante ; le texte
(« Client, name, or password is not correct; log on again ») ne l'est pas.

### Après déconnexion

URL `https://localhost:50001/sap/public/bc/icf/logoff?sap-client=001`, titre
`Logoff`, **aucun runtime UI5**, texte « Goodbye / You have been logged off ».

## Scénarios

### 1. La page de connexion est bien celle du serveur ABAP visé

- **Préconditions** : navigateur ouvert, contexte tolérant le certificat
  auto-signé, aucune session en cours.
- **Étapes** :
  1. Ouvrir l'URL du launchpad en HTTPS.
  2. Relever l'URL réellement atteinte, AVANT toute frappe.
  3. Constater qu'aucun runtime UI5 n'est présent.
  4. Percevoir la composition de la page.
  5. Relever les champs du formulaire de connexion et les langues proposées.
- **Résultat attendu** : l'URL atteinte est celle demandée, sur l'hôte demandé
  (aucune redirection vers un autre nom d'hôte) ; le runtime UI5 est **absent** ;
  la composition annonce `ui5_controls = 0` et le seul moteur `dom` ; le
  formulaire porte un champ utilisateur, un champ mot de passe, un sélecteur de
  langue et un bouton de connexion ; le sélecteur propose exactement **2**
  langues.
- **Pourquoi ce scénario existe** : sans le contrôle d'URL de l'étape 2, une
  page de connexion servie par un AUTRE système rendrait ce test parfaitement
  vert. Voir « Pièges ».
- **Keywords métier manquants** : `Ouvrir Le Launchpad ABAP`,
  `La Page De Connexion Est Rendue`, `Lire Les Langues De Connexion`.

### 2. Une authentification refusée le dit, et ne laisse pas entrer

- **Préconditions** : scénario 1 atteint (page de connexion affichée).
- **Étapes** :
  1. Saisir un utilisateur valide et un mot de passe volontairement faux.
  2. Valider la connexion.
  3. Constater l'état de la page.
- **Résultat attendu** : la page de connexion est **toujours** là (le formulaire
  existe encore) ; un message d'erreur est rendu et il porte la classe
  d'erreur du logon ICF ; aucun runtime UI5 n'est chargé.
- **À exécuter AVANT le scénario 3** dans une même campagne : une seule
  tentative fautive, jamais plus, pour ne pas approcher le verrouillage du
  compte (le seuil est un réglage serveur, non observé ici).
- **Keywords métier manquants** : `Tenter Une Connexion`,
  `La Connexion Est Refusee`.

### 3. La connexion nominale rend un shell FLP identifiable

- **Préconditions** : page de connexion affichée.
- **Étapes** :
  1. Se connecter avec les identifiants fournis.
  2. Attendre que le runtime UI5 soit prêt puis que la page soit au repos.
  3. Percevoir la composition de la page.
  4. Lire l'utilisateur connecté, sa langue et son thème au conteneur ushell.
- **Résultat attendu** : le runtime UI5 est présent et sa version commence par
  `1.71` ; la composition annonce **zéro** hôte Web Component, **zéro** iframe,
  et les moteurs `role`/`xpath`/`dom` ; le nombre de contrôles rendus est
  supérieur à 150 (mesuré 184) ; l'utilisateur retourné par le conteneur est
  celui fourni en paramètre ; l'URL porte le fragment de l'accueil.
- **Note d'assertion** : ne jamais asserter le titre de page (« Home » est
  traduit). Le fragment d'URL, lui, ne l'est pas.
- **Keywords métier manquants** : `Se Connecter Au Launchpad`,
  `Le Shell Du Launchpad Est Rendu`, `Lire L Identite De Session`.

### 4. Le catalogue de l'utilisateur est inventorié par le service, pas par l'écran

- **Préconditions** : shell rendu (scénario 3).
- **Étapes** :
  1. Inventorier les catalogues assignés à l'utilisateur.
  2. Pour chaque catalogue, inventorier ses tuiles et leur intent cible.
  3. Dédoublonner les intents et compter les objets sémantiques.
- **Résultat attendu** : au moins un catalogue est retourné ; chaque tuile de
  catalogue porte un intent de forme `SemanticObject-action` ; le nombre
  d'intents uniques est inférieur ou égal au nombre de tuiles (des tuiles
  peuvent partager un intent : mesuré 62 intents pour 67 tuiles) ; l'inventaire
  ne dépend d'aucun rendu.
- **Pourquoi** : mesuré live, l'App Finder ne rend que les applications
  actuellement filtrées et visibles (1 seule après une recherche), là où le
  service en déclare 67. Compter sur l'écran donnerait un nombre faux.
- **Keywords métier manquants** : `Inventorier Les Catalogues`,
  `Inventorier Les Applications Du Catalogue`.

### 5. Toute application offerte au catalogue est réellement ouvrable, ou l'écart est nommé

- **Préconditions** : catalogue inventorié (scénario 4).
- **Étapes** :
  1. Soumettre la liste complète des intents du catalogue au service de
     résolution de navigation, **plus un intent fabriqué qui n'existe pas**.
  2. Séparer les intents résolvables des autres.
  3. Rapporter nommément chaque intent assigné mais non résolvable.
- **Résultat attendu** : l'intent fabriqué est déclaré **non** résolvable (c'est
  la contre-preuve : sans elle, un service qui répondrait « oui » à tout rendrait
  le test vert et vide) ; les intents assignés non résolvables sont listés.
  Sur la cible observée : 61 résolvables sur 62, l'écart étant
  `ApplicationJob-show`.
- **Décision de conception** : cet écart est **rapporté**, pas mis en échec. Il
  décrit l'état d'un système de démonstration dont tous les composants ne sont
  pas déployés ; le figer en assertion ferait échouer la campagne sur un autre
  système parfaitement sain. C'est le nombre d'écarts qui doit être stable d'un
  passage à l'autre sur une MÊME cible.
- **Keywords métier manquants** : `Les Intents Sont Ils Resolvables`,
  `Rapporter Les Applications Non Ouvrables`.

### 6. L'accueil rend ses groupes et ses tuiles, compteurs compris

- **Préconditions** : shell rendu, accueil affiché.
- **Étapes** :
  1. Inventorier les groupes de l'accueil et le nombre de tuiles de chacun.
  2. Lire la **propriété** d'en-tête de chaque tuile rendue (jamais son rendu).
  3. Lire l'intent cible de chaque tuile.
  4. Lire la valeur du compteur de chaque tuile dynamique.
- **Résultat attendu** : au moins un groupe visible ; chaque tuile rendue porte
  un intent de forme `SemanticObject-action` présent dans le catalogue du
  scénario 4 (les tuiles de l'accueil sont un sous-ensemble du catalogue) ;
  chaque tuile dynamique porte soit une valeur numérique, soit la valeur
  d'attente `...` qui signale un fournisseur de données non résolu, et ce
  dernier cas est **rapporté nommément**.
- **Assertion de croisement disponible** (optionnelle, à activer quand le canal
  API est ouvert dans la même campagne) : le compteur de la tuile dont l'intent
  est `EPMProduct-manage_st` doit égaler le `$count` de l'entity set produits du
  service OData correspondant. Mesuré 214 des deux côtés.
- **Piège encodé** : le titre RENDU du groupe par défaut (« My Home ») diffère du
  titre retourné par le service (« Fiori Wave2 Launchpad Home ») et il est
  traduit. Aucune assertion ne doit porter sur l'un ou l'autre : l'ancre est
  l'identifiant technique du groupe.
- **Keywords métier manquants** : `Inventorier Les Groupes De L Accueil`,
  `Lire Les Tuiles De L Accueil`, `Lire Le Compteur De La Tuile`.

### 7. Ouvrir une application par sa tuile et par son intent mène au même endroit

- **Préconditions** : accueil affiché.
- **Étapes** :
  1. Choisir une application de l'accueil (découverte, jamais en dur).
  2. L'ouvrir par son **intent**.
  3. Constater l'application ouverte.
  4. Revenir à l'accueil.
  5. Rouvrir la **même** application en cliquant sa tuile.
  6. Constater l'application ouverte.
  7. Comparer les deux constats.
- **Résultat attendu** : dans les deux cas, le fragment d'URL vaut l'intent de
  l'application, et le conteneur d'application correspondant à cet intent est
  présent exactement une fois ; les deux voies donnent le même fragment et le
  même conteneur. Le nombre de contrôles rendus est nettement supérieur à celui
  de l'accueil.
- **Comment constater « quelle application est ouverte »** : par la présence du
  conteneur d'application dérivé de l'intent (voir annexe). C'est un identifiant
  **calculé à partir de l'intent**, donc ni généré ni traduit ; c'est l'ancre
  qui remplace ici le test d'iframe des launchpads Work Zone.
- **Keywords métier manquants** : `Ouvrir L Application Par Intent`,
  `Ouvrir L Application Par Sa Tuile`, `L Application Ouverte Est`,
  `Revenir A L Accueil`.

### 8. La recherche du shell trouve les applications de l'utilisateur

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Ouvrir la recherche depuis la barre shell.
  2. Constater que le champ de recherche du shell est rendu.
  3. Saisir un terme correspondant à une application connue du catalogue.
  4. Déclencher la recherche.
  5. Constater le résultat.
- **Résultat attendu** : la recherche navigue vers l'intent de recherche du
  shell ; la source de données interrogée est la catégorie **applications** ;
  au moins un résultat est rendu et il correspond à une application du catalogue
  du scénario 4.
- **Fait à ne pas mal lire** : la recherche d'entreprise (ESH/InA) n'est PAS
  déployée sur cette cible (403 et 404 en console au chargement) et pourtant la
  recherche du shell fonctionne, parce qu'elle se rabat sur le catalogue
  d'applications local. Un test qui conclurait « recherche cassée » à partir des
  erreurs console serait faux.
- **Keywords métier manquants** : `Ouvrir La Recherche Du Shell`,
  `Rechercher Dans Le Shell`, `Lire Les Resultats De Recherche`.

### 9. La zone utilisateur expose ses entrées, et elles dépendent de l'endroit

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Sur l'accueil, ouvrir la zone utilisateur et relever ses entrées.
  2. Fermer, ouvrir une application, rouvrir la zone utilisateur, relever ses
     entrées.
  3. Comparer les deux relevés.
- **Résultat attendu** : les deux relevés contiennent les entrées permanentes
  (activités récentes, applications fréquentes, App Finder, paramètres, à propos,
  déconnexion) ; le relevé fait sur l'ACCUEIL contient **en plus** l'entrée
  d'édition de la page d'accueil, absente du relevé fait dans une application.
- **Assertion locale-indépendante** : chaque entrée est identifiée par le suffixe
  technique de son identifiant, jamais par son libellé, qui est traduit.
- **Piège encodé** : l'identifiant complet d'une entrée contient sa POSITION
  dans la liste, et cette position change entre l'accueil et une application.
  L'ancre est le suffixe d'action seul.
- **Keywords métier manquants** : `Ouvrir La Zone Utilisateur`,
  `Lire Les Entrees De La Zone Utilisateur`, `Fermer La Zone Utilisateur`.

### 10. Le dialogue « À propos » identifie le système et le composant courant

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Ouvrir la zone utilisateur, puis l'entrée « à propos ».
  2. Constater l'ouverture du dialogue.
  3. Relever le contenu technique du dialogue.
  4. Refermer le dialogue.
- **Résultat attendu** : le dialogue est ouvert ; il expose le nom technique du
  composant en cours, la version SAPUI5 servie, la version du produit et le rôle
  du mandant ; la version SAPUI5 annoncée est cohérente avec le runtime chargé
  (même ligne majeure/mineure) ; après fermeture, aucun dialogue n'est ouvert.
- **Valeur pour la campagne** : c'est le seul endroit de l'interface qui nomme
  la version du produit ABAP. Il donne à la campagne une **empreinte de cible**
  utile pour distinguer deux systèmes de release différente.
- **Keywords métier manquants** : `Ouvrir Le Dialogue A Propos`,
  `Lire L Empreinte Systeme`, `Fermer Le Dialogue A Propos`.

### 11. Le dialogue des paramètres s'ouvre et se referme sans rien modifier

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Ouvrir la zone utilisateur, puis l'entrée « paramètres ».
  2. Constater l'ouverture du dialogue.
  3. Relever les rubriques de sa liste maître.
  4. Refermer par **annuler**, jamais par enregistrer.
- **Résultat attendu** : le dialogue est ouvert ; sa liste maître contient au
  moins les rubriques compte utilisateur, apparence, page d'accueil, langue et
  région ; après annulation, le dialogue est fermé et **aucun réglage
  utilisateur n'a été écrit**.
- **LECTURE SEULE assumée** : le bouton d'enregistrement du dialogue écrit une
  personnalisation utilisateur côté serveur. La campagne ne l'actionne jamais.
- **Keywords métier manquants** : `Ouvrir Les Parametres Utilisateur`,
  `Lire Les Rubriques De Parametres`, `Annuler Les Parametres Utilisateur`.

### 12. L'App Finder ouvre le catalogue et sait le filtrer

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Ouvrir l'App Finder depuis la zone utilisateur.
  2. Constater l'arrivée sur l'App Finder.
  3. Relever la liste des sources de catalogue proposées.
  4. Saisir un terme de recherche et valider.
  5. Compter les applications rendues.
- **Résultat attendu** : le fragment d'URL est celui de l'App Finder ; **aucun**
  conteneur d'application n'est présent (l'App Finder est une page du shell, pas
  une application) ; la liste des sources contient une entrée « toutes » plus une
  entrée par catalogue assigné, donc son cardinal vaut le nombre de catalogues
  du scénario 4, plus un ; après filtrage, le nombre d'applications rendues est
  strictement inférieur au nombre d'applications du catalogue.
- **À ne pas faire** : compter les applications du catalogue ici. Le rendu est
  paresseux, il ne montre que ce qui est filtré et visible.
- **Candidat d'écriture DEVENU le scénario 20** : chaque application de l'App
  Finder porte un bouton d'épinglage qui l'ajoute à un groupe de l'accueil. C'est
  une écriture de personnalisation utilisateur, réversible en dépinglant, et le
  cycle est désormais couvert sous accord explicite d'écriture (révision du
  2026-08-24). Ce scénario-ci reste, lui, en lecture seule : il filtre, il
  n'épingle pas.
- **Keywords métier manquants** : `Ouvrir L App Finder`,
  `Lire Les Sources De Catalogue`, `Filtrer L App Finder`,
  `Compter Les Applications Rendues`.

### 13. Le mode édition de l'accueil s'ouvre et se quitte sans rien changer

- **Préconditions** : accueil affiché.
- **Étapes** :
  1. Relever le nombre de groupes et le nombre de tuiles par groupe.
  2. Entrer en mode édition depuis la zone utilisateur.
  3. Constater que la barre de pied de page d'édition est rendue.
  4. Quitter le mode édition par son bouton de validation.
  5. Relever de nouveau les groupes et le nombre de tuiles par groupe.
- **Résultat attendu** : le mode édition est bien entré (la barre de pied de
  page existe) puis bien quitté (elle n'existe plus) ; les groupes et le nombre
  de tuiles de chacun sont **strictement identiques** avant et après.
- **Portée** : entrer et sortir du mode édition sans rien déplacer ne modifie
  aucune personnalisation, ce qui a été vérifié live par la comparaison
  avant/après. Ajouter, déplacer, supprimer une tuile ou un groupe sont des
  écritures et restent hors périmètre.
- **Observation à consigner** : en mode édition, le sous-titre et le libellé du
  compteur de chaque tuile deviennent visibles, ce qui n'est pas le cas en mode
  affichage. Ne pas en faire une assertion de texte (ces libellés sont traduits).
- **Keywords métier manquants** : `Entrer En Mode Edition De L Accueil`,
  `Quitter Le Mode Edition De L Accueil`, `Le Mode Edition Est Actif`.

### 14. Le menu « toutes mes applications » du titre de shell liste le catalogue

- **Préconditions** : shell rendu.
- **Étapes** :
  1. Cliquer le titre de shell.
  2. Constater l'ouverture du popover.
  3. Relever les sources listées et le nombre d'entrées rendues.
  4. Refermer.
- **Résultat attendu** : le popover est ouvert ; il propose les applications de
  la page d'accueil et une entrée par catalogue assigné ; le nombre d'entrées
  rendues correspond au volume du catalogue inventorié au scénario 4 (mesuré 67).
- **Keywords métier manquants** : `Ouvrir Le Menu Toutes Mes Applications`,
  `Compter Les Entrees Du Menu Toutes Mes Applications`.

### 15. La navigation arrière du navigateur ramène à l'écran précédent

- **Préconditions** : au moins deux applications ouvertes successivement.
- **Étapes** :
  1. Ouvrir une première application par intent, la constater.
  2. Ouvrir une seconde application par intent, la constater.
  3. Déclencher la navigation arrière du navigateur.
  4. Constater l'écran atteint.
- **Résultat attendu** : après la navigation arrière, le fragment d'URL et le
  conteneur d'application sont **ceux de la première application** ; le
  conteneur de la seconde n'est plus présent.
- **Fait structurel constaté** : un seul conteneur d'application existe à la
  fois. Passer d'une application à l'autre détruit la précédente, et la
  navigation arrière la reconstruit.
- **Keywords métier manquants** : `Revenir En Arriere Dans Le Shell`.

### 16. Un intent inexistant est refusé proprement, sans quitter l'écran courant

- **Préconditions** : une application ouverte, pour pouvoir vérifier que le
  refus ne détruit pas l'existant.
- **Étapes** :
  1. Relever le fragment courant et l'application ouverte.
  2. Demander la navigation vers un intent **fabriqué**, de forme correcte mais
     inconnu.
  3. Constater l'état du shell.
  4. Acquitter le dialogue d'erreur.
  5. Relever de nouveau le fragment et l'application ouverte.
- **Résultat attendu** : un dialogue en **état d'erreur** est ouvert ; le
  fragment d'URL n'a **pas** changé ; l'application précédemment ouverte est
  toujours là. Après acquittement, plus aucun dialogue n'est ouvert et l'état est
  identique au relevé initial.
- **Assertion locale-indépendante** : la propriété d'état du dialogue, jamais son
  titre ni son texte, qui sont traduits. L'acquittement se fait par la
  **position** du bouton dans le dialogue, pour la même raison (leçon reprise du
  parcours Work Zone, où les boutons d'une boîte de message étaient en français).
- **Variante observée à couvrir de la même façon** : un intent réellement
  présent au catalogue mais non résolvable (`ApplicationJob-show` sur la cible)
  produit **exactement le même** dialogue d'erreur. Le test ne doit donc pas
  chercher à distinguer les deux par l'écran ; c'est la préflight du scénario 5
  qui les distingue, sans navigation.
- **Keywords métier manquants** : `Demander Un Intent Inconnu`,
  `Le Shell Refuse La Navigation`, `Acquitter Le Dialogue D Erreur`.

### 17. Un fragment d'URL malformé est refusé, avec un message distinct

- **Préconditions** : une application ouverte.
- **Étapes** :
  1. Écrire dans l'URL un fragment qui n'a pas la forme d'un intent (pas de
     partie action).
  2. Constater l'état du shell.
  3. Acquitter et vérifier le retour à l'état antérieur.
- **Résultat attendu** : un dialogue en état d'erreur est ouvert ; le fragment
  revient à celui de l'application précédente ; après acquittement l'état est
  intact.
- **Différence observée avec le scénario 16** : le dialogue du fragment malformé
  ne propose PAS l'accès aux détails techniques, contrairement à celui de
  l'intent inconnu. La différence est structurelle (contenu du dialogue) et non
  textuelle ; elle est notée ici comme observation, et n'est proposée en
  assertion que si le générateur la confirme live.
- **Keywords métier manquants** : `Forcer Un Fragment Malforme`.

### 18. Aucune exception JavaScript non rattrapée sur le parcours

- **Préconditions** : parcours complet joué (accueil, deux applications, retour,
  recherche, zone utilisateur).
- **Étapes** :
  1. Collecter le diagnostic Fiori agrégé.
  2. Séparer les erreurs de page (exceptions non rattrapées) des erreurs console.
  3. Classer les erreurs console par origine.
  4. Rapporter la classification.
- **Résultat attendu** : **zéro** exception JavaScript non rattrapée. Les erreurs
  console sont classées et leur nombre par classe est stable d'un passage à
  l'autre : sur la cible observée, trois erreurs au chargement propre de
  l'accueil (fournisseur de données de tuile dynamique, recherche d'entreprise
  absente en 403, service InA absent en 404).
- **Décision de conception** : l'assertion dure porte sur les exceptions non
  rattrapées, jamais sur un comptage brut d'erreurs console. On classe, on ne
  compte pas : une erreur console attendue et documentée n'est pas un défaut,
  et un test qui compte devient rouge à la première ressource optionnelle
  absente.
- **Piège de mesure encodé** : l'exploration elle-même pollue la console. Sonder
  l'existence d'un service ushell absent produit un 404 imputé au bootstrap, et
  une tentative de connexion refusée laisse son message d'erreur dans le journal.
  La mesure de référence se prend donc sur un **chargement propre**, après
  authentification et sans sondage préalable.
- **Keywords métier manquants** : `Classer Les Erreurs Du Shell`,
  `Aucune Exception JS Non Rattrapee`.

### 19. La déconnexion demande confirmation et atterrit sur la page de sortie

- **Préconditions** : session ouverte. **Dernier scénario de la campagne.**
- **Étapes** :
  1. Ouvrir la zone utilisateur.
  2. Déclencher la déconnexion.
  3. Constater le dialogue de confirmation et sa structure.
  4. Confirmer.
  5. Constater l'écran d'arrivée.
- **Résultat attendu** : un dialogue de confirmation à **deux** boutons est
  ouvert, et il n'est **pas** en état d'erreur (ce qui le distingue
  structurellement du dialogue de refus de navigation du scénario 16) ; après
  confirmation, l'URL atteinte est celle de la page de déconnexion ICF du
  serveur, et **aucun runtime UI5 n'est présent**.
- **Assertion locale-indépendante** : le chemin de l'URL de déconnexion et
  l'absence de runtime, jamais le texte d'adieu.
- **Keywords métier manquants** : `Se Deconnecter Du Launchpad`,
  `La Session Est Fermee`.

### 20. Épingler puis dépingler une application rend l'accueil à son état initial

- **Préconditions** : shell rendu, App Finder accessible, **accord explicite
  d'écriture donné** (voir ci-dessous).
- **Portée** : c'est le **seul scénario qui écrit** de la campagne, et il écrit
  une personnalisation d'accueil de l'utilisateur, pas une donnée métier.
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
- **Deux faits mesurés live** (2026-08-24), tous deux encodés dans le page
  object : le service `LaunchPage` sert un modèle PÉRIMÉ tant qu'on est sur l'App
  Finder (le constat se prend après retour à l'accueil), et la propriété
  `selected` du bouton d'épinglage retarde d'un cycle (l'état qui fait foi est
  celui des cases du popover).
- **Terme de filtrage propre à cette cible** : les quatre tuiles de l'accueil
  couvrent déjà `EPMProduct-shop`, donc le terme du scénario 12 ne convient pas
  ici ; « Logos » ne laisse qu'une vignette (`Logo-manage`), relevé live.
- **Keywords métier manquants** : `Lire L Unique Application De L App Finder`,
  `Epingler L Application`, `Depingler L Application`,
  `Lire Les Intents Des Tuiles De L Accueil`, `Exiger L Accord D Ecriture`,
  `Retirer L Epinglage Si Present`, `Nettoyer L Epinglage Et Diagnostiquer`.

## Scénarios non validés live : décision par point

Révision du 2026-08-24 (second passage) : chaque point porte désormais un
verdict, pas un simple constat. Trois verdicts possibles, et rien d'autre :
**couvert** (un scénario existe maintenant), **refusé** (avec sa raison, la
décision est prise et ne sera pas reprise à l'identique), **reporté** (avec ce
qu'il faudrait pour le lever).

| Point | Verdict | Motif, ou ce qu'il faudrait |
|---|---|---|
| Cycle réversible « épingler puis dépingler » | **couvert** | Scénario 20, opt-in à deux tours, validé live sur cette cible |
| Approbation ou rejet d'une commande d'achat | **refusé** | Écriture métier sans compensation connue : rien ne garantit qu'on rende le système à son état, et une campagne d'exploration n'a pas à laisser une commande approuvée derrière elle |
| Envoi d'un retour utilisateur (« Give Feedback ») | **refusé** | Le composant émet une requête SORTANTE, hors du système sous test : ce n'est plus le launchpad qu'on éprouverait |
| Changement de langue ou de thème | **refusé** | Écriture de personnalisation qui invaliderait tous les relevés de libellés de la campagne, pour éprouver un réglage et non un comportement |
| Seuil de verrouillage du compte | **refusé** | Ne se mesure pas sans verrouiller le compte, et c'est le SEUL compte des deux campagnes sur un système partagé : le prix d'un chiffre serait de rendre les deux suites injouables |
| Bouton de débordement de la barre shell | **reporté** | Il faudrait une variante de largeur de fenêtre (le contrôle n'est jamais rendu en 1600 x 1000) : c'est un scénario de responsive design, à ouvrir comme tel |
| Contenu des rubriques « Recent Activities » et « Frequently Used » | **reporté** | Le panneau est couvert sur la cible 1.120 (scénario 11) ; ici il faudrait le même relevé d'ancres, et l'assertion resterait structurelle : le CONTENU dépend de l'historique de l'utilisateur |

## Points de vigilance

### Pièges de cible et d'environnement

1. **L'URL HTTP est un piège de cible, pas une commodité.** `http://…:50000/…`
   répond, mais l'ICF redirige vers le nom d'hôte virtuel `vhcala4hci`, que les
   deux conteneurs ABAP du poste annoncent. On arrive alors sur le launchpad de
   l'AUTRE système avec une perception parfaitement cohérente. Attaquer
   directement l'URL HTTPS de la cible. Vérifié ce jour : en HTTPS direct,
   aucune redirection ne se produit.
2. **Le certificat est auto-signé.** Le contexte navigateur doit être ouvert
   avec `ignoreHTTPSErrors=True`. L'orthographe `ignoreHttpsErrors` est refusée
   par la bibliothèque Browser.
3. **Le premier chargement d'un système froid est long.** Sur la session
   observée, tout est resté rapide, mais la compilation côté serveur peut
   dépasser la minute au tout premier accès. Un échec d'attente au premier appel
   n'est pas une panne : rejouer avant de conclure.

### Pièges de perception et de localisation

4. **Aucune iframe : ne pas transposer le page object Work Zone.**
   `Get Ui5 App Frame`, `Push Ui5 App Frame`, la pile de frames et les tests
   d'étanchéité de portée n'ont **pas** de sens ici. Le témoin de « quelle
   application est ouverte » est le conteneur d'application dérivé de l'intent
   (annexe).
5. **`visible` peut valoir vrai sur un contrôle qui n'est pas rendu.** Le bouton
   d'accueil de la barre shell rapporte `visible = true` dans une application
   alors qu'il n'a **aucun** nœud DOM : le shell rend le bouton de retour à sa
   place. Le témoin fiable est l'existence du nœud DOM, ce que fait déjà le
   moteur de résolution de la bibliothèque : il ne voit que les contrôles
   RENDUS. Corollaire pratique : pour revenir à l'accueil depuis une
   application, viser le bouton de retour, ou naviguer vers l'intent d'accueil ;
   viser le bouton d'accueil échoue avec un message de localisateur introuvable
   qui ressemble à une dérive alors que c'en est une autre.
6. **Le moteur ne voit que le rendu, et c'est ce qu'on veut.** Trois champs de
   recherche de dialogues d'applications détruites subsistaient dans le registre
   UI5 sans nœud DOM ; le comptage par type de contrôle en a rapporté zéro. Ne
   jamais compter au registre brut ce qu'on veut compter à l'écran.
7. **Les préfixes de vue sont générés ET incrémentés à chaque ré-entrée.** La
   même application, ouverte trois fois dans la même session, a porté les
   préfixes `__xmlview1`, `__xmlview4`, `__xmlview7`. Les SUFFIXES d'identifiant,
   eux, sont stables et parlants (`catalogTitle`, `sortBtn`, `favoriteColumn`) :
   c'est l'ancre à utiliser, jamais l'identifiant complet.
8. **L'identifiant d'une entrée de la zone utilisateur contient sa POSITION**, et
   cette position change selon qu'on est à l'accueil ou dans une application
   (l'entrée d'édition de l'accueil s'insère au milieu de la liste). Ancrer sur
   le suffixe d'action seul.
9. **Lire la propriété, pas le rendu.** Les titres de tuile se lisent sur la
   propriété d'en-tête du contrôle ; le rendu d'une tuile ajoute son sous-titre,
   son compteur et le libellé du compteur, ce qui produit un texte inexploitable
   comme localisateur.
10. **Le titre du groupe par défaut diverge entre le service et l'écran.** Le
    service retourne « Fiori Wave2 Launchpad Home », l'écran affiche « My Home ».
    Les deux sont traduits. L'ancre est l'identifiant technique du groupe.

### Pièges d'assertion

11. **Tout libellé visible est traduit** : titres de tuile, titres de groupe,
    titres de dialogue, textes de bouton, libellés de compteur, titre de page.
    La langue servie ici est l'anglais parce que l'utilisateur est en `EN` ; le
    même parcours en allemand rendrait tous ces textes autrement. Les ancres
    locale-indépendantes disponibles sont : le fragment d'URL, l'intent, les
    identifiants techniques de groupe et de catalogue, les identifiants stables
    du shell, la propriété d'état d'un dialogue, les compteurs numériques, le
    nombre de contrôles rendus, le nombre de `ShellHeadItem` rendus.
12. **Les boutons d'un dialogue se désignent par leur position**, pas par leur
    texte. Les dialogues d'erreur et de confirmation observés portent des
    identifiants générés (`__dialog0`, `__confirm0`, `__mbox-btn-0`).
13. **Ne pas compter les erreurs console : les classer.** Trois erreurs sont
    attendues au chargement propre de cet accueil, toutes tracées à un service
    non déployé ou à une tuile dont le fournisseur de données ne répond pas. La
    seule assertion dure est l'absence d'exception JavaScript non rattrapée.
14. **L'exploration pollue sa propre mesure.** Sonder des services ushell
    absents ajoute des 404, une tentative de connexion refusée ajoute son
    message. Prendre la mesure de référence sur un chargement propre.

### Pièges d'outillage

15. **`Wait For Ui5 Idle` prend un `settle` en chaîne de temps Robot**
    (`300 ms` par défaut). Passer `settle=2000` vaut **2000 secondes**, pas
    2000 ms : le keyword échoue alors au bout de son timeout en annonçant un
    calme de 15 s, ce qui se lit comme une page agitée alors qu'elle est au
    repos depuis longtemps. Écrire `settle=2 s`.
16. **Le serveur rf-mcp ne travaille pas forcément depuis la racine du dépôt** :
    l'import de resource par chemin relatif a échoué, le chemin absolu a
    fonctionné. À vérifier avant de conclure à une resource manquante.
17. **`sapfx_state` regarde les bibliothèques IMPORTÉES de la session**, pas
    celles qu'une resource embarque : importer explicitement `Browser` et
    `SapFioriLibrary` dans la session rf-mcp.

## Écarts constatés à la génération

Relevés le 2026-08-24 par sap-generator, en rejouant chaque scénario live avant
de l'écrire. Chaque écart dit ce que le plan annonce, ce qui a été observé, et
ce que la suite en fait.

1. **Zone utilisateur : 7 entrées à l'accueil et 6 dans une application**, pas
   8 et 7. L'entrée « Give Feedback » (`-EndUserFeedbackBtn`) existe bien dans
   la liste, à sa position, mais elle porte `visible = false` et n'a **aucun
   nœud DOM** : elle n'est jamais rendue sur cette cible. Le plan la comptait
   parmi les entrées permanentes. La suite n'assère aucun cardinal : elle
   compare les deux relevés et exige que l'écart accueil/application se réduise
   exactement à l'entrée d'édition. C'est le piège n°6 du plan appliqué à
   lui-même : ne jamais compter au registre ce qu'on veut compter à l'écran.

2. **Paramètres utilisateur : 5 rubriques rendues sur les 7 déclarées.**
   `userProfiling-UserSettingsEntry` et `defaultParameters-UserSettingsEntry`
   sont dans la liste maître sans être rendus. Les 5 rendus sont
   `userAccountEntry`, `themes`, `flpSettingsEntry`, `language`,
   `UserActivitiesEntry`. La suite exige une liste non vide et journalise les
   clés, sans figer le lot.

3. **Le témoin du mode édition n'est pas la barre de pied de page.**
   `sapUshellDashboardFooter` n'est jamais résolu, même en mode édition ; c'est
   `sapUshellDashboardFooterDoneBtn` qui apparaît et disparaît. Le page object
   prend le bouton comme témoin, dans les deux sens.

4. **La recherche du shell a deux comportements selon le terme.** Soumettre le
   titre EXACT d'une application (`Shop`) fait naviguer le shell **directement
   vers cette application** (`#EPMProduct-shop`), sans page de résultats. Un
   terme partiel (`Manage`) atteint bien `#Action-search`, avec la source de
   données `$$APPS$$` et le terme dans le filtre. Le scénario 8 est donc écrit
   avec un terme partiel, et le page object documente le piège.

5. **Le menu « toutes mes applications » rend la source SÉLECTIONNÉE, pas tout
   le catalogue.** Mesuré 64 entrées (le volume du premier catalogue) pour 67
   tuiles déclarées, là où le plan annonçait 67. L'assertion est devenue
   relationnelle : entrées rendues supérieures à zéro et inférieures ou égales
   au volume total du catalogue, les deux mesurés dans le même run.

6. **Les dialogues de refus des scénarios 16 et 17 sont identiques.** Le plan
   notait, comme observation à confirmer, que le dialogue du fragment malformé
   n'offrirait pas l'accès aux détails techniques. Mesuré live, les deux portent
   `state = Error` et les **mêmes trois boutons** rendus (positions 0, 1, 2).
   L'assertion n'a donc pas été écrite, conformément à la réserve du plan.

7. **Le sélecteur de langue de la page de connexion porte 3 options**, dont une
   VIDE en tête : les 2 langues du plan sont les 2 valeurs non vides. Le
   mot-clé de lecture filtre l'option vide.

8. **Les identifiants de catalogue portent un préfixe.** Le service retourne
   `X-SAP-UI2-CATALOGPAGE:SAP_BASIS_TCR_T`, là où le plan cite le nom nu. Aucune
   assertion ne porte sur ces identifiants, seulement sur leur présence.

9. **`SearchableContent` n'est pas le seul absent, et un dialogue fermé reste
   rendu.** Constat qui a fait bouger la bibliothèque plutôt que la suite (voir
   ci-dessous) : après acquittement, le dialogue « à propos » garde son nœud
   DOM, donc `Get Ui5 Match Count` en rapporte encore 1. Ni un comptage ni une
   résolution ne distinguent ouvert de fermé.

10. **Volumétrie de l'accueil** : 192 puis 200 contrôles selon le run, contre
    184 dans le plan. C'est bien pourquoi le plan demandait un seuil et non une
    égalité ; la suite exige plus de 150.

### Second passage du 2026-08-24 (lot d'achèvement)

- **Le plancher de contrôles de l'accueil était une assertion, ce devait être
  une ATTENTE.** Mesuré sur la cible jumelle : 84 contrôles relevés juste après
  le retour au repos, là où le même écran en porte de 134 à 169 une seconde plus
  tard. Le message d'échec disait « le shell n'a pas fini de se construire », et
  il avait raison : une mesure prise une fois ne peut pas trancher entre un shell
  pauvre et un shell en cours de construction. Les deux suites attendent
  désormais que le plancher soit atteint (`Attendre Que Le Shell Soit
  Construit`), et n'échouent que s'il ne l'est jamais. Le plancher lui-même est
  inchangé.
- **La touche d'échappement ne referme pas le popover de la zone utilisateur de
  façon fiable.** Elle a fonctionné au premier passage sur cette cible et a
  échoué au second, sur le même écran, après vingt secondes d'attente d'une
  fermeture qui ne venait pas : elle dépend de l'endroit où se trouve le focus.
  La BASCULE (un second clic sur le bouton d'ouverture) referme sur les deux
  releases, vérifié live sur chacune, et devient donc la stratégie par défaut du
  page object. L'échappement reste disponible sous son nom.

### Capacités ajoutées à la bibliothèque (convention 12)

Trois manques de `SapFioriLibrary` ont été fermés dans `src/`, avec leurs tests
hors navigateur, plutôt que contournés par du JavaScript dans le page object :

- `Get Ui5 Ids` : la bibliothèque savait compter les correspondances et lire
  leurs propriétés, jamais dire LESQUELLES avaient matché, alors que l'ancre
  documentée d'un shell est le suffixe d'identifiant.
- `Get Ui5 Open Popups` : le pendant Fiori de `Get Open Windows` (ECC), seule
  lecture qui distingue un popup ouvert d'un popup simplement rendu.
- `Click Ui5 Dialog Button` : acquitter un dialogue par la POSITION de son
  bouton. Le mot-clé métier existant vise le bouton par son libellé, donc par
  un texte traduit, ce que deux campagnes live ont payé dans deux langues.

## Annexe : localisateurs et intents relevés, pour la couche page object

Rien de ce qui suit n'a sa place dans une suite (convention 1). Tout doit vivre
dans un page object, par exemple `resources/page_objects/abap_flp_shell.resource`
pour le shell et un fichier par application pour ce qui vit dedans.

### Page de connexion ICF (moteur `dom`, aucun runtime UI5)

| Rôle | Sélecteur relevé |
|---|---|
| Champ utilisateur | `css=input[name="sap-user"]` (id `USERNAME_FIELD-inner`) |
| Champ mot de passe | `css=input[name="sap-password"]` (id `PASSWORD_FIELD-inner`) |
| Sélecteur de langue | `css=#LANGUAGE_SELECT` |
| Bouton de connexion | `css=#LOGIN_LINK` |
| Bouton de changement de mot de passe | `css=#CHANGE_PASSWORD_LINK` |
| Bloc d'erreur de connexion | `css=#LOGIN_ERROR_BLOCK` |
| Message d'erreur (classe = ancre de TYPE) | `css=.loginMessage.sapUiError` |
| Formulaire | `css=#LOGIN_FORM` (POST vers `/sap/bc/ui2/flp`) |

### Shell FLP (moteur `role`, ancrage par suffixe d'identifiant)

| Rôle | Ancre (`idSuffix`) | Type de contrôle |
|---|---|---|
| Bouton accueil | `homeBtn` | `sap.ushell.ui.shell.ShellHeadItem` |
| Bouton retour | `backBtn` | `sap.ushell.ui.shell.ShellHeadItem` |
| Bouton de débordement | `endItemsOverflowBtn` | `sap.ushell.ui.shell.ShellHeadItem` |
| Zone utilisateur | `meAreaHeaderButton` | `sap.ushell.ui.shell.ShellHeadItem` |
| Bouton recherche | `sf` | `sap.ushell.ui.shell.ShellHeadItem` |
| Titre de shell / menu apps | `shellAppTitle` | `sap.ushell.ui.shell.ShellAppTitle` |
| Popover zone utilisateur | `sapUshellMeAreaPopover` | `sap.m.Popover` |
| Popover « All My Apps » | `sapUshellAllMyAppsPopover-popover` | `sap.m.Popover` |
| Liste des sources de « All My Apps » | `sapUshellAllMyAppsDataSourcesList` | `sap.m.List` |
| Champ de recherche du shell | `searchFieldInShell-input` | `SearchInput` |
| Bouton de recherche du shell | `searchFieldInShell-button` | `SearchButton` |
| Page du tableau de bord | `sapUshellDashboardPage` | `sap.m.Page` |
| Pied de page du mode édition | `sapUshellDashboardFooter` | `sap.m.Bar` |
| Bouton « terminé » du mode édition | `sapUshellDashboardFooterDoneBtn` | `sap.m.Button` |

### Entrées de la zone utilisateur (ancre = suffixe d'action, jamais l'index)

`-recentActivitiesBtn`, `-frequentActivitiesBtn`, `-openCatalogBtn`,
`-userSettingsBtn`, `-ActionModeBtn` (accueil seulement), `-EndUserFeedbackBtn`,
`-aboutBtn`, `-logoutBtn`.

### Dialogues

| Rôle | Ancre | Note |
|---|---|---|
| Dialogue « à propos » | `aboutContainerDialogID` | id stable |
| Dialogue des paramètres | `sapFlpUserSettings-View--userSettingsDialog` | id stable |
| Enregistrer les paramètres | `userSettingSaveButton` | **ne jamais actionner** en lecture seule |
| Annuler les paramètres | `userSettingCancelButton` | la sortie propre |
| Liste maître des paramètres | `userSettingEntryList` | 7 entrées `…-UserSettingsEntry` |
| Dialogue d'erreur de navigation | (généré) | ancrer sur `controlType=sap.m.Dialog` + propriété `state = Error` |
| Confirmation de déconnexion | (généré) | boutons par position : `__mbox-btn-0` (valider), `__mbox-btn-1` (annuler) |

### App Finder

| Rôle | Ancre | Type |
|---|---|---|
| Vue | `appFinderView` | `sap.ui.core.mvc.JSView` |
| Page | `appFinderPage` | `sap.m.Page` |
| Champ de recherche | `appFinderSearch` | `sap.m.SearchField` |
| Liste des sources de catalogue | `catalogSelect` | `sap.m.List` |
| Conteneur des tuiles de catalogue | `catalogTiles` | `CatalogsContainer` |
| Page de détail | `catalogTilesDetailedPage` | `sap.m.Page` |
| Vignette d'application | (généré) | `controlType=sap.ushell.ui.appfinder.AppBox` |
| Bouton d'épinglage | (généré) | `controlType=sap.ushell.ui.appfinder.PinButton` (**écriture**) |

### Tuiles de l'accueil

- Contrôle de tuile : `controlType=sap.m.GenericTile`, propriété `header` pour le
  titre, `subheader` pour le sous-titre, `state` pour l'état de chargement.
- Contenu numérique : `controlType=sap.m.NumericContent`, propriété `value`
  (la valeur `...` signale un compteur non résolu).
- Libellé du compteur : `controlType=sap.m.TileContent`, propriété `footer`
  (traduit, à ne pas asserter).
- Conteneur de groupe : `controlType=sap.ushell.ui.launchpad.TileContainer`
  (identifiants générés, ancrer sur l'identifiant technique du groupe via le
  service).
- Emplacement d'ajout : `controlType=sap.ushell.ui.launchpad.PlusTile`.
- Barre d'ancres de groupes : `controlType=sap.ushell.ui.launchpad.AnchorItem`.

### Témoin « quelle application est ouverte » (l'ancre centrale de ce launchpad)

Le shell construit, pour l'application courante, deux contrôles dont
l'identifiant est **dérivé de l'intent**, donc ni généré ni traduit :

- `application-<SemanticObject>-<action>` : `ApplicationContainer` ;
- `application-<SemanticObject>-<action>-content` : `ComponentContainer`.

Vérifié live : le comptage par `idSuffix=application-EPMPurchaseOrder-approve`
vaut **1** quand l'application est ouverte et **0** sur l'accueil. Le composant
correspondant, `application-<SemanticObject>-<action>-component`, apparaît et
disparaît dans le registre des composants au même rythme.

Les intents servis par le shell lui-même (`Shell-home`, `Shell-appfinder`) ne
produisent **aucun** conteneur de ce genre : c'est ce qui les distingue d'une
application.

### Intents relevés (sous-ensemble utile)

| Intent | Application | Nature |
|---|---|---|
| `Shell-home` | accueil du launchpad | page du shell |
| `Shell-appfinder` | App Finder | page du shell |
| `Action-search` | résultats de recherche | application du shell |
| `EPMProduct-shop` | Shop | application de démonstration, lecture |
| `EPMProduct-manage_st` | Manage Products (Fiori Elements) | application de démonstration |
| `EPMPurchaseOrder-approve` | Approve Purchase Orders | **application d'écriture métier**, à n'ouvrir qu'en consultation |
| `Repository-manage` | git-enabled CTS | tuile au compteur non résolu |
| `ApplicationJob-show` | (aucune) | assigné au catalogue, **non résolvable** |
| `Foo-bar` | (aucune) | intent fabriqué, contre-preuve de la préflight |

### Services ushell utilisés pour la perception

| Besoin | Service | Remarque |
|---|---|---|
| Groupes et tuiles de l'accueil | `LaunchPage` | `getGroups`, `getGroupTiles`, `getGroupId`, `getGroupTitle`, `getTileTitle` |
| Intent d'une tuile de l'accueil | contexte de liaison du contrôle `sap.ushell.ui.launchpad.Tile` | `getTileTarget` retourne `null` sur cet adaptateur ABAP |
| Catalogues et leurs tuiles | `LaunchPage` | `getCatalogs` (résultats en `progress`), `getCatalogTiles`, `getCatalogTileTargetURL` |
| Résolvabilité d'un intent | `CrossApplicationNavigation` | `isIntentSupported` sur une liste, réponse par intent |
| Identité de session | `sap.ushell.Container.getUser()` | id, langue, thème |
| Inventaire général des applications | **PAS** `SearchableContent` | absent de ce ushell (404) |
