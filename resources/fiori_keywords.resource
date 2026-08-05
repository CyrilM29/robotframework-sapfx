*** Settings ***
Documentation       Mots-clés web Fiori / S/4HANA lisibles métier.
...                 Miroir délibéré de `ecc_keywords.resource` : un test se lit de la
...                 même façon (`Open ...`, `Go To ...`, `Save And Expect Success`)
...                 qu'il pilote le client lourd SAP GUI ou l'interface web Fiori.
...                 Les localisateurs sont des sélecteurs de contrôles UI5 (stables),
...                 jamais du CSS/XPath brut.
...
...                 Table de correspondance ECC ↔ Fiori (mêmes noms quand la
...                 sémantique coïncide, alias fournis ici) :
...                 | =ECC=                    | =Fiori=                                 |
...                 | Open SAP And Log In      | Open SAP And Log In (→ Open Fiori Launchpad) |
...                 | Go To Transaction        | Open App (naviguer vers une tuile/app)  |
...                 | Popup Is Present         | Popup Is Present                        |
...                 | Confirm Popup            | Confirm Popup (→ Confirm Ui5 Dialog)    |
...                 | Cancel Popup             | Cancel Popup (→ Cancel Ui5 Dialog)      |
...                 | Save And Expect Success  | Save And Expect Success                 |
...                 | Close SAP                | Close SAP (→ Close Fiori)               |
...                 Divergence assumée : `Go To Transaction` (code transaction) n'a pas
...                 d'équivalent nominal web : on ouvre une *application* (`Open App`).
...
...                 La resource couvre aussi le **WebGUI classique** (SAP GUI for HTML
...                 via ITS : moteur `sid`, ids relevés live sur A4H 2026-07-18) :
...                 `Open WebGui` / `Log In To WebGui` (login ITS au moteur dom),
...                 `Go To WebGui Transaction` (l'équivalent WebGUI de
...                 `Go To Transaction`, par URL `~transaction`),
...                 `Count WebGui Table Entries` (miroir du `Count Table Entries`
...                 ECC), `Log Off WebGui` / `Close WebGui` (miroir de `Close SAP`).
...                 Sur WebGUI, un SID = l'id de scripting SAP GUI desktop
...                 (`wnd[0]/usr/...`), le même espace d'ids que
...                 `ecc_keywords.resource`.

Library             Browser
# Import sans argument (défaut ui5_timeout=15s) : une suite qui veut un autre
# budget appelle `Set Ui5 Timeout` (0.6.1) au lieu de ré-importer la lib avec
# d'autres arguments : Robot ignorerait le second import avec un warning.
Library             SapFioriLibrary


*** Variables ***
${FIORI_BASE_URL}       https://sdk.openui5.org/    # cible par défaut : OpenUI5 Demo Kit
${BROWSER}              chromium
${HEADLESS}             ${False}
${FIORI_USER}           ${EMPTY}
${FIORI_PASSWORD}       ${EMPTY}

# --- WebGUI (SAP GUI for HTML via ITS) : SIDs et sélecteurs stables, relevés live sur A4H (2026-07-18)
${WEBGUI_URL}                       ${EMPTY}    # URL du service ICF webgui : fournie par la suite ou -v
${WEBGUI_TIMEOUT}                   45s    # le défaut Browser (10 s) a fait échouer le premier New Page live
${WEBGUI_OKCODE_SID}                wnd[0]/tbar[0]/okcd    # champ transaction : masqué par défaut (présence, pas visibilité)
${WEBGUI_TABLE_NAME_SID}            wnd[0]/usr/ctxtDATABROWSE-TABLENAME    # SE16 : nom de table
${WEBGUI_TABLE_CONTENTS_SID}        wnd[0]/tbar[1]/btn[7]    # SE16 initial : « Table Contents (F7) »
${WEBGUI_COUNT_BUTTON_SID}          wnd[0]/tbar[1]/btn[31]    # écran de sélection : « Number of Entries »
${WEBGUI_COUNT_RESULT_SID}          wnd[1]/usr/txtG_DBCOUNT    # compteur du popup : SPAN texte, pas un input
${WEBGUI_POPUP_CLOSE_SID}           wnd[1]/tbar[0]/btn[0]    # popup : « Close (Enter) »
${WEBGUI_POPUP_CONFIRM_SID}         wnd[1]/usr/btnSPOP-OPTION1    # popup SPOP : « Yes »
${WEBGUI_MORE_BUTTON_SELECTOR}      css=[id$="-moreButton"] >> visible=true    # bandeau : bouton « More » (id u… dynamique par écran, jamais en dur)
${WEBGUI_SYSINFO_DYNPRO_SELECTOR}    css=[id="sysInfoAreaMenuItemSAPITS_MBAR_DYNPRO"]    # zone info système : ligne dynpro (id stable)


