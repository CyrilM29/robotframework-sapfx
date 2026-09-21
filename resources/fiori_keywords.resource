*** Settings ***
Documentation       **EXEMPLE À PERSONNALISER** : ce fichier porte le vocabulaire
...                 métier du LABORATOIRE de ce dépôt (identifiants, chemins, noms
...                 de tables et de modules relevés live sur SES cibles). Beaucoup
...                 s'y réutilise tel quel sur un autre système (écrans et services
...                 standard), mais rien n'y fait autorité : à VÉRIFIER sur votre
...                 cible et à adapter à votre métier. Ce qui fait foi partout,
...                 c'est `src/`, les bibliothèques, qui portent les capacités :
...                 voir `resources/README.md`.
...
...                 Mots-clés web Fiori / S/4HANA lisibles métier.
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
Library             Collections
# Import sans argument (défaut ui5_timeout=15s) : une suite qui veut un autre
# budget appelle `Set Ui5 Timeout` (0.6.1) au lieu de ré-importer la lib avec
# d'autres arguments : Robot ignorerait le second import avec un warning.
Library             SapFioriLibrary
# Primitives pures atteintes par un KEYWORD (décision DDIC 2026-08-17) :
# `Displayed Count` normalise un compteur affiché (séparateurs de milliers).
Library             sapfx_common.robot_args
# Le contrat d'extraction d'un tableau, COMMUN aux trois canaux : la règle de
# refus d'un relevé amputé vit à un seul endroit, sans quoi chaque canal la
# réécrit et finit par l'oublier.
Library             sapfx_common.table_extract
# Déballage d'un `Secret` RF 7.4 à la FRONTIÈRE (ici l'en-tête HTTP qui porte
# l'authentification) : par un keyword, jamais par un `Evaluate getattr(...)`
# qui sortirait la valeur claire dans l'espace des variables. `Basic Auth
# Header` est du savoir de protocole, donc de la bibliothèque.
Library             sapfx_common.secrets
Library             sapfx_common.auth_flows
# Le message d'un critère de sélection absent, qui LISTE ceux que l'écran
# porte vraiment : un nom manquant est le plus souvent un champ écarté du
# choix des champs de sélection (réglage persistant par utilisateur), pas une
# faute de frappe, et la liste tranche sans retourner sur le système.
Library             sapfx_common.webgui_selection


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
${WEBGUI_MAX_HITS_SID}              wnd[0]/usr/txtMAX_SEL    # écran de sélection : « Maximum No. of Hits »
${WEBGUI_EXECUTE_SID}               wnd[0]/tbar[1]/btn[8]    # écran de sélection : « Execute » (F8)
${WEBGUI_COUNT_RESULT_SID}          wnd[1]/usr/txtG_DBCOUNT    # compteur du popup : SPAN texte, pas un input
${WEBGUI_POPUP_CLOSE_SID}           wnd[1]/tbar[0]/btn[0]    # popup : « Close (Enter) »
${WEBGUI_POPUP_CONFIRM_SID}         wnd[1]/usr/btnSPOP-OPTION1    # popup SPOP : « Yes »
${WEBGUI_MORE_BUTTON_SELECTOR}      css=[id$="-moreButton"] >> visible=true    # bandeau : bouton « More » (id u… dynamique par écran, jamais en dur)
${WEBGUI_SYSINFO_DYNPRO_SELECTOR}    css=[id="sysInfoAreaMenuItemSAPITS_MBAR_DYNPRO"]    # zone info système : ligne dynpro (id stable)
# --- Vocabulaire métier du Data Browser en WebGUI (convention 1 : un nom de
# transaction, de table ou de colonne vit ICI et jamais dans une suite).
${WEBGUI_DATA_BROWSER_TCODE}        SE16    # le Data Browser
${WEBGUI_MESSAGE_TABLE}             T100    # les textes de messages système : présente sur tout système SAP
${WEBGUI_MESSAGE_LANGUAGE_COLUMN}    SPRSL    # la langue d'un texte de message : la colonne qui ne peut pas être vide


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
    ...                passait avant le rendu. Le prédicat vit dans la bibliothèque
    ...                (`Ui5 Runtime Is Ready`, lecture pure sans bundle,
    ...                convention #12) ; ce keyword n'en garde que l'attente.
    Wait Until Keyword Succeeds    15s    0.5s    Ui5 Runtime Should Be Ready

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
    ...
    ...                `extra_headers` pose des en-têtes sur le contexte, ce
    ...                qui permet notamment de porter une AUTHENTIFICATION HTTP
    ...                directe et de court-circuiter le formulaire. Ce n'est pas
    ...                un raccourci de confort : mesuré le 2026-09-15, un des
    ...                deux systèmes du banc rend un formulaire de connexion
    ...                dont TOUS les champs restent à 0x0, en HTTP comme en
    ...                HTTPS, donc inatteignables par n'importe quel moteur.
    ...                Voir `Open WebGui Session`, qui choisit la voie.
    ...
    ...                `ignore_https_errors` est indispensable devant un
    ...                certificat auto-signé, ce qu'est celui d'un conteneur de
    ...                laboratoire. NB d'orthographe : la bibliothèque Browser
    ...                refuse `ignoreHttpsErrors`, la forme est
    ...                `ignoreHTTPSErrors`.
    [Arguments]    ${url}=${WEBGUI_URL}    ${browser}=${BROWSER}    ${headless}=${HEADLESS}
    ...    ${extra_headers}=${None}    ${ignore_https_errors}=${False}
    New Browser    ${browser}    headless=${headless}
    IF    $extra_headers is None
        New Context    ignoreHTTPSErrors=${ignore_https_errors}
    ELSE
        New Context    ignoreHTTPSErrors=${ignore_https_errors}
        ...    extraHTTPHeaders=${extra_headers}
    END
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
    ...                La perception vit dans la bibliothèque (`Webgui Is Present`).
    Wait Until Keyword Succeeds    ${WEBGUI_TIMEOUT}    0.5s
    ...    WebGui Elements Should Be Present

WebGui Elements Should Be Present
    [Documentation]    Assertion instantanée : au moins un élément WebGUI
    ...                (`lsdata`) est rendu. La forme à sonder dans un
    ...                `Wait Until Keyword Succeeds`.
    ${present}=    Webgui Is Present
    Should Be True    ${present}    msg=Aucun élément WebGUI (lsdata) rendu dans la portée courante.

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

Open WebGui Session
    [Documentation]    Ouvre une session WebGUI RENDUE, par la voie qui convient
    ...                à la cible, et rend l'identité du système atteint.
    ...
    ...                Deux stratégies NOMMÉES, jamais un `IF` sur le système
    ...                (même règle que les page objects multi-release) :
    ...
    ...                - `form` : le formulaire de connexion ICF, rempli au
    ...                  moteur `dom` (rôle + nom accessible). La voie nominale.
    ...                - `basic` : l'authentification HTTP portée par le
    ...                  contexte du navigateur, qui court-circuite le
    ...                  formulaire.
    ...
    ...                La seconde n'est pas un raccourci : mesuré le 2026-09-15,
    ...                un des deux systèmes du banc rend un formulaire dont TOUS
    ...                les champs restent à 0x0 sans parent de mise en page, en
    ...                HTTP comme en HTTPS, donc hors d'atteinte de n'importe
    ...                quel moteur (14 champs, 0 visible), là où l'autre en rend
    ...                5 visibles. La même adresse répond en revanche
    ...                parfaitement à une authentification d'en-tête. Un test
    ...                qui ne connaîtrait que la voie formulaire conclurait
    ...                « cible injoignable » sur un système disponible.
    ...
    ...                **La CAUSE n'est pas établie.** L'avertissement « No
    ...                switch to HTTPS occurred, so it is not secure to send a
    ...                password » avait d'abord paru l'expliquer ; une seconde
    ...                mesure l'a trouvé AUSSI sur le système dont le formulaire
    ...                fonctionne, donc il accompagne toute page servie en clair
    ...                et n'explique rien. Le seul écart propre au système muet
    ...                est qu'il rend son fragment de repli sans script comme du
    ...                TEXTE. Consigné comme indice, pas comme cause : la
    ...                stratégie se choisit sur le CONSTAT que le formulaire est
    ...                inatteignable, pas sur une explication.
    [Arguments]    ${url}    ${user}    ${password}    ${strategy}=form
    ...    ${ignore_https_errors}=${False}
    IF    '${strategy}' == 'basic'
        # L'identifiant part dans un EN-TÊTE et non dans le dictionnaire
        # `httpCredentials` de la bibliothèque Browser : celui-ci n'accepte
        # qu'une variable par la syntaxe `$variable`, qui ne résout PAS une
        # variable créée dans un keyword utilisateur (vérifié le 2026-09-15).
        # L'en-tête, lui, passe partout, et la construction de l'identifiant
        # est du savoir de protocole, donc de la bibliothèque.
        ${previous_log_level}=    Set Log Level    NONE
        ${autorisation}=    Basic Auth Header    ${user}    ${password}
        ${entetes}=    Create Dictionary    Authorization=${autorisation}
        Open WebGui    ${url}    ignore_https_errors=${ignore_https_errors}
        ...    extra_headers=${entetes}
        Set Log Level    ${previous_log_level}
        WebGui Should Be Rendered
    ELSE IF    '${strategy}' == 'form'
        Open WebGui    ${url}    ignore_https_errors=${ignore_https_errors}
        Log In To WebGui    ${user}    ${password}
    ELSE
        Fail    Stratégie de connexion WebGUI inconnue : « ${strategy} ». Les stratégies connues sont « form » (formulaire ICF) et « basic » (authentification d'en-tête, pour une cible dont le formulaire ne s'affiche pas).
    END
    ${identite}=    Read WebGui Session Identity
    RETURN    ${identite}

WebGui Identity Should Be Readable
    [Documentation]    Assertion instantanée : la zone info système nomme un
    ...                identifiant système. La forme à sonder dans un
    ...                `Wait Until Keyword Succeeds`, et elle est nécessaire :
    ...                le bandeau se rend APRÈS les premiers éléments `lsdata`,
    ...                donc une lecture d'identité enchaînée sur le login passe
    ...                parfois et échoue parfois, en rendant une identité VIDE
    ...                plutôt qu'une erreur (course gagnée deux fois puis perdue
    ...                le 2026-09-15). Retourne l'identité lue.
    ${identite}=    Get Webgui Session Identity
    Should Not Be Empty    ${identite}[system_id]
    ...    msg=La zone info système ne nomme encore aucun identifiant système : le bandeau n'est pas rendu.
    RETURN    ${identite}

