# Perception et navigation d'un launchpad SAP Build Work Zone (BTP)

- **Canal** : Fiori (web)
- **Système / URL** : site **SAP Build Work Zone** (cFLP) hébergé sur un compte
  **SAP BTP** de trial, protégé par un tenant **SAP Cloud Identity Services**
  (IAS). L'URL du site, l'utilisateur et le mot de passe sont fournis en ligne
  de commande (`-v WORKZONE_SITE:…`, `-v WORKZONE_USER:…`,
  `-v "WORKZONE_PASSWORD: Secret:…"`) : aucune valeur n'est écrite dans le
  dépôt (convention 11, et une URL de tenant reste une donnée privée).
  Runtime du shell relevé : **SAPUI5 1.151.0**.
- **Préconditions** :
  - un utilisateur du tenant IAS, avec au moins une application publiée au
    catalogue du site ;
  - navigateur Chromium fourni par la bibliothèque Browser (`rfbrowser init`).
- **Portée** : **lecture seule**. La campagne navigue, perçoit et classe ; elle
  n'écrit rien. Le parcours applicatif réversible fait l'objet du plan
  [workzone-panier-parcours-applicatif.md](workzone-panier-parcours-applicatif.md).

## Données observées

Relevé live le 2026-08-24, exploration pilotée par rf-mcp (Browser +
SapFioriLibrary), navigateur Chromium en mode sans interface.

**Chaîne d'authentification.** L'ouverture du site redirige vers le point
d'autorisation OAuth2 du tenant (`/oauth2/authorize`, avec `code_challenge`
S256), servi par un **hôte différent** de celui du site. Le tenant présente son
formulaire en **une seule page** (identifiant et mot de passe ensemble) là où
les fixtures du projet imitent un déroulé à deux étapes ; le preset `sap-ias`
de `Log In Via Identity Provider` s'y applique tel quel. Après authentification,
le navigateur revient sur le site, sur le hash `#Shell-home`.

**Composition du shell** (`Get Page Composition` sur la page du launchpad) :

| Élément | Valeur relevée |
|---|---|
| `ui5_runtime` / `ui5_version` | `True` / `1.151.0` |
| `ui5_controls` (accueil) | 139 |
| `wc_hosts` | 6 sur l'accueil, 7 avec une application ouverte |
| `frames` | `[]` sur l'accueil, une frame quand une application est ouverte |
| `engines` | `['role', 'xpath', 'wc', 'dom']` |

- La **barre shell est en UI5 Web Components à tags SCOPÉS** :
  `ui5-shellbar-6bfd01e3`, `ui5-shellbar-branding-…`, `ui5-shellbar-item-…`,
  `ui5-avatar-…`, `ui5-button-…`. Le moteur `wc`, écrit pour les pages sans
  runtime UI5, sert donc ici au launchpad d'avenir de SAP, sur une page qui a
  par ailleurs un runtime UI5 complet.
- Côté UI5 classique, le shell expose surtout des enveloppes :
  `sap.f.gen.ui5.webcomponents_fiori.dist.ShellBar` (le contrôle UI5 qui
  encapsule le Web Component), la vue
  `sap.ushell.components.shell.ShellBar.view.ShellBar`, et un
  `ComponentContainer` `shell-header`.
- **Snapshot ARIA du shell** : `banner "Shell Bar"` contenant les boutons
  `Back`, `Search`, `Theme Manager`, `Avatar`, le lien du site (`#Shell-home`)
  et le titre de l'application ouverte, puis `main "Content"` contenant
  l'`iframe`.

**Catalogue.** Le service ushell `SearchableContent` répond ce que
l'utilisateur connecté peut réellement ouvrir : sur la cible, **une**
application, `Shopping Cart`, d'intent `ShoppingCart-display` (le `targetURL`
ajoute un paramètre `sap-ui-app-id-hint`, à ne pas confondre avec l'intent).
La lecture par ce service, plutôt que par les tuiles rendues, distingue « ce que
l'utilisateur a le droit d'ouvrir » de « ce que cette page affiche ».

**Iframe applicative.**

- L'iframe est créée **après** le retour du keyword de navigation : une
  perception immédiate ne voit que le shell et rapporte `frames: []`.
- Son identifiant est **généré** par UI5 : `__container4` sur ce run, après
  `__container1`, `__container4` puis `__container3` relevés lors des runs du
  2026-08-23 sur la même application. Écrire cet identifiant dans un test
  revient à parier sur un compteur.