*** Keywords ***
Open Fiori Launchpad
    [Documentation]    Ouvre le navigateur sur le launchpad / l'application Fiori et
    ...                s'authentifie si des identifiants sont fournis. Prévu pour
    ...                Suite Setup. Miroir de `Open SAP And Log In` côté ECC.
    [Arguments]    ${url}=${FIORI_BASE_URL}    ${user}=${FIORI_USER}    ${password}=${FIORI_PASSWORD}
    New Browser    ${BROWSER}    headless=${HEADLESS}
    New Page       ${url}
    Run Keyword If    '${user}' != '${EMPTY}'    Log In To Fiori    ${user}    ${password}
    Wait For UI5 Ready

Log In To Fiori
    [Documentation]    Remplit le formulaire de connexion SAP (contrôles UI5) et le soumet.
    [Arguments]    ${user}    ${password}
    Fill Ui5 Input    ${user}        properties={'name': 'sap-user'}
    ${previous_log_level}=    Set Log Level    NONE
    Fill Ui5 Input    ${password}    properties={'name': 'sap-password'}
    Set Log Level    ${previous_log_level}
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'Log On'}
    Wait For UI5 Ready

Wait For UI5 Ready
    [Documentation]    Bloque jusqu'à ce que le moteur SAPUI5 soit *inactif*, pas
    ...                seulement chargé. Équivalent UI5 du mot-clé ECC `Wait Until Busy Done` :
    ...                exige (1) le runtime présent : Core hérité **ou** module Element
    ...                (UI5 2.x supprime `sap.ui.getCore()`), (2) aucune mise à jour d'UI
    ...                en attente (`getUIDirty`, quand le Core l'expose), et (3) aucun
    ...                indicateur d'occupation visible (BusyIndicator local/global,
    ...                BusyDialog), proxy fiable d'une requête OData/XHR en vol. Bien
    ...                plus fort que le simple test « `sap.ui.require` existe », qui
    ...                passait avant le rendu.
    Wait For Function    () => { const s = window.sap; if (!(s && s.ui)) return false; let E = null; try { E = s.ui.require && s.ui.require('sap/ui/core/Element'); } catch (e) {} const c = s.ui.getCore ? s.ui.getCore() : null; if (!c && !E) return false; if (c && typeof c.getUIDirty === 'function' && c.getUIDirty()) return false; const b = document.querySelectorAll('.sapUiLocalBusyIndicator, .sapMBusyDialog, #sapUiBusyIndicator'); for (let i = 0; i < b.length; i++) { if (b[i].offsetParent !== null) return false; } return true; }
    ...    message=UI5 runtime did not become idle

Open App
    [Documentation]    Navigue vers une application Fiori par le texte de sa tuile /
    ...                de son titre. Contrepartie web de `Go To Transaction`.
    [Arguments]    ${app_title}
    Click Ui5 Control    controlType=sap.m.GenericTile    properties={'header': '${app_title}'}
    Wait For UI5 Ready