Read WebGui Session Identity
    [Documentation]    L'identité du système derrière la session, une fois le
    ...                bandeau rendu. C'est la forme à employer dans un Suite
    ...                Setup, là où `Get Webgui Session Identity` (bibliothèque)
    ...                est la lecture instantanée.
    ${identite}=    Wait Until Keyword Succeeds    ${WEBGUI_TIMEOUT}    0.5s
    ...    WebGui Identity Should Be Readable
    RETURN    ${identite}

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
    ${count}=    Displayed Count    ${raw}
    RETURN    ${count}

Close WebGui Popup
    [Documentation]    Ferme le popup WebGUI courant (`wnd[1]`) par son bouton
    ...                « Close (Enter) » et sonde jusqu'à ce que plus aucun élément
    ...                `wnd[1]/*` ne soit visible.
    Click Sid    ${WEBGUI_POPUP_CLOSE_SID}
    No WebGui Popup Should Be Visible

No WebGui Popup Should Be Visible
    [Documentation]    Sonde jusqu'à la disparition de tout élément WebGUI de la
    ...                fenêtre popup (`wnd[1]`), via la perception de la
    ...                bibliothèque (`Get Webgui Element Count    window=1`).
    Wait Until Keyword Succeeds    ${WEBGUI_TIMEOUT}    0.5s    WebGui Popup Should Be Gone