- `Get Ui5 App Frame` retourne un sélecteur **positionnel** (`iframe >> nth=0`),
  qui ne dépend d'aucun identifiant.
- Contenu de la frame : l'application est servie ici par une **URL externe**
  (application de type URL du site), le contenu réel étant la démonstration
  Shopping Cart d'OpenUI5. Composition dans la frame : `ui5_controls` **844**,
  `wc_hosts` 0, `engines` `['role', 'xpath', 'dom']`.
- **Étanchéité de portée mesurée** : le champ de recherche du shell
  (`idSuffix=ShellBarView--shellBarSearchInput`) est résolu **1 fois** sur le
  shell et **0 fois** depuis l'application ; réciproquement, les lignes de
  liste de l'application sont résolues 10 fois dans la frame et **0 fois**
  depuis le shell.

**Deux voies d'ouverture, une seule destination.** L'accueil rend **1**
`sap.m.GenericTile` pour l'application du catalogue ; la tuile s'adresse par sa
propriété `header` (`Open App`), l'intent par le hash (`Open App By Intent`).
Les deux mènent à la même URL dans la frame. À noter : la carte numérotée
(`Get Ui5 Page Map`) ne montre PAS la tuile parmi ses cibles par défaut (elle
ne retient qu'un champ de saisie sur l'accueil), il faut lui demander le type
`GenericTile` explicitement.

**Retour à l'accueil.** Naviguer sur l'intent `Shell-home` **détruit** l'iframe
applicative : plus aucune iframe dans le document, et `Get Ui5 App Frame`
échoue en nommant ce qu'il a trouvé et le remède (« Aucune iframe
d'application dans cette page (0 iframe(s) présente(s)…) … naviguer par
`Open App By Intent` ou cliquer une tuile d'abord »).

**Console du shell.** `Get Fiori Diagnostics` relève **20 erreurs console, 1
avertissement, 0 erreur de page**. Sur les 20 erreurs, **19 sont des
dépréciations émises par le shell lui-même** (`[FUTURE FATAL] [since SAPUI5
1.120] 'sap.ushell.services.Personalization' is deprecated`,
`sap.ushell.ui.launchpad.AnchorNavigationBar`, `…UsageAnalytics`…) et une est
un `Failed to load resource: 404`. Aucune n'est imputable à une application
testée : compter les erreurs console d'un launchpad ne veut rien dire, il faut
les classer.

## Scénarios

### 1. Le launchpad est servi derrière un fournisseur d'identité distinct
- **Étapes** :
  1. Ouvrir le site sans session (Suite Setup) et relever l'URL atteinte avant
     toute frappe.
  2. S'authentifier avec le preset `sap-ias`.
  3. Comparer les hôtes du site et du formulaire, puis l'URL après retour.
- **Résultat attendu** : l'URL d'avant authentification contient
  `/oauth2/authorize` et son hôte diffère de celui du site ; après
  authentification, le navigateur est revenu sur l'hôte du site. Sans le
  constat de l'hôte, une page de connexion applicative locale produirait le
  même test vert.
- **Keywords métier manquants** :
  - `Ouvrir La Session Work Zone` : ouvre, relève l'URL d'avant
    authentification (elle n'existe qu'à cet instant), s'authentifie, attend le
    rendu réel du shell.

### 2. Le shell est un cFLP réel dont la barre est en Web Components
- **Étapes** :
  1. Lire la composition de la page du shell.
  2. Compter les hôtes Web Components de la barre shell.
- **Résultat attendu** : `ui5_runtime` vrai, `ui5_controls > 0`,
  `wc_hosts > 0`, le moteur `wc` proposé, et au moins un hôte de barre shell
  résolu par le moteur Web Components. Aucune valeur exacte n'est assertée : le
  nombre de contrôles d'un shell dépend du thème, des extensions et du contenu.
- **Keywords métier manquants** :
  - `Lire La Composition De La Portee Courante`, `Compter Les Hotes Web
    Components De La Barre Shell`.
