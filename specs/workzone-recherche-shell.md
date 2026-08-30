# Recherche du shell d'un launchpad Work Zone (BTP)

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
  dont le scénario 6 **compte** le champ de recherche du shell comme témoin
  d'étanchéité de portée, et dont le scénario 8 prouve que la tuile et l'intent
  mènent au même endroit. Cette campagne-ci **exerce** la recherche et en fait
  la **troisième** voie d'ouverture.
- **Préconditions** :
  - un utilisateur du tenant, et au moins une application publiée au catalogue ;
  - le titre et l'intent de cette application sont **découverts** au catalogue,
    jamais écrits en dur ;
  - navigateur Chromium fourni par la bibliothèque Browser.
- **Portée** : **lecture seule**. La recherche interroge, elle n'écrit pas. Le
  teardown de suite ramène le shell à son accueil.

## Données observées

Relevé live le 2026-08-26.

### Deux implémentations de recherche cohabitent, et la configuration dit laquelle est active

| Fait | Valeur relevée |
|---|---|
| `ushell.searchCEPNew.enabled` (configuration du shell) | **`false`** |
| Champ de la barre shell en Web Components | `…ShellBarView--shellBarSearch`, type `…dist.ShellBarSearch`, **jamais rendu** |
| Champ interne de ce composant | `…ShellBarView--shellBarSearchInput`, type `sap.m.Input`, **rendu mais de rectangle nul** |
| Champ réellement utilisé | `searchFieldInShell-input`, type **`sap.esh.search.ui.controls.SearchInput`** |
| Service de recherche déclaré | `Search`, parmi les 24 services de la configuration |

C'est le constat le plus important de la campagne : **le contrôle que la
campagne de perception compte n'est pas celui dans lequel l'utilisateur tape**.
Le `shellBarSearchInput` appartient à la recherche « CEP » nouvelle génération,
que la configuration déclare désactivée ; la recherche active est l'**Enterprise
Search** classique (`sap.esh.search.ui`), dont les identifiants sont exactement
ceux des launchpads ABAP (`searchFieldInShell`, `-input`, `-button`).

### Le bouton qui ouvre la recherche vit dans un shadow root

| Fait | Valeur relevée |
|---|---|
| Emplacement | shadow root du `ui5-shellbar` |
| Identifiant | **aucun** |
| Signature | hôte `ui5-button`, attribut `icon="search"` |
| Résolution par le moteur `wc` | **0** |
| Résolution par le moteur `dom`, même sélecteur CSS | **0** |
| Résolution par la bibliothèque Browser, même sélecteur CSS | **1** |

Le sélecteur qui fonctionne est un CSS de descendance ancré sur le **suffixe**
d'identifiant de la barre shell et sur l'attribut d'icône, exécuté par la
bibliothèque Browser, dont le CSS traverse les shadow roots ouverts.

### Le champ de recherche est créé au premier clic

Avant le premier clic sur le bouton, **aucun** contrôle `sap.esh.*` n'existe au
registre. Après le clic :

| Contrôle | Identifiant | Type | Largeur mesurée |
|---|---|---|---|
| Groupe | `searchFieldInShell` | `…controls.SearchFieldGroup` | 400 |
| Saisie | `searchFieldInShell-input` | `…controls.SearchInput` | 344 |
| Déclenchement | `searchFieldInShell-button` | `…controls.SearchButton` | 32 |
| Suggestions | `searchFieldInShell-input-popup` (+ `-popup-table`) | `sap.m.Popover`, `sap.m.Table` | rendu à la frappe |
| Sélecteur de source | `searchFieldInShell-select` | `…controls.SearchSelect` | non rendu |
| Annulation | `searchFieldInShell-buttonCancel` | `sap.m.Button` | non rendu |
| Menu d'actions | `searchFieldInShell-actionsMenuButton` | `sap.m.Button` | non rendu |
| Explication de requête | `searchFieldInShell-nlqExplainButton` | `sap.m.Button` | non rendu |