WebGui Popup Should Be Gone
    [Documentation]    Assertion instantanée : plus aucun élément VISIBLE de la
    ...                fenêtre popup `wnd[1]`. La forme à sonder dans un
    ...                `Wait Until Keyword Succeeds`.
    ${n}=    Get Webgui Element Count    window=1
    Should Be Equal As Integers    ${n}    0
    ...    msg=Le popup WebGUI (wnd[1]) est encore rendu (${n} élément(s) visibles).

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

Open WebGui Data Browser
    [Documentation]    Ouvre le Data Browser et vérifie qu'on y est. Le code
    ...                transaction vit ICI et non dans une suite (convention 1),
    ...                comme les noms de table et de colonne du vocabulaire
    ...                ci-dessus.
    [Arguments]    ${url}=${WEBGUI_URL}
    Go To WebGui Transaction    ${WEBGUI_DATA_BROWSER_TCODE}    ${url}
    WebGui Data Browser Should Be Open

Display WebGui Table Contents
    [Documentation]    Depuis l'écran initial du Data Browser (SE16), affiche le
    ...                CONTENU de `${table}` dans une grille ALV : nom de table,
    ...                « Table Contents », plafond de hits, puis « Execute ».
    ...                Miroir WebGUI de `Display Table Contents` (ECC).
    ...
    ...                Le plafond de hits n'est pas un détail d'ergonomie : la
    ...                grille WebGUI n'envoie au navigateur qu'une PAGE de
    ...                lignes (200 mesurées), donc au-delà la lecture est
    ...                partielle et rien dans les lignes rendues ne le montre.
    ...                Le laisser à sa valeur par défaut (200) garde la lecture
    ...                complète ; le monter est un choix à confronter ensuite à
    ...                `declared_rows`.
    [Arguments]    ${table}    ${max_hits}=${EMPTY}
    Fill Sid Input    ${WEBGUI_TABLE_NAME_SID}    ${table}
    Click Sid    ${WEBGUI_TABLE_CONTENTS_SID}
    Sid Should Be Visible    ${WEBGUI_COUNT_BUTTON_SID}    # écran de sélection rendu
    IF    '${max_hits}' != '${EMPTY}'
        Fill Sid Input    ${WEBGUI_MAX_HITS_SID}    ${max_hits}
    END
    Click Sid    ${WEBGUI_EXECUTE_SID}
    WebGui Should Be Rendered
    Wait Until Keyword Succeeds    ${WEBGUI_TIMEOUT}    0.5s    WebGui Grid Should Be Rendered

