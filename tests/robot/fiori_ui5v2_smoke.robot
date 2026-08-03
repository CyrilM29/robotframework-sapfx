*** Settings ***
Documentation       Smoke **compatibilité UI5 2.x** : exerce SapFioriLibrary contre le
...                 runtime OpenUI5 **2.0 nightly** (CDN officiel ``sdk.openui5.org/
...                 nightly/2``) chargé par ``fixtures/ui5_v2_fixture.html``. 2.x
...                 supprime les APIs dépréciées de la baseline 1.136 — dont
...                 ``Element.registry`` et la façade ``sap.ui.getCore()`` : ce smoke
...                 prouve que ``registryForEach`` passe bien par le module
...                 ``sap/ui/core/ElementRegistry`` (branche 2.x) et qu'aucun de nos
...                 chemins ne dépend d'une API supprimée. Pendant symétrique de
...                 ``fiori_legacy_smoke.robot`` (1.60) à l'autre bout du spectre.
...                 Nécessite le réseau (CDN SAP nightly — INSTABLE par nature :
...                 un échec ici signale une dérive 2.x à investiguer, pas
...                 forcément une régression de la bibliothèque). Aucun SAP.
...                 Exécution :  robot --pythonpath src tests/robot/fiori_ui5v2_smoke.robot

Library             OperatingSystem
Library             Browser
Library             SapFioriLibrary    ui5_timeout=60s

Suite Setup         Open V2 Fixture
Suite Teardown      Close Browser


*** Variables ***
${HEADLESS}         ${True}


*** Keywords ***
Open V2 Fixture
    ${fixture}=    Normalize Path    ${CURDIR}/fixtures/ui5_v2_fixture.html
    ${url}=        Evaluate    pathlib.Path(r"${fixture}").as_uri()    pathlib
    New Browser    chromium    headless=${HEADLESS}
    Set Browser Timeout    120s
    New Page       ${url}    wait_until=domcontentloaded
    Wait For Function    () => window.__fixtureReady === true    timeout=120s


*** Test Cases ***
Runtime Is A 2.x Build Without The Legacy Registry
    [Documentation]    Garde-fou : version 2.x, et ``Element.registry`` (déprécié
    ...                en 1.120, hors baseline) absent — sinon ce smoke ne
    ...                prouverait pas la branche module ``ElementRegistry``.
    # ``sap.ui.version`` (global) n'existe plus en 2.x — c'est déjà un signal ;
    # la version officielle s'obtient par le module VersionInfo (API 2.x).
    ${version}=    Evaluate JavaScript    ${None}
    ...    () => new Promise((res) => sap.ui.require(['sap/ui/VersionInfo'], (VI) => VI.load().then((i) => res(i.version)).catch(() => res('load-failed')), () => res('module-missing')))
    Should Match Regexp    ${version}    ^2\\.    msg=Runtime is not a 2.x build (got ${version})
    ${module_registry}=    Evaluate JavaScript    ${None}
    ...    () => { const R = sap.ui.require('sap/ui/core/ElementRegistry'); const E = sap.ui.require('sap/ui/core/Element'); return !!R && typeof R.forEach === 'function' && !(E && E.registry); }
    Should Be True    ${module_registry}    msg=ElementRegistry module missing or legacy registry still present

Role Engine Resolves Controls Via The ElementRegistry Module
    [Documentation]    La résolution role/propriétés fonctionne sur le registre 2.x.
    Ui5 Control Should Be Visible    controlType=sap.m.Button    properties={'text': 'V2 Go'}
    Click Ui5 Control    controlType=sap.m.Button    properties={'text': 'V2 Go'}
    ${pressed}=    Evaluate JavaScript    ${None}    () => window.__pressed === true
    Should Be True    ${pressed}

Inputs And Tables Work On The 2.x Runtime
    Fill Ui5 Input    bonjour    controlType=sap.m.Input    properties={'placeholder': 'v2 input'}
    ${rows}=    Read Ui5 Table    controlType=sap.m.Table
    Length Should Be    ${rows}    2
    Should Be Equal    ${rows}[0][Name]    Acme

Xpath Engine Works On The 2.x Runtime
    ${sel}=    Resolve Ui5 By Xpath    //Table//Text[@text='Globex']
    Should Not Be Empty    ${sel}
    ${xp}=    Get Ui5 Xpath    id=v2Table
    ${roundtrip}=    Resolve Ui5 By Xpath    ${xp}
    Should Be Equal    ${roundtrip}    css=[id="v2Table"]
