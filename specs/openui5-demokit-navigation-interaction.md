# Navigation et interaction poussée dans le Demo Kit OpenUI5

- **Canal** : Fiori (web)
- **Système / URL** : Demo Kit public **OpenUI5 SDK**, `https://sdk.openui5.org/`.
  Application SAPUI5 mono-page à routage par hash (`#/...`), runtime SAPUI5
  **1.151.0** (relevé live le **2026-08-30**). Aucune authentification, aucune
  donnée métier, cible publique.
- **Préconditions** :
  - Accès réseau à `sdk.openui5.org`.
  - **Navigateur VISIBLE, `headless=False`** : critère explicite de cette
    campagne. Elle est faite pour être regardée pendant qu'elle s'exécute
    (menus en cascade, changement de thème, iframe d'échantillon). Le mode
    visible est donc une exigence fonctionnelle du livrable, pas un réglage de
    confort, et il doit rester paramétrable par variable pour la CI.
  - Bannière de consentement cookies TrustArc à accepter avant toute
    interaction (voir « Points de vigilance »).
  - **LECTURE SEULE.** Aucune écriture, aucun formulaire soumis. Les seuls
    réglages touchés (thème, case d'affichage) sont restaurés par un teardown
    qui s'exécute même sur échec.

Cette campagne ne redouble pas `tests/robot/fiori_smoke.robot` ni
`tests/robot/exploratory_campaign_fiori.robot` (inventaire de types de
contrôles, convergence role↔xpath, SearchField réversible simple) ni les trois
specs `openui5-demokit-*` existantes (consultation d'une fiche de doc). Elle
porte sur la **navigation** et sur l'**interaction avec des familles de
contrôles UI5 distinctes**.

## Données observées

Relevé live le **2026-08-30**, exploration pilotée par rf-mcp (Browser +
SapFioriLibrary), Chromium **non headless**, viewport 1600x950.

### Composition et volumétrie

`Get Page Composition` retourne partout `ui5_runtime=True`,
`ui5_version='1.151.0'`, `wc_hosts=0`, `webgui_elements=0`, `frameworks=[]`,
moteurs recommandés `['role', 'xpath', 'dom']`. Page mono-technologie UI5 : le
moteur `role` suffit, sauf sur la page d'un échantillon (voir iframe).

| Page | `ui5_controls` observés |
|---|---|
| Accueil `#/` | 551 |
| `#/api/sap.m.Table` (deep-link à froid) | 2800 |
| `#/entity/sap.m.Button` (liste d'échantillons) | 3286 |
| `#/entity/sap.m.Button/sample/sap.m.sample.Button` | 3323 (+ 55 dans l'iframe) |
| `#/api/sap.uxap.ObjectPageLayout` | 5015 |

Ces nombres varient d'un contrôle documenté à l'autre et d'une version du SDK à
l'autre : ils servent d'ordre de grandeur, jamais d'assertion.

### Barre de navigation : la clé technique vaut la route

Les six onglets sont des `sap.m.IconTabFilter` d'id `sdk---app--<tab>Tab`, tous
porteurs d'une propriété **`key` technique qui est exactement le nom de la route
de hash**. C'est l'ancre locale-indépendante de toute la navigation.

| Rôle | idSuffix | `key` | route de hash |
|---|---|---|---|
| Accueil | `welcomeTab` | `home` | `#/` |
| Documentation | `topicMasterTab` | `topic` | `#/topic` |
| Référence de l'API | `apiMasterTab` | `api` | `#/api` |
| Échantillons | `controlsMasterTab` | `controls` | `#/controls` |
| Applications de démo | `demoAppsTab` | `demoapps` | `#/demoapps` |
| Ressources | `resourcesTab` | `resources` | `#/resources` |

Le conteneur des onglets est `sdk---app--demoKitSubHeader`
(`sap.m.IconTabHeader`) et sa propriété **`selectedKey`** donne l'onglet actif :
`topic` mesuré sur `#/topic`, `controls` sur `#/entity/...`, `api` sur une fiche
d'API. **Deux témoins indépendants** (fragment d'URL et `selectedKey`) qui
doivent concorder.

Autres ancres d'en-tête relevées : `sdk---app--searchControl-searchField`
(`sap.m.SearchField`, recherche globale) et `sdk---app--aboutMenuButton`
(`sap.m.OverflowToolbarMenuButton`, icône `sap-icon://action-settings`, menu
Options). Le badge de version de l'accueil est un `sap.m.ObjectStatus` de texte
`Version 1.151.0` mais d'id **généré** (`__status0`) : il s'adresse par
controlType plus propriété, jamais par son id.

### Routes de hash relevées

`#/`, `#/topic`, `#/api`, `#/api/<nom.qualifié>`, `#/controls`,
`#/entity/<nom.qualifié>` (liste d'échantillons d'un contrôle),
`#/sample/<id>/preview` (exécution d'un échantillon).

**L'application réécrit certaines routes.** Demandé
`#/sample/sap.m.sample.Button/preview`, l'application a rendu
`#/entity/sap.m.Button/sample/sap.m.sample.Button`. Une assertion de deep-link
ne compare donc pas l'URL courante à l'URL demandée mot pour mot.

### Panneau maître de la Référence de l'API

Tous à ids stables sous le préfixe de vue `sdk---apiMaster--` :

| Élément | idSuffix | controlType |
|---|---|---|
| Champ de filtre | `apiMaster--searchField` | `sap.m.SearchField` |
| Déplier tout | `apiMaster--expandAllButton` | `sap.m.Button` |
| Replier tout | `apiMaster--collapseAllButton` | `sap.m.Button` |
| Inclure les éléments dépréciés | `apiMaster--includeDeprecated` | `sap.m.CheckBox` |
| Inclure les éléments expérimentaux | `apiMaster--includeExperimental` | `sap.m.CheckBox` |
| Arbre de l'API | `apiMaster--tree` | `sap.m.Tree` |

L'arbre est peuplé de `sap.ui.documentation.DemokitTreeItem`. Chaque nœud porte
`title` (le segment court, par exemple `ObjectPageLayout`) **et `target`, le nom
pleinement qualifié** (`sap.uxap.ObjectPageLayout`). `target` est la meilleure
ancre métier des nœuds.

Mesures de l'arbre (toutes volatiles, à traiter en relations) : 371 nœuds sur
une fiche `sap.m`, 372 sur `sap.m.Table`, **406 après activation de la case
« inclure les dépréciés »**, **4** sous le filtre `ObjectPageLayout` (les deux
ancêtres de namespace `sap` et `uxap`, plus `ObjectPageLayout` et
`ObjectPageLayoutMediaRange`). La hauteur rendue de l'arbre est de 12 243 px
dans un conteneur de 748 px : la quasi-totalité des nœuds sont rendus mais hors
du champ visible.

### Recherche globale et suggestions

Saisie de `Button` dans `searchControl-searchField` : un popover de suggestions
s'ouvre (`sap.m.ResponsivePopover`, id généré `__popover1-popover`, 600x570 px)
contenant `2` `sap.m.GroupHeaderListItem`, `14` `sap.m.StandardListItem` et un
`sap.m.Link` de texte `Tout (488)`.

Les 14 entrées se répartissent en 4 lignes de catégorie (libellés localisés) et
10 résultats dont les titres portent des **identifiants techniques non
traduits** : `sap.m.Button (class): ...`, `sap.m.Button (samples): ...`,
`sap.m.ButtonType (enum): ...`, `Button (property): sap.m.LinkAccessibleRole`.
Le compte 488 et le nombre d'entrées dépendent de l'index du SDK : ne rien
graver.

Le clic sur la suggestion dont le titre commence par `sap.m.Button (class)`
navigue vers `#/api/sap.m.Button`, titre de document
`sap.m.Button - API Reference - Demo Kit - OPENUI5 SDK`.

### Fiche d'API : les tables de documentation

Les tables d'une fiche ne sont **pas** des `sap.m.Table` mais des
`sap.ui.documentation.LightTable` (contrôle propre au SDK), à ids **générés**
(`__table0` à `__table7` sur `sap.m.Button`). Elles s'adressent par leur
rubrique conteneuse via `containedIn=<idSuffix de la section>`.

Sur `sap.m.Button`, 8 LightTables relevées, dont celle des propriétés
(`containedIn=controlproperties`, id `__table1`, en-têtes
`Name / Type / Default Value / Description`, 12 lignes) et celle des méthodes
(`Method / Description`, 44 lignes).

Deux voies de lecture, non interchangeables :

- **en-têtes** : `columnTitles` est une **propriété** (liste de chaînes), lue
  par `Get Ui5 Property`. Ce n'est pas une agrégation.
- **lignes** : `rows` est une **agrégation** de `sap.ui.documentation.Row`, lue
  par `Get Ui5 Aggregation Info`. Chaque ligne porte un **contexte de liaison**
  (`/ui5-metadata/properties/<n>`) dont l'objet expose les clés techniques
  `name`, `defaultValue`, `group`, `visibility`, `since`, `description`. C'est
  là que se lit le nom technique d'une propriété documentée, indépendamment de
  la langue et du rendu.

Les 12 propriétés propres documentées de `sap.m.Button` relevées ainsi :
`accessibleRole`, `activeIcon`, `ariaHasPopup`, `badgeStyle`, `enabled`,
`icon`, `iconDensityAware`, `iconFirst`, `text`, `textDirection`, `type`,
`width`. Le même contrôle, lu au registre sur un `sap.m.Button` réellement
rendu dans la page, expose **18** propriétés (les 12 précédentes plus 6
héritées de `sap.ui.core.Control` : `blocked`, `busy`, `busyIndicatorDelay`,
`busyIndicatorSize`, `visible`, et la documentation les range dans les listes
`sap.ui.documentation.BorrowedList`). **Inclusion vérifiée live : aucune
propriété documentée absente du contrôle vivant.**

Les rubriques de la fiche sont des `sap.uxap.ObjectPageSection` d'idSuffix
technique : `overview`, `constructor`, `controlproperties`, `aggregations`,
`associations`, `events`, `methods` (7 sur `sap.m.Button` et sur
`sap.m.Table`). La barre d'ancrage de l'ObjectPage est elle aussi faite
d'`IconTabFilter`, dont les `key` reprennent ces idSuffixes préfixés par la vue
générée (`__xmlview2--controlproperties`) : ancrer sur le suffixe.

### Menu Options : clés techniques et cascade de popovers

`sdk---app--aboutMenuButton` ouvre un `sap.m.Menu` dont les entrées sont des
`sap.m.MenuItem` à **id généré** mais à **`key` et `icon` techniques** :

| `key` | `icon` | rôle |
|---|---|---|
| `about` | `sap-icon://hint` | À propos |
| `appearance` | `sap-icon://palette` | Aspect (sous-menu de thèmes) |
| `sitemap` | `sap-icon://tree` | Plan du site |
| `settings` | `sap-icon://hello-world` | Langue (ouvre le dialogue) |

Le sous-menu `appearance` porte cinq entrées de clés `light`, `dark`, `hcb`,
`hcw`, `auto`. Aucune n'a `selected=True`, y compris celle du thème courant :
**la propriété `selected` d'une entrée de thème ne dit pas le thème appliqué.**

L'ouverture empile les popovers : `Get Ui5 Open Popups` rend 1 entrée après
l'ouverture du menu, **2** après l'ouverture du sous-menu (cascade).

### Dialogue des paramètres

L'entrée `settings` ouvre un `sap.m.Dialog` d'**id STABLE `GlobalSettingsDialog`**
(le seul id non généré de toute la couche popup relevée), portant un
`sap.m.Select` d'id stable **`LanguageSelect`** et deux `sap.m.Button` à ids
générés dont les `type` distinguent le rôle : position 0 `type=Emphasized`
(valider), position 1 `type=Default` (annuler). `Click Ui5 Dialog Button 1`
annule et referme, `Get Ui5 Open Popups` revient à `[]`.

### Thème

`Theming.getTheme()` valait `sap_horizon` à l'ouverture, `sap_horizon_dark`
après le choix de la clé `dark`, puis de nouveau `sap_horizon` après la clé
`light` : cycle complet réversible vérifié. La classe `sapUiTheme-<thème>` sur
`<html>` suit, mais **avec retard** (voir « Points de vigilance »).

### Échantillon exécuté : une iframe à id stable

Sur `#/entity/<contrôle>/sample/<id>`, l'exemple s'exécute dans une **iframe
d'id stable `sampleFrame`**, de même origine
(`https://sdk.openui5.org/resources/sap/ui/documentation/sdk/index.html?sap-ui-xx-sample-id=...`),
portant son **propre runtime UI5 1.151.0** avec 55 contrôles et le titre de
document `SAPUI5 Navigation`. `Get Page Composition` descend dedans et rend le
sélecteur `iframe[id="sampleFrame"]`.

Étanchéité de portée vérifiée : `idSuffix=apiMasterTab` compte **0** dans la
frame et **1** après `Pop Ui5 Frame`. Les ids générés de la frame repartent à
`__button0` alors que le document hôte en a déjà consommé : les deux espaces
d'ids se recouvrent, seule la portée les sépare.

### Langue servie, et son instabilité mesurée

`Get Page Languages` a rendu `{'document': 'fr-FR', 'navigator': 'fr-FR'}` sur
la première page, puis `{'document': 'en-US', 'navigator': 'fr-FR'}` sur une
page ouverte **plus tard dans le même run, dans le même contexte navigateur**.
Les libellés relevés ont suivi (« Référence de l'API » puis « API Reference »,
« Accueil » puis « Home », « Aspect » puis « Appearance »).

Un même popover a même mélangé les deux langues : ses deux en-têtes de groupe
valaient `Results by Category` et `Les 10 meilleurs résultats de Tout`.

### Erreurs console : trois familles, aucune imputable à l'application

Relevé exhaustif sur la session (aucune n'est une régression à surveiller) :

1. **Tiers hors application** : `people.wdf.sap.corp/favicon.ico?vpncheck<n>`
   en `ERR_NAME_NOT_RESOLVED` (sonde de VPN interne SAP, hôte non résoluble
   depuis l'extérieur) ; `secure.adnxs.com/getuidj` bloqué par CORS puis
   `ERR_FAILED` ; et l'unique erreur JS **non interceptée** de la session,
   `TypeError: Cannot read properties of null (reading 'addEventListener')`,
   levée par `consent.trustarc.com`.
2. **Ressources statiques 404 du SDK lui-même** :
   `resources/sap/ui/thirdparty/jqueryui/themes/base/jquery.ui.button.css` et
   `jquery.ui.theme.css`, à chaque chargement de page.
3. **Avertissements du runtime UI5** (`type: assert`) :
   `[FUTURE FATAL] Element sap.ui.core.mvc.XMLView#<vue>: encountered unknown
   setting 'style' for class sap.m.Link`, émis trois fois par vue de fiche
   d'API instanciée.

Le nombre croît avec la navigation (nouvelles occurrences à chaque fiche
ouverte) : l'assertion porte sur l'appartenance aux familles déclarées, jamais
sur un compte.

`Get Ui5 Messages` a rendu `{'messages': [], 'toasts': []}` du début à la fin :
cette application ne passe pas par le MessageManager.

## Scénarios

### 1. Le Demo Kit s'ouvre en navigateur visible et se laisse percevoir

- **Étapes** :
  1. Ouvrir un navigateur **visible** (`headless=False`, valeur par défaut de
     la suite, surchargeable par variable) et une page sur l'URL du Demo Kit.
  2. Attendre le runtime UI5.
  3. Accepter la bannière de consentement si elle est présente (moteur `dom`,
     keyword idempotent).
  4. Percevoir la composition de la page et relever la langue servie.
- **Résultat attendu** :
  - `ui5_runtime` vrai, `ui5_version` non vide et **journalisée** (relevée
    `1.151.0`, susceptible de bouger : jamais assertée en dur) ;
  - aucune frame, aucun hôte Web Component, moteurs recommandés contenant
    `role` ;
  - la bannière de consentement n'est plus présente (comptage `0`) ;
  - le nombre de contrôles rendus dépasse un plancher raisonné (`>= 100`,
     551 observés) ;
  - la langue servie est **journalisée, jamais assertée** (voir vigilance).
- **Keywords métier manquants** :
  - `Ouvrir Le Demo Kit` : navigateur visible, page sur l'URL, attente du
    runtime, acceptation du consentement, attente du repos.
  - `Accepter Le Consentement Cookies` : clique l'élément DOM de consentement
    s'il est présent, ne fait rien sinon (idempotent).
  - `Le Demo Kit Doit Etre Percu` : composition perçue, runtime présent,
    version et langue journalisées, plancher de contrôles vérifié.

### 2. Les onglets de navigation portent des clés techniques égales aux routes

- **Étapes** :
  1. Depuis l'accueil, relever la clé de chaque onglet de navigation.
  2. Ouvrir successivement deux onglets par leur clé technique (par exemple
     `topic` puis `api`).
  3. Après chaque ouverture, lire le fragment d'URL **et** la clé sélectionnée
     du conteneur d'onglets.
- **Résultat attendu** :
  - les clés relevées contiennent au moins `home`, `topic`, `api`, `controls` ;
  - après ouverture de l'onglet de clé `K`, le fragment d'URL commence par
    `#/K` **et** `selectedKey` du conteneur vaut `K` : les **deux témoins
    concordent**, l'un ne remplace pas l'autre ;
  - aucune assertion sur un libellé d'onglet.
- **Keywords métier manquants** :
  - `Lister Les Cles De Navigation` : rend la liste des `key` des onglets.
  - `Ouvrir La Section` (`${cle}`) : clique l'onglet portant cette clé, attend
    le repos, vérifie fragment d'URL et `selectedKey`.
  - `La Section Active Doit Etre` (`${cle}`) : les deux témoins.

### 3. La recherche globale propose des suggestions et l'une d'elles navigue

- **Étapes** :
  1. Depuis l'accueil, saisir un terme technique dans le champ de recherche
     global (par exemple le nom court d'un contrôle).
  2. Constater l'ouverture du popover de suggestions.
  3. Lire les en-têtes de groupe et les titres des entrées, dans la portée du
     popover.
  4. Cliquer l'entrée dont le titre correspond à la fiche de classe du contrôle
     cherché (ancrage par expression régulière, voir vigilance).
  5. Attendre le repos et lire l'URL et le titre du document.
- **Résultat attendu** :
  - un popover est ouvert (constaté sur la **pile de popups du runtime**, pas
    sur la présence des entrées) ;
  - il contient au moins un en-tête de groupe et plus d'entrées que de
    catégories (`> 4` ; 2 en-têtes et 14 entrées observés) ;
  - au moins un titre d'entrée **contient le nom qualifié technique** du
    contrôle cherché (assertion locale-indépendante) ;
  - après le clic, le fragment d'URL vaut `#/api/<nom.qualifié>` et le titre du
    document commence par `<nom.qualifié> - API Reference` ;
  - aucune assertion sur le compte total annoncé par le lien de repli
    (`Tout (488)` observé, volatile).
- **Keywords métier manquants** :
  - `Rechercher Dans Le Demo Kit` (`${terme}`) : saisit le terme, constate
    l'ouverture du popover de suggestions, rend son identifiant de portée.
  - `Les Suggestions Doivent Proposer` (`${nom_qualifie}`) : au moins une
    entrée dont le titre porte l'identifiant technique.
  - `Ouvrir La Suggestion De Classe` (`${nom_qualifie}`) : clique l'entrée de
    fiche de classe, attend le repos, vérifie l'URL et le titre.

### 4. Un deep-link direct restitue l'état sans passer par l'accueil

- **Étapes** :
  1. Ouvrir une **page neuve** directement sur une URL profonde de fiche d'API
     (`#/api/<nom.qualifié>`), sans jamais afficher l'accueil.
  2. Attendre le runtime puis le repos.
  3. Percevoir : fragment d'URL, titre du document, clé de section active,
     présence de l'arbre latéral et des rubriques de la fiche.
- **Résultat attendu** :
  - le titre du document commence par `<nom.qualifié> - API Reference` ;
  - la clé de section active vaut `api` **bien que l'accueil n'ait jamais été
    affiché** : c'est le coeur du scénario ;
  - l'arbre latéral est peuplé (`> 0` nœuds) et déplié jusqu'à l'entité visée
    (le nœud de `target` égal au nom qualifié existe) ;
  - la fiche porte au moins une rubrique de documentation ;
  - le fragment d'URL **contient** le nom qualifié, sans comparaison mot pour
    mot avec l'URL demandée (l'application peut réécrire la route).
- **Keywords métier manquants** :
  - `Ouvrir Directement La Fiche D Api` (`${nom_qualifie}`) : page neuve sur
    l'URL profonde, attente du runtime et du repos.
  - `L Etat Doit Etre Restitue Depuis Le Lien Profond` (`${nom_qualifie}`) :
    les cinq constats ci-dessus en un verdict.

### 5. Le retour arrière du navigateur remonte le fil de la navigation

- **Étapes** :
  1. Depuis une fiche d'API A, naviguer vers une fiche B (par l'arbre ou par
     une suggestion).
  2. Déclencher le retour arrière du navigateur.
  3. Percevoir l'URL et le titre du document.
- **Résultat attendu** :
  - le fragment d'URL est revenu sur la fiche A et le titre du document
    recommence par le nom qualifié de A ;
  - le témoin d'arrivée est le **couple URL plus titre**, jamais une attente
    réseau (voir vigilance : le retour arrière n'émet aucune requête).
- **Keywords métier manquants** :
  - `Revenir En Arriere Dans Le Demo Kit` : retour arrière puis attente d'un
    témoin de rendu, pas d'un repos réseau.
  - `La Fiche Affichee Doit Etre` (`${nom_qualifie}`) : URL et titre concordants.

### 6. L'arbre latéral se filtre, s'ancre sur le nom qualifié et navigue

- **Étapes** :
  1. Sur la Référence de l'API, compter les nœuds de l'arbre.
  2. Saisir un nom de contrôle dans le champ de filtre du panneau maître.
  3. Recompter les nœuds et relever les noms qualifiés restants.
  4. Cliquer le nœud dont le nom qualifié correspond **exactement** au contrôle
     visé (ancrage exact obligatoire, voir vigilance).
  5. Attendre le repos, lire l'URL.
  6. Vider le filtre et recompter.
- **Résultat attendu** :
  - le comptage filtré est **strictement inférieur** au comptage non filtré
    (371 puis 4 observés : la relation est l'assertion, pas les nombres) ;
  - tout nœud restant est soit un ancêtre de namespace, soit porteur du terme
    filtré dans son nom qualifié ;
  - le clic mène à `#/api/<nom.qualifié complet>`, le nom complet étant reconstitué
    par l'application depuis la hiérarchie de l'arbre ;
  - après vidage du filtre, le comptage redevient strictement supérieur au
    comptage filtré (sans exiger l'égalité stricte avec la mesure initiale,
    voir vigilance).
- **Keywords métier manquants** :
  - `Compter Les Noeuds De L Arbre D Api` : nombre de nœuds rendus.
  - `Filtrer L Arbre D Api` (`${terme}`) : saisit le filtre, constate la
    réduction, rend le nouveau comptage.
  - `Ouvrir Le Noeud D Api` (`${nom_qualifie}`) : clique le nœud d'ancrage
    exact, attend le repos, vérifie l'URL.
  - `Vider Le Filtre D Arbre` : remet le filtre à vide et constate l'élargissement.

### 7. Une bascule d'affichage change l'arbre et se remet en état

- **Étapes** :
  1. Relever l'état de la case « inclure les éléments dépréciés » et le
     comptage de l'arbre.
  2. Basculer la case.
  3. Relever l'état de la case et le nouveau comptage.
  4. Rebasculer la case (également en teardown, pour le cas d'échec).
  5. Relever l'état final de la case.
- **Résultat attendu** :
  - la case passe de non cochée à cochée, puis revient à non cochée ;
  - le comptage de l'arbre **augmente strictement** quand les dépréciés sont
    inclus (371 puis 406 observés) ;
  - la remise en état est constatée sur la **propriété du contrôle**, jamais
    sur le retour du comptage à sa valeur initiale (voir vigilance : le
    comptage n'est pas revenu exactement à sa valeur d'origine).
- **Keywords métier manquants** :
  - `Lire La Bascule D Affichage` (`${idSuffix}`) : état booléen de la case.
  - `Basculer L Affichage` (`${idSuffix}`) : clique et constate l'inversion de
    la propriété.
  - `Restaurer Les Bascules D Affichage` : teardown, remet chaque case dans
    l'état relevé au setup.

### 8. La table de propriétés se lit par ses en-têtes et s'accorde avec le contrôle vivant

- **Étapes** :
  1. Ouvrir la fiche d'API d'un contrôle également rendu dans la page (par
     exemple un contrôle de bouton).
  2. Résoudre la table de la rubrique des propriétés par sa **rubrique
     conteneuse**, pas par son id.
  3. Lire ses en-têtes de colonnes (propriété), puis ses lignes (agrégation).
  4. Extraire de chaque ligne le nom technique porté par son contexte de
     liaison.
  5. Lire, au registre, l'ensemble des propriétés d'une instance réellement
     rendue du même contrôle.
  6. Confronter les deux ensembles.
- **Résultat attendu** :
  - la table est résolue en **exactement 1** correspondance ;
  - ses en-têtes contiennent les colonnes techniques de nom et de type ;
  - elle porte au moins une ligne, et chaque ligne expose un nom technique non
    vide ;
  - **invariant central** : tout nom de propriété documenté appartient à
    l'ensemble des propriétés du contrôle vivant (12 documentées incluses dans
    18 vivantes, mesuré ; l'inverse est faux, les héritées ne sont pas dans
    cette table mais dans les listes d'éléments empruntés) ;
  - aucune assertion sur le nombre de lignes ni sur les descriptions.
- **Keywords métier manquants** :
  - `Lire Les En Tetes De Table De Doc` (`${rubrique}`) : en-têtes de la
    LightTable de la rubrique.
  - `Lire Les Noms Techniques De Table De Doc` (`${rubrique}`) : noms extraits
    des contextes de liaison des lignes.
  - `Lire Les Proprietes Du Controle Vivant` (`${controlType}`) : clés de
    propriétés d'une instance rendue.
  - `La Doc Doit Etre Incluse Dans Le Controle Vivant` : verdict d'inclusion,
    échec nommant les propriétés documentées absentes.

### 9. Le menu Options ouvre une cascade de popovers, puis un dialogue annulable

- **Étapes** :
  1. Constater qu'aucun popup n'est ouvert.
  2. Ouvrir le menu Options par son bouton d'en-tête.
  3. Constater l'ouverture, et lire les clés techniques des entrées.
  4. Ouvrir le sous-menu d'aspect par sa clé technique.
  5. Constater la **profondeur** de la pile de popups et lire les clés du
     sous-menu.
  6. Ouvrir l'entrée de paramètres par sa clé technique.
  7. Constater le dialogue, lire les rôles de ses boutons.
  8. Annuler par **position**, puis constater la fermeture.
- **Résultat attendu** :
  - la pile de popups passe de 0 à 1 (menu), puis à 2 (sous-menu en cascade),
    puis à 1 dialogue, puis à 0 ;
  - l'ouverture est **toujours constatée sur la pile de popups du runtime**,
    jamais sur la présence des entrées du menu (voir vigilance) ;
  - les clés du menu contiennent `about`, `appearance`, `sitemap`, `settings` ;
    celles du sous-menu contiennent `light` et `dark` ;
  - le dialogue est celui d'id stable des paramètres globaux, il porte
    exactement 2 boutons dont les rôles sont `Emphasized` puis `Default` ;
  - après annulation, aucun popup n'est ouvert **et** le thème et la langue
    sont inchangés.
- **Keywords métier manquants** :
  - `Ouvrir Le Menu Options` : clique le bouton d'en-tête, constate
    l'ouverture sur la pile de popups.
  - `Lister Les Cles Du Menu Ouvert` : clés techniques des entrées rendues.
  - `Ouvrir L Entree De Menu` (`${cle}`) : clique par clé technique.
  - `La Pile De Popups Doit Avoir` (`${profondeur}`) : assertion de profondeur.
  - `Annuler Le Dialogue Des Parametres` : annule par position et constate la
    fermeture.

### 10. Le thème change et revient, constaté sur le thème appliqué

- **Étapes** :
  1. Relever le thème courant (setup de la suite, mémorisé pour le teardown).
  2. Ouvrir le menu Options puis le sous-menu d'aspect, choisir la clé `dark`.
  3. Attendre que le thème **appliqué** porte la nouvelle valeur.
  4. Choisir la clé correspondant au thème initial.
  5. Attendre que le thème appliqué soit revenu à la valeur du setup.
- **Résultat attendu** :
  - le thème demandé passe à une valeur sombre (`sap_horizon_dark` observé
    depuis `sap_horizon`, valeurs susceptibles de changer avec la version du
    SDK : le scénario compare avant et après, il ne grave pas les noms) ;
  - le thème appliqué finit par porter la même valeur que le thème demandé ;
  - à la fin, thème demandé et thème appliqué valent la valeur du setup ;
  - le teardown restaure le thème du setup **même si le test échoue en cours
    de cycle**.
- **Keywords métier manquants** :
  - `Lire Le Theme Demande` / `Lire Le Theme Applique` : les deux témoins,
    distincts par nature.
  - `Choisir Le Theme` (`${cle}`) : ouvre le menu, le sous-menu, clique la clé.
  - `Le Theme Applique Doit Devenir` (`${theme}`) : attente active du thème
    appliqué, jamais une lecture unique juste après le clic.
  - `Restaurer Le Theme Initial` : teardown.

### 11. L'échantillon s'exécute dans une iframe, dont la portée est étanche

- **Étapes** :
  1. Ouvrir la page d'exécution d'un échantillon d'un contrôle.
  2. Percevoir la composition de la page et lister ses iframes.
  3. Entrer dans l'iframe de l'échantillon (empilement de portée).
  4. Percevoir les cibles actionnables de l'échantillon, et vérifier qu'une
     ancre du shell n'y est **pas** résoluble.
  5. Sortir de l'iframe.
  6. Vérifier que l'ancre du shell est de nouveau résoluble.
- **Résultat attendu** :
  - exactement une iframe, d'id stable connu, de même origine ;
  - la composition descend dans la frame et y voit un runtime UI5 propre, avec
    son propre compte de contrôles (55 observés) ;
  - dans la frame, l'échantillon expose au moins un contrôle actionnable, et
    l'ancre du shell compte **0** ;
  - après dépilement, la même ancre compte **1** : la portée est étanche dans
    les deux sens ;
  - aucune assertion sur les ids générés de l'échantillon (ils se recouvrent
    avec ceux du document hôte, seule la portée les distingue).
- **Keywords métier manquants** :
  - `Ouvrir L Echantillon` (`${id_echantillon}`) : navigue, attend le repos,
    tolère la réécriture de la route.
  - `Entrer Dans L Iframe D Echantillon` / `Sortir De L Iframe D Echantillon`.
  - `La Portee De L Iframe Doit Etre Etanche` : l'ancre du shell absente
    dedans, présente dehors.

### 12. Le diagnostic classe les anomalies au lieu de les compter

- **Étapes** :
  1. En fin de parcours, relever les messages UI5 par type.
  2. Relever les erreurs console et les erreurs de page non interceptées.
  3. Trier chaque entrée dans les familles déclarées de la cible.
- **Résultat attendu** :
  - aucun message UI5 de type erreur (aucun message d'aucun type observé sur
    cette cible : elle n'utilise pas le gestionnaire de messages) ;
  - **toute** entrée console et toute erreur de page appartient à l'une des
    trois familles déclarées dans « Données observées » (tiers hors
    application, ressources statiques 404 du SDK, avertissements de dépréciation
    du runtime) ;
  - une entrée hors de ces familles fait **échouer** le scénario en la
    nommant : c'est le seul verdict utile, un comptage étant inexploitable
    puisqu'il croît avec la navigation ;
  - le rapport de diagnostic est journalisé pour le lecteur du log.
- **Keywords métier manquants** :
  - `Classer Les Anomalies De La Page` : rend un dict famille vers entrées,
    plus la liste des entrées non classées.
  - `Aucune Anomalie Hors Familles Connues` : échoue en nommant les entrées non
    classées.
  - `Journaliser Le Diagnostic Du Demo Kit` : rapport lisible dans le log.

## Points de vigilance

- **La bannière de consentement intercepte réellement les clics, et c'est
  prouvable sans provoquer d'échec.** À l'ouverture, l'élément situé au centre
  de la fenêtre est l'overlay de consentement (`trustarc-banner-overlay`), le
  bandeau étant par ailleurs un dialogue `consent_blackbar`. Le bouton
  d'acceptation est un élément **DOM** (`truste-consent-button`, 1 exemplaire,
  70x32 px) : c'est le **seul endroit de cette campagne où le moteur `dom` est
  obligatoire**, la bannière étant hors du runtime UI5 et donc absente de
  l'arbre UI5 comme de la carte des cibles. Son script tiers est aussi la
  source de l'unique erreur JS non interceptée de la session.

- **La langue servie change en cours de run, mesuré.** Sur la même cible, dans
  le même navigateur et le même contexte, la langue du document est passée de
  `fr-FR` à `en-US` entre deux pages ouvertes à quelques minutes d'intervalle,
  et les libellés ont suivi. Un même popover a même affiché un en-tête en
  anglais et un en français côte à côte. Conséquence non négociable : **aucune
  assertion, aucun localisateur sur un libellé visible**, pas même en anglais.
  Les seules chaînes exploitables sont techniques : `key` d'un onglet ou d'une
  entrée de menu, `icon`, `target` d'un nœud d'arbre, nom qualifié d'un
  contrôle, titre du document. La langue se **journalise** (`Get Page
  Languages`) pour expliquer un log, elle ne s'asserte pas.

- **La présence des entrées d'un menu ne prouve JAMAIS que le menu est
  ouvert.** Mesuré : menu refermé, une entrée du sous-menu de thème compte
  encore **1** correspondance, mais son rectangle est **nul** et l'assertion de
  visibilité échoue en le disant. Le témoin d'ouverture est la **pile de popups
  du runtime**, secondairement le rectangle non nul. Corollaire du même piège :
  le `sap.m.Menu` lui-même se déclare `rendered=False` et `visible=True`
  **pendant** que son popover est affiché, et le moteur `role` ne le résout pas
  du tout ; ses entrées ne s'atteignent que par le popover rendu, ou son
  agrégation depuis le bouton propriétaire.

- **Le `sap.m.Popover` de cette version n'a pas de propriété `open`.** Le
  réflexe hérité des shells en Web Components (constater l'ouverture sur la
  propriété `open` du popover) ne s'applique pas ici : la liste des propriétés
  relevée n'en contient aucune. La pile de popups reste le témoin.

- **Le sélecteur de langue ment sur la langue effective.** Le `Select` du
  dialogue des paramètres portait `selectedKey='ar_SA'` (la première entrée de
  la liste, par `forceSelection`) alors que l'interface était rendue en
  français. Asserter la langue sur ce contrôle produirait un test vert et faux.

- **Les entrées de thème n'indiquent pas le thème courant.** Aucune ne porte
  `selected=True`, y compris celle du thème appliqué. Le thème se lit sur le
  runtime, pas sur le menu.

- **Le thème appliqué arrive après le thème demandé, et il existe une fenêtre
  sans aucun thème.** Juste après le clic, le thème demandé portait déjà la
  nouvelle valeur alors que `<html>` **ne portait plus aucune** classe
  `sapUiTheme-*` ; la classe de la nouvelle valeur est apparue ensuite. Lire la
  classe une seule fois juste après le clic est donc une course perdue :
  attendre activement la valeur attendue.

- **L'appariement des propriétés se fait par sous-chaîne : tout nom qui est le
  préfixe d'un autre est ambigu.** Mesuré : le nœud d'arbre de titre
  `ObjectPageLayout` compte **2** correspondances (il y a aussi
  `ObjectPageLayoutMediaRange`), et son nom qualifié `sap.uxap.ObjectPageLayout`
  en compte **2** également. La forme d'ancrage exact par expression régulière
  (`/^...$/`) ramène à 1. Cela vaut pour toute la famille de noms d'API du
  Demo Kit, où les préfixes communs sont la règle.

- **Les tables de documentation ne sont pas des tables UI5 standard, et la
  lecture générique rend une liste VIDE sans échouer.** Mesuré : le sélecteur
  résout exactement 1 `sap.ui.documentation.LightTable`, et la lecture
  générique de table rend `[]`. C'est le profil « vert et faux » type, un test
  qui croit avoir lu la table. Deux voies correctes, à ne pas confondre :
  `columnTitles` est une **propriété** (lecture de propriété), `rows` est une
  **agrégation** (lecture d'agrégation), et le nom technique d'une ligne est
  dans son **contexte de liaison**, pas dans son rendu. *Écart de capacité à
  remonter* : la lecture générique de table devrait signaler qu'elle ne sait
  pas lire ce contrôle plutôt que rendre une liste vide (convention 12, à
  traiter dans la bibliothèque, pas contourné dans la campagne).

- **Le repos réseau ne témoigne pas des actions locales.** Mesuré : après
  l'ouverture des suggestions, le repos annonçait 121 782 ms de calme continu,
  et après un retour arrière 93 481 ms. Ni les suggestions (index client) ni le
  retour arrière (données déjà en cache) n'émettent de requête : l'attente rend
  la main instantanément et **ne prouve rien**. L'attente de repos garde tout
  son sens après une navigation qui charge des données (1,3 s à 3,9 s mesurés),
  mais le témoin d'une action locale est le contrôle attendu, pas le réseau. Ne
  jamais compenser par une attente fixe (convention 2).

- **L'arbre UI5 en `mode=diff` est contre-productif après une navigation de
  page.** Mesuré : arbre complet 167 803 caractères, diff après changement de
  fiche d'API **407 568 caractères**, soit 2,4 fois plus long que ce qu'il
  résume (la navigation régénère presque tous les contrôles avec de nouveaux ids
  générés, chaque ligne devenant une paire supprimée puis ajoutée). Le même
  diff après un changement **local** (vidage du filtre d'arbre) fait 13 984
  caractères, soit 12 fois moins que l'arbre complet. Le `mode=diff` est donc
  l'outil des changements locaux sur cette cible, et l'arbre complet ne doit de
  toute façon jamais entrer dans un log de suite.

- **L'application réécrit certaines routes de hash.** L'URL d'exécution d'un
  échantillon demandée en `#/sample/<id>/preview` est devenue
  `#/entity/<contrôle>/sample/<id>`. Une assertion de navigation vérifie une
  **appartenance** (le nom qualifié est dans le fragment), pas une égalité avec
  l'URL demandée.

- **Cliquer l'onglet déjà sélectionné n'est pas un geste neutre.** Depuis une
  route profonde de la section Échantillons, un clic sur l'onglet Échantillons
  déjà actif a ramené l'URL à la racine de la section (`#/controls`). C'est
  exploitable pour revenir à un état connu, mais cela interdit de traiter ce
  clic comme sans effet.

- **La réversibilité se constate sur la propriété du contrôle, pas sur une
  mesure dérivée.** Mesuré sur la bascule des éléments dépréciés : la case est
  bien revenue à son état initial, mais le comptage de l'arbre valait 371 après
  le cycle contre 372 avant (un nœud d'écart, l'état de dépliage ayant bougé).
  Un teardown qui asserterait le retour du comptage échouerait sur un système
  parfaitement restauré.

- **Les ids générés ne traversent ni les pages ni les frames.** Les entrées du
  menu Options portaient `__item10` à `__item18` sur une page et `__item16` à
  `__item24` sur une autre. Les boutons de l'échantillon dans l'iframe repartent
  à `__button0` alors que le document hôte en a déjà consommé. Tout ce qui est
  généré (`__item*`, `__button*`, `__table*`, `__popover*`, `__status*`,
  `__menu*`) est interdit d'ancrage. Restent les ids stables (`sdk---app--*`,
  `sdk---apiMaster--*`, `GlobalSettingsDialog`, `LanguageSelect`, `sampleFrame`),
  toujours adressés par leur **suffixe**, et les propriétés techniques.

- **Un contrôle au rectangle non nul n'est pas forcément à l'écran.** L'arbre de
  l'API mesure 12 243 px de haut dans un conteneur de 748 px : la quasi-totalité
  de ses nœuds sont rendus et mesurables tout en étant hors du champ visible.
  L'assertion de visibilité de la bibliothèque tranche le cas « rendu à 0x0 »
  (celui des menus fermés), pas le cas « rendu hors écran ».

- **Périmètre strictement non destructif.** Aucune écriture, aucun formulaire
  soumis, aucun bouton de validation de dialogue actionné (le dialogue des
  paramètres est ouvert, lu, puis **annulé**). Les deux seuls réglages touchés,
  le thème et la case d'affichage, sont relevés au setup et remis en état par un
  teardown de suite qui s'exécute sur toutes les branches, y compris après
  échec.

## Artefacts prévus

- **Page object** : `resources/page_objects/openui5_demokit.resource` (les
  localisateurs, les clés techniques, les familles d'anomalies connues, et les
  keywords métier listés ci-dessus). Rien de tout cela ne remonte dans la suite,
  qui ne doit contenir aucun identifiant de contrôle (convention 1).
- **Suite** : `tests/robot/ui/fiori/navigation_interaction_demokit.robot`,
  navigateur visible par défaut (`${HEADLESS}` valant `False`, surchargeable en
  ligne de commande pour la CI), `Suite Setup` relevant l'état initial
  (thème, bascules d'affichage) et `Suite Teardown` le restaurant puis fermant
  le navigateur, sur toutes les branches.
- **Capacité à remonter à la bibliothèque** (convention 12) : la lecture
  générique de table rend une liste vide sur un contrôle de table non standard
  au lieu de signaler qu'elle ne sait pas le lire. À traiter dans `src/`, pas
  contourné dans le page object.

## Écarts constatés à la génération

Relevés le **2026-08-30** par sap-generator, en rejouant chaque étape live avant
de l'écrire. Les artefacts produits sont
`resources/page_objects/openui5_demokit.resource` et
`tests/robot/ui/fiori/navigation_interaction_demokit.robot` (12 scénarios,
validés **12/12 sur deux exécutions consécutives**).

### Écarts de capacité de la bibliothèque (convention 12), CORRIGÉS le 2026-08-30

Les deux écarts ci-dessous ont été relevés à la génération, laissés ouverts le
temps d'une décision, puis **corrigés dans `src/` le jour même**. La couche
resources appelle désormais la bibliothèque et ne contourne plus rien.

1. **La lecture générique de table rendait une liste VIDE au lieu d'échouer.**
   Confirmé live sur la table des propriétés de `sap.m.Button` : le sélecteur
   résout exactement 1 `sap.ui.documentation.LightTable`, ce contrôle porte
   bien ses lignes, et `Read Ui5 Table` rendait `[]`. Une table vide et une
   table illisible devenaient indiscernables : le profil « vert et faux ».
   *Correction* : le bundle rend maintenant un CONSTAT (type du contrôle, voie
   de lecture, lignes candidates, lignes écartées) et `Read Ui5 Table` échoue
   en nommant le type, le compte de lignes et la voie de repli quand aucune
   ligne n'expose de cellules ou que le contrôle n'a ni `items` ni `rows`. Une
   table vraiment vide continue de rendre `[]`, ce qui reste un résultat
   légitime. La campagne garde la voie du registre (`columnTitles` en
   propriété, `rows` en agrégation, nom technique au contexte de liaison) :
   c'était déjà la voie correcte pour ce contrôle.
2. **Le thème DEMANDÉ du runtime n'était lisible par aucun keyword.** Le plan
   distingue thème demandé et thème appliqué ; le premier supposait
   `Theming.getTheme()`, donc du JS inline depuis la couche Robot, que la
   convention 12 interdit. *Correction* : `Get Ui5 Theme` rend les deux valeurs
   (`requested` lu sur le module `sap/ui/core/Theming` avec repli sur la
   configuration du Core hérité, `applied` extrait de la classe technique
   `sapUiTheme-*`), en lecture PURE sans injection du bundle. C'est la mesure
   qui distingue « le changement n'a pas été demandé » de « le changement est
   en cours d'application », la fenêtre transitoire mesurée au scénario 10. Le
   page object lit désormais les deux (`Lire Le Theme Applique`,
   `Lire Le Theme Demande`) au lieu de parser lui-même la classe du document.

### Divergences plan contre réalité mesurée

3. **L'arbre de l'API se compte DANS son conteneur, sinon il compte autre
   chose.** Le plan lit les nœuds par leur type. Mesuré : le comptage global
   rend **380** nœuds là où l'arbre de l'API en porte **371**, le maître de la
   Documentation restant rendu à côté avec des nœuds du même type, dont le
   `target` est une empreinte de rubrique (`99ac68a5b1c3...`) et non un nom
   qualifié. Sans portée, l'assertion « tout nœud restant porte le terme
   filtré » échouait sur des nœuds qui n'ont rien à y faire. Toutes les
   lectures d'arbre du page object sont donc portées par leur conteneur.
4. **Le filtre de l'arbre et la bascule d'affichage sont DIFFÉRÉS.** Le
   comptage lu immédiatement après la frappe valait encore 371, la réduction à
   4 arrivant ensuite ; même chose après la bascule (comptage inchangé à
   l'instant du clic). Le plan prévoyait déjà de ne pas attendre le réseau : la
   suite attend ACTIVEMENT le témoin (comptage, propriété), jamais une durée.
5. **La croissance de l'arbre quand on inclut les dépréciés dépend de la
   branche dépliée.** Le plan la donne pour acquise (371 puis 406). Mesuré sur
   une fiche de l'espace `sap.uxap` : **39 nœuds avant et 39 après**, la
   branche affichée ne portant aucune entité dépréciée. L'assertion de
   croissance stricte serait donc rouge selon le test qui a précédé. Deux
   conséquences dans la suite : le scénario ouvre lui-même la fiche dont la
   branche porte des dépréciés (mesuré 399 puis 434, croissance stricte
   vérifiée), et il ajoute l'invariant qui vaut dans TOUS les états, celui que
   le plan n'énonçait pas : inclure les dépréciés n'enlève jamais un nœud (les
   cibles d'avant sont incluses dans celles d'après).
6. **Naviguer vers la fiche DÉJÀ affichée réinitialise le titre du document,
   définitivement.** Découvert par l'échec du premier run live et reproduit
   isolément : demander l'URL courante à l'identique est une navigation de
   fragment sans changement, donc le routeur ne re-résout rien, mais le titre
   passe du titre de l'entité au titre générique de la section et n'en revient
   jamais (60 s d'attente active). Le rechargement, lui, reconstruit
   l'application et rétablit le titre. C'est le pendant, pour les liens, du
   piège que le plan a relevé sur les onglets (« cliquer l'onglet déjà
   sélectionné n'est pas un geste neutre »). Le keyword d'ouverture de fiche
   choisit donc son geste selon l'état courant, ce qui le rend indépendant du
   test qui l'a précédé : c'est la condition de la rejouabilité.
7. **La bannière de consentement arrive APRÈS le runtime UI5.** Le plan la
   décrit présente à l'ouverture. Mesuré sur un contexte neuf : le comptage
   immédiatement après le retour du runtime rend **0**, puis la bannière
   s'affiche. Un keyword qui se contente de « cliquer si présent » la manque
   donc et laisse son overlay intercepter tous les clics suivants, ce que la
   session de génération a vérifié en s'y prenant elle-même (un clic sur une
   case du panneau maître refusé pendant 10 s, l'overlay nommé dans l'erreur).
   L'acceptation attend donc son apparition dans un budget court, et tolère
   qu'elle ne vienne jamais (contexte déjà consentant).
8. **Les en-têtes des tables de documentation ne suivent pas la langue de
   l'interface.** Relevés en anglais (`Name / Type / Default Value /
   Description`) alors que toute l'interface était rendue en français, sur deux
   pages différentes. Le plan attend « les colonnes techniques de nom et de
   type » ; asserter ces chaînes reviendrait quand même à parier sur du texte.
   Le scénario 8 assure donc la STRUCTURE (au moins deux colonnes, toutes
   lues) et JOURNALISE les en-têtes, l'invariant réel portant sur les noms
   techniques extraits des contextes de liaison, eux indiscutablement
   indépendants de la langue.
9. **Une quatrième signature d'anomalie apparaît quand un échantillon est
   exécuté.** Le plan déclare trois familles, relevées sans jamais ouvrir
   d'échantillon. Le premier run complet a fait sortir deux entrées de plus
   (un 404 sur `sdk/samples/Component-preload.js` et le refus correspondant du
   système de modules UI5, dont l'origine est le noyau et qui NOMME la
   ressource dans son texte). Le classement retenu ne s'élargit pas en motif
   attrape-tout : les ressources statiques manquantes du SDK sont un
   INVENTAIRE déclaré de trois fichiers, et l'appariement porte sur le texte et
   l'origine réunis (les deux formes du même manque). Une ressource manquante
   de plus sortira en anomalie non classée et fera échouer le scénario, ce qui
   est l'effet voulu.
10. **Les bascules d'affichage n'existent que dans le panneau maître de la
    Référence de l'API.** Le plan fait relever leur état initial au Suite
    Setup, qui ouvre l'accueil : le relevé y rendait un dictionnaire vide et le
    teardown ne restaurait donc rien, en silence. Le relevé est devenu
    idempotent et tardif : le scénario qui touche ces cases le déclenche avant
    d'y toucher, et le teardown restaure ce qui a réellement été relevé.

### Note technique de génération (ne concerne pas la cible)

11. Une variable Robot référencée par `$nom` dans un `Evaluate` **n'est pas
    visible depuis la portée d'une compréhension Python** (« is used in a scope
    where it cannot be seen »), ce qui a fait échouer le Suite Setup du premier
    run alors que le dry run passait. Les cinq expressions concernées ont été
    réécrites (boucle Robot, `filter`/`map` évalués dans la portée externe, ou
    interpolation `${...}` d'une valeur littérale sûre). À savoir pour toute
    régénération : le dry run ne voit pas ce défaut.