WebGui Grid Should Be Rendered
    [Documentation]    Assertion instantanée : une grille ALV est rendue et
    ...                porte au moins une colonne. La forme à sonder dans un
    ...                `Wait Until Keyword Succeeds` : le rendu d'une grille
    ...                suit l'aller-retour serveur, donc une lecture instantanée
    ...                part trop tôt et rendrait un relevé vide plutôt qu'une
    ...                erreur.
    ${info}=    Get Webgui Grid Info
    Should Not Be Empty    ${info}[columns]
    ...    msg=La grille WebGUI est rendue mais ne déclare aucune colonne.
    RETURN    ${info}

Display WebGui Table Contents With Filter
    [Documentation]    Comme `Display WebGui Table Contents`, mais applique
    ...                d'abord des critères nommés (``CHAMP=valeur``, ids
    ...                TECHNIQUES en majuscules) sur l'écran de sélection.
    ...                Miroir WebGUI de `Display Table Contents With Filter`
    ...                (ECC), à une différence près qui vaut d'être dite : ce
    ...                canal n'a AUCUN dictionnaire de positions à maintenir.
    ...
    ...                Les critères d'un écran de sélection SE16 sont
    ...                positionnels (``I1-LOW``, ``I2-LOW``…), leur ordre suit
    ...                le choix des champs de sélection (qui persiste par
    ...                utilisateur) et le préfixe de type varie d'un champ à
    ...                l'autre : `Get Webgui Selection Criteria` DÉRIVE la
    ...                carte de l'écran courant plutôt que de la déclarer, ce
    ...                qui rend ce keyword utilisable sur n'importe quelle
    ...                table sans rien ajouter ici.
    ...
    ...                Un champ absent de l'écran ÉCHOUE en listant les
    ...                critères réellement présents : sans cette garde, la
    ...                sélection partirait sans filtre et la grille rendrait
    ...                des lignes parfaitement lisibles qui ne sont pas
    ...                celles qu'on a demandées. Sans critère, équivaut à
    ...                `Display WebGui Table Contents`.
    ...
    ...                Ex. : ``Display WebGui Table Contents With Filter    SNWD_PD    PRODUCT_ID=AR-FB-1000``
    [Arguments]    ${table}    ${max_hits}=${EMPTY}    &{filters}
    Fill Sid Input    ${WEBGUI_TABLE_NAME_SID}    ${table}
    Click Sid    ${WEBGUI_TABLE_CONTENTS_SID}
    Sid Should Be Visible    ${WEBGUI_COUNT_BUTTON_SID}    # écran de sélection rendu
    # Les conditions lisent les VARIABLES (`$filters`, `$champ`) au lieu de
    # les interpoler : une valeur de filtre peut porter des apostrophes ou des
    # crochets, et la forme interpolée les injecterait dans l'expression
    # Python évaluée.
    IF    $filters
        ${criteres}=    Get Webgui Selection Criteria
        # La carte est DÉRIVÉE de l'écran : la journaliser est ce qui permet,
        # après coup, de distinguer « ce champ n'existe pas sur cette table »
        # d'une dérivation qui aurait silencieusement rétréci.
        ${releves}=    Get Length    ${criteres}
        Log    Critères dérivés de l'écran de sélection de ${table} : ${releves} (${criteres}).
        FOR    ${champ}    ${valeur}    IN    &{filters}
            IF    $champ not in $criteres
                ${message}=    Missing Criterion Message    ${champ}    ${criteres}
                Fail    ${message} Table ${table}.
            END
            Fill Sid Input    ${criteres}[${champ}]    ${valeur}
        END
    END
    IF    '${max_hits}' != '${EMPTY}'
        Fill Sid Input    ${WEBGUI_MAX_HITS_SID}    ${max_hits}
    END
    Click Sid    ${WEBGUI_EXECUTE_SID}
    WebGui Should Be Rendered
    Wait Until Keyword Succeeds    ${WEBGUI_TIMEOUT}    0.5s    WebGui Grid Should Be Rendered

