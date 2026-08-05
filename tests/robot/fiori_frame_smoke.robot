*** Settings ***
Documentation       Smoke **iframe launchpad** : exerce `Set Ui5 Frame` contre
...                 ``fixtures/shell_iframe_fixture.html``, un « shell » sans
...                 runtime UI5 qui embarque l'app UI5 dans une iframe, la
...                 structure de SAP Build Work Zone / cFLP. Vérifie que :
...                 (1) sans frame ciblée, la page top ne résout rien (préuve que
...                 le smoke teste bien quelque chose) ; (2) avec `Set Ui5 Frame`,
...                 résolution, clic, saisie et lecture de table fonctionnent dans
...                 l'app embarquée, sélecteurs préfixés ``>>>`` compris ;
...                 (3) les scénarios de fragilité observés dans l'écosystème
...                 (wdi5 a dû corriger deux fois la gestion des iframes
...                 Work Zone fin 2025/début 2026) : DEUX apps en frames (la
...                 portée d'une frame ne fuit jamais vers l'autre),
...                 rechargement de la frame (aucun contexte périmé, on
...                 ré-agit sans rien réinitialiser), et navigation de la
...                 frame vers une AUTRE app, où la résolution suit le nouveau
...                 contenu (``fixtures/shell_multi_iframe_fixture.html``).
...                 Nécessite le réseau (CDN UI5 pour l'app embarquée), aucun SAP.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_frame_smoke.robot

Library             OperatingSystem
Library             Browser
Library             SapFioriLibrary    ui5_timeout=60s

Suite Setup         Open Shell Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}
${FRAME}            iframe#application-frame
${FRAME_1}          iframe#app-frame-1
${FRAME_2}          iframe#app-frame-2


*** Keywords ***
Open Shell Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/shell_iframe_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    Set Browser Timeout    120s
    New Page       ${url}    wait_until=domcontentloaded
    # En file://, l'iframe a l'origine "null" : la frame est réellement
    # CROSS-ORIGIN (comme un vrai Work Zone) : le shell ne peut pas lire son
    # contentWindow. On attend donc la disponibilité via un sélecteur
    # frame-piercing Playwright (>>>), qui traverse les origines.
    Wait For Elements State    ${FRAME} >>> css=[id="myTable"]    visible    timeout=120s

Open Multi Shell Fixture
    # Go To (navigation de la page de suite) et non New Page : une page ouverte
    # PENDANT un test est refermée par l'auto-closing TEST de Browser à la fin
    # du test : les tests suivants retomberaient sur le shell mono-iframe.
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/shell_multi_iframe_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    Go To          ${url}
    Wait For Elements State    ${FRAME_1} >>> css=[id="myTable"]    visible    timeout=120s
    Wait For Elements State    ${FRAME_2} >>> css=[id="secondBtn"]    visible    timeout=120s


*** Test Cases ***
The Top Page Alone Sees No UI5 Controls
    [Documentation]    Garde-fou : le shell n'a pas de runtime UI5, donc sans
    ...                `Set Ui5 Frame`, le compteur de correspondances est nul.
    Set Ui5 Frame    ${EMPTY}
    ${count}=    Get Ui5 Match Count    controlType=sap.m.Button
    Should Be Equal As Integers    ${count}    0

Resolution Works Inside The Application Frame
    Set Ui5 Frame    ${FRAME}
    ${sel}=    Resolve Ui5 Control    controlType=sap.m.Button    properties={'text': 'Open Dialog'}
    Should Start With    ${sel}    ${FRAME} >>>
    Ui5 Control Should Be Visible    controlType=sap.m.Table

Actions And Reads Work Through The Frame
    Set Ui5 Frame    ${FRAME}
    Fill Ui5 Input    bonjour    id=nameInput
    ${rows}=    Read Ui5 Table    controlType=sap.m.Table
    Length Should Be    ${rows}    2
    Should Be Equal    ${rows}[1][Name]    Globex
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'Open Dialog'}
    Ui5 Control Should Be Visible    controlType=sap.m.Dialog
    [Teardown]    Set Ui5 Frame    ${EMPTY}

Each Frame Is Scoped Independently
    [Documentation]    Deux apps ouvertes dans deux frames (launchpad
    ...                multi-apps) : la résolution ciblée sur une frame ne voit
    ...                JAMAIS les contrôles de l'autre : les compteurs croisés
    ...                le prouvent dans les deux sens.
    Open Multi Shell Fixture
    Set Ui5 Frame    ${FRAME_2}
    Ui5 Control Should Be Visible    controlType=sap.m.Button    properties={'text': 'Second App Go'}
    ${tables}=    Get Ui5 Match Count    controlType=sap.m.Table
    Should Be Equal As Integers    ${tables}    0
    Set Ui5 Frame    ${FRAME_1}
    Ui5 Control Should Be Visible    controlType=sap.m.Table
    ${foreign}=    Get Ui5 Match Count    controlType=sap.m.Button    properties={'text': 'Second App Go'}
    Should Be Equal As Integers    ${foreign}    0

Frame Reload Leaves No Stale Context
    [Documentation]    La zone de fragilité classique (corrigée deux fois chez
    ...                wdi5) : après rechargement complet de la frame, la
    ...                résolution et les actions repartent sans réinitialiser
    ...                quoi que ce soit : aucun contexte périmé n'est retenu.
    Open Multi Shell Fixture
    Set Ui5 Frame    ${FRAME_1}
    Ui5 Control Should Be Visible    controlType=sap.m.Table
    Evaluate JavaScript    ${None}    () => { const f = document.getElementById('app-frame-1'); f.src = f.getAttribute('src'); }
    Wait For Elements State    ${FRAME_1} >>> css=[id="myTable"]    visible    timeout=120s
    Fill Ui5 Input    apres-reload    id=nameInput
    ${rows}=    Read Ui5 Table    controlType=sap.m.Table
    Length Should Be    ${rows}    2

Frame Navigation To Another App Re-Resolves The New Content
    [Documentation]    La frame navigue vers une AUTRE application (changement
    ...                d'app dans le launchpad) : la résolution suit le nouveau
    ...                contenu : les contrôles de l'ancienne app ont disparu,
    ...                ceux de la nouvelle se résolvent.
    Open Multi Shell Fixture
    Set Ui5 Frame    ${FRAME_1}
    Evaluate JavaScript    ${None}    () => { document.getElementById('app-frame-1').src = 'ui5_second_app_fixture.html'; }
    Wait For Elements State    ${FRAME_1} >>> css=[id="secondBtn"]    visible    timeout=120s
    Ui5 Control Should Be Visible    controlType=sap.m.Button    properties={'text': 'Second App Go'}
    ${tables}=    Get Ui5 Match Count    controlType=sap.m.Table
    Should Be Equal As Integers    ${tables}    0
    [Teardown]    Set Ui5 Frame    ${EMPTY}