- **Défaut de bibliothèque trouvé par ce scénario, puis corrigé** : le tag réel
  est `ui5-shellbar`, en **un seul mot**. Le type court `ShellBar` était
  converti en `shell-bar` par le moteur `wc`, ce qui contient un tiret, donc
  était traité comme un tag COMPLET et n'était jamais préfixé de `ui5-` : il ne
  matchait rien (0 résultat mesuré) alors que la page portait bien la barre.
  Le moteur essaie désormais les deux orthographes qu'emploie UI5 Web
  Components, collée (`ui5-shellbar`) et à tirets (`ui5-side-navigation`) ; les
  deux cas sont verrouillés hors ligne dans `tests/robot/fiori_wc_smoke.robot`.
  Reste vrai : la correspondance se fait par PRÉFIXE, donc le comptage inclut
  les sous-composants (`ui5-shellbar-branding`, `ui5-shellbar-item`), et vaut
  comme preuve de présence, jamais comme cardinalité.

### 3. Le catalogue expose des applications adressables par intent
- **Étapes** :
  1. Interroger le service `SearchableContent` du shell.
  2. Vérifier chaque entrée.
- **Résultat attendu** : au moins une application ; chacune porte un titre non
  vide et un intent de la forme `SemanticObject-action`. Le contrôle de forme
  se fait par découpage sur le tiret, **jamais par une expression régulière à
  backslash** : Robot défigure silencieusement `\w` (leçon verrouillée par
  `tests/unit/test_se16_exploration_logic.py`).
- **Keywords métier manquants** :
  - `Inventorier Les Applications Du Catalogue` : retourne
    `[{titre, intent, cible}]`.

### 4. Chaque application du catalogue s'ouvre dans son iframe
- **Étapes** : pour chaque application déclarée, ouvrir par intent, entrer dans
  l'iframe, lire la composition, ressortir, revenir à l'accueil.
- **Résultat attendu** : chaque application matérialise une iframe dont le
  contenu porte au moins un contrôle UI5. Le balayage est **borné par le
  catalogue du jour** : une application ajoutée au site entre dans la campagne
  sans modifier le test.
- **Keywords métier manquants** :
  - `Ouvrir L Application Par Intent`, `Entrer Dans L Application`,
    `Sortir De L Application`, `Revenir A L Accueil Du Launchpad`.
  - `Attendre L Iframe De L Application` : l'iframe naît APRÈS le retour de la
    navigation, l'attente est obligatoire.

### 5. L'iframe de l'application est désignée sans son identifiant généré
- **Étapes** :
  1. Ouvrir la première application du catalogue et entrer dans sa frame.
  2. Relever les identifiants d'iframe réellement présents.
- **Résultat attendu** : le sélecteur retenu est positionnel (`iframe >> nth=`)
  et ne contient aucun des identifiants relevés. L'identifiant du run est
  journalisé : c'est la trace qui montre le compteur bouger d'un run à l'autre.
- **Keywords métier manquants** :
  - `Lire Les Identifiants D Iframe` : constat, jamais un localisateur.

### 6. La portée de frame est étanche entre le shell et l'application
- **Étapes** :
  1. Dans l'application : compter le champ de recherche du shell, lire la
     composition.
  2. De retour sur le shell : les deux mêmes mesures.
- **Résultat attendu** : 0 dans l'application, 1 sur le shell, et l'application
  porte plus de contrôles que le shell (844 contre 139 relevés). Le témoin
  choisi appartient au shell, donc le test ne dépend d'aucune application.
- **Keywords métier manquants** : `Compter Le Champ De Recherche Du Shell`.

### 7. Le retour à l'accueil détruit l'iframe et l'absence est diagnostiquée
- **Étapes** :
  1. Ouvrir une application, constater la présence d'une iframe.
  2. Revenir à l'accueil, constater qu'il n'y en a plus.
  3. Demander la frame applicative et vérifier le message d'échec.
- **Résultat attendu** : plus aucune iframe, et l'échec **nomme** ce qui a été
  trouvé et le remède, au lieu d'un « sélecteur introuvable » qui enverrait
  chercher une dérive de localisateur.
- **Keywords métier manquants** :
  - `Aucune Iframe D Application N Est Presente`.

### 8. La tuile de l'accueil ouvre la même application que l'intent
- **Étapes** : ouvrir par la tuile, relever l'URL chargée dans la frame ;
  revenir à l'accueil ; ouvrir par l'intent, relever la même mesure.
- **Résultat attendu** : les deux URL sont identiques. La comparaison porte sur
  deux mesures du **même run** : aucune URL n'est écrite dans le test.
- **Keywords métier manquants** : `Ouvrir L Application Par Sa Tuile`,
  `Compter Les Tuiles De L Accueil`.

### 9. Le shell n'émet aucune erreur non rattrapée
- **Étapes** : collecter le diagnostic Fiori agrégé et classer les erreurs
  console.