Extract Displayed WebGui Grid
    [Documentation]    Lit la grille ALV affichée et rend le relevé AVEC son
    ...                contrat, sous la forme commune aux trois canaux
    ...                (`Build Table Extract`) : lignes, colonnes TECHNIQUES,
    ...                titres affichés, total DÉCLARÉ par la grille.
    ...
    ...                Le jugement n'est pas fait ici : `Table Extract Should Be
    ...                Complete` est la garde, et elle s'appelle avant toute
    ...                écriture. Miroir WebGUI d'`Extract Displayed Report`
    ...                (ECC).
    [Arguments]    ${sid}=${EMPTY}    ${key}=${EMPTY}    ${source}=${EMPTY}
    ${grille}=    Read Webgui Grid    ${sid}
    ${nom}=    Set Variable If    '${source}' == '${EMPTY}'
    ...    grille WebGUI ${grille}[container]    ${source}
    ${extrait}=    Build Table Extract    ${grille}[rows]    columns=${grille}[columns]
    ...    headers=${grille}[headers]    declared_rows=${grille}[declared_rows]
    ...    source=${nom}    key=${key}
    # Le contrat que la GRILLE publie voyage avec le relevé : il porte de quoi
    # asserter que le balayage des titres a fonctionné (`headers_found`, seule
    # chose qui distingue des titres identiques aux identifiants d'un repli
    # silencieux) et de quoi journaliser ce que la cible a réellement déclaré,
    # au lieu de le raconter dans une documentation.
    Set To Dictionary    ${extrait}    headers_found=${grille}[headers_found]
    ...    candidates=${grille}[candidates]    visible_rows=${grille}[visible_rows]
    ...    scrolling=${grille}[scrolling]
    ...    client_cell_threshold=${grille}[client_cell_threshold]
    ...    first_row_index=${grille}[first_row_index]
    RETURN    ${extrait}

Log Off WebGui
    [Documentation]    Déconnexion propre : bouton « More » du bandeau, menu System
    ...                repéré par POSITION RELATIVE (avant-dernier : la barre de menus
    ...                varie par transaction), dernier item (Log Off), confirmation
    ...                SPOP, puis assertion 100 % locale-indépendante de fin de
    ...                session : plus AUCUN élément `lsdata`.
    ...
    ...                `budget` borne chaque attente du déroulé, y compris les
    ...                deux étapes qui ne répondent qu'au timeout du navigateur
    ...                (le clic sur « More » et l'attente du popup) : c'est la
    ...                PREMIÈRE de ces deux-là qui n'aboutit pas sur la cible
    ...                concernée, donc les borner à moitié ne bornait rien. Le défaut
    ...                convient à une déconnexion qu'on veut voir aboutir ; un
    ...                teardown, lui, en passe un court, parce qu'un déroulé qui
    ...                ne peut pas aboutir sur une cible donnée y coûterait
    ...                plusieurs minutes d'acharnement. Mesuré le 2026-09-15 sur
    ...                une campagne à cinq cibles : 361 s de tentatives en échec
    ...                pour une cible, soit les deux tiers des 535 s de la
    ...                campagne entière, là où la cible voisine se déconnectait
    ...                en 1,2 s.
    [Arguments]    ${budget}=${WEBGUI_TIMEOUT}
    # Le budget borne AUSSI les deux étapes qui passent par la bibliothèque
    # Browser (le clic sur « More », et l'attente du popup de confirmation) :
    # celles-là n'écoutent que le timeout du navigateur, et la PREMIÈRE est
    # justement celle qui n'aboutit pas sur la cible qui a motivé ce
    # paramètre. Sans cette bascule, un teardown qui promet dix secondes en
    # coûtait quarante-cinq.
    ${timeout_precedent}=    Set Browser Timeout    ${budget}
    TRY
        Click    ${WEBGUI_MORE_BUTTON_SELECTOR}
        ${menu_ids}=    Wait Until Keyword Succeeds    ${budget}    0.5s
        ...    WebGui Menu Bar Entries
        ${system_menu}=    Set Variable    ${menu_ids}[-2]    # System = avant-dernier, Help = dernier
        Click    css=[id="${system_menu}"]
        # Items DIRECTS du menu System seulement (pas les sous-menus, que la
        # bibliothèque écarte). Log Off = dernier item (convention SAP).
        ${items}=    Wait Until Keyword Succeeds    ${budget}    0.5s
        ...    WebGui Open Menu Items    ${system_menu}
        ${logoff_item}=    Set Variable    ${items}[-1]
        Click    css=[id="${logoff_item}"]
        Sid Should Be Visible    ${WEBGUI_POPUP_CONFIRM_SID}
        Click Sid    ${WEBGUI_POPUP_CONFIRM_SID}
        Wait Until Keyword Succeeds    ${budget}    0.5s
        ...    WebGui Session Should Be Over
    FINALLY
        Set Browser Timeout    ${timeout_precedent}
    END

WebGui Menu Bar Entries
    [Documentation]    Menus VISIBLES de la barre de menus WebGUI (perception
    ...                `List Webgui Menus`), échec quand la barre n'est pas
    ...                encore rendue : la forme à sonder dans un
    ...                `Wait Until Keyword Succeeds`.
    ${ids}=    List Webgui Menus
    Should Not Be Empty    ${ids}    msg=La barre de menus WebGUI n'est pas (encore) rendue.
    RETURN    ${ids}

WebGui Open Menu Items
    [Documentation]    Items directs et visibles du menu WebGUI ouvert
    ...                (`List Webgui Menu Items`), échec tant que le menu
    ...                n'est pas déroulé : la forme à sonder.
    [Arguments]    ${menu_id}
    ${items}=    List Webgui Menu Items    ${menu_id}
    Should Not Be Empty    ${items}    msg=Le menu ${menu_id} n'est pas (encore) déroulé.
    RETURN    ${items}

WebGui Session Should Be Over
    [Documentation]    Assertion 100 % locale-indépendante de fin de session :
    ...                plus AUCUN élément `lsdata` dans la page.
    ${n}=    Get Webgui Element Count
    Should Be Equal As Integers    ${n}    0
    ...    msg=La session WebGUI est encore rendue (${n} élément(s) lsdata).

Close WebGui
    [Documentation]    Ferme le navigateur, après un log off best-effort si une
    ...                session WebGUI est encore rendue (ne jamais accumuler de
    ...                sessions GUI serveur). Prévu pour Suite Teardown, miroir
    ...                WebGUI de `Close SAP`.
    ...
    ...                La tentative de déconnexion est BORNÉE (`logoff_budget`,
    ...                court par défaut) : un teardown doit rendre la main. Sur
    ...                une cible dont le déroulé de déconnexion n'aboutit pas,
    ...                le budget nominal coûtait 361 s d'acharnement, mesuré le
    ...                2026-09-15. Quand elle échoue, la session serveur est
    ...                laissée à EXPIRER et le journal le DIT : une session
    ...                abandonnée en silence est une ressource qu'on croit
    ...                rendue.
    [Arguments]    ${logoff_budget}=10s
    ${status}    ${still}=    Run Keyword And Ignore Error
    ...    Get Webgui Element Count
    IF    '${status}' == 'PASS'
        IF    ${still} > 0
            ${verdict}    ${detail}=    Run Keyword And Ignore Error
            ...    Log Off WebGui    budget=${logoff_budget}
            IF    '${verdict}' != 'PASS'
                Log    Déconnexion WebGUI NON aboutie en ${logoff_budget} : la session serveur est laissée à expirer. Cause : ${detail}    WARN
            END
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
