# Canal Fiori : web UI5, WebGUI, pages hybrides (`SapFioriLibrary`)

La bibliothèque ne pilote pas la page elle-même : elle réutilise la page active
de la bibliothèque **Browser** (Playwright) et y injecte le bundle `__SAPFX`.
Une suite doit donc importer `Library    Browser` à côté.

## Les cinq moteurs de résolution

| Moteur | Quand | Keywords |
| --- | --- | --- |
| `role` | page UI5 classique, registre de contrôles peuplé | `Resolve/Click/Fill Ui5 …` |
| `xpath` | hiérarchie de contrôles (`//Table//Button[@text='Edit']`) | mêmes keywords, localisateur xpath ; `Get Ui5 Xpath` rend le plus court unique |
| `sid` | SAP GUI for HTML (WebGUI), non-UI5 | `Resolve/Click/Fill Sid …` |
| `wc` | UI5 Web Components SANS runtime UI5 (registre vide) | `Resolve/Click/Fill Wc …` |
| `dom` | zones NON-SAP d'une page hybride (React, Angular, vanilla) | `Resolve/Click/Fill Dom …` |

`Resolve Ui5 With Fallback` enchaîne role → xpath → sid → wc → dom, journalise
la réparation et alimente la télémétrie.

Localisateurs d'accessibilité disponibles côté `dom` ET `wc` : `role=` (rôle
ARIA CALCULÉ, explicite ou implicite via la sémantique HTML) et `name=` (nom
accessible : `aria-labelledby`, `aria-label`, `label[for]`, `alt`, texte ; côté
`wc`, la convention `accessible-name` / `accessibleName`). C'est le localisateur
« intention utilisateur ».

Ancres utiles côté UI5 : `idSuffix` (ids stables Fiori Elements `fe::…`),
`viewId` (la vue propriétaire), `containedIn` (containment DOM : les contrôles
rendus À L'INTÉRIEUR du noeud d'un autre, la voie des tuiles rendues par un
composant séparé). `Get Ui5 Ids` répond LESQUELS ont matché.

## Percevoir

- `Get Ui5 Page Tree` (`mode=diff` ensuite), `Get Ui5 Page Map` (carte `@N`,
  puis `Resolve/Click/Fill Ui5 Ref`, fraîcheur re-vérifiée au registre rendu).
- `Get Ui5 Application State` : portée de frame, runtime, messages en UN appel.
  Le « où en suis-je » à joindre au diagnostic d'un échec.
- `Get Page Composition` : quelles technologies cohabitent et quels moteurs
  valent par région, avec descente d'un niveau dans chaque iframe.
- `Get Fiori Diagnostics` / `Log Fiori Diagnostics` : composition, arbre UI5,
  erreurs console et page, snapshot ARIA des zones non-SAP, chaque section
  best-effort, plus une synthèse `issues` actionnable. Lire `issues` d'abord.
- `Ui5 Runtime Is Present` : la sonde à poser AVANT tout keyword qui exige le
  runtime. Elle répond True/False sans jamais échouer, et c'est la SEULE
  expression web qui n'injecte pas le bundle, donc qui n'instrumente pas
  `fetch`/XHR de l'application : observer ne doit rien modifier.
- `Get Ui5 Control Info` (type plein, contexte de liaison réduit à ses entrées
  primitives) et `Get Ui5 Aggregation Info` (les enfants d'une agrégation,
  RENDUS OU NON : les items d'un `Select` popover fermé n'existent pas au DOM).

## Attendre et juger

- `Wait For Ui5 Idle` : le repos RÉEL (XHR et fetch instrumentés, indicateurs
  busy, calme continu `settle`). « Rendu » ne veut pas dire « données
  arrivées ». Unité Robot : `settle=2000` nu vaut 2000 secondes.
- `Get Ui5 Messages` / `Ui5 Should Have No Messages Of Type` : MessageManager
  plus hook `MessageToast`. Assertion par TYPE, jamais sur le texte localisé.
  Retourne un dict `{messages, toasts}`.
