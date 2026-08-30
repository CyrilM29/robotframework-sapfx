# Résilience de session et deep-links d'un launchpad Work Zone (BTP)

- **Canal** : Fiori (web), cFLP **SAP Build Work Zone** hébergé sur SAP BTP,
  derrière un tenant **SAP Cloud Identity Services** (IAS).
- **Système / URL** : fournis en ligne de commande (`-v WORKZONE_SITE:…`,
  `-v WORKZONE_USER:…`, `-v "WORKZONE_PASSWORD: Secret:…"`), jamais écrits dans
  le dépôt (convention 11).
- **Exploration live** : **2026-08-26**, rf-mcp (Browser + SapFioriLibrary),
  Chromium sans interface, fenêtre 1600 x 1000. Runtime relevé : **SAPUI5
  1.151.0**.
- **Complément de** :
  [workzone-launchpad-btp-perception.md](workzone-launchpad-btp-perception.md),
  qui établit la chaîne d'authentification et l'ouverture d'application par
  intent et par tuile. Cette campagne-ci éprouve ce qui arrive **autour** :
  rechargement, accès direct, historique du navigateur, second onglet, perte de
  session.
- **Préconditions** :
  - un utilisateur du tenant, et au moins une application publiée au catalogue ;
  - l'intent de cette application est **découvert** au catalogue (service
    `SearchableContent`), jamais écrit en dur ;
  - navigateur Chromium fourni par la bibliothèque Browser.
- **Portée** : **lecture seule**. Aucune donnée métier n'est écrite. Deux
  scénarios manipulent l'état de la session du **navigateur** (un contexte
  supplémentaire, vidé de ses cookies) : ils se jouent dans un contexte
  **dédié**, jamais dans celui de la suite, et ce contexte est fermé en
  teardown. Le scénario d'expiration réelle est **opt-in** (voir scénario 9).

## Données observées

Relevé live le 2026-08-26. Chaque valeur ci-dessous a été mesurée, aucune n'est
recopiée d'une campagne antérieure.

### Chaîne d'authentification et sort du fragment d'URL

| Étape | Fait mesuré |
|---|---|
| Accès sans session, avec un fragment d'intent | redirection vers `/oauth2/authorize` sur un hôte **distinct** de celui du site, avec `code_challenge` S256 et un paramètre `state` |
| Sur la page du fournisseur d'identité | `location.hash` vaut la **chaîne vide** : le fragment n'y est plus |
| Formulaire du tenant | **une seule page** (identifiant et mot de passe ensemble), un champ de type mot de passe, champs cachés `authenticity_token`, `RelayState`, `redirect_uri` |
| Titre de la page du fournisseur | porte le nom du produit du site, pas celui du tenant |
| Après authentification | retour sur l'hôte du site, **fragment RESTAURÉ**, application ouverte |

Le fragment disparaît du document du fournisseur d'identité et **réapparaît**
après le retour. Le mécanisme n'a pas été instrumenté ; le fait, lui, est
mesuré, et c'est lui qui rend un deep-link partageable.

### Accès direct à une application (deep-link)

| Fait | Session vivante | Sans session (après authentification) |
|---|---|---|
| Fragment atteint | `#<SemanticObject>-<action>` | idem |
| Page d'accueil (`sapUshellDashboardPage`) rendue | **non (0)** | **non (0)** |
| iframe applicative | 1 | 1 |
| Contrôles UI5 du shell | **19** | **19** |
| Formulaire de connexion rencontré | 0 | 1, avant authentification |

Fait notable : l'intent **seul** suffit. Le paramètre `sap-ui-app-id-hint` que
le catalogue ajoute à sa cible est **facultatif** ; le fragment nu ouvre la même
application.

### Rechargement pendant qu'une application est ouverte

