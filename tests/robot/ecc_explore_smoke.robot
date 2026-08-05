*** Settings ***
Documentation       Live ECC *exploratory* smoke: captured interactively via rf-mcp
...                 (RobotMCP) against a real ABAP Platform A4H (ABAP Platform Trial
...                 in Docker) and hardened into a re-runnable suite. Drives SAP GUI
...                 through the Scripting API: login lands on SAP Easy Access, the
...                 client table T000 is read through the ALV grid and asserted on
...                 technical columns (MANDT / LOGSYS, locale-independent), and an
...                 unknown transaction fails explicitly.
...
...                 Requires a reachable system + scripting enabled server-side
...                 (sapgui/user_scripting = TRUE) and client-side. Connection can be a
...                 SAP Logon entry name OR a connection string (/H/host/S/3200). Run:
...
...                   robot --pythonpath src ^
...                     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER ^
...                     -v "SAP_PASSWORD: Secret:***" -v SAP_CLIENT:001 -v SAP_LANGUAGE:EN ^
...                     tests/robot/ecc_explore_smoke.robot
...
...                 FR : Smoke ECC *exploratoire*, capturé interactivement via rf-mcp
...                 contre un vrai ABAP Platform A4H (ABAP Platform Trial sous Docker)
...                 puis figé en suite rejouable. Pilote SAP GUI via l'API Scripting :
...                 le login aboutit sur SAP Easy Access, la table des clients T000 est
...                 lue via la grille ALV et vérifiée sur des colonnes techniques
...                 (MANDT / LOGSYS, indépendantes de la langue), et une transaction
...                 inconnue échoue explicitement.

Resource            ../../resources/ecc_keywords.resource

Suite Setup         Open SAP And Log In
Suite Teardown      Close SAP

Test Tags           ecc    smoke    exploratory


*** Variables ***
${EXPECTED_LOGSYS}      A4HCLNT001    # Système logique du client 001 sur ce système A4H (override par -v)


*** Test Cases ***
Login Lands On SAP Easy Access
    [Documentation]    Le login aboutit sur le menu SAP Easy Access (transaction
    ...                SESSION_MANAGER) : vérification par le code de transaction actif,
    ...                indépendant de la langue.
    ${tx}=    Get Current Transaction
    Should Be Equal    ${tx}    SESSION_MANAGER

Data Browser Opens On SE16
    [Documentation]    Go To Transaction démarre bien le Data Browser SE16
    ...                (vérification locale-indépendante par la transaction active).
    Go To Transaction    SE16
    ${tx}=    Get Current Transaction
    Should Be Equal    ${tx}    SE16

Client Table T000 Lists The A4H Logon Client
    [Documentation]    Bascule SE16 en sortie grille ALV, lit la table des clients
    ...                T000 en liste de dicts, et vérifie sur des colonnes techniques
    ...                (indépendantes de la langue) que le client de référence SAP 000
    ...                et le client de connexion 001 y figurent, et que le système
    ...                logique du client 001 est ${EXPECTED_LOGSYS}.
    Use ALV Grid In Data Browser
    Display Table Contents    T000
    ${rows}=    Read Displayed Grid
    Should Not Be Empty    ${rows}
    ${clients}=    Evaluate    [r['MANDT'] for r in $rows]
    Should Contain    ${clients}    000
    Should Contain    ${clients}    001
    ${client_001}=    Evaluate    next(r for r in $rows if r['MANDT'] == '001')
    Should Be Equal    ${client_001}[LOGSYS]    ${EXPECTED_LOGSYS}

Unknown Transaction Is Reported
    [Documentation]    Une transaction inexistante ne démarre pas -> erreur explicite.
    ...                (En live, ce cas renvoie un statut de type 'S', d'où la
    ...                vérification par la transaction active et non par le type.)
    Run Keyword And Expect Error    *ZZZNOTREAL*
    ...    Go To Transaction    ZZZNOTREAL