Open App By Intent
    [Documentation]    Navigue le launchpad par **intent sémantique**
    ...                ``SemanticObject-action`` (``SalesOrder-manage``,
    ...                paramètres nommés en query), puis attend que
    ...                l'application soit rendue et inactive. La voie STABLE :
    ...                le hash d'intent survit aux réorganisations de
    ...                catalogue, au thème et à la langue, là où `Open App`
    ...                (clic de tuile par titre) reste la voie « comme
    ...                l'utilisateur ». Exemple ::
    ...
    ...                    Open App By Intent    SalesOrder-manage    SalesOrder=1234
    [Arguments]    ${intent}    &{params}
    Open Fiori App    ${intent}    &{params}
    Wait For UI5 Ready

Save And Expect Success
    [Documentation]    Déclenche l'action Enregistrer et vérifie l'apparition d'un
    ...                MessageToast (preuve d'un retour positif) **sans** dépendre du
    ...                texte localisé du message (convention : on vérifie le *type* de
    ...                feedback, pas son libellé ; le côté ECC vérifie le type `S`, pas
    ...                le texte). Le MessageToast n'est pas un contrôle UI5 enregistré
    ...                (aucun id de registre à résoudre) : on cible donc, à titre
    ...                exceptionnel et au seul niveau resource, sa classe-cadre stable
    ...                `.sapMMessageToast`. Même intention et même nom que le mot-clé ECC.
    Click Ui5 Control    controlType=sap.m.Button    properties={'icon': 'sap-icon://save'}
    Wait For UI5 Ready
    Wait For Elements State    css=.sapMMessageToast    visible

Ui5 Dialog Should Be Visible
    [Documentation]    Vérifie qu'une boîte de dialogue UI5 (``sap.m.Dialog``) est ouverte
    ...                et rendue. Couvre aussi les MessageBox, qui sont des Dialog.
    Ui5 Control Should Be Visible    controlType=sap.m.Dialog

Confirm Ui5 Dialog
    [Documentation]    Clique le bouton ``${button}`` d'une boîte de dialogue UI5 ouverte
    ...                (``sap.m.Dialog`` / MessageBox). On cible le bouton par son libellé
    ...                (fourni en argument, jamais codé en dur dans un mot-clé métier)
    ...                à l'intérieur du Dialog, ce qui reste une adresse de contrôle UI5.
    [Arguments]    ${button}=OK
    Click Ui5 By Xpath    //Dialog//Button[@text='${button}']
    Wait For UI5 Ready

Cancel Ui5 Dialog
    [Documentation]    Ferme une boîte de dialogue UI5 par son bouton d'annulation
    ...                (libellé ``${button}``, par défaut « Cancel »).
    [Arguments]    ${button}=Cancel
    Click Ui5 By Xpath    //Dialog//Button[@text='${button}']
    Wait For UI5 Ready

Close Fiori
    [Documentation]    Ferme le navigateur. Prévu pour Suite Teardown.
    Close Browser

# --- WebGUI classique (SAP GUI for HTML via ITS) : moteur sid -----------------
# La page de login ITS n'est ni UI5 ni WebGUI : on la pilote au moteur dom
# (rôle ARIA + nom accessible). Ensuite, tout s'adresse par SID : le même espace
# d'ids que le scripting SAP GUI desktop. Chaque action déclenche un
# aller-retour serveur qui RE-REND le DOM : on sonde toujours jusqu'au rendu
# (Wait For Function / keywords sid), jamais de Sleep.

Open WebGui
    [Documentation]    Ouvre le navigateur sur le WebGUI (SAP GUI for HTML / ITS) et
    ...                vérifie par `Get Page Composition` que les moteurs `sid` et
    ...                `dom` s'appliquent (échec explicite sinon). Prévu pour
    ...                Suite Setup, avant `Log In To WebGui`.
    [Arguments]    ${url}=${WEBGUI_URL}    ${browser}=${BROWSER}    ${headless}=${HEADLESS}
    New Browser    ${browser}    headless=${headless}
    New Context
    Set Browser Timeout    ${WEBGUI_TIMEOUT}
    New Page    ${url}    wait_until=domcontentloaded
    ${comp}=    Get Page Composition
    Should Contain    ${comp}[engines]    sid
    ...    msg=La page ${url} n'expose aucun élément WebGUI (lsdata) : pas une cible du moteur sid
    Should Contain    ${comp}[engines]    dom
    ...    msg=Moteur dom non recommandé sur ${url} : page de login ITS inattendue

Log In To WebGui
    [Documentation]    S'authentifie sur la page de login ITS par le moteur dom
    ...                (rôle + nom accessible, la page de login n'est pas du WebGUI).
    ...                Mot de passe : chaîne ou type `Secret` RF 7.4, jamais journalisé.
    ...                Garde post-login : au moins un élément WebGUI (lsdata) rendu.
    [Arguments]    ${user}    ${password}
    Fill Dom Input    ${user}    role=textbox    name=User
    ${previous_log_level}=    Set Log Level    NONE
    ${plain}=    Evaluate    getattr($password, 'value', $password)    # déballe un Secret RF 7.4
    Fill Dom Input    ${plain}    role=textbox    name=Password
    Set Log Level    ${previous_log_level}
    Click Dom Element    role=button    name=Log On
    WebGui Should Be Rendered

WebGui Should Be Rendered
    [Documentation]    Sonde jusqu'au rendu d'au moins un élément WebGUI (attribut
    ...                `lsdata`), le pendant WebGUI de `Wait Until Busy Done` / `Wait
    ...                For UI5 Ready` après une navigation ou un aller-retour serveur.
    Wait For Function    () => document.querySelectorAll('[lsdata]').length > 0
    ...    timeout=${WEBGUI_TIMEOUT}

WebGui Ok Code Field Should Be Present
    [Documentation]    Vérifie que le champ OK-code (transaction) est adressable par
    ...                SID dans le DOM. Présence, pas visibilité : le champ est masqué
    ...                par défaut et le réglage « Show OK Code field » n'est pas
    ...                persistant côté serveur (relevé live A4H). Attente d'état
    ...                `attached` (sondée) : la toolbar est rendue APRÈS les premiers
    ...                éléments lsdata : un comptage instantané part trop tôt.
    ${sel}=    Resolve Sid    ${WEBGUI_OKCODE_SID}
    Wait For Elements State    ${sel}    attached    timeout=${WEBGUI_TIMEOUT}
    ...    message=Champ OK-code introuvable par SID : session WebGUI non connectée ?

Go To WebGui Transaction
    [Documentation]    Navigue vers une transaction par le paramètre d'URL
    ...                `~transaction`, la voie déterministe (le champ OK-code est
    ...                masqué par défaut), puis attend le rendu WebGUI. NB : chaque
    ...                navigation `~transaction` ouvre une nouvelle session GUI
    ...                serveur (l'ancienne expire) : toujours terminer par
    ...                `Log Off WebGui`.
    [Arguments]    ${tcode}    ${url}=${WEBGUI_URL}
    Go To    ${url}&~transaction=${tcode}    wait_until=domcontentloaded
    WebGui Should Be Rendered

WebGui Dynpro Should Contain
    [Documentation]    Vérifie que la ligne « dynpro » de la zone info système du
    ...                bandeau WebGUI contient le fragment donné (id technique
    ...                programme/écran, ex. `SAPLSETB`, jamais un libellé localisé).
    ...                L'équivalent WebGUI de `Get Screen Signature` pour asserter
    ...                « je suis sur le bon écran ».
    [Arguments]    ${fragment}
    ${text}=    Get Text    ${WEBGUI_SYSINFO_DYNPRO_SELECTOR}
    Should Contain    ${text}    ${fragment}
    ...    msg=L'écran courant n'est pas le dynpro attendu (${fragment})

WebGui Data Browser Should Be Open
    [Documentation]    Vérifie par SID que l'écran initial du Data Browser (SE16) est
    ...                rendu : champ « nom de table » visible et dynpro `SAPLSETB`
    ...                (assertions locale-indépendantes).
    Sid Should Be Visible    ${WEBGUI_TABLE_NAME_SID}
    WebGui Dynpro Should Contain    SAPLSETB

Read WebGui Popup Count
    [Documentation]    Lit le compteur du popup SE16 « Number of Entries »
    ...                (`txtG_DBCOUNT`, rendu SPAN texte sur WebGUI, pas un input) et
    ...                le normalise en entier (chiffres seuls, les séparateurs de
    ...                milliers varient par locale). Miroir WebGUI du pattern
    ...                « Number of Entries » d'`ecc_keywords.resource`.
    Sid Should Be Visible    ${WEBGUI_COUNT_RESULT_SID}
    ${sel}=    Resolve Sid    ${WEBGUI_COUNT_RESULT_SID}
    ${raw}=    Get Text    ${sel}
    # Filtrage caractère par caractère : un motif regex à backslash serait
    # silencieusement défiguré par l'échappement Robot (leçon verrouillée par
    # tests/unit/test_se16_exploration_logic.py).
    ${count}=    Evaluate    int(''.join(c for c in $raw if c.isdigit()) or 0)
    RETURN    ${count}

Close WebGui Popup
    [Documentation]    Ferme le popup WebGUI courant (`wnd[1]`) par son bouton
    ...                « Close (Enter) » et sonde jusqu'à ce que plus aucun élément
    ...                `wnd[1]/*` ne soit visible.
    Click Sid    ${WEBGUI_POPUP_CLOSE_SID}
    No WebGui Popup Should Be Visible

No WebGui Popup Should Be Visible
    [Documentation]    Sonde jusqu'à la disparition de tout élément WebGUI de la
    ...                fenêtre popup (`wnd[1]/*` dans l'attribut `lsdata`).
    Wait For Function
    ...    () => Array.from(document.querySelectorAll('[lsdata]')).filter(e => (e.getAttribute('lsdata') || '').indexOf('wnd[1]') !== -1 && e.offsetParent !== null).length === 0
    ...    timeout=${WEBGUI_TIMEOUT}

Count WebGui Table Entries
    [Documentation]    Depuis l'écran initial du Data Browser (SE16), compte les
    ...                entrées de `${table}` via « Table Contents » puis « Number of
    ...                Entries » (tout au moteur sid) et referme le popup. Retourne
    ...                l'entier. Miroir WebGUI du `Count Table Entries` ECC ;
    ...                consultation pure (jamais `btn[5]` « Create Entries »).
    [Arguments]    ${table}
    Fill Sid Input    ${WEBGUI_TABLE_NAME_SID}    ${table}
    Click Sid    ${WEBGUI_TABLE_CONTENTS_SID}
    Sid Should Be Visible    ${WEBGUI_COUNT_BUTTON_SID}    # écran de sélection rendu
    Click Sid    ${WEBGUI_COUNT_BUTTON_SID}
    ${count}=    Read WebGui Popup Count
    Close WebGui Popup
    RETURN    ${count}

Log Off WebGui
    [Documentation]    Déconnexion propre : bouton « More » du bandeau, menu System
    ...                repéré par POSITION RELATIVE (avant-dernier : la barre de menus
    ...                varie par transaction), dernier item (Log Off), confirmation
    ...                SPOP, puis assertion 100 % locale-indépendante de fin de
    ...                session : plus AUCUN élément `lsdata`.
    Click    ${WEBGUI_MORE_BUTTON_SELECTOR}
    Wait For Function
    ...    () => Array.from(document.querySelectorAll('[id^="wnd[0]/mbar/menu["][id$="-BtnChoiceMenu"]')).filter(e => e.offsetParent !== null).length > 0
    ...    timeout=${WEBGUI_TIMEOUT}
    ${menu_ids}=    Evaluate JavaScript    ${None}
    ...    () => Array.from(document.querySelectorAll('[id^="wnd[0]/mbar/menu["][id$="-BtnChoiceMenu"]')).filter(e => e.offsetParent !== null).map(e => e.id)
    ${system_menu}=    Set Variable    ${menu_ids}[-2]    # System = avant-dernier, Help = dernier
    Click    css=[id="${system_menu}"]
    ${menu_base}=    Evaluate    $system_menu.replace('-BtnChoiceMenu', '')
    Wait For Function
    ...    () => Array.from(document.querySelectorAll('[id^="${menu_base}/menu["]')).filter(e => e.offsetParent !== null).length > 0
    ...    timeout=${WEBGUI_TIMEOUT}
    # Items DIRECTS du menu System seulement (pas les sous-menus) : après le
    # préfixe, plus aucun « / » dans l'id. Log Off = dernier item (convention SAP).
    ${items}=    Evaluate JavaScript    ${None}
    ...    () => Array.from(document.querySelectorAll('[id^="${menu_base}/menu["]')).filter(e => e.offsetParent !== null && e.id.slice('${menu_base}/menu['.length).indexOf('/') === -1).map(e => e.id)
    ${logoff_item}=    Set Variable    ${items}[-1]
    Click    css=[id="${logoff_item}"]
    Sid Should Be Visible    ${WEBGUI_POPUP_CONFIRM_SID}
    Click Sid    ${WEBGUI_POPUP_CONFIRM_SID}
    Wait For Function    () => document.querySelectorAll('[lsdata]').length === 0
    ...    timeout=${WEBGUI_TIMEOUT}

Close WebGui
    [Documentation]    Ferme le navigateur, après un log off best-effort si une
    ...                session WebGUI est encore rendue (ne jamais accumuler de
    ...                sessions GUI serveur). Prévu pour Suite Teardown, miroir
    ...                WebGUI de `Close SAP`.
    ${status}    ${still}=    Run Keyword And Ignore Error
    ...    Evaluate JavaScript    ${None}    () => document.querySelectorAll('[lsdata]').length
    IF    '${status}' == 'PASS'
        IF    ${still} > 0
            Run Keyword And Ignore Error    Log Off WebGui
        END
    END
    Close Browser

# --- alias miroir ECC (mêmes noms que ecc_keywords.resource) ------------------
# Un test multi-canal peut ainsi utiliser le même vocabulaire quel que soit le
# canal ; en cas d'import des deux resources dans une même suite, préfixer par le
# nom du fichier (`fiori_keywords.Close SAP`).

Open SAP And Log In
    [Documentation]    Alias miroir du mot-clé ECC du même nom : ouvre le launchpad /
    ...                l'application Fiori et s'authentifie si des identifiants sont
    ...                fournis. Délègue à `Open Fiori Launchpad`.
    [Arguments]    ${url}=${FIORI_BASE_URL}    ${user}=${FIORI_USER}    ${password}=${FIORI_PASSWORD}
    Open Fiori Launchpad    ${url}    ${user}    ${password}

Popup Is Present
    [Documentation]    Vrai si une boîte de dialogue UI5 (``sap.m.Dialog``, MessageBox
    ...                incluses) est actuellement rendue. Miroir du `Popup Is Present`
    ...                ECC (``wnd[1]``) : retourne un booléen sans jamais lever et
    ...                sans attendre.
    ${count}=    Get Ui5 Match Count    controlType=sap.m.Dialog
    RETURN    ${{ ${count} > 0 }}

Confirm Popup
    [Documentation]    Miroir du `Confirm Popup` ECC : confirme la boîte de dialogue
    ...                UI5 ouverte en cliquant son bouton ``${button}`` (OK par défaut).
    ...                Ne fait rien si aucun dialogue n'est ouvert.
    [Arguments]    ${button}=OK
    ${present}=    Popup Is Present
    IF    ${present}    Confirm Ui5 Dialog    ${button}

Cancel Popup
    [Documentation]    Miroir du `Cancel Popup` ECC : ferme la boîte de dialogue UI5
    ...                ouverte par son bouton d'annulation (``${button}``, « Cancel »
    ...                par défaut). Ne fait rien si aucun dialogue n'est ouvert.
    [Arguments]    ${button}=Cancel
    ${present}=    Popup Is Present
    IF    ${present}    Cancel Ui5 Dialog    ${button}

Close SAP
    [Documentation]    Alias miroir du `Close SAP` ECC : ferme le navigateur.
    ...                Prévu pour Suite Teardown d'un test multi-canal.
    Close Fiori