| Fait | Valeur mesurée |
|---|---|
| Fragment après rechargement | **inchangé** |
| Re-authentification | **aucune** (0 champ de mot de passe) |
| iframe applicative | reconstruite |
| Contrôles UI5 dans la frame après reconstruction | **844** |
| Identifiant de l'iframe avant rechargement | `__container11` |
| Identifiant de l'iframe après rechargement | **`__container1`** |

### Le compteur d'identifiant d'iframe, mesuré sur une seule session

| Moment | Identifiant relevé |
|---|---|
| Ouverture depuis un résultat de recherche | `__container11` |
| Après rechargement de la page | `__container1` |
| Après navigation arrière puis avant | `__container5` |
| Accès direct dans un onglet neuf | `__container1` |

Quatre valeurs pour la **même** application, dans la **même** session, plus les
quatre valeurs déjà relevées les 2026-08-23 et 2026-08-24. Le compteur repart de
1 à chaque chargement de document et grimpe avec les navigations.

### Historique du navigateur

| Geste | Fait mesuré |
|---|---|
| Navigation arrière depuis une application | l'iframe est **détruite** (0 iframe) et l'écran précédent est reconstruit |
| État restauré | complet : la page de résultats de recherche revient avec son terme (`Shopp`) et son unique résultat |
| Navigation avant | l'application est rouverte dans une **nouvelle** iframe, à un identifiant différent, même URL chargée |
| Contrôles rendus après retour arrière | 63, contre 254 sur la page de résultats fraîchement construite |

### Second onglet du même navigateur

| Fait | Valeur mesurée |
|---|---|
| Ouverture d'un onglet sur le site, avec fragment d'intent | **aucune** redirection vers le fournisseur d'identité |
| Champs de mot de passe rencontrés | 0 |
| Application ouverte | oui, sans passer par l'accueil |

La session est portée par des **cookies de contexte**, donc partagée entre les
onglets d'un même contexte de navigateur et cloisonnée entre deux contextes
distincts.

### Cookies de session (noms et domaines seulement)

| Nom | Domaine | Durée |
|---|---|---|
| `JSESSIONID` | hôte du site | session |
| `__VCAP_ID__` | hôte du site | session |
| `__VCAP_ID_META__` | hôte du site | session |
| `IDP_USER` | tenant du fournisseur d'identité | session |
| `__HOST-IDP_J_COOKIE` | tenant du fournisseur d'identité | session |
| `__HOST-XSRF_COOKIE` | tenant du fournisseur d'identité | session |

