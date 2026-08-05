*** Settings ***
Documentation       Smoke **multi-session** live (registre par alias) contre l'ABAP
...                 Platform Trial A4H : prouve sur une vraie connexion COM le cycle
...                 `Create Gui Session` (2e fenêtre, même connexion, AUCUN re-login
...                 donc aucun popup multi-logon) → multiplexage `Switch Sap Session`
...                 (états de transaction indépendants entre les deux sessions) →
...                 `List Sap Sessions` (inventaire JSON-safe) → `Close Sap Session`
...                 (teardown isolé : l'autre alias et la connexion partagée restent
...                 debout). Suite AUTO-SUFFISANTE (aucune resource du projet).
...
...                 Exécution (`Secret` RF 7.4 : le mot de passe typé dès la ligne de
...                 commande n'apparaît jamais dans les logs, même en TRACE) :
...                 | robot --pythonpath src
...                 |     -v SAP_CONNECTION:/H/vhcala4hci/S/3200 -v SAP_USER:DEVELOPER
...                 |     -v "SAP_PASSWORD: Secret:<motdepasse>" -v SAP_CLIENT:001 -v SAP_LANGUAGE:EN
...                 |     tests/robot/ecc_multisession_smoke.robot

Library             SapEccLibrary    screenshots_on_error=${True}    default_timeout=30s

Suite Setup         Open SAP And Log In
Suite Teardown      Close SAP Cleanly


*** Variables ***
# --- Paramètres de connexion (surchargables via -v en ligne de commande) --------
${SAP_CONNECTION}       /H/vhcala4hci/S/3200
${SAP_USER}             DEVELOPER
${SAP_PASSWORD}         ${EMPTY}      # OBLIGATOIRE : fournir via -v "SAP_PASSWORD: Secret:<motdepasse>"
${SAP_CLIENT}           001
${SAP_LANGUAGE}         EN

# --- Localisateurs SAP GUI (jamais dans les cas de test ; relevés live A4H) ------
${MULTI_LOGON_RADIO}    wnd[1]/usr/radMULTI_LOGON_OPT1


*** Test Cases ***
Second Window Session Opens Without Any Re-Login
    [Documentation]    `Create Gui Session` ouvre une 2e fenêtre sur la connexion
    ...                ACTIVE (l'équivalent scripté de /o) : aucun nouveau login,
    ...                donc aucun popup multi-logon. Le nouvel alias devient actif
    ...                et est immédiatement pilotable.
    Create Gui Session    verif
    ${active}=    Get Active Sap Session
    Should Be Equal    ${active}    verif
    Run Transaction    SE16
    ${tx}=    Get Current Transaction
    Should Be Equal    ${tx}    SE16

Sessions Multiplex With Independent State
    [Documentation]    Le scénario cible « agir dans une session, vérifier dans
    ...                l'autre » : chaque alias garde SA transaction active, la
    ...                bascule est explicite, l'état ne fuit jamais d'une session
    ...                à l'autre.
    ${tx_verif}=    Get Current Transaction
    Should Be Equal    ${tx_verif}    SE16
    Switch Sap Session    default
    ${tx_default}=    Get Current Transaction
    Should Not Be Equal    ${tx_default}    SE16
    ...    msg=La session « default » a hérité de l'état de « verif » : le registre fuit.
    Switch Sap Session    verif
    ${tx_back}=    Get Current Transaction
    Should Be Equal    ${tx_back}    SE16

List Reports Both Sessions Json Safe
    [Documentation]    `List Sap Sessions` inventorie le registre : deux alias
    ...                connectés, le même utilisateur, exactement un actif,
    ...                uniquement des chaînes/booléens (contrainte rf-mcp).
    ${sessions}=    List Sap Sessions
    Length Should Be    ${sessions}    2
    FOR    ${entry}    IN    @{sessions}
        Should Be True    ${entry}[connected]
        Should Be Equal    ${entry}[user]    ${SAP_USER}
    END
    ${actives}=    Evaluate    [e['alias'] for e in $sessions if e['active']]
    Length Should Be    ${actives}    1

Closing One Alias Leaves The Other Alive
    [Documentation]    Teardown isolé : fermer « verif » ne ferme QUE sa fenêtre,
    ...                « default » (même connexion) reste debout et pilotable, et
    ...                redevient l'alias actif.
    Close Sap Session    verif
    ${active}=    Get Active Sap Session
    Should Be Equal    ${active}    default
    ${sessions}=    List Sap Sessions
    ${aliases}=    Evaluate    [e['alias'] for e in $sessions if e['connected']]
    Should Not Contain    ${aliases}    verif
    # la session restante est toujours vivante : un aller-retour de transaction
    Run Transaction    SE16
    ${tx}=    Get Current Transaction
    Should Be Equal    ${tx}    SE16


*** Keywords ***
Open SAP And Log In
    [Documentation]    Suite Setup. Lance le Logon Pad, ouvre la connexion (chaîne
    ...                directe ou entrée enregistrée), s'authentifie (mot de passe
    ...                jamais journalisé) et gère le popup « connexion multiple ».
    ...                Cette session historique EST l'alias « default » du registre.
    # Should Not Be Equal (et non Should Not Be Empty) : tolère un mot de passe
    # de type Secret RF 7.4, qui n'a pas de longueur mesurable.
    Should Not Be Equal    ${SAP_PASSWORD}    ${EMPTY}
    ...    msg=SAP_PASSWORD est vide : fournissez-le via -v "SAP_PASSWORD: Secret:<motdepasse>".
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

Close SAP Cleanly
    [Documentation]    Suite Teardown. Ferme toutes les sessions du registre (best-
    ...                effort), quitte (/nex, tolérant) et arrête le Logon Pad :
    ...                aucune étape ne masque l'échec réel d'un test.
    Run Keyword And Ignore Error    Close All Sap Sessions
    Run Keyword And Ignore Error    Run Transaction    /nex
    Close Sap Logon

Handle Multiple Logon Popup
    [Documentation]    SAP affiche un dialogue « licence / connexion multiple » quand
    ...                le même utilisateur est déjà connecté ailleurs. On choisit
    ...                « continuer avec cette connexion » si présent ; sinon, rien.
    ${present}=    Run Keyword And Return Status    Element Should Be Present    ${MULTI_LOGON_RADIO}
    IF    ${present}
        Select Radio Button    ${MULTI_LOGON_RADIO}
        Click Element    wnd[1]/tbar[0]/btn[0]
        Wait Until Busy Done
    END