Le focus part sur le champ interne dès l'ouverture. Une fois créés, **ces
contrôles ne sont plus détruits** : dans une application, le groupe est replié
(rectangle nul) mais reste au registre.

### Suggestions

Terme partiel saisi, sans validation : le popover de suggestions s'ouvre et sa
table porte **1** ligne (`sap.m.ColumnListItem`) dont le texte est le titre de
l'unique application du catalogue. La recherche indexe donc **le catalogue
d'applications**.

### Page de résultats

| Fait | Valeur relevée |
|---|---|
| Fragment atteint | `#Action-search&/top=20&filter={…}` |
| Contenu décodé du filtre | source de données de type `Category`, identifiant **`$$APPS$$`**, plus le terme soumis |
| Conteneur d'application | `application-Action-search-content`, `sap.ui.core.ComponentContainer` |
| iframes | **0** |
| Vue de résultats | `searchContainerApp`, `sap.ushell.components.shell.Search.ResultsApp.view.SearchApp` |
| Contrôle composite | `eshCompGenId_<n>`, `sap.esh.search.ui.SearchCompositeControl` |
| Grille de résultats | `<composite>-ushell-search-result-app`, `sap.f.GridContainer` |
| Élément de résultat | `sap.ushell.ui.launchpad.VizInstanceCdm`, identifiant généré |
| Compteur de résultats | `<composite>-SearchCountBreadcrumbs-Label`, texte localisé |
| Contrôles rendus | **254**, contre 139 sur l'accueil |

Fait d'architecture qui corrige une lecture trop rapide de la campagne de
perception : **les applications du shell lui-même ne sont pas dans une iframe**.
La page de résultats est rendue dans le document du shell, sous un conteneur
dérivé de son intent, exactement comme sur un launchpad ABAP. Seules les
applications de **type URL** publiées par le site sont iframées.

Le compteur `_<n>` du contrôle composite est **généré**. Il est resté à zéro sur
tous les chargements observés et n'a pas incrémenté entre deux recherches d'un
même chargement, mais il reste une valeur générée : l'ancre est le **suffixe**
d'identifiant.

### Le piège du comptage global de tuiles

Sur la page de résultats, un comptage **global** de `sap.m.GenericTile` retourne
**2** pour **1** résultat :

| Contrôle | Rectangle | Ancêtre significatif |
|---|---|---|
| tuile de l'accueil | **nul** | conteneur de groupe de l'accueil |
| tuile du résultat | non nul | élément de la grille de résultats |

La tuile de l'accueil est encore rendue, invisible, sous la page de résultats.
Le comptage qui a un sens est porté par le **conteneur** de résultats, ou par le
type propre aux résultats.

### Recherche sans correspondance

| Fait | Valeur relevée |
|---|---|
| Fragment | porte le terme soumis |
| Grille de résultats | **absente** du registre |
| Écran dédié | `<composite>-searchContainerResultsView-noResultScreen`, `sap.m.VBox` |
| Illustration | `…-noResultScreen-illustratedMessage`, `sap.m.IllustratedMessage` |
| Compteur | texte localisé annonçant zéro |

L'état « sans résultat » est donc **structurellement distinct** de l'état
« résultats » : présence d'un écran dédié et **absence** de la grille. Une
recherche suivante avec un terme trouvé fait disparaître l'écran dédié et
revenir la grille, mesuré dans le même chargement.

### Ouvrir un résultat

| Fait | Valeur relevée |
|---|---|
| Cible portée par le résultat (contexte de liaison) | `#<SemanticObject>-<action>?sap-ui-app-id-hint=…` |
| Fragment atteint après le clic | le même |
| Adresse chargée dans l'iframe | identique à celle atteinte par la voie « intent » |
| Effet sur l'application déjà ouverte | rechercher depuis une application **détruit** son iframe (0 iframe sur la page de résultats) |