- **Résultat attendu** : **zéro erreur de page** (exception JS non rattrapée),
  et un tri exhaustif des erreurs console entre dépréciations UI5 et autres.
  Les dépréciations ne font PAS échouer le test : elles proviennent du code de
  SAP, que ce dépôt ne maintient pas (posture « constater, ne pas corriger »).
  Elles sont journalisées avec leur compte, ainsi que la première « autre »
  erreur.
- **Keywords métier manquants** :
  - `Classer Les Erreurs De La Page Du Shell` : retourne
    `{erreurs_console, depreciations, autres, erreurs_de_page, premiere_autre}`.

## Écarts constatés à la génération

Relevés le 2026-08-24 en rejouant chaque étape live avant écriture, puis en
exécutant la suite produite
(`tests/robot/ui/fiori/exploration_launchpad_workzone.robot`).

1. **« L'application porte plus de contrôles que le shell » n'est pas une
   propriété, c'est une observation.** Le plan la donnait comme critère du
   scénario 6 (844 contre 139 relevés en exploration). Le premier run live l'a
   fait échouer : la perception a lieu juste après l'entrée dans la frame, où
   l'application n'a encore construit qu'une fraction de ses contrôles. Et même
   stabilisée, rien ne garantit qu'une application embarquée soit plus riche que
   le shell qui l'héberge. Le test compare désormais les **URL** perçues dans
   les deux portées (deux documents différents) et vérifie que la portée
   applicative perçoit des contrôles ; les deux comptages restent journalisés.
2. **Entrer dans l'iframe ne veut pas dire que l'application a démarré.** Le
   scénario 4 échouait sur « s'ouvre mais ne construit aucun contrôle » : la
   frame existe et sa portée est déjà utilisable pendant que l'application boote.
   Le pilotage interactif ne pouvait pas le voir, chaque tour d'agent laissant
   passer des secondes. `Entrer Dans L Application` attend donc le premier
   contrôle construit, puis le repos réseau réel.
3. **Le compteur d'iframe bouge à l'intérieur d'une même session** :
   `__container4` puis `__container5` sur deux runs consécutifs du même jour, en
   plus des trois valeurs relevées la veille. La démonstration du scénario 5 est
   donc plus forte que prévu.
4. **Le nombre d'erreurs console n'est pas stable d'un run à l'autre** : 20
   erreurs (dont 17 dépréciations et 3 autres) sur un run, 0 sur un autre, selon
   ce que le shell a eu le temps de journaliser avant la lecture. C'est une
   raison de plus de ne rien asserter dessus : seule l'absence d'exception non
   rattrapée est un critère, et le tri reste exhaustif (la somme des classes
   égale le total).

## Points de vigilance

- **« Runtime prêt » ne veut pas dire « shell rendu ».** Sur un cFLP,
  `Wait For UI5 Ready` peut être satisfait alors que le shell n'a construit
  **aucun** contrôle : runtime chargé, rien de busy, page vide. Une fixture rend
  tout d'un coup et ne montre jamais cet état. L'ouverture de session sonde donc
  jusqu'à ce qu'un contrôle existe.
- **L'iframe naît après la navigation** : toute perception immédiate rapporte
  `frames: []`, ce qui ressemble à une cécité de la sonde.
- **Aucun identifiant de conteneur UI5 dans un test** (`__containerN`), et
  aucun préfixe de composant (`__component0---…`) : l'ancre est le suffixe
  d'id.
- **Ne jamais compter les erreurs console d'un launchpad**, seulement les
  classer : UI5 journalise ses propres dépréciations en niveau `error`.
- **La page est ouverte au niveau SUITE.** L'auto-fermeture de la bibliothèque
  Browser est au niveau TEST : une page ouverte pendant un test disparaît à sa
  fin et les tests suivants échouent sur « No page open ».
- **Un test d'échec d'authentification ne se fait pas sur un compte de
  travail** : un IAS verrouille un utilisateur après quelques tentatives. Ce
  plan ne contient donc aucun scénario d'échec de connexion ; ils vivent dans
  `tests/robot/ui/fiori/authentification_ias_live.robot`, qui utilise une
  identité inexistante et un compte dédié.
- **La pile de frames doit être dépilée même après un échec**, sinon un test
  qui échoue dans l'application laisse la portée empilée et fait échouer les
  suivants pour une raison qui n'est pas la leur.
