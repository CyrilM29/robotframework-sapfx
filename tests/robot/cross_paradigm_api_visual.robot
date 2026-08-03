*** Settings ***
Documentation       Test cross-canal **API ↔ GUI + assertion visuelle** — le 3ᵉ volet, après
...                 les campagnes ECC (SAP GUI) et Fiori (web). Un même fait métier (le
...                 nombre de produits EPM) est vérifié par TROIS canaux indépendants du
...                 MÊME système A4H :
...
...                 * **API** — le service OData Gateway embarqué ``SEPMRA_SHOP`` : ``$count``
...                   de l'entity set ``Products`` et lecture d'entités (``SapApiLibrary``,
...                   stdlib pure, HTTP — aucune dépendance nouvelle).
...                 * **GUI** — la table sous-jacente ``SNWD_PD`` comptée par SE16
...                   (« Number of Entries », ``SapEccLibrary``).
...                 * **VISUEL** — l'écran SE16 qui produit ce compte est comparé, par
...                   **empreinte perceptuelle** (dHash), à une baseline committée
...                   (``Screen Should Match Baseline``) : le canal *pixels* atteste que le
...                   rendu de l'écran n'a pas dérivé — ce que ni l'API ni l'API Scripting ne
...                   voient.
...
...                 C'est le patron recommandé du projet : recouper la donnée par l'API,
...                 ne passer par l'écran que pour ce qu'on teste, et sceller le rendu par
...                 l'assertion visuelle. Suite AUTO-SUFFISANTE (aucune resource/suite
...                 existante importée). Tout relevé PUIS validé live vs A4H (2026-07-17) :
...                 ``$count`` OData = 205 = SE16 ``SNWD_PD`` ; empreinte de l'écran de
...                 sélection déterministe (distance de Hamming 0 entre deux navigations).
...
...                 Le canal visuel exige l'extra ``visual`` (Pillow). La baseline est créée
...                 au 1er passage (WARNING) puis committée ; ``.gitignore`` exclut ``*.png``
...                 — ajouter ``tests/robot/visual_baselines/*.png`` à sa liste d'exceptions
...                 pour committer la référence.
...
...                 Exécution (`Secret` RF 7.4 : le mot de passe typé dès la ligne de
...                 commande n'apparaît jamais dans les logs, même en TRACE) :
...                 | robot --pythonpath src
...                 |     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER
...                 |     -v "SAP_PASSWORD: Secret:<motdepasse>" -v SAP_CLIENT:001 -v SAP_LANGUAGE:EN
...                 |     tests/robot/cross_paradigm_api_visual.robot

Library             SapApiLibrary
Library             SapEccLibrary    screenshots_on_error=${True}    default_timeout=30s
Library             Collections

Suite Setup         Connect All Channels
Suite Teardown      Disconnect All Channels


*** Variables ***
# --- Connexion GUI (surchargeable via -v) ---------------------------------------
${SAP_CONNECTION}       /H/vhcala4hci/S/3200
${SAP_USER}             DEVELOPER
${SAP_PASSWORD}         ${EMPTY}      # OBLIGATOIRE : fournir via -v "SAP_PASSWORD: Secret:<motdepasse>"
${SAP_CLIENT}           001
${SAP_LANGUAGE}         EN

# --- Canal API (Gateway OData v2 embarquée de l'A4H, HTTP mappé par le conteneur) ---
${A4H_API_URL}          http://vhcala4hci:50000
${EPM_PRODUCTS_PATH}    /sap/opu/odata/sap/SEPMRA_SHOP/Products    # service « Shop » du modèle EPM
${EPM_PRODUCTS_TABLE}    SNWD_PD                                   # la table que ce service projette

# --- Localisateurs SAP GUI (jamais dans les cas de test) ------------------------
${SE16_TABLE_FIELD}     wnd[0]/usr/ctxtDATABROWSE-TABLENAME
${SE16_COUNT_BUTTON}    wnd[0]/tbar[1]/btn[31]     # « Number of Entries » — fiable même à 0
${SE16_COUNT_POPUP}     wnd[1]/usr/txtG_DBCOUNT
${MULTI_LOGON_RADIO}    wnd[1]/usr/radMULTI_LOGON_OPT1

# --- Canal visuel ---------------------------------------------------------------
# Baseline colocalisée avec la suite (tests/robot/visual_baselines/), indépendante du cwd.
${VISUAL_BASELINE_DIR}    ${CURDIR}/visual_baselines
${VISUAL_BASELINE_NAME}    snwd_pd_selection_screen
${VISUAL_THRESHOLD}     ${5}      # distance de Hamming tolérée (fresh-to-fresh mesuré à 0)


*** Test Cases ***
Product Count Agrees Across API And GUI Channels
    [Documentation]    Recoupement cross-paradigme : le compte GUI (SE16 « Number of Entries »
    ...                sur ``SNWD_PD``) et le compte API (``$count`` OData de l'entity set
    ...                ``Products``) du MÊME système doivent coïncider. Toute divergence
    ...                trahit un service qui filtre, une donnée fantôme, ou un mandant croisé.
    [Tags]    api    gui    cross
    ${gui_count}=    Count Table Entries    ${EPM_PRODUCTS_TABLE}
    Should Be True    ${gui_count} > 0
    ...    msg=Table ${EPM_PRODUCTS_TABLE} vide — données EPM absentes sur ce système ?
    ${api_count}=    Get Odata Count    ${EPM_PRODUCTS_PATH}    alias=a4h
    Should Be Equal As Integers    ${api_count}    ${gui_count}
    ...    msg=OData $count (${api_count}) ≠ SE16 ${EPM_PRODUCTS_TABLE} (${gui_count}).
    Log    Produits EPM : ${api_count} via OData == ${gui_count} via SE16.

OData Products Expose Their Key Fields
    [Documentation]    Profondeur API : au-delà du compte, on lit quelques entités et on
    ...                vérifie que chacune porte ses champs clés — noms de propriétés
    ...                techniques, donc indépendants de la langue (``Id``, ``Name``,
    ...                ``Price``). Le service n'est pas qu'un compteur : il projette des données.
    [Tags]    api
    ${products}=    Get Odata Entities    ${EPM_PRODUCTS_PATH}    alias=a4h    top=5
    Should Not Be Empty    ${products}    msg=Aucun produit renvoyé par OData.
    FOR    ${product}    IN    @{products}
        Dictionary Should Contain Key    ${product}    Id
        Dictionary Should Contain Key    ${product}    Name
        Dictionary Should Contain Key    ${product}    Price
    END
    Log    ${products}[0][Id] — ${products}[0][Name] — ${products}[0][Price] ${products}[0][CurrencyCode]

SE16 Product Screen Matches Its Visual Baseline
    [Documentation]    Assertion **visuelle** : l'écran SE16 qui a servi au comptage GUI est
    ...                comparé à une baseline committée par empreinte perceptuelle (dHash).
    ...                1er passage = baseline créée (WARNING, PNG à committer) ; ensuite,
    ...                distance de Hamming <= ``${VISUAL_THRESHOLD}``. ``mask_elements=auto``
    ...                neutralise la barre de statut / le titre (zones volatiles) avant hachage.
    ...                Le screenshot est aussi incrusté dans le log (preuve visuelle).
    [Tags]    gui    visual
    Open Table In SE16    ${EPM_PRODUCTS_TABLE}
    Log Screenshot    Écran de sélection SE16 de ${EPM_PRODUCTS_TABLE} (source du compte GUI)
    Screen Should Match Baseline    ${VISUAL_BASELINE_NAME}
    ...    threshold=${VISUAL_THRESHOLD}    baseline_directory=${VISUAL_BASELINE_DIR}
    ...    mask_elements=auto


*** Keywords ***
Connect All Channels
    [Documentation]    Suite Setup. Ouvre les DEUX canaux vers le même A4H : session GUI
    ...                (SAP GUI Scripting) et session API (OData HTTP, auth Basic + sap-client).
    ...                Le mot de passe n'est jamais journalisé.
    # Should Not Be Equal (et non Should Not Be Empty) : tolère un mot de passe
    # de type Secret RF 7.4, qui n'a pas de longueur mesurable.
    Should Not Be Equal    ${SAP_PASSWORD}    ${EMPTY}
    ...    msg=SAP_PASSWORD est vide : fournissez-le via -v "SAP_PASSWORD: Secret:<motdepasse>".
    # Canal GUI
    Open Sap Logon
    Connect To Session With Retry
    IF    "${SAP_CONNECTION}".startswith("/")
        Open Connection By String    ${SAP_CONNECTION}
    ELSE
        Open Connection    ${SAP_CONNECTION}
    END
    Maximize Window
    Input Text    wnd[0]/usr/txtRSYST-MANDT    ${SAP_CLIENT}
    Input Text    wnd[0]/usr/txtRSYST-BNAME    ${SAP_USER}
    ${previous_level}=    Set Log Level    NONE
    Input Password    wnd[0]/usr/pwdRSYST-BCODE    ${SAP_PASSWORD}
    Set Log Level    ${previous_level}
    Input Text    wnd[0]/usr/txtRSYST-LANGU    ${SAP_LANGUAGE}
    Send Vkey    0
    Wait Until Busy Done
    Handle Multiple Logon Popup
    # Canal API (même identifiants, même mandant)
    Open Api Session    ${A4H_API_URL}    user=${SAP_USER}    password=${SAP_PASSWORD}
    ...    sap_client=${SAP_CLIENT}    alias=a4h

Disconnect All Channels
    [Documentation]    Suite Teardown. Ferme les sessions API puis quitte le GUI et arrête le
    ...                Logon Pad. Chaque étape est tolérante aux erreurs pour ne pas masquer
    ...                l'échec réel d'un test.
    Run Keyword And Ignore Error    Close All Api Sessions
    Run Keyword And Ignore Error    Run Transaction    /nex
    Close Sap Logon

Handle Multiple Logon Popup
    [Documentation]    Choisit « continuer avec cette connexion » si SAP affiche le dialogue
    ...                de connexion multiple ; sinon ne fait rien.
    ${present}=    Run Keyword And Return Status    Element Should Be Present    ${MULTI_LOGON_RADIO}
    IF    ${present}
        Select Radio Button    ${MULTI_LOGON_RADIO}
        Click Element    wnd[1]/tbar[0]/btn[0]
        Wait Until Busy Done
    END

Start Transaction
    [Documentation]    Ouvre un code transaction et attend la stabilisation de l'écran.
    [Arguments]    ${tcode}
    Run Transaction    ${tcode}
    Wait Until Busy Done

Open Table In SE16
    [Documentation]    Ouvre SE16 sur ``${table}`` et atteint son écran de sélection (par
    ...                navigation fraîche — reproductible au pixel près, ce qui rend l'écran
    ...                baselinable). Échoue si SE16 rejette le nom (message de type ``E``).
    [Arguments]    ${table}
    Start Transaction    SE16
    Input Text    ${SE16_TABLE_FIELD}    ${table}
    Send Vkey    0
    Wait Until Busy Done
    ${type}    ${message}=    Get Status Message
    IF    '${type}' == 'E'
        Fail    SE16 refuse la table '${table}' (message de type E) : ${message}
    END

Count Table Entries
    [Documentation]    Compte les entrées de ``${table}`` via SE16 > « Number of Entries »
    ...                (fiable même à 0). Renvoie un entier ; les séparateurs de milliers du
    ...                profil utilisateur sont retirés.
    [Arguments]    ${table}
    Open Table In SE16    ${table}
    Click Element    ${SE16_COUNT_BUTTON}
    Wait Until Busy Done
    Wait Until Element Present    ${SE16_COUNT_POPUP}
    ${raw}=    Get Value    ${SE16_COUNT_POPUP}
    Send Vkey    12    window=1
    Wait Until Busy Done
    ${count}=    Evaluate    int(''.join(c for c in $raw if c.isdigit()) or 0)
    RETURN    ${count}