## Scénarios

### 1. La recherche active du shell est celle que la configuration déclare
- **Étapes** :
  1. Lire la configuration du shell et relever l'indicateur d'activation de la
     recherche nouvelle génération.
  2. Compter, sur l'accueil, le champ de recherche de la barre en Web
     Components.
  3. Mesurer sa **visibilité réelle** (rectangle), pas seulement sa présence.
- **Résultat attendu** : la configuration déclare la recherche nouvelle
  génération **désactivée** ; le champ correspondant est bien **présent au
  registre** et pourtant **de rectangle nul** ; l'implémentation active est donc
  l'autre. Le test **journalise** les deux et n'échoue que si la configuration
  et le rendu se contredisent, c'est-à-dire si un champ déclaré désactivé est
  réellement visible, ou l'inverse.
- **Ce que ce scénario corrige** : la campagne de perception compte
  `ShellBarView--shellBarSearchInput` comme « le champ de recherche du shell ».
  Ce contrôle est un témoin d'étanchéité de portée parfaitement valable, et ce
  n'est **pas** le champ dans lequel l'utilisateur tape. Le plan le dit plutôt
  que de le laisser deviner.
- **Keywords métier manquants** :
  - `Lire La Configuration De La Recherche` (indicateur d'activation),
  - `Le Champ Est Visible A L Ecran` (mesure du rectangle, voir le défaut 2
    ci-dessous).

### 2. Le champ de recherche est créé au premier clic, et son bouton vit dans un shadow root
- **Étapes** :
  1. Sur l'accueil, compter les contrôles de la recherche d'entreprise **avant**
     toute action.
  2. Compter le bouton de recherche par le moteur `wc`, puis par le moteur
     `dom`, puis par la bibliothèque Browser, avec le **même** sélecteur pour
     les deux derniers.
  3. Cliquer le bouton par la voie qui fonctionne.
  4. Recompter les contrôles de la recherche et constater que le champ de saisie
     est visible.
- **Résultat attendu** : **zéro** contrôle de recherche avant le clic, au moins
  trois après (groupe, saisie, déclenchement) ; les deux moteurs de la
  bibliothèque retournent **0** là où la bibliothèque Browser retourne **1** ;
  après le clic, le champ de saisie a un rectangle non nul. Sans le comptage
  « avant », le test ne prouverait pas la création différée et pourrait passer
  sur un champ déjà ouvert par un test précédent.
- **Convention 12** : l'écart entre les trois comptages **est** le défaut de
  bibliothèque, mesuré dans le test lui-même. Il est journalisé et ne fait pas
  échouer la campagne tant que le contournement fonctionne ; il disparaîtra
  quand les moteurs traverseront les shadow roots.
- **Keywords métier manquants** :
  - `Ouvrir La Recherche Du Shell` (clic sur le bouton du shadow root),
  - `Compter Les Controles De La Recherche`,
  - `Compter Le Bouton De Recherche Par Moteur` (retourne un dict
    `{wc, dom, navigateur}`, la mesure du défaut).

### 3. Un terme partiel propose des suggestions issues du catalogue
- **Étapes** :
  1. Inventorier le catalogue et relever le titre d'une application.
  2. Ouvrir la recherche et saisir un **préfixe** de ce titre, sans valider.
  3. Constater que le popover de suggestions est **ouvert**.
  4. Compter les suggestions et relever leur contenu.
- **Résultat attendu** : le popover est ouvert, il porte au moins une
  suggestion, et **au moins une** suggestion contient le titre relevé au
  catalogue. La comparaison porte sur deux mesures du **même** run : aucun titre
  n'est écrit dans le test, et le terme soumis est **dérivé** du titre découvert.
- **Piège encodé** : soumettre le titre **exact** d'une application peut faire
  naviguer certains shells directement vers elle, sans page de résultats
  (comportement relevé sur le FLP ABAP 1.71). Le scénario n'utilise qu'un
  **préfixe**, et il ne valide pas.
- **Keywords métier manquants** :
  - `Saisir Un Terme De Recherche` (sans valider),
  - `Les Suggestions Sont Proposees`, `Lire Les Suggestions`,
  - `Deriver Un Terme Partiel` (préfixe d'un titre découvert).

### 4. La recherche produit une page de résultats portée par le fragment
- **Étapes** :
  1. Compter les contrôles rendus sur l'accueil.
  2. Ouvrir la recherche, saisir un terme partiel, déclencher.
  3. Attendre que le conteneur d'application de la recherche soit présent.
  4. Relever le fragment atteint et en décoder le filtre.
  5. Recompter les contrôles rendus et compter les iframes.
- **Résultat attendu** : le fragment commence par l'intent de recherche du
  shell ; le filtre décodé nomme la **source de données technique** des
  applications et porte **exactement** le terme soumis ; le conteneur
  d'application dérivé de cet intent est présent **une** fois ; **aucune**
  iframe n'est créée ; le nombre de contrôles rendus est strictement supérieur à
  celui de l'accueil.
- **Piège de temporisation, hérité de la campagne ABAP 2023 et applicable ici**
  : le fragment change **avant** que l'application de résultats existe. Le
  témoin d'attente est le **conteneur d'application**, jamais le fragment seul.
- **Assertions locale-indépendantes** : l'intent, l'identifiant technique de la
  source de données, le terme soumis, des comptages. Jamais le libellé de la
  source ni le texte du compteur.
- **Keywords métier manquants** :
  - `Lancer La Recherche`,
  - `Attendre L Application De Recherche`,
  - `Lire Le Filtre De Recherche` (dict `{source, terme}` décodé du fragment).

### 5. Les résultats se comptent dans leur conteneur, jamais globalement
- **Étapes** :
  1. Sur la page de résultats, compter les tuiles **globalement**.
  2. Compter les résultats **portés par la grille de résultats**.
  3. Pour chaque tuile globale, relever si son rectangle est nul et à quel
     conteneur elle appartient.
- **Résultat attendu** : le comptage global est **strictement supérieur** au
  comptage porté (mesuré 2 contre 1), et l'écart s'explique entièrement par des
  tuiles de rectangle nul appartenant à l'accueil. Le comptage porté est celui
  qui sert dans tous les autres scénarios.
- **Pourquoi ce scénario existe** : c'est la démonstration, dans le test, que le
  comptage naïf mentirait. Sans lui, un scénario « la recherche a trouvé
  quelque chose » serait vert sur une recherche vide, la tuile de l'accueil
  suffisant à faire le compte.
- **Keywords métier manquants** :
  - `Compter Les Resultats De Recherche` (portée = la grille de résultats),
  - `Compter Toutes Les Tuiles De La Page` (le contre-exemple, journalisé),
  - `Lire Les Resultats De Recherche` (liste de dicts `{titre, cible}` lus au
    **contexte de liaison**, jamais au rendu).

### 6. Un terme sans correspondance produit un état structurellement distinct
- **Étapes** :
  1. Soumettre un terme fabriqué, sans correspondance possible.
  2. Constater l'absence de la grille de résultats.
  3. Constater la présence de l'écran dédié « sans résultat ».
  4. Soumettre de nouveau un terme trouvé.
  5. Constater le retour de la grille et la disparition de l'écran dédié.
- **Résultat attendu** : à l'étape 2 la grille de résultats **n'est pas rendue**
  et l'écran dédié **l'est** ; à l'étape 5 les deux constats sont **inversés**.
  L'aller-retour est ce qui rend le scénario non trivial : constater seulement
  « zéro résultat » serait vrai sur une page qui n'a rien construit du tout.
- **Assertions locale-indépendantes** : la présence ou l'absence de deux
  contrôles identifiés par leur **suffixe**, jamais le texte du message
  d'absence ni celui du compteur.
- **Keywords métier manquants** :
  - `L Ecran Sans Resultat Est Affiche`,
  - `La Grille De Resultats Est Affichee`.

### 7. Ouvrir un résultat mène à la même application que l'intent
- **Étapes** :
  1. Depuis la page de résultats, relever la **cible** portée par le premier
     résultat.
  2. Ouvrir ce résultat, attendre l'iframe, relever le fragment et l'adresse
     chargée dans l'iframe.
  3. Revenir à l'accueil.
  4. Ouvrir la même application par son **intent** découvert au catalogue,
     relever les deux mêmes mesures.
  5. Comparer.
- **Résultat attendu** : les deux fragments portent le **même** intent et les
  deux adresses chargées dans l'iframe sont **identiques**. La comparaison porte
  sur deux mesures du **même** run : aucune adresse n'est écrite dans le test.
  Avec le scénario 8 de la campagne de perception, qui établit l'équivalence
  tuile et intent, les **trois** voies d'ouverture sont alors éprouvées.
- **Note relevée** : la cible d'un résultat porte un paramètre d'identification
  du contenu du site, que l'intent nu ne porte pas. La comparaison se fait donc
  sur l'**intent** et sur l'**adresse chargée**, pas sur le fragment complet.
- **Keywords métier manquants** :
  - `Ouvrir Le Premier Resultat De Recherche`,
  - `Lire L Intent Porte Par Le Fragment` (partie `SemanticObject-action`, isolée
    par **découpage**, jamais par une expression régulière à contre-oblique).

### 8. Rechercher depuis une application quitte l'application
- **Étapes** :
  1. Ouvrir l'application du catalogue par son intent, constater son iframe.
  2. Sans revenir à l'accueil, ouvrir la recherche depuis la barre shell.
  3. Soumettre un terme trouvé.
  4. Compter les iframes et constater le conteneur d'application de la
     recherche.
- **Résultat attendu** : la recherche est **atteignable** depuis une application
  (le bouton est rendu dans les deux endroits) ; après soumission, **zéro**
  iframe subsiste et le conteneur de l'application de recherche est présent.
  L'application précédente a donc été quittée, pas superposée.
- **Keywords métier manquants** : aucun au-delà des précédents.

### 9. Le terme recherché survit à la navigation arrière
- **Étapes** :
  1. Soumettre un terme trouvé et relever le compte de résultats.
  2. Ouvrir le premier résultat.
  3. Déclencher la navigation arrière du navigateur.
  4. Attendre le repos, relever le terme porté par le champ de saisie, le filtre
     du fragment et le compte de résultats.
- **Résultat attendu** : le champ de saisie porte **le terme soumis à l'étape
  1**, le filtre du fragment aussi, et le compte de résultats est **identique**.
  C'est la preuve que l'état de la recherche est porté par l'URL et non par la
  mémoire de la page.
- **Piège de temporisation** : après un retour arrière, la page de résultats est
  reconstruite et se stabilise à un nombre de contrôles bien inférieur à celui
  de sa première construction (mesuré 63 contre 254). Ne rien conclure d'un
  comptage de contrôles ici ; le critère est le trio terme, filtre, compte de
  résultats.
- **Keywords métier manquants** :
  - `Lire Le Terme Du Champ De Recherche`.

## Défauts et lacunes de bibliothèque relevés (convention 12)

Les trois premiers points sont les mêmes que ceux du plan
[workzone-zone-utilisateur-parametres.md](workzone-zone-utilisateur-parametres.md),
rencontrés ici sur une autre cible et donc re-mesurés. Ils sont rappelés parce
que c'est cette campagne-ci qui en paie le prix le plus visible : sans
contournement, **la recherche du shell n'est pas ouvrable** par les moteurs de
la bibliothèque.

1. **Aucun moteur de la bibliothèque ne traverse les shadow roots.** Le bouton
   de recherche est un `ui5-button` sans identifiant, dans le shadow root du
   `ui5-shellbar`. `Get Wc Match Count tag=Button` retourne **0** ;
   `Get Dom Match Count` avec un sélecteur CSS retourne **0** ; le **même**
   sélecteur passé à `Get Element Count` de la bibliothèque Browser retourne
   **1**. Contournement retenu dans les scénarios : un sélecteur CSS de
   descendance exécuté par Browser, ancré sur le **suffixe** d'identifiant de la
   barre shell et sur l'attribut d'icône.
2. **`Ui5 Control Should Be Visible` passe sur un contrôle de rectangle nul.**
   Mesuré sur le champ de recherche replié dans une application : rectangle
   0 x 0, `offsetParent` nul, `Get Element States` de Browser rapporte `hidden`,
   et le mot-clé **passe** quand même, alors que sa documentation annonce
   « rendu, rectangle non nul ». Contre-épreuve faite : il échoue correctement
   sur un contrôle inexistant. Conséquence directe pour cette campagne : la
   visibilité du champ de recherche ne peut pas être constatée par ce mot-clé, il
   faut mesurer le rectangle, d'où le keyword métier
   `Le Champ Est Visible A L Ecran`.
3. **La forme courte des tags Web Components échoue sur la famille
   `ui5-shellbar-*`** (`tag=ShellBarItem` retourne 0, `tag=ui5-shellbar-item`
   retourne 1). Sans effet direct sur la recherche, mais c'est la même famille
   de tags.
4. **Lacune, pas défaut** : la bibliothèque n'expose aucune lecture de la
   **configuration du shell** (`sap-ushell-config`), alors que c'est la source
   la plus locale-indépendante qui soit sur un launchpad : elle déclare ce que
   le shell offre avant même qu'il le rende. Les trois campagnes Work Zone en
   ont maintenant besoin, ce qui en fait une capacité et non du vocabulaire de
   site.

## Points de vigilance

- **Deux champs de recherche cohabitent** et le mauvais est le plus facile à
  trouver. Le témoin d'étanchéité de portée de la campagne de perception
  (`ShellBarView--shellBarSearchInput`) reste valable comme témoin ; il ne doit
  jamais être rempli.
- **Rendu ne veut pas dire visible**, et ici cela va dans les deux sens : le
  champ CEP est rendu et invisible en permanence, le champ d'entreprise est
  rendu et invisible dès qu'une application est ouverte.
- **Créé une fois, jamais détruit** : les contrôles de la recherche
  n'apparaissent qu'au premier clic mais survivent ensuite à toute la session.
  Un test qui compte « zéro avant » doit donc être le **premier** à ouvrir la
  recherche dans la suite, ou remettre la page à neuf.
- **Ne jamais compter les tuiles globalement** sur la page de résultats : la
  tuile de l'accueil reste rendue, invisible, et fausse le compte.
- **Le compteur du contrôle composite est généré** (`eshCompGenId_<n>`), même
  s'il est resté à zéro sur tous les chargements observés. Toutes les ancres de
  la page de résultats sont des **suffixes** d'identifiant relatifs à ce
  composite.
- **Le fragment change avant que la page de résultats existe.** Attendre le
  conteneur d'application, jamais le fragment.
- **Le nombre de contrôles rendus dépend du chemin d'arrivée** : 254 sur une
  page de résultats fraîche, 63 sur la même page restaurée par un retour
  arrière, 139 sur l'accueil. Aucun plancher gravé.
- **Ne pas soumettre le titre exact d'une application** : c'est un libellé
  traduit, et sur certains shells il déclenche une navigation directe sans page
  de résultats. Le terme soumis est un **préfixe** dérivé d'un titre découvert
  au catalogue.
- **La page est ouverte au niveau SUITE**, l'auto-fermeture de la bibliothèque
  Browser étant au niveau TEST.
- **Le teardown ramène le shell à son accueil** : une suite qui s'arrête sur une
  page de résultats laisse un fragment porteur d'état pour le test suivant.

## Écarts constatés à la génération

Relevés le **2026-08-26** en rejouant chaque étape du plan en direct (rf-mcp,
Browser + SapFioriLibrary 0.7.0) sur la même cible, avant d'écrire la suite
`tests/robot/ui/fiori/recherche_shell_workzone.robot`.

### 1. Le moteur `wc` traverse désormais les shadow roots (défaut 1 du plan, à moitié refermé)

Le plan relève `Get Wc Match Count tag=Button` à **0** sur le bouton de
recherche, et en conclut que la recherche n'est pas ouvrable par un moteur de
la bibliothèque. Mesuré ce jour avec la 0.7.0 : `tag=Button` rend **3**, et
`Resolve Wc Control tag=Button properties={'icon': 'search'}` rend un chemin
CSS qui **descend dans le shadow root** du `ui5-shellbar`
(`… header > div > div > ui5-button-6bfd01e3`). La suite ouvre donc la
recherche par `Click Wc Control`, un moteur de la bibliothèque, sans passer par
un sélecteur Browser hors bibliothèque.

Ce qui reste vrai, et que le scénario 2 continue de mesurer avec la MÊME ancre
technique : `Get Dom Match Count` rend **0** là où `Get Element Count` de la
bibliothèque Browser rend **1**. Le défaut est donc désormais circonscrit au
moteur `dom`, dont le balayage reste au light DOM. Il est journalisé par le
test, il ne le fait pas échouer.

### 2. Le défaut 2 du plan est corrigé dans la bibliothèque

Le plan constate que `Ui5 Control Should Be Visible` **passe** sur un contrôle
de rectangle nul, et en déduit un keyword métier qui mesurerait le rectangle
lui-même. Mesuré ce jour : le mot-clé **échoue** correctement, en nommant les
identifiants rendus mais sans rectangle et en renvoyant vers `Get Ui5 Property`
et `Get Ushell Config`. `Le Champ Est Visible A L Ecran` n'est donc plus une
mesure maison : c'est ce mot-clé de bibliothèque, lu en prédicat, corroboré par
les états que rapporte la bibliothèque Browser (`attached, hidden` sur le champ
de la recherche nouvelle génération).

### 3. Le bouton de recherche n'est pas une bascule : il disparaît

Fait absent du plan, et qui casse toute écriture naïve d'un « ouvrir la
recherche ». Une fois le champ ouvert, le bouton d'icône `search` **n'existe
plus** : mesuré à 0 par les trois canaux (moteur `wc`, moteur `dom`,
bibliothèque Browser). Conséquences encodées dans le page object :
`Ouvrir La Recherche Du Shell` vérifie d'abord si la recherche est ouverte et
ne clique que si elle ne l'est pas, et `Compter Le Bouton De Recherche Par
Moteur` n'a de sens que recherche FERMÉE.

### 4. Le champ de la recherche nouvelle génération n'est pas permanent

Le plan, comme la campagne de perception, traite
`ShellBarView--shellBarSearchInput` comme un témoin d'étanchéité de portée
disponible à tout moment. Mesuré ce jour : il est bien là au premier chargement
(1 correspondance, rectangle nul), et il a **disparu du registre** (0
correspondance) une fois la recherche d'entreprise entrée en scène, plus loin
dans la campagne.

Conséquence : le scénario 1 doit être le **premier** test de la suite, ce que
sa documentation dit explicitement. Conséquence pour la campagne de perception
voisine : son témoin de portée n'est valable que tant que la recherche du shell
n'a pas été ouverte.

### 5. Poser la valeur du champ ne déclenche pas les suggestions

Fait absent du plan. `Fill Ui5 Input` renseigne bien le champ (sa propriété
`value` porte le terme) et le popover de suggestions reste **fermé**. La
recherche d'entreprise réagit à la FRAPPE, pas à la valeur. `Saisir Un Terme De
Recherche` passe donc par de vraies frappes clavier, après un clic de focus et
une sélection totale du contenu précédent.

### 6. Les suggestions arrivent après le retour au repos réseau

Une lecture des popups ouverts faite immédiatement après `Wait For Ui5 Idle`
rend une liste **vide**, alors qu'un instant plus tard `sap.m.InstanceManager`
et `Get Ui5 Open Popups` rapportent tous deux le popover ouvert. Ce n'est pas
un défaut du mot-clé : c'est le rythme de la recherche d'entreprise. `Les
Suggestions Sont Proposees` sonde donc jusqu'à l'ouverture réelle.

### 7. Le nombre de contrôles rendus varie encore plus que le plan ne le relève

Le plan relève 139 à l'accueil, 254 sur les résultats, 63 après un retour
arrière. Mesuré sur un seul run de bout en bout : 139 à l'accueil au premier
chargement, puis 424 et 621 sur des pages de résultats successives, 369 puis
377 sur l'accueil en fin de campagne, 557 sur une page de résultats restaurée
par retour arrière. Le plan avait raison de refuser tout plancher gravé, et la
suite ne compare que **deux relevés d'un même test**.

### 8. La touche Entrée n'est pas un déclencheur fiable, le bouton du champ l'est

Écart trouvé par le PREMIER run complet de la suite, pas par le pas-à-pas : le
scénario 7 a échoué en atterrissant sur l'application au lieu de la page de
résultats. Le diagnostic est venu de l'état relevé à l'échec, pas d'une
supposition : fragment `#ShoppingCart-display?…` et une iframe présente, alors
que la seule action demandée était de relancer la recherche.

Cause : sur une page de résultats, la frappe peut manquer le champ, son
application reprenant le focus après le rendu. Les touches partent alors au
document, et la touche Entrée y ACTIVE l'élément focalisé, c'est-à-dire la
tuile du premier résultat. Le geste rejoué à l'identique passait la fois
suivante, ce qui en fait une course, la pire espèce d'échec à laisser dans une
suite.

Deux corrections, chacune vérifiée en direct :

- `Lancer La Recherche` soumet par le **bouton de déclenchement du champ** et
  non par la touche Entrée. Trois soumissions consécutives du même terme depuis
  la page de résultats restent sur la page de résultats, zéro iframe.
- `Saisir Un Terme De Recherche` **relit le champ** après la frappe et rejoue le
  geste tant qu'il ne porte pas le terme. Une frappe qui manque sa cible ne peut
  donc plus être suivie d'une assertion portant sur une recherche que personne
  n'a saisie.

La suite a ensuite été rejouée **deux fois de suite en 9 sur 9**.

### 9. Ce que le relevé confirme sans réserve

Le reste du plan est retrouvé tel quel : `ushell.searchCEPNew.enabled` à
`false`, le champ CEP rendu à 0 par 0, la création différée des contrôles de la
recherche au premier clic, la source de données `$$APPS$$` de type `Category`
dans le filtre du fragment, le conteneur `application-Action-search-content`
sans aucune iframe, le comptage global de tuiles à 2 pour 1 résultat porté,
l'écran dédié « sans résultat » et l'absence de grille, l'aller-retour entre
les deux états dans un même chargement, l'égalité de l'intent et de l'adresse
chargée entre la voie « résultat » et la voie « intent », la destruction de
l'iframe applicative quand on recherche depuis une application, et la
persistance du terme, du filtre et du compte de résultats à travers la
navigation arrière. Le compteur du contrôle composite est resté
`eshCompGenId_0`. Le service de recherche déclaré est servi par l'adaptateur
`sap.ushell.adapters.local.SearchAdapter`, un fait technique que le scénario 1
assortit d'une assertion.
