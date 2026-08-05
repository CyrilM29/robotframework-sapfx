*** Settings ***
Documentation       Live ECC smoke test: validated against a real ABAP Platform A4H
...                 (ABAP Platform Trial 1909 in Docker). Drives SAP GUI via the
...                 Scripting API: login, transaction navigation checked with the
...                 locale-independent current-transaction code, table browse in SE16,
...                 and clear failure on an unknown transaction.
...
...                 Requires a reachable system + scripting enabled server-side
...                 (sapgui/user_scripting = TRUE) and client-side. See
...                 docs/ecc-validation.md. Connection can be a SAP Logon entry name
...                 OR a connection string (/H/host/S/3200). Run e.g.:
...
...                   robot --pythonpath src ^
...                     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                     -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 ^
...                     tests/robot/ecc_smoke.robot
...
...                 (`Secret` is the Robot Framework 7.4 typed-variable syntax: the
...                 password value then never appears in logs, even at TRACE level.)
...
...                 FR : Test smoke ECC en live, validé contre un vrai ABAP Platform
...                 A4H (ABAP Platform Trial 1909 sous Docker). Pilote SAP GUI via
...                 l'API Scripting : login, navigation de transaction vérifiée par le
...                 code de transaction courant (indépendant de la langue), parcours
...                 de la table T000 dans SE16, et échec explicite sur transaction
...                 inconnue. Prérequis : scripting activé serveur
...                 (sapgui/user_scripting = TRUE) et client (voir docs/ecc-validation.fr.md).

Resource            ../../resources/ecc_keywords.resource

Suite Setup         Open SAP And Log In
Suite Teardown      Close SAP


*** Test Cases ***
Login Lands On SAP Easy Access
    [Documentation]    Le login aboutit sur le menu (transaction SESSION_MANAGER).
    ${tx}=    Get Current Transaction
    Should Be Equal    ${tx}    SESSION_MANAGER

Navigate To SE16 Data Browser
    [Documentation]    Go To Transaction démarre bien SE16 (vérif locale-indépendante).
    Go To Transaction    SE16
    ${tx}=    Get Current Transaction
    Should Be Equal    ${tx}    SE16

Browse Table T000 In SE16
    [Documentation]    Saisit la table T000, exécute, et vérifie l'écran de résultats.
    Go To Transaction    SE16
    Input Text    ${SE16_TABLE_FIELD}    T000
    Send Vkey     0
    Send Vkey     8
    Wait Until Busy Done
    ${title}=    Get Window Title    wnd[0]
    Should Contain    ${title}    T000

Read ALV Grid In SM50 Process Overview
    [Documentation]    Exerce tout le mixin grille ALV sur une vraie GridView : la vue
    ...                des work processes (SM50). Résolution de colonne par titre,
    ...                lecture de cellule par titre, et Read Grid -> liste de dicts.
    Go To Transaction    SM50
    Wait Until Element Present    ${SM50_GRID}
    ${count}=    Get Row Count    ${SM50_GRID}
    Should Be True    ${count} >= 1
    ${col}=    Get Column Id By Title    ${SM50_GRID}    Type
    Should Contain    ${col}    TYPE
    ${type0}=    Get Cell Value By Column Title    ${SM50_GRID}    0    Type
    Should Not Be Empty    ${type0}
    ${rows}=    Read Grid    ${SM50_GRID}    max_rows=3
    Length Should Be    ${rows}    3
    Should Not Be Empty    ${rows}[0][Type]

Unknown Transaction Is Reported
    [Documentation]    Une transaction inexistante ne démarre pas -> erreur explicite.
    ...                (En live, ce cas renvoie un statut de type 'S', d'où la
    ...                vérification par la transaction active et non par le type.)
    Run Keyword And Expect Error    *ZZZNOTREAL*
    ...    Go To Transaction    ZZZNOTREAL
