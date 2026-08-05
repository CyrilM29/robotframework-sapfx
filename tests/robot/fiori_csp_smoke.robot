*** Settings ***
Documentation       Smoke **injection sous CSP stricte** : la page de
...                 ``fixtures/csp_fixture.html`` n'autorise en scripts QUE le CDN
...                 UI5 et les balises porteuses de son nonce, pas de
...                 ``unsafe-inline``, pas de ``unsafe-eval``. Le premier test
...                 prouve que la politique bloque réellement un ``<script>``
...                 injecté au DOM sans nonce ; les suivants prouvent que le
...                 bundle ``__SAPFX`` (injecté via l'evaluate Playwright, canal
...                 CDP, hors de portée de la CSP de page) et les moteurs
...                 role/xpath fonctionnent quand même. Conclusion opérationnelle
...                 (docs/hardening-test-environment.md §4) : AUCUN
...                 assouplissement CSP n'est à demander sur un système testé,
...                 la posture CSP durcie vers laquelle SAP pousse (ligne
...                 legacy-free) ne gêne pas l'outillage.
...                 Nécessite le réseau (CDN OpenUI5), aucun SAP.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_csp_smoke.robot

Library             OperatingSystem
Library             Browser
Library             SapFioriLibrary    ui5_timeout=60s

Suite Setup         Open Csp Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Keywords ***
Open Csp Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/csp_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    Set Browser Timeout    120s
    New Page       ${url}    wait_until=domcontentloaded
    Wait For Function    () => window.__fixtureReady === true    timeout=120s


*** Test Cases ***
Page CSP Actually Blocks Non Nonce Script Injection
    [Documentation]    Garde-fou : sans lui, les tests suivants ne prouveraient
    ...                rien. Un ``<script>`` inline ajouté au DOM sans le nonce
    ...                de la page doit être bloqué par la CSP (et la violation
    ...                comptée par l'écouteur du fixture).
    ${blocked}=    Evaluate JavaScript    ${None}
    ...    () => new Promise((res) => { const s = document.createElement('script'); s.textContent = 'window.__cspLeak = true'; document.head.appendChild(s); setTimeout(() => res(window.__cspLeak !== true && window.__cspViolations > 0), 300); })
    Should Be True    ${blocked}    msg=La CSP du fixture n'a pas bloqué un script sans nonce : la politique n'est pas effective

Sapfx Bundle Injects And Role Engine Works Under Strict CSP
    [Documentation]    Le canal d'injection (evaluate Playwright → CDP) n'est pas
    ...                soumis à la CSP de page : résolution + clic fonctionnent.
    Ui5 Control Should Be Visible    controlType=sap.m.Button    properties={'text': 'CSP Go'}
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'CSP Go'}
    ${pressed}=    Evaluate JavaScript    ${None}    () => window.__pressed === true
    Should Be True    ${pressed}
    Fill Ui5 Input    bonjour    controlType=sap.m.Input    properties={'placeholder': 'csp input'}

Xpath Engine And Page Tree Work Under Strict CSP
    ${sel}=    Resolve Ui5 By Xpath    //Button[@text='CSP Go']
    Should Not Be Empty    ${sel}
    ${tree}=    Get Ui5 Page Tree
    Should Contain    ${tree}    Button