Les six sont des cookies de **session** (aucune date d'expiration future) :
il n'existe pas de jeton persistant de type « rester connecté ». C'est une
propriété structurelle assertable, et aucune valeur de cookie n'a sa place dans
un test.

### Ce que la configuration du shell déclare sur la session

Lu dans `window['sap-ushell-config']`, valeurs techniques donc assertables :

| Clé | Valeur relevée |
|---|---|
| `sessionTimeoutIntervalInMinutes` | **19** |
| `sessionTimeoutReminderInMinutes` | **3** |
| `sessionTimeoutTileStopRefreshIntervalInMinutes` | **15** |
| `sessionKeepAlive.url` | un chemin de maintien de session sur l'hôte du site |

Lecture : la session expire après **19 minutes** d'inactivité, avec un rappel
**3 minutes** avant, soit **16 minutes** d'inactivité stricte avant le premier
signe visible. C'est ce chiffre qui rend l'expiration réelle impraticable dans
une campagne courte, et c'est lui qui justifie la simulation du scénario 8.

### Perte de session simulée

Dans un contexte de navigateur **dédié**, après suppression de ses cookies puis
rechargement :

| Fait | Valeur mesurée |
|---|---|
| Hôte atteint | celui du fournisseur d'identité |
| Chemin atteint | `/oauth2/authorize` |
| Runtime UI5 | **absent** |
| Champs de mot de passe | 1 |
| Fragment | perdu |

Le trajet est identique à celui d'un accès sans session : c'est ce qui rend la
simulation représentative.

### Navigation refusée : l'écran survit, le fragment revient plus tard

| Instant | Fragment | iframe applicative | Popups ouverts |
|---|---|---|---|
| Avant la demande | `#<intent valide>` | 1, identifiant `X` | aucun |
| Pendant le dialogue de refus | **`#<intent fabriqué>`** | 1, identifiant `X` **inchangé** | 1 dialogue, état `Error`, 2 boutons |
| Après acquittement | **`#<intent valide>` restauré** | 1, identifiant `X` **inchangé** | aucun |

Le dialogue est **généré** (`__dialog0`) et **réutilisé** d'un refus à l'autre.
Ses deux boutons sont, dans l'ordre, une action de copie (type `Default`) et
l'acquittement (type **`Emphasized`**). Mesuré deux fois avec deux intents
fabriqués différents.

## Scénarios

### 1. Sans session, un accès direct passe par le fournisseur d'identité et y perd son fragment
- **Préconditions** : contexte de navigateur **neuf**, sans cookie.
- **Étapes** :
  1. Ouvrir le site avec le fragment d'intent d'une application du catalogue.
  2. Relever l'URL atteinte **avant toute frappe** : hôte, chemin, fragment.
  3. Constater qu'aucun runtime UI5 n'est présent.
  4. Constater la présence d'un champ de mot de passe.
- **Résultat attendu** : l'hôte atteint **diffère** de l'hôte du site, le chemin
  est celui du point d'autorisation, le fragment est **vide**, et aucun runtime
  UI5 n'est chargé. Sans le contrôle de l'hôte, une page de connexion locale
  rendrait ce test parfaitement vert (leçon reprise du scénario 1 de la campagne
  de perception).
- **Ce que ce scénario établit** : le fragment n'est pas transmis au serveur, ce
  qui rend le scénario 2 non trivial.
- **Keywords métier manquants** :
  - `Ouvrir Un Contexte Neuf` (contexte de navigateur isolé, à fermer en
    teardown),
  - `Ouvrir Le Site Sur Un Intent` (navigation directe, sans authentification),
  - `Lire L Adresse Atteinte` (dict `{hote, chemin, fragment}`),
  - `Aucun Runtime UI5 N Est Present`.

### 2. Après authentification, l'accès direct retrouve sa cible sans passer par l'accueil
- **Préconditions** : scénario 1 atteint, formulaire du fournisseur affiché.
- **Étapes** :
  1. S'authentifier avec le preset du tenant.
  2. Attendre le repos réel de la page.
  3. Relever l'hôte, le fragment, la présence de la page d'accueil, le nombre
     d'iframes.
- **Résultat attendu** : retour sur l'hôte du site ; le fragment est **celui
  demandé avant authentification** ; la page d'accueil du launchpad **n'est
  jamais rendue** ; exactement une iframe applicative est présente. Le contrôle
  décisif est l'absence de la page d'accueil : sans lui, un shell qui
  atterrirait sur l'accueil puis ouvrirait l'application produirait le même
  fragment final.
- **Keywords métier manquants** :
  - `La Page D Accueil Est Rendue` (prédicat sur l'ancre `sapUshellDashboardPage`),
  - `Compter Les Iframes Applicatives`.

### 3. Le rechargement ne redemande pas d'authentification et reconstruit l'application
- **Préconditions** : session vivante, application ouverte par intent, portée de
  frame **dépilée**.
- **Étapes** :
  1. Relever le fragment et l'identifiant de l'iframe.
  2. Recharger la page.
  3. Constater qu'aucun champ de mot de passe n'apparaît et que l'hôte est
     inchangé.
  4. Attendre le rendu réel du shell puis l'iframe applicative.
  5. Entrer dans l'application et compter ses contrôles.
  6. Relever le nouvel identifiant d'iframe.
- **Résultat attendu** : fragment **identique** avant et après ; zéro champ de
  mot de passe ; l'application a **reconstruit** ses contrôles (comptage
  strictement positif dans la frame, mesuré 844) ; l'identifiant d'iframe a
  **changé**.
- **Piège de mesure encodé** : le rechargement rend la main bien avant que
  l'application ait démarré. Le témoin est le premier contrôle construit **dans
  la frame**, jamais la seule présence de l'iframe.
- **Keywords métier manquants** :
  - `Recharger Le Launchpad`,
  - `Lire L Identifiant De L Iframe Applicative` (constat, jamais un
    localisateur).

### 4. L'identifiant de l'iframe applicative est un compteur, pas une ancre
- **Étapes** : collecter l'identifiant de l'iframe à quatre moments d'un même
  run (ouverture, après rechargement, après un aller-retour d'historique, dans
  un onglet neuf), puis comparer.
- **Résultat attendu** : le sélecteur retenu par la bibliothèque pour désigner
  la frame est **positionnel** et ne contient aucun des identifiants relevés ;
  **au moins deux** des identifiants collectés diffèrent ; tous sont
  journalisés. Sur la cible, quatre valeurs distinctes ont été observées dans la
  même session.
- **Ce que le scénario refuse** : ce test n'assère aucune valeur d'identifiant.
  Il assère la **variabilité**, ce qui est précisément la propriété à protéger.
- **Keywords métier manquants** : aucun au-delà du précédent.

### 5. La navigation arrière détruit l'application et restaure l'écran précédent avec son état
- **Préconditions** : un écran de shell portant un **état dans le fragment**
  (une page de résultats de recherche convient, voir
  [workzone-recherche-shell.md](workzone-recherche-shell.md)), puis une
  application ouverte depuis cet écran.
- **Étapes** :
  1. Relever le fragment de l'écran de départ et l'état qu'il porte.
  2. Ouvrir l'application, constater l'iframe.
  3. Déclencher la navigation arrière du navigateur.
  4. Attendre le repos, relever fragment, iframes et état restauré.
- **Résultat attendu** : **zéro** iframe après le retour ; le fragment est
  **exactement** celui de l'étape 1 ; l'état qu'il porte est restauré à
  l'identique. Vérifier seulement le fragment laisserait passer un écran
  reconstruit vide.
- **Piège de temporisation** : le retour arrière relance la construction de
  l'écran précédent. Le budget d'attente doit être une **variable de cible** :
  la campagne ABAP 2023 a mesuré jusqu'à 55 secondes sur un autre couple
  d'écrans.
- **Keywords métier manquants** :
  - `Revenir En Arriere Dans Le Navigateur` (avec budget d'attente en argument),
  - `Lire Le Fragment Courant`, `Lire L Etat Porte Par Le Fragment`.

### 6. La navigation avant rouvre l'application dans une nouvelle iframe
- **Étapes** : depuis l'écran restauré du scénario 5, déclencher la navigation
  avant, attendre l'iframe, relever son identifiant et l'adresse chargée.
- **Résultat attendu** : une iframe est de nouveau présente, son identifiant
  **diffère** de celui relevé avant le retour arrière, et l'adresse chargée est
  la **même**. L'application est donc reconstruite, pas remise en cache.
- **Keywords métier manquants** :
  - `Avancer Dans Le Navigateur`,
  - `Lire L Adresse Chargee Dans L Iframe` (le chemin seul, sans les paramètres
    de requête, qui portent des identifiants de contenu du site).

### 7. Un second onglet du même navigateur partage la session
- **Étapes** :
  1. Session vivante dans le premier onglet.
  2. Ouvrir un **second onglet** du même contexte sur le site, avec un fragment
     d'intent.
  3. Relever immédiatement hôte, fragment et nombre de champs de mot de passe.
  4. Attendre le repos et constater l'ouverture de l'application.
  5. Revenir au premier onglet et vérifier qu'il est toujours utilisable.
- **Résultat attendu** : aucune redirection vers le fournisseur d'identité,
  **zéro** champ de mot de passe, l'application s'ouvre, et le premier onglet
  reste fonctionnel. Le dernier contrôle interdit la lecture « le second onglet
  a volé la session ».
- **Keywords métier manquants** :
  - `Ouvrir Un Second Onglet Sur Le Site`, `Revenir Au Premier Onglet`.

### 8. La perte de session est observable en secondes, et se constate au trajet
- **Préconditions** : un contexte de navigateur **dédié**, authentifié, avec une
  application ouverte. Jamais le contexte de la suite.
- **Étapes** :
  1. Relever les **noms** et domaines des cookies du contexte, et vérifier
     qu'aucun ne porte de date d'expiration future.
  2. Vider les cookies du contexte.
  3. Recharger.
  4. Relever hôte, chemin, présence d'un runtime UI5 et d'un champ de mot de
     passe.
  5. Fermer le contexte dédié.
- **Résultat attendu** : les cookies relevés sont **tous** des cookies de
  session ; après vidage et rechargement, le navigateur est sur l'hôte du
  fournisseur d'identité, au chemin d'autorisation, **sans** runtime UI5, avec
  un champ de mot de passe. Aucune valeur de cookie n'est lue ni journalisée.
- **Ce que ce scénario remplace, et pourquoi** : l'expiration réelle demande
  **16 minutes d'inactivité stricte** avant le premier signe (voir scénario 9).
  Vider les cookies produit le même trajet observable en quelques secondes, et
  c'est un test de **comportement du shell face à une session absente**, pas une
  mesure du délai.
- **Ce que le scénario NE prouve PAS, et le dit** : il ne dit rien de ce que
  fait le shell quand la session meurt **sans** rechargement, au moment d'un
  appel de service en cours de page. Une sonde a été tentée sur la page
  d'amorçage du site, qui répond 200 sans authentification et ne tranche donc
  rien ; il faudrait un point de service authentifié du shell pour le lever.
- **Keywords métier manquants** :
  - `Lire Les Cookies De Session` (noms, domaines et durées **seulement**,
    jamais les valeurs),
  - `Vider Les Cookies Du Contexte`,
  - `Le Trajet De Reauthentification Est Atteint`.

### 9. Le shell déclare ses délais de session
- **Étapes** : lire la configuration ushell et en extraire l'intervalle
  d'expiration, le délai de rappel et le point de maintien de session.
- **Résultat attendu** : les trois valeurs numériques sont présentes et
  cohérentes entre elles (le rappel est **strictement inférieur** à
  l'intervalle) ; le point de maintien de session est un chemin sur l'hôte du
  site. Les valeurs exactes sont **journalisées**, pas gravées : ce sont des
  réglages de site.
- **Variante longue, opt-in à deux tours** : attendre le rappel d'expiration
  demande une inactivité stricte supérieure à l'intervalle moins le rappel
  (mesuré 16 minutes sur la cible). Le scénario correspondant est proposé sous
  tag `long` **et** une variable d'accord explicite, sans quoi il est sauté, y
  compris dans un run complet. Sa difficulté n'est pas la durée mais
  l'inactivité : toute sonde de perception pendant l'attente risque de réarmer
  le maintien de session, ce qui reste **à vérifier** avant d'écrire ce test.
- **Keywords métier manquants** :
  - `Lire Les Delais De Session Declares` (dict `{intervalle, rappel,
    maintien}`),
  - `Exiger L Accord Pour Un Scenario Long`.

### 10. Une navigation refusée laisse l'écran intact, et le fragment n'est restauré qu'à l'acquittement
- **Préconditions** : une application ouverte.
- **Étapes** :
  1. Relever fragment et identifiant de l'iframe.
  2. Demander la navigation vers un intent **fabriqué**, de forme correcte et
     inconnu du catalogue.
  3. Constater le dialogue : son **état**, son nombre de boutons, le **type** de
     chacun.
  4. Relever le fragment **pendant** que le dialogue est ouvert.
  5. Acquitter par le bouton de type mis en avant.
  6. Relever fragment, iframe et popups ouverts.
- **Résultat attendu** : un dialogue en état **`Error`** avec **deux** boutons,
  dont **le dernier** est de type mis en avant ; pendant le dialogue, le
  fragment porte l'intent **refusé** ; après acquittement, le fragment est
  **restauré** à sa valeur de l'étape 1, l'identifiant de l'iframe est
  **inchangé** (l'application n'a jamais été détruite) et aucun popup n'est
  ouvert.
- **Piège que ce scénario encode**, et qui rendrait un test rouge sur un shell
  sain : mesurer le fragment **pendant** le dialogue et conclure que la
  navigation a eu lieu. La mesure qui fait foi est prise **après**
  acquittement.
- **Second piège, hérité de la campagne ABAP 2023 et re-constaté ici** :
  acquitter par la **position 0** copierait le message technique et laisserait
  le dialogue ouvert. L'ancre locale-indépendante est le **type** du bouton, pas
  sa position.
- **Keywords métier manquants** :
  - `Demander Un Intent Inconnu`,
  - `Le Shell Refuse La Navigation` (état du dialogue plus structure de ses
    boutons),
  - `Acquitter Le Refus De Navigation` (par type de bouton).

## Points de vigilance

- **Le fragment d'URL est le seul porteur d'état de navigation.** Il survit au
  rechargement, à l'historique et au partage entre onglets, et il est
  reconstitué après le passage par le fournisseur d'identité. C'est ce qui fait
  d'un deep-link une fonctionnalité testable, et c'est aussi pourquoi toute
  assertion de navigation doit porter sur lui plutôt que sur ce qui est à
  l'écran.
- **Le nombre de contrôles rendus dépend du CHEMIN d'arrivée**, pas seulement
  de l'écran : **139** sur un accueil chargé à neuf, **44** sur un accueil
  reconstruit après un accès direct, **19** sur un accès direct à une
  application, **254** sur une page de résultats fraîche, **63** sur la même
  page restaurée par un retour arrière. Aucun plancher ne peut être gravé ; un
  plancher est une **attente**, et l'échec de cette attente veut dire « pas
  encore construit », jamais « écran pauvre ».
- **L'iframe naît après le retour du keyword de navigation**, et l'application
  démarre après la naissance de l'iframe. Deux attentes distinctes, dans cet
  ordre.
- **Ne jamais écrire un identifiant de conteneur** : quatre valeurs différentes
  ont été mesurées pour la même application dans la même session.
- **Les valeurs de cookies ne sont jamais lues ni journalisées**, seuls leurs
  noms, domaines et durées le sont. La suppression de cookies se fait dans un
  contexte **dédié**, jamais dans celui de la suite, sous peine de faire échouer
  tous les tests suivants pour une raison qui n'est pas la leur.
- **Le paramètre `sap-ui-app-id-hint` que porte la cible du catalogue identifie
  un contenu du site** : il n'entre ni dans un test ni dans ce plan. L'intent
  nu suffit à ouvrir l'application, c'est mesuré.
- **La pile de frames doit être dépilée même après un échec** : un rechargement
  ou une navigation arrière effectués portée empilée laissent la portée pointer
  vers une frame détruite.
- **Le titre de la page du fournisseur d'identité porte le nom du produit du
  site** : il ne distingue donc pas un vrai fournisseur d'une page de connexion
  applicative. C'est l'**hôte** qui tranche, jamais le titre.

## Défauts et limites d'outillage relevés

1. **Convention 12, lacune de bibliothèque** : rien ne permet de lire le trajet
   d'authentification (hôte atteint avant frappe, présence d'un runtime,
   présence d'un formulaire) en un appel. Chaque campagne Work Zone le
   réimplémente en JavaScript de page object. Un keyword de perception
   « où suis-je et suis-je authentifié » aurait sa place dans la bibliothèque,
   au même titre que `Get Ui5 Application State`.
2. **Limite de l'exploration par rf-mcp, pas du produit** : la portée de frame
   établie par un keyword de **resource** n'est pas visible du pas suivant
   (`Get Ui5 Frame Stack` retourne une pile vide après un
   `Entrer Dans L Application`, alors qu'un `Push Ui5 App Frame` appelé
   directement persiste). C'est l'attribution des appels imbriqués aux tests
   synthétiques du serveur, déjà consignée dans les notes terrain du dépôt. En
   exécution `robot` ordinaire la portée persiste dans le test : les scénarios
   ci-dessus s'appuient donc sans réserve sur les mots-clés de resource.
3. **Limite de l'exploration par rf-mcp** : les variables déclarées par une
   resource importée ne sont pas résolues dans l'espace de noms des pas, ce qui
   fait échouer les mots-clés de page object qui en dépendent
   (`Classer Les Erreurs De La Page Du Shell` sort en « Variable non trouvée »).
   Sans effet sur une suite réelle.
4. **Observation de confort** : l'URL rapportée par l'état de session du serveur
   rf-mcp est en retard sur le fragment réel après une navigation par hash. La
   mesure qui fait foi est celle prise dans la page.

## Écarts constatés à la génération

Relevés live le **2026-08-26** en générant
`tests/robot/ui/fiori/resilience_deeplinks_workzone.robot`. Tout ce qui suit a
été mesuré sur la cible, aucune valeur n'est déduite du plan.

1. **Les clés de session ne sont pas là où le plan les nomme.** Le plan liste
   `sessionTimeoutIntervalInMinutes`, `sessionTimeoutReminderInMinutes` et
   `sessionKeepAlive.url` comme si elles vivaient sous une racine `ushell` :
   `Get Ushell Config path=ushell.sessionTimeoutIntervalInMinutes` échoue en
   listant les clés de premier niveau. Les chemins RÉELS sont
   `renderers.fiori2.componentData.config.sessionTimeout*` pour les trois délais
   et `services.Container.adapter.config.systemProperties.sessionKeepAlive` pour
   le point de maintien. Les valeurs, elles, sont bien celles du plan (19, 3, 15,
   et un chemin `HEAD` sur l'hôte du site). La suite lit les chemins réels, et
   son page object les commente comme relevés plutôt que devinés.
2. **Un cookie de session ne se reconnaît pas à une expiration ABSENTE.** La
   bibliothèque Browser encode l'expiration de session par une date de 1969
   (epoch moins un), pas par un champ vide : un prédicat « pas d'expiration »
   classe les six cookies en permanents et le scénario 8 devient vert à
   l'envers. Le prédicat retenu est celui que le plan formule déjà correctement,
   « aucune date d'expiration FUTURE », et c'est lui qui est codé.
3. **Le rappel d'expiration EXISTE, et l'expiration ne repasse PAS par le
   fournisseur d'identité.** Les deux moitiés de la variante longue du scénario
   9 ont été mesurées, sur deux passages.
   - Le rappel : à **16,8 minutes** d'inactivité stricte (absent à 10,9), un
     dialogue `sapUshellKeepAliveDialog` est OUVERT, de type `sap.m.Dialog`,
     d'état **`Warning`** et à deux boutons. Les 19 moins 3 minutes déduites de
     la configuration sont donc justes, et `Get Ui5 Open Popups` le voit.
     L'état `Warning` le distingue au passage du dialogue de refus de
     navigation du scénario 10, qui est en `Error`. La suite générée le
     reproduit sans l'avoir cherché : **16,5 minutes** au run de recette, pour
     16 déclarées, ce qui vaut aussi comme mesure de reproductibilité.
   - L'expiration : sur un passage non acquitté, le shell navigue vers
     `/logoff.html` **sur l'hôte du site** (constaté à 18,1 minutes, absent à
     12,0), sans popup subsistant et sans runtime UI5. Le plan supposait le
     même trajet que la perte de session simulée : ce n'est pas le cas.
   Le prédicat de fin d'attente est donc « un popup est ouvert » OU « le
   launchpad n'est plus servi » (aucun runtime UI5), ce qui couvre les trois
   formes possibles au lieu d'une seule. Le scénario 8, lui, est confirmé tel
   quel : le vidage de cookies mène bien à `/oauth2/authorize` sur l'hôte du
   tenant, l'expiration réelle non.
4. **La question laissée ouverte par le plan est tranchée** : sonder la page
   pendant l'attente ne réarme PAS le maintien de session. Mesuré sur un
   passage sans aucune sonde entre la 12e et la 18e minute, puis sur un passage
   sondé plusieurs fois : dans les deux cas le compte à rebours est allé à son
   terme. Une évaluation de script par le protocole de débogage n'émet aucun
   événement de souris ni de clavier, seuls événements auxquels le shell
   raccroche son compte à rebours. C'est ce qui rend la variante longue
   observable **sans `Sleep`** (convention 2) : elle sonde, elle ne dort pas.
   Corollaire encodé dans la suite : le repère de départ est posé juste après
   une frappe réelle, sinon le compte à rebours aurait démarré plus tôt que la
   mesure et l'assertion de durée deviendrait un faux rouge.
5. **L'acquittement du refus de navigation est asynchrone sur DEUX plans.** Le
   plan décrit correctement l'état d'arrivée, mais la mesure immédiate donne
   autre chose : juste après le clic sur le bouton mis en avant, le dialogue est
   encore listé OUVERT et le fragment porte encore l'intent refusé. Les deux
   constatations attendent donc, et l'attente porte d'abord sur le fragment
   restauré, ensuite sur la disparition du popup.
6. **Le sélecteur positionnel n'est rendu que par `Get Ui5 App Frame`.** Le
   scénario 4 doit viser ce keyword précisément : la composition perçue
   (`Get Page Composition`) rapporte, elle, un sélecteur qui CONTIENT
   l'identifiant généré (`iframe[id="__container4"]`). Les deux sont justes dans
   leur rôle, un seul est une ancre.
7. **Deux onglets ouverts sur le même deep-link sont indiscernables.** Même URL,
   même fragment, même structure, et `Switch Page` retourne l'identifiant de
   l'onglet QUITTÉ (sémantique de la bibliothèque Browser), pas celui rejoint.
   Le retour au premier onglet est donc constaté sur un témoin volatile déposé
   dans la page, sans quoi le scénario 7 pourrait interroger le second onglet en
   croyant vérifier le premier.
8. **Les nombres relevés diffèrent de ceux du plan, dans les deux sens**, ce qui
   confirme sa propre règle plutôt que de la contredire : 84 puis 52 contrôles
   de shell sur un accès direct (le plan mesurait 19), 485 sur une page de
   résultats restaurée par un retour arrière contre 427 sur la même page
   fraîche (le plan mesurait 63 contre 254, soit l'inverse). Aucun plancher
   n'est gravé nulle part dans la suite, et aucun de ces nombres n'entre dans
   une assertion. Identifiants d'iframe de ce run pour la même application dans
   la même session : `__container4`, `__container1`, `__container8`,
   `__container12`, plus `__container1` dans un onglet neuf.
9. **Le catalogue de la cible ne publie qu'UNE application.** L'application
   témoin, son intent et le terme de recherche qui en dérive sont donc tous les
   trois issus de cette entrée unique, découverte au catalogue par le Suite
   Setup. Rien n'est écrit dans la suite, mais le scénario 5 n'aurait aucune
   marge si le site venait à n'en publier aucune : son écran porteur d'état
   échouerait au relevé du catalogue, avec le message qui le dit.
10. **Complément au point 4 des limites d'outillage** : l'état de session du
    serveur rf-mcp est en retard non seulement sur le fragment, mais aussi sur
    l'onglet actif (`page_id` continue de nommer l'onglet quitté après un
    `Switch Page` réussi). Sans effet sur une suite réelle, mais trompeur en
    exploration.