- `Ui5 Control Should Be Visible` exige le rectangle NON NUL en plus du registre
  rendu : un champ de recherche peut rester rendu à 0x0.
- Lire une VALEUR : `Get Ui5 Property` / `Get Ui5 Properties` (la propriété au
  registre), pas `Get Ui5 Text`, qui lit ce que le navigateur AFFICHE, exige la
  visibilité et rend tout ce que le contrôle dessine (un item à compteur lit
  `"Accessories\n34"` là où sa propriété `title` vaut `"Accessories"`).
- `Read Ui5 Table` : table UI5 vers liste de dicts, miroir de `Read Grid`.

## Dialogues et popups

`Get Ui5 Open Popups` cumule `sap.m.InstanceManager` ET les popups Web
Components ouverts (témoin `open`) : un dialogue fermé reste RENDU, seul
l'InstanceManager tranche, et le menu utilisateur d'un shell Work Zone est un
popover WC que l'InstanceManager ignore.

`Click Ui5 Dialog Button` acquitte par POSITION : les boutons d'une MessageBox
portent un id généré et un texte traduit, et **la bonne position varie par
release** (relevé live : en UI5 1.120 le refus de navigation offre
`[0] Copy` et `[1] Close`, donc acquitter en position 0 copie le message et
laisse le dialogue ouvert).

## Frames

`Set Ui5 Frame` remplace la pile ; `Push Ui5 Frame` / `Pop Ui5 Frame` gèrent les
frames IMBRIQUÉES (portée chaînée `a >>> b`), le cas Work Zone / cFLP où
l'application vit dans une iframe. Ne jamais ancrer un `__containerN` : cet
identifiant est un COMPTEUR (mesuré `__container4` puis `__container5` dans la
même session). `List Page Iframes` permet d'asserter la structure.

Un launchpad ABAP classique, lui, n'a AUCUNE iframe : l'application est rendue
dans le document du shell, reconnue par le conteneur dérivé de son intent.

## Launchpad et FLP

`Open Fiori App` (navigation par intent `SemanticObject-action`, le hash stable
cross-catalogue, thème et langue), `Log In Via Identity Provider` (presets
sap-ias, azure-ad, generic ; déroulés une-page ET deux-étapes détectés
dynamiquement), `Get Ushell Config` (la configuration DÉCLARÉE, lecture pure
sans injection), et les lectures de services ushell : `Get Flp User`,
`List Flp Apps`, `List Flp Catalogs`, `List Flp Groups`,
`Get Flp Intent Support`, plus les prédicats `Flp Container Is/Should Be
Present` et `Flp Service Is Available` (un service absent d'une release est un
branchement, pas un échec).

Inventorier un catalogue par le SERVICE, pas par les tuiles affichées : c'est ce
que l'utilisateur a le droit d'ouvrir.

## WebGUI (SAP GUI for HTML)

`Webgui Is Present`, `Get Webgui Element Count` (`window=1` = popup, visible
seulement ; sans argument = tous les `lsdata`, le témoin de fin de session),
`List Webgui Menus`, `List Webgui Menu Items`. L'espace des SID est identique au
scripting desktop (`wnd[0]/usr/ctxtDATABROWSE-TABLENAME`).

## Visuel et état

`Get Ui5 Perceptual Hash` / `Ui5 Screen Should Match Baseline` (même cycle
snapshot que l'ECC), `Get Page Languages` (la langue réellement servie),
`Get Session Cookie Summary` (jamais de valeur ; prédicat « expiration
FUTURE » : la bibliothèque Browser rend un cookie de session daté de 1969),
`Get Page Location` (accepte `url=` / `base=` pour décomposer une adresse
donnée), `Upload File Via Ui5`.

Pièges web relevés live : voir [pieges-terrain.md](pieges-terrain.md).
