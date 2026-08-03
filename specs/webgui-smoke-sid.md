# WebGUI (SAP GUI for HTML) — smoke non-destructif du moteur sid

- **Canal** : Web (Browser + SapFioriLibrary) — cible **WebGUI classique** (SAP GUI
  for HTML via ITS), PAS une app UI5. C'est le terrain du moteur **sid**
  (`Resolve Sid` / `Click Sid` / `Fill Sid Input` / `Sid Should Be Visible`),
  complété par le moteur **dom** pour la page de login (qui n'est ni UI5 ni WebGUI).
- **Système / URL** : A4H (ABAP Platform 1909 trial, client 001) —
  `http://vhcala4hci:50000/sap/bc/gui/sap/its/webgui?sap-client=001`
  (service ICF actif, observé HTTP 200 ; bannière login « SAP NetWeaver »,
  message système « SAP ABAP Platform 1909 developer trial »).
- **Credentials** : variables `${WEBGUI_URL}`, `${SAP_USER}`, `${SAP_PASSWORD}`
  (type RF `Secret` — jamais en clair dans la suite ni dans cette spec).
- **Préconditions** :
  - La page s'ouvre avec les keywords Browser purs (`New Browser` /
    `New Context` / `New Page`) — **PAS** `Open Fiori Launchpad` (elle attend un
    runtime UI5 que le WebGUI n'a pas). `Wait For UI5 Ready` ne s'applique pas.
  - Timeout Browser : le défaut de 10 s a fait échouer le premier `New Page`
    live ; passer `Set Browser Timeout    45s` (ou `wait_until=domcontentloaded`).
  - **Prérequis produit (RÉSOLU le 2026-07-18)** : voir Points de vigilance §1 —
    le format `lsdata` du WebGUI réel ne matchait pas le sélecteur JSON-seul de
    `sid_xpath` ; corrigé dans `src/SapFioriLibrary/_ui5_js.py` (double prédicat
    XPath + regex de capture tolérante, verrouillé par
    `tests/unit/test_sid_and_spy.py`).

## Données observées

Tout ce qui suit a été relevé live le 2026-07-18 sur A4H via rf-mcp
(perception → action, aucun élément supposé).

### Page de login ITS (avant connexion)

- `Get Page Composition` : `title='Logon'`, `ui5_runtime=False`, 57 éléments
  `lsdata` déjà présents, moteurs recommandés `['sid', 'dom']`.
- Formulaire POST vers `/sap/bc/gui/sap/its/webgui`, champs à ids stables :
  `#sysid` (pré-rempli `A4H`), `#sap-client` (pré-rempli `001` via le paramètre
  d'URL), `#sap-user`, `#sap-password`, `#sap-language-dropdown` (pré-rempli
  `English`).
- Localisateurs d'accessibilité validés live avec le moteur **dom** :
  - `Fill Dom Input    <user>    role=textbox    name=User`
  - `Fill Dom Input    <password>    role=textbox    name=Password`
  - `Click Dom Element    role=button    name=Log On`
  (accnames observés : « User Required », « Password Required »,
  « Log On Emphasized » — le matching sous-chaîne suffit).
- Après login la connexion reste portée par les cookies `SAP_SESSIONID_A4H_001`
  + `MYSAPSSO2` : toute navigation ultérieure du même contexte est authentifiée.

### Format réel de l'attribut `lsdata` (découverte centrale)

Le WebGUI A4H (unified rendering, thème Belize) émet un **littéral JS à clés
non citées et guillemets simples**, pas du JSON :

```
lsdata="{21:{SID:'wnd[0]/tbar[0]/okcd',Type:'GuiOKCodeField',ModalNo:0,display:'X'}}"
```

Preuve empirique (écran SAP Easy Access) :
- Sélecteur actuel `Resolve Sid` → `xpath=//*[contains(@lsdata, '"SID":"wnd[0]/tbar[0]/okcd"')]`
  → `Get Element Count` = **0**.
- Format corrigé `xpath=//*[contains(@lsdata, "SID:'wnd[0]/tbar[0]/okcd'")]`
  → `Get Element Count` = **1** (l'`INPUT#ToolbarOkCode`).

Tout le déroulé ci-dessous a été exécuté live avec le format corrigé : le
concept sid fonctionne de bout en bout, seul le littéral du sélecteur est faux.

### L'espace des SIDs = l'espace du scripting SAP GUI desktop

Confirmé écran par écran — les ids sont IDENTIQUES aux field notes ECC :

| Écran | SID observé | Type lsdata | Rôle |
|---|---|---|---|
| tous | `wnd[0]/tbar[0]/okcd` | GuiOKCodeField | champ transaction (`INPUT#ToolbarOkCode`, title « Enter Transaction Code ») |
| SE16 initial | `wnd[0]/usr/ctxtDATABROWSE-TABLENAME` | GuiCTextField | nom de table (label jumeau `wnd[0]/usr/lblDATABROWSE-TABLENAME`) |
| SE16 initial | `wnd[0]/tbar[1]/btn[7]` | GuiButton | « Table Contents (F7) » |
| SE16 sélection | `wnd[0]/tbar[1]/btn[8]` | GuiButton | « Execute (F8) » |
| SE16 sélection | `wnd[0]/tbar[1]/btn[31]` | GuiButton | « Number of Entries (Ctrl+F7) » |
| SE16 sélection | `wnd[0]/usr/txtI1-LOW` … `ctxtI6-HIGH` | GuiTextField/GuiCTextField | champs positionnels (T000 : I1/I2/I4 = `txt`, I3/I5/I6 = `ctxt` — même variance que le desktop) |
| popup comptage | `wnd[1]/usr/txtG_DBCOUNT` | — | compteur (rendu **SPAN texte**, pas input — lire `textContent`) |
| popup comptage | `wnd[1]/tbar[0]/btn[0]` | GuiButton | « Close (Enter) » |
| popup log off | `wnd[1]/usr/btnSPOP-OPTION1` / `OPTION2` | GuiButton | Yes / No (structure SPOP classique) |

- Écrans traversés (ancres locale-indépendantes) : SMEN → SE16
  `SAPLSETB/0230` → sélection T000 `/1BCDWB/DBT000/1000`.
  Comptage T000 observé : **2** entrées (clients 000 et 001).
- La **zone info système** (coin haut droit, `#sysInfoAreaToggle` puis menu
  `#sysInfoAreaMenu`) expose transaction et dynpro courants dans des lignes à
  ids stables : `#sysInfoAreaMenuItemSAPITS_MBAR_TRANSACTION` (texte contient
  le tcode, ex. `SE16`) et `...SAPITS_MBAR_DYNPRO` (ex. `SAPLSETB/0230`) —
  l'équivalent WebGUI de `Get Screen Signature` pour asserter « je suis dans la
  bonne transaction » sans libellé localisé.

### Champ OK-code : masqué par défaut, réglage NON persistant côté serveur

- À la première connexion, `INPUT#ToolbarOkCode` existe mais est replié
  (`display:none` sur ses wrappers `ToolbarOkCode-r`/`-tr`).
- Chemin pour le révéler (ids stables, validé live) : bouton « More » du bandeau
  (`css=[id$=-moreButton]` — voir vigilance §3) → item
  `#wnd[0]/tbar[0]/btn/myITSBtn-BtnChoiceMenu` (« GUI Actions and Settings ») →
  `#tbmnuentryItsOptions` (« Settings... ») → dialogue `#optionsPopupWindow` →
  case `#wguOptOkHid` (« Show OK Code field », `role=checkbox`) →
  `#wguOptionsSave`. Le champ devient visible immédiatement.
- **Persistance testée live : contexte navigateur SEULEMENT.** Un re-login dans
  un `New Context` vierge re-masque le champ (aucun cookie/localStorage
  d'options observé). Le réglage n'est PAS un paramètre utilisateur serveur —
  contrairement à `Use ALV Grid In Data Browser` côté ECC.
- **Alternative robuste validée live** : le paramètre d'URL
  `...webgui?sap-client=001&~transaction=SE16` atterrit directement sur « Data
  Browser: Initial Screen » en réutilisant la session de login du contexte
  (58 éléments lsdata, `ctxtDATABROWSE-TABLENAME` présent). C'est la voie
  recommandée pour le smoke : zéro dépendance au réglage d'affichage.

### Lancement de transaction et navigation observés

- OK-code : `Fill Sid Input    wnd[0]/tbar[0]/okcd    /nSE16` puis touche
  Entrée sur le même élément (`Press Keys ... Enter` — chaque action déclenche
  un aller-retour serveur qui RE-REND le DOM).
- Menus : la barre de menus vit derrière le bouton « More » du bandeau ; les
  items portent l'id DOM = id SAP GUI (`#wnd[0]/mbar/menu[4]-BtnChoiceMenu`,
  sous-items `#wnd[0]/mbar/menu[4]/menu[12]`).
- Log off validé deux fois : menu System → « Log Off » (dernier item du menu
  System) → popup SPOP → `wnd[1]/usr/btnSPOP-OPTION1` (Yes) → page finale
  `document.title == 'Logoff'` et **0 élément `lsdata`**.

## Scénarios

### 1. Login ITS par le moteur dom
- **Étapes** :
  1. Ouvrir Chromium (`headless=False`), nouveau contexte, `New Page ${WEBGUI_URL}`
     (timeout ≥ 45 s ou `wait_until=domcontentloaded`).
  2. Vérifier la composition : moteurs recommandés contiennent `sid` et `dom`
     (`Get Page Composition`).
  3. `Fill Dom Input` utilisateur (`role=textbox` + `name=User`), mot de passe
     (`name=Password`), puis `Click Dom Element` (`role=button` + `name=Log On`).
- **Résultat attendu** : le document contient > 0 éléments `[lsdata]` et le
  champ `wnd[0]/tbar[0]/okcd` est présent dans le DOM (résolution sid, comptage
  ≥ 1) — aucune assertion sur un libellé localisé ni sur `document.title`.

### 2. Lancement de SE16 par URL `~transaction` et vérification par sid
- **Étapes** :
  1. Depuis le contexte connecté, `Go To ${WEBGUI_URL}&~transaction=SE16`.
  2. Vérifier par sid la présence du champ table :
     `Sid Should Be Visible    wnd[0]/usr/ctxtDATABROWSE-TABLENAME`.
- **Résultat attendu** : l'élément au SID `wnd[0]/usr/ctxtDATABROWSE-TABLENAME`
  est visible ; la ligne info système `...SAPITS_MBAR_DYNPRO` contient
  `SAPLSETB` (id technique, pas un libellé).

### 3. Comptage T000 de bout en bout au moteur sid (cœur du smoke)
- **Étapes** :
  1. `Fill Sid Input    wnd[0]/usr/ctxtDATABROWSE-TABLENAME    T000`.
  2. `Click Sid    wnd[0]/tbar[1]/btn[7]` (Table Contents) → attendre le rendu
     de l'écran de sélection par sid (`Sid Should Be Visible    wnd[0]/tbar[1]/btn[31]`).
  3. `Click Sid    wnd[0]/tbar[1]/btn[31]` (Number of Entries).
  4. Lire le texte de l'élément au SID `wnd[1]/usr/txtG_DBCOUNT`
     (`Get Text` sur `Resolve Sid` — c'est un SPAN, pas un input).
  5. `Click Sid    wnd[1]/tbar[0]/btn[0]` (fermer le popup).
- **Résultat attendu** : le compteur, débarrassé des non-chiffres, est un entier
  **≥ 2** (T000 contient au minimum les clients 000 et 001) ; après fermeture,
  plus aucun élément `wnd[1]/*` visible.
- **Non-destructif** : ne JAMAIS toucher `wnd[0]/tbar[1]/btn[5]`
  (« Create Entries (F5) », présent sur l'écran initial SE16).

### 4. Déconnexion propre par le menu System
- **Étapes** :
  1. Ouvrir le bouton « More » du bandeau, puis le menu System — le repérer
     par POSITION RELATIVE (avant-dernier `mbar/menu[n]` avant Help), pas par
     index absolu (voir vigilance §4).
  2. Cliquer le dernier item du menu System (Log Off).
  3. `Click Sid    wnd[1]/usr/btnSPOP-OPTION1` (confirmer).
- **Résultat attendu** : le document ne contient plus AUCUN élément `[lsdata]`
  (comptage = 0) — assertion 100 % locale-indépendante de fin de session.
  Fermer ensuite le navigateur (`Close Browser` / `Close Fiori`).

## Keywords métier manquants (sap-generator → `resources/fiori_keywords.resource`)

1. `Open WebGui` — New Browser/Context + `New Page ${url}` avec timeout adapté,
   garde `Get Page Composition` (moteur `sid` recommandé sinon échec explicite).
2. `Log In To WebGui    ${user}    ${password}` — le trio dom
   (`name=User` / `name=Password` / `name=Log On`), garde post-login
   « > 0 éléments lsdata » ; mot de passe `Secret`, jamais journalisé.
3. `Go To WebGui Transaction    ${tcode}` — voie nominale URL `&~transaction=`
   + re-perception ; variante OK-code (`Fill Sid Input` + Entrée) quand le champ
   est visible.
4. `Read WebGui Popup Count` — lit et normalise (chiffres seuls) le texte du SID
   `wnd[1]/usr/txtG_DBCOUNT` ; miroir WebGUI du pattern SE16 « Number of
   Entries » d'`ecc_keywords.resource`.
5. `Log Off WebGui` — More → System (position relative) → dernier item →
   `btnSPOP-OPTION1` → assertion « 0 lsdata ».
6. Alias miroirs à brancher sur la table de correspondance existante de
   `fiori_keywords.resource` (`Open SAP And Log In`, `Confirm Popup`,
   `Close SAP`) une fois 1–5 en place.

## Points de vigilance

1. **Format `lsdata` double (RÉSOLU le 2026-07-18) : le WebGUI réel émet un
   littéral JS, pas du JSON.** `sid_xpath` cherchait `"SID":"…"` (JSON,
   guillemets doubles — le format de nos fixtures `hybrid_fixture.html` /
   `shell_iframe_fixture.html`), mais A4H émet `SID:'…'` (littéral JS,
   guillemets simples, clés non citées). Prouvé live : 0 match vs 1 match sur
   `wnd[0]/tbar[0]/okcd`. Correctif appliqué dans
   `src/SapFioriLibrary/_ui5_js.py` : `sid_xpath` émet un double prédicat
   XPath (un par encodage) et le `captureSid` du bundle/recorder web utilise
   une regex tolérante aux deux formes ; verrouillé par
   `tests/unit/test_sid_and_spy.py`, non-régression fixtures JSON par
   `fiori_hybrid_smoke.robot`, validation live par la suite générée depuis
   cette spec.
2. **Chaque action = aller-retour serveur + re-rendu DOM.** Les références
   d'éléments deviennent périmées à chaque interaction ; toujours re-résoudre
   (les keywords sid re-résolvent par construction). Les assertions doivent
   sonder jusqu'au rendu, jamais de `Sleep`.
3. **Ids `u…` dynamiques par écran.** Le conteneur toolbar et son bouton
   « More » changent d'id à chaque écran (`u71-moreButton` sur SMEN,
   `u64D-moreButton` sur SE16 sélection). Ne jamais coder ces ids en dur —
   utiliser `css=[id$=-moreButton]` (unique, validé) ou les SIDs. Stables en
   revanche : `#ToolbarOkCode`, `#sysInfoArea*`, `#tbmnuentry*`, `#wguOpt*`,
   `#optionsPopupWindow`, et tous les ids `#wnd[0]/...` des menus.
4. **La position du menu System varie par transaction** (`mbar/menu[4]` sur
   SMEN, `mbar/menu[5]` sur SE16 — la barre de menus est celle de la
   transaction). Convention SAP fiable : System = avant-dernier menu, Help =
   dernier ; « Log Off » = dernier item du menu System. Le keyword métier doit
   compter les `mbar/menu[n]-BtnChoiceMenu` visibles plutôt qu'indexer en dur.
5. **Réglage « Show OK Code field » non persistant côté serveur** (perdu dans un
   contexte vierge) : ne pas fonder le smoke dessus ; l'URL `~transaction` est
   la voie déterministe. Si le champ OK-code est nécessaire, le révéler à
   CHAQUE run via le dialogue Settings (ids stables §Données observées).
6. **Chaque navigation `~transaction` ouvre une nouvelle session GUI serveur**
   (l'ancienne expire par timeout). Acceptable sur le trial ; sur un système
   partagé, préférer une seule navigation puis l'OK-code, et TOUJOURS terminer
   par le log off (« 0 lsdata » vérifié) pour ne pas accumuler de sessions.
7. **Popups de la page de login** : bandeau d'avertissement « No switch to
   HTTPS occurred » présent (HTTP pur) — informatif, ne bloque pas ; aucun
   consentement cookies sur ce système.
8. **`Get Ui5 Page Tree` est sans objet** sur WebGUI (pas de registre UI5) —
   son échec n'est pas un signal d'erreur ; la perception passe par
   `Get Page Composition`, le snapshot ARIA et l'extraction des SIDs.
9. **Iframes présentes mais vides** (`#cnt0-iframe`, `#cnt0-bgiframe`,
   `about:blank`, invisibles) : tout le WebGUI vit dans le document principal —
   aucune portée de frame (`Set Ui5 Frame`) n'est nécessaire sur A4H.
